"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013, 2014, 2015 Rob Hagemans 
This file is released under the GNU GPL version 3.
"""

from StringIO import StringIO
import sys
import traceback

import config
import logging
import state
import vartypes
import representation
import expressions
import tokenise
import program

debug_mode = False
debug_tron = False
watch_list = []

def prepare():
    """ Initialise the debug module. """
    global debug_mode
    if config.options['debug']:
        debug_mode = True

def debug_exec(debug_cmd):
    """ Execute a debug command. """
    buf = StringIO()
    save_stdout = sys.stdout
    sys.stdout = buf
    try:
        exec(debug_cmd)
    except Exception as e:
        debug_handle_exc(e)
        traceback.print_tb(sys.exc_info()[2])
    sys.stdout = save_stdout
    logging.debug(buf.getvalue()[:-1]) # exclude \n

def debug_step(linum):
    """ Execute traces and watches on a program step. """
    if not debug_mode:
        return
    outstr = ''
    if debug_tron:
        outstr += ('['+('%i' % linum) +']')
    for (expr, outs) in watch_list:
        outstr += (' ' + expr +' = ')
        outs.seek(2)
        try:
            val = expressions.parse_expression(outs)
            st = vartypes.unpack_string(representation.value_to_str_keep(val, screen=False))
            if val[0] == '$':
                outstr += ('"'+st+'"')
            else:
                outstr += (st)
        except Exception as e:
            debug_handle_exc(e)
    if outstr:
        logging.debug(outstr)

def debug_handle_exc(e):
    """ Handle debugging exception. """
    logging.debug(str(type(e))+' '+str(e))

# DEBUG user utilities

def dump_program():
    """ Hex dump the program to the log. """
    logging.debug(state.basic_state.bytecode.getvalue().encode('hex'))

def dump_vars():
    """ Dump all variables to the log. """
    logging.debug(repr(state.basic_state.variables))

def show_screen():
    """ Copy the screen buffer to the log. """
    logging.debug('  +' + '-'*state.console_state.screen.mode.width+'+')
    i = 0
    lastwrap = False
    for row in state.console_state.screen.apage.row:
        s = [ c[0] for c in row.buf ]
        i += 1
        outstr = '{0:2}'.format(i)
        if lastwrap:
            outstr += ('\\')
        else:
            outstr += ('|')
        outstr += (''.join(s))
        if row.wrap:
            logging.debug(outstr + '\\ {0:2}'.format(row.end))
        else:
            logging.debug(outstr + '| {0:2}'.format(row.end))
        lastwrap = row.wrap
    logging.debug('  +' + '-'*state.console_state.screen.mode.width+'+')

def show_program():
    """ Write a marked-up hex dump of the program to the log. """
    code = state.basic_state.bytecode.getvalue()
    offset_val, p = 0, 0
    for key in sorted(state.basic_state.line_numbers.keys())[1:]:
        offset, linum = code[p+1:p+3], code[p+3:p+5]
        last_offset = offset_val
        offset_val = vartypes.uint_to_value(bytearray(offset)) - program.program_memory_start
        linum_val  = vartypes.uint_to_value(bytearray(linum))
        logging.debug(    (code[p:p+1].encode('hex') + ' ' +
                        offset.encode('hex') + ' (+%03d) ' +
                        code[p+3:p+5].encode('hex') + ' [%05d] ' +
                        code[p+5:state.basic_state.line_numbers[key]].encode('hex')),
                     offset_val - last_offset, linum_val )
        p = state.basic_state.line_numbers[key]
    logging.debug(code[p:p+1].encode('hex') + ' ' +
                code[p+1:p+3].encode('hex') + ' (ENDS) ' +
                code[p+3:p+5].encode('hex') + ' ' + code[p+5:].encode('hex'))

def trace(on=True):
    """ Switch line number tracing on or off. """
    global debug_tron
    debug_tron = on

def watch(expr):
    """ Add an expression to the watch list. """
    outs = tokenise.tokenise_line('?'+expr)
    watch_list.append((expr, outs))

prepare()
