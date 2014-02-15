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

import oslayer
import error
import fileio
from fileio import RandomBase, TextFile
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
    scrn = fileio.PseudoFile(ConsoleStream())
    kybd = fileio.PseudoFile(ConsoleStream())
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
    if mode.upper() in ('O', 'A') and device_name in output_devices:
        device = output_devices[device_name]
    elif mode.upper() in ('I') and device_name in input_devices:
        device = input_devices[device_name]
    elif mode.upper() in ('R') and device_name in random_devices:
        device = random_devices[device_name]
    else:
        # bad file mode
        raise error.RunError(54)
    # create a clone of the object, inheriting WIDTH settings etc.
    inst = copy.copy(device)
    if number < 0 or number > 255:
        # bad file number
        raise error.RunError(52)
    if number in fileio.files:
        # file already open
        raise error.RunError(55)
    if inst==None:
        # device unavailable
        raise error.RunError(68)
    inst.number = number
    inst.access = access
    inst.mode = mode.upper()
    fileio.files[number] = inst

def create_device(arg, default=None):
    device = None
    if arg != None:
        for a in arg:
            [addr,val] = a.split(':')
            if addr.upper()=='CUPS':
                device = fileio.PseudoFile(PrinterStream(val))      
            elif addr.upper()=='FILE':
                device = DeviceFile(val, access='wb')
    else:
        device = default
    return device


# device & file interface:
#   number
#   access
#   mode
#   init()
#   close()
#   loc()
#   lof()

# input:
#   read()
#   read_chars()
#   peek_char()
#   eof()

# output:
#   write()
#   flush()
#   set_width()
#   get_col()


class ConsoleStream:
    def write(self, c):
        console.write(c)
        
    def read(self, n):
        return console.read_chars(n)
    
    def seek(self, a, b=0):
        pass
        
    def tell(self):
        return 1

    def flush(self):
        pass

    def close(self):
        pass
    

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
        if self.number !=0:
            del files[self.number]



    
class SerialFile(RandomBase):
    # communications buffer overflow
    overflow_error = 69
    
    def __init__(self, port, number, reclen=128):
        RandomBase.__itnit__(self, serial.Serial(port), number, 'R', 'r+b', reclen)
    
    # read (GET)    
    def read_field(self, num):
        # blocking read of num bytes
        self.field[:] = self.fhandle.read(num)
        
    # write (PUT)
    def write_field(self, num):
        self.fhandle.write(self.field[:num])
        
    def loc(self):
        # for LOC(i) (comms files)
        # returns numer of chars waiting to be read
        return min(serial_in_size, self.fhandle.inWaiting())
            
    def eof(self):
        # for EOF(i)
        return self.fhandle.inWaiting() <= 0
    
    def lof(self):
        return max(0, serial_in_size - self.fhandle.inWaiting())
        
        
                
        
