#
# PC-BASIC 3.23 - stat_machine.py
#
# Machine and direct memory access statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import util
import vartypes
import expressions
import error


# do-nothing POKE        
def exec_poke(ins):
    addr = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)

    
# do-nothing DEF SEG    
def exec_def_seg(ins):
    if util.skip_white_read_if(ins, '\xE7'): #=
        vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)
        

# do-nothing DEF USR    
def exec_def_usr(ins):
    if util.peek(ins) in tokenise.ascii_digits:
        ins.read(1)
    util.require_read(ins, '\xE7')     
    vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
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

       
# ioctl: not implemented
def exec_ioctl(ins):
    raise error.RunError(73)   
    

# do-nothing out       
def exec_out(ins):
    addr = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)
     

# do-nothing wait        
def exec_wait(ins):
    addr = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    if util.skip_white_read_if(ins, ','):
        j = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)
        
       
            
