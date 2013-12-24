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



import sys
import StringIO

import glob
import error
import fp
import vartypes
import var
import rnd

from util import *

import expressions
import tokenise
import program
import fileio

# for music_foreground in CLEAR
import stat_graph


def exec_clear(ins):
    # CLEAR Command
    # To set all numeric variables to zero, all string variables to null, and to close all open files. Options set the end of memory 
    # and  reserve the amount of string and stack space available for use by GW-BASIC.
    #
    #   Closes all files
    #   Clears all COMMON and user variables
    #   Resets the stack and string space
    #   Releases all disk buffers
    #   Turns off any sound
    #   Resets sound to music foreground
    #   Resets PEN to off
    #   Resets STRIG to off
    #   Disables ON ERROR trapping

    #   also resets err and erl to 0
    #   also resets tthe random number generator
        
    # clear all variables
    var.clear_variables()
    # reset random number generator
    rnd.clear()
    
    # close all files
    fileio.close_all()
    # release all disk buffers (FIELD)?
    fileio.fields={}
    
    # clear ERR and ERL
    error.reset_error()
    # disable error trapping
    error.on_error=None
    error.error_resume = None
    
    # stop all sound
    glob.sound.stop_all_sound()
    stat_graph.music_foreground=True

    # integer expression allowed but ignored
    intexp = expressions.parse_expression(ins, allow_empty=True)
    
    if intexp != ('','')  and intexp != None:
        vartypes.pass_int_keep(intexp)
    
    
    if skip_white_read_if(ins, ','):

        # NOT IMPLEMENTED
        
        # expression1 is a memory location that, if specified, sets the maximum number of bytes available for use by GW-BASIC        
        exp1 = expressions.parse_expression(ins, allow_empty=True)
        if exp1 != ('',''):
            exp1 = vartypes.pass_int_keep(exp1)[1]
        
        
        if exp1==0:
            #  0 leads to illegal fn call
            raise error.RunError(5)
            
        if skip_white_read_if(ins, ','):
            
            # NOT IMPLEMENTED
            # expression2 sets aside stack space for GW-BASIC. The default is the previous stack space size. 
            # When GW-BASIC is first executed, the stack space is set to 512 bytes, or one-eighth of the available memory, 
            # whichever is smaller.
            vartypes.pass_int_keep(expressions.parse_expression(ins))
       
    
    require(ins, end_statement)
    

def exec_data(ins):
    # ignore rest of statement after DATA
    #skip_to(ins, end_line + (':',))
    skip_to(ins, end_statement)


 

def exec_dim(ins):
    
    while True:
        
        skip_white(ins)
        name = var.getvarname(ins) 
        
        if name=='':
            raise error.RunError(2)
        
        dimensions = [ 10 ]   
        
        if skip_white(ins) in ('[', '('):
            ins.read(1)
            dimensions = expressions.parse_int_list(ins, 255, 9) # subscript out of range
            while len(dimensions)>0 and dimensions[-1]==None:
                dimensions = dimensions[:-1]
            if None in dimensions:
                raise error.RunError(2)
            c= peek(ins)
            if c not in (')', ']') :   
                # yes, we can write dim gh[5) 
                raise error.RunError(2)
            else:
                ins.read(1)
                    
        #d = skip_white(ins)
        
        var.dim_array(name, dimensions)            

        if skip_white(ins)!=',':
            break
        else:
            ins.read(1)    

    require(ins, end_statement)

def exec_deftype(typechar, ins):
    start = -1
    stop = -1
    while True:
        d = skip_white_read(ins).upper()
        if d < 'A' or d > 'Z':
            raise error.RunError(2)
        else:
            start = ord(d)-ord('A')
            stop = start
            
        d = skip_white_read(ins)
        if d == '\xEA':  # token for -
            d = skip_white_read(ins).upper()
        
            if d < 'A' or d > 'Z':
                raise error.RunError(2)
            else:
                stop = ord(d)-ord('A')
            d = skip_white_read(ins)
            
        if d==',' or d in end_statement:
            var.deftype[start:stop+1] = [typechar]*(stop-start+1)    
       
        if d in end_statement and d!= '':
            ins.seek(-1, 1)
            break         



    

def exec_erase(ins):
    
    while True:
        skip_white(ins)
        name = var.getvarname(ins)
        var.erase_array(name)
        
        d = skip_white(ins)
        if d in end_statement:
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
    
    require_read(ins, '\xe7')   # =
    
    val = expressions.parse_expression(ins)
    var.set_var_or_array(name, indices, val)

    require(ins, end_statement)
   
   
def exec_mid(ins):
    
    # MID$
    require_read(ins, '(')
    #name = var.getvarname(ins)
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:    
        # pre-dim even if this is not a legal statement!
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
        var.check_dim_array(name, indices)
    
    require_read(ins, ',')
    
    
    arglist = expressions.parse_int_list(ins, size=2, err=2)

    if arglist[0]==None:
        raise error.RunError(2)
        
    start = arglist[0]
    num = 0
    if arglist[1]!= None:
        num = arglist[1]
    
    require_read(ins, ')')
    
    if start <1 or start>255:
        raise error.RunError(5)
    if num <0 or num>255:
        raise error.RunError(5)
    
    require_read(ins, '\xE7') # =
    val = list( vartypes.pass_string_keep(expressions.parse_expression(ins))[1] )
    
    require(ins, end_statement)
         
    s = list(var.get_var_or_array(name, indices)[1])
    start -= 1    
    stop = start + num 
    if arglist[1] == None or stop > len(s):
        stop = len(s)
    
    if start==stop or start>len(s):
        return 
    
    if len(val) > stop-start:
        val = val[:stop-start]
    
    s[start:stop] = val
    var.set_var_or_array(name, indices, ('$', ''.join(s)))
    
    
   
   

def exec_lset(ins, justify_right=False):
    skip_white(ins)
    name = var.getvarname(ins)
    d = skip_white_read(ins)
    
    if d != '\xe7':   # =
        raise error.RunError(2)
        return False
    else:
        val = expressions.parse_expression(ins)
    
    var.lset(name, val, justify_right)


def exec_rset(ins):
    exec_lset(ins, justify_right=True)
    


def exec_option(ins):
    skip_white(ins)
    word = ins.read(4)
    if word.upper() == 'BASE':
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = skip_white(ins)
        if d == '0':
            var.base_array(0)
        elif d=='1':
            var.base_array(1)
        else:
            raise error.RunError(2)
    else:
        raise error.RunError(2)
        
    skip_to(ins, end_statement)
    




def parse_var_list(ins):
    readvar = []
    while True:
        skip_white(ins)
        name, indices = expressions.get_var_or_array_name(ins)
        readvar.append([name, indices])
        
        if skip_white(ins) != ',':
            break
        else:
            ins.read(1)

    return readvar



    


def exec_read(ins):
    readvar = parse_var_list(ins)
    
    # read the DATA            
    current = program.bytecode.tell()
    program.bytecode.seek(program.data_pos)
    
     
    for v in readvar:
        if peek(program.bytecode) in end_statement:
            # initialise - find first DATA
            program.data_line = skip_to(program.bytecode, '\x84')  # DATA
        
        c = program.bytecode.read(1)
        if c not in ('\x84', ','):
            # out of DATA
            raise error.RunError(4)
        
        vals = read_entry(program.bytecode)
                
        # syntax error in DATA line (not type mismatch!) if can't convert to var type
        if not var.setvar_read(*v, val=vals):#, err=2, erl=program.data_line) 
            raise error.RunError(2, program.data_line)
    
    program.data_pos = program.bytecode.tell()
    program.bytecode.seek(current)
    
    skip_white(ins)
    if peek(ins) not in end_statement:    
        raise error.RunError(2)

    
def read_entry(ins, end=end_line, ends=end_statement):
    vals = ''
    word = ''
    verbatim=False
            
    while True:
        # read entry
        c = peek(ins)
        if not verbatim:    
            c = skip_white(ins)
        
        if c=='"':
            ins.read(1)
            if not verbatim:
                verbatim=True
                c=peek(ins)
            else:
                verbatim = False
                c = skip_white(ins)
                if c not in ends+(',',):
                     raise error.RunError(2)
            
        if c == '':
            break
                             
        elif not verbatim and c==',':
            break
        elif c in end or (not verbatim and c in ends):
            ## skip to next entry or end-of-program
            #program.data_line = skip_to(program.bytecode, '\x84')  # DATA
            break
        else:        
            ins.read(1)
            if verbatim:
                vals += c
            else:
                word += c
        
        # omit trailing whitespace                        
        if c not in whitespace:    
            vals += word
            word = ''

    return vals


def exec_common(ins):    
    
    #readvar = parse_var_list(ins)
    skip_white(ins)
    varlist = []
    arraylist = []
    while True:
        skip_white(ins)
        name = var.getvarname(ins)
        # array?
        if skip_white(ins) in ('[', '('):
            ins.read(1)
            if skip_white(ins) not in (']', ')'):
                raise error.RunError(2)
            else:
                ins.read(1)
                arraylist.append(name)            
        else:
            varlist.append(name)
        
        if skip_white(ins) != ',':
            break
        else:
            ins.read(1)

    var.common_names += varlist
    var.common_array_names += arraylist

   

def parse_prompt(ins):
    # parse prompt
    prompt = ''
    following = ';'
    d = peek(ins)
    if d=='"':
        ins.read(1)        
        # only literal allowed, not a string expression
        d = ins.read(1)
        while d not in end_line + ('"',)  : 
            prompt += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1,1)  
        
        following = skip_white_read(ins)
        if following not in (';',','):
            raise error.RunError(2)
    return prompt, following
   
   
def exec_input(ins):
    d = skip_white(ins)
    
    finp = expressions.parse_file_number(ins)
    if finp!=None:
        # INPUT#
        # get list of variables
        readvar = parse_var_list(ins)
        for v in readvar:
            if v[0][-1] in vartypes.numeric:
                valstr = input_number(finp)
            else:    
                valstr = input_string(finp)
                
            var.setvar_read(*v, val=vals)
        if skip_white(ins) not in end_statement:
            raise error.RunError(2)
        return
    
            
    # ; to avoid echoing newline
    newline = True
    if d==';':
        newline=False
        ins.read(1)
        d = skip_white(ins)
    
    prompt, following = parse_prompt(ins)    
    if following ==';':
        prompt += '? '
            
    # get list of variables
    readvar = parse_var_list(ins)
        
    while True:
        glob.scrn.write(prompt) 
        
        # read the input
        line = glob.scrn.read_screenline(write_endl=newline)
        
        inputs = StringIO.StringIO(line) 
        text_file = fileio.pseudo_textfile(inputs)
        
        inputs.seek(0)
        success = True
        for v in readvar:
            if v[0] !='' and v[0][-1] in vartypes.numeric:
                # don't stop reading on blanks and line feeds
                valstr= input_number(text_file, hard_end = (',', '\x0d', ''), soft_end = () )
            else:    
                valstr= input_string(text_file, end_all = ('\x0d', ''), end_entry = (',',) )
            
            if v[0]=='':
                # error is only raised after the input in read!
                raise error.RunError(2)
                
            if not var.setvar_read(*v, val=valstr):
                success = False
                break
                
        if not success:
            glob.scrn.write('?Redo from start'+glob.endl)  # ... good old Redo!
            continue
        else:
            break
    
    #if newline:
    #    glob.scrn.write(glob.endl)
    
    if skip_white(ins) not in end_statement:
        raise error.RunError(2)
           

def text_skip(text_file, skip_range):
    d = text_file.peek_chars(1)
    while d in skip_range:
        text_file.read_chars(1) 
        d = text_file.peek_chars(1)
    return d

# hard end: means a null entry is read if they're repeated. soft ends can be repeated between entries.
def input_number(text_file, hard_end=(',', '\x0d', '\x1a', ''), soft_end = (' ', '\x0a') ):
    word = ''
    #soft_end = end_entry
    end_entry = soft_end + hard_end
    # skip *leading* spaces and line feeds and NUL. 
    # cf READ skips whitespace inside numbers as well
    c = text_skip(text_file, ascii_white)
    while True:
        # read entry
        c = text_file.read_chars(1)
        if c in end_entry:
            # TextFile filters 0d0a ->0d
            # repeated soft ends are ignored
            # TODO: I think \0a\0d is soft too
            text_skip(text_file, soft_end)
            break
        else:        
            word += c
    return word


# , is hard, LF is soft but will be caught as part of the whitespace skipping.
def input_string(text_file, end_all = ('\x0d', '\x1a', ''), end_entry = (',', '\x0a')):
    end_entry += end_all  
    max_len = 255
    
    word = ''
    quoted=False
    # skip *leading* spaces and line feeds and NUL. 
    # cf READ skips whitespace inside numbers as well
    c = text_skip(text_file, ascii_white)
    # check first char
    c = text_file.read_chars(1)
    if c=='"':
        quoted=True
        c = text_file.read_chars(1)
    while True:
        if c in end_all:
            break
        elif not quoted and c in end_entry:
            break    
        elif quoted and c=='"':
            # ignore blanks after the quotes
            c = text_skip(text_file, ascii_white)
            # but we need a comma if there's to be more input        
            c = text_file.read_chars(1)
            break
        else:        
            word += c
        if len(word) >= max_len:
            break        
        c = text_file.read_chars(1)
        
    return word



def exec_line_input(ins):
    d = skip_white(ins)
    
    finp = expressions.parse_file_number(ins)
    if finp!=None:
        # get string variable
        skip_white(ins)
        readvar, indices = expressions.get_var_or_array_name(ins)
        # read the input
        inputs = finp.read()
        var.set_var_or_array(readvar, indices, ('$', inputs))
        return
    
    # ; to avoid echoing newline
    newline = True
    if d==';':
        newline=False
        ins.read(1)
        d = skip_white(ins)
    
    prompt, following = parse_prompt(ins)    
            
    # get string variable
    readvar,indices = expressions.get_var_or_array_name(ins)

    # read the input
    glob.scrn.write(prompt) 
    
    inputs = glob.scrn.read_screenline(write_endl=newline)
    var.set_var_or_array(readvar, indices, ('$', inputs))
    
   

def exec_restore():
    program.data_line =-1
    program.data_pos = 0
    

    

def exec_swap(ins):
    skip_white(ins)
    name1 = var.getvarname(ins)
    
    d = skip_white(ins)
    if d!=',':
        raise error.RunError(2)
    else:
        ins.read(1)
        skip_white(ins)
        name2= var.getvarname(ins)
        var.swapvar(name1, name2)
        
    d = skip_white(ins)    
    if d not in end_statement:
        raise error.RunError(2)
                             
                             
def exec_def_fn(ins):
    skip_white(ins)
    fnname = var.getvarname(ins)
    
    # read variables
    fnvars=[]
    require_read(ins, '(')
    while True:
        skip_white(ins)
        fnvars.append(var.getvarname(ins))
        if skip_white(ins) in end_statement+(')',):
            break    
        require_read(ins,',')
    require_read(ins, ')')
    
    # read code
    fncode=''
    require_read(ins, '\xe7') #=
    while skip_white(ins) not in end_statement:
        fncode+=ins.read(1)        
    
    if not program.runmode():
        # GW doesn't allow DEF FN in direct mode, neither do we (for no good reason, works fine)
        raise error.RunError(12)
    
    var.functions[fnname] = [fnvars, fncode]
    
    
def value_fn(ins):
    skip_white(ins)
    fnname = var.getvarname(ins)
    
    if fnname not in var.functions:
        # undefined user function
        raise error.RunError(18)

    varnames, fncode = var.functions[fnname]
    
    # save existing vars
    varsave = {}
    for name in varnames:
        if name[0]=='$':
            # we're just not doing strings
            raise error.RunError(13)
        if name in var.variables:
            varsave[name] = var.variables[name]

    # read variables
    require_read(ins, '(')
    exprs = expressions.parse_expr_list(ins, len(varnames), err=2)
    if None in exprs:
        raise error.RunError(2)
    for i in range(len(varnames)):
        var.setvar(varnames[i], exprs[i])
    require_read(ins,')')
    
    fns = StringIO.StringIO(fncode)
    fns.seek(0)
    value= expressions.parse_expression(fns)    

    # restore existing vars
    
    for name in varnames:
        del var.variables[name]
    for name in varsave:    
        var.variables[name] = varsave[name]

    return value    

                             
                             
