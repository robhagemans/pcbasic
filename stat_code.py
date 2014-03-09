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
import automode
import console
import deviceio

# for rnd.clear() on CHAIN
import rnd
# for fileio.close_all() on LOAD, NEW
import fileio


def parse_line_range(ins):
    from_line = -1
    to_line = -1
    if util.skip_white_read_if(ins, ('\x0E',)):   # line number starts
        from_line = vartypes.uint_to_value(bytearray(ins.read(2)))
    elif util.skip_white_read_if(ins, ('.',)):
        from_line = automode.auto_last_stored    
    if util.skip_white_read_if(ins, ('\xEA',)):   # -
        if util.skip_white_read_if(ins, ('\x0E',)):
            to_line = vartypes.uint_to_value(bytearray(ins.read(2)))
        elif util.skip_white_read_if(ins, ('.',)):
            to_line = automode.auto_last_stored    
    else:
        to_line = from_line
    return (from_line, to_line)    
    
def exec_delete(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    program.delete_lines(from_line, to_line)
    # throws back to direct mode
    program.unset_runmode()

def exec_edit(ins):
    if program.protected:
        # don't list protected files
        raise error.RunError(5)
    if util.skip_white(ins) in util.end_statement:
        # undefined line number
        raise error.RunError(8)    
    util.require(ins, ('\x0E', '.'), err=5)   # line number starts
    c = ins.read(1)
    if c == '\x0E':
        from_line = vartypes.uint_to_value(bytearray(ins.read(2)))
        util.require(ins, util.end_statement, err=5)
        if from_line not in program.line_numbers:
            raise error.RunError(8)
    elif c == '.':
        from_line = automode.auto_last_stored
        if from_line == -1:
            raise error.RunError(8)
    program.edit_line(from_line)
    
def exec_auto(ins):
    d = util.skip_white(ins)
    if d == '\x0e':   # line number starts
        ins.read(1)
        automode.auto_linenum = vartypes.uint_to_value(bytearray(ins.read(2)))
    elif d == '.':
        ins.read(1)
        # use current auto_linenum; if not specified before, set to 0.
        automode.auto_linenum = automode.auto_last_stored
        if automode.auto_linenum == -1:
            automode.auto_linenum = 0
    else:
        # default to 10
        automode.auto_linenum = 10
    if util.skip_white_read_if(ins, ','): 
        if util.skip_white_read_if(ins, ('\x0E',)):   # line number starts
            automode.auto_increment = vartypes.uint_to_value(bytearray(ins.read(2))) 
        else:
            pass
    else:
        automode.auto_increment = 10
    util.require(ins, util.end_statement)
    automode.auto_linenum -= automode.auto_increment
    automode.auto_mode = True
    program.prompt = False
    program.unset_runmode()
    
def exec_list(ins):
    from_line, to_line = parse_line_range(ins)
    if util.skip_white_read_if(ins, (',',)):
        filename = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        out = fileio.open_dosname(0, filename, 'O', 'wb')
        list_to_file(out, from_line, to_line)    
        out.close()        
    else:
        util.require(ins, util.end_statement)
        out = StringIO()
        list_to_file(out, from_line, to_line)
        lines = out.getvalue().split(util.endl)
        if lines[-1] == '':
            lines = lines[:-1]
        for line in lines:
            console.check_events()
            console.clear_line(console.row)
            console.write(line + util.endl)
    
def list_to_file(out, from_line, to_line):
    if program.protected:
        # don't list protected files
        raise error.RunError(5)
    if to_line == -1:
        to_line = 65530
    current = program.bytecode.tell()	        
    program.bytecode.seek(1)
    tokenise.detokenise(program.bytecode, out, from_line, to_line)
    program.bytecode.seek(current)
    program.unset_runmode()
    
def exec_llist(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    list_to_file(deviceio.lpt1, from_line, to_line)
    deviceio.lpt1.flush()
        
def exec_load(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    close_files = True
    if util.skip_white_read_if(ins, (',',)):
        util.require_read(ins, 'R')
        close_files = False
    util.require(ins, util.end_statement)
    g = fileio.open_dosname(0, name, mode='L', access='rb', defext='BAS')  
    program.load(g)
    g.close()    
    if close_files:
        fileio.close_all()
    else:
        # in ,R mode, run the file
        program.set_runmode()
        
def exec_chain(ins):
    action = program.merge if util.skip_white_read_if(ins, ('\xBD',)) else program.load     # MERGE
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    jumpnum, common_all = None, False    
    if util.skip_white_read_if(ins, (',',)):
        # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr != None:
            jumpnum = vartypes.pass_int_unpack(expr, maxint=0xffff)
            # negative numbers will be two's complemented into a line number
            if jumpnum < 0:
                jumpnum = 0x10000 + jumpnum            
        if util.skip_white_read_if(ins, (',',)):
            util.skip_white(ins)
            if util.peek(ins, 3).upper() == 'ALL':
                ins.read(3)
                common_all = True
            delete_lines = None            
            if util.skip_white_read_if(ins, (',',)) and util.skip_white_read_if(ins, ('\xa9',)):
                delete_lines = parse_line_range(ins) # , DELETE
    util.require(ins, util.end_statement)
    g = fileio.open_dosname(0, name, mode='L', access='rb', defext='BAS')  
    chain(action, g, jumpnum, common_all, delete_lines)
    g.close()

def chain(action, g, jumpnum, common_all, delete_lines):    
    if delete_lines:
        # delete lines from existing code before merge (without MERGE, this is pointless)
        program.delete_lines(*delete_lines)
    if common_all:
        common, common_arrays = copy.copy(var.variables), copy.copy(var.arrays)
    else:
        # preserve COMMON variables
        common, common_arrays = {}, {}
        for varname in var.common_names:
            try:
                common[varname] = var.variables[varname]
            except KeyError: 
                pass    
        for varname in var.common_array_names:
            try:
                common_arrays[varname] = var.arrays[varname]
            except KeyError:
                pass    
    # preserve deftypes (only for MERGE)
    common_deftype = copy.copy(vartypes.deftype) 
    # preserve option base
    base = var.array_base    
    # load & merge call preparse call reset_program:  # data restore  # erase def fn   # erase defint etc
    action(g)
    # reset random number generator
    rnd.clear()
    # restore only common variables
    var.variables = common
    var.arrays = common_arrays
    # restore option base
    var.array_base = base
    # restore deftypes (if MERGE specified)
    if action == program.merge:
        vartypes.deftype = common_deftype
    # don't close files!
    # RUN
    program.set_runmode()
    if jumpnum != None:
        program.jump(jumpnum)
    
def exec_save(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    g = fileio.open_dosname(0, name, mode='S', access='wb', defext='BAS')  
    #    # cryptic errors given by GW-BASIC:    
    #    if len(name)>8 or len(ext)>3:
    #        # 52: bad file number 
    #        raise error.RunError(errlen)
    #    if ext.find('.') > -1:
    #        # 53: file not found
    #        raise error.RunError(errdots)
    mode = 'B'
    if util.skip_white_read_if(ins, (',',)):
        d = util.skip_white_read(ins)
        if d.upper() not in ('A', 'P'):
            raise error.RunError(2)
        mode = d.upper()
    program.save(g, mode)
    g.close()
    util.require(ins, util.end_statement)
    
def exec_merge(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    g = fileio.open_dosname(0, name, mode='L', access='rb', defext='BAS')  
    program.merge(g)
    g.close()    
    util.require(ins, util.end_statement)
    
def exec_new(ins):
    # deletes the program currently in memory and clears all variables.
    program.clear_program()
    var.clear_variables()
    fileio.close_all()

def exec_renum(ins):
    nums = util.parse_jumpnum_list(ins, size=3, err=2)
    program.renumber(*nums)    

    
