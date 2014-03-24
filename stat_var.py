#
# PC-BASIC 3.23 - stat_var.py
#
# Variable & array statements
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from cStringIO import StringIO

import error
import representation
import vartypes
import var
import rnd

import util
import expressions
import program
import fileio

# for randomize
import console

def parse_var_list(ins):
    readvar = []
    while True:
        readvar.append(list(expressions.get_var_or_array_name(ins)))
        if not util.skip_white_read_if(ins, (',',)):
            break
    return readvar

################################################

def exec_clear(ins):
    program.clear_all()
    # integer expression allowed but ignored
    intexp = expressions.parse_expression(ins, allow_empty=True)
    if intexp:
        expr = vartypes.pass_int_unpack(intexp)
        if expr < 0:
            raise error.RunError(5)
    if util.skip_white_read_if(ins, (',',)):
        # TODO: NOT IMPLEMENTED
        # expression1 is a memory location that, if specified, sets the maximum number of bytes available for use by GW-BASIC        
        exp1 = expressions.parse_expression(ins, allow_empty=True)
        if exp1:
            exp1 = vartypes.pass_int_unpack(exp1)
        if exp1 == 0:
            #  0 leads to illegal fn call
            raise error.RunError(5)
        if util.skip_white_read_if(ins, (',',)):
            # TODO: NOT IMPLEMENTED
            # expression2 sets aside stack space for GW-BASIC. The default is the previous stack space size. 
            # When GW-BASIC is first executed, the stack space is set to 512 bytes, or one-eighth of the available memory, 
            # whichever is smaller.
            exp2 = expressions.parse_expression(ins, empty_err=2)
            if vartypes.pass_int_unpack(exp2) == 0:
                #  0 leads to illegal fn call
                raise error.RunError(5)
    util.require(ins, util.end_statement)

def exec_common(ins):    
    varlist, arraylist = [], []
    while True:
        name = util.get_var_name(ins)
        # array?
        if util.skip_white_read_if(ins, ('[', '(')):
            util.require_read(ins, (']', ')'))
            arraylist.append(name)            
        else:
            varlist.append(name)
        if not util.skip_white_read_if(ins, (',',)):
            break
    var.common_names += varlist
    var.common_array_names += arraylist

def exec_data(ins):
    # ignore rest of statement after DATA
    util.skip_to(ins, util.end_statement)

#
def parse_int_list_var(ins):
    output = [ vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2)) ]   
    while True:
        d = util.skip_white(ins)
        if d == ',': 
            ins.read(1)
            c = util.peek(ins)
            if c in util.end_statement:
                # missing operand
                raise error.RunError(22)
            # if end_expression, syntax error    
            output.append(vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2)))
        elif d in util.end_statement:
            # statement ends - syntax error
            raise error.RunError(2)        
        elif d in util.end_expression:
            break
        else:  
            raise error.RunError(2)
    return output
    
def exec_dim(ins):
    while True:
        name = util.get_var_name(ins) 
        dimensions = [ 10 ]   
        if util.skip_white_read_if(ins, ('[', '(')):
            # at most 255 indices, but there's no way to fit those in a 255-byte command line...
            dimensions = parse_int_list_var(ins)
            while len(dimensions) > 0 and dimensions[-1] == None:
                dimensions = dimensions[:-1]
            if None in dimensions:
                raise error.RunError(2)
            util.require_read(ins, (')', ']'))   
            # yes, we can write dim gh[5) 
        var.dim_array(name, dimensions)            
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)

def exec_deftype(ins, typechar):
    start, stop = -1, -1
    while True:
        d = util.skip_white_read(ins).upper()
        if d < 'A' or d > 'Z':
            raise error.RunError(2)
        else:
            start = ord(d) - ord('A')
            stop = start
        if util.skip_white_read_if(ins, ('\xEA',)):  # token for -
            d = util.skip_white_read(ins).upper()
            if d < 'A' or d > 'Z':
                raise error.RunError(2)
            else:
                stop = ord(d) - ord('A')
        vartypes.deftype[start:stop+1] = [typechar] * (stop-start+1)    
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)

def exec_erase(ins):
    while True:
        var.erase_array(util.get_var_name(ins))
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, end_statement)

def exec_let(ins):
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:    
        # pre-dim even if this is not a legal statement!
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
        var.check_dim_array(name, indices)
    util.require_read(ins, ('\xE7',))   # =
    var.set_var_or_array(name, indices, expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
   
def exec_mid(ins):
    # MID$
    util.require_read(ins, ('(',))
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:    
        # pre-dim even if this is not a legal statement!
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out of range afterwards
        var.check_dim_array(name, indices)
    util.require_read(ins, (',',))
    arglist = expressions.parse_int_list(ins, size=2, err=2)
    if arglist[0] == None:
        raise error.RunError(2)
    start = arglist[0]
    num = arglist[1] if arglist[1] != None else 255
    util.require_read(ins, (')',))
    s = vartypes.pass_string_unpack(var.get_var_or_array(name, indices))
    util.range_check(0, 255, num)
    if num > 0:
        util.range_check(1, len(s), start)
    util.require_read(ins, ('\xE7',)) # =
    val = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    vartypes.str_replace_mid(s, start, num, val)     
    
def exec_lset(ins, justify_right=False):
    name = util.get_var_name(ins)
    util.require_read(ins, ('\xE7',))
    val = expressions.parse_expression(ins)
    var.assign_field_var(name, val, justify_right)

def exec_rset(ins):
    exec_lset(ins, justify_right=True)

def exec_option(ins):
    if util.skip_white_read_if(ins, ('BASE',)):
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = util.skip_white_read(ins)
        if d == '0':
            var.base_array(0)
        elif d == '1':
            var.base_array(1)
        else:
            raise error.RunError(2)
    else:
        raise error.RunError(2)
    util.skip_to(ins, util.end_statement)

def exec_read(ins):
    # reading loop
    for v in parse_var_list(ins):
        # syntax error in DATA line (not type mismatch!) if can't convert to var type
        num = representation.str_to_type(program.read_entry(), v[0][-1])
        if num == None: 
            raise error.RunError(2, program.data_line)
        var.set_var_or_array(*v, value=num)
    util.require(ins, util.end_statement)

def parse_prompt(ins, question_mark):
    # parse prompt
    if util.skip_white_read_if(ins, ('"',)):
        prompt = ''
        # only literal allowed, not a string expression
        d = ins.read(1)
        while d not in util.end_line + ('"',)  : 
            prompt += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1, 1)  
        following = util.skip_white_read(ins)
        if following == ';':
            prompt += question_mark
        elif following != ',':
            raise error.RunError(2)
    else:
        prompt = question_mark
    return prompt

def exec_input(ins):
    finp = expressions.parse_file_number(ins)
    if finp != None:
        varlist = representation.input_vars_file(parse_var_list(ins), finp)
        for v in varlist:
            var.set_var_or_array(*v)
    else:
        # ; to avoid echoing newline
        newline = not util.skip_white_read_if(ins, (';',))
        prompt = parse_prompt(ins, '? ')    
        readvar = parse_var_list(ins)
        # move the program pointer to the start of the statement to ensure correct behaviour for CONT
        pos = ins.tell()
        ins.seek(program.current_statement)
        # read the input
        while True:
            console.write(prompt) 
            line = console.wait_screenline(write_endl=newline)
            varlist = [ v[:] for v in readvar ]
            varlist = representation.input_vars(varlist, fileio.TextFile(StringIO(line), mode='I'))
            if not varlist:
                console.write('?Redo from start\r\n')  # ... good old Redo!
            else:
                break
        for v in varlist:
            var.set_var_or_array(*v)
        ins.seek(pos)        
    util.require(ins, util.end_statement)
    
def exec_line_input(ins):
    finp = expressions.parse_file_number(ins)
    if not finp:
        # ; to avoid echoing newline
        newline = not util.skip_white_read_if(ins, (';',))
        # get prompt    
        prompt = parse_prompt(ins, '')
    # get string variable
    readvar, indices = expressions.get_var_or_array_name(ins)
    if not readvar or readvar[0] == '':
        raise error.RunError(2)
    elif readvar[-1] != '$':
        raise error.RunError(13)    
    # read the input
    if finp:
        line = finp.read_line()
    else:    
        console.write(prompt) 
        line = console.wait_screenline(write_endl=newline)
    var.set_var_or_array(readvar, indices, vartypes.pack_string(line))

def exec_restore(ins):
    if not util.skip_white(ins) in util.end_statement:
        datanum = util.parse_jumpnum(ins, err=8)
    else:
        datanum = -1
    # undefined line number for all syntax errors
    util.require(ins, util.end_statement, err=8)
    program.restore(datanum)

def exec_swap(ins):
    name1 = util.get_var_name(ins)
    util.require_read(ins, (',',))
    name2 = util.get_var_name(ins)
    var.swap_var(name1, name2)
    # if syntax error. the swap has happened
    util.require(ins, util.end_statement)
                             
def exec_def_fn(ins):
    fnname = util.get_var_name(ins)
    # read parameters
    fnvars = []
    if util.skip_white_read_if(ins, ('(',)):
        while True:
            fnvars.append(util.get_var_name(ins))
            if util.skip_white(ins) in util.end_statement + (')',):
                break    
            util.require_read(ins, (',',))
        util.require_read(ins, (')',))
    # read code
    fncode = ''
    util.require_read(ins, ('\xE7',)) #=
    while util.skip_white(ins) not in util.end_statement:
        fncode += ins.read(1)        
    if not program.run_mode:
        # GW doesn't allow DEF FN in direct mode, neither do we (for no good reason, works fine)
        raise error.RunError(12)
    var.functions[fnname] = [fnvars, fncode]
                             
def exec_randomize(ins):
    val = expressions.parse_expression(ins, allow_empty=True)
    # prompt for random seed if not specified
    if not val:
        console.write("Random number seed (-32768 to 32767)? ")
        seed = console.wait_screenline()
        # seed entered on prompt is rounded to int
        val = vartypes.pass_int_keep(representation.str_to_value_keep(vartypes.pack_string(seed)))
    elif val[0] == '$':
        raise error.RunError(5)
    rnd.randomize(val)
    util.require(ins, util.end_statement)
    
