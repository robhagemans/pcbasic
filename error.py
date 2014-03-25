#
# PC-BASIC 3.23 - error.py
#
# Error handling 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
import util
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
        self.erl = -1 if not program.run_mode else program.get_line_number(program.current_statement)
        self.msg = "Break"
        
    def handle_break(self):
        write_error_message(self.msg, self.erl)
        if program.run_mode:
            program.stop = program.bytecode.tell()
            program.set_runmode(False)
        
    def handle_continue(self):
        # can't trap
        return False
            
class RunError(Error):
    def __init__(self, value, linum=-1):
        self.err = value
        self.erl = linum if not program.run_mode or linum != -1 else program.get_line_number(program.current_statement)
        self.msg = get_message(value)

    def handle_continue(self):
        global error_resume, error_handle_mode
        set_err(self)
        # don't jump if we're already busy handling an error
        if on_error != None and on_error != 0 and not error_handle_mode:
            error_resume = program.current_statement, program.run_mode
            program.jump(on_error)
            error_handle_mode = True
            events.suspend_all_events = True
            return True
            
    def handle_break(self):
        global errn
        set_err(self)
        # not handled by ON ERROR, stop execution
        write_error_message(self.msg, self.erl)   
        error_handle_mode = False
        program.set_runmode(False)
        # special case
        if self.err == 2:
            # for syntax error, line edit gadget appears
            if self.erl != -1:
                console.start_line()
                console.write_line("Ok\xff")
                textpos = program.edit_line(self.erl, program.bytecode.tell())
            # for some reason, err is reset to zero by GW-BASIC in this case.
            errn = 0
    
    
def resume(jumpnum):  
    global error_handle_mode, error_resume  
    start_statement, runmode = error_resume 
    errn = 0
    error_handle_mode = False
    error_resume = None
    events.suspend_all_events = False    
    if jumpnum == 0: 
        # RESUME or RESUME 0 
        program.set_runmode(runmode, start_statement)
    elif jumpnum == -1:
        # RESUME NEXT
        program.set_runmode(runmode, start_statement)        
        util.skip_to(program.current_codestream, util.end_statement, break_on_first_char=False)
    else:
        # RESUME n
        program.jump(jumpnum)

def set_err(e):
    global errn, erl
    # set ERR and ERL
    errn = e.err
    erl = e.erl if e.erl and e.erl > -1 and e.erl < 65535 else 65535
    
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
    console.write_line(' ')                  

# math errors only break execution if handler is set
def math_error(errnum):
    if on_error: 
        # also raises exception in error_handle_mode! in that case, prints a normal error message
        raise(RunError(errnum))
    else:
        # write a message & continue as normal
        # start_line() ?
        console.write_line(get_message(errnum)) # no space, no line number

