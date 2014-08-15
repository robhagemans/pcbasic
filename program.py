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
import tokenise
import protect
import util
import console
# for check_events in LIST
import backend
import state
import flow

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from copy import copy 

# program bytecode buffer
state.basic_state.bytecode = StringIO()
# direct line buffer
state.basic_state.direct_line = StringIO()

# don't list or save,a beyond this line
max_list_line = 65530
# don't protect files
dont_protect = False

# program memory model; offsets in files
program_memory_start = 0x126e

# accept CR, LF and CRLF line endings; interpret as CR only if the next line starts with a number
universal_newline = False

def erase_program():
    state.basic_state.bytecode.truncate(0)
    state.basic_state.bytecode.write('\0\0\0')
    state.basic_state.protected = False
    state.basic_state.line_numbers = { 65536: 0 }
    state.basic_state.current_statement = 0
    state.basic_state.last_stored = None
    # reset stacks
    flow.init_program()

erase_program()

def truncate_program(rest=''):
    state.basic_state.bytecode.write(rest if rest else '\0\0\0')
    # cut off at current position    
    state.basic_state.bytecode.truncate()    
      
# get line number for stream position
def get_line_number(pos):
    pre = -1
    for linum in state.basic_state.line_numbers:
        linum_pos = state.basic_state.line_numbers[linum] 
        if linum_pos <= pos and linum > pre:
            pre = linum
    return pre

def rebuild_line_dict():
    # preparse to build line number dictionary
    state.basic_state.line_numbers, offsets = {}, []
    state.basic_state.bytecode.seek(0)
    scanline, scanpos, last = 0, 0, 0
    while True:
        state.basic_state.bytecode.read(1) # pass \x00
        scanline = util.parse_line_number(state.basic_state.bytecode)
        if scanline == -1:
            scanline = 65536
            # if parse_line_number returns -1, it leaves the stream pointer here: 00 _00_ 00 1A
            break 
        state.basic_state.line_numbers[scanline] = scanpos  
        last = scanpos
        util.skip_to(state.basic_state.bytecode, util.end_line)
        scanpos = state.basic_state.bytecode.tell()
        offsets.append(scanpos)
    state.basic_state.line_numbers[65536] = scanpos     
    # rebuild offsets
    state.basic_state.bytecode.seek(0)
    last = 0
    for pos in offsets:
        state.basic_state.bytecode.read(1)
        state.basic_state.bytecode.write(str(vartypes.value_to_uint(program_memory_start + pos)))
        state.basic_state.bytecode.read(pos - last - 3)
        last = pos
    # ensure program is properly sealed - last offset must be 00 00. keep, but ignore, anything after.
    state.basic_state.bytecode.write('\0\0\0')

def update_line_dict(pos, afterpos, length, deleteable, beyond):
    # subtract length of line we replaced
    length -= afterpos - pos
    addr = program_memory_start + afterpos
    state.basic_state.bytecode.seek(afterpos + length + 1)  # pass \x00
    while True:
        next_addr = bytearray(state.basic_state.bytecode.read(2))
        if len(next_addr) < 2 or next_addr == '\0\0':
            break
        next_addr = vartypes.uint_to_value(next_addr)
        state.basic_state.bytecode.seek(-2, 1)
        state.basic_state.bytecode.write(str(vartypes.value_to_uint(next_addr + length)))
        state.basic_state.bytecode.read(next_addr - addr - 2)
        addr = next_addr
    # update line number dict
    for key in deleteable:
        del state.basic_state.line_numbers[key]
    for key in beyond:
        state.basic_state.line_numbers[key] += length
            
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
    if state.basic_state.protected:
        raise error.RunError(5)
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    # check if linebuf is an empty line after the line number
    empty = (util.skip_white_read(linebuf) in util.end_line)
    pos, afterpos, deleteable, beyond = find_pos_line_dict(scanline, scanline)
    if empty and not deleteable:
        raise error.RunError(8)   
    # read the remainder of the program into a buffer to be pasted back after the write
    state.basic_state.bytecode.seek(afterpos)
    rest = state.basic_state.bytecode.read()
    # insert    
    state.basic_state.bytecode.seek(pos)
    # write the line buffer to the program buffer
    length = 0
    if not empty:
        # set offsets
        linebuf.seek(3) # pass \x00\xC0\xDE 
        length = len(linebuf.getvalue())
        state.basic_state.bytecode.write( '\0' + str(vartypes.value_to_uint(program_memory_start + pos + length)) + linebuf.read())
    # write back the remainder of the program
    truncate_program(rest)
    # update all next offsets by shifting them by the length of the added line
    update_line_dict(pos, afterpos, length, deleteable, beyond)
    if not empty:
        state.basic_state.line_numbers[scanline] = pos
    # clear all program stacks
    flow.init_program()
    state.basic_state.last_stored = scanline

def find_pos_line_dict(fromline, toline):
    deleteable = [ num for num in state.basic_state.line_numbers if num >= fromline and num <= toline ]
    beyond = [num for num in state.basic_state.line_numbers if num > toline ]
    # find lowest number strictly above range
    afterpos = state.basic_state.line_numbers[min(beyond)]
    # find lowest number within range
    try:
        startpos = state.basic_state.line_numbers[min(deleteable)]
    except ValueError:
        startpos = afterpos
    return startpos, afterpos, deleteable, beyond

def delete(fromline, toline):
    fromline = fromline if fromline != None else min(state.basic_state.line_numbers)
    toline = toline if toline != None else 65535 
    startpos, afterpos, deleteable, beyond = find_pos_line_dict(fromline, toline)
    if not deleteable:
        # no lines selected
        raise error.RunError(5)        
    # do the delete
    state.basic_state.bytecode.seek(afterpos)
    rest = state.basic_state.bytecode.read()
    state.basic_state.bytecode.seek(startpos)
    truncate_program(rest)
    # update line number dict
    update_line_dict(startpos, afterpos, 0, deleteable, beyond)
    # clear all program stacks
    flow.init_program()

def edit(from_line, bytepos=None):
    if state.basic_state.protected:
        console.write(str(from_line)+'\r')
        raise error.RunError(5)
    # list line
    state.basic_state.bytecode.seek(state.basic_state.line_numbers[from_line]+1)
    _, output, textpos = tokenise.detokenise_line(state.basic_state.bytecode, bytepos)
    console.clear_line(state.console_state.row)
    console.write(str(output))
    console.set_pos(state.console_state.row, textpos+1 if bytepos else 1)
    # throws back to direct mode
    flow.set_pointer(False)
    # suppress prompt
    state.basic_state.prompt = False
    
def renum(new_line, start_line, step):
    new_line = 10 if new_line == None else new_line
    start_line = 0 if start_line == None else start_line
    step = 10 if step == None else step 
    # get a sorted list of line numbers 
    keys = sorted([ k for k in state.basic_state.line_numbers.keys() if k >= start_line])
    # assign the new numbers
    old_to_new = {}
    for old_line in keys:
        if old_line < 65535 and new_line > 65529:
            raise error.RunError(5)
        if old_line == 65536:
            break
        old_to_new[old_line] = new_line
        state.basic_state.last_stored = new_line
        new_line += step    
    # write the new numbers
    for old_line in old_to_new:
        state.basic_state.bytecode.seek(state.basic_state.line_numbers[old_line])
        # skip the \x00\xC0\xDE & overwrite line number
        state.basic_state.bytecode.read(3)
        state.basic_state.bytecode.write(str(vartypes.value_to_uint(old_to_new[old_line])))
    # rebuild the line number dictionary    
    new_lines = {}
    for old_line in old_to_new:
        new_lines[old_to_new[old_line]] = state.basic_state.line_numbers[old_line]          
        del state.basic_state.line_numbers[old_line]
    state.basic_state.line_numbers.update(new_lines)    
    # write the indirect line numbers
    state.basic_state.bytecode.seek(0)
    while util.skip_to_read(state.basic_state.bytecode, ('\x0e',)) == '\x0e':
        # get the old g number
        jumpnum = vartypes.uint_to_value(bytearray(state.basic_state.bytecode.read(2)))
        try:
            newjump = old_to_new[jumpnum]
        except KeyError:
            # not redefined, exists in program?
            if jumpnum in state.basic_state.line_numbers:
                newjump = jumpnum
            else:    
                linum = get_line_number(state.basic_state.bytecode.tell())
                console.write_line('Undefined line ' + str(jumpnum) + ' in ' + str(linum))
        state.basic_state.bytecode.seek(-2, 1)
        state.basic_state.bytecode.write(str(vartypes.value_to_uint(newjump)))
    # stop running if we were
    flow.set_pointer(False)
    # reset loop stacks
    state.basic_state.gosub_return = []
    state.basic_state.for_next_stack = []
    state.basic_state.while_wend_stack = []
    # renumber error handler
    if state.basic_state.on_error:
        state.basic_state.on_error = old_to_new[state.basic_state.on_error]
    # renumber event traps
    for handler in state.basic_state.all_handlers:
        if handler.gosub:
            handler.gosub = old_to_new[handler.gosub]    
        
def load(g):
    erase_program()
    c = g.read(1)
    if c == '\xFF':
        # bytecode file
        state.basic_state.bytecode.truncate(0)
        state.basic_state.bytecode.write('\0')
        while c:
            c = g.read(1)
            state.basic_state.bytecode.write(c)
    elif c == '\xFE':
        # protected file
        state.basic_state.bytecode.truncate(0)
        state.basic_state.bytecode.write('\0')
        state.basic_state.protected = not dont_protect                
        protect.unprotect(g, state.basic_state.bytecode) 
    elif c != '':
        # ASCII file, maybe; any thing but numbers or whitespace will lead to Direct Statement in File
        load_ascii_file(g, c)        
    g.close()
    # rebuild line number dict and offsets
    rebuild_line_dict()
    
def merge(g):
    c = g.read(1)
    if c in ('\xFF', '\xFE', '\xFC', ''):
        # bad file mode
        raise error.RunError(54)
    else:
        load_ascii_file(g, c)
    g.close()
    
    
# readln, but break on \r rather than \n. ignore single starting LF to account for CRLF *without seeking*.
# include the \r at the end of the line. break at \x1a EOF. Do not include \x1a.
def read_program_line(ins, last, cr=('\r')):
    d = ins.read(1)
    eof = d in ('\x1a', '')
    out = d if (not eof and (last != '\r' or d != '\n')) else ''    
    while d not in cr and not eof:
        d = ins.read(1)
        eof = d in ('\x1a', '')
        if eof:
            break
        out += d       
    return out, eof, d

# buffered line reader
class LineGetter(object): 
    def __init__(self, g, universal):
        self.universal = universal
        if universal:
            self.cr = ('\r', '\n')
        else:
            self.cr = ('\r')   
        self.source = g    
        self.last = ''
        self.cache = None
        
    def get_line(self):
        if self.cache != None:
            line, eof = self.cache
            self.cache = None
        else:    
            line, eof, self.last = read_program_line(self.source, self.last, self.cr)
        if not self.universal:
            return line, eof
        # keep adding lines until one starts with a number
        while not eof:
            line2, eof2, self.last = read_program_line(self.source, self.last, self.cr)
            i = 0
            while i < len(line2) and line2[i] in (' ', '\0'):
                i += 1
            # if not starting with a number after whitespace, concatenate    
            if i == len(line2) or line2[i] < '0' or line2[i] > '9':
                line = line[:-1] + '\n' + line2
                eof = eof2
            else:
                break 
        if not eof:        
            self.cache = line2, eof2   
        if line[-1] == '\n':
            line = line[:-1] + '\r'
        return line, eof
        
# load an ascii encoded program
def load_ascii_file(g, first_char=''):
    eof = False
    lg = LineGetter(g, universal_newline)
    while not eof:
        line, eof = lg.get_line()
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

def chain(action, g, jumpnum, delete_lines): 
    # FIXME: does CHAIN ... DELETE ignore COMMON? this code doesn't clear variables on DELETE.   
    if delete_lines:
        # delete lines from existing code before merge (without MERGE, this is pointless)
        delete(*delete_lines)
    action(g)
    # don't close files!
    # RUN
    flow.jump(jumpnum, err=5)

def save(g, mode='B'):
    if state.basic_state.protected and mode != 'P':
        raise error.RunError(5)
    current = state.basic_state.bytecode.tell()
    # skip first \x00 in bytecode, replace with appropriate magic number
    state.basic_state.bytecode.seek(1)
    if mode == 'B':
        g.write('\xff')
        last = ''
        while True:
            nxt = state.basic_state.bytecode.read(1)
            if not nxt:
                break
            g.write(nxt)
            last = nxt
        if last != '\x1a':
            g.write('\x1a')    
    elif mode == 'P':
        g.write('\xfe')
        protect.protect(state.basic_state.bytecode, g)
        g.write('\x1a')    
    else:
        while True:
            current_line, output, _ = tokenise.detokenise_line(state.basic_state.bytecode)
            if current_line == -1 or (current_line > max_list_line):
                break
            g.write(str(output) + '\r\n')
        g.write('\x1a')       
    state.basic_state.bytecode.seek(current)         
    g.close()
    
def list_lines(dev, from_line, to_line):
    if state.basic_state.protected:
        # don't list protected files
        raise error.RunError(5)
    # 65529 is max insertable line number for GW-BASIC 3.23. 
    # however, 65530-65535 are executed if present in tokenised form.
    # in GW-BASIC, 65530 appears in LIST, 65531 and above are hidden
    if to_line == None:
        to_line = max_list_line
    # sort by positions, not line numbers!
    listable = sorted([ state.basic_state.line_numbers[num] for num in state.basic_state.line_numbers if num >= from_line and num <= to_line ])
    for pos in listable:        
        state.basic_state.bytecode.seek(pos + 1)
        _, line, _ = tokenise.detokenise_line(state.basic_state.bytecode)
        if dev == state.io_state.devices['SCRN:']:
            # flow of listing is visible on screen
            backend.check_events()
            console.clear_line(state.console_state.row)
            console.write_line(str(line))
            # remove empty line after 80-column program line
            if len(line) == state.console_state.width:
                console.cut_line()
        else:
            dev.write_line(str(line))
    dev.close()
    flow.set_pointer(False)
        
     

