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

import copy

import fp
import error

floats = ['#','!']
numeric = floats + ['%']
strings = ['$']
all_types = numeric + strings


# command line option /d
# allow double precision math for ^, ATN, COS, EXP, LOG, SIN, SQR, and TAN
option_double = False




def is_type(typechars, value):
    return (value[0] in typechars)


def pass_int_keep(inp, maxint=0x7fff, err=13):
    val = 0
    if inp[0]=='%':
        val= inp[1]
    elif inp[0] in ('!', '#'):
        val= fp.round_to_int(fp.unpack(inp))
    #elif inp[0]=='#':
    #    val= fp.round_to_int(fp.mbfd_frombytes(inp[1]))
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(err)
    if val > maxint or val < -0x8000:
        # overflow
        raise error.RunError(6)
    
    return ('%', val)


def pass_single_keep(num):
    
    if num[0] == '!':
        val= num[1]
    elif num[0] == '%':
        val= fp.to_bytes(fp.from_int(fp.MBF_class,num[1]))
    elif num[0] == '#':
        # TODO: *round* to single
        if (ord(num[1][6]) & 0x80) == 0: 
            val= num[1][4:]
        else:
            val= num[1][4:]    
    elif num[0] == '$':
        raise error.RunError(13)
    else:
        raise error.RunError(2)
    
    return ('!', val)
    
    

def pass_double_keep(num):
    if num[0] == '#':
        val = num[1]
    elif num[0] == '%':
        val = fp.to_bytes(fp.from_int(fp.MBFD_class, num[1]))
    elif num[0] == '!':
        val = ('\x00', '\x00', '\x00', '\x00', num[1][0], num[1][1], num[1][2], num[1][3])    
    elif num[0] == '$':
        raise error.RunError(13)
    else:
        raise error.RunError(2)
    return ('#', val)


def pass_float_keep(num):
    if num[0] == '#':
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


def pass_type_keep(typechar, value):     
    if typechar == '$':
        return pass_string_keep(value)
    elif typechar == '%':
        return pass_int_keep(value)
    elif typechar=='!':
        return pass_single_keep(value)
    elif typechar=='#':
        return pass_double_keep(value)
    else:
        raise error.RunError(2)
  
 
def pass_most_precise_keep(left, right, err=13):
    if is_type('#', left) or is_type('#', right):
        return (pass_type_keep('#', left), pass_type_keep('#', right))
    elif is_type('!', left) or is_type('!', right):
        return (pass_type_keep('!', left), pass_type_keep('!', right))
    elif is_type('%', left) or is_type('%', right):
        return (pass_type_keep('%', left), pass_type_keep('%', right))
    else:
        raise error.RunError(err)
        






# string output
# screen=False means in a program listing
# screen=True is used for screen, str$ and sequential files
def value_to_str_keep(inp, screen=False, write=False, allow_empty_expression=False):
    
    if inp[0] == '$':
        return ('$', inp[1])
    elif inp[0]== '%':
        if screen and not write and inp[1]>=0:
            return ('$', ' '+ int_to_str(inp[1]) )
        else:
            return ('$', int_to_str(inp[1]))
    elif inp[0]=='!':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    elif inp[0]=='#':
        return ('$', fp.to_str(fp.unpack(inp), screen, write) )
    elif inp[0]=='':
        if allow_empty_expression:
            return ('$', '')
        else:
            raise error.RunError(2)    
    else:
        raise error.RunError(2)    

    
##################################################
##################################################

# unpack GW-BASIC numeric constants


def ubyte_to_value(s):
    return ord(s)
    
def uint_to_value(s):
    s = map(ord, s)
    # unsigned int. 
    return 0x100 * s[1] + s[0]

def sint_to_value(s):
    # 2's complement signed int, least significant byte first, sign bit is most significant bit
    s = map(ord, s)
    value =  0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value 
    else: 
        return value

# pack

    
# string representations    

def int_to_str(num):
    return str(num)   



    
   
def uint_to_str(s):
    return str(uint_to_value(s))

def sint_to_str(s):
    return str(sint_to_value(s))

def ubyte_to_str(s):
    return str(ord(s))
    
    
    
    

def value_to_uint(n):
    if n>0xffff:
        # overflow
        raise error.RunError(6)        
    return chr(n&0xff)+ chr(n >> 8) 


def value_to_sint(n):
    if n>0xffff:  # 0x7fff ?
        # overflow
        raise error.RunError(6)     
    if n<0:
        n = 0x10000 + n        
    return chr(n&0xff)+ chr(n >> 8) 


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
                

def hex_to_str(s):
    return "&H" + hex(uint_to_value(s))[2:].upper()

def oct_to_str(s):
    return "&O" + oct(uint_to_value(s))[1:]
   

   
    



   
   
   
########################################################### 

    

def null_keep(typechar):
    if typechar=='$':
        return ('$', '')
    elif typechar == '%':
        return  ('%', 0)
    elif typechar == '!':
        return  fp.pack(fp.MBF_class.zero)
    elif typechar == '#':
        return  fp.pack(fp.MBFD_class.zero)
            
    

# single & double precision math

def vsqrt(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_sqrt(fp.unpack(pass_double_keep(inp))))
    else:
        return fp.pack(fp.mbf_sqrt(fp.unpack(pass_single_keep(inp))))
        
def vexp(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_pow(fp.mbfd_e, fp.unpack(pass_double_keep(inp)))) 
    else:
        return fp.pack(fp.mbf_pow(fp.mbf_e, fp.unpack(pass_single_keep(inp)))) 
            
def vsin(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_sin(fp.unpack(pass_double_keep(inp)))) 
    else:
        return fp.pack(fp.mbf_sin(fp.unpack(pass_single_keep(inp)))) 

def vcos(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_cos(fp.unpack(pass_double_keep(inp))))
    else:
        return fp.pack(fp.mbf_cos(fp.unpack(pass_single_keep(inp))))

def vtan(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_tan(fp.unpack(pass_double_keep(inp))))
    else:
        return fp.pack(fp.mbf_tan(fp.unpack(pass_single_keep(inp)))) 

def vatn(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_atn(fp.unpack(pass_double_keep(inp)))) 
    else:
        return fp.pack(fp.mbf_atn(fp.unpack(pass_single_keep(inp)))) 

def vlog(inp):
    if inp[0] == '#' and option_double:
        return fp.pack(fp.mbfd_log(fp.unpack(pass_double_keep(inp))))
    else:
        return fp.pack(fp.mbf_log(fp.unpack(pass_single_keep(inp)))) 



###########################################################
# functions


def vabs(inp):
    if inp[0] == '$':
        raise error.RunError(13)
        return inp
    elif inp[0]== '%':
        return (inp[0], abs(inp[1]))
    elif inp[0] in ('!','#'):
        out = copy.deepcopy(inp) 
        out[1][-2] = chr( ord(out[1][-2]) & 0x7F ) 
        return out  
    #elif inp[0]=='#':
    #    out = copy.copy(inp)
    #    out[1][6] = chr( ord(out[1][6]) & 0x7F ) 
    #    return out  
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    

def vint(inp):
    if inp[0]=='%':
        return inp
    elif inp[0]=='!':
        return fp.pack(fp.floor(fp.unpack(inp))) 
    elif inp[0]=='#':
        return fp.pack(fp.floor(fp.unpack(inp))) 
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
        return ('%', fp.sign(fp.unpack(inp)) )
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
        return fp.pack(fp.from_int(fp.MBF_class,fp.trunc_to_int(fp.unpack(inp)))) 
    elif inp[0]=='#':
        return fp.pack(fp.from_int(fp.MBFD_class,fp.trunc_to_int(fp.unpack(inp)))) 
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    
    
    
    

def vnot(inp):
    # two's complement
    return ('%', -pass_int_keep(inp)[1]-1)


# unary operators
    
def vneg(inp):
    if inp[0] == '$':
        raise error.RunError(13)
        return inp
    elif inp[0]== '%':
        return (inp[0], -inp[1])
    elif inp[0] == '!':
        out = copy.deepcopy(inp)
        out[1][2] = chr( ord(out[1][2]) ^ 0x80 ) 
        return out  
    elif inp[0]=='#':
        out = copy.deepcopy(inp)
        out[1][6] = chr( ord(inp[1][6]) ^ 0x80 ) 
        return out 
    elif inp[0]=='':
        raise error.RunError(2)    
    else:     
        # type mismatch
        raise error.RunError(13)
    
# binary operators
        
def vcaret(left, right):
    if (left[0] == '#' or right[0] == '#') and option_double:
        #if option_double:
            return fp.pack( fp.mbfd_pow(fp.unpack(pass_double_keep(left)), fp.unpack(pass_double_keep(right))) )
        #else:
        #    return fp.pack( fp.mbf_pow(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )
    else:
        if right[0]=='%':
            return fp.pack( fp.ipow(fp.unpack(pass_single_keep(left)), right[1]) )
        else:
            return fp.pack( fp.mbf_pow(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )


def vtimes(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.mul(fp.unpack(pass_double_keep(left)), fp.unpack(pass_double_keep(right))) )
    else:
        return fp.pack( fp.mul(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )


def vdiv(left, right):
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(pass_double_keep(left)), fp.unpack(pass_double_keep(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(pass_single_keep(left)), fp.unpack(pass_single_keep(right))) )


def vidiv(left, right):
    return ('%', pass_int_keep(left)[1] / pass_int_keep(right)[1])    
    
def vmod(left, right):
    return ('%', pass_int_keep(left)[1] % pass_int_keep(right)[1])    



def vplus(left, right):
    if left[0] == '$':
        return ('$', pass_string_keep(left)[1] + pass_string_keep(right)[1] )
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] == '#':
            return fp.pack(fp.add(fp.unpack(left), fp.unpack(right)))
        elif left[0] == '!':
            return fp.pack(fp.add(fp.unpack(left), fp.unpack(right)))
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
        gt = str_gt(pass_string_keep(left)[1], pass_string_keep(right)[1])
        #gt = (len(pass_string_keep(left)[1]) > len(pass_string_keep(right)[1]))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            gt = fp.gt(fp.unpack(left), fp.unpack(right)) 
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
        return bool_to_int_keep(pass_string_keep(left)[1] == pass_string_keep(right)[1])
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return bool_to_int_keep(fp.equals(fp.unpack(left),fp.unpack(right)) )
        else:
            return bool_to_int_keep(left[1]==right[1])    
    
    
# two's complement int

def bool_to_int_keep(boo):
    if boo:
        return ('%', -1)
    else:
        return ('%', 0)


def int_to_bool(iboo):
    return not (iboo[1] == 0)
       


def pass_twoscomp(num):
    val = pass_int_keep(num)[1]
    if val<0:
        return 0x10000 + val
    else:
        return val

def twoscomp_to_int(num):
    if num > 0x7fff:
        num -= 0x10000 
        
    return ('%', num )    
    
        
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

    
    
    
    
    
    
    
        
