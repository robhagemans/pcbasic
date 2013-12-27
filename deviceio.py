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

def init_devices():
    global input_devices, output_devices, random_devices
    global scrn, kybd, lpt1, lpt2, lpt3, com1, com2
    
    # these are the *output* devices
    output_devices = { 'SCRN:': scrn, 'LPT1:': lpt1, 'LPT2:': lpt2,  'LPT3:': lpt3, 'COM1:': com1, 'COM2:': com2 }    
    # input devices
    input_devices = { 'KYBD:': kybd, 'COM1:': com1, 'COM2:': com2 }
    # random access devices
    random_devices = { 'COM1:': com1, 'COM2:': com2 }
    
