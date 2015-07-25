"""
PC-BASIC 3.23 - vartypes.py
Type conversions and generic functions

(c) 2013, 2014 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import fp
import error
import state

# zeroed out
null = { '$': ('$', ''), '%': ('%', bytearray('\x00')*2), '!': ('!', bytearray('\x00')*4), '#': ('#', bytearray('\x00')*8) }

def complete_name(name):
    """ Add type specifier to a name, if missing. """
    if name and name[-1] not in ('$', '%', '!', '#'):
        name += state.basic_state.deftype[ord(name[0].upper()) - 65] # ord('A')
    return name

###############################################################################
# Int (%) - stored as two's complement, little-endian

def pass_int_keep(inp, maxint=0x7fff, err=13):
    """ Check if variable is numeric, convert to Int. """
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
    """ Convert numeric variable to Python integer. """
    return unpack_int(pass_int_keep(inp, maxint, err))

def unpack_int(inp):
    """ Convert Int to Python integer. """
    return sint_to_value(inp[1])

def pack_int(inp):
    """ Convert Python integer to Int. """
    return ('%', value_to_sint(inp))


###############################################################################
# Single (!) - stored as 4-byte Microsoft Binary Format

def pass_single_keep(num):
    """ Check if variable is numeric, convert to Single. """
    if not num:
        raise error.RunError(2)
    typechar = num[0]
    if typechar == '!':
        return num
    elif typechar == '%':
        return fp.pack(fp.Single.from_int(unpack_int(num)))
    elif typechar == '#':
        # *round* to single
        return fp.pack(fp.unpack(num).round_to_single())
    elif typechar == '$':
        raise error.RunError(13)

###############################################################################
# Double (!) - stored as 8-byte Microsoft Binary Format

def pass_double_keep(num):
    """ Check if variable is numeric, convert to Double. """
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

###############################################################################
# String ($) - stored as 1-byte length plus 2-byte pointer to string space

def pass_string_keep(inp, allow_empty=False, err=13):
    """ Check if variable is String-valued. """
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
    """ Convert string-valued variable to Python bytearray. """
    return pass_string_keep(inp, allow_empty, err)[1]

def unpack_string(inp):
    """ Convert string-valued variable to Python bytearray, no checks """
    return inp[1]

def pack_string(inp):
    """ Convert Python bytearray to string-valued variable, no checks. """
    return ('$', inp)

###############################################################################
# multi-type functions

def pass_float_keep(num, allow_double=True):
    """ Check if variable is numeric, convert to Double or Single. """
    if num and num[0] == '#' and allow_double:
        return num
    else:
        return pass_single_keep(num)

def pass_number_keep(inp, err=13):
    """ Check if variable is numeric. """
    if inp[0] not in ('%', '!', '#'):
        raise error.RunError(err)
    return inp

def pass_type_keep(typechar, value):
    """ Check if variable can be converted to the given type and convert. """
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
    """ Check if variables are numeric and convert to highest-precision. """
    left_type, right_type = left[0][-1], right[0][-1]
    if left_type=='#' or right_type=='#':
        return (pass_double_keep(left), pass_double_keep(right))
    elif left_type=='!' or right_type=='!':
        return (pass_single_keep(left), pass_single_keep(right))
    elif left_type=='%' or right_type=='%':
        return (pass_int_keep(left), pass_int_keep(right))
    else:
        raise error.RunError(err)


###############################################################################
# int tokens to Python ints

def uint_to_value(s):
    """ Convert unsigned little-endian int token to Python integer """
    return 0x100 * s[1] + s[0]

def sint_to_value(s):
    """ Convert two's complement little-endian int token to Python integer """
    # 2's complement signed int, least significant byte first, sign bit is most significant bit
    value = 0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value
    else:
        return value

###############################################################################
# Python ints to int tokens

def value_to_uint(n):
    """ Convert Python integer to unsigned little-endian token. """
    if n > 0xffff:
        # overflow
        raise error.RunError(6)
    return bytearray((n&0xff, n >> 8))

def value_to_sint(n):
    """ Convert Python integer to two's complement little-endian token. """
    if n > 0xffff:  # 0x7fff ?
        # overflow
        raise error.RunError(6)
    if n < 0:
        n = 0x10000 + n
    return bytearray((n&0xff, n >> 8))

###############################################################################
# boolean functions operate as bitwise functions on unsigned Python ints

def bool_to_int_keep(boo):
    """ Convert Python boolean to Int. """
    return pack_int(-boo)

def int_to_bool(iboo):
    """ Convert Int to Python boolean. """
    return not (unpack_int(iboo) == 0)

# _twoscomp is a misnomer here, _unsigned would be better
def pass_twoscomp(num):
    """ Convert Int to Python int (unsigned). """
    val = pass_int_unpack(num)
    if val < 0:
        return 0x10000 + val
    else:
        return val

# _twoscomp is a misnomer here, _unsigned would be better
def twoscomp_to_int(num):
    """ Convert Python int (unsigned) to Int. """
    if num > 0x7fff:
        num -= 0x10000
    return pack_int(num)

###############################################################################
# string operations

def str_gt(left, right):
    """ String ordering: return whether left > right. """
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

def str_instr(big, small, n):
    """ Find substring in string and return starting index. """
    if big == '' or n > len(big):
        return null['%']
    # BASIC counts string positions from 1
    find = big[n-1:].find(small)
    if find == -1:
        return null['%']
    return pack_int(n + find)

###############################################################################
# numeric operations

def number_add(left, right):
    """ Add two numbers. """
    left, right = pass_most_precise_keep(left, right)
    if left[0] in ('#', '!'):
        return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
    else:
        return pack_int(unpack_int(left) + unpack_int(right))

def number_sgn(inp):
    """ Return the sign of a number. """
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
    """ Return the absolute value of a number. """
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
    """ Return the negation of a number. """
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
    """ Return whether two numbers are equal. """
    if left[0] == '$':
        return pass_string_unpack(left) == pass_string_unpack(right)
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).equals(fp.unpack(right))
        else:
            return unpack_int(left)==unpack_int(right)

def gt(left, right):
    """ Number ordering: return whether left > right. """
    if left[0] == '$':
        return str_gt(pass_string_unpack(left), pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right))
        else:
            return unpack_int(left) > unpack_int(right)
