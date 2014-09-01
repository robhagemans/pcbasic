#
# PC-BASIC 3.23 - expressions.py
#
# Expression parser 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from functools import partial

import fp
import vartypes
import representation
import rnd
import oslayer
import util
import error
import var
import iolayer
import graphics
import console
# for FRE() only
import program
import state
import machine
import sound
import backend
import timedate

# binary operator priority, lowest index is tightest bound 
# operators of the same priority are evaluated left to right      
priority = [
    ['\xED'], # ^  
    ['\xEB', '\xEC'], # *, /
    ['\xF4'], # \
    ['\xF3'], # MOD
    ['\xE9', '\xEA'], # +, -
    ['\xE6', '\xE7', '\xE8', '\xE6\xE7', '\xE8\xE7', '\xE8\xE6' ], # >, =, <, >=, <=, <>  
    ['\xEE'], # AND
    ['\xEF'], # OR
    ['\xF0'], # XOR
    ['\xF1'], # EQV
    ['\xF2'] # IMP
]

# flatten list
operator_tokens = [item for sublist in priority for item in sublist]
# command line option /d
# allow double precision math for ^, ATN, COS, EXP, LOG, SIN, SQR, and TAN
option_double = False
# enable pcjr/tandy syntax extensions
pcjr_syntax = False

def parse_expression(ins, allow_empty=False, empty_err=22):
    units, operators = [], []
    while True: 
        d = util.skip_white(ins)
        if d in util.end_expression:
            break    
        units.append(parse_expr_unit(ins))
        d = util.skip_white(ins)
        # string lit breaks expression, number after string lit breaks expression, + or - doesnt (could be an operator...
        if d not in operator_tokens:
            break
        else:
            ins.read(1)
        if d in ('\xE6', '\xE7', '\xE8'):
            nxt = util.skip_white(ins)
            if nxt in ('\xE6', '\xE7', '\xE8'):
                ins.read(1)
                if d == nxt:
                    raise error.RunError(2)
                else:    
                    d += nxt
                    if d[0] == '\xe7': #= 
                        # =>, =<
                        d = d[1]+d[0]
                    elif d == '\xe6\xe8': # ><
                        d = '\xe8\xe6'    
        operators.append(d)
    # empty expression is a syntax error (inside brackets) or Missing Operand (in an assignment) or ok (in print)
    # PRINT 1+      :err 22
    # Print (1+)    :err 2
    # print 1+)     :err 2
    if len(units) == 0:
        if allow_empty:
            return None
        else:    
            if d in (')', ']'):
                ins.read(1) # for positioning of cursor in edit gadget
            # always 22 here now that the bracket is taken out?
            raise error.RunError(2 if d in (')', ']') else empty_err)
    if len(units) <= len(operators):
        if d in (')', ']'):
            ins.read(1)
        raise error.RunError(2 if d in (')', ']') else 22)
    return parse_operators(operators, units)

def parse_operators(operators, units):
    for current_priority in priority:
        pos = 0
        while pos < len(operators):
            if operators[pos] in current_priority:
                units[pos] = value_operator(operators[pos], units[pos], units[pos+1])
                del units[pos+1]
                del operators[pos]
            else:
                pos += 1
        if len(operators) == 0:
            break
    if len(operators) > 0:
        # unrecognised operator, syntax error
        raise error.RunError(2)
    return units[0]    
    
def parse_expr_unit(ins):
    d = util.skip_white(ins)
    # string literal
    if d == '"':
        ins.read(1)
        output = bytearray()
        # while tokenised nmbers inside a string literal will be printed as tokenised numbers, they don't actually execute as such:
        # a \00 character, even if inside a tokenised number, will break a string literal (and make the parser expect a 
        # line number afterwards, etc. We follow this.
        d = ins.read(1)
        while d not in util.end_line + ('"',)  : # ['"', '\x00', '']:
            output += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1, 1)
        return vartypes.pack_string(output)
    # variable name
    elif d >= 'A' and d <= 'Z':
        name, indices = get_var_or_array_name(ins)
        return var.get_var_or_array(name, indices)
    # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
    # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
    elif d >= '0' and d <= '9':
        outs = StringIO()
        representation.tokenise_number(ins, outs)
        outs.seek(0)
        return util.parse_value(outs)
    # number literals
    elif d in ('\x0b','\x0c','\x0f', '\x11','\x12','\x13','\x14','\x15','\x16',
                '\x17','\x18','\x19','\x1a','\x1b', '\x1c','\x1d', '\x1f'):
        return util.parse_value(ins)   
    # gw-basic allows adding line numbers to numbers     
    elif d == '\x0e':
        return vartypes.pack_int(util.parse_jumpnum(ins))
    # brackets
    elif d == '(':
        return parse_bracket(ins)
    # single-byte tokens 
    else:
        ins.read(1)       
        if d == '\x85':         return value_input(ins)
        elif d == '\xC8':       return value_screen(ins)
        elif d == '\xD0':       return value_usr(ins)
        elif d == '\xD1':       return value_fn(ins)
        elif d == '\xD3':       return value_not(ins)
        elif d == '\xD4':       return value_erl(ins)
        elif d == '\xD5':       return value_err(ins)
        elif d == '\xD6':       return value_string(ins)
        elif d == '\xD8':       return value_instr(ins)    
        elif d == '\xDA':       return value_varptr(ins)
        elif d == '\xDB':       return value_csrlin(ins)
        elif d == '\xDC':       return value_point(ins)
        elif d == '\xDE':       return value_inkey(ins)
        elif d == '\xE9':       return parse_expr_unit(ins)
        elif d == '\xEA':       return value_neg(ins)     
        # two-byte tokens
        elif d == '\xFD':
            d = ins.read(1)
            if d == '\x81':      return value_cvi(ins)
            elif d =='\x82':     return value_cvs(ins)
            elif d =='\x83':     return value_cvd(ins)
            elif d =='\x84':     return value_mki(ins)
            elif d =='\x85':     return value_mks(ins)
            elif d =='\x86':     return value_mkd(ins)
            elif d == '\x8b':    return value_exterr(ins)
        # two-byte tokens
        elif d == '\xFE':
            d = ins.read(1)        
            if d == '\x8D':      return value_date(ins)
            elif d == '\x8E':    return value_time(ins)
            elif d == '\x93':    return value_play(ins)
            elif d == '\x94':    return value_timer(ins)
            elif d == '\x95':    return value_erdev(ins)
            elif d == '\x96':    return value_ioctl(ins)
            elif d == '\x9B':    return value_environ(ins)
            elif d == '\x9E':    return value_pmap(ins)
        # two-byte tokens                    
        elif d == '\xFF':
            d = ins.read(1)
            if d == '\x81':     return value_left(ins)
            elif d == '\x82':   return value_right(ins)
            elif d == '\x83':   return value_mid(ins)
            elif d == '\x84':   return value_sgn(ins)
            elif d == '\x85':   return value_int(ins)
            elif d == '\x86':   return value_abs(ins)
            elif d == '\x87':   return value_sqrt(ins)
            elif d == '\x88':   return value_rnd(ins)
            elif d == '\x89':   return value_sin(ins)
            elif d == '\x8a':   return value_log(ins)
            elif d == '\x8b':   return value_exp(ins)
            elif d == '\x8c':   return value_cos(ins)
            elif d == '\x8D':   return value_tan(ins)
            elif d == '\x8E':   return value_atn(ins)
            elif d == '\x8F':   return value_fre(ins)
            elif d == '\x90':   return value_inp(ins)
            elif d == '\x91':   return value_pos(ins)
            elif d == '\x92':   return value_len(ins)
            elif d == '\x93':   return value_str(ins)
            elif d == '\x94':   return value_val(ins)
            elif d == '\x95':   return value_asc(ins)
            elif d == '\x96':   return value_chr(ins)
            elif d == '\x97':   return value_peek(ins)
            elif d == '\x98':   return value_space(ins)
            elif d == '\x99':   return value_oct(ins)
            elif d == '\x9A':   return value_hex(ins)
            elif d == '\x9B':   return value_lpos(ins)
            elif d == '\x9C':   return value_cint(ins)
            elif d == '\x9D':   return value_csng(ins)
            elif d == '\x9E':   return value_cdbl(ins)
            elif d == '\x9F':   return value_fix(ins)    
            elif d == '\xA0':   return value_pen(ins)
            elif d == '\xA1':   return value_stick(ins)
            elif d == '\xA2':   return value_strig(ins)
            elif d == '\xA3':   return value_eof(ins)
            elif d == '\xA4':   return value_loc(ins)
            elif d == '\xA5':   return value_lof(ins)
        else:
            return None

######################################################################
# expression parsing utility functions 

def parse_bracket(ins):
    util.require_read(ins, ('(',))
    # we need a Syntax error, not a Missing operand
    val = parse_expression(ins, empty_err=2)
    util.require_read(ins, (')',))
    return val

def parse_int_list(ins, size, err=5, allow_last_empty=False):
    exprlist = parse_expr_list(ins, size, err, allow_last_empty=allow_last_empty)
    return [(vartypes.pass_int_unpack(expr) if expr else None) for expr in exprlist]

def parse_expr_list(ins, size, err=5, separators=(',',), allow_last_empty=False):
    output = []
    while True:
        output.append(parse_expression(ins, allow_empty=True))
        if not util.skip_white_read_if(ins, separators):
            break
    if len(output) > size:            
        raise error.RunError(err)
    # can't end on a comma: Missing Operand  
    if not allow_last_empty and output and output[-1] == None:
        raise error.RunError(22)
    while len(output) < size:
        output.append(None)
    return output

def parse_file_number(ins, file_mode='IOAR'):
    screen = None
    if util.skip_white_read_if(ins, ('#',)):
        number = vartypes.pass_int_unpack(parse_expression(ins))
        util.range_check(0, 255, number)
        screen = iolayer.get_file(number, file_mode)
        util.require_read(ins, (',',))
    return screen        

def parse_file_number_opthash(ins):
    util.skip_white_read_if(ins, ('#',))
    number = vartypes.pass_int_unpack(parse_expression(ins))
    util.range_check(0, 255, number)
    return number    

def get_var_or_array_name(ins):
    name = util.get_var_name(ins)
    indices = []
    if util.skip_white_read_if(ins, ('[', '(')):
        # it's an array, read indices
        indices = parse_int_list(ins, 255, 9) # subscript out of range
        while len(indices) > 0 and indices[-1] == None:
            indices = indices[:-1]
        if None in indices:
            raise error.RunError(2)
        util.require_read(ins, (']', ')'))
    return name, indices

######################################################################
# conversion

def value_cvi(ins):            
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 2:
        raise error.RunError(5)
    return vartypes.pack_int(vartypes.sint_to_value(cstr[:2]))

def value_cvs(ins):            
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 4:
        raise error.RunError(5)
    return ('!', cstr[:4]) 

def value_cvd(ins):            
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 8:
        raise error.RunError(5)
    return ('#', cstr[:8])

def value_mki(ins):            
    return vartypes.pack_string(vartypes.value_to_sint(vartypes.pass_int_unpack(parse_bracket(ins))))

def value_mks(ins):            
    return vartypes.pack_string(vartypes.pass_single_keep(parse_bracket(ins))[1])

def value_mkd(ins):       
    return vartypes.pack_string(vartypes.pass_double_keep(parse_bracket(ins))[1])

def value_cint(ins):            
    return vartypes.pass_int_keep(parse_bracket(ins))

def value_csng(ins):            
    return vartypes.pass_single_keep(parse_bracket(ins))

def value_cdbl(ins):            
    return vartypes.pass_double_keep(parse_bracket(ins))

def value_str(ins):            
    s = vartypes.pass_number_keep(parse_bracket(ins))
    return representation.value_to_str_keep(s, screen=True)
        
def value_val(ins):  
    val = representation.str_to_value_keep(parse_bracket(ins))
    return val if val else vartypes.null['%']

def value_chr(ins):            
    val = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 255, val)
    return vartypes.pack_string(bytearray(chr(val)))

def value_oct(ins):            
    # allow range -32768 to 65535
    val = vartypes.pass_int_unpack(parse_bracket(ins), 0xffff)
    return vartypes.pack_string(representation.oct_to_str(vartypes.value_to_sint(val))[2:])

def value_hex(ins):            
    # allow range -32768 to 65535
    val = vartypes.pass_int_unpack(parse_bracket(ins), 0xffff)
    return vartypes.pack_string(representation.hex_to_str(vartypes.value_to_sint(val))[2:])

######################################################################
# string maniulation            
    
def value_len(ins):            
    return vartypes.pack_int(len(vartypes.pass_string_unpack(parse_bracket(ins))) )

def value_asc(ins):            
    s = vartypes.pass_string_unpack(parse_bracket(ins))
    if not s:
        raise error.RunError(5)
    return vartypes.pack_int(s[0])
    
def value_instr(ins):
    util.require_read(ins, ('(',))
    big, small, n = '', '', 1
    s = parse_expression(ins, empty_err=2)
    if s[0] != '$':
        n = vartypes.pass_int_unpack(s)
        util.range_check(1, 255, n)
        util.require_read(ins, (',',))
        big = vartypes.pass_string_unpack(parse_expression(ins, allow_empty=True))
    else:
        big = vartypes.pass_string_unpack(s)
    util.require_read(ins, (',',))
    small = vartypes.pass_string_unpack(parse_expression(ins, allow_empty=True))
    util.require_read(ins, (')',))
    return vartypes.str_instr(big, small, n)

def value_mid(ins):
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    start = vartypes.pass_int_unpack(parse_expression(ins))
    if util.skip_white_read_if(ins, (',',)):
        num = vartypes.pass_int_unpack(parse_expression(ins))
    else:
        num = len(s)
    util.require_read(ins, (')',))
    util.range_check(1, 255, start)
    util.range_check(0, 255, num)
    if num == 0 or start > len(s):
        return vartypes.null['$']
    start -= 1    
    stop = start + num 
    stop = min(stop, len(s))
    return vartypes.pack_string(s[start:stop])  
    
def value_left(ins):
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    stop = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 255, stop)
    if stop == 0:
        return vartypes.null['$']
    stop = min(stop, len(s))
    return vartypes.pack_string(s[:stop])  
    
def value_right(ins):
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    stop = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 255, stop)
    if stop == 0:
        return vartypes.null['$']
    stop = min(stop, len(s))
    return vartypes.pack_string(s[-stop:])  

def value_string(ins): # STRING$
    util.require_read(ins, ('(',))
    n, j = parse_expr_list(ins, 2)    
    n = vartypes.pass_int_unpack(n)
    util.range_check(0, 255, n)
    if j[0] == '$':
        j = vartypes.unpack_string(j)
        util.range_check(1, 255, len(j))
        j = j[0]
    else:
        j = vartypes.pass_int_unpack(j)        
        util.range_check(0, 255, j)
    util.require_read(ins, (')',))
    return vartypes.pack_string(bytearray(chr(j)*n))

def value_space(ins):            
    num = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 255, num)
    return vartypes.pack_string(bytearray(' '*num))
    
######################################################################
# console functions

def value_screen(ins):
    util.require_read(ins, ('(',))
    row, col, z = parse_int_list(ins, 3, 5) 
    if row == None or col == None:
        raise error.RunError(5)
    if z == None:
        z = 0    
    util.range_check(1, state.console_state.height, row)
    if state.console_state.view_set:
        util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
    util.range_check(1, state.console_state.width, col)
    util.range_check(0, 255, z)
    util.require_read(ins, (')',))
    if z and state.console_state.screen_mode:
        return vartypes.null['%']    
    else:
        return vartypes.pack_int(console.get_screen_char_attr(row, col, z!=0))
    
def value_input(ins):    # INPUT$
    util.require_read(ins, ('$',))
    util.require_read(ins, ('(',))
    num = vartypes.pass_int_unpack(parse_expression(ins))
    util.range_check(1, 255, num)
    screen = state.io_state.devices['KYBD:']   
    if util.skip_white_read_if(ins, (',',)):
        screen = iolayer.get_file(parse_file_number_opthash(ins))
    util.require_read(ins, (')',))
    word = bytearray()
    for char in screen.read_chars(num):
        if len(char) > 1 and char[0] == '\x00':
            # replace some scancodes than console can return
            if char[1] in ('\x4b', '\x4d', '\x48', '\x50', '\x47', '\x49', '\x4f', '\x51', '\x53'):
                word += '\x00'
            # ignore all others    
        else:
            word += char                        
    return vartypes.pack_string(bytearray(word))
    
def value_inkey(ins):
    return vartypes.pack_string(bytearray(console.get_char()))

def value_csrlin(ins):
    row, col = state.console_state.row, state.console_state.col 
    if col == state.console_state.width and state.console_state.overflow and row < state.console_state.scroll_height:
        # in overflow position, return row+1 except on the last row
        row += 1
    return vartypes.pack_int(row)

def value_pos(ins):            
    # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
    parse_bracket(ins)
    col = state.console_state.col
    if col == state.console_state.width and state.console_state.overflow:
        # in overflow position, return column 1.
        col = 1
    return vartypes.pack_int(col)

def value_lpos(ins):            
    num = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, num)
    printer = state.io_state.devices['LPT' + max(1, num) + ':']
    return vartypes.pack_int(printer.col)
           
######################################################################
# file access

def value_loc(ins): # LOC
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    util.range_check(0, 255, num)
    the_file = iolayer.get_file(num)
    return vartypes.pack_int(the_file.loc())

def value_eof(ins): # EOF
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    if num == 0:
        return vartypes.null['%']
    util.range_check(0, 255, num)
    the_file = iolayer.get_file(num, 'IR')
    return vartypes.bool_to_int_keep(the_file.eof())
  
def value_lof(ins): # LOF
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    util.range_check(0, 255, num)
    the_file = iolayer.get_file(num)
    return vartypes.pack_int(the_file.lof() )
    

######################################################################
# env, time and date functions
       
def value_environ(ins):
    util.require_read(ins, ('$',))
    expr = parse_bracket(ins)
    if expr[0] == '$':
        return vartypes.pack_string(oslayer.get_env(vartypes.unpack_string(expr)))
    else:
        expr = vartypes.pass_int_unpack(expr)
        util.range_check(1, 255, expr)
        return vartypes.pack_string(oslayer.get_env_entry(expr))

def value_timer(ins):
    # precision of GWBASIC TIMER is about 1/20 of a second
    return fp.pack(fp.div( fp.Single.from_int(timedate.timer_milliseconds()/50), fp.Single.from_int(20)))
    
def value_time(ins):
    return vartypes.pack_string(timedate.get_time())
    
def value_date(ins):
    return vartypes.pack_string(timedate.get_date())

#######################################################
# user-defined functions

def value_fn(ins):
    fnname = util.get_var_name(ins)
    try:
        varnames, fncode = state.basic_state.functions[fnname]
    except KeyError:
        # undefined user function
        raise error.RunError(18)
    # save existing vars
    varsave = {}
    for name in varnames:
        if name in state.basic_state.variables:
            # copy the *value* - set_var is in-place it's safe for FOR loops
            varsave[name] = state.basic_state.variables[name][:]
    # read variables
    if util.skip_white_read_if(ins, ('(',)):
        exprs = parse_expr_list(ins, len(varnames), err=2)
        if None in exprs:
            raise error.RunError(2)
        for i in range(len(varnames)):
            var.set_var(varnames[i], exprs[i])
        util.require_read(ins, (')',))
    # execute the code
    fns = StringIO(fncode)
    fns.seek(0)
    value = parse_expression(fns)    
    # restore existing vars
    for name in varsave:    
        # re-assign the stored value
        state.basic_state.variables[name][:] = varsave[name]
    return value    

###############################################################
# graphics    
    
def value_point(ins):
    util.require_read(ins, ('(',))
    lst = parse_expr_list(ins, 2, err=2)
    util.require_read(ins, (')',))
    if not lst[0]:
        raise error.RunError(2)
    if not lst[1]:
        # single-argument version
        x, y = state.console_state.last_point
        fn = vartypes.pass_int_unpack(lst[0])
        if fn == 0:
            return vartypes.pack_int(x)
        elif fn == 1:
            return vartypes.pack_int(y)
        elif fn == 2:
            fx, _ = graphics.get_window_coords(x, y)
            return fp.pack(fx)
        elif fn == 3:
            _, fy = graphics.get_window_coords(x, y)
            return fp.pack(fy)
    else:       
        # two-argument mode
        graphics.require_graphics_mode()
        return vartypes.pack_int(graphics.get_point(*graphics.window_coords(
                        fp.unpack(vartypes.pass_single_keep(lst[0])), 
                        fp.unpack(vartypes.pass_single_keep(lst[1])))))     

def value_pmap(ins):
    util.require_read(ins, ('(',))
    coord = parse_expression(ins)
    util.require_read(ins, (',',))
    mode = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 3, mode)
    if not state.console_state.screen_mode:
        return vartypes.null['%']
    if mode == 0:
        value, _ = graphics.window_coords(fp.unpack(vartypes.pass_single_keep(coord)), fp.Single.zero)       
        return vartypes.pack_int(value)        
    elif mode == 1:
        _, value = graphics.window_coords(fp.Single.zero, fp.unpack(vartypes.pass_single_keep(coord)))       
        return vartypes.pack_int(value)        
    elif mode == 2:
        value, _ = graphics.get_window_coords(vartypes.pass_int_unpack(coord), 0)       
        return fp.pack(value)
    elif mode == 3:
        _, value = graphics.get_window_coords(0, vartypes.pass_int_unpack(coord))       
        return fp.pack(value)
    
#####################################################################
# sound functions
    
def value_play(ins):
    voice = vartypes.pass_int_unpack(parse_bracket(ins))    
    util.range_check(0, 255, voice)
    if not(pcjr_syntax and voice in (1, 2)):
        voice = 0    
    return vartypes.pack_int(sound.music_queue_length(voice))
    
#####################################################################
# error functions

def value_erl(ins):
    return fp.pack(fp.Single.from_int(program.get_line_number(state.basic_state.errp)))

def value_err(ins):
    return vartypes.pack_int(state.basic_state.errn)
    
#####################################################################
# pen, stick and strig

def value_pen(ins):
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 9, fn)
    pen = backend.penstick.get_pen(fn)
    if pen == None or not state.basic_state.pen_handler.enabled:
        # should return 0 or char pos 1 if PEN not ON    
        pen = 1 if fn >= 6 else 0 
    return vartypes.pack_int(pen)
    
def value_stick(ins):
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, fn)
    return vartypes.pack_int(backend.penstick.get_stick(fn))
    
def value_strig(ins):
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
    util.range_check(0, 7, fn)
    return vartypes.bool_to_int_keep(backend.penstick.get_strig(fn))
    
#########################################################
# memory and machine

def value_fre(ins):
    val = parse_bracket(ins)
    if val[0] == '$':
        # grabge collection if a string-valued argument is specified.
        var.collect_garbage()
    return fp.pack(fp.Single.from_int(var.fre()))

# read memory location 
# currently, var memory, text&graphics memory and preset values only    
def value_peek(ins):
    addr = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    return vartypes.pack_int(machine.peek(addr))
    
# VARPTR, VARPTR$    
def value_varptr(ins):   
    dollar = util.skip_white_read_if(ins, ('$',)) 
    util.require_read(ins, ('(',))
    name, indices = get_var_or_array_name(ins)
    util.require_read(ins, (')',))
    var_ptr = machine.varptr(name, indices)
    if var_ptr < 0:
        raise error.RunError(5) # ill fn cll
    if dollar:
        return vartypes.pack_string(bytearray(chr(var.byte_size[name[-1]])) + vartypes.value_to_uint(var_ptr))
    else:
        # TODO: strings, fields, file control blocks not yet implemented 
        return vartypes.pack_int(var_ptr)
        
def value_usr(ins):
    if util.peek(ins) in ('\x11','\x12','\x13','\x14','\x15','\x16','\x17','\x18','\x19','\x1a'): # digits 0--9
        ins.read(1)
    parse_bracket(ins)
    raise error.RunError(5)
    
def value_inp(ins):
    port = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    return vartypes.pack_int(machine.inp(port))

#  erdev, erdev$        
def value_erdev(ins):
    if util.skip_white_read_if(ins, ('$',)):
        return vartypes.null['$']
    else:    
        return vartypes.null['%']
        
# exterr        
def value_exterr(ins):
    x = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, x)
    return vartypes.null['%']
    
# ioctl$    
def value_ioctl(ins):
    util.require_read(ins, ('$',))
    util.require_read(ins, ('(',))
    num = parse_file_number_opthash(ins)
    util.require_read(ins, (')',))
    iolayer.get_file(num)
    raise error.RunError(5)   
    
###########################################################
# option_double regulated single & double precision math

def value_unary(ins, fn):
    return fp.pack(fn(fp.unpack(vartypes.pass_float_keep(parse_bracket(ins), option_double))))

value_sqrt = partial(value_unary, fn=fp.sqrt)
value_exp = partial(value_unary, fn=fp.exp)
value_sin = partial(value_unary, fn=fp.sin)
value_cos = partial(value_unary, fn=fp.cos)
value_tan = partial(value_unary, fn=fp.tan)
value_atn = partial(value_unary, fn=fp.atn)
value_log = partial(value_unary, fn=fp.log)
 
# others

def value_rnd(ins):
    if util.skip_white(ins) == '(':
        return rnd.get_random(fp.unpack(vartypes.pass_single_keep(parse_bracket(ins))))
    else:
        return rnd.get_random_int(1)

def value_abs(ins):
    return vartypes.number_abs(vartypes.pass_number_keep(parse_bracket(ins)))

def value_int(ins):
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    return inp if inp[0] == '%' else fp.pack(fp.unpack(inp).ifloor()) 

def value_sgn(ins):
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    if inp[0] == '%':
        inp_int = vartypes.unpack_int(inp) 
        return vartypes.pack_int(0 if inp_int==0 else (1 if inp_int > 0 else -1))
    else:
        return vartypes.pack_int(fp.unpack(inp).sign() )

def value_fix(ins):
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    if inp[0] == '%':
        return inp
    elif inp[0] == '!':
        # needs to be a float to avoid overflow
        return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int())) 
    elif inp[0] == '#':
        return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int())) 

def value_neg(ins):
    return vartypes.number_neg(vartypes.pass_number_keep(parse_expr_unit(ins)))

def value_not(ins):
    # two's complement not, -x-1
    return vartypes.pack_int(~vartypes.pass_int_unpack(parse_expr_unit(ins)))
    
# binary operators
        
def value_operator(op, left, right):
    if op == '\xED':                # ^
        return vcaret(left, right)
    elif op == '\xEB':              # *
        return vtimes(left, right)
    elif op == '\xEC':              # /
        return vdiv(left, right)
    elif op == '\xF4':              # \
        return fp.pack(fp.div(fp.unpack(vartypes.pass_single_keep(left)).ifloor(), 
                fp.unpack(vartypes.pass_single_keep(right)).ifloor()).apply_carry().ifloor())
    elif op == '\xF3':              # %
        numerator = vartypes.pass_int_unpack(right)
        if numerator == 0:
            # simulate division by zero
            return fp.pack(fp.div(fp.unpack(vartypes.pass_single_keep(left)).ifloor(), 
                    fp.unpack(vartypes.pass_single_keep(right)).ifloor()).ifloor())
        return vartypes.pack_int(vartypes.pass_int_unpack(left) % numerator)    
    elif op == '\xE9':              # +
        return vplus(left, right)
    elif op == '\xEA':              # -
        return vartypes.number_add(left, vartypes.number_neg(right))
    elif op ==  '\xE6':             # >
        return vartypes.bool_to_int_keep(vartypes.gt(left,right)) 
    elif op ==  '\xE7':             # =
        return vartypes.bool_to_int_keep(vartypes.equals(left, right))
    elif op ==  '\xE8':             # <  
        return vartypes.bool_to_int_keep(not(vartypes.gt(left,right) or vartypes.equals(left, right)))
    elif op ==  '\xE6\xE7':         # >=
        return vartypes.bool_to_int_keep(vartypes.gt(left,right) or vartypes.equals(left, right))
    elif op ==  '\xE8\xE7':         # <=
        return vartypes.bool_to_int_keep(not vartypes.gt(left,right))
    elif op ==  '\xE8\xE6':         # <>
        return vartypes.bool_to_int_keep(not vartypes.equals(left, right))
    elif op ==  '\xEE':             # AND
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) & vartypes.pass_twoscomp(right) )
    elif op ==  '\xEF':             # OR
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) | vartypes.pass_twoscomp(right) )
    elif op ==  '\xF0':             # XOR
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) ^ vartypes.pass_twoscomp(right) )
    elif op == '\xF1':              # EQV
        return vartypes.twoscomp_to_int( ~(vartypes.pass_twoscomp(left) ^ vartypes.pass_twoscomp(right)) )
    elif op ==  '\xF2':             # IMP
        return vartypes.twoscomp_to_int( (~vartypes.pass_twoscomp(left)) | vartypes.pass_twoscomp(right) )
    else:
        raise error.RunError(2)

def vcaret(left, right):
    if (left[0] == '#' or right[0] == '#') and option_double:
        return fp.pack( fp.power(fp.unpack(vartypes.pass_double_keep(left)), fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        if right[0] == '%':
            return fp.pack( fp.unpack(vartypes.pass_single_keep(left)).ipow_int(vartypes.unpack_int(right)) )
        else:
            return fp.pack( fp.power(fp.unpack(vartypes.pass_single_keep(left)), fp.unpack(vartypes.pass_single_keep(right))) )

def vtimes(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.unpack(vartypes.pass_double_keep(left)).imul(fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        return fp.pack( fp.unpack(vartypes.pass_single_keep(left)).imul(fp.unpack(vartypes.pass_single_keep(right))) )

def vdiv(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(vartypes.pass_double_keep(left)), fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(vartypes.pass_single_keep(left)), fp.unpack(vartypes.pass_single_keep(right))) )

def vplus(left, right):
    if left[0] == '$':
        return vartypes.pack_string(vartypes.pass_string_unpack(left) + vartypes.pass_string_unpack(right))
    else:
        return vartypes.number_add(left, right)

