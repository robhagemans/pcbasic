#
# PC-BASIC 3.23 - deviceio.py
#
# Device files
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import copy
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import logging
import serial_socket
import oslayer
import error
import fileio
from fileio import RandomBase, TextFile, BaseFile
import console


# buffer sizes (/c switch in GW-BASIC)
serial_in_size = 256
serial_out_size = 128

devices = {}

allowed_protocols = {
    # first protocol is default
    'LPT': ('FILE', 'PRINTER', 'PORT', 'SOCKET'),
    'COM': ('PORT', 'SOCKET')
    }

def prepare_devices(args):
    global devices
    # always defined
    devices['SCRN:'] = SCRNFile()
    devices['KYBD:'] = KYBDFile()
    devices['LPT1:'] = create_device('LPT1:', args.lpt1, oslayer.nullstream) 
    # optional
    devices['LPT2:'] = create_device('LPT2:', args.lpt2)
    devices['LPT3:'] = create_device('LPT3:', args.lpt3)
    devices['COM1:'] = create_device('COM1:', args.com1)
    devices['COM2:'] = create_device('COM2:', args.com2)

def create_device(name, arg, default=None):
    if not arg:
        stream = default
    else:   
        stream = create_device_stream(arg, allowed_protocols[name[:3]])
        if not stream:
            logging.warning('Could not attach %s to %s.\n' % (name, arg))
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
        stream = oslayer.CUPSStream(val)
    elif addr == 'FILE':
        stream = oslayer.safe_open(val, 'R', 'RW')
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
    device = devices[str(device_name).upper()]
    if not device:    
        # device unavailable
        raise error.RunError(68)      
    if mode not in device.allowed_modes:
        # bad file mode
        raise error.RunError(54)
    # don't lock devices
    return device.open(number, mode, access, '', reclen)

def close_devices():
    for d in devices:
        if devices[d]:
            devices[d].close()


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
        fileio.files[number] = inst
    return inst


class NullDevice(object):
    def __init__(self):
        self.width = 255
        self.number = 0

    # for device_open
    def open(self, number, mode, access, lock, reclen):
        if number != 0:
            fileio.files[number] = self
        return open_device_file(self, number, mode, access, lock, reclen)
    
    def close(self):
        if self.number != 0:
            del fileio.files[self.number]
    
    # stream interface - do we really need these?
#    def seek(self, a, b=0):
#        pass
#    def tell(self):
#        return 1
#    def flush(self):
#        pass
#    def truncate(self):
#        pass
    
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
        self.fhandle = console
        self.name = 'KYBD:'
        self.mode = 'I'
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
        return console.read_chars(num)

    # for INPUT and LINE INPUT
    def read(self, n):
        word = ''
        for c in console.read_chars(n):
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
        return (console.wait_char() == '\x1a')

    # setting KYBD width is allowed, anomalously; but has no effect if on files. changes screen width if on device.
    def set_width(self, new_width=255):
        if self.number == 0:
            if not console.set_width(new_width):
                raise error.RunError(5)

class SCRNFile(NullDevice):
    allowed_modes = 'OR'
    
    def __init__(self):
        self.fhandle = console
        self.name = 'SCRN:'
        self.mode = 'O'
        self.width = console.width
        NullDevice.__init__(self)
    
    def write(self, inp):
        for s in inp:
            console.write(s)
            if console.col > self.width and self.width != 255:
                console.write_line()
            
    def write_line(self, inp=''):
        self.write(inp)
        console.write_line()
            
    @property
    def col(self):  
        return console.col
        
    # WIDTH "SCRN:, 40 works directly on console 
    # whereas OPEN "SCRN:" FOR OUTPUT AS 1: WIDTH #1,23 works on the wrapper text file
    # WIDTH "LPT1:" works on lpt1 for the next time it's opened; also for other devices.
    def set_width(self, new_width=255):
        if self.number == 0:
            if not console.set_width(new_width):
                raise error.RunError(5)
        else:    
            self.width = new_width


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
        self.output_stream.write(self.fhandle.getvalue())
        self.fhandle.truncate(0)
        
    def set_width(self, new_width=255):
        self.width = new_width

    def write(self, s):
        for c in str(s):
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                self.fhandle.write('\r\n')
                self.flush()
                self.col = 1
            if c in ('\n', '\r'): # don't replace with CRLF when writing to files
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
        self.output_stream.flush()
        
        
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
            console.idle()        
            console.check_events() 
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

