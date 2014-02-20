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

# for music_foreground in CLEAR
import sound
# for randomize
import console

# whitespace for INPUT#, INPUT
# TAB x09 is not whitespace for input#. NUL \x00 and LF \x0a are. 
ascii_white = (' ', '\x00', '\x0a')

def parse_var_list(ins):
    readvar = []
    while True:
        name, indices = expressions.get_var_or_array_name(ins)
        readvar.append([name, indices])
        if not util.skip_white_read_if(ins, ','):
            break
    return readvar

################################################

# CLEAR Command
# To set all numeric variables to zero, all string variables to null, and to close all open files. Options set the end of memory 
# and  reserve the amount of string and stack space available for use by GW-BASIC.
#   Closes all files
#   Clears all COMMON and user variables
#   Resets the stack and string space
#   Releases all disk buffers
#   Turns off any sound
#   Resets sound to music foreground
#   Resets PEN to off
#   Resets STRIG to off
#   Disables ON ERROR trapping
# NOTE:
#   also resets err and erl to 0
#   also resets tthe random number generator
def exec_clear(ins):
    # clear all variables
    var.clear_variables()
    # reset random number generator
    rnd.clear()
    # close all files
    fileio.close_all()
    # release all disk buffers (FIELD)?
    fileio.fields = {}
    # clear ERR and ERL
    error.reset_error()
    # disable error trapping
    error.on_error = None
    error.error_resume = None
    # stop all sound
    sound.stop_all_sound()
    sound.music_foreground = True
    # integer expression allowed but ignored
    intexp = expressions.parse_expression(ins, allow_empty=True)
    if intexp != ('','')  and intexp != None:
        expr = vartypes.pass_int_unpack(intexp)
        if expr < 0:
            raise error.RunError(5)
    if util.skip_white_read_if(ins, ','):
        # NOT IMPLEMENTED
        # expression1 is a memory location that, if specified, sets the maximum number of bytes available for use by GW-BASIC        
        exp1 = expressions.parse_expression(ins, allow_empty=True)
        if exp1 != ('',''):
            exp1 = vartypes.pass_int_unpack(exp1)
        if exp1 == 0:
            #  0 leads to illegal fn call
            raise error.RunError(5)
        if util.skip_white_read_if(ins, ','):
            # NOT IMPLEMENTED
            # expression2 sets aside stack space for GW-BASIC. The default is the previous stack space size. 
            # When GW-BASIC is first executed, the stack space is set to 512 bytes, or one-eighth of the available memory, 
            # whichever is smaller.
            exp2 = expressions.parse_expression(ins, allow_empty=True)
            if exp2 == ('', ''):
                raise error.RunError(2)
            if vartypes.pass_int_unpack(exp2) == 0:
                #  0 leads to illegal fn call
                raise error.RunError(5)
    util.require(ins, util.end_statement)

def exec_common(ins):    
    varlist = []
    arraylist = []
    while True:
        name = util.get_var_name(ins)
        # array?
        if util.skip_white_read_if(ins, ('[', '(')):
            util.require_read(ins, (']', ')'))
            arraylist.append(name)            
        else:
            varlist.append(name)
        if not util.skip_white_read_if(ins, ','):
            break
    var.common_names += varlist
    var.common_array_names += arraylist

def exec_data(ins):
    # ignore rest of statement after DATA
    util.skip_to(ins, util.end_statement)

def exec_dim(ins):
    while True:
        name = util.get_var_name(ins) 
        if name == '':
            # syntax error
            raise error.RunError(2)
        dimensions = [ 10 ]   
        if util.skip_white(ins) in ('[', '('):
            ins.read(1)
            # at most 255 indices, but there's no way to fit those in a 255-byte command line...
            dimensions = expressions.parse_int_list_var(ins, 255)
            while len(dimensions) > 0 and dimensions[-1] == None:
                dimensions = dimensions[:-1]
            if None in dimensions:
                raise error.RunError(2)
            c= util.peek(ins)
            if c not in (')', ']') :   
                # yes, we can write dim gh[5) 
                raise error.RunError(2)
            else:
                ins.read(1)
        var.dim_array(name, dimensions)            
        if not util.skip_white_read_if(ins, ','):
            break
    util.require(ins, util.end_statement)

def exec_deftype(ins, typechar):
    start = -1
    stop = -1
    while True:
        d = util.skip_white_read(ins).upper()
        if d < 'A' or d > 'Z':
            raise error.RunError(2)
        else:
            start = ord(d)-ord('A')
            stop = start
        if util.skip_white_read_if(ins, '\xEA'):  # token for -
            d = util.skip_white_read(ins).upper()
            if d < 'A' or d > 'Z':
                raise error.RunError(2)
            else:
                stop = ord(d)-ord('A')
        vartypes.deftype[start:stop+1] = [typechar]*(stop-start+1)    
        d = util.skip_white(ins)
        if d in util.end_statement:
            break
        elif d != ',':
            raise error.RunError(2)
        ins.read(1)        

def exec_erase(ins):
    while True:
        name = util.get_var_name(ins)
        if name == '':
            raise error.RunError(2)
        var.erase_array(name)
        d = util.skip_white(ins)
        if d in util.end_statement:
            break
        elif d != ',':
            raise error.RunError(2)
        ins.read(1)        

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
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
        var.check_dim_array(name, indices)
    util.require_read(ins, (',',))
    arglist = expressions.parse_int_list(ins, size=2, err=2)
    if arglist[0] == None:
        raise error.RunError(2)
    start = arglist[0]
    num = 0
    if arglist[1] != None:
        num = arglist[1]
    util.require_read(ins, (')',))
    if start < 1 or start > 255:
        raise error.RunError(5)
    if num < 0 or num > 255:
        raise error.RunError(5)
    util.require_read(ins, ('\xE7',)) # =
    val = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    ### str_mid     
    # get a reference to the actual stored bytearray
    s = vartypes.pass_string_unpack(var.get_var_or_array(name, indices))
    start -= 1    
    stop = start + num 
    if arglist[1] == None or stop > len(s):
        stop = len(s)
    if start == stop or start > len(s):
        return 
    if len(val) > stop-start:
        val = val[:stop-start]
    s[start:stop] = val
    
def exec_lset(ins, justify_right=False):
    name = util.get_var_name(ins)
    util.require_read(ins, ('\xE7',))
    val = expressions.parse_expression(ins)
    var.assign_field_var(name, val, justify_right)

def exec_rset(ins):
    exec_lset(ins, justify_right=True)

def exec_option(ins):
    util.skip_white(ins)
    word = ins.read(4)
    if word.upper() == 'BASE':
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = util.skip_white(ins)
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
    readvar = parse_var_list(ins)
    # reading loop
    current = program.bytecode.tell()
    program.bytecode.seek(program.data_pos)
    for v in readvar:
        if util.peek(program.bytecode) in util.end_statement:
            # initialise - find first DATA
            util.skip_to(program.bytecode, '\x84')  # DATA
            program.data_line = program.get_line_number(program.bytecode.tell())
        if program.bytecode.read(1) not in ('\x84', ','):
            # out of DATA
            raise error.RunError(4)
        vals = read_entry(program.bytecode)
        # syntax error in DATA line (not type mismatch!) if can't convert to var type
        num = str_to_type(vals, v[0][-1])
        if num == None: 
            raise error.RunError(2, program.data_line)
        var.set_var_or_array(*v, value=num)
    program.data_pos = program.bytecode.tell()
    program.bytecode.seek(current)
    util.require(ins, util.end_statement)

def read_entry(ins, end=util.end_line, ends=util.end_statement):
    vals = ''
    word = ''
    verbatim = False
    while True:
        # read entry
        if not verbatim:    
            c = util.skip_white(ins)
        else:
            c = util.peek(ins)
        if c == '"':
            ins.read(1)
            if not verbatim:
                verbatim = True
                c = util.peek(ins)
            else:
                verbatim = False
                c = util.skip_white(ins)
                if c not in ends+(',',):
                     raise error.RunError(2)
        if c == '':
            break
        elif not verbatim and c==',':
            break
        elif c in end or (not verbatim and c in ends):
            break
        else:        
            ins.read(1)
            if verbatim:
                vals += c
            else:
                word += c
        # omit trailing whitespace                        
        if c not in util.whitespace:    
            vals += word
            word = ''
    return vals



def parse_prompt(ins):
    # parse prompt
    prompt = ''
    following = ';'
    if util.skip_white_read_if(ins, '"'):
        # only literal allowed, not a string expression
        d = ins.read(1)
        while d not in util.end_line + ('"',)  : 
            prompt += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1,1)  
        following = util.skip_white_read(ins)
        if following not in (';', ','):
            raise error.RunError(2)
    return prompt, following

def text_skip(text_file, skip_range):
    while True:
        d = text_file.peek_char() 
        if d not in skip_range:
            break
        text_file.read_chars(1)    
    return d

def exec_input(ins):
    startpos = program.current_statement
    util.skip_white(ins)
    finp = expressions.parse_file_number(ins)
    if finp != None:
        return exec_input_file(ins, finp)
    # ; to avoid echoing newline
    newline = not util.skip_white_read_if(ins, ';')
    # get the prompt
    prompt, following = parse_prompt(ins)    
    if following == ';':
        prompt += '? '
    # get list of variables
    readvar = parse_var_list(ins)
    # move the program pointer to the start of the statement to ensure correct behaviour for CONT
    pos = ins.tell()
    ins.seek(startpos)
    # read the input
    while True:
        console.write(prompt) 
        text_file = fileio.PseudoFile(StringIO(console.read_screenline(write_endl=newline)))
        values = []
        count_commas = 0    
        for v in readvar:
            typechar = v[0][-1]
            val = str_to_type(input_entry(text_file, allow_quotes=(typechar=='$')), typechar)
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
    ins.seek(pos)        
    util.require(ins, util.end_statement)
            
def exec_input_file(ins, text_file):
    # INPUT#
    # get list of variables
    readvar = parse_var_list(ins)
    # read the input
    for v in readvar:
        typechar = v[0][-1]
        if typechar == '$':
            valstr = input_entry(text_file, allow_quotes=True, end_all = ('\x0d', '\x1a', ''), end_not_quoted = (',', '\x0a'))
        else:
            valstr = input_entry(text_file, allow_quotes=False, end_all = ('\x0d', '\x1a', '', ',', '\x0a', ' '))
        value = str_to_type(valstr, typechar)    
        if value == None:
            value = vartypes.null[typechar]
        var.set_var_or_array(*v, value=value)
        # process the ending char
        if text_file.peek_char() not in ('', '\x1a'):
            text_file.read_chars(1)
    util.require(ins, util.end_statement)


def input_entry(text_file, allow_quotes, end_all=('',), end_not_quoted=(',',)):
    word, blanks = '', ''
    # skip leading spaces and line feeds and NUL. 
    c = text_skip(text_file, ascii_white)
    if c == '"' and allow_quotes:
        quoted = True
        text_file.read_chars(1)
    else:
        quoted = False
    while True:
        # read entry
        c = text_file.read_chars(1)
        if c == '"' and quoted:
            quoted = False
            # ignore blanks after the quotes, position on first non-blank (in correct file, a comma)
            text_skip(text_file, ascii_white)
            text_file.read_chars(1)
            break
        elif c in ascii_white and not quoted:
            blanks += c    
        else:
            word += blanks + c
        if len(word) >= 255:
            break
        c = text_file.peek_char()
        if c in end_all:
            break
        elif c in end_not_quoted and not quoted:
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


def exec_line_input(ins):
    util.skip_white(ins)
    finp = expressions.parse_file_number(ins)
    if finp!=None:
        # get string variable
        #util.skip_white(ins)
        readvar, indices = expressions.get_var_or_array_name(ins)
        # read the input
        inputs = finp.read()
        var.set_var_or_array(readvar, indices, ('$', inputs))
        return
    # ; to avoid echoing newline
    newline = not util.skip_white_read_if(ins,';')
    # get prompt    
    prompt, following = parse_prompt(ins)    
    # get string variable
    readvar,indices = expressions.get_var_or_array_name(ins)
    # read the input
    console.write(prompt) 
    inputs = console.read_screenline(write_endl=newline)
    var.set_var_or_array(readvar, indices, ('$', inputs))

def exec_restore(ins):
    if not util.skip_white(ins) in util.end_statement:
        datanum = util.parse_jumpnum(ins)
    else:
        datanum = -1
    util.require(ins, util.end_statement)
    program.data_line = datanum
    program.data_pos = program.line_numbers[datanum]

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
            if util.skip_white(ins) in util.end_statement+(')',):
                break    
            util.require_read(ins, (',',))
        util.require_read(ins, (')',))
    # read code
    fncode = ''
    util.require_read(ins, ('\xE7',)) #=
    while util.skip_white(ins) not in util.end_statement:
        fncode += ins.read(1)        
    if not program.runmode():
        # GW doesn't allow DEF FN in direct mode, neither do we (for no good reason, works fine)
        raise error.RunError(12)
    var.functions[fnname] = [fnvars, fncode]
                             
def exec_randomize(ins):
    val = expressions.parse_expression(ins, allow_empty=True)
    # prompt for random seed if not specified
    if val == ('', ''):
        console.write("Random number seed (-32768 to 32767)? ")
        # should be interpreted as integer sint if it is
        val = tokenise.str_to_value_keep(('$', console.read_screenline()))
    # RANDOMIZE converts to int in a non-standard way - looking at the first two bytes in the internal representation
    if val[0] == '$':
        raise error.RunError(5)
    elif val[0] == '%':
        s = vartypes.value_to_sint(vartypes.unpack_int(val))    
    else:
        # get the bytes
        s = val[1]
    # on a program line, if a number outside the signed int range (or -32768) is entered,
    # the number is stored as a MBF double or float. Randomize then:
    #   - ignores the first 4 bytes (if it's a double)
    #   - reads the next two
    #   - xors them with the final two (most signifant including sign bit, and exponent)
    # and interprets them as a signed int 
    # e.g. 1#    = /x00/x00/x00/x00 /x00/x00/x00/x81 gets read as /x00/x00 ^ /x00/x81 = /x00/x81 -> 0x10000-0x8100 = -32512 (sign bit set)
    #      0.25# = /x00/x00/x00/x00 /x00/x00/x00/x7f gets read as /x00/x00 ^ /x00/x7f = /x00/x7F -> 0x7F00 = 32512 (sign bit not set)
    #              /xDE/xAD/xBE/xEF /xFF/x80/x00/x80 gets read as /xFF/x80 ^ /x00/x80 = /xFF/x00 -> 0x00FF = 255   
    final_two = s[-2:]
    mask = '\x00\x00'
    if len(s) >= 4:
        mask = s[-4:-2]
    final_two = bytearray(chr(final_two[0]^mask[0]) + chr(final_two[1]^mask[1]))
    rnd.randomize_int(vartypes.sint_to_value(final_two))        
    util.require(ins, util.end_statement)


