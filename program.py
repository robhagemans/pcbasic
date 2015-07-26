"""
PC-BASIC - program.py
Program buffer utilities

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import config
import error
import vartypes
import basictoken as tk
import tokenise
import protect
import util
import backend
import console
import state
import flow
import unicodepage
import memory
import logging
# ensure initialisation of state_console_state.sound
import sound

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

# bytecode buffer is defined in memory.py
# direct line buffer
state.basic_state.direct_line = StringIO()

# don't list or save,a beyond this line
max_list_line = 65530
# don't protect files
dont_protect = False


def prepare():
    """ Initialise program module. """
    global max_list_line, dont_protect
    global program_memory_start
    if (not config.options['strict-hidden-lines']) or config.options['convert']:
        max_list_line = 65535
    else:
        max_list_line = 65530
    dont_protect = (not config.options['strict-protect']) or config.options['convert']
    # program memory model; offsets in files (4718 == 0x126e)
    program_memory_start = memory.code_start + 1
    erase_program()

def erase_program():
    """ Erase the program from memory. """
    state.basic_state.bytecode.truncate(0)
    state.basic_state.bytecode.write('\0\0\0')
    state.basic_state.protected = False
    state.basic_state.line_numbers = { 65536: 0 }
    state.basic_state.current_statement = 0
    state.basic_state.last_stored = None
    # reset stacks
    flow.init_program()

def truncate_program(rest=''):
    """ Write bytecode and cut the program of beyond the current position. """
    state.basic_state.bytecode.write(rest if rest else '\0\0\0')
    # cut off at current position
    state.basic_state.bytecode.truncate()

def get_line_number(pos):
    """ Get line number for stream position. """
    pre = -1
    for linum in state.basic_state.line_numbers:
        linum_pos = state.basic_state.line_numbers[linum]
        if linum_pos <= pos and linum > pre:
            pre = linum
    return pre

def rebuild_line_dict():
    """ Preparse to build line number dictionary. """
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
        util.skip_to(state.basic_state.bytecode, tk.end_line)
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
    """ Update line number dictionary after deleting lines. """
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
    """ Check if the given line buffer starts with a line number. """
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    c = util.skip_white_read(linebuf)
    # check if linebuf is an empty line after the line number
    empty = (c in tk.end_line)
    # check if we start with a number
    if c in tk.number:
        raise error.RunError(2)
    return empty, scanline

def store_line(linebuf):
    """ Store the given line buffer. """
    if state.basic_state.protected:
        raise error.RunError(5)
    # get the new line number
    linebuf.seek(1)
    scanline = util.parse_line_number(linebuf)
    # check if linebuf is an empty line after the line number
    empty = (util.skip_white_read(linebuf) in tk.end_line)
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
    """ Find code positions for line range. """
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
    """ Delete range of lines from stored program. """
    fromline = fromline if fromline is not None else min(state.basic_state.line_numbers)
    toline = toline if toline is not None else 65535
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
    """ Output program line to console and position cursor. """
    if state.basic_state.protected:
        console.write(str(from_line)+'\r')
        raise error.RunError(5)
    # list line
    state.basic_state.bytecode.seek(state.basic_state.line_numbers[from_line]+1)
    _, output, textpos = tokenise.detokenise_line(state.basic_state.bytecode, bytepos)
    # no newline to avoid scrolling on line 24
    console.list_line(str(output), newline=False)
    # find row, column position for textpos
    newlines, c = 0, 0
    pos_row, pos_col = 0, 0
    for i, byte in enumerate(output):
        c += 1
        if chr(byte) == '\n' or c > state.console_state.screen.mode.width:
            newlines += 1
            c = 0
        if i == textpos:
            pos_row, pos_col = newlines, c
    if textpos > i:
        pos_row, pos_col = newlines, c + 1
    if bytepos:
        console.set_pos(state.console_state.row-newlines+pos_row, pos_col)
    else:
        console.set_pos(state.console_state.row-newlines, 1)

def renum(new_line, start_line, step):
    """ Renumber stored program. """
    new_line = 10 if new_line is None else new_line
    start_line = 0 if start_line is None else start_line
    step = 10 if step is None else step
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
    for handler in state.basic_state.events.all:
        if handler.gosub:
            handler.set_jump(old_to_new[handler.gosub])

def load(g):
    """ Load program from ascii, bytecode or protected stream. """
    erase_program()
    if g.filetype == 'B':
        # bytecode file
        state.basic_state.bytecode.seek(1)
        state.basic_state.bytecode.write(g.read())
    elif g.filetype == 'P':
        # protected file
        state.basic_state.bytecode.seek(1)
        state.basic_state.protected = not dont_protect
        protect.unprotect(g, state.basic_state.bytecode)
    else:
        if g.filetype != 'A':
            logging.debug("Incorrect file type '%s' on LOAD", g.filetype)
        # assume ASCII file
        # anything but numbers or whitespace: Direct Statement in File
        merge(g)
    # rebuild line number dict and offsets
    rebuild_line_dict()

def merge(g):
    """ Merge program from ascii or utf8 (if utf8_files is True) stream. """
    while True:
        line = g.read_line()
        if line is None:
            break
        linebuf = tokenise.tokenise_line(line)
        if linebuf.read(1) == '\0':
            # line starts with a number, add to program memory; store_line seeks to 1 first
            store_line(linebuf)
        else:
            # we have read the :
            if util.skip_white(linebuf) not in tk.end_line:
                # direct statement in file
                raise error.RunError(66)

def chain(action, g, jumpnum, delete_lines):
    """ Chain load the program from g and hand over execution. """
    if delete_lines:
        # delete lines from existing code before merge (without MERGE, this is pointless)
        delete(*delete_lines)
    action(g)
    # don't close files!
    # RUN
    flow.jump(jumpnum, err=5)

def save(g):
    """ Save the program to stream g in (A)scii, (B)ytecode or (P)rotected mode. """
    mode = g.filetype
    if state.basic_state.protected and mode != 'P':
        raise error.RunError(5)
    current = state.basic_state.bytecode.tell()
    # skip first \x00 in bytecode
    state.basic_state.bytecode.seek(1)
    if mode == 'B':
        # binary bytecode mode
        g.write(state.basic_state.bytecode.read())
    elif mode == 'P':
        # protected mode
        protect.protect(state.basic_state.bytecode, g)
    else:
        # ascii mode
        while True:
            current_line, output, _ = tokenise.detokenise_line(state.basic_state.bytecode)
            if current_line == -1 or (current_line > max_list_line):
                break
            g.write_line(str(output))
    state.basic_state.bytecode.seek(current)

def list_lines(dev, from_line, to_line):
    """ List line range to console or device. """
    if state.basic_state.protected:
        # don't list protected files
        raise error.RunError(5)
    # 65529 is max insertable line number for GW-BASIC 3.23.
    # however, 65530-65535 are executed if present in tokenised form.
    # in GW-BASIC, 65530 appears in LIST, 65531 and above are hidden
    if to_line is None:
        to_line = max_list_line
    # sort by positions, not line numbers!
    listable = sorted([ state.basic_state.line_numbers[num]
                            for num in state.basic_state.line_numbers
                            if num >= from_line and num <= to_line ])
    for pos in listable:
        state.basic_state.bytecode.seek(pos + 1)
        _, line, _ = tokenise.detokenise_line(state.basic_state.bytecode)
        if dev == backend.scrn_file:
            console.list_line(str(line))
        else:
            dev.write_line(str(line))
    dev.close()
    flow.set_pointer(False)

prepare()
