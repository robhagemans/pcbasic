#
# PC-BASIC 3.23 - stat_code.py
#
# Program editing statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


from cStringIO import StringIO
import copy

import error
import vartypes
import var
import util
import expressions
import tokenise
import program
import oslayer
import automode
import console
import deviceio

# for rnd.clear() on CHAIN
import rnd
# for fileio.close_all() on LOAD, NEW
import fileio


    
def parse_line_range(ins):
    from_line=-1
    to_line=-1
    d = util.skip_white(ins)
    if d=='\x0E':   # line number starts
        ins.read(1)
        from_line=vartypes.uint_to_value(ins.read(2))
        if util.skip_white_read_if(ins, '\xEA'):  # -
            if util.skip_white_read(ins)=='\x0e':
                to_line=vartypes.uint_to_value(ins.read(2))
        else:
            to_line = from_line
    
    elif d=='\xEA':
        ins.read(1)
        if util.skip_white_read_if(ins, '\x0e'):
            to_line=vartypes.uint_to_value(ins.read(2))
            
    return (from_line, to_line)    




    
def exec_delete(ins):
    [from_line, to_line] = parse_line_range(ins)
    util.require(ins, util.end_statement)
    program.delete_lines(from_line, to_line)
    # throws back to direct mode
    program.unset_runmode()
    
    
    


def exec_edit(ins):
    if program.protected:
        # don't list protected files
        raise error.RunError(5)
    
    util.require_read(ins, '\x0E', err=5)   # line number starts
    from_line=vartypes.uint_to_value(ins.read(2))
    util.require(ins, util.end_statement, err=5)
    if from_line not in program.line_numbers:
        raise error.RunError(8)
    program.edit_line(from_line)
    


    
def exec_auto(ins):
    #global auto_increment, auto_linenum
    #global auto_mode
    
    d = util.skip_white(ins)
    automode.auto_linenum=10
    if d=='\x0e':   # line number starts
        ins.read(1)
        automode.auto_linenum=vartypes.uint_to_value(ins.read(2))
    elif d=='.':
        ins.read(1)
        automode.auto_linenum = program.linenum
        
    if util.skip_white_read_if(ins, ','): 
        if util.skip_white_read_if(ins, '\x0e'):   # line number starts
            automode.auto_increment = vartypes.uint_to_value(ins.read(2)) 
        else:
            pass
    else:
        automode.auto_increment=10
            
    util.require(ins, util.end_statement)

    automode.auto_linenum -= automode.auto_increment
    automode.auto_mode=True
    program.prompt=False
    program.unset_runmode()
        
    
    
def exec_list(ins, out=None):
    if program.protected:
        # don't list protected files
        raise error.RunError(5)
    
    [from_line, to_line] = parse_line_range(ins)
    util.require(ins, util.end_statement)

    if out==None:
        out = console
    if out==console:
        output = StringIO()
    else:
        output = out

    current = program.bytecode.tell()	        
    program.bytecode.seek(1)
    tokenise.detokenise(program.bytecode, output, from_line, to_line)
    program.bytecode.seek(current)
    
    if out == console:
        lines = output.getvalue().split(util.endl)
        if lines[-1]=='':
            lines = lines[:-1]
        for line in lines:
            console.check_events()
            console.clear_line(console.row)
            console.write(line+util.endl)
    
    
def exec_llist(ins):
    exec_list(ins, deviceio.lpt1)
    deviceio.lpt1.flush()
    
        
def exec_load(ins):
    name = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    name = oslayer.dospath_read(name, 'BAS', 53)
        
    close_files = True
    if util.skip_white(ins) == ',':
        if ins.read(2).upper() != ',R':
            raise error.RunError(2)
        else:
            close_files = False
    
    util.require(ins, util.end_statement)
    
    g = oslayer.safe_open(name, 'rb')
    program.load(g)
    g.close()    
    
    if close_files:
        fileio.close_all()
    else:
        # in ,R mode, run the file
        program.set_runmode()
    

        
def exec_chain(ins):
    action = program.load
    if util.skip_white_read_if(ins, '\xBD'): # MERGE
        action = program.merge
    
    name = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    name = oslayer.dospath_read(name, 'BAS', 53)
    
    jumpnum=-1    
    d = util.skip_white(ins)
    if d == ',':
        ins.read(1)
        d = util.skip_white(ins)
        
        # check for an expression that indicates a line in the other program. not stored as a jumpnum (to avoid RENUM)
        # NOTE in GW, negative numbers will be two's complemented into a line number!
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr != ('',''):
            jumpnum = vartypes.pass_int_keep(expr, maxint=0xffff)[1]
            if jumpnum <0:
                jumpnum = 0x10000 + jumpnum            
        
    elif d not in util.end_statement:
        raise error.RunError(2)
    
    # preserve COMMON variables
    common = {}
    common_arrays= {}
    # reset deftypes unless ALL specified
    common_deftype = ['!']*26
    
    for varname in var.common_names:
        if varname in var.variables:
            common[varname] = var.variables[varname]
    for varname in var.common_array_names:
        if varname in var.arrays:
            common_arrays[varname] = var.arrays[varname]
    
    d = util.skip_white(ins)
    if d==',':
        ins.read(1)
        if util.peek(ins, 3).upper() == 'ALL':
            ins.read(3)
            common = copy.copy(var.variables)
            common_arrays = copy.copy(var.arrays)
            # preserve DEFTYPES
            common_deftype = copy.copy(var.deftype)
    elif d not in util.end_statement:
        raise error.RunError(2)
            
    d = util.skip_white(ins)
    if d==',':
        ins.read(1)
        if util.peek(ins) == '\xa9': # DELETE
            ins.read(2)
            #delete lines from existing code before merge
            # (without MERGE, this is pointless)
            [from_line, to_line] = parse_line_range(ins)
            program.delete_lines(from_line, to_line)
    
    # TODO: should the program be loaded or not if we see this error?
    util.require(ins, util.end_statement)
    
    # keep option base
    base = var.array_base    
    
    # load & merge call preparse call reset_program, 
    # data restore
    # erase def fn
    # erase defint etc
    
    g = oslayer.safe_open(name, 'rb')
    action(g)
    g.close()    
    
    # reset random number generator
    rnd.clear()
    
    # keep only common variables
    var.variables = common
    var.arrays = common_arrays
    # keep option base
    var.array_base = base
    # keep deftypes (if ALL specified)
    var.deftype = common_deftype
    # don't close files!
    
    # RUN
    program.set_runmode()
    if jumpnum !=-1:
        program.jump(jumpnum)

    
def exec_save(ins):
    name = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    # 76 is path not found
    name = oslayer.dospath_write(name, 'BAS', 76) 

    #    # cryptic errors given by GW-BASIC:    
    #    if len(name)>8 or len(ext)>3:
    #        # 52: bad file number 
    #        raise error.RunError(errlen)
    #    if ext.find('.') > -1:
    #        # 53: file not found
    #        raise error.RunError(errdots)
    
    mode = 'B'
    d = util.skip_white_read(ins)
    if d== ',':
        d = util.skip_white_read(ins)
        if d.upper() not in ('A', 'P'):
            raise error.RunError(2)
            return False
        mode=d.upper()
    elif d== ':':
        ins.seek(-1,1)
    elif d in ('', '\x00'):
        pass
    else:
        raise error.RunError(2)
        return False

    # append BAS if no extension specified    
    if name.find('.') < 0:
        name = name + '.BAS'
        
    g = oslayer.safe_open(name, 'wb')
    program.save(g, mode)
    g.close()

    util.require(ins, util.end_statement)
    
    
def exec_merge(ins):
    name = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    name = oslayer.dospath_read(name, 'BAS', 53)
        
    g = oslayer.safe_open(name, 'rb')
    program.merge(g)
    g.close()    
        
    util.require(ins, util.end_statement)
    
    
def exec_new():
    # NEW Command
    #   To delete the program currently in memory and clear all variables.
    program.clear_program()
    var.clear_variables()
    fileio.close_all()


def exec_renum(ins):
    nums = util.parse_jumpnum_list(ins, size=3, err=2)
    program.renumber(*nums)    

    
