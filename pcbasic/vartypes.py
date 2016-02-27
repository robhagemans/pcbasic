"""
PC-BASIC - vartypes.py
Type conversions and generic functions

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import fp
import error
import state

# BASIC types:
# Integer (%) - stored as two's complement, little-endian
# Single (!) - stored as 4-byte Microsoft Binary Format
# Double (#) - stored as 8-byte Microsoft Binary Format
# String ($) - stored as 1-byte length plus 2-byte pointer to string space

# zeroed out
def null(sigil):
    """ Return null value for the given type. """
    return {'$': ('$', bytearray()), '%': ('%', bytearray(2)), '!': ('!', bytearray(4)), '#': ('#', bytearray(8))}[sigil]

def complete_name(name):
    """ Add type specifier to a name, if missing. """
    if name and name[-1] not in ('$', '%', '!', '#'):
        name += state.basic_state.deftype[ord(name[0].upper()) - 65] # ord('A')
    return name

###############################################################################
# type checks

#RENAME pass_integer
def pass_int_keep(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """ Check if variable is numeric, convert to Int. """
    if not inp:
        raise error.RunError(error.STX)
    typechar = inp[0]
    if typechar == '%':
        return inp
    elif typechar in ('!', '#'):
        val = fp.unpack(inp).round_to_int()
        if val > maxint or val < -0x8000:
            # overflow
            raise error.RunError(error.OVERFLOW)
        return int_to_integer_unsigned(val)
    else:
        # type mismatch
        raise error.RunError(err)

#RENAME pass_single
def pass_single_keep(num):
    """ Check if variable is numeric, convert to Single. """
    if not num:
        raise error.RunError(error.STX)
    typechar = num[0]
    if typechar == '!':
        return num
    elif typechar == '%':
        return fp.pack(fp.Single.from_int(integer_to_int_signed(num)))
    elif typechar == '#':
        # *round* to single
        return fp.pack(fp.unpack(num).round_to_single())
    elif typechar == '$':
        raise error.RunError(error.TYPE_MISMATCH)

#RENAME pass_double
def pass_double_keep(num):
    """ Check if variable is numeric, convert to Double. """
    if not num:
        raise error.RunError(error.STX)
    typechar = num[0]
    if typechar == '#':
        return num
    elif typechar == '%':
        return fp.pack(fp.Double.from_int(integer_to_int_signed(num)))
    elif typechar == '!':
        return ('#', bytearray(4) + num[1])
    elif typechar == '$':
        raise error.RunError(error.TYPE_MISMATCH)

#RENAME pass_string
def pass_string_keep(inp, allow_empty=False, err=error.TYPE_MISMATCH):
    """ Check if variable is String-valued. """
    if not inp:
        if not allow_empty:
            raise error.RunError(error.STX)
        else:
            return null('$')
    if inp[0] == '$':
        return inp
    else:
        raise error.RunError(err)

#RENAME pass_float
def pass_float_keep(num, allow_double=True):
    """ Check if variable is numeric, convert to Double or Single. """
    if num and num[0] == '#' and allow_double:
        return num
    else:
        return pass_single_keep(num)

#RENAME pass_number
def pass_number_keep(inp, err=error.TYPE_MISMATCH):
    """ Check if variable is numeric. """
    if inp[0] not in ('%', '!', '#'):
        raise error.RunError(err)
    return inp

#RENAME pass_type
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
        raise error.RunError(error.STX)

#RENAME pass_most_precise
def pass_most_precise_keep(left, right, err=error.TYPE_MISMATCH):
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
# functions to be refactored

#D
def pass_string_unpack(inp, allow_empty=False, err=error.TYPE_MISMATCH):
    """ Convert String to Python bytearray. """
    return pass_string_keep(inp, allow_empty, err)[1]

#D
def pass_int_unpack(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """ Convert numeric variable to Python integer. """
    return integer_to_int_signed(pass_int_keep(inp, maxint, err))


###############################################################################
# convert between BASIC Integer and token bytes

def bytes_to_integer(in_bytes):
    """ Copy and convert token bytearray, list or str to BASIC integer. """
    return ('%', bytearray(in_bytes))

def integer_to_bytes(in_integer):
    """ Copy and convert BASIC integer to token bytearray. """
    return bytearray(in_integer[1])


###############################################################################
# convert between BASIC Integer and Python int

def int_to_integer_signed(n):
    """ Convert Python int in range [-32768, 32767] to BASIC Integer. """
    if n > 0x7fff or n < -0x8000:
        raise error.RunError(error.OVERFLOW)
    if n < 0:
        n = 0x10000 + n
    return ('%', bytearray((n&0xff, n >> 8)))

def int_to_integer_unsigned(n):
    """ Convert Python int in range [-32768, 65535] to BASIC Integer. """
    if n > 0xffff or n < -0x8000:
        raise error.RunError(error.OVERFLOW)
    if n < 0:
        n = 0x10000 + n
    return ('%', bytearray((n&0xff, n >> 8)))

def integer_to_int_signed(in_integer):
    """ Convert BASIC Integer to Python int in range [-32768, 32767]. """
    s = in_integer[1]
    # 2's complement signed int, least significant byte first,
    # sign bit is most significant bit
    value = 0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value
    else:
        return value

def integer_to_int_unsigned(in_integer):
    """ Convert BASIC Integer to Python int in range [0, 65535]. """
    s = in_integer[1]
    return 0x100 * s[1] + s[0]

###############################################################################
# convert between BASIC Strings and Python str

#RENAME string_to_str
def unpack_string(inp):
    """ Convert String to Python bytearray, no checks """
    return inp[1]

#RENAME str_to_string
#D already in representations.py
def pack_string(python_str):
    """ Convert and copy Python str or bytearray to String. """
    if len(python_str) > 255:
        raise error.RunError(error.STRING_TOO_LONG)
    return ('$', bytearray(python_str))

###############################################################################
# boolean functions operate as bitwise functions on unsigned Python ints

#RENAME bool_to_integer
def bool_to_int_keep(boo):
    """ Convert Python boolean to Integer. """
    return ('%', bytearray('\xff\xff')) if boo else ('%', bytearray('\0\0'))

#RENAME integer_to_bool
def int_to_bool(in_integer):
    """ Convert Integer to Python boolean. """
    return (in_integer[1][0] != 0 or in_integer[1][1] != 0)

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
        return null('%')
    # BASIC counts string positions from 1
    find = big[n-1:].find(small)
    if find == -1:
        return null('%')
    return int_to_integer_signed(n + find)

###############################################################################
# numeric operations

def number_add(left, right):
    """ Add two numbers. """
    left, right = pass_most_precise_keep(left, right)
    if left[0] in ('#', '!'):
        return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
    else:
        # return Single to avoid wrapping on integer overflow
        return fp.pack(fp.Single.from_int(integer_to_int_signed(left) + integer_to_int_signed(right)))

def number_sgn(inp):
    """ Return the sign of a number. """
    if inp[0] == '%':
        i = integer_to_int_signed(inp)
        if i > 0:
            return int_to_integer_signed(1)
        elif i < 0:
            return int_to_integer_signed(-1)
        else:
            return int_to_integer_signed(0)
    elif inp[0] in ('!', '#'):
        return int_to_integer_signed(fp.unpack(inp).sign())
    return inp

def number_abs(inp):
    """ Return the absolute value of a number. """
    if inp[0] == '%':
        val = abs(integer_to_int_signed(inp))
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return int_to_integer_signed(val)
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:])
        out[1][-2] &= 0x7F
        return out
    return inp

def number_neg(inp):
    """ Return the negation of a number. """
    if inp[0] == '%':
        val = -integer_to_int_signed(inp)
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return int_to_integer_signed(val)
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
            return integer_to_int_signed(left) == integer_to_int_signed(right)

def gt(left, right):
    """ Number ordering: return whether left > right. """
    if left[0] == '$':
        return str_gt(pass_string_unpack(left), pass_string_unpack(right))
    else:
        left, right = pass_most_precise_keep(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right))
        else:
            return integer_to_int_signed(left) > integer_to_int_signed(right)
