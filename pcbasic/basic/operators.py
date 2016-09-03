"""
PC-BASIC - operators.py
Numeric and string operators

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

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

    def __init__(self, values):
        """Initialise context."""
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
            tk.O_DIV: values.div,
            tk.O_INTDIV: self._values.divide_int,
            tk.MOD: self._values.mod,
            tk.O_PLUS: self._values.add,
            tk.O_MINUS: self._values.subtract,
            tk.O_GT: self._values.gt,
            tk.O_EQ: self._values.equals,
            tk.O_LT: self._values.lt,
            tk.O_GT + tk.O_EQ: self._values.gte,
            tk.O_EQ + tk.O_GT: self._values.gte,
            tk.O_LT + tk.O_EQ: self._values.lte,
            tk.O_EQ + tk.O_LT: self._values.lte,
            tk.O_LT + tk.O_GT: self._values.not_equals,
            tk.O_GT + tk.O_LT: self._values.not_equals,
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
