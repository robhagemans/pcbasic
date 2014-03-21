#
# PC-BASIC 3.23 - stat_machine.py
#
# Machine and direct memory access statements
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import util
import tokenise
import vartypes
import expressions
import error
import var

# do-nothing POKE        
def exec_poke(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff) 
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    util.require(ins, util.end_statement)
    
# DEF SEG    
def exec_def_seg(ins):
    # &hb800: text screen buffer; &h13d: data segment
    if util.skip_white_read_if(ins, ('\xE7',)): #=
        var.segment = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    else:
        var.segment = var.data_segment    
    util.require(ins, util.end_statement)

# do-nothing DEF USR    
def exec_def_usr(ins):
    if util.peek(ins) in ('\x11','\x12','\x13','\x14','\x15','\x16','\x17','\x18','\x19','\x1a'): # digits 0--9
        ins.read(1)
    util.require_read(ins, ('\xE7',))     
    vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=0xffff)
    util.require(ins, util.end_statement)
        
# bload: not implemented        
def exec_bload(ins):
    raise error.RunError(73)    

# bsave: not implemented        
def exec_bsave(ins):
    raise error.RunError(73)    
        
# call: not implemented        
def exec_call(ins):
    raise error.RunError(73)    

# do-nothing out       
def exec_out(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    util.require(ins, util.end_statement)

# do-nothing wait        
def exec_wait(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    ander = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, ander)
    xorer = 0
    if util.skip_white_read_if(ins, (',',)):
        xorer = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, xorer)
    util.require(ins, util.end_statement)
            
