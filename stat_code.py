#
# PC-BASIC 3.23 - stat_code.py
#
# Program editing statements
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


from cStringIO import StringIO

import error
import vartypes
import util
import expressions
import program
import automode
import console
import deviceio
import run
# for fileio.close_all() on LOAD, NEW
import fileio


def parse_line_range(ins):
    from_line = parse_jumpnum_or_dot(ins, allow_empty=True)    
    if util.skip_white_read_if(ins, ('\xEA',)):   # -
        to_line = parse_jumpnum_or_dot(ins, allow_empty=True)
    else:
        to_line = from_line
    return (from_line, to_line)    

def parse_jumpnum_or_dot(ins, allow_empty=False, err=2):
    c = util.skip_white_read(ins)
    if c == '\x0E':
        return vartypes.uint_to_value(bytearray(ins.read(2)))
    elif c == '.':
        return program.last_stored
    else:        
        if allow_empty:
            ins.seek(-len(c), 1)
            return None
        raise error.RunError(err)
            
def exec_delete(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    program.delete_lines(from_line, to_line)
    # throws back to direct mode
    program.set_runmode(False)

def exec_edit(ins):
    if program.protected:
        # don't list protected files
        raise error.RunError(5)
    if util.skip_white(ins) in util.end_statement:
        # undefined line number
        raise error.RunError(8)    
    from_line = parse_jumpnum_or_dot(ins, err=5)
    if from_line == None or from_line not in program.line_numbers:
        raise error.RunError(8)
    util.require(ins, util.end_statement, err=5)
    program.edit_line(from_line)
    # suppress prompt, move cursor?
    run.prompt = False
    
def exec_auto(ins):
    linenum = parse_jumpnum_or_dot(ins, allow_empty=True)
    increment = None
    if util.skip_white_read_if(ins, (',',)): 
        increment = util.parse_jumpnum(ins, allow_empty=True)
    util.require(ins, util.end_statement)
    automode.auto_loop(linenum, increment)
    program.set_runmode(False)
    
def exec_list(ins):
    from_line, to_line = parse_line_range(ins)
    if util.skip_white_read_if(ins, (',',)):
        filename = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        out = fileio.open_file_or_device(0, filename, 'O')
        program.list_to_file(out, from_line, to_line)    
        out.close()        
    else:
        util.require(ins, util.end_statement)
        out = StringIO()
        program.list_to_file(out, from_line, to_line)
        lines = out.getvalue().split('\r\n')
        if lines[-1] == '':
            lines = lines[:-1]
        for line in lines:
            console.check_events()
            console.clear_line(console.row)
            console.write_line(line)
    
def exec_llist(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    list_to_file(deviceio.lpt1, from_line, to_line)
    deviceio.lpt1.flush()
        
def exec_load(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    comma = util.skip_white_read_if(ins, (',',))
    if comma:
        util.require_read(ins, 'R')
    util.require(ins, util.end_statement)
    program.load(fileio.open_file_or_device(0, name, mode='L', defext='BAS'))
    if comma:
        # in ,R mode, don't close files; run the program
        program.jump(None)
    else:
        fileio.close_all()
        
def exec_chain(ins):
    action = program.merge if util.skip_white_read_if(ins, ('\xBD',)) else program.load     # MERGE
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    jumpnum, common_all, delete_lines = None, False, None    
    if util.skip_white_read_if(ins, (',',)):
        # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr != None:
            jumpnum = vartypes.pass_int_unpack(expr, maxint=0xffff)
            # negative numbers will be two's complemented into a line number
            if jumpnum < 0:
                jumpnum = 0x10000 + jumpnum            
        if util.skip_white_read_if(ins, (',',)):
            if util.skip_white_read_if(ins, ('ALL',)):
                common_all = True
            if util.skip_white_read_if(ins, (',',)) and util.skip_white_read_if(ins, ('\xa9',)):
                delete_lines = parse_line_range(ins) # , DELETE
    util.require(ins, util.end_statement)
    program.chain(action, fileio.open_file_or_device(0, name, mode='L', defext='BAS'), jumpnum, common_all, delete_lines)

def exec_save(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    mode = 'B'
    if util.skip_white_read_if(ins, (',',)):
        mode = util.skip_white_read(ins).upper()
        if mode not in ('A', 'P'):
            raise error.RunError(2)
    program.save(fileio.open_file_or_device(0, name, mode='S', defext='BAS'), mode)
    util.require(ins, util.end_statement)
    
def exec_merge(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    program.merge(fileio.open_file_or_device(0, name, mode='L', defext='BAS') )
    util.require(ins, util.end_statement)
    
def exec_new(ins):
    # deletes the program currently in memory and clears all variables.
    program.clear_program()

def exec_renum(ins):
    new, old, step = None, None, None
    if util.skip_white(ins) not in util.end_statement: 
        new = parse_jumpnum_or_dot(ins, allow_empty=True)
        if util.skip_white_read_if(ins, (',',)):
            old = parse_jumpnum_or_dot(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                step = util.parse_jumpnum(ins, allow_empty=True) # returns -1 if empty
    util.require(ins, util.end_statement)            
    if step != None and step < 1: 
        raise error.RunError(5)
    program.renum(new, old, step)
    
