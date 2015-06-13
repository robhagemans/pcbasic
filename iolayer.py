"""
PC-BASIC 3.23 - iolayer.py
File and Device I/O operations 

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3.
"""

import os
import copy
import logging
import string
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from bytestream import ByteStream
import config
import error
import console
import util
import state
import memory
import backend
import serial_socket
import printer

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

# set by disk.py
current_device = None


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


############################################################################
# General file manipulation

def open_file(number, description, filetype, mode='I', access='R', lock='',
              reclen=128, seg=0, offset=0, length=0):
    """ Open a file on a device specified by description. """
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
        try:
            device = backend.devices[dev_name]
        except KeyError:
            # not an allowable device or drive name
            # bad file number, for some reason
            raise error.RunError(52)
    else:
        device = current_device
        dev_param = name
    # check if device exists and allows the requested mode
    new_file = device.open(number, dev_param, filetype, mode, access, lock,
                           reclen, seg, offset, length)
    if number:
        state.io_state.files[number] = new_file
    return new_file

def get_file(num, mode='IOAR'):
    """ Get the file object for a file number and check allowed mode. """
    try:
        the_file = state.io_state.files[num]
    except KeyError:
        # bad file number
        raise error.RunError(52)
    if the_file.mode.upper() not in mode:
        # bad file mode
        raise error.RunError(54)
    return the_file

def close_file(num):
    """ Close a numbered file. """
    try:
        state.io_state.files[num].close()
        del state.io_state.files[num]
    except KeyError:
        pass

def close_files():
    """ Close all files. """
    for f in state.io_state.files.values():
        f.close()
    state.io_state.files = {}

def close_devices():
    """ Close device master files. """
    for d in backend.devices.values():
        d.close()


############################################################################
# Device classes
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

    def __init__(self):
        """ Set up device. """
        self.device_file = None

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on the device. """
        if not self.device_file:
            # device unavailable
            raise error.RunError(68)
        if mode not in self.allowed_modes:
            # bad file mode
            raise error.RunError(54)
        new_file = self.clone_master(number, mode, access, lock, reclen)
        return new_file

    def clone_master(self, number, mode, access, lock='', reclen=128):
        """ Clone device object as device file object (helper method). """
        inst = copy.copy(self.device_file)
        inst.number = number
        inst.access = access
        inst.mode = mode
        inst.lock = lock
        inst.reclen = reclen
        return inst

    def close(self):
        if self.device_file:
            self.device_file.close()


class SCRNDevice(Device):
    """ Screen device (SCRN:) """
    
    allowed_modes = 'OR'

    def __init__(self):
        """ Initialise screen device. """
        # open a master file on the screen
        Device.__init__(self)
        self.device_file = SCRNFile()


class KYBDDevice(Device):
    """ Keyboard device (KYBD:) """
    
    allowed_modes = 'IR'

    def __init__(self):
        """ Initialise keyboard device. """
        # open a master file on the keyboard
        Device.__init__(self)
        self.device_file = KYBDFile()


class LPTDevice(Device):
    """ Parallel port or printer device (LPTn:) """

    allowed_protocols = ('PRINTER', 'PARPORT', 'FILE')
    allowed_modes = 'OR'

    def __init__(self, arg, default_stream, flush_trigger):
        """ Initialise LPTn: device. """
        Device.__init__(self)
        addr, val = parse_protocol_string(arg)
        self.stream = default_stream
        if (addr and addr not in self.allowed_protocols):
            logging.warning('Could not attach %s to LPT device', arg)
        elif addr == 'FILE':
            try:
                if not os.path.exists(val):
                    open(val, 'wb').close()
                self.stream = open(val, 'r+b')
            except (IOError, OSError) as e:
                logging.warning('Could not attach file %s to LPT device: %s', val, str(e))
        elif addr == 'PARPORT':
            # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
           self.stream = serial_socket.parallel_port(val)
        else:
            # 'PRINTER' is default
            self.stream = printer.PrinterStream(val)
        if self.stream:
            self.device_file = LPTFile(self.stream, flush_trigger)
            self.device_file.flush_trigger = flush_trigger

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on LPTn: """
        # don't trigger flushes on LPT files, just on the device directly
        f = LPTFile(self.stream, 'close')
        # inherit width settings from device file
        f.width = self.device_file.width
        f.col = self.device_file.col
        return f


class COMDevice(Device):
    """ Serial port device (COMn:). """

    allowed_protocols = ('PORT', 'SOCKET')
    allowed_modes = 'IOAR'

    def __init__(self, arg, max_reclen, serial_in_size):
        """ Initialise COMn: device. """
        Device.__init__(self)
        addr, val = parse_protocol_string(arg)
        self.stream = None
        if (not val):
            pass
        elif (addr and addr not in self.allowed_protocols):
            logging.warning('Could not attach %s to COM device', arg)
        elif addr == 'SOCKET':
            self.stream = serial_socket.serial_for_url('socket://'+val)
        else:
            # 'PORT' is default
            # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows. Or anything supported by serial_for_url (RFC 2217 etc)
            self.stream = serial_socket.serial_for_url(val)
        if self.stream:
            self.device_file = COMFile(self.stream)

    def open(self, number, param, filetype, mode, access, lock,
                       reclen, seg, offset, length):
        """ Open a file on COMn: """
        if not self.stream:
            # device unavailable
            raise error.RunError(68)
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
        return Device.open(self, number, param, filetype, mode, access, lock, reclen)

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


#################################################################################
# file classes


class NullFile(object):
    """ Base file class. """

    def __init__(self):
        """ Initialise file. """
        self.number = 0
        self.name = ''
        self.filetype = ''

    def __enter__(self):
        """ Context guard. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Context guard. """
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
        """ Write string s and the appropriate end-of-line to device """
        pass

    def set_width(self, new_width=255):
        """ Set device width. """
        pass

    def read_raw(self, n):
        """ Read a string from device, without CR/LF replacement (INPUT$). """
        return ''

    def read(self, n):
        """ Read a string from device (INPUT and LINE INPUT). """
        return ''


class RawFile(NullFile):
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
    
    def close(self):
        """ Close the file. """
        self.fhandle.close()

    def read_raw(self, num=-1):
        """ Read num chars. If num==-1, read all available. """
        return self.fhandle.read(num)

    def read(self, num=-1):
        """ Read num chars. If num==-1, read all available. """
        return self.read_raw(num)

    def tell(self):
        """ Get position of file pointer. """
        return self.fhandle.tell()

    def seek(self, num, from_where=0):
        """ Move file pointer. """
        self.fhandle.seek(num, from_where)

    def write(self, s):
        """ Write string or bytearray to file. """
        self.fhandle.write(str(s))

    #D write_line should also only be used on text/ascii program streams
    def write_line(self, s=''):
        """ Write string or bytearray and newline to file. """
        self.write(str(s) + '\r\n')

    def flush(self):
        """ Write contents of buffers to file. """
        self.fhandle.flush()

    # needed only for representation.input_vars
    def eof(self):
        """ End-of-file. """
        return (util.peek(self.fhandle) == '')


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
        # set as Input-mode file to seek to start and not write EOF at close
        # TODO this is a bit hackish - just create a FieldTextFile class?
        self.field_text_file = TextFile(ByteStream(self.field), mode='I')
        self.field_text_file.col = 1
        # width=255 means line wrap
        self.field_text_file.width = 255

    def read_line(self):
        """ Read line from FIELD buffer. """
        s = self.field_text_file.read_line()
        self._check_overflow()
        return s

    def read_raw(self, num=-1):
        """ Read num chars as a string, from FIELD buffer. """
        s = self.field_text_file.read(num)
        self._check_overflow()
        return s

    def write(self, s):
        """ Write one or more chars to FIELD buffer. """
        self.field_text_file.write(s)
        self._check_overflow(write=True)

    def _check_overflow(self, write=False):
        """ Check for FIELD OVERFLOW. """
        # FIELD overflow happens if last byte in record has been read or written
        if self.field_text_file.fhandle.tell() > self.reclen + write - 1:
            # FIELD overflow
            raise error.RunError(self.overflow_error)

    def seek(self, n, from_where=0):
        """ Get file pointer location in FIELD buffer. """
        return self.field_text_file.seek(n, from_where)

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
# Text file


class TextFileBase(RawFile);
    """ Base for text files on disk, KYBD file, field buffer. """

    def read_line(self):
        """ Read a single line. """
        out = bytearray('')
        while len(out) < 255:
            c = self.read(1)
            # don't check for CRLF on KYBD:, CAS:, etc.
            if not c or c == '\r':
                break
            out += c
        return out

    def set_width(self, new_width=255):
        """ Set the line width of the file. """
        self.width = new_width




#TODO: handle utf8 etc (LineGetter)


class TextFile(TextFileBase):
    """ Text file on disk device or field buffer. """

    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        """ Initialise text file object. """
        RawFile.__init__(self, fhandle, name, number, mode, access, lock)
        if self.mode in ('I', 'O', 'R'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        # width=255 means unlimited
        self.width = 255
        self.col = 1

    def close(self):
        """ Close text file. """
        if self.mode in ('O', 'A'):
            # write EOF char
            self.fhandle.write('\x1a')
        self.fhandle.close()

    def read_line(self):
        """ Read line from text file. """
        # readline breaks line on LF, we can only break on CR or CRLF
        s = ''
        while len(s) < 255:
            c = self.fhandle.read(1)
            if c in ('', '\x1a'):
                # don't continue reading on Ctrl-Z on disk text files
                self.fhandle.seek(-len(c), 1)
                break
            elif c == '\n':
                s += c
                # special: allow LFCR (!) to pass
                c = self.fhandle.read(1)
                if c != '\r':
                    self.fhandle.seek(-len(c), 1)
                else:
                    s += '\r'
            elif c == '\r':
                # check for CR/LF
                c = self.fhandle.read(1)
                if c != '\n':
                    self.fhandle.seek(-len(c), 1)
                break
            else:
                s += c
        return s

    def write_line(self, s=''):
        """ Write string or bytearray and newline to file. """
        self.write(str(s) + '\r\n')

    def read_raw(self, num=-1):
        """ Read num characters as string. """
        s = ''
        l = 0
        while True:
            if num > -1 and l >= num:
                break
            l += 1
            c = self.fhandle.read(1)
            # check for \x1A (EOF char will actually stop further reading
            # (that's true in disk text files but not on LPT devices)
            if c in ('\x1a', ''):
                self.fhandle.seek(-len(c), 1)
                break
            s += c
        return s

    def read(self, num=-1):
        """ Read num characters, replacing CR LF with CR. """
        return self.read_raw(num).replace('\r\n', '\r')

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


#################################################################################
# Console files

class KYBDFile(TextFileBase):
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

    def read_raw(self, num=1):
        """ Read a list of chars from the keyboard - INPUT$ """
        word = ''
        for c in state.console_state.keyb.read_chars(n):
            if len(char) > 1 and char[0] == '\x00':
                # replace some scancodes than console can return
                if char[1] in ('\x4b', '\x4d', '\x48', '\x50',
                                '\x47', '\x49', '\x4f', '\x51', '\x53'):
                    word += '\x00'
                # ignore all others
            else:
                word += char
        return word

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

class LPTFile(TextFileBase):
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
        if self.fhandle:
            val = self.fhandle.getvalue()
            self.output_stream.write(val)
            self.fhandle.truncate(0)

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
                    self.fhandle.truncate()  
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
        self.output_stream.flush()
        self.fhandle.close()
        self.fhandle = None

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

    def read_raw(self, num=-1):
        """ Read num characters from the port as a string; blocking """
        if num == -1:
            # read whole buffer, non-blocking
            self.check_read()
            out = self.in_buffer
            del self.in_buffer[:]
        else:
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
    
    def char_waiting(self):
        """ Whether a char is present in buffer. For ON COM(n). """
        return self._in_buffer != ''

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


prepare()

