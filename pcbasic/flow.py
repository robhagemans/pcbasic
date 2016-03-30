"""
PC-BASIC - flow.py
DATA utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import state
import util
import error
import basictoken as tk



def restore(datanum=-1):
    """ Reset data pointer (RESTORE) """
    try:
        state.basic_state.data_pos = 0 if datanum == -1 else state.basic_state.line_numbers[datanum]
    except KeyError:
        raise error.RunError(error.UNDEFINED_LINE_NUMBER)

def read_entry():
    """ READ a unit of DATA. """
    current = state.basic_state.bytecode.tell()
    state.basic_state.bytecode.seek(state.basic_state.data_pos)
    if util.peek(state.basic_state.bytecode) in tk.end_statement:
        # initialise - find first DATA
        util.skip_to(state.basic_state.bytecode, ('\x84',))  # DATA
    if state.basic_state.bytecode.read(1) not in ('\x84', ','):
        raise error.RunError(error.OUT_OF_DATA)
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
