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
null = { '$': ('$', ''), '%': ('%',0), '!':('!', bytearray('\x00')*4), '#':('#', bytearray('\x00')*8) }


def complete_name(name):
    if name != '' and name[-1] not in ('$', '%', '!', '#'):
        return name + deftype[ord(name[0].upper()) - 65] # ord('A') 
    

def pass_int_unpack(inp, maxint=0x7fff, err=13):
    typechar = inp[0]
    if typechar == '%':
        return inp[1]
    elif typechar in ('!', '#'):
        return fp.unpack(inp).round_to_int()
    elif typechar == '':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(err)
    if val > maxint or val < -0x8000:
        # overflow
        raise error.RunError(6)
    


def pass_int_keep(inp, maxint=0x7fff, err=13):
    return ('%', pass_int_unpack(inp, maxint, err))


def pass_single_keep(num):
    typechar = num[0]
    if typechar == '!':
        return num
    elif typechar == '%':
        return fp.pack(fp.Single.from_int(num[1]))
    elif typechar == '#':
        val = num[1][4:]
        # TODO: *round* to single
        #if (num[1][3] & 0x80) == 1: 
        return ('!', val)        
    elif typechar == '$':
        raise error.RunError(13)
    else:
        raise error.RunError(2)
    
    
def pass_double_keep(num):
    typechar = num[0]
    if typechar == '#':
        return num
    elif typechar == '%':
        return fp.pack(fp.Double.from_int(num[1]))
    elif typechar == '!':
        return ('#', bytearray('\x00\x00\x00\x00')+num[1])    
    elif typechar == '$':
        raise error.RunError(13)
    else:
        raise error.RunError(2)
    

def pass_float_keep(num, allow_double=True):
    if num[0] == '#' and allow_double:
        return num
    else:
        return pass_single_keep(num)


def pass_string_keep(inp, allow_empty=False, err=13):
    if inp[0] == '$':
        return inp
    elif inp[0]=='':
        if not allow_empty:
            raise error.RunError(2)    
        else:
            return ('$', '')
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
    typechar = inp[0]
    if typechar == '$':
        return ('$', inp[1])
    elif typechar == '%':
        if screen and not write and inp[1]>=0:
            return ('$', ' '+ int_to_str(inp[1]) )
        else:
            return ('$', int_to_str(inp[1]))
    elif typechar == '!':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    elif typechar == '#':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    elif typechar == '':
        if allow_empty_expression:
            return ('$', '')
        else:
            raise error.RunError(2)    
    else:
        raise error.RunError(2)    




    
##################################################
# unpack tokenised numeric constants


def unpack_int(inp):
    return inp[1]

def pack_int(inp):
    return ('%', inp)
   
def uint_to_value(s):
    # unsigned int. 
    return 0x100 * s[1] + s[0]

def sint_to_value(s):
    # 2's complement signed int, least significant byte first, sign bit is most significant bit
    value =  0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value 
    else: 
        return value
    
# python ints to tokenised ints

def value_to_uint(n):
    if n>0xffff:
        # overflow
        raise error.RunError(6)        
    return bytearray((n&0xff, n >> 8)) 

def value_to_sint(n):
    if n>0xffff:  # 0x7fff ?
        # overflow
        raise error.RunError(6)     
    if n<0:
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
    

# python str to tokenised int

def str_to_uint(s):
    return value_to_uint(int(s))

def str_to_hex(word):
    if len(word)<=2:
        return 0
    word=word[2:]
    return value_to_uint(int(word,16))

def str_to_oct(word):
    if len(word)<=2:
        return 0
    word=word[2:]
    return value_to_uint(int(word,8))
                
    
# boolean functions - two's complement int

def bool_to_int_keep(boo):
    return ('%', -boo)
    
def int_to_bool(iboo):
    return not (iboo[1] == 0)

def pass_twoscomp(num):
    val = pass_int_unpack(num)
    if val<0:
        return 0x10000 + val
    else:
        return val

def twoscomp_to_int(num):
    if num > 0x7fff:
        num -= 0x10000 
    return ('%', num)    
    


###########################################################
###########################################################
###########################################################

# maths functions

from functools import partial

# command line option /d
# allow double precision math for ^, ATN, COS, EXP, LOG, SIN, SQR, and TAN
option_double = False


    
###########################################################
# unary functions


# option_double regulated single & double precision math

def vunary(inp, fn):
    return fp.pack(fn(fp.unpack(pass_float_keep(inp, option_double))))

vsqrt = partial(vunary, fn=fp.sqrt)
vexp = partial(vunary, fn=fp.exp)
vsin = partial(vunary, fn=fp.sin)
vcos = partial(vunary, fn=fp.cos)
vtan = partial(vunary, fn=fp.tan)
vatn = partial(vunary, fn=fp.atn)
vlog = partial(vunary, fn=fp.log)
 
# others

def vabs(inp):
    if inp[0] == '$':
        raise error.RunError(13)
        return inp
    elif inp[0]== '%':
        return (inp[0], abs(inp[1]))
    elif inp[0] in ('!','#'):
        out = (inp[0], inp[1][:])  
        out[1][-2] &= 0x7F 
        return out  
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    

def vint(inp):
    if inp[0]=='%':
        return inp
    elif inp[0] in ('!', '#'):
        return fp.pack(fp.unpack(inp).ifloor()) 
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    

def vsgn(inp):
    if inp[0]=='%':
        if inp[1]>0:
            return ('%', 1)
        elif inp[1] <0:
            return ('%', -1)
        else:
            return ('%', 0)
    elif inp[0] in ('!','#'):
        return ('%', fp.unpack(inp).sign() )
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    

def vfix(inp):
    if inp[0]=='%':
        return inp
    elif inp[0]=='!':
        # needs to be a float to avoid overflow
        return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int())) 
    elif inp[0]=='#':
        return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int())) 
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    
    
def vneg(inp):
    if inp[0] == '$':
        raise error.RunError(13)
    elif inp[0] == '%':
        return (inp[0], -inp[1])
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:]) 
        out[1][-2] ^= 0x80 
        return out  
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)

        
def vnot(inp):
    # two's complement
    return ('%', -pass_int_unpack(inp)-1)

    
# binary operators
        
def vcaret(left, right):
    if (left[0] == '#' or right[0] == '#') and option_double:
        return fp.pack( fp.power(fp.unpack(pass_double_keep(left)), fp.unpack(pass_double_keep(right))) )
    else:
        if right[0]=='%':
            return fp.pack( fp.unpack(pass_single_keep(left)).ipow_int(right[1]) )
        else:
            return fp.pack( fp.power(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )


def vtimes(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.unpack(pass_double_keep(left)).imul(fp.unpack(pass_double_keep(right))) )
    else:
        return fp.pack( fp.unpack(pass_single_keep(left)).imul(fp.unpack(pass_single_keep(right))) )


def vdiv(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(pass_double_keep(left)), fp.unpack(pass_double_keep(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )


def vidiv(left, right):
    return ('%', pass_int_unpack(left) / pass_int_unpack(right))    
    
    
def vmod(left, right):
    return ('%', pass_int_unpack(left) % pass_int_unpack(right))    


def vplus(left, right):
    if left[0] == '$':
        return ('$', pass_string_unpack(left) + pass_string_unpack(right) )
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
        else:
            return ('%', left[1]+right[1])           
    

def vminus(left, right):
    return vplus(left, vneg(right))
    
    
def str_gt(left,right):
    shortest = min(len(left), len(right))
    for i in range(shortest):
        if left[i]>right[i]:
            return True
        elif left[i]<right[i]:
            return False
    # the same so far...
    
    # the shorter string is said to be less than the longer, 
    # provided they are the same up till the length of the shorter.
    if len(left)>len(right):
        return True
    # left is shorter, or equal strings
    return False                    

    
def vgt(left, right):
    gt = False
    if left[0]=='$':
        gt = str_gt(pass_string_unpack(left), pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            gt = fp.unpack(left).gt(fp.unpack(right)) 
        else:
            gt = left[1]>right[1]           
    
    return bool_to_int_keep(gt) 
    

def vlt(left, right):
    return vnot(vgte(left, right))
    
def vgte(left, right):
    return vor(vgt(left,right), veq(left, right))
    
def vlte(left, right):
    return vnot(vgt(left, right))
    
def veq(left, right):
    if left[0] == '$':
        return bool_to_int_keep(pass_string_unpack(left) == pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return bool_to_int_keep(fp.unpack(left).equals(fp.unpack(right)) )
        else:
            return bool_to_int_keep(left[1]==right[1])    

def vneq(left, right):
    return vnot(veq(left,right))
    
def vand(left, right):
    return twoscomp_to_int( pass_twoscomp(left) & pass_twoscomp(right) )
            
def vor(left, right):
    return twoscomp_to_int( pass_twoscomp(left) | pass_twoscomp(right) )
                       
def vxor(left, right):
    return twoscomp_to_int( pass_twoscomp(left) ^ pass_twoscomp(right) )

def veqv(left, right):
    return vnot(vxor(left, right))

def vimp(left, right):
    return vor(vnot(left), right)

    
