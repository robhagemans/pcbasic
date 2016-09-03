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
            tk.O_MINUS: values.neg,
            tk.O_PLUS: lambda x: x,
            tk.NOT: values.not_,
        }
        # binary operators
        self.binary = {
            tk.O_CARET: values.pow,
            tk.O_TIMES: values.mul,
            tk.O_DIV: values.div,
            tk.O_INTDIV: values.intdiv,
            tk.MOD: values.mod_,
            tk.O_PLUS: values.add,
            tk.O_MINUS: values.sub,
            tk.O_GT: values.gt,
            tk.O_EQ: values.eq,
            tk.O_LT: values.lt,
            tk.O_GT + tk.O_EQ: values.gte,
            tk.O_EQ + tk.O_GT: values.gte,
            tk.O_LT + tk.O_EQ: values.lte,
            tk.O_EQ + tk.O_LT: values.lte,
            tk.O_LT + tk.O_GT: values.neq,
            tk.O_GT + tk.O_LT: values.neq,
            tk.AND: values.and_,
            tk.OR: values.or_,
            tk.XOR: values.xor_,
            tk.EQV: values.eqv_,
            tk.IMP: values.imp_,
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
