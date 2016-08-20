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

    def __init__(self, values, string_space):
        """Initialise context."""
        self.strings = string_space
        self._values = values
        self._init_operators()

    def _init_operators(self):
        """Initialise operators."""
        # unary operators
        self.unary = {
            tk.O_MINUS: self._values.negate,
            tk.O_PLUS: lambda x: x,
            tk.NOT: self._values.bitwise_not,
        }
        # binary operators
        self.binary = {
            tk.O_CARET: self._values.power,
            tk.O_TIMES: self._values.multiply,
            tk.O_DIV: self._values.divide,
            tk.O_INTDIV: self._values.divide_int,
            tk.MOD: self._values.mod,
            tk.O_PLUS: self.plus,
            tk.O_MINUS: self._values.subtract,
            tk.O_GT: self.gt,
            tk.O_EQ: self.equals,
            tk.O_LT: self.lt,
            tk.O_GT + tk.O_EQ: self.gte,
            tk.O_EQ + tk.O_GT: self.gte,
            tk.O_LT + tk.O_EQ: self.lte,
            tk.O_EQ + tk.O_LT: self.lte,
            tk.O_LT + tk.O_GT: self.not_equals,
            tk.O_GT + tk.O_LT: self.not_equals,
            tk.AND: self._values.bitwise_and,
            tk.OR: self._values.bitwise_or,
            tk.XOR: self._values.bitwise_xor,
            tk.EQV: self._values.bitwise_eqv,
            tk.IMP: self._values.bitwise_imp,
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
            left, right = self._values.pass_most_precise(left, right)
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
            left, right = self._values.pass_most_precise(left, right)
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
            return self._values.add(left, right)
