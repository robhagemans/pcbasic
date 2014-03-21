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
import fileio

from cStringIO import StringIO 
from copy import copy 

# program bytecode buffer
bytecode = StringIO()
# direct line buffer
direct_line = StringIO()

# show a prompt?
prompt = True

def init_program():
    global gosub_return, for_next_stack, while_wend_stack, linenum, stop
    # stop running if we were
    set_runmode(False)
    # reset loop stacks
    gosub_return = []
    for_next_stack = []
    while_wend_stack = []
    # reset stop/cont
    stop = None
    # current line number
    linenum = -1
    # reset program pointer
    bytecode.seek(0)
    # reset data reader
    restore()

def erase_program():
    global protected, line_numbers, current_statement, last_stored
    bytecode.truncate(0)
    bytecode.write('\x00\x00\x00\x1A')
    protected = False
    line_numbers = {}
    current_statement = 0
    last_stored = None

def set_runmode(new_runmode=True):
    global run_mode, current_codestream
    run_mode = new_runmode
    current_codestream = bytecode if run_mode else direct_line
    
# RESTORE
def restore(datanum=-1):
    global data_line, data_pos
    data_line = datanum
    try:
        data_pos = 0 if datanum==-1 else line_numbers[datanum]
    except KeyError:
        raise error.RunError(8)
        
init_program()
erase_program()

# CLEAR
def clear_all():
    #   Resets the stack and string space
    #   Clears all COMMON and user variables
    var.clear_variables()
    # reset random number generator
    rnd.clear()
    # close all files
    fileio.close_all()
    # release all disk buffers (FIELD)?
    fileio.fields = {}
    # clear ERR and ERL
    error.errn, error.erl = 0, 0
    # disable error trapping
    error.on_error = None
    error.error_resume = None
    # stop all sound
    console.sound.stop_all_sound()
    #   Resets sound to music foreground
    console.sound.music_foreground = True
    #   Resets STRIG to off
    console.stick_is_on = False
    # disable all event trapping (resets PEN to OFF too)
    events.reset_events()

# NEW    
def clear_program():
    erase_program()    
    init_program()
    clear_all()

def truncate_program(rest):
    bytecode.write(rest if rest else '\x00\x00\x00\x1a')
    # cut off at current position    
    bytecode.truncate()    
          
def memory_size():
    return len(bytecode.getvalue()) - 4
    
# get line number for stream position
def get_line_number(pos):
    pre = -1
    for linum in line_numbers:
        linum_pos = line_numbers[linum] 
        if linum_pos <= pos and linum > pre:
            pre = linum
    return pre

# jump to line number    
def jump(jumpnum, err=8):
    global linenum
    if jumpnum in line_numbers:
        # jump to target
        bytecode.seek(line_numbers[jumpnum])
        linenum = jumpnum
        set_runmode()
    else:
        # Undefined line number
        raise error.RunError(err)

# READ a unit of DATA
def read_entry():
    global data_line, data_pos
    current = bytecode.tell()
    bytecode.seek(data_pos)
    if util.peek(bytecode) in util.end_statement:
        # initialise - find first DATA
        util.skip_to(bytecode, ('\x84',))  # DATA
        data_line = get_line_number(bytecode.tell())
    if bytecode.read(1) not in ('\x84', ','):
        # out of DATA
        raise error.RunError(4)
    vals, word, verbatim = '', '', False
    while True:
        # read next char; omit leading whitespace
        if not verbatim and vals == '':    
            c = util.skip_white(bytecode)
        else:
            c = util.peek(bytecode)
        # parse char
        if c == '' or (not verbatim and c == ',') or (c in util.end_line or (not verbatim and c in util.end_statement)):
            break
        elif c == '"':
            bytecode.read(1)
            verbatim = not verbatim
            if not verbatim:
                util.require(bytecode, util.end_statement+(',',))
        else:        
            bytecode.read(1)
            if verbatim:
                vals += c
            else:
                word += c
            # omit trailing whitespace                        
            if c not in util.whitespace:    
                vals += word
                word = ''
    data_pos = bytecode.tell()
    bytecode.seek(current)
    return vals

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
    init_program()
    clear_all()

def store_line(linebuf, auto_mode=False):
    global line_numbers, last_stored
    linebuf.tell()
    # check if linebuf is an empty line after the line number
    linebuf.seek(5)
    empty = (util.skip_white_read(linebuf) in util.end_line)
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    # find the lowest line after scanline
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
    last_stored = scanline
    return scanline 

def delete_lines(fromline, toline):
    keys = sorted(line_numbers.keys())
    # find lowest number within range
    startline = None
    if fromline != None:
        for num in keys:
            if num >= fromline:
                startline = num
                break
    # find lowest number strictly above range
    afterline = 65536
    if toline != None:
        for num in keys:
            if num > toline:
                afterline = num
                break
    # if toline not specified, afterpos will be the number stored at 65536, ie the end of program
    try:
        startpos = 0 if startline == None else line_numbers[startline]        
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

def edit_line(from_line, bytepos=None):
    global prompt
    # list line
    current = bytecode.tell()	        
    bytecode.seek(1)
    output = StringIO()
    textpos = tokenise.detokenise(bytecode, output, from_line, from_line, bytepos)
    output.seek(0)
    bytecode.seek(current)
    console.clear_line(console.row)
    # cut off CR/LF at end
    console.write(output.getvalue()[:-2])
    output.close()
    # throws back to direct mode
    set_runmode(False)
    # suppress prompt, move cursor?
    prompt = False
    console.set_pos(console.row, textpos+1 if bytepos else 1)
    
def renum(new_line, start_line, step):
    global last_stored
    new_line = 10 if new_line == None else new_line
    start_line = 0 if start_line == None else start_line
    step = 10 if step == None else step 
    # get a sorted list of line numbers 
    keys = sorted([ k for k in line_numbers.keys() if k >= start_line])
    # assign the new numbers
    old_to_new = {}
    for old_line in keys:
        if old_line < 65535 and new_line > 65529:
            raise error.RunError(5)
        if old_line == 65536:
            break
        old_to_new[old_line] = new_line
        last_stored = new_line
        new_line += step    
    # write the new numbers
    for old_line in old_to_new:
        bytecode.seek(line_numbers[old_line])
        # skip the \x00\xC0\xDE & overwrite line number
        bytecode.read(3)
        bytecode.write(str(vartypes.value_to_uint(old_to_new[old_line])))
    # write the indirect line numbers
    bytecode.seek(0)
    while True:
        if util.skip_to_read(bytecode, ('\x0d', '\x0e')) not in ('\x0d', '\x0e'):
            break
        # get the old jump number
        jumpnum = vartypes.uint_to_value(bytearray(bytecode.read(2)))
        try:
            bytecode.seek(-2, 1)
            bytecode.write(str(vartypes.value_to_uint(old_to_new[jumpnum])))
        except StopIteration:
            linum = get_line_number(bytecode.tell())
            console.write('Undefined line ' + str(jumpnum) + ' in ' + str(linum) + '\r\n')
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
    g.close()
    
def merge(g):
    if g.peek_char() in ('\xFF', '\xFE', '\xFC', ''):
        # bad file mode
        raise error.RunError(54)
    else:
        more = True
        while (more):
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
    g.close()
    
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
        jump(jumpnum, err=5)

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
    g.close()
    
def list_to_file(out, from_line, to_line):
    if protected:
        # don't list protected files
        raise error.RunError(5)
    if to_line == None:
        to_line = 65530
    current = bytecode.tell()	        
    bytecode.seek(1)
    tokenise.detokenise(bytecode, out, from_line, to_line)
    bytecode.seek(current)
    set_runmode(False)
                  
def loop_init(ins, forpos, forline, varname, nextpos, nextline, start, stop, step):
    loopvar = vartypes.pass_type_keep(varname[-1], start)
    var.set_var(varname, start)
    for_next_stack.append((forpos, forline, varname, nextpos, nextline, start, stop, step)) 
    return loop_jump_if_ends(ins, loopvar, stop, step)
    
def loop_iterate(ins):            
    # JUMP to FOR statement
    forpos, forline, varname, _, _, start, stop, step = for_next_stack[-1]
    linenum = forline
    ins.seek(forpos)
    # skip to end of FOR statement
    util.skip_to(ins, util.end_statement)
    # increment counter
    loopvar = var.get_var(varname)
    loopvar = vartypes.number_add(loopvar, step)
    var.set_var(varname, loopvar)
    return loop_jump_if_ends(ins, loopvar, stop, step)
        
def loop_jump_if_ends(ins, loopvar, stop, step):
    global linenum
    sgn = vartypes.unpack_int(vartypes.number_sgn(step)) 
    if sgn < 0:
        loop_ends = vartypes.int_to_bool(vartypes.number_gt(stop, loopvar)) 
    elif sgn > 0:
        loop_ends = vartypes.int_to_bool(vartypes.number_gt(loopvar, stop)) 
    else:
        # step 0 is infinite loop
        loop_ends = False
    if loop_ends:
        # jump to just after NEXT
        _, _, _, nextpos, linenum, _, _, _ = for_next_stack.pop()
        ins.seek(nextpos)
    return loop_ends
    
