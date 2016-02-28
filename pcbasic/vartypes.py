"""
PC-BASIC - py
Type conversions and generic functions

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3.
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

# command line option /d
# allow double precision math for ^, ATN, COS, EXP, LOG, SIN, SQR, and TAN
option_double = False

def prepare():
    """ Initialise expressions module. """
    global option_double
    option_double = config.get('double')

# zeroed out
def null(sigil):
    """ Return null value for the given type. """
    return {'$': ('$', bytearray()), '%': ('%', bytearray(2)), '!': ('!', bytearray(4)), '#': ('#', bytearray(8))}[sigil]

def complete_name(name):
    """ Add type specifier to a name, if missing. """
    if name and name[-1] not in ('$', '%', '!', '#'):
        name += state.basic_state.deftype[ord(name[0].upper()) - ord('A')]
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
def pass_string_unpack(inp, allow_empty=False, err=error.TYPE_MISMATCH):
    """ Convert String to Python bytearray. """
    return pass_string(inp, allow_empty, err)[1]

#D
def pass_int_unpack(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """ Convert numeric variable to Python integer. """
    return integer_to_int_signed(pass_integer(inp, maxint, err))


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

def string_to_str(inp):
    """ Convert and copy String to Python bytearray """
    return bytearray(inp[1])

def str_to_string(python_str):
    """ Convert and copy Python str or bytearray to String. """
    if len(python_str) > 255:
        raise error.RunError(error.STRING_TOO_LONG)
    return ('$', bytearray(python_str))

###############################################################################
# boolean functions operate as bitwise functions on unsigned Python ints

def bool_to_integer(boo):
    """ Convert Python boolean to Integer. """
    return ('%', bytearray('\xff\xff')) if boo else ('%', bytearray('\0\0'))

def integer_to_bool(in_integer):
    """ Convert Integer to Python boolean. """
    return (in_integer[1][0] != 0 or in_integer[1][1] != 0)

###############################################################################
# string operations

def string_gt(left, right):
    """ String ordering: return whether left > right. """
    left, right = pass_string_unpack(left), pass_string_unpack(right)
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

def string_instr(big, small, n):
    """ Find substring in string and return starting index. """
    big, small = pass_string_unpack(big), pass_string_unpack(small)
    if big == '' or n > len(big):
        return null('%')
    # BASIC counts string positions from 1
    find = big[n-1:].find(small)
    if find == -1:
        return null('%')
    return int_to_integer_signed(n + find)

def string_concat(left, right):
    """ Concatenate strings. """
    return str_to_string(pass_string_unpack(left) + pass_string_unpack(right))

###############################################################################
# numeric operations

def number_add(left, right):
    """ Add two numbers. """
    left, right = pass_most_precise(left, right)
    if left[0] in ('#', '!'):
        return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
    else:
        # return Single to avoid wrapping on integer overflow
        return fp.pack(fp.Single.from_int(integer_to_int_signed(left) + integer_to_int_signed(right)))

def number_subtract(left, right):
    """ Subtract two numbers. """
    return number_add(left, number_neg(right))

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
    inp = pass_number(inp)
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


def number_power(left, right):
    """ Left^right. """
    if (left[0] == '#' or right[0] == '#') and option_double:
        return fp.pack( fp.power(fp.unpack(pass_double(left)), fp.unpack(pass_double(right))) )
    else:
        if right[0] == '%':
            return fp.pack( fp.unpack(pass_single(left)).ipow_int(integer_to_int_signed(right)) )
        else:
            return fp.pack( fp.power(fp.unpack(pass_single(left)), fp.unpack(pass_single(right))) )

def number_multiply(left, right):
    """ Left*right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.unpack(pass_double(left)).imul(fp.unpack(pass_double(right))) )
    else:
        return fp.pack( fp.unpack(pass_single(left)).imul(fp.unpack(pass_single(right))) )

def number_divide(left, right):
    """ Left/right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(pass_double(left)), fp.unpack(pass_double(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(pass_single(left)), fp.unpack(pass_single(right))) )

def number_intdiv(left, right):
    """ Left\\right. """
    dividend = pass_int_unpack(left)
    divisor = pass_int_unpack(right)
    if divisor == 0:
        # simulate (float!) division by zero
        return number_divide(left, right)
    if (dividend >= 0) == (divisor >= 0):
        return int_to_integer_signed(dividend / divisor)
    else:
        return int_to_integer_signed(-(abs(dividend) / abs(divisor)))

def number_modulo(left, right):
    """ Left MOD right. """
    divisor = pass_int_unpack(right)
    if divisor == 0:
        # simulate (float!) division by zero
        return number_divide(left, right)
    dividend = pass_int_unpack(left)
    mod = dividend % divisor
    if dividend < 0 or mod < 0:
        mod -= divisor
    return int_to_integer_signed(mod)

def number_not(right):
    """ Bitwise NOT, -x-1. """
    return int_to_integer_signed(-pass_int_unpack(right)-1)

def number_and(left, right):
    """ Bitwise AND. """
    return int_to_integer_unsigned(
        integer_to_int_unsigned(pass_integer(left)) &
        integer_to_int_unsigned(pass_integer(right)))

def number_or(left, right):
    """ Bitwise OR. """
    return int_to_integer_unsigned(
        integer_to_int_unsigned(pass_integer(left)) |
        integer_to_int_unsigned(pass_integer(right)))

def number_xor(left, right):
    """ Bitwise XOR. """
    return int_to_integer_unsigned(
        integer_to_int_unsigned(pass_integer(left)) ^
        integer_to_int_unsigned(pass_integer(right)))

def number_eqv(left, right):
    """ Bitwise equivalence. """
    return int_to_integer_unsigned(0xffff-(
        integer_to_int_unsigned(pass_integer(left)) ^
        integer_to_int_unsigned(pass_integer(right))))

def number_imp(left, right):
    """ Bitwise implication. """
    return int_to_integer_unsigned(
        (0xffff-integer_to_int_unsigned(pass_integer(left))) |
        integer_to_int_unsigned(pass_integer(right)))

###############################################################################
# number and string operations

def _bool_eq(left, right):
    """ Return true if left == right, false otherwise. """
    if left[0] == '$':
        return pass_string_unpack(left) == pass_string_unpack(right)
    else:
        left, right = pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).equals(fp.unpack(right))
        else:
            return integer_to_int_signed(left) == integer_to_int_signed(right)

def _bool_gt(left, right):
    """ Ordering: return -1 if left > right, 0 otherwise. """
    if left[0] == '$':
        return string_gt(left, right)
    else:
        left, right = pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right))
        else:
            return integer_to_int_signed(left) > integer_to_int_signed(right)

def equals(left, right):
    """ Return -1 if left == right, 0 otherwise. """
    return bool_to_integer(_bool_eq(left, right))

def not_equals(left, right):
    """ Return -1 if left != right, 0 otherwise. """
    return bool_to_integer(not _bool_eq(left, right))

def gt(left, right):
    """ Ordering: return -1 if left > right, 0 otherwise. """
    return bool_to_integer(_bool_gt(left, right))

def gte(left, right):
    """ Ordering: return -1 if left >= right, 0 otherwise. """
    return bool_to_integer(_bool_gt(left, right) or _bool_eq(left, right))

def lte(left, right):
    """ Ordering: return -1 if left <= right, 0 otherwise. """
    return bool_to_integer(not _bool_gt(left, right))

def lt(left, right):
    """ Ordering: return -1 if left < right, 0 otherwise. """
    return bool_to_integer(not _bool_gt(left, right) and not _bool_eq(left, right))

def plus(left, right):
    """ + operator: add or concatenate. """
    if left[0] == '$':
        return string_concat(left, right)
    else:
        return number_add(left, right)


prepare()
