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
old__null = { '$': ('$', ''), '%': ('%',0), '!':('!', bytearray('\x00')*4), '#':('#', bytearray('\x00')*8) }

null = { '$': ('$', ''), '%': ('%', bytearray('\x00')*2), '!': ('!', bytearray('\x00')*4), '#': ('#', bytearray('\x00')*8) }

def complete_name(name):
    if name != '' and name[-1] not in ('$', '%', '!', '#'):
        name += deftype[ord(name[0].upper()) - 65] # ord('A') 
    return name


def pass_int_keep(inp, maxint=0x7fff, err=13):
    typechar = inp[0]
    if typechar == '%':
        return inp
    elif typechar in ('!', '#'):
        val = fp.unpack(inp).round_to_int()
        if val > maxint or val < -0x8000:
            # overflow
            raise error.RunError(6)
        return pack_int(val)
    elif typechar == '':
        raise error.RunError(2)    
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

def old__pass_int_unpack(inp, maxint=0x7fff, err=13):
    typechar = inp[0]
    if typechar == '%':
        val = inp[1]
    elif typechar in ('!', '#'):
        val = fp.unpack(inp).round_to_int()
    elif typechar == '':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(err)
    if val > maxint or val < -0x8000:
        # overflow
        raise error.RunError(6)
    return val


def old__pass_int_keep(inp, maxint=0x7fff, err=13):
    return ('%', pass_int_unpack(inp, maxint, err))


def pass_single_keep(num):
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
    else:
        raise error.RunError(2)
    
    
def pass_double_keep(num):
    typechar = num[0]
    if typechar == '#':
        return num
    elif typechar == '%':
        return fp.pack(fp.Double.from_int(unpack_int(num)))
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
        if screen and not write and unpack_int(inp) >= 0:
            return ('$', ' '+ int_to_str(unpack_int(inp)) )
        else:
            return ('$', int_to_str(unpack_int(inp)))
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


def old__unpack_int(inp):
    return inp[1]

def old__pack_int(inp):
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
    if left[0]=='$':
        return str_gt(pass_string_unpack(left), pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right)) 
        else:
            return unpack_int(left) > unpack_int(right)           



