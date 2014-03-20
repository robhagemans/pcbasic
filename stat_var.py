#
# PC-BASIC 3.23 - stat_var.py
#
# Variable & array statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from cStringIO import StringIO

import error
import fp
import vartypes
import var
import rnd

import util
import expressions
import tokenise
import program
import fileio

# for randomize
import console

# whitespace for INPUT#, INPUT
# TAB x09 is not whitespace for input#. NUL \x00 and LF \x0a are. 
ascii_white = (' ', '\x00', '\x0a')

def parse_var_list(ins):
    readvar = []
    while True:
        readvar.append(expressions.get_var_or_array_name(ins))
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


def parse_int_list_var(ins, size, err=5):
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
            output.append(vartypes.pass_int_unpack(expressios.parse_expression(ins, empty_err=2)))
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
            dimensions = parse_int_list_var(ins, 255)
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
        num = str_to_type(program.read_entry(), v[0][-1])
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
        input_vars_file(parse_var_list(ins), finp)
    else:
        # ; to avoid echoing newline
        newline = not util.skip_white_read_if(ins, (';',))
        prompt = parse_prompt(ins, '? ')    
        readvar = parse_var_list(ins)
        # move the program pointer to the start of the statement to ensure correct behaviour for CONT
        pos = ins.tell()
        ins.seek(program.current_statement)
        # read the input
        input_vars(prompt, readvar, newline)
        ins.seek(pos)        
    util.require(ins, util.end_statement)

####

def input_vars_file(readvar, text_file):
    for v in readvar:
        typechar = v[0][-1]
        if typechar == '$':
            valstr = input_entry(text_file, allow_quotes=True, end_all = ('\x0d', '\x1a'), end_not_quoted = (',', '\x0a'))
        else:
            valstr = input_entry(text_file, allow_quotes=False, end_all = ('\x0d', '\x1a', ',', '\x0a', ' '))
        value = str_to_type(valstr, typechar)    
        if value == None:
            value = vartypes.null[typechar]
        # process the ending char (this may raise FIELD OVERFLOW but should avoid INPUT PAST END)
        if not text_file.end_of_file() and text_file.peek_char() not in ('', '\x1a'):
            text_file.read_chars(1)
        # and then set the value
        var.set_var_or_array(*v, value=value)

def input_vars(prompt, readvar, newline):
    while True:
        console.write(prompt) 
        text_file = fileio.TextFile(StringIO(console.read_screenline(write_endl=newline)), mode='I')
        values, count_commas = [], 0
        for v in readvar:
            typechar = v[0][-1]
            valstr = input_entry(text_file, allow_quotes=(typechar=='$'), end_all=('',))
            val = str_to_type(valstr, typechar)
            values.append(val)
            if text_file.peek_char() != ',':
                break
            else:
                text_file.read_chars(1)
                count_commas += 1
        if len(readvar) != len(values) or count_commas != len(readvar)-1 or None in values:
            console.write('?Redo from start' + util.endl)  # ... good old Redo!
        else:
            break
    for i in range(len(readvar)):
        var.set_var_or_array(*readvar[i], value=values[i])
            
def text_skip(text_file, skip_range):
    d = ''
    while True:
        if text_file.end_of_file():
            break
        d = text_file.peek_char() 
        if d not in skip_range:
            break
        text_file.read_chars(1)
    return d

def input_entry(text_file, allow_quotes, end_all=(), end_not_quoted=(',',)):
    word, blanks = '', ''
    # skip leading spaces and line feeds and NUL. 
    c = text_skip(text_file, ascii_white)
    if c in end_all + end_not_quoted:
        return ''
    quoted = (c == '"' and allow_quotes)
    if quoted:
        text_file.read_chars(1)
    while True:
        # read entry
        if text_file.end_of_file():
            break
        c = ''.join(text_file.read_chars(1))
        if c in end_all or (c in end_not_quoted and not quoted):
            # on KYBD: text file, this will do nothing - comma is swallowed
            text_file.seek(-len(c), 1)
            break
        elif c == '"' and quoted:
            quoted = False
            # ignore blanks after the quotes
            c = text_skip(text_file, ascii_white)
            break
        elif c in ascii_white and not quoted:
            blanks += c    
        else:
            word += blanks + c
        if len(word)+len(blanks) >= 255:
            text_file.seek(-len(c), 1)
            break
    return word

def str_to_type(word, type_char):
    if type_char == '$':
        return vartypes.pack_string(bytearray(word))
    else:
        try:
            return fp.pack(fp.from_str(word, False))
        except AttributeError:
            return None
#####

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
        inputs = finp.read_line()
    else:    
        console.write(prompt) 
        inputs = console.read_screenline(write_endl=newline)
    var.set_var_or_array(readvar, indices, vartypes.pack_string(inputs))

def exec_restore(ins):
    if not util.skip_white(ins) in util.end_statement:
        datanum = util.parse_jumpnum(ins)
    else:
        datanum = -1
    util.require(ins, util.end_statement)
    program.restore_data(datanum)

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
    if val == None:
        console.write("Random number seed (-32768 to 32767)? ")
        # should be interpreted as integer sint if it is
        val = tokenise.str_to_value_keep(('$', console.read_screenline()))
    # RANDOMIZE converts to int in a non-standard way - looking at the first two bytes in the internal representation
    if val[0] == '$':
        raise error.RunError(5)
    rnd.randomize(val)
    util.require(ins, util.end_statement)
    
