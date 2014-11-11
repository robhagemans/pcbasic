#
# PC-BASIC 3.23 - io.py
#
# File and Device I/O operations 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import copy
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import config
import oslayer
import error
import console
import util
import state
import backend
import serial_socket
import var
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

allowed_protocols = {
    # first protocol is default
    'LPT': ('FILE', 'PRINTER', 'PARPORT'),
    'COM': ('PORT', 'SOCKET')
    }

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
    global max_files, max_reclen, serial_in_size
    if config.options['max-files'] != None:
        max_files = config.options['max-files']
    if config.options['max-reclen'] != None:
        max_reclen = config.options['max-reclen']
        max_reclen = max(1, min(32767, max_reclen))
    if config.options['serial-buffer-size'] != None:
        serial_in_size = config.options['serial-buffer-size']
    # always defined
    backend.devices['SCRN:'] = SCRNFile()
    backend.devices['KYBD:'] = KYBDFile()
    backend.devices['LPT1:'] = create_device('LPT1:', config.options['lpt1'], nullstream) 
    # optional
    backend.devices['LPT2:'] = create_device('LPT2:', config.options['lpt2'])
    backend.devices['LPT3:'] = create_device('LPT3:', config.options['lpt3'])
    backend.devices['COM1:'] = create_device('COM1:', config.options['com1'])
    backend.devices['COM2:'] = create_device('COM2:', config.options['com2'])
    
def open_file_or_device(number, name, mode='I', access='R', lock='', reclen=128, defext=''):
    if (not name) or (number < 0) or (number > max_files):
        # bad file number; also for name='', for some reason
        raise error.RunError(52)
    if number in state.io_state.files:
        # file already open
        raise error.RunError(55)
    name, mode = str(name), mode.upper()
    inst = None
    split_colon = name.upper().split(':')
    if len(split_colon) > 1: # : found
        dev_name = split_colon[0] + ':' 
        try:
            inst = device_open(dev_name, number, mode, access, lock, reclen)
        except KeyError:    
            if len(dev_name) > 2:
                # devname could be A:, B:, C:, etc.. but anything longer is an error (bad file number, for some reason).
                raise error.RunError(52)   
    if not inst:
        # translate the file name to something DOS-ish if necessary
        if mode in ('O', 'A'):
            # don't open output or append files more than once
            check_file_not_open(name)
        if mode in ('I', 'L'):
            name = oslayer.native_path(name, defext)
        else:    
            # random files: try to open matching file
            # if it doesn't exist, create an all-caps 8.3 file name
            name = oslayer.native_path(name, defext, make_new=True)
        # obtain a lock
        request_lock(name, lock, access)
        # open the file
        fhandle = oslayer.open_file(name, mode, access)
        # apply the BASIC file wrapper
        if mode in ('S', 'L'): # save, load
            inst = BaseFile(fhandle, name, number, mode, access, lock)
        elif mode in ('I', 'O', 'A'):
            inst = TextFile(fhandle, name, number, mode, access, lock)
        else:
            inst = RandomFile(fhandle, name, number, mode, access, lock, reclen)
    return inst    
    
def get_file(num, mode='IOAR'):
    try:
        the_file = state.io_state.files[num]
    except KeyError:
        # bad file number
        raise error.RunError(52)
    if the_file.mode.upper() not in mode:
        raise error.RunError(54)    
    return the_file    
     
def check_file_not_open(path):
    for f in state.io_state.files:
        if oslayer.native_path(path) == state.io_state.files[f].name:
            raise error.RunError(55)

def find_files_by_name(name):
    return [state.io_state.files[f] for f in state.io_state.files if state.io_state.files[f].name == name]
      
def close_all():
    for f in list(state.io_state.files):
        if f > 0:
            state.io_state.files[f].close()

def lock_records(nr, start, stop):
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
    same_files = find_files_by_name(name)
    if not lock: # default mode; don't accept default mode if SHARED/LOCK present
        for f in same_files:
            if f.lock:
                raise error.RunError(70)    
    elif lock == 'RW':  # LOCK READ WRITE
        raise error.RunError(70)    
    elif lock == 'S':   # SHARED
        for f in same_files:
            if not f.lock:
                raise error.RunError(70)       
    else:               # LOCK READ or LOCK WRITE
        for f in same_files:
            if f.access == lock or lock == 'RW':
                raise error.RunError(70)


#################################################################################


class BaseFile(object):
    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        # width=255 means line wrap
        self.fhandle = fhandle
        self.name = name
        self.number = number
        self.mode = mode.upper()
        self.access = access
        self.lock = lock
        self.lock_list = set()    
        if number != 0:
            state.io_state.files[number] = self
    
    # set_width
    # width
    # col
    # lof
    # loc
    # eof

    def close(self):
        try:
            self.fhandle.flush()
        except (IOError, ValueError):
            # ignore errors on flushing
            pass    
        # don't close the handle - for devices
        if self.number != 0:
            del state.io_state.files[self.number]
    
    def read_chars(self, num):
        return list(self.fhandle.read(num)) 
        
    def read(self, num):
        return ''.join(self.read_chars(num))
    
    def read_line(self):
        out = bytearray('')
        while True:
            c = self.read(1)
            if c == '\r':
                break
            out += c
        return out            
            
    def peek_char(self):
        s = self.fhandle.read(1)
        self.fhandle.seek(-len(s), 1)
        return s
    
    def tell(self):
        return self.fhandle.tell()
        
    def seek(self, num, from_where=0):    
        self.fhandle.seek(num, from_where)
    
    def write(self, s):
        self.fhandle.write(str(s))
    
    def write_line(self, s=''):
        self.write(str(s) + '\r\n')    

    def end_of_file(self):
        return self.peek_char() == ''
        
    def flush(self):
        self.fhandle.flush()

    def truncate(self):
        self.fhandle.truncate()

class TextFile(BaseFile):
    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        BaseFile.__init__(self, fhandle, name, number, mode, access, lock)
        if self.mode in ('I', 'O', 'R', 'S', 'L'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        # width=255 means unlimited
        self.width = 255
        self.col = 1
    
    def close(self):
        if self.mode in ('O', 'A', 'S'):
            # write EOF char
            self.fhandle.write('\x1a')
        BaseFile.close(self)
        self.fhandle.close()
        
    # read line    
    def read_line(self):
        if self.end_of_file():
            # input past end
            raise error.RunError(62)
        # readline breaks line on LF, we can only break on CR or CRLF
        s = ''
        while True:
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
        s = []
        for _ in range(num):
            c = self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading (that's true in files but not devices)
            if c in ('\x1a', ''):
                # input past end
                raise error.RunError(62)
            s.append(c)
        return s 
        
    # write one or more chars
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
        self.width = new_width
    
    # for internal use    
    def end_of_file(self):
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def eof(self):
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def loc(self):
        # for LOC(i)
        if self.mode == 'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof


class RandomBase(BaseFile):
    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        BaseFile.__init__(self, fhandle, name, number, mode, access, lock)
        self.reclen = reclen
        # replace with empty field if already exists    
        try:
            self.field = state.io_state.fields[self.number]
        except KeyError:
            self.field = bytearray()
            state.io_state.fields[self.number] = self.field
        if self.number > 0:    
            self.field_address = var.field_mem_start + (self.number-1)*var.field_mem_offset
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
    
    # read line (from field buffer)    
    def read_line(self):
        # FIELD overflow happens if last byte in record is actually read
        if self.field_text_file.fhandle.tell() >= self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read_line()
        
    def read_chars(self, num):
        if self.field_text_file.fhandle.tell() + num > self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read_chars(num)
    
    # write one or more chars to field buffer
    def write(self, s):
        ins = StringIO(s)
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell() < len(s):
            raise error.RunError(self.overflow_error) 
    
    def peek_char(self):
        return self.field_text_file.peek_char()
    
    def seek(self, n, from_where=0):
        return self.field_text_file.seek(n, from_where)
        
    def truncate(self):
    # this is only used when writing chr$(8), not sure how to implement for random files
        pass
        
    @property
    def col(self):
        return self.field_text_file.col
    
    @property
    def width(self):
        return self.field_text_file.width
    
    def set_width(self, new_width=255):
        self.field_text_file.width = new_width

        
class RandomFile(RandomBase):
    # FIELD overflow
    overflow_error = 50

    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        RandomBase.__init__(self, fhandle, name, number, mode, access, lock, reclen)
        # position at start of file
        self.recpos = 0
        self.fhandle.seek(0)
    
    def close(self):
        RandomBase.close(self)
        self.fhandle.close()
        
    # read record    
    def read_field(self, dummy=None):
        if self.eof():
            self.field[:] = '\x00'*self.reclen
        else:
            self.field[:] = self.fhandle.read(self.reclen)
        self.field_text_file.seek(0)    
        self.recpos += 1
        
    # write record
    def write_field(self, dummy=None):
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0, 2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\x00'*numrecs*self.reclen)
        self.fhandle.write(self.field)
        self.recpos += 1
        
    def set_pos(self, newpos):
        # first record is newpos number 1
        self.fhandle.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        # for LOC(i)
        # returns number of record we're just past
        return self.recpos
        
    def eof(self):
        # for EOF(i)
        return self.recpos*self.reclen > self.lof()
            
    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

#################################################################################

class ByteStream(object):

    """ ByteStream is a StringIO-like wrapper for bytearray.
    """        

    def __init__(self, contents=''):       
        self.setvalue(contents)

    def setvalue(self, contents=''):
        """ Assign a bytearray s, move location to 0. This does not create a copy, changes affect the original bytearray. """
        self._contents = contents
        self._loc = 0
    
    def getvalue(self):
        """ Retrieve the bytearray. changes will affect the bytestream. """
        return self._contents
        
    def tell(self):
        """ Get the current location. """    
        return self._loc
        
    def seek(self, n_bytes, from_where=0):
        """ Move loc by n bytes from start(w=0), current(w=1) or end(w=2). """    
        if from_where == 0:
            self._loc = n_bytes
        elif from_where == 1:
            self._loc += n_bytes
        elif from_where == 2:
            self._loc = len(self._contents)-n_bytes        
        if self._loc < 0:
            self._loc = 0
        elif self._loc > len(self._contents):
            self._loc = len(self._contents)    
    
    def read(self, n_bytes=None):
        """ Get an n-length string and move the location n forward. If loc>len, return empty string. """
        if n_bytes == None:
            n_bytes = len(self._contents) - self._loc
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)
            return ''
        peeked = self._contents[self._loc:self._loc+n_bytes]
        self._loc += len(peeked)   
        return peeked
            
    def write(self, substr):
        """ Write a str or bytearray or char s to the current location. Overwrite, do not insert. """    
        if self._loc >= len(self._contents):
            self._contents += substr
            self._loc = len(self._contents)    
        else:    
            self._contents[self._loc:self._loc+len(substr)] = substr
            self._loc += len(substr)

    def truncate(self, n=None):
        """ Clip off the bytearray after position n. """
        if n == None:
            n = self._loc
        self._contents = self._contents[:n]
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)

    def close(self):
        """ Close the stream. """
        pass            

######################################################
# Device files

def create_device(name, arg, default=None):
    if not arg:
        stream = default
    else:   
        stream = create_device_stream(arg, allowed_protocols[name[:3]])
        if not stream:
            logging.warning('Could not attach %s to %s.' % (name, arg))
            stream = default
    if stream:        
        if name[:3] == 'COM':
            return COMFile(stream, name)
        else:
            return LPTFile(stream, name)    
    else:
        return None        

def create_device_stream(arg, allowed):
    argsplit = arg.split(':', 1)
    if len(argsplit) == 1:
        # use first allowed protocol as default
        addr, val = allowed[0], argsplit[0]
    elif len(argsplit) == 2:
        addr, val = argsplit[0].upper(), argsplit[1]
    else:
        return None
    if addr not in allowed:
        return None
    if addr == 'PRINTER':
        stream = printer.PrinterStream(val)
    elif addr == 'FILE':
        try:
            if not os.path.exists(val):
                open(val, 'wb').close() 
            stream = open(val, 'r+b')
        except (IOError, OSError) as e:
            return None    
    elif addr == 'PARPORT':
        # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
        stream = serial_socket.parallel_port(val)
    elif addr == 'PORT':
        # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows. Or anything supported by serial_for_url (RFC 2217 etc)
        stream = serial_socket.serial_for_url(val)
    elif addr == 'SOCKET':
        stream = serial_socket.serial_for_url('socket://'+val)
    else:
        # File not found
        raise error.RunError(53)
    return stream
            
def device_open(device_name, number, mode, access, lock, reclen):
    # check if device exists and allows the requested mode    
    # if not exists, raise KeyError to caller
    device = backend.devices[str(device_name).upper()]
    if not device:    
        # device unavailable
        raise error.RunError(68)      
    if mode not in device.allowed_modes:
        # bad file mode
        raise error.RunError(54)
    # don't lock devices
    return device.open(number, mode, access, '', reclen)

def close_devices():
    for d in backend.devices:
        if backend.devices[d]:
            backend.devices[d].close()


############################################################################

# for device_open
def open_device_file(dev, number, mode, access, lock='', reclen=128):
    inst = copy.copy(dev)
    inst.number = number
    inst.access = access
    inst.mode = mode
    inst.lock = lock
    inst.reclen = reclen
    if number != 0:
        state.io_state.files[number] = inst
    return inst


class NullDevice(object):
    def __init__(self):
        self.number = 0

    # for device_open
    def open(self, number, mode, access, lock, reclen):
        if number != 0:
            state.io_state.files[number] = self
        return open_device_file(self, number, mode, access, lock, reclen)
    
    def close(self):
        if self.number != 0:
            del state.io_state.files[self.number]
    
    def lof(self):
        # bad file mode
        raise error.RunError(54)
    def loc(self):
        # bad file mode
        raise error.RunError(54)
    def eof(self):
        # bad file mode
        raise error.RunError(54)
           
    # output
    def write(self, s):
        pass
    def write_line(self, s):
        pass
    def set_width(self, new_width=255):
        pass
    
    # input
    def read_line(self):
        return ''    
    def read_chars(self, n):
        return []
    def read(self, n):
        return ''        

    def end_of_file(self):
        return False    

        
        
class KYBDFile(NullDevice):
    input_replace = { 
        '\x00\x47': '\xFF\x0B', '\x00\x48': '\xFF\x1E', '\x00\x49': '\xFE', 
        '\x00\x4B': '\xFF\x1D', '\x00\x4D': '\xFF\x1C', '\x00\x4F': '\xFF\x0E',
        '\x00\x50': '\xFF\x1F', '\x00\x51': '\xFE', '\x00\x53': '\xFF\x7F', '\x00\x52': '\xFF\x12'
        }

    allowed_modes = 'IR'
    col = 0
    
    def __init__(self):
        self.name = 'KYBD:'
        self.mode = 'I'
        self.width = 255
        NullDevice.__init__(self)
        
    def read_line(self):
        s = bytearray('')
        while True:
            c = self.read(1)
            if c == '\r':
                # don't check for CR/LF when reading KYBD:
                break
            else:        
                s += c    
        return s

    # for INPUT$
    def read_chars(self, num):
        return backend.read_chars(num)

    # for INPUT and LINE INPUT
    def read(self, n):
        word = ''
        for c in backend.read_chars(n):
            if len(c) > 1 and c[0] == '\x00':
                try:
                    word += self.input_replace[c]
                except KeyError:
                    pass
            else:
                word += c        
        return word
        
    def lof(self):
        return 1

    def loc(self):
        return 0
     
    def eof(self):
        # KYBD only EOF if ^Z is read
        if self.mode in ('A', 'O'):
            return False
        # blocking read
        return (backend.wait_char() == '\x1a')

    # setting KYBD width is allowed, anomalously; but has no effect if on files. changes screen width if on device.
    def set_width(self, new_width=255):
        if self.number == 0:
            if not console.set_width(new_width):
                raise error.RunError(5)


class SCRNFile(NullDevice):

    """ SCRN: device, allows writing to the screen as a text file. 
        If number==0, this accesses console directly; otherwise, through a wrapper text file.
        For example, WIDTH "SCRN:, 40 works directly on console,
        whereas OPEN "SCRN:" FOR OUTPUT AS 1: WIDTH #1,23 works on the wrapper text file.
        Likewise, WIDTH "LPT1:" works on lpt1 for the next time it's opened; also for other devices.
    """

    allowed_modes = 'OR'
    
    def __init__(self):
        self.name = 'SCRN:'
        self.mode = 'O'
        self._width = state.console_state.width
        self._col = state.console_state.col
        NullDevice.__init__(self)
    
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
        for c in str(s):
            if self.width <= state.console_state.width and self.col > self.width:
                console.write_line(do_echo=do_echo)
                self._col = 1
            if self.col <= state.console_state.width or self.width <= state.console_state.width:
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
            return state.console_state.width
        else:
            return self._width
    
    def set_width(self, new_width=255):
        """ Set (virtual) screen width. """
        if self.number == 0:
            if not console.set_width(new_width):
                raise error.RunError(5)
        else:    
            self._width = new_width


class LPTFile(BaseFile):
    allowed_modes = 'OR'
    
    def __init__(self, stream, name):
        # width=255 means line wrap
        self.width = 255
        self.col = 1
        self.output_stream = stream
        BaseFile.__init__(self, StringIO(), name)

    # for device_open
    def open(self, number, mode, access, lock, reclen):
        return open_device_file(self, number, mode, access, lock, reclen)

    def flush(self):
        try:
            self.output_stream.write(self.fhandle.getvalue())
            self.fhandle.truncate(0)
        except ValueError:
            # already closed, ignore
            pass
        
    def set_width(self, new_width=255):
        self.width = new_width

    def write(self, s):
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
        # bad file mode
        raise error.RunError(54)

    def loc(self):
        # bad file mode
        raise error.RunError(54)

    def eof(self):
        # bad file mode
        raise error.RunError(54)
    
    def close(self):
        # actually print
        self.flush()
        try:
            self.output_stream.flush()
        except ValueError:
            # already closed, ignore
            pass    
        BaseFile.close(self)
        
class COMFile(RandomBase):
    allowed_modes = 'IOAR'
    
    # communications buffer overflow
    overflow_error = 69

    def __init__(self, stream, name):
        self._in_buffer = bytearray()
        RandomBase.__init__(self, stream, name, 0, 'R', 'RW', '', serial_in_size)

    # for device_open
    def open(self, number, mode, access, lock, reclen):
        # open the COM port
        if self.fhandle._isOpen:
            # file already open
            raise error.RunError(55)
        else:
            try:
                self.fhandle.open()
            except serial_socket.SerialException:
                # device timeout
                raise error.RunError(24)
        return open_device_file(self, number, mode, access, lock, reclen)   
    
    # fill up buffer - non-blocking    
    def check_read(self):
        # fill buffer at most up to buffer size        
        try:
            self._in_buffer += self.fhandle.read(serial_in_size - len(self._in_buffer))
        except serial_socket.SerialException:
            # device I/O
            raise error.RunError(57)
        
    def read(self, num):
        out = ''
        while len(out) < num:
            # non blocking read
            self.check_read()
            to_read = min(len(self._in_buffer), num - len(out))
            out += str(self._in_buffer[:to_read])
            del self._in_buffer[:to_read]
            # allow for break & screen updates
            backend.wait()        
        return out
        
    # blocking read
    def read_chars(self, num=1):
        return list(self.read(num))
    
    # blocking read line (from com port directly - NOT from field buffer!)    
    def read_line(self):
        out = bytearray('')
        while True:
            c = self.read(1)
            if c == '\r':
                c = self.read(1)
                out += ''.join(c)
                if c == '\n':    
                    break
            out += ''.join(c)
        return out
    
    def peek_char(self):
        if self._in_buffer:
            return str(self._in_buffer[0])
        else:
            return ''    
        
    def write(self, s):
        try:
            self.fhandle.write(s)
        except serial_socket.SerialException:
            # device I/O
            raise error.RunError(57)
    
    # read (GET)    
    def read_field(self, num):
        # blocking read of num bytes
        self.field[:] = self.read(num)
        
    # write (PUT)
    def write_field(self, num):
        self.write(self.field[:num])
        
    def loc(self):
        # for LOC(i) (comms files)
        # returns numer of chars waiting to be read
        # don't use inWaiting() as SocketSerial.inWaiting() returns dummy 0    
        # fill up buffer insofar possible
        self.check_read()
        return len(self._in_buffer) 
            
    def eof(self):
        # for EOF(i)
        return self.loc() <= 0
        
    def lof(self):
        return serial_in_size - self.loc()
    
    def close(self):
        self.fhandle.close()
        RandomBase.close(self)

prepare()


