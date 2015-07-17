"""
PC-BASIC - flow.py
Program pointer utilities

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import state
import fp
import var
import vartypes
import util
import error
import basictoken as tk

# pointer position: False for direct line, True for program
state.basic_state.run_mode = False
# line number tracing
state.basic_state.tron = False

def init_program():
    """ Initialise the stacks and pointers for a new program. """
    # stop running if we were
    set_pointer(False)
    # reset loop stacks
    state.basic_state.gosub_return = []
    state.basic_state.for_next_stack = []
    state.basic_state.while_wend_stack = []
    # reset program pointer
    state.basic_state.bytecode.seek(0)
    # reset stop/cont
    state.basic_state.stop = None
    # reset data reader
    restore()

def restore(datanum=-1):
    """ Reset data pointer (RESTORE) """
    try:
        state.basic_state.data_pos = 0 if datanum == -1 else state.basic_state.line_numbers[datanum]
    except KeyError:
        raise error.RunError(8)

def set_pointer(new_runmode, pos=None):
    """ Set program pointer to the given codestream and position. """
    state.basic_state.run_mode = new_runmode
    state.console_state.sound.persist(new_runmode)
    codestream = get_codestream()
    if pos != None:
        # jump to position, if given
        codestream.seek(pos)
    else:
        # position at end - don't execute anything unless we jump
        codestream.seek(0, 2)

def get_codestream():
    """ Get the current codestream. """
    return state.basic_state.bytecode if state.basic_state.run_mode else state.basic_state.direct_line

def jump_gosub(jumpnum, handler=None):
    """ Execute jump for a GOSUB. """
    # set return position
    state.basic_state.gosub_return.append((get_codestream().tell(), state.basic_state.run_mode, handler))
    jump(jumpnum)

def jump_return(jumpnum):
    """ Execute jump for a RETURN. """
    try:
        pos, orig_runmode, handler = state.basic_state.gosub_return.pop()
    except IndexError:
        # RETURN without GOSUB
        raise error.RunError(3)
    # returning from ON (event) GOSUB, re-enable event
    if handler:
        # if stopped explicitly using STOP, we wouldn't have got here; it STOP is run  inside the trap, no effect. OFF in trap: event off.
        handler.stopped = False
    if jumpnum == None:
        # go back to position of GOSUB
        set_pointer(orig_runmode, pos)
    else:
        # jump to specified line number
        jump(jumpnum)

def loop_init(ins, forpos, nextpos, varname, start, stop, step):
    """ Initialise a FOR loop. """
    # set start to start-step, then iterate - slower on init but allows for faster iterate
    var.set_var(varname, vartypes.number_add(start, vartypes.number_neg(step)))
    # NOTE: all access to varname must be in-place into the bytearray - no assignments!
    sgn = vartypes.unpack_int(vartypes.number_sgn(step))
    state.basic_state.for_next_stack.append((forpos, nextpos, varname[-1], state.basic_state.variables[varname], number_unpack(stop), number_unpack(step), sgn))
    ins.seek(nextpos)

def number_unpack(value):
    """ Unpack a number value. """
    if value[0] in ('#', '!'):
        return fp.unpack(value)
    else:
        return vartypes.unpack_int(value)

def number_inc_gt(typechar, loopvar, stop, step, sgn):
    """ Increase number and check if it exceeds a limit. """
    if sgn == 0:
        return False
    if typechar in ('#', '!'):
        fp_left = fp.from_bytes(loopvar).iadd(step)
        loopvar[:] = fp_left.to_bytes()
        return fp_left.gt(stop) if sgn > 0 else stop.gt(fp_left)
    else:
        int_left = vartypes.sint_to_value(loopvar) + step
        loopvar[:] = vartypes.value_to_sint(int_left)
        return int_left > stop if sgn > 0 else stop > int_left

def loop_iterate(ins):
    """ Iterate a loop (NEXT). """
    # we MUST be at nextpos to run this
    # find the matching NEXT record
    pos = ins.tell()
    num = len(state.basic_state.for_next_stack)
    for depth in range(num):
        forpos, nextpos, typechar, loopvar, stop, step, sgn = state.basic_state.for_next_stack[-depth-1]
        if pos == nextpos:
            # only drop NEXT record if we've found a matching one
            state.basic_state.for_next_stack = state.basic_state.for_next_stack[:len(state.basic_state.for_next_stack)-depth]
            break
    else:
        # next without for
        raise error.RunError(1)
    # increment counter
    loop_ends = number_inc_gt(typechar, loopvar, stop, step, sgn)
    if loop_ends:
        state.basic_state.for_next_stack.pop()
    else:
        ins.seek(forpos)
    return loop_ends

def resume(jumpnum):
    """ Execute jump for a RESUME instruction. """
    start_statement, runmode = state.basic_state.error_resume
    state.basic_state.errn = 0
    state.basic_state.error_handle_mode = False
    state.basic_state.error_resume = None
    state.basic_state.events.suspend_all = False
    if jumpnum == 0:
        # RESUME or RESUME 0
        set_pointer(runmode, start_statement)
    elif jumpnum == -1:
        # RESUME NEXT
        set_pointer(runmode, start_statement)
        util.skip_to(get_codestream(), tk.end_statement, break_on_first_char=False)
    else:
        # RESUME n
        jump(jumpnum)

def jump(jumpnum, err=8):
    """ Execute jump for a GOTO or RUN instruction. """
    if jumpnum == None:
        set_pointer(True, 0)
    else:
        try:
            # jump to target
            set_pointer(True, state.basic_state.line_numbers[jumpnum])
        except KeyError:
            # Undefined line number
            raise error.RunError(err)

def read_entry():
    """ READ a unit of DATA. """
    current = state.basic_state.bytecode.tell()
    state.basic_state.bytecode.seek(state.basic_state.data_pos)
    if util.peek(state.basic_state.bytecode) in tk.end_statement:
        # initialise - find first DATA
        util.skip_to(state.basic_state.bytecode, ('\x84',))  # DATA
    if state.basic_state.bytecode.read(1) not in ('\x84', ','):
        # out of DATA
        raise error.RunError(4)
    vals, word, literal = '', '', False
    while True:
        # read next char; omit leading whitespace
        if not literal and vals == '':
            c = util.skip_white(state.basic_state.bytecode)
        else:
            c = util.peek(state.basic_state.bytecode)
        # parse char
        if c == '' or (not literal and c == ',') or (c in tk.end_line or (not literal and c in tk.end_statement)):
            break
        elif c == '"':
            state.basic_state.bytecode.read(1)
            literal = not literal
            if not literal:
                util.require(state.basic_state.bytecode, tk.end_statement + (',',))
        else:
            state.basic_state.bytecode.read(1)
            if literal:
                vals += c
            else:
                word += c
            # omit trailing whitespace
            if c not in tk.whitespace:
                vals += word
                word = ''
    state.basic_state.data_pos = state.basic_state.bytecode.tell()
    state.basic_state.bytecode.seek(current)
    return vals
