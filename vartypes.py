#
# PC-BASIC 3.23 - vartypes.py
#
# Type conversions and generic functions
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import fp
#import string_ptr
import error

# default type for variable name starting with a-z
deftype = ['!']*26
# zeroed out
null = { '$': ('$', ''), '%': ('%', bytearray('\x00')*2), '!': ('!', bytearray('\x00')*4), '#': ('#', bytearray('\x00')*8) }

def complete_name(name):
    if name and name[-1] not in ('$', '%', '!', '#'):
        name += deftype[ord(name[0].upper()) - 65] # ord('A') 
    return name

def pass_int_keep(inp, maxint=0x7fff, err=13):
    if not inp:
        raise error.RunError(2)    
    typechar = inp[0]
    if typechar == '%':
        return inp
    elif typechar in ('!', '#'):
        val = fp.unpack(inp).round_to_int()
        if val > maxint or val < -0x8000:
            # overflow
            raise error.RunError(6)
        return pack_int(val)
    else:     
        # type mismatch
        raise error.RunError(err)
    
def pass_int_unpack(inp, maxint=0x7fff, err=13):
    return unpack_int(pass_int_keep(inp, maxint, err))

def unpack_int(inp):
    return sint_to_value(inp[1])

def pack_int(inp):
    return ('%', value_to_sint(inp))
       
######################################

def pass_single_keep(num):
    if not num:
        raise error.RunError(2)
    typechar = num[0]
    if typechar == '!':
        return num
    elif typechar == '%':
        return fp.pack(fp.Single.from_int(unpack_int(num)))
    elif typechar == '#':
        val = num[1][4:]
        # TODO: *round* to single
        #if (num[1][3] & 0x80) == 1: 
        return ('!', val)        
    elif typechar == '$':
        raise error.RunError(13)
    
def pass_double_keep(num):
    if not num:
        raise error.RunError(2)
    typechar = num[0]
    if typechar == '#':
        return num
    elif typechar == '%':
        return fp.pack(fp.Double.from_int(unpack_int(num)))
    elif typechar == '!':
        return ('#', bytearray('\x00\x00\x00\x00')+num[1])    
    elif typechar == '$':
        raise error.RunError(13)

def pass_float_keep(num, allow_double=True):
    if num and num[0] == '#' and allow_double:
        return num
    else:
        return pass_single_keep(num)

def pass_string_keep(inp, allow_empty=False, err=13):
    if not inp:
        if not allow_empty:
            raise error.RunError(2)    
        else:
            return ('$', '')
    if inp[0] == '$':
        return inp
    else:     
        raise error.RunError(err)

def pass_string_unpack(inp, allow_empty=False, err=13):
    return pass_string_keep(inp, allow_empty, err)[1]

def pass_type_keep(typechar, value):     
    if typechar == '$':
        return pass_string_keep(value)
    elif typechar == '%':
        return pass_int_keep(value)
    elif typechar == '!':
        return pass_single_keep(value)
    elif typechar == '#':
        return pass_double_keep(value)
    else:
        raise error.RunError(2)
 
def pass_most_precise_keep(left, right, err=13):
    left_type, right_type = left[0][-1], right[0][-1]
    if left_type=='#' or right_type=='#':
        return (pass_double_keep(left), pass_double_keep(right))
    elif left_type=='!' or right_type=='!':
        return (pass_single_keep(left), pass_single_keep(right))
    elif left_type=='%' or right_type=='%':
        return (pass_int_keep(left), pass_int_keep(right))
    else:
        raise error.RunError(err)

# string output
# screen=False means in a program listing
# screen=True is used for screen, str$ and sequential files
def value_to_str_keep(inp, screen=False, write=False, allow_empty_expression=False):
    if not inp:
        if allow_empty_expression:
            return ('$', '')
        else:
            raise error.RunError(2)    
    typechar = inp[0]
    if typechar == '$':
        return ('$', inp[1])
    elif typechar == '%':
        if screen and not write and unpack_int(inp) >= 0:
            return ('$', ' '+ int_to_str(unpack_int(inp)) )
        else:
            return ('$', int_to_str(unpack_int(inp)))
    elif typechar == '!':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    elif typechar == '#':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    else:
        raise error.RunError(2)    
    
##################################################
# unpack tokenised numeric constants

def uint_to_value(s):
    # unsigned int. 
    return 0x100 * s[1] + s[0]

def sint_to_value(s):
    # 2's complement signed int, least significant byte first, sign bit is most significant bit
    value = 0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value 
    else: 
        return value
    
# python ints to tokenised ints

def value_to_uint(n):
    if n > 0xffff:
        # overflow
        raise error.RunError(6)        
    return bytearray((n&0xff, n >> 8)) 

def value_to_sint(n):
    if n > 0xffff:  # 0x7fff ?
        # overflow
        raise error.RunError(6)     
    if n < 0:
        n = 0x10000 + n        
    return bytearray((n&0xff, n >> 8)) 

##################################################

def unpack_string(inp):
    return inp[1]
            
def pack_string(inp):
    return ('$', inp)

# python int to python str

def int_to_str(num):
    return str(num)   

# tokenised ints to python str

def uint_to_str(s):
    return str(uint_to_value(s))

def sint_to_str(s):
    return str(sint_to_value(s))

def ubyte_to_str(s):
    return str(s[0])
    
def hex_to_str(s):
    return "&H" + hex(uint_to_value(s))[2:].upper()

def oct_to_str(s):
    return "&O" + oct(uint_to_value(s))[1:]
    
# boolean functions - two's complement int

def bool_to_int_keep(boo):
    return pack_int(-boo)
    
def int_to_bool(iboo):
    return not (unpack_int(iboo) == 0)

def pass_twoscomp(num):
    val = pass_int_unpack(num)
    if val < 0:
        return 0x10000 + val
    else:
        return val

def twoscomp_to_int(num):
    if num > 0x7fff:
        num -= 0x10000 
    return pack_int(num)    

##################################################

def str_gt(left,right):
    shortest = min(len(left), len(right))
    for i in range(shortest):
        if left[i] > right[i]:
            return True
        elif left[i] < right[i]:
            return False
    # the same so far...
    # the shorter string is said to be less than the longer, 
    # provided they are the same up till the length of the shorter.
    if len(left) > len(right):
        return True
    # left is shorter, or equal strings
    return False                    


def number_gt(left, right):
    left, right = pass_most_precise_keep(left, right)
    if left[0] in ('#', '!'):
        gt = fp.unpack(left).gt(fp.unpack(right)) 
    else:
        gt = unpack_int(left) > unpack_int(right)           
    return bool_to_int_keep(gt) 
    
    
def number_add(left, right):
    left, right = pass_most_precise_keep(left, right)
    if left[0] in ('#', '!'):
        return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
    else:
        return pack_int(unpack_int(left) + unpack_int(right))           

def number_sgn(inp):
    if inp[0] == '%':
        i = unpack_int(inp)
        if i > 0:
            return pack_int(1)
        elif i < 0:
            return pack_int(-1)
        else:
            return pack_int(0)
    elif inp[0] in ('!', '#'):
        return pack_int(fp.unpack(inp).sign())
    return inp

def number_abs(inp):
    if inp[0] == '%':
        val = abs(unpack_int(inp))
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return pack_int(val)
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:])  
        out[1][-2] &= 0x7F 
        return out  
    return inp

def number_neg(inp):
    if inp[0] == '%':
        val = -unpack_int(inp)
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return pack_int(val)
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:]) 
        out[1][-2] ^= 0x80 
        return out  
    # pass strings on, let error happen somewhere else.    
    return inp
            
def equals(left,right): 
    if left[0] == '$':
        return pass_string_unpack(left) == pass_string_unpack(right)
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).equals(fp.unpack(right)) 
        else:
            return unpack_int(left)==unpack_int(right)

def gt(left, right):
    if left[0] == '$':
        return str_gt(pass_string_unpack(left), pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right)) 
        else:
            return unpack_int(left) > unpack_int(right)           
            
########################################
                
def format_number(value, fors):
    if value[0] == '#':
        type_sign, exp_sign = '#', 'D'
    else:
        type_sign, exp_sign = '!', 'E'
    c = fors.read(1)
    width = 0
    plus_sign = (c == '+')
    if plus_sign:
        c = fors.read(1)
        width += 1
    digits_before = 0
    dollar_sign = (c == '$')
    if dollar_sign:
        fors.read(1)
        c = fors.read(1)        
        digits_before += 2
    asterisk = (c == '*')    
    if asterisk:    
        fors.read(1)
        c = fors.read(1)
        digits_before += 2        
        if c == '$':
            dollar_sign = True
            c = fors.read(1)
            digits_before += 1
    if asterisk:
        fill_char = '*'
    else:
        fill_char = ' '
    while c == '#':
        digits_before += 1
        c = fors.read(1)
        if c == ',':
            digits_before += 1
            c = fors.read(1)            
    decimals = 0    
    dots = 0
    if c == '.':
        dots += 1
        c = fors.read(1)
        while c == '#':
            decimals += 1
            c = fors.read(1)
    width += digits_before + decimals + dots
    exp_form = False
    if c == '^':
        if util.peek(fors,3) == '^^^':
            fors.read(3)
            c = fors.read(1)
            exp_form = True
            width += 4
    sign_after = c in ('-','+') and not plus_sign
    if sign_after:
        if c == '+':
            plus_sign = True
        c = fors.read(1)
        width+=1
    if digits_before + decimals > 24:
        # illegal function call
        raise error.RunError(5)
    ##############################################
    # format to string
    expr = fp.unpack(number_abs(value))
    if exp_form:
        if not plus_sign and not sign_after and digits_before > 0:
            # reserve space for sign
            digits_before -= 1
        work_digits = digits_before + decimals
        if work_digits > expr.digits:
            # decimal precision of the type
            work_digits = expr.digits
        if work_digits > 0:
            # scientific representation
            lim_bot = fp.just_under(fp.pow_int(expr.ten, work_digits-1))
        else:
            # special case when work_digits == 0, see also below
            # setting to 0.1 results in incorrect rounding (why?)
            lim_bot = expr.one
        lim_top = lim_bot.copy()
        lim_top.imul10()
        num, exp10 = expr.bring_to_range(lim_bot, lim_top)
        digitstr = fp.get_digits(num, work_digits)
        if len(digitstr) < digits_before + decimals:
            digitstr += '0' * (digits_before+decimals-len(digitstr))
        # this is just to reproduce GW results for no digits: 
        # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
        if work_digits == 0:
            exp10 += 1
        exp10 += digits_before + decimals - 1  
        fp_repr = fp.scientific_notation(digitstr, exp10, exp_sign, digits_to_dot=digits_before, force_dot=(dots>0))
    else:
        # fixed-point representation
        factor = fp.pow_int(expr.ten, decimals) 
        unrounded = fp.mul(expr, factor)
        num = unrounded.copy().iround()
        # find exponent 
        exp10 = 1
        pow10 = fp.pow_int(expr.ten, exp10) # pow10 = 10L**exp10
        while num.gt(pow10) or num.equals(pow10): # while pow10 <= num:
            pow10.imul10() #pow10*=10
            exp10 += 1
        work_digits = exp10 + 1
        diff = 0
        if exp10 > expr.digits:
            diff = exp10 - expr.digits
            factor = fp.pow_int(expr.ten, diff) # pow10 = 10L**exp10
            num = fp.div(unrounded, factor).iround() #expr.from_int(10L**diff))
            work_digits -= diff
        num = num.trunc_to_int()   
        # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
        digitstr = fp.get_digits(num, work_digits-1, remove_trailing=False)
        # fill up with zeros
        digitstr += '0' * diff
        fp_repr = fp.decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', (dots>0))
    ##########################################
    valstr = ''
    if dollar_sign:
        valstr += '$'
    valstr += fp_repr    
    sign = unpack_int(number_sgn(value))
    if sign_after:
        sign_str = ' '
    else:
        sign_str = ''    
    if sign < 0:
        sign_str = '-'
    elif plus_sign:
        sign_str = '+'    
    if sign_after:
        valstr += sign_str
    else:
        valstr = sign_str + valstr
    if len(valstr) > width:
        valstr = '%' + valstr
    else:
        valstr = fill_char*(width-len(valstr)) + valstr
    return valstr
    
            
