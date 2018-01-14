"""
PC-BASIC - operators.py
Numeric and string operators

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import tokens as tk
from .. import values


# operators and precedence
# key is tuple (token, nargs)
PRECEDENCE = {
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
OPERATORS = set(PRECEDENCE)

# can be combined like <> >=
COMBINABLE = (tk.O_LT, tk.O_EQ, tk.O_GT)

# unary operators
UNARY = {
    tk.O_MINUS: values.neg,
    tk.O_PLUS: lambda x: x,
    tk.NOT: values.not_,
}

# binary operators
BINARY = {
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
