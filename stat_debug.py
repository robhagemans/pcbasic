#
# PC-BASIC 3.23 - stat_debug.py
#
# DEBUG statement and utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import StringIO
import sys

import util
import program
import console
import var
import vartypes
import expressions
import tokenise

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
        print type(e) #"[exception]"
    sys.stdout = sys.__stdout__

    console.write(buf.getvalue())

def debug_print(s):
    sys.stderr.write(s)    
        
def debug_step(linum):
    global debug_tron
    if not tokenise.debug:
        return
    
    if debug_tron:
        debug_print('['+('%i' % linum) +']')
    for expr in watch_list:
        expr.seek(0)
        debug_print(' ' + expr.getvalue()+' = ')
        try:
            val = expressions.parse_expression(expr)
            st = vartypes.value_to_str_keep(val, screen=False)[1]
            debug_print(st+'\n')        
        except Exception as e:
            debug_print(repr(type(e))+'\n')
        
# DEBUG user utilities
def dump_program():
    debug_print(program.bytecode.getvalue().encode('hex')+'\n')    

def dump_vars():
    debug_print(repr(var.variables)+'\n')    
        
def trace(on=True):
    global debug_tron
    debug_tron=True        

def watch(expr):
    global watch_list    
    watch_list.append(StringIO.StringIO(expr))
   
