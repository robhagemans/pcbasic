#
# PC-BASIC 3.23 - deviceio.py
#
# Device files
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import copy
import StringIO
import serial
import socket
import select

import oslayer
import error
import fileio
from fileio import RandomBase, TextFile, BaseFile
import console


# buffer sizes (/c switch in GW-BASIC)
serial_in_size = 256
serial_out_size = 128

input_devices = {}
output_devices = {}
random_devices = {}

# device implementations
scrn = None
kybd = None
lpt1 = None
lpt2 = None
lpt3 = None
com1 = None
com2 = None

def init_devices(args):
    global input_devices, output_devices, random_devices
    global scrn, kybd, lpt1, lpt2, lpt3, com1, com2
    scrn = ConsoleFile()
    kybd = ConsoleFile()
    lpt1 = create_device(args.lpt1, fileio.PseudoFile(PrinterStream()))
    lpt2 = create_device(args.lpt2)
    lpt3 = create_device(args.lpt3)
    com1 = create_device(args.com1)
    com2 = create_device(args.com2)
    # these are the *output* devices
    output_devices = { 'SCRN:': scrn, 'LPT1:': lpt1, 'LPT2:': lpt2, 'LPT3:': lpt3, 'COM1:': com1, 'COM2:': com2 }    
    # input devices
    input_devices =  { 'KYBD:': kybd, 'COM1:': com1, 'COM2:': com2 }
    # random access devices
    random_devices = { 'COM1:': com1, 'COM2:': com2 }
    
def is_device(aname):
    return aname in output_devices or aname in input_devices or aname in random_devices
            
def device_open(number, device_name, mode='I', access='rb'):
    global output_devices, input_devices, random_devices
    if mode.upper() in ('O', 'A', 'S') and device_name in output_devices:
        device = output_devices[device_name]
    elif mode.upper() in ('I', 'L') and device_name in input_devices:
        device = input_devices[device_name]
    elif mode.upper() in ('R') and device_name in random_devices:
        device = random_devices[device_name]
    else:
        # bad file mode
        raise error.RunError(54)
    if isinstance(device, SerialFile):
        device.open()
        inst = device
    else:    
        # create a clone of the object, inheriting WIDTH settings etc.
        inst = copy.copy(device)
    if inst == None:
        # device unavailable
        raise error.RunError(68)
    inst.number = number
    inst.access = access
    inst.mode = mode.upper()
    if number != 0:
        fileio.files[number] = inst
    return inst    

def create_device(arg, default=None):
    device = None
    if arg != None:
        for a in arg:
            [addr, val] = a.split(':', 1)
            if addr.upper() == 'CUPS':
                device = fileio.PseudoFile(PrinterStream(val))      
            elif addr.upper() == 'FILE':
                device = DeviceFile(val, access='wb')
            elif addr.upper() == 'PORT':
                device = SerialFile(val)    
    else:
        device = default
    return device


# device & file interface:
#   number
#   access
#   mode
#   col
#   init()
#   close()
#   loc()
#   lof()

# input:
#   read_line()
#   read_chars()
#   read()
#   peek_char()
#   eof()

# output:
#   write()
#   flush()
#   set_width()


input_replace = { 
    '\x00\x47': '\xFF\x0B', '\x00\x48': '\xFF\x1E', '\x00\x49': '\xFE', 
    '\x00\x4B': '\xFF\x1D', '\x00\x4D': '\xFF\x1C', '\x00\x4F': '\xFF\x0E',
    '\x00\x50': '\xFF\x1F', '\x00\x51': '\xFE', '\x00\x53': '\xFF\x7F', '\x00\x52': '\xFF\x12'
    }

# wrapper for console for reading from KYBD: and writing to SCRN:
class ConsoleFile(BaseFile):
    def __init__(self):
        self.fhandle = console
        self.number = 0
        self.mode = 'A'
        self.access = 'r+b'
        # SCRN file uses a separate width setting from the console
        self.width = console.width

        
    def seek(self, a, b=0):
        pass
    
    def tell(self):
        return 1

    def flush(self):
        pass

    def truncate(self):
        pass

    def read_line(self):
        s = ''
        while True:
            c = self.read(1)
            if c == '\x0D':
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
                    word += input_replace[c]
                except KeyError:
                    pass
            else:
                word += c        
        return word

    def write(self, inp):
        import sys
        sys.stderr.write(repr(inp)+'\n')
        last = ''
        for s in inp:
            import sys
            sys.stderr.write(repr(s)+repr(self.col)+'\n')
            if s == '\x0a' and last == '\x0d':
                console.write('\x0d\x0a')
            elif s == '\x0d':
                pass
            elif self.col > self.width and self.width != 255:  # width 255 means wrapping enabled
                sys.stderr.write('CRLF')
                console.write('\x0d\x0a'+s)
            else:        
                console.write(s)
            last = s
        if last == '\x0d':
            console.write(last)    
            
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
    
    def lof(self):
        return 1

    def loc(self):
        return 0
        
    # console read_char is blocking so we need to avoid calling it here.
    def peek_char(self):
        return console.peek_char()
    
    def end_of_file(self):
        return False
        
    def eof(self):
        # KYBD only EOF if ^Z is read
        if self.mode in ('A', 'O'):
            return False
        # blocking read
        return (console.wait_char() == '\x1a')

    def close(self):
        # don't write EOF \x1A to SCRN:
        if self.number != 0:
            del fileio.files[self.number]
        
    @property
    def col(self):
        return console.col


class PrinterStream(StringIO.StringIO):
    def __init__(self, name=''):
        self.printer_name=name
        StringIO.StringIO.__init__(self)
    
    # flush buffer to LPR printer    
    def flush(self):
        oslayer.line_print(self.getvalue(), self.printer_name)
        self.truncate(0)
        self.seek(0)

    def close(self):
        self.flush()
        # don't actually close the stream, there may be copies
        

# essentially just a text file that doesn't close if asked to
class DeviceFile(TextFile):
    def __init__(self, unixpath, access='rb'):
        if 'W' in access.upper():
            mode = 'O'
        else:
            mode = 'I'
        TextFile.__init__(self, oslayer.safe_open(unixpath, access), 0, mode, access)
        
    def close(self):
        # don't close the file handle as we may have copies
        if self.number != 0:
            del fileio.files[self.number]

    
class SerialFile(RandomBase):
    # communications buffer overflow
    overflow_error = 69

    def __init__(self, port, number=0, reclen=128):
        self._in_buffer = bytearray()
        RandomBase.__init__(self, serial.serial_for_url(port, timeout=0, do_not_open=True), number, 'R', 'r+b', reclen)
        if port.split(':', 1)[0] == 'socket':
            self.fhandle = SocketSerialWrapper(self.fhandle)
    
    # fill up buffer - non-blocking    
    def check_read(self):
        # fill buffer at most up to buffer size        
        try:
            self._in_buffer += self.fhandle.read(serial_in_size - len(self._in_buffer))
        except serial.SerialException:
            # device I/O
            raise error.RunError(57)
        
    # blocking read
    def read_chars(self, num=1):
        out = []
        while len(out) < num:
            # non blocking read
            self.check_read()
            to_read = min(len(self._in_buffer), num - len(out))
            out.append(self._in_buffer[:to_read])
            del self._in_buffer[:to_read]
            # allow for break & screen updates
            console.idle()        
            console.check_events()                       
        return out
    
    # blocking read line (from com port directly - NOT from field buffer!)    
    def read(self):
        out = ''
        while True:
            c = self.read_chars()
            if c == '\r':
                c = self.read_chars()
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
        self.fhandle.write(s)
    
    # read (GET)    
    def read_field(self, num):
        # blocking read of num bytes
        self.field[:] = ''.join(self.read_chars(num))
        
    # write (PUT)
    def write_field(self, num):
        self.fhandle.write(self.field[:num])
        
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
    
    def open(self):
        if self.fhandle._isOpen:
            # file already open
            raise error.RunError(55)
        else:
            self.fhandle.open()
    
    def close(self):
        self.fhandle.close()
        RandomBase.close(self)


class SocketSerialWrapper(object):
    ''' workaround for some limitations of SocketSerial with timeout==0 '''
    
    def __init__(self, socketserial):
        self._serial = socketserial    
        self._isOpen = self._serial._isOpen
    
    def open(self):
        self._serial.open()
        self._isOpen = self._serial._isOpen
    
    def close(self):
        self._serial.close()
        self._isOpen = self._serial._isOpen
        
    # non-blocking read   
    # SocketSerial.read always returns '' if timeout==0
    def read(self, num=1):
        self._serial._socket.setblocking(0)
        if not self._serial._isOpen: 
            raise serial.serialutil.portNotOpenError
        # poll for bytes (timeout = 0)
        ready, _, _ = select.select([self._serial._socket], [], [], 0)
        if not ready:
            # no bytes present after poll
            return ''
        try:
            # fill buffer at most up to buffer size        
            return self._serial._socket.recv(num)
        except socket.timeout:
            pass
        except socket.error, e:
            raise serial.SerialException('connection failed (%s)' % e)
    
    def write(self, s):
        self._serial.write(s)                    


