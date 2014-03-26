#
# PC-BASIC 3.23  - program.py
#
# Program buffer utilities
# 
# (c) 2013, 2014 Rob Hagemans 
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
# for prompt
import run

from cStringIO import StringIO 
from copy import copy 

# program bytecode buffer
bytecode = StringIO()
# direct line buffer
direct_line = StringIO()
# pointer position: False for direct line, True for program
run_mode = False
# memory model; offsets in files
program_memory_start = 0x126e

# line number tracing
tron = False

def init_program():
    global gosub_return, for_next_stack, while_wend_stack, stop
    # stop running if we were
    set_runmode(False)
    # reset loop stacks
    gosub_return = []
    for_next_stack = []
    while_wend_stack = []
    # reset stop/cont
    stop = None
    # reset program pointer
    bytecode.seek(0)
    # reset data reader
    restore()

def erase_program():
    global protected, line_numbers, current_statement, last_stored
    bytecode.truncate(0)
    bytecode.write('\0\0\0')
    protected = False
    line_numbers = { 65536: 0 }
    current_statement = 0
    last_stored = None

def set_runmode(new_runmode=True, pos=None):
    global run_mode, current_codestream
    current_codestream = bytecode if new_runmode else direct_line
    if run_mode != new_runmode:
        run_mode = new_runmode
        # position at end - don't execute anything unless we jump
        current_codestream.seek(0, 2)
    if pos != None:
        # jump to position, if given
        current_codestream.seek(pos)    
    
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
def clear_all(close_files=False):
    #   Resets the stack and string space
    #   Clears all COMMON and user variables
    var.clear_variables()
    # reset random number generator
    rnd.clear()
    if close_files:
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
    # reset all stacks   
    init_program()
    # clear all variables
    clear_all()

def truncate_program(rest=''):
    bytecode.write(rest if rest else '\0\0\0')
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

# build list of line numbers and positions
def preparse():
    rebuild_line_dict()
    # reset all stacks    
    init_program() 
    # clear all variables
    clear_all()

def rebuild_line_dict():
    global line_numbers
    # preparse to build line number dictionary
    line_numbers, offsets = {}, []
    bytecode.seek(1)
    scanline, scanpos, last = 0, 0, 0
    while True:
        scanline = util.parse_line_number(bytecode)
        if scanline == -1:
            scanline = 65536
            # if parse_line_number returns -1, it leaves the stream pointer here: 00 _00_ 00 1A
            break 
        line_numbers[scanline] = scanpos  
        util.skip_to_read(bytecode, util.end_line)
        last = scanpos
        scanpos = bytecode.tell() - 1
        offsets.append(scanpos)
    line_numbers[65536] = scanpos     
    # rebuild offsets
    bytecode.seek(1)
    last = 0
    for pos in offsets:
        bytecode.write(str(vartypes.value_to_uint(program_memory_start + pos)))
        bytecode.read(pos - last - 2)
        last = pos
    # ensure program is properly sealed - last offset must be 00 00. keep, but ignore, anything after.
    bytecode.write('\0\0')

# find stream position using line number dictionary
def find_pos_line_dict(scanline):
    # find the lowest line after scanline
    after, afterpos = 65536, 0
    for num in line_numbers:
        if num > scanline and num <= after:
            after = num
            afterpos = line_numbers[after]        
            # if not found, afterpos will be the number stored at 65536, ie the end of program
    try:
        # line number exists, replace line
        pos = line_numbers[scanline]
    except KeyError:
        pos = afterpos
    return pos, afterpos

def update_line_dict(pos, afterpos, length, scanline=None):
    # subtract length of line we replaced
    length -= afterpos - pos
    addr = program_memory_start + afterpos
    bytecode.seek(afterpos + length + 1)  # pass \x00
    while True:
        next_addr = bytearray(bytecode.read(2))
        if len(next_addr) < 2 or next_addr == '\0\0':
            break
        next_addr = vartypes.uint_to_value(next_addr)
        bytecode.seek(-2, 1)
        bytecode.write(str(vartypes.value_to_uint(next_addr + length)))
        bytecode.read(next_addr - addr - 2)
        addr = next_addr
    # update line number dict
    if length and scanline:
        line_numbers[scanline] = pos
    for key in line_numbers:
        if key > scanline:
            line_numbers[key] += length
            
def check_number_start(linebuf):
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    c = util.skip_white_read(linebuf) 
    # check if linebuf is an empty line after the line number
    empty = (c in util.end_line)
    # check if we start with a number
    if c in tokenise.tokens_number:        
        raise error.RunError(2)
    return empty, scanline   

def store_line(linebuf): 
    global line_numbers, last_stored
    if protected:
        raise error.RunError(5)
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    # check if linebuf is an empty line after the line number
    empty = (util.skip_white_read(linebuf) in util.end_line)
    if empty and not scanline in line_numbers:
        raise error.RunError(8)
    pos, afterpos = find_pos_line_dict(scanline)
    # read the remainder of the program into a buffer to be pasted back after the write
    bytecode.seek(afterpos)
    rest = bytecode.read()
    # insert    
    bytecode.seek(pos)
    # write the line buffer to the program buffer
    length = 0
    if not empty:
        # set offsets
        linebuf.seek(3) # pass \x00\xC0\xDE 
        length = len(linebuf.getvalue())
        bytecode.write( '\0' + str(vartypes.value_to_uint(program_memory_start + pos + length)) + linebuf.read())
    # write back the remainder of the program
    truncate_program(rest)
    # update all next offsets by shifting them by the length of the added line
    update_line_dict(pos, afterpos, length, scanline)
    # clear all program stacks
    init_program()
    # clear variables (storing a line does that)
    clear_all()
    last_stored = scanline
    
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
    # update line number dict
    update_line_dict(startpos, afterpos, 0)
    # clear all program stacks
    init_program()
    # clear variables (storing a line does that)
    clear_all()

def edit_line(from_line, bytepos=None):
    if protected:
        console.write(str(from_line)+'\r')
        raise error.RunError(5)
    # list line
    bytecode.seek(1)
    output = StringIO()
    textpos = tokenise.detokenise(bytecode, output, from_line, from_line, bytepos)
    console.clear_line(console.row)
    # cut off CR/LF at end
    console.write(output.getvalue()[:-2])
    console.set_pos(console.row, textpos+1 if bytepos else 1)
    # throws back to direct mode
    set_runmode(False)
    # suppress prompt
    run.prompt = False
    
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
    # rebuild the line number dictionary    
    preparse()
#    for old_line in old_to_new:
#        line_numbers[old_line] = old_to_new[old_line]   
    # write the indirect line numbers
    bytecode.seek(0)
    while util.skip_to_read(bytecode, ('\x0e',)) == '\x0e':
        # get the old g number
        jumpnum = vartypes.uint_to_value(bytearray(bytecode.read(2)))
        try:
            newjump = old_to_new[jumpnum]
        except KeyError:
            # not redefined, exists in program?
            if jumpnum in line_numbers:
                newjump = jumpnum
            else:    
                linum = get_line_number(bytecode.tell())
                console.write_line('Undefined line ' + str(jumpnum) + ' in ' + str(linum))
        bytecode.seek(-2, 1)
        bytecode.write(str(vartypes.value_to_uint(newjump)))

def load(g):
    global protected
    erase_program()
    c = g.read(1)
    if c == '\xFF':
        # bytecode file
        bytecode.truncate(0)
        bytecode.write('\0')
        while c:
            c = g.read(1)
            bytecode.write(c)
    elif c == '\xFE':
        # protected file
        bytecode.truncate(0)
        bytecode.write('\0')
        protected = True                
        protect.unprotect(g, bytecode) 
    elif c != '':
        # ASCII file, maybe; any thing but numbers or whitespace will lead to Direct Statement in File
        load_ascii_file(g, c)        
    preparse()
    g.close()
    
def merge(g):
    c = g.read(1)
    if c in ('\xFF', '\xFE', '\xFC', ''):
        # bad file mode
        raise error.RunError(54)
    else:
        load_ascii_file(g, c)
    g.close()
    
def load_ascii_file(g, first_char=''):
    eof = False
    while not eof:
        line, eof = tokenise.read_program_line(g)
        line, first_char = first_char + line, ''
        linebuf = tokenise.tokenise_line(line)
        if linebuf.read(1) == '\0':
            # line starts with a number, add to program memory; store_line seeks to 1 first
            store_line(linebuf)
        else:
            # we have read the :
            if util.skip_white(linebuf) not in util.end_line:
                # direct statement in file
                raise error.RunError(66)   

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
    jump(jumpnum, err=5)

def save(g, mode='B'):
    if protected and mode != 'P':
        raise error.RunError(5)
    current = bytecode.tell()
    # skip first \x00 in bytecode, replace with appropriate magic number
    bytecode.seek(1)
    if mode == 'B':
        g.write('\xff')
        last = ''
        while True:
            nxt = bytecode.read(1)
            if not nxt:
                break
            g.write(nxt)
            last = nxt
        if last != '\x1a':
            g.write('\x1a')    
    elif mode == 'P':
        g.write('\xfe')
        protect.protect(bytecode, g)
        g.write('\x1a')    
    else:
        tokenise.detokenise(bytecode, g) 
        g.write('\x1a')       
    bytecode.seek(current)         
    g.close()
    
def list_to_file(out, from_line, to_line):
    if protected:
        # don't list protected files
        raise error.RunError(5)
    if to_line == None:
        to_line = 65530
    bytecode.seek(1)
    tokenise.detokenise(bytecode, out, from_line, to_line)
    set_runmode(False)
             
# jump to line number    
def jump(jumpnum, err=8):
    if jumpnum == None:
        set_runmode(True, 0)
    else:    
        try:    
            # jump to target
            set_runmode(True, line_numbers[jumpnum])
        except KeyError:
            # Undefined line number
            raise error.RunError(err)
        
def jump_gosub(jumpnum, handler=None):    
    # set return position
    gosub_return.append((current_codestream.tell(), run_mode, handler))
    jump(jumpnum)
 
def jump_return(jumpnum):        
    try:
        pos, orig_runmode, handler = gosub_return.pop()
    except IndexError:
        # RETURN without GOSUB
        raise error.RunError(3)
    # returning from ON (event) GOSUB, re-enable event
    if handler:
        # if stopped explicitly using STOP, we wouldn't have got here; it STOP is run  inside the trap, no effect. OFF in trap: event off.
        handler.stopped = False
    if jumpnum == None:
        # go back to position of GOSUB
        set_runmode(orig_runmode, pos)   
    else:
        # jump to specified line number 
        jump(jumpnum)

def loop_init(ins, forpos, nextpos, varname, start, stop, step):
    loopvar = vartypes.pass_type_keep(varname[-1], start)
    var.set_var(varname, start)
    for_next_stack.append((forpos, nextpos, varname, start, stop, step)) 
    return loop_jump_if_ends(ins, loopvar, stop, step)
    
def loop_iterate(ins):            
    # JUMP to FOR statement
    forpos, _, varname, start, stop, step = for_next_stack[-1]
    ins.seek(forpos)
    # skip to end of FOR statement
    util.skip_to(ins, util.end_statement)
    # increment counter
    loopvar = var.get_var(varname)
    loopvar = vartypes.number_add(loopvar, step)
    var.set_var(varname, loopvar)
    return loop_jump_if_ends(ins, loopvar, stop, step)
        
def loop_jump_if_ends(ins, loopvar, stop, step):
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
        _, nextpos, _, _, _, _ = for_next_stack.pop()
        ins.seek(nextpos)
    return loop_ends
    
def loop_find_next(ins, pos):
    while True:
        if len(for_next_stack) == 0:
            # next without for
            raise error.RunError(1) #1  
        forpos, nextpos, varname, _, _, _ = for_next_stack[-1]
        if pos != nextpos:
            # not the expected next, we must have jumped out
            for_next_stack.pop()
        else:
            break
    return forpos, nextpos, varname
                
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
     
