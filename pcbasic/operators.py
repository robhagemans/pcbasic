"""
PC-BASIC - operators.py
Numeric and string operators

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import state
import fp
import vartypes
import var



###############################################################################
# numeric operations

def number_add(left, right):
    """ Add two numbers. """
    left, right = vartypes.pass_most_precise(left, right)
    if left[0] in ('#', '!'):
        return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
    else:
        # return Single to avoid wrapping on integer overflow
        return fp.pack(fp.Single.from_int(vartypes.integer_to_int_signed(left) +
                            vartypes.integer_to_int_signed(right)))

def number_subtract(left, right):
    """ Subtract two numbers. """
    return number_add(left, number_neg(right))

def number_sgn(inp):
    """ Return the sign of a number. """
    if inp[0] == '%':
        i = vartypes.integer_to_int_signed(inp)
        if i > 0:
            return vartypes.int_to_integer_signed(1)
        elif i < 0:
            return vartypes.int_to_integer_signed(-1)
        else:
            return vartypes.int_to_integer_signed(0)
    elif inp[0] in ('!', '#'):
        return vartypes.int_to_integer_signed(fp.unpack(inp).sign())
    return inp

def number_abs(inp):
    """ Return the absolute value of a number. """
    if inp[0] == '%':
        val = abs(vartypes.integer_to_int_signed(inp))
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return vartypes.int_to_integer_signed(val)
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:])
        out[1][-2] &= 0x7F
        return out
    return inp

def number_neg(inp):
    """ Return the negation of a number. """
    inp = vartypes.pass_number(inp)
    if inp[0] == '%':
        val = -vartypes.integer_to_int_signed(inp)
        if val == 32768:
            return fp.pack(fp.Single.from_int(val))
        else:
            return vartypes.int_to_integer_signed(val)
    elif inp[0] in ('!', '#'):
        out = (inp[0], inp[1][:])
        out[1][-2] ^= 0x80
        return out
    # pass strings on, let error happen somewhere else.
    return inp


def number_power(left, right):
    """ Left^right. """
    if (left[0] == '#' or right[0] == '#') and vartypes.option_double:
        return fp.pack( fp.power(fp.unpack(vartypes.pass_double(left)), fp.unpack(vartypes.pass_double(right))) )
    else:
        if right[0] == '%':
            return fp.pack( fp.unpack(vartypes.pass_single(left)).ipow_int(vartypes.integer_to_int_signed(right)) )
        else:
            return fp.pack( fp.power(fp.unpack(vartypes.pass_single(left)), fp.unpack(vartypes.pass_single(right))) )

def number_multiply(left, right):
    """ Left*right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.unpack(vartypes.pass_double(left)).imul(fp.unpack(vartypes.pass_double(right))) )
    else:
        return fp.pack( fp.unpack(vartypes.pass_single(left)).imul(fp.unpack(vartypes.pass_single(right))) )

def number_divide(left, right):
    """ Left/right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(vartypes.pass_double(left)), fp.unpack(vartypes.pass_double(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(vartypes.pass_single(left)), fp.unpack(vartypes.pass_single(right))) )

def number_intdiv(left, right):
    """ Left\\right. """
    dividend = vartypes.pass_int_unpack(left)
    divisor = vartypes.pass_int_unpack(right)
    if divisor == 0:
        # division by zero, return single-precision maximum
        raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
    if (dividend >= 0) == (divisor >= 0):
        return vartypes.int_to_integer_signed(dividend / divisor)
    else:
        return vartypes.int_to_integer_signed(-(abs(dividend) / abs(divisor)))

def number_modulo(left, right):
    """ Left MOD right. """
    divisor = vartypes.pass_int_unpack(right)
    dividend = vartypes.pass_int_unpack(left)
    if divisor == 0:
        # division by zero, return single-precision maximum
        raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
    mod = dividend % divisor
    if dividend < 0 or mod < 0:
        mod -= divisor
    return vartypes.int_to_integer_signed(mod)

def number_not(right):
    """ Bitwise NOT, -x-1. """
    return vartypes.int_to_integer_signed(-vartypes.pass_int_unpack(right)-1)

def number_and(left, right):
    """ Bitwise AND. """
    return vartypes.int_to_integer_unsigned(
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(left)) &
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(right)))

def number_or(left, right):
    """ Bitwise OR. """
    return vartypes.int_to_integer_unsigned(
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(left)) |
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(right)))

def number_xor(left, right):
    """ Bitwise XOR. """
    return vartypes.int_to_integer_unsigned(
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(left)) ^
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(right)))

def number_eqv(left, right):
    """ Bitwise equivalence. """
    return vartypes.int_to_integer_unsigned(0xffff-(
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(left)) ^
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(right))))

def number_imp(left, right):
    """ Bitwise implication. """
    return vartypes.int_to_integer_unsigned(
        (0xffff-vartypes.integer_to_int_unsigned(vartypes.pass_integer(left))) |
        vartypes.integer_to_int_unsigned(vartypes.pass_integer(right)))


###############################################################################
# string operations

def string_concat(left, right):
    """ Concatenate strings. """
    return state.basic_state.strings.store(var.copy_str(vartypes.pass_string(left)) + var.copy_str(vartypes.pass_string(right)))


###############################################################################
# number and string operations

def _bool_eq(left, right):
    """ Return true if left == right, false otherwise. """
    if left[0] == '$':
        return var.copy_str(vartypes.pass_string(left)) == var.copy_str(vartypes.pass_string(right))
    else:
        left, right = vartypes.pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).equals(fp.unpack(right))
        else:
            return vartypes.integer_to_int_signed(left) == vartypes.integer_to_int_signed(right)

def _bool_gt(left, right):
    """ Ordering: return -1 if left > right, 0 otherwise. """
    if left[0] == '$':
        left, right = var.copy_str(vartypes.pass_string(left)), var.copy_str(vartypes.pass_string(right))
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
    else:
        left, right = vartypes.pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.unpack(left).gt(fp.unpack(right))
        else:
            return vartypes.integer_to_int_signed(left) > vartypes.integer_to_int_signed(right)

def equals(left, right):
    """ Return -1 if left == right, 0 otherwise. """
    return vartypes.bool_to_integer(_bool_eq(left, right))

def not_equals(left, right):
    """ Return -1 if left != right, 0 otherwise. """
    return vartypes.bool_to_integer(not _bool_eq(left, right))

def gt(left, right):
    """ Ordering: return -1 if left > right, 0 otherwise. """
    return vartypes.bool_to_integer(_bool_gt(left, right))

def gte(left, right):
    """ Ordering: return -1 if left >= right, 0 otherwise. """
    return vartypes.bool_to_integer(not _bool_gt(right, left))

def lte(left, right):
    """ Ordering: return -1 if left <= right, 0 otherwise. """
    return vartypes.bool_to_integer(not _bool_gt(left, right))

def lt(left, right):
    """ Ordering: return -1 if left < right, 0 otherwise. """
    return vartypes.bool_to_integer(_bool_gt(right, left))

def plus(left, right):
    """ Binary + operator: add or concatenate. """
    if left[0] == '$':
        return string_concat(left, right)
    else:
        return number_add(left, right)

def neg(right):
    """ Unary - operator: negate or no-op for strings. """
    if right[0] == '$':
        return right
    else:
        return number_neg(right)
