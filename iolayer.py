"""
PC-BASIC 3.23 - iolayer.py
File and Device I/O operations 

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3.
"""

import os
import copy
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from bytestream import ByteStream
import config
import oslayer
import error
import console
import util
import state
import memory
import backend
import serial_socket
import printer
import cassette

# file numbers
state.io_state.files = {}
# fields are preserved on file close, so have a separate store
state.io_state.fields = {}

# maximum file number = maximum number of open files
# this is a command line option -f
max_files = 3
# maximum record length (-s)
max_reclen = 128

# buffer sizes (/c switch in GW-BASIC)
serial_in_size = 256
serial_out_size = 128

# GW-BASIC FILE CONTROL BLOCK structure:
# source: IBM Basic reference 1982 (for BASIC-C, BASIC-D, BASIC-A) appendix I-5
# byte  length  description
# 0     1       Mode 1-input 2-output 4-random 16-append
# 1     38      MSDOS FCB:
# ------------------------
# 0     1       Drive number (0=Default, 1=A, etc)
# 01h   8       blank-padded file name
# 09h   3       blank-padded file extension
# 0Ch   2       current block number
# 0Eh   2       logical record size
# 10h   4       file size
# 14h   2       date of last write (see #01666 at AX=5700h)
# 16h   2       time of last write (see #01665 at AX=5700h) (DOS 1.1+)
# 18h   8       reserved (see #01347,#01348,#01349,#01350,#01351)
# 20h   1       record within current block
# 21h   4       random access record number (if record size is > 64 bytes, high byte is omitted)
# ------------------------
# 39    2       For seq files, the number of sectors read or written. For random files, 1+the last record read or written
# 41    1       Number of bytes in sector when read or written
# 42    1       Number of bytes left in input buffer
# 43    3       (reserved)
# 46    1       Drive number 0=A, 1=B, 248=LPT3,2 250=COM2,1 252=CAS1 253=LPT1 254=SCRN 255=KYBD
# 47    1       Device width
# 48    1       Position in buffer for PRINT#
# 49    1       internal use during LOAD and SAVE
# 50    1       Output position used during tab expansion
# 51    128     Physical data buffer for transfer between DOS and BASIC. Can examine this data in seq I/O mode.
# 179   2       Variable length record size, default 128
# 181   2       Current physical record number
# 183   2       Current logical record number
# 185   1       (reserved)
# 186   2       Position for PRINT#, INPUT#, WRITE#
# 188   n       FIELD buffer, default length 128 (given by /s:n)

nullstream = open(os.devnull, 'w')

def prepare():
    """ Initialise iolayer module. """
    global max_files
    if config.options['max-files'] != None:
        max_files = min(16, config.options['max-files'])
    # console
    backend.devices['SCRN:'] = SCRNDevice()
    backend.devices['KYBD:'] = KYBDDevice()
    backend.scrn_file = backend.devices['SCRN:'].device_file
    backend.kybd_file = backend.devices['KYBD:'].device_file
    # parallel devices - LPT1: must always be defined
    print_trigger = config.options['print-trigger']
    backend.devices['LPT1:'] = LPTDevice(config.options['lpt1'], nullstream, print_trigger)
    backend.devices['LPT2:'] = LPTDevice(config.options['lpt2'], None, print_trigger)
    backend.devices['LPT3:'] = LPTDevice(config.options['lpt3'], None, print_trigger)
    backend.lpt1_file = backend.devices['LPT1:'].device_file
    # serial devices
    global max_reclen, serial_in_size
    if config.options['max-reclen'] != None:
        max_reclen = config.options['max-reclen']
        max_reclen = max(1, min(32767, max_reclen))
    if config.options['serial-buffer-size'] != None:
        serial_in_size = config.options['serial-buffer-size']
    backend.devices['COM1:'] = COMDevice(config.options['com1'], max_reclen, serial_in_size)
    backend.devices['COM2:'] = COMDevice(config.options['com2'], max_reclen, serial_in_size)
    # cassette
    backend.devices['CAS1:'] = CASDevice(config.options['cas1'])
    # disk devices
    #TODO: move from oslayer


############################################################################
# General file manipulation

#TODO: enable 'with' for open_file?

def open_file(number, description, filetype, mode='I', access='R', lock='', reclen=128, defext=''):
    """ Open a file on a device specified by description. """
    # TODO: defext can be handled by Disk device now that we know filetype; no need to carry it for everyone
    if (not description) or (number < 0) or (number > max_files):
        # bad file number; also for name='', for some reason
        raise error.RunError(52)
    if number in state.io_state.files:
        # file already open
        raise error.RunError(55)
    name, mode = str(description), mode.upper()
    inst = None
    split_colon = name.split(':')
    if len(split_colon) > 1: # : found
        dev_name = split_colon[0].upper() + ':'
        dev_param = ''.join(split_colon[1:])
    else:
        # TODO: shld be current_device, can also be e.g. CAS1: if no disks present
        dev_name = oslayer.current_drive.upper() + ':'
        dev_param = name
    print dev_name, dev_param
    try:
        # check if device exists and allows the requested mode
        # if not exists, raise KeyError
        device = backend.devices[dev_name]
        if not device:
            if len(dev_name) > 2:
                # device unavailable
                raise error.RunError(68)
            else:
                # for drive letters: path not found
                raise error.RunError(76)
        return device.open(number, dev_param, filetype, mode, access, lock, reclen, defext)
    except KeyError:
        if len(dev_name) > 2:
            # devname could be A:, B:, C:, etc.. but anything longer is an error (bad file number, for some reason).
            raise error.RunError(52)

def get_file(num, mode='IOAR'):
    """ Get the file object for a file number and check allowed mode. """
    try:
        the_file = state.io_state.files[num]
    except KeyError:
        # bad file number
        raise error.RunError(52)
    if the_file.mode.upper() not in mode:
        raise error.RunError(54)
    return the_file

def check_file_not_open(path):
    """ Raise an error if the file is open. """
    # TODO: this should be a disk-only thing!
    for f in state.io_state.files:
        if oslayer.native_path(path) == state.io_state.files[f].name:
            raise error.RunError(55)

def close_file(num):
    """ Close a regular file. """
    if num > 0:
        try:
            state.io_state.files[num].close()
            del state.io_state.files[num]
        except KeyError:
            pass

def close_all():
    """ Close all regular files. """
    open_files = state.io_state.files.keys()
    for num in open_files:
        close_file(num)

#D?
def close_system_files():
    """ Close all files including system files. """
    for f in state.io_state.files.values():
        f.close()
    state.io_state.files = {}

############################################################################
# Locking (disk only)

def find_files_by_name(name):
    """ Find all file numbers open to the given filename."""
    return [state.io_state.files[f] for f in state.io_state.files if state.io_state.files[f].name == name]

def lock_records(nr, start, stop):
    """ Try to lock a range of records in a file. """
    thefile = get_file(nr)
    if thefile.name in backend.devices:
        # permission denied
        raise error.RunError(70)
    lock_list = set()
    for f in find_files_by_name(thefile.name):
        lock_list |= f.lock_list
    if isinstance(thefile, TextFile):
        bstart, bstop = 0, -1
        if lock_list:
            raise error.RunError(70)
    else:
        bstart, bstop = (start-1) * thefile.reclen, stop*thefile.reclen - 1
        for start_1, stop_1 in lock_list:
            if stop_1 == -1 or (bstart >= start_1 and bstart <= stop_1) or (bstop >= start_1 and bstop <= stop_1):
                raise error.RunError(70)
    thefile.lock_list.add((bstart, bstop))

def unlock_records(nr, start, stop):
    """ Unlock a range of records in a file. """
    thefile = get_file(nr)
    if thefile.name in backend.devices:
        # permission denied
        raise error.RunError(70)
    if isinstance(thefile, TextFile):
        bstart, bstop = 0, -1
    else:
        bstart, bstop = (start-1) * thefile.reclen, stop*thefile.reclen - 1
    # permission denied if the exact record range wasn't given before
    try:
        thefile.lock_list.remove((bstart, bstop))
    except KeyError:
        raise error.RunError(70)

def request_lock(name, lock, access):
    """ Try to lock a file. """
    same_files = find_files_by_name(name)
    if not lock:
        # default mode; don't accept default mode if SHARED/LOCK present
        for f in same_files:
            if f.lock:
                raise error.RunError(70)
    elif lock == 'RW':
        # LOCK READ WRITE
        raise error.RunError(70)
    elif lock == 'S':
        # SHARED
        for f in same_files:
            if not f.lock:
                raise error.RunError(70)
    else:
        # LOCK READ or LOCK WRITE
        for f in same_files:
            if f.access == lock or lock == 'RW':
                raise error.RunError(70)




############################################################################
# Device files
#
#  Some devices have a master file, where newly opened files inherit
#  width (and other?) settings from this file
#  For example, WIDTH "SCRN:", 40 works directly on the console,
#  whereas OPEN "SCRN:" FOR OUTPUT AS 1: WIDTH #1,23 works on the wrapper file
#  but does ot affect other files on SCRN: nor the console itself.
#  Likewise, WIDTH "LPT1:" works on LLIST etc and on lpt1 for the next time it's opened.


############################################################################

def parse_protocol_string(arg):
    """ Retrieve protocol and options from argument. """
    argsplit = arg.split(':', 1)
    if len(argsplit) == 1:
        addr, val = None, argsplit[0]
    else:
        addr, val = argsplit[0].upper(), ''.join(argsplit[1:])
    return addr, val


class Device(object):
    """ Device interface for master-file devices. """

    allowed_modes = ''
    allowed_protocols = ()

    def __init__(self):
        """ Set up device. """
        self.device_file = None

    def open(self, number, param, filetype, mode, access, lock, reclen, defext):
        """ Open a file on the device. """
        if mode not in self.allowed_modes:
            # bad file mode
            raise error.RunError(54)
        new_file = self.clone_master(number, mode, access, lock, reclen)
        state.io_state.files[number] = new_file
        return new_file

    def clone_master(self, number, mode, access, lock='', reclen=128):
        """ Clone device object as device file object (helper method). """
        inst = copy.copy(self.device_file)
        inst.number = number
        inst.access = access
        inst.mode = mode
        inst.lock = lock
        inst.reclen = reclen
        if number != 0:
            state.io_state.files[number] = inst
        return inst


class SCRNDevice(Device):
    """ Screen device (SCRN:) """
    
    allowed_modes = 'ORS'

    def __init__(self):
        """ Initialise screen device. """
        # open a master file on the screen
        self.device_file = SCRNFile()


class KYBDDevice(Device):
    """ Keyboard device (KYBD:) """
    
    allowed_modes = 'IRL'

    def __init__(self):
        """ Initialise keyboard device. """
        # open a master file on the keyboard
        self.device_file = KYBDFile()


class LPTDevice(Device):
    """ Parallel port or printer device (LPTn:) """

    allowed_protocols = ('PRINTER', 'PARPORT', 'FILE')
    allowed_modes = 'ORS'

    def __init__(self, arg, default_stream, flush_trigger):
        """ Initialise LPTn: device. """
        addr, val = parse_protocol_string(arg)
        if val == None or addr and addr not in self.allowed_protocols:
            logging.warning('Could not attach %s to LPT device', arg)
        elif addr == 'FILE':
            try:
                if not os.path.exists(val):
                    open(val, 'wb').close()
                self.stream = open(val, 'r+b')
            except (IOError, OSError) as e:
                logging.warning('Could not attach file %s to LPT device: %s', val, str(e))
                self.stream = default_stream
        elif addr == 'PARPORT':
            # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
           self.stream = serial_socket.parallel_port(val)
        else:
            # 'PRINTER' is default
            self.stream = printer.PrinterStream(val)
        self.device_file = LPTFile(self.stream, flush_trigger)
        self.device_file.flush_trigger = flush_trigger

    def open(self, number, param, filetype, mode, access, lock, reclen, defext):
        """ Open a file on LPTn: """
        f = Device.open(self, number, param, filetype, mode, access, lock, reclen, defext)
        # don't trigger flushes on LPT files, just on the device directly
        f.flush_trigger = 'close'
        return f


class COMDevice(Device):
    """ Serial port device (COMn:). """

    allowed_protocols = ('PORT', 'SOCKET')
    allowed_modes = 'IOARLS'

    def __init__(self, arg, max_reclen, serial_in_size):
        """ Initialise COMn: device. """
        addr, val = parse_protocol_string(arg)
        if val == None or addr and addr not in self.allowed_protocols:
            logging.warning('Could not attach %s to COM device', arg)
        elif addr == 'SOCKET':
            self.stream = serial_socket.serial_for_url('socket://'+val)
        else:
            # 'PORT' is default
            # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows. Or anything supported by serial_for_url (RFC 2217 etc)
            self.stream = serial_socket.serial_for_url(val)
        # FIXME: name not defined
        self.device_file = COMFile(self.stream)

    def open(self, number, param, filetype, mode, access, lock, reclen, defext):
        """ Open a file on COMn: """
        # open the COM port
        if self.stream._isOpen:
            # file already open
            raise error.RunError(55)
        else:
            try:
                self.stream.open()
            except serial_socket.SerialException:
                # device timeout
                raise error.RunError(24)
        try:
            self.set_parameters(param)
        except Exception:
            self.stream.close()
            raise
        return Device.open(self, number, param, filetype, mode, access, lock, reclen, defext)

    def set_parameters(self, param):
        """ Set serial port connection parameters """
        max_param = 10
        param_list = param.upper().split(',')
        if len(param_list) > max_param:
            # Bad file name
            raise error.RunError(64)
        param_list += ['']*(max_param-len(param_list))
        speed, parity, data, stop, RS, CS, DS, CD, LF, PE = param_list
        # set speed
        if speed not in ('75', '110', '150', '300', '600', '1200',
                          '1800', '2400', '4800', '9600', ''):
            # Bad file name
            raise error.RunError(64)
        speed = int(speed) if speed else 300
        self.stream.baudrate = speed
        # set parity
        if parity not in ('S', 'M', 'O', 'E', 'N', ''):
            raise error.RunError(64)
        parity = parity or 'E'
        self.stream.parity = parity
        # set data bits
        if data not in ('4', '5', '6', '7', '8', ''):
            raise error.RunError(64)
        data = int(data) if data else 7
        bytesize = data + (parity != 'N')
        if bytesize not in range(5, 9):
            raise error.RunError(64)
        self.stream.bytesize = bytesize
        # set stopbits
        if stop not in ('1', '2', ''):
            raise error.RunError(64)
        if not stop:
            stop = 2 if (speed in (75, 110)) else 1
        else:
            stop = int(stop)
        self.stream.stopbits = stop
        if (RS not in ('RS', '') or CS[:2] not in ('CS', '')
            or DS[:2] not in ('DS', '') or CD[:2] not in ('CD', '')
            or LF not in ('LF', '') or PE not in ('PE', '')):
            raise error.RunError(64)
        # set LF
        self.stream.linefeed = (LF != '')


class DiskDevice(object):
    """ Disk device (A:, B:, C:, ...) """

    allowed_modes = 'IORSL'

    # posix access modes for BASIC modes INPUT, OUTPUT, RANDOM, APPEND
    # and internal LOAD and SAVE modes
    access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab', 'L': 'rb', 'S': 'wb' }
    # posix access modes for BASIC ACCESS mode for RANDOM files only
    access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }

    def __init__(self, cwd):
        """ Initialise a disk device. """
        # current working directory on this drive
        self.drive_cwd = cwd

    def open(self, number, param, filetype, mode, access, lock, reclen, defext):
        """ Open a file on a disk drive. """
        # translate the file name to something DOS-ish if necessary
        if mode in ('O', 'A'):
            # don't open output or append files more than once
            check_file_not_open(param)
        if mode in ('I', 'L'):
            name = oslayer.native_path(param, defext)
        else:
            # random files: try to open matching file
            # if it doesn't exist, create an all-caps 8.3 file name
            name = oslayer.native_path(param, defext, make_new=True)
        # obtain a lock
        request_lock(name, lock, access)
        # open the file
        fhandle = self.open_stream(name, mode, access)
        # apply the BASIC file wrapper
        # TODO: instead of S, L -> use filetype in ('P', 'B', 'M')
        #        but check what happens with ASCII program files
        if filetype in ('S', 'L'): # save, load
            inst = RawFile(fhandle, name, number, mode, access, lock)
        elif mode in ('I', 'O', 'A'):
            inst = TextFile(fhandle, name, number, mode, access, lock)
        else:
            inst = RandomFile(fhandle, name, number, mode, access, lock, reclen)

    def open_stream(self, native_name, mode, access):
        """ Open a stream on disk by os-native name with BASIC mode and access level. """
        name = str(native_name)
        if (access and mode == 'R'):
            posix_access = self.access_access[access]
        else:
            posix_access = self.access_modes[mode]
        try:
            # create file if in RANDOM or APPEND mode and doesn't exist yet
            # OUTPUT mode files are created anyway since they're opened with wb
            if ((mode == 'A' or (mode == 'R' and access == 'RW')) and
                    not os.path.exists(name)):
                open(name, 'wb').close()
            if mode == 'A':
                # APPEND mode is only valid for text files (which are seekable);
                # first cut of EOF byte, if any.
                f = open(name, 'r+b')
                try:
                    f.seek(-1, 2)
                    if f.read(1) == '\x1a':
                        f.seek(-1, 1)
                        f.truncate()
                except IOError:
                    pass
                f.close()
            return open(name, posix_access)
        except EnvironmentError as e:
            oslayer.handle_oserror(e)
        except TypeError:
            # bad file number, which is what GW throws for open chr$(0)
            raise error.RunError(52)


class CASDevice(object):
    """ Cassette tape device (CASn:) """

    allowed_protocols = ('CAS', 'WAV')
    allowed_modes = 'IOLS'

    def __init__(self, arg):
        """ Initialise tape device. """
        addr, val = parse_protocol_string(arg)
        ext = val.split('.')[-1].upper()
        if not val:
            self.tapestream = None
        elif addr == 'WAV' or (addr != 'CAS' and ext == 'WAV'):
            # if unspecified, determine type on the basis of filename extension
            self.tapestream = cassette.WAVStream(val)
        else:
            # 'CAS' is default
            self.tapestream = cassette.CASStream(val)

    def open(self, number, param, filetype, mode, access, lock, reclen, defext):
        """ Open a file on tape. """
        if mode == 'L':
            file_types = ('A','B','P','M')
        elif mode in ('I', 'O'):
            file_types = ('D', )
        elif mode == 'S':
            # FIXME - need a file type parameter so that we know we're saving
            # (instead of writing magic byte)
            # bytecode or protected or bsave
            # also need to provide length, seg, offs for these
            file_types = ('A', )
        if not self.tapestream:
            # device unavailable
            raise error.RunError(68)
        else:
            self.tapestream.open(param, file_types, mode, length=0, seg=0, offs=0)


#################################################################################
# file classes


class NullFile(object):
    """ Base file class. """

    def __init__(self):
        """ Initialise null file. """
        self.number = 0
        self.name = ''

    def __del__(self):
        self.close()

    def close(self):
        """ Close this file. """
        pass

    def lof(self):
        """ LOF: bad file mode. """
        raise error.RunError(54)

    def loc(self):
        """ LOC: bad file mode. """
        raise error.RunError(54)

    def eof(self):
        """ EOF: bad file mode. """
        raise error.RunError(54)

    def write(self, s):
        """ Write string s to device. """
        pass

    def write_line(self, s):
        """ Write string s and CR/LF to device """
        pass

    def set_width(self, new_width=255):
        """ Set device width. """
        pass

    def read_line(self):
        """ Read a line from device. """
        return ''

    def read_chars(self, n):
        """ Read a list of chars from device. """
        return []

    def read(self, n):
        """ Read a string from device. """
        return ''

    def end_of_file(self):
        """ Check for end-of-file. """
        return False


class RawFile(object):
    """ File class for raw access to underlying stream. """

    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        """ Setup the basic properties of the file. """
        # width=255 means line wrap
        self.fhandle = fhandle
        self.name = name
        self.number = number
        self.mode = mode.upper()
        self.access = access
        self.lock = lock
        self.lock_list = set()    
        # TODO: let open_file handle this
        if number != 0:
            state.io_state.files[number] = self
    
    # set_width
    # width
    # col
    # lof
    # loc
    # eof

    def close(self):
        """ Close the file. """
        try:
            self.fhandle.flush()
        except (IOError, ValueError):
            # ignore errors on flushing
            pass    

    def read_chars(self, num=-1):
        """ Read num chars as a list. If num==-1, read all available. """
        return list(self.fhandle.read(num))

    def read(self, num=-1):
        """ Read num chars as a string. If num==-1, read all available. """
        return self.fhandle.read(num)

    def read_line(self):
        """ Read a single line. """
        out = bytearray('')
        while len(out) < 255:
            c = self.read(1)
            if c == '\r':
                break
            out += c
        return out

    def peek_char(self):
        """ Get next char to be read. """
        s = self.fhandle.read(1)
        self.fhandle.seek(-len(s), 1)
        return s

    def tell(self):
        """ Get position of file pointer. """
        return self.fhandle.tell()

    def seek(self, num, from_where=0):
        """ Move file pointer. """
        self.fhandle.seek(num, from_where)

    def write(self, s):
        """ Write string or bytearray to file. """
        self.fhandle.write(str(s))

    def write_line(self, s=''):
        """ Write string or bytearray and newline to file. """ 
        self.write(str(s) + '\r\n')

    def end_of_file(self):
        """ Return whether the file pointer is at the end of file. """
        return self.peek_char() == ''

    def flush(self):
        """ Write contents of buffers to file. """
        self.fhandle.flush()

    def truncate(self):
        """ Delete file from pointer position onwards. """
        self.fhandle.truncate()


class RandomBase(RawFile):
    """ Random-access file base object. """

    # FIELD overflow
    overflow_error = 50

    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        """ Initialise random-access file. """
        RawFile.__init__(self, fhandle, name, number, mode, access, lock)
        self.reclen = reclen
        # replace with empty field if already exists
        try:
            self.field = state.io_state.fields[self.number]
        except KeyError:
            self.field = bytearray()
            state.io_state.fields[self.number] = self.field
        if self.number > 0:
            self.field_address = memory.field_mem_start + (self.number-1)*memory.field_mem_offset
        else:
            self.field_address = -1
        self.field[:] = bytearray('\x00')*reclen
        # open a pseudo text file over the buffer stream
        # to make WRITE# etc possible
        # all text-file operations on a RANDOM file number actually work on the FIELD buffer
        self.field_text_file = TextFile(ByteStream(self.field))
        self.field_text_file.col = 1
        # width=255 means line wrap
        self.field_text_file.width = 255

    def read_line(self):
        """ Read line from FIELD buffer. """
        # FIELD overflow happens if last byte in record is actually read
        if self.field_text_file.fhandle.tell() >= self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read_line()

    def read_chars(self, num=-1):
        """ Read num characters as list. """
        return list(self.read(num))

    def read(self, num=-1):
        """ Read num chars as a string, from FIELD buffer. """
        if num==-1 or self.field_text_file.fhandle.tell() + num > self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read(num)

    def write(self, s):
        """ Write one or more chars to FIELD buffer. """
        ins = StringIO(s)
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell() < len(s):
            raise error.RunError(self.overflow_error)

    def peek_char(self):
        """ Get next char to be read from FIELD buffer. """
        return self.field_text_file.peek_char()

    def seek(self, n, from_where=0):
        """ Get file pointer location in FIELD buffer. """
        return self.field_text_file.seek(n, from_where)

    def truncate(self):
        """ Not implemented. """
        # this is only used when writing chr$(8)
        # not sure how to implement for random files
        pass

    @property
    def col(self):
        """ Get current column. """
        return self.field_text_file.col

    @property
    def width(self):
        """ Get file width. """
        return self.field_text_file.width

    def set_width(self, new_width=255):
        """ Set file width. """
        self.field_text_file.width = new_width


#################################################################################
# Disk files

class TextFile(RawFile):
    """ Text file on disk device. """

    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        """ Initialise text file object. """
        RawFile.__init__(self, fhandle, name, number, mode, access, lock)
        if self.mode in ('I', 'O', 'R', 'S', 'L'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        # width=255 means unlimited
        self.width = 255
        self.col = 1

    def close(self):
        """ Close text file. """
        if self.mode in ('O', 'A', 'S'):
            # write EOF char
            self.fhandle.write('\x1a')
        RawFile.close(self)
        if self.fhandle:
            self.fhandle.close()

    def read_line(self):
        """ Read line from text file. """
        if self.end_of_file():
            # input past end
            raise error.RunError(62)
        # readline breaks line on LF, we can only break on CR or CRLF
        s = ''
        while len(s) < 255:
            c = self.fhandle.read(1)
            if c in ('', '\x1a'):
                break
            elif c == '\n':
                s += c
                # special: allow LFCR (!) to pass
                if self.peek_char() == '\r':
                    self.fhandle.read(1)
                    s += '\r'
            elif c == '\r':
                # check for CR/LF
                if self.peek_char() == '\n':
                    self.fhandle.read(1)
                break
            else:
                s += c
        return s

    def read_chars(self, num):
        """ Read num characters as list. """
        return list(self.read(num))

    def read(self, num=-1):
        """ Read num characters as string. """
        s = ''
        l = 0
        while True:
            if num > -1 and l >= num:
                break
            l += 1
            c = self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading (that's true in files but not devices)
            if c in ('\x1a', ''):
                if num == -1:
                    break
                else:
                    # input past end
                    raise error.RunError(62)
            s += c
        return s 

    def write(self, s):
        """ Write the string s to the file, taking care of width settings. """
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in str(s):
            if c in ('\r', '\n'):
                newline = True
                break
            if ord(c) >= 32:
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if self.width != 255 and self.col != 1 and self.col-1 + s_width > self.width and not newline:
            self.fhandle.write('\r\n')
            self.flush()
            self.col = 1
        for c in str(s):
            # don't replace CR or LF with CRLF when writing to files
            if c in ('\n', '\r'):
                self.fhandle.write(c)
                self.flush()
                self.col = 1
            else:    
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                if ord(c) >= 32:
                    self.col += 1

    def set_width(self, new_width=255):
        """ Set the line width of the file. """
        self.width = new_width

    def end_of_file(self):
        """ Check for end of file - for internal use. """
        return (util.peek(self.fhandle) in ('', '\x1a'))

    def eof(self):
        """ Check for end of file EOF. """
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return (util.peek(self.fhandle) in ('', '\x1a'))

    def loc(self):
        """ Get file pointer LOC """
        # for LOC(i)
        if self.mode == 'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        """ Get length of file LOF. """
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof


class RandomFile(RandomBase):
    """ Random-access file on disk device. """

    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        """ Initialise random-access file. """        
        RandomBase.__init__(self, fhandle, name, number, mode, access, lock, reclen)
        # position at start of file
        self.recpos = 0
        self.fhandle.seek(0)

    def close(self):
        """ Close random-access file. """
        RandomBase.close(self)
        if self.fhandle:
            self.fhandle.close()

    def read_field(self, dummy=None):
        """ Read a record. """
        if self.eof():
            self.field[:] = '\x00'*self.reclen
        else:
            self.field[:] = self.fhandle.read(self.reclen)
        self.field_text_file.seek(0)
        self.recpos += 1

    def write_field(self, dummy=None):
        """ Write a record. """
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0, 2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\x00'*numrecs*self.reclen)
        self.fhandle.write(self.field)
        self.recpos += 1

    def set_pos(self, newpos):
        """ Set current record number. """
        # first record is newpos number 1
        self.fhandle.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        """ Get number of record just past, for LOC. """
        return self.recpos

    def eof(self):
        """ Return whether we're past currentg end-of-file, for EOF. """
        return self.recpos*self.reclen > self.lof()

    def lof(self):
        """ Get length of file, in bytes, for LOF. """
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof


#################################################################################
# Console files

class KYBDFile(NullFile):
    """ KYBD device: keyboard. """

    input_replace = { 
        '\x00\x47': '\xFF\x0B', '\x00\x48': '\xFF\x1E', '\x00\x49': '\xFE', 
        '\x00\x4B': '\xFF\x1D', '\x00\x4D': '\xFF\x1C', '\x00\x4F': '\xFF\x0E',
        '\x00\x50': '\xFF\x1F', '\x00\x51': '\xFE', '\x00\x53': '\xFF\x7F', '\x00\x52': '\xFF\x12'
        }

    col = 0

    def __init__(self):
        """ Initialise keyboard file. """
        NullFile.__init__(self)
        self.name = 'KYBD:'
        self.mode = 'I'
        self.width = 255

    def read_line(self):
        """ Read a line from the keyboard. """
        s = bytearray('')
        while len(s) < 255:
            c = self.read(1)
            if c == '\r':
                # don't check for CR/LF when reading KYBD:
                break
            else:
                s += c
        return s

    def read_chars(self, num=1):
        """ Read a list of chars from the keyboard - INPUT$ """
        return state.console_state.keyb.read_chars(num)

    def read(self, n=1):
        """ Read a string from the keyboard - INPUT and LINE INPUT. """
        word = ''
        for c in state.console_state.keyb.read_chars(n):
            if len(c) > 1 and c[0] == '\x00':
                try:
                    word += self.input_replace[c]
                except KeyError:
                    pass
            else:
                word += c
        return word

    def lof(self):
        """ LOF for KYBD: is 1. """
        return 1

    def loc(self):
        """ LOC for KYBD: is 0. """
        return 0

    def eof(self):
        """ KYBD only EOF if ^Z is read. """
        if self.mode in ('A', 'O'):
            return False
        # blocking peek
        return (state.console_state.keyb.wait_char() == '\x1a')

    def set_width(self, new_width=255):
        """ Setting width on KYBD device (not files) changes screen width. """
        if self.number == 0:
            console.set_width(new_width)


class SCRNFile(NullFile):
    """ SCRN: file, allows writing to the screen as a text file. 
        SCRN: files work as a wrapper text file. """

    def __init__(self):
        """ Initialise screen file. """
        NullFile.__init__(self)
        self.name = 'SCRN:'
        self.mode = 'O'
        self._width = state.console_state.screen.mode.width
        self._col = state.console_state.col

    def write(self, s):
        """ Write string s to SCRN: """
        # writes to SCRN files should *not* be echoed
        do_echo = (self.number == 0)
        self._col = state.console_state.col
        # take column 80+overflow int account
        if state.console_state.overflow:
            self._col += 1
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in str(s):
            if c in ('\r', '\n'):
                newline = True
                break
            if c == '\b':
                # for lpt1 and files, nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                s_width -= 1
            elif ord(c) >= 32:
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if (self.width != 255 
                and self.col != 1 and self.col-1 + s_width > self.width and not newline):
            console.write_line(do_echo=do_echo)
            self._col = 1
        cwidth = state.console_state.screen.mode.width
        for c in str(s):
            if self.width <= cwidth and self.col > self.width:
                console.write_line(do_echo=do_echo)
                self._col = 1
            if self.col <= cwidth or self.width <= cwidth:
                console.write(c, do_echo=do_echo)
            if c in ('\n', '\r'):
                self._col = 1
            else:
                self._col += 1

    def write_line(self, inp=''):
        """ Write a string to the screen and follow by CR. """
        self.write(inp)
        console.write_line(do_echo=(self.number==0))

    @property
    def col(self):  
        """ Return current (virtual) column position. """
        if self.number == 0:
            return state.console_state.col
        else:
            return self._col

    @property
    def width(self):
        """ Return (virtual) screen width. """
        if self.number == 0:
            return state.console_state.screen.mode.width
        else:
            return self._width

    def set_width(self, new_width=255):
        """ Set (virtual) screen width. """
        if self.number == 0:
            console.set_width(new_width)
        else:    
            self._width = new_width


#################################################################################
# Parallel-port and printer files

class LPTFile(RawFile):
    """ LPTn: device - line printer or parallel port. """

    def __init__(self, stream, flush_trigger='close'):
        """ Initialise LPTn. """
        # we don't actually need the name for non-disk files
        RawFile.__init__(self, StringIO(), 'LPTn:')
        # width=255 means line wrap
        self.width = 255
        self.col = 1
        self.output_stream = stream
        self.flush_trigger = flush_trigger

    def flush(self):
        """ Flush the printer buffer to the underlying stream. """
        try:
            self.output_stream.write(self.fhandle.getvalue())
            self.fhandle.truncate(0)
        except ValueError:
            # already closed, ignore
            pass

    def set_width(self, new_width=255):
        """ Set the width for LPTn. """
        self.width = new_width

    def write(self, s):
        """ Write a string to the printer buffer. """
        for c in str(s):
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                self.fhandle.write('\r\n')
                self.flush()
                self.col = 1
            if c in ('\n', '\r', '\f'): 
                # don't replace CR or LF with CRLF when writing to files
                self.fhandle.write(c)
                self.flush()
                self.col = 1
                # do the actual printing if we're on a short trigger
                if (self.flush_trigger == 'line' and c == '\n') or (self.flush_trigger == 'page' and c == '\f'):
                    self.output_stream.flush()
            elif c == '\b':   # BACKSPACE
                if self.col > 1:
                    self.col -= 1
                    self.seek(-1, 1)
                    self.truncate()  
            else:    
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                # for lpt1 and files , nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                if ord(c) >= 32:
                    self.col += 1

    def lof(self):
        """ LOF: bad file mode """
        raise error.RunError(54)

    def loc(self):
        """ LOC: bad file mode """
        raise error.RunError(54)

    def eof(self):
        """ EOF: bad file mode """
        raise error.RunError(54)

    def close(self):
        """ Close the printer device and actually print the output. """
        self.flush()
        try:
            self.output_stream.flush()
        except ValueError:
            # already closed, ignore
            pass    
        RawFile.close(self)


#################################################################################
# Serial-port files

class COMFile(RandomBase):
    """ COMn: device - serial port. """

    # communications buffer overflow
    overflow_error = 69

    def __init__(self, stream):
        """ Initialise COMn: device """
        # we don't actually need the name for non-disk files
        RandomBase.__init__(self, stream, 'COMn:', 0, 'R', 'RW', '', serial_in_size)
        self.in_buffer = bytearray()
        self.linefeed = False

    def check_read(self):
        """ Fill buffer at most up to buffer size; non blocking. """
        try:
            self.in_buffer += self.fhandle.read(serial_in_size - len(self.in_buffer))
        except (serial_socket.SerialException, ValueError):
            # device I/O
            raise error.RunError(57)

    def read(self, num=1):
        """ Read num characters from the port as a string; blocking """
        out = ''
        while len(out) < num:
            # non blocking read
            self.check_read()
            to_read = min(len(self.in_buffer), num - len(out))
            out += str(self.in_buffer[:to_read])
            del self.in_buffer[:to_read]
            # allow for break & screen updates
            backend.wait()
        return out

    def read_chars(self, num=1):
        """ Read num characters from the port as a list; blocking """
        return list(self.read(num))

    def read_line(self):
        """ Blocking read line from the port (not the FIELD buffer!). """
        out = bytearray('')
        while len(out) < 255:
            c = self.read(1)
            if c == '\r':
                if self.linefeed:
                    c = self.read(1)
                    if c == '\n':
                        break
                    out += ''.join(c)
                else:
                    break
            out += ''.join(c)
        return out

    def peek_char(self):
        """ Get the next char to be read. """
        if self.in_buffer:
            return str(self.in_buffer[0])
        else:
            return ''

    def write_line(self, s=''):
        """ Write string or bytearray and newline to port. """
        self.write(str(s) + '\r')

    def write(self, s):
        """ Write string to port. """
        try:
            if self.linefeed:
                s = s.replace('\r', '\r\n')
            self.fhandle.write(s)
        except (serial_socket.SerialException, ValueError):
            # device I/O
            raise error.RunError(57)

    def read_field(self, num):
        """ Read a record - GET. """
        # blocking read of num bytes
        self.field[:] = self.read(num)

    def write_field(self, num):
        """ Write a record - PUT. """
        self.write(self.field[:num])

    def loc(self):
        """ LOC: Returns number of chars waiting to be read. """
        # don't use inWaiting() as SocketSerial.inWaiting() returns dummy 0
        # fill up buffer insofar possible
        self.check_read()
        return len(self.in_buffer) 

    def eof(self):
        """ EOF: no chars waiting. """
        # for EOF(i)
        return self.loc() <= 0

    def lof(self):
        """ Returns number of bytes free in buffer. """
        return serial_in_size - self.loc()

    def close(self):
        """ Close the COMn device. """
        RandomBase.close(self)
        if self.fhandle:
            self.fhandle.close()


#################################################################################
# Cassette files

class CASFile(NullFile):
    """ Base object for devices and device files. """

    def __init__(self, tapestream, name='', number=0, mode='A'):
        """ Initialise file on tape. """
        NullFile.__init__(self)
        self.number = number
        self.tapestream = tapestream
        self.name = name
        self.mode = mode

    def lof(self):
        """ LOF: illegal function call. """
        raise error.RunError(5)

    def loc(self):
        """ LOC: illegal function call. """
        raise error.RunError(5)

    def eof(self):
        """ End of file. """
        if self.mode in ('A', 'O'):
            return False
        return self.tapestream.eof()

    def write(self, s):
        """ Write string s to tape file. """
        self.tapestream.write(s)

    def write_line(self, s):
        """ Write string s and CR to tape file. """
        self.write(s + '\r')

    def read_chars(self, n):
        """ Read a list of chars from device. """
        return list(self.read(n))

    def read(self, n):
        """ Read a string from device. """
        return self.tapestream.read(n)

    def read_line(self):
        """ Read a line from device. """
        if self.end_of_file():
            # input past end
            raise error.RunError(62)
        # readline breaks line on LF, we can only break on CR
        s = ''
        while len(s) < 255:
            c = self.tapestream.read(1)
            if c == '':
                break
            elif c == '\r':
                break
            else:
                s += c
        return s


prepare()

