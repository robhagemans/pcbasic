"""
PC-BASIC - py
Type conversions and generic functions

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import fp
import error
import state
import config

# BASIC types:
# Integer (%) - stored as two's complement, little-endian
# Single (!) - stored as 4-byte Microsoft Binary Format
# Double (#) - stored as 8-byte Microsoft Binary Format
# String ($) - stored as 1-byte length plus 2-byte pointer to string space

byte_size = {'$': 3, '%': 2, '!': 4, '#': 8}

def null(sigil):
    """ Return null value for the given type. """
    return (sigil, bytearray(byte_size[sigil]))

def complete_name(name):
    """ Add type specifier to a name, if missing. """
    if name and name[-1] not in ('$', '%', '!', '#'):
        name += state.session.deftype[ord(name[0].upper()) - ord('A')]
    return name

###############################################################################
# type checks

def pass_integer(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
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

def pass_single(num):
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

def pass_double(num):
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

def pass_string(inp, allow_empty=False, err=error.TYPE_MISMATCH):
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

def pass_float(num, allow_double=True):
    """ Check if variable is numeric, convert to Double or Single. """
    if num and num[0] == '#' and allow_double:
        return num
    else:
        return pass_single(num)

def pass_number(inp, err=error.TYPE_MISMATCH):
    """ Check if variable is numeric. """
    if inp[0] not in ('%', '!', '#'):
        raise error.RunError(err)
    return inp

def pass_type(typechar, value):
    """ Check if variable can be converted to the given type and convert. """
    if typechar == '$':
        return pass_string(value)
    elif typechar == '%':
        return pass_integer(value)
    elif typechar == '!':
        return pass_single(value)
    elif typechar == '#':
        return pass_double(value)
    else:
        raise error.RunError(error.STX)

def pass_most_precise(left, right, err=error.TYPE_MISMATCH):
    """ Check if variables are numeric and convert to highest-precision. """
    left_type, right_type = left[0][-1], right[0][-1]
    if left_type=='#' or right_type=='#':
        return (pass_double(left), pass_double(right))
    elif left_type=='!' or right_type=='!':
        return (pass_single(left), pass_single(right))
    elif left_type=='%' or right_type=='%':
        return (pass_integer(left), pass_integer(right))
    else:
        raise error.RunError(err)


###############################################################################
# convenience functions

#D
def pass_int_unpack(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """ Convert numeric variable to Python integer. """
    return integer_to_int_signed(pass_integer(inp, maxint, err))


#D
def number_unpack(value):
    """ Unpack a number value. """
    if value[0] in ('#', '!'):
        return fp.unpack(value)
    else:
        return integer_to_int_signed(value)


###############################################################################
# convert between BASIC Integer and token bytes

def bytes_to_integer(in_bytes):
    """ Copy and convert token bytearray, list or str to BASIC integer. """
    return ('%', bytearray(in_bytes))

def integer_to_bytes(in_integer):
    """ Copy and convert BASIC integer to token bytearray. """
    return bytearray(in_integer[1])


###############################################################################
# convert between BASIC String and token address bytes

def bytes_to_string(in_bytes):
    """ Copy and convert token bytearray, list or str to BASIC string. """
    return ('$', bytearray(in_bytes))

def string_to_bytes(in_string):
    """ Copy and convert BASIC string to token bytearray. """
    return bytearray(in_string[1])

def string_length(in_string):
    """ Get string length as Python int. """
    return in_string[1][0]

def string_address(in_string):
    """ Get string address as Python int. """
    return integer_to_int_unsigned(bytes_to_integer(in_string[1][1:]))


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
# boolean functions operate as bitwise functions on unsigned Python ints

def bool_to_integer(boo):
    """ Convert Python boolean to Integer. """
    return ('%', bytearray('\xff\xff')) if boo else ('%', bytearray('\0\0'))

def integer_to_bool(in_integer):
    """ Convert Integer to Python boolean. """
    return (in_integer[1][0] != 0 or in_integer[1][1] != 0)
