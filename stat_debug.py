#
# PC-BASIC 3.23 - stat_debug.py
#
# DEBUG statement and utilities
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import StringIO
import sys
import traceback

import util
import program
import console
import var
import vartypes
import representation
import expressions
import tokenise

from console import debug_print

debug_tron = False
watch_list = []

def exec_DEBUG(ins):
    # this is not a GW-BASIC behaviour, but helps debugging.
    # this is parsed like a REM by the tokeniser.
    # rest of the line is considered to be a python statement
    d = util.skip_white(ins)
    debug = ''
    while util.peek(ins) not in util.end_line:
        d = ins.read(1)
        debug += d
    buf = StringIO.StringIO()
    sys.stdout = buf
    try:
        exec(debug)
    except Exception as e:
        sys.stderr.write(repr(type(e))+'\n')    
        traceback.print_tb(sys.exc_info()[2])
    sys.stdout = sys.__stdout__
    debug_print(buf.getvalue())
        
def debug_step(linum):
    if not tokenise.debug:
        return
    global debug_tron
    if debug_tron:
        debug_print('['+('%i' % linum) +']')
    for (expr, outs) in watch_list:
        debug_print(' ' + expr +' = ')
        outs.seek(2)
        try:
            val = expressions.parse_expression(outs)
            st = vartypes.unpack_string(representation.value_to_str_keep(val, screen=False))
            debug_print(st+'\n')        
        except Exception as e:
            debug_print(repr(type(e))+'\n')
        
# DEBUG user utilities
def dump_program():
    debug_print(program.bytecode.getvalue().encode('hex')+'\n')    

def dump_vars():
    debug_print(repr(var.variables)+'\n')    
    
def dump_screen():
    debug_print('  +' + '-'*console.width+'+\n')
    i = 0
    for row in console.apage.row:
        s = [ c[0] for c in row.buf ]
        i += 1
        debug_print('{0:2}'.format(i) + '|' + ''.join(s)+'|\n')    
    debug_print('  +' + '-'*console.width+'+\n')
        
def trace(on=True):
    global debug_tron
    debug_tron = on        

def watch(expr):
    global watch_list    
    outs = tokenise.tokenise_line('?'+expr) 
    watch_list.append((expr, outs))

