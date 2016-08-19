"""
PC-BASIC - operators.py
Numeric and string operators

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from . import fp
from . import values
from . import basictoken as tk


# operators and precedence
# key is tuple (token, nargs)
precedence = {
    tk.O_CARET: 12,
    tk.O_TIMES: 11,
    tk.O_DIV: 11,
    tk.O_INTDIV: 10,
    tk.MOD: 9,
    tk.O_PLUS: 8,
    tk.O_MINUS: 8,
    tk.O_GT: 7,
    tk.O_EQ: 7,
    tk.O_LT: 7,
    tk.O_GT + tk.O_EQ: 7,
    tk.O_EQ + tk.O_GT: 7,
    tk.O_LT + tk.O_EQ: 7,
    tk.O_EQ + tk.O_LT: 7,
    tk.O_LT + tk.O_GT: 7,
    tk.O_GT + tk.O_LT: 7,
    tk.NOT: 6,
    tk.AND: 5,
    tk.OR: 4,
    tk.XOR: 3,
    tk.EQV: 2,
    tk.IMP: 1,
}
operators = set(precedence)

# can be combined like <> >=
combinable = (tk.O_LT, tk.O_EQ, tk.O_GT)


class Operators(object):
    """Context for numeric and string operations."""

    def __init__(self, values, string_space, double_math):
        """Initialise context."""
        self.strings = string_space
        self.values = values
        # double-precision power operator
        self.double_math = double_math
        self._init_operators()

    def _init_operators(self):
        """Initialise operators."""
        # unary operators
        self.unary = {
            tk.O_MINUS: self.neg,
            tk.O_PLUS: lambda x: x,
            tk.NOT: self.number_not,
        }
        # binary operators
        self.binary = {
            tk.O_CARET: self.number_power,
            tk.O_TIMES: self.number_multiply,
            tk.O_DIV: self.number_divide,
            tk.O_INTDIV: self.number_intdiv,
            tk.MOD: self.number_modulo,
            tk.O_PLUS: self.plus,
            tk.O_MINUS: self.number_subtract,
            tk.O_GT: self.gt,
            tk.O_EQ: self.equals,
            tk.O_LT: self.lt,
            tk.O_GT + tk.O_EQ: self.gte,
            tk.O_EQ + tk.O_GT: self.gte,
            tk.O_LT + tk.O_EQ: self.lte,
            tk.O_EQ + tk.O_LT: self.lte,
            tk.O_LT + tk.O_GT: self.not_equals,
            tk.O_GT + tk.O_LT: self.not_equals,
            tk.AND: self.number_and,
            tk.OR: self.number_or,
            tk.XOR: self.number_xor,
            tk.EQV: self.number_eqv,
            tk.IMP: self.number_imp,
        }


    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['unary'] = None
        pickle_dict['binary'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_operators()



    ###############################################################################
    # numeric operations

    def number_add(self, left, right):
        """Add two numbers."""
        left, right = self.values.pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
        else:
            # return Single to avoid wrapping on integer overflow
            return fp.pack(fp.Single.from_int(values.integer_to_int_signed(left) +
                                values.integer_to_int_signed(right)))

    def number_subtract(self, left, right):
        """Subtract two numbers."""
        return self.number_add(left, self.number_neg(right))

    @staticmethod
    def number_sgn(inp):
        """Return the sign of a number."""
        if inp[0] == '%':
            i = values.integer_to_int_signed(inp)
            if i > 0:
                return values.int_to_integer_signed(1)
            elif i < 0:
                return values.int_to_integer_signed(-1)
            else:
                return values.int_to_integer_signed(0)
        elif inp[0] in ('!', '#'):
            return values.int_to_integer_signed(fp.unpack(inp).sign())
        return inp

    @staticmethod
    def number_abs(inp):
        """Return the absolute value of a number."""
        if inp[0] == '%':
            val = abs(values.integer_to_int_signed(inp))
            if val == 32768:
                return fp.pack(fp.Single.from_int(val))
            else:
                return values.int_to_integer_signed(val)
        elif inp[0] in ('!', '#'):
            out = (inp[0], inp[1][:])
            out[1][-2] &= 0x7F
            return out
        return inp

    @staticmethod
    def number_neg(inp):
        """Return the negation of a number."""
        inp = values.pass_number(inp)
        if inp[0] == '%':
            val = -values.integer_to_int_signed(inp)
            if val == 32768:
                return fp.pack(fp.Single.from_int(val))
            else:
                return values.int_to_integer_signed(val)
        elif inp[0] in ('!', '#'):
            out = (inp[0], inp[1][:])
            out[1][-2] ^= 0x80
            return out
        # pass strings on, let error happen somewhere else.
        return inp

    def number_power(self, left, right):
        """Left^right."""
        if (left[0] == '#' or right[0] == '#') and self.double_math:
            return self.values.power(self.values.pass_double(left), self.values.pass_double(right))
        else:
            if right[0] == '%':
                return fp.pack( fp.unpack(self.values.pass_single(left)).ipow_int(values.integer_to_int_signed(right)) )
            else:
                return self.values.power(self.values.pass_single(left), self.values.pass_single(right))

    def number_multiply(self, left, right):
        """Left*right."""
        if left[0] == '#' or right[0] == '#':
            return fp.pack( fp.unpack(self.values.pass_double(left)).imul(fp.unpack(self.values.pass_double(right))) )
        else:
            return fp.pack( fp.unpack(self.values.pass_single(left)).imul(fp.unpack(self.values.pass_single(right))) )

    def number_divide(self, left, right):
        """Left/right."""
        if left[0] == '#' or right[0] == '#':
            return fp.pack( fp.div(fp.unpack(self.values.pass_double(left)), fp.unpack(self.values.pass_double(right))) )
        else:
            return fp.pack( fp.div(fp.unpack(self.values.pass_single(left)), fp.unpack(self.values.pass_single(right))) )

    @staticmethod
    def number_intdiv(left, right):
        """Left\\right."""
        dividend = values.pass_int_unpack(left)
        divisor = values.pass_int_unpack(right)
        if divisor == 0:
            # division by zero, return single-precision maximum
            raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
        if (dividend >= 0) == (divisor >= 0):
            return values.int_to_integer_signed(dividend / divisor)
        else:
            return values.int_to_integer_signed(-(abs(dividend) / abs(divisor)))

    @staticmethod
    def number_modulo(left, right):
        """Left MOD right."""
        divisor = values.pass_int_unpack(right)
        dividend = values.pass_int_unpack(left)
        if divisor == 0:
            # division by zero, return single-precision maximum
            raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
        mod = dividend % divisor
        if dividend < 0 or mod < 0:
            mod -= divisor
        return values.int_to_integer_signed(mod)

    @staticmethod
    def number_not(right):
        """Bitwise NOT, -x-1."""
        return values.int_to_integer_signed(-values.pass_int_unpack(right)-1)

    @staticmethod
    def number_and(left, right):
        """Bitwise AND."""
        return values.int_to_integer_unsigned(
            values.integer_to_int_unsigned(values.pass_integer(left)) &
            values.integer_to_int_unsigned(values.pass_integer(right)))

    @staticmethod
    def number_or(left, right):
        """Bitwise OR."""
        return values.int_to_integer_unsigned(
            values.integer_to_int_unsigned(values.pass_integer(left)) |
            values.integer_to_int_unsigned(values.pass_integer(right)))

    @staticmethod
    def number_xor(left, right):
        """Bitwise XOR."""
        return values.int_to_integer_unsigned(
            values.integer_to_int_unsigned(values.pass_integer(left)) ^
            values.integer_to_int_unsigned(values.pass_integer(right)))

    @staticmethod
    def number_eqv(left, right):
        """Bitwise equivalence."""
        return values.int_to_integer_unsigned(0xffff-(
            values.integer_to_int_unsigned(values.pass_integer(left)) ^
            values.integer_to_int_unsigned(values.pass_integer(right))))

    @staticmethod
    def number_imp(left, right):
        """Bitwise implication."""
        return values.int_to_integer_unsigned(
            (0xffff-values.integer_to_int_unsigned(values.pass_integer(left))) |
            values.integer_to_int_unsigned(values.pass_integer(right)))


    ###############################################################################
    # string operations

    def string_concat(self, left, right):
        """Concatenate strings."""
        return self.strings.store(
            self.strings.copy(values.pass_string(left)) +
            self.strings.copy(values.pass_string(right)))


    ###############################################################################
    # number and string operations

    def _bool_eq(self, left, right):
        """Return true if left == right, false otherwise."""
        if left[0] == '$':
            return (self.strings.copy(values.pass_string(left)) ==
                    self.strings.copy(values.pass_string(right)))
        else:
            left, right = self.values.pass_most_precise(left, right)
            if left[0] in ('#', '!'):
                return fp.unpack(left).equals(fp.unpack(right))
            else:
                return values.integer_to_int_signed(left) == values.integer_to_int_signed(right)

    def _bool_gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        if left[0] == '$':
            left = self.strings.copy(values.pass_string(left))
            right = self.strings.copy(values.pass_string(right))
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
            left, right = self.values.pass_most_precise(left, right)
            if left[0] in ('#', '!'):
                return fp.unpack(left).gt(fp.unpack(right))
            else:
                return values.integer_to_int_signed(left) > values.integer_to_int_signed(right)

    def equals(self, left, right):
        """Return -1 if left == right, 0 otherwise."""
        return values.bool_to_integer(self._bool_eq(left, right))

    def not_equals(self, left, right):
        """Return -1 if left != right, 0 otherwise."""
        return values.bool_to_integer(not self._bool_eq(left, right))

    def gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        return values.bool_to_integer(self._bool_gt(left, right))

    def gte(self, left, right):
        """Ordering: return -1 if left >= right, 0 otherwise."""
        return values.bool_to_integer(not self._bool_gt(right, left))

    def lte(self, left, right):
        """Ordering: return -1 if left <= right, 0 otherwise."""
        return values.bool_to_integer(not self._bool_gt(left, right))

    def lt(self, left, right):
        """Ordering: return -1 if left < right, 0 otherwise."""
        return values.bool_to_integer(self._bool_gt(right, left))

    def plus(self, left, right):
        """Binary + operator: add or concatenate."""
        if left[0] == '$':
            return self.string_concat(left, right)
        else:
            return self.number_add(left, right)

    @staticmethod
    def neg(right):
        """Unary - operator: negate or no-op for strings."""
        if right[0] == '$':
            return right
        else:
            return Operators.number_neg(right)
