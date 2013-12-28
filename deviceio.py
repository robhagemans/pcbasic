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

import error
import fileio
import printer
import console


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
    
    scrn = fileio.pseudo_textfile(console.ConsoleStream())
    kybd = fileio.pseudo_textfile(console.ConsoleStream())
    
    #lpt1 = create_device(args.lpt1, printer.Device_Lpt())
    lpt1 = create_device(args.lpt1, fileio.pseudo_textfile(printer.PrinterStream()))
    
    lpt2 = create_device(args.lpt2)
    lpt3 = create_device(args.lpt3)
    
    com1 = create_device(args.com1)
    com2 = create_device(args.com2)
    
    # these are the *output* devices
    output_devices = { 'SCRN:': scrn, 'LPT1:': lpt1, 'LPT2:': lpt2,  'LPT3:': lpt3, 'COM1:': com1, 'COM2:': com2 }    
    # input devices
    input_devices = { 'KYBD:': kybd, 'COM1:': com1, 'COM2:': com2 }
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
    
    # create a clone of the object
    inst = copy.copy(device)

    if number <0 or number>255:
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
    if arg !=None:
        for a in arg:
            [addr,val] = a.split(':')
            if addr.upper()=='CUPS':
                device = fileio.pseudo_textfile(printer.PrinterStream(val))      
            elif addr.upper()=='FILE':
                device = fileio.DeviceFile(val, access='wb')
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


