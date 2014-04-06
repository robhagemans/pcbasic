#
# PC-BASIC 3.23 - debug.py
#
# DEBUG statement and utilities
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import cStringIO
import sys
import logging
import traceback

import util
import program
import console
import var
import vartypes
import representation
import expressions
import tokenise

debug_mode = False
debug_tron = False
watch_list = []

def debug_exec(debug_cmd):
    buf = cStringIO.StringIO()
    sys.stdout = buf
    try:
        exec(debug_cmd)
    except Exception as e:
        debug_handle_exc(e)
        traceback.print_tb(sys.exc_info()[2])
    sys.stdout = sys.__stdout__
    logging.debug(buf.getvalue()[:-1]) # exclude \n
        
def debug_step(linum):
    if not debug_mode:
        return
    global debug_tron
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
        logging.debug(outstr)
        
def debug_handle_exc(e):
    logging.debug(str(type(e))+' '+str(e))    
        
# DEBUG user utilities
def dump_program():
    logging.debug(program.bytecode.getvalue().encode('hex'))    

def dump_vars():
    logging.debug(repr(var.variables))    
    
def show_screen():
    logging.debug('  +' + '-'*console.width+'+')
    i = 0
    lastwrap = False
    for row in console.apage.row:
        s = [ c[0] for c in row.buf ]
        i += 1
        outstr = '{0:2}'.format(i)
        if lastwrap:
            outstr += ('\\')
        else:
            outstr += ('|')
        outstr += (''.join(s))
        if row.wrap:
            logging.debug(outstr + '\\')
        else:
            logging.debug(outstr + '| {0:2}'.format(row.end))        
        lastwrap = row.wrap    
    logging.debug('  +' + '-'*console.width+'+')

def show_program():
    code = program.bytecode.getvalue()
    offset_val, p = 0, 0
    for key in sorted(program.line_numbers.keys())[1:]:
        offset, linum = code[p+1:p+3], code[p+3:p+5]
        last_offset = offset_val
        offset_val = vartypes.uint_to_value(bytearray(offset)) - program.program_memory_start
        linum_val  = vartypes.uint_to_value(bytearray(linum))
        logging.debug(    (code[p:p+1].encode('hex') + ' ' +
                        offset.encode('hex') + ' (+%03d) ' +  
                        code[p+3:p+5].encode('hex') + ' [%05d] ' + 
                        code[p+5:program.line_numbers[key]].encode('hex'))
                    % (offset_val - last_offset, linum_val) )
        p = program.line_numbers[key]
    logging.debug(code[p:p+1].encode('hex') + ' ' +
                code[p+1:p+3].encode('hex') + ' (ENDS) ' +  
                code[p+3:p+5].encode('hex') + ' ' + code[p+5:].encode('hex'))   
        
def trace(on=True):
    global debug_tron
    debug_tron = on        

def watch(expr):
    global watch_list    
    outs = tokenise.tokenise_line('?'+expr) 
    watch_list.append((expr, outs))

