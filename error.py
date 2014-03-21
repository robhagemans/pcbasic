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
import console
import program
import events

# number and line number of last error
errn = -1
erl = 65535

# jump line number 
on_error = None
error_handle_mode = False
error_resume = None
            
default_msg = 'Unprintable error'
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
    # 21    
    22: 'Missing operand',
    23: 'Line buffer overflow',
    24: 'Device Timeout',
    25: 'Device Fault',
    26: 'FOR without NEXT',
    27: 'Out of paper',
    # 28
    29: 'WHILE without WEND',
    30: 'WEND without WHILE',
    # 31--49
    50: 'FIELD overflow',
    51: 'Internal error',
    52: 'Bad file number',
    53: 'File not found',
    54: 'Bad file mode',
    55: 'File already open',
    # 56
    57: 'Device I/O error',
    58: 'File already exists',
    # 59--60
    61: 'Disk full',
    62: 'Input past end',
    63: 'Bad record number',
    64: 'Bad file name',
    # 65
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
    76: 'Path not found',
    77: 'Deadlock',
}


class Error(Exception):
    pass            
        
class Break(Error):
    def __init__(self):
        self.erl = -1
        self.msg = "Break"
        
    def handle(self):
        program.prompt = True  
        errline = self.erl if not program.run_mode or self.erl != -1 else program.linenum 
        write_error_message(self.msg, errline)
        if program.run_mode:
            program.stop = [program.bytecode.tell(), program.linenum]
            program.set_runmode(False)
        return False    
        
class RunError(Error):
    def __init__(self, value, linum=-1):
        self.err = value
        self.erl = linum # -1 means not set, will be program.linenum if we're running
        self.msg = get_message(value)

    def handle(self):
        global errm, erl, error_resume, error_handle_mode
        program.prompt = True  
        errline = self.erl if not program.run_mode or self.erl != -1 else program.linenum     
        # set ERR and ERL
        errn = self.err
        erl = errline if errline and errline > -1 and errline < 65535 else 65536
        # don't jump if we're already busy handling an error
        if on_error != None and on_error != 0 and not error_handle_mode:
            error_resume = program.current_statement, program.current_codestream, program.run_mode
            program.jump(on_error)
            error_handle_mode = True
            program.set_runmode()
            events.suspend_all_events = True
            return True
        else:
            # not handled by ON ERROR, stop execution
            write_error_message(self.msg, errline)   
            error_handle_mode = False
            program.set_runmode(False)
            # for syntax error, line edit gadget appears
            if self.err == 2 and errline != -1:
                console.start_line()
                console.write("Ok \r\n")
                textpos = program.edit_line(errline, program.bytecode.tell())
            # for some reason, err is reset to zero by GW-BASIC in this case.
            if self.err == 2:
                errn = 0
            return False    

def get_message(errnum):
    try:
        msg = errors[errnum]
    except KeyError:
        msg = default_msg
    return msg    

def write_error_message(msg, linenum):
    console.start_line()
    console.write(msg) 
    if linenum != None and linenum > -1 and linenum < 65535:
        console.write(' in %i' % linenum)
    console.write(' \r\n')                  

