#
# PC-BASIC 3.23  - program.py
#
# Program buffer utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import vartypes
import var
import events
import tokenise
import protect
import util
import console
# for clear()
import rnd

from cStringIO import StringIO 
from copy import copy 

# program bytecode buffer
bytecode = StringIO()
# direct line buffer
direct_line = StringIO()

# for error handling - can be in program bytecode or in linebuf
current_codestream = None
current_statement =  0

# bookkeeping of file positions and line numbers for jumps
line_numbers = {}

# protected flag, disallow LIST, LLIST and SAVE to ascii
protected = False

# current line number, here as a convenient place for globals used by many modules
linenum = -1        

# return positions    
gosub_return = []
for_next_stack = []
while_wend_stack = []

# stream position for CONT
stop = None  

# where are we READing DATA?
data_pos=0
data_line = -1

# is the program running?    
run_mode = False

# show a prompt?
prompt = True


def set_runmode(new_runmode=True):
    global run_mode, current_codestream
    run_mode = new_runmode
    current_codestream = bytecode if run_mode else direct_line
    
def unset_runmode():
    set_runmode(False)

# get line number for stream position
def get_line_number(pos): #, after=False):
    pre = -1
    for linum in line_numbers:
        linum_pos = line_numbers[linum] 
        if linum_pos <= pos and linum < pre:
            pre = linum
    return pre

# jump to line number    
def jump(jumpnum):
    global linenum
    if jumpnum in line_numbers:
        # jump to target
        bytecode.seek(line_numbers[jumpnum])
        linenum = jumpnum
        set_runmode()
    else:
        # Undefined line number
        raise error.RunError(8)

# build list of line numbers and positions
def preparse():
    global line_numbers
    # preparse to build line number dictionary
    line_numbers = {}
    bytecode.seek(1)
    last = 1
    while True:
        scanline = util.parse_line_number(bytecode)
        if scanline == -1:
            # program ends
            if util.peek(bytecode) == '':
                # truncated file, no \00\00\00\nn (\nn can be \1a or something else)
                # fix that
                bytecode.write('\x00\x00\x00\x1a')
                # try again from cycle
                bytecode.seek(last + 5)
                util.skip_to_read(bytecode, util.end_line)
                util.parse_line_number(bytecode)
            # if parse_line_number returns -1, it leaves the stream pointer here: 00 _00_ 00 1A 
            line_numbers[65536] = bytecode.tell() - 1  
            break
        # -5 because we're eg at x in 00 C0 DE 00 0A _XX_ and we need to be on the line-ending 00: _00_ C0 DE 00 0A XX
        last = bytecode.tell() - 5   
        line_numbers[scanline] = last  
        util.skip_to_read(bytecode, util.end_line)
    reset_program()
            
def reset_program():
    global gosub_return, for_next_stack, while_wend_stack, linenum, data_line, data_pos, stop
    # reset loop stacks
    gosub_return = []
    for_next_stack = []
    while_wend_stack = []
    # disable error trapping
    error.error_resume = None
    error.on_error = 0
    # reset err and erl
    error.reset_error()
    # reset event trapping
    events.reset_events()    
    # reset stop/cont
    stop = None
    # current line number
    linenum = -1
    # clear all variables
    var.clear_variables()
    # reset program pointer
    bytecode.seek(0)
    # reset data reader
    data_line = -1
    data_pos = 0
    
def clear_program():
    global protected, line_numbers
    bytecode.truncate(0)
    bytecode.write('\x00\x00\x00\x1A')
    protected = False
    line_numbers = {}    
    reset_program()
   
def truncate_program(rest):
    if rest == '':
        bytecode.write('\x00\x00\x00\x1a')
    else:
        bytecode.write(rest)
    # cut off at current position    
    bytecode.truncate()    
    
def store_line(linebuf, auto_mode=False):
    global line_numbers
    linebuf.tell()
    # check if linebuf is an empty line after the line number
    linebuf.seek(5)
    empty = (util.skip_white_read(linebuf) in util.end_line)
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    # find the lowest line after this number
    after = 65536
    afterpos = 0 
    for num in line_numbers:
        if num > scanline and num <= after:
            after = num
            afterpos = line_numbers[after]        
            # if not found, afterpos will be the number stored at 65536, ie the end of program
    # read the remainder of the program into a buffer to be pasted back after the write
    bytecode.seek(afterpos)
    rest = bytecode.read()
    # replace or insert?
    if scanline in line_numbers and not (auto_mode and empty):
        # line number exists, replace line
        bytecode.seek(line_numbers[scanline])
    else:
        if empty:
            if not auto_mode:
                # undefined line number
                raise error.RunError(8)
            else:
                return scanline
        # insert    
        bytecode.seek(afterpos)
    # write the line buffer to the program buffer
    if not empty:
        linebuf.seek(0)
        bytecode.write(linebuf.read())
    # write back the remainder of the program
    truncate_program(rest)
    bytecode.seek(0)
    preparse()
    return scanline 

def delete_lines(fromline, toline):
    keys = sorted(line_numbers.keys())
    # find lowest number within range
    startline = -1
    if fromline != -1:
        for num in keys:
            if num >= fromline:
                startline = num
                break
    # find lowest number strictly above range
    afterline = 65536
    if toline != -1:
        for num in keys:
            if num > toline:
                afterline = num
                break
    # if toline not specified, afterpos will be the number stored at 65536, ie the end of program
    try:
        if startline == -1:
            startpos = 0
        else:
            startpos = line_numbers[startline]        
        afterpos = line_numbers[afterline]
    except KeyError:
        # no program stored
        raise error.RunError(5)
    if afterpos <= startpos:
        # no lines selected
        raise error.RunError(5)
    # do the delete
    bytecode.seek(afterpos)
    rest = bytecode.read()
    bytecode.seek(startpos)
    truncate_program(rest)
    bytecode.seek(0)
    preparse()

def edit_line(from_line, pos=-1):
    global prompt
    # list line
    current = bytecode.tell()	        
    bytecode.seek(1)
    output = StringIO()
    tokenise.detokenise(bytecode, output, from_line, from_line, pos)
    output.seek(0)
    bytecode.seek(current)
    console.clear_line(console.row)
    console.write(output.getvalue())
    output.close()
    # throws back to direct mode
    unset_runmode()
    # suppress prompt, move cursor?
    prompt = False
    console.set_pos(console.row-1, 1)
    
def renumber(new_line=-1, start_line=-1, step=-1):
    # set defaults
    if new_line == -1:
        new_line = 10
    if start_line == -1:
        start_line = 0
    if step == -1:
        step = 10        
    # get line number dict in the form it should've been in anyway had I implemented it sensibly
    lines = []
    for num in line_numbers:
        if num >= start_line:
            lines.append([num, line_numbers[num]])        
    lines.sort()    
    # assign the new numbers
    for pairs in lines:
        pairs.append(new_line)
        new_line += step    
    # write the new numbers
    for pairs in lines:
        if pairs[0]==65536:
            break
        bytecode.seek(pairs[1])
        bytecode.read(3)
        bytecode.write(vartypes.value_to_uint(pairs[2]))
    # write the indirect line numbers
    bytecode.seek(0)
    linum = -1
    while util.peek(bytecode) != '':
        util.skip_to(bytecode, ['\x0d', '\x0e'])
        linum = get_line_number(bytecode.tell())
        if linum == 65536:
            break
        bytecode.read(1)
        s = bytecode.read(2)
        jumpnum = vartypes.uint_to_value(s)
        newnum = -1
        for triplets in lines:
            if triplets[0] == jumpnum:
                newnum = triplets[2]
        if newnum != -1:    
            bytecode.seek(-2, 1)
            bytecode.write(vartypes.value_to_uint(newnum))
        else:
            # just a message, not an actual error. keep going.
            console.write('Undefined line '+str(jumpnum)+' in '+str(linum)+util.endl)
    # rebuild the line number dictionary    
    preparse()    

def load(g):
    global protected
    bytecode.truncate(0)
    c = ''.join(g.read_chars(1))
    if c == '\xFF':
        # bytecode file
        bytecode.write('\x00')
        protected = False
        while c != '':
            c = ''.join(g.read_chars(1))
            bytecode.write(c)
    elif c == '\xFE':
        # protected file
        bytecode.write('\x00')
        protected = True                
        protect.unprotect(g, bytecode)
    #elif c=='\xFC':
        # QuickBASIC file
    elif c == '':
        # empty file
        pass
    else:
        # TODO: check allowed first chars for ASCII file - > whitespace + nums? letters?
        # ASCII file, maybe
        g.seek(-1, 1)
        protected = False
        tokenise.tokenise_stream(g, bytecode)
        # terminate bytecode stream properly
        bytecode.write('\x00\x00\x00\x1a')
    preparse()

def merge(g):
    if g.peek_char() in ('\xFF', '\xFE', '\xFC', ''):
        # bad file mode
        raise error.RunError(54)
    else:
        more = True
        while (more): #peek(g)=='' and not peek(g)=='\x1A':
            tempbuf = StringIO()
            more = tokenise.tokenise_stream(g, tempbuf, one_line=True)
            tempbuf.seek(0)
            c = util.peek(tempbuf) 
            if c == '\x00':
                # line starts with a number, add to program memory
                store_line(tempbuf)
            elif util.skip_white(tempbuf) in util.end_line:
                # empty line
                pass
            else:
                # direct statement in file
                raise error.RunError(66)                
            tempbuf.close()    

def chain(action, g, jumpnum, common_all, delete_lines):    
    if delete_lines:
        # delete lines from existing code before merge (without MERGE, this is pointless)
        delete_lines(*delete_lines)
    if common_all:
        common, common_arrays, common_functions = copy(var.variables), copy(var.arrays), copy(var.functions)
    else:
        # preserve COMMON variables
        common, common_arrays, common_functions = {}, {}, {}
        for varname in var.common_names:
            try:
                common[varname] = var.variables[varname]
            except KeyError: 
                pass    
        for varname in var.common_array_names:
            try:
                common_arrays[varname] = var.arrays[varname]
            except KeyError:
                pass    
    # preserve deftypes (only for MERGE)
    common_deftype = copy(vartypes.deftype) 
    # preserve option base
    base = var.array_base    
    # load & merge call preparse call reset_program:  # data restore  # erase def fn   # erase defint etc
    action(g)
    # reset random number generator
    rnd.clear()
    # restore only common variables
    var.variables = common
    var.arrays = common_arrays
    # restore user functions (if ALL specified)
    var.functions = common_functions
    # restore option base
    var.array_base = base
    # restore deftypes (if MERGE specified)
    if action == merge:
        vartypes.deftype = common_deftype
    # don't close files!
    # RUN
    set_runmode()
    if jumpnum != None:
        jump(jumpnum)

def save(g, mode='B'):
    # skip first \x00 in bytecode, replace with appropriate magic number
    # TODO: what happens if we SAVE during a running program?
    bytecode.seek(1)
    if mode == 'B':
        if protected:
            raise error.RunError(5)
        else:
            g.write('\xff')
            g.write(bytecode.read())
    elif mode == 'P':
        g.write('\xfe')
        protect.protect(bytecode, g)    
    else:
        if protected:
            raise error.RunError(5)
        else:
            tokenise.detokenise(bytecode, g) 
            # fix \x1A eof
            g.write('\x1a')        

def list_to_file(out, from_line, to_line):
    if protected:
        # don't list protected files
        raise error.RunError(5)
    if to_line == -1:
        to_line = 65530
    current = bytecode.tell()	        
    bytecode.seek(1)
    tokenise.detokenise(bytecode, out, from_line, to_line)
    bytecode.seek(current)
    unset_runmode()
                        
def memory_size():
    return len(bytecode.getvalue()) - 4
    
