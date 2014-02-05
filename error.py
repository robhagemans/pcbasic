#
# PC-BASIC 3.23 - error.py
#
# Error handling 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys

# number and line number of last error
errn = -1
erl = 65535

# jump line number 
on_error = None
error_handle_mode = False
error_resume = None
# allow non-GW warnings
warnings_on = False

###################

            
class Error (Exception):
    pass            

        
class Break(Error):
    def __init__(self):
        self.erl = -1
        self.msg = "Break"
                    
class RunError(Error):
    def __init__(self, value, linum=-1):
        self.err = value
        self.erl = linum # -1 means not set, will be program.linenum if we're running
        if value in errors:
            self.msg = errors[value]
        # set_error                
                
class AdHocError(Error):
    def __init__(self, msg, linum=-1):
        self.err = 0
        self.erl = linum
        self.msg = msg    
     
def get_error():
    global errn, erl
    return (errn, erl)     

def reset_error():
    global erl, errn
    erl = 0         
    errn = 0

def set_error(errnum, linenum):
    global errn, erl
    if errnum>0 and errnum <256:
        errn = errnum
    if linenum > -1 and linenum < 65535:
       erl = linenum
    else:
       erl = 65535

def get_message(errnum):
    msg = default_msg
    if errnum in errors:
        msg = errors[errnum]
    return msg    
        
# non-fatal warning to stderr
def warning(warnum, linenum, info):           
    # only output warnings if asked
    if not warnings_on:
        return
    sys.stderr.write(warnings[warnum])
    if linenum > -1:
        sys.stderr.write(' in ' +str(linenum))
    if info != '':
        sys.stderr.write(': '+info)
    sys.stderr.write('\n')


default_msg = 'Unprintable error'

# these are the errors documented for GW-BASIC
errors = {
    1: 'NEXT without FOR',                    
    2: 'Syntax error',
    3: 'RETURN without GOSUB',
    4: 'Out of DATA',
    5: 'Illegal function call',
    6: 'Overflow',
    7: 'Out of memory',
    8: 'Undefined line number',
    9: 'Subscript out of range',
    10: 'Duplicate Definition',
    11: 'Division by zero',
    12: 'Illegal direct',
    13: 'Type mismatch',
    14: 'Out of string space',
    15: 'String too long',
    16: 'String formula too complex',
    17: "Can't continue",
    18: 'Undefined user function',
    19: 'No RESUME',
    20: 'RESUME without error',
    
    22: 'Missing operand',
    23: 'Line buffer overflow',
    24: 'Device Timeout',
    25: 'Device Fault',
    26: 'FOR without NEXT',
    27: 'Out of paper',
    
    29: 'WHILE without WEND',
    30: 'WEND without WHILE',
    
    50: 'FIELD overflow',
    51: 'Internal error',
    52: 'Bad file number',
    53: 'File not found',
    54: 'Bad file mode',
    55: 'File already open',
    
    57: 'Device I/O error',
    58: 'File already exists',
    
    61: 'Disk full',
    62: 'Input past end',
    63: 'Bad record number',
    64: 'Bad file name',
    
    66: 'Direct statement in file',
    67: 'Too many files',
    68: 'Device Unavailable',
    69: 'Communication buffer overflow',
    70: 'Permission Denied',
    71: 'Disk not Ready',
    72: 'Disk media error',
    73: 'Advanced Feature',
    74: 'Rename across disks',
    75: 'Path/File access error',
    76: 'Path not found'
}

# these are not GW-BASIC warnings    
warnings = {
    1: 'Unexpected token',
    2: 'No EOF (&H1A) at end of file',    
    3: 'Unexpected string past end of file',
    4: 'Trucated line at end of file',
    5: 'Line number exceeds 65530',
    6: "Can't read QuickBASIC files"
}


