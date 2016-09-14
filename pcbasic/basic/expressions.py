"""
PC-BASIC - expressions.py
Expression stack

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
import string
import struct

from . import operators as op
from . import tokens as tk
from . import error
from . import values


# AIMS
# separate expression parsing from statement parsing (done)
# separate parsing from evaluation (ExpressionParser creates Expression, which can then evaluate)
# difficulty: reproduce sequence of errors (syntax checks during evaluation)
# complete the implementation of action callbacks (get var, pointer, file)
# remove Functions class and/or combine with UserFunctions
# perhaps Functions (holding callbacks and user function state) should become ExpressionParser/ExpressionManager


class Expression(object):
    """Expression stack."""

    def __init__(self, values, memory, program, functions):
        """Initialise empty expression."""
        self._values = values
        # for variable retrieval
        self._memory = memory
        # for code strings
        self._program = program
        # for action callbacks
        self._functions = functions

    def new(self):
        """Create new expression object."""
        return Expression(self._values, self._memory, self._program, self._functions)

    def parse(self, ins):
        """Build stacks from tokenised expression."""
        self._stack = deque()
        self._units = deque()
        self._final = True
        # see https://en.wikipedia.org/wiki/Shunting-yard_algorithm
        d = ''
        while True:
            last = d
            ins.skip_blank()
            d = ins.read_keyword_token()
            ins.seek(-len(d), 1)
            if d == tk.NOT and not (last in op.OPERATORS or last == ''):
                # unary NOT ends expression except after another operator or at start
                break
            elif d in op.OPERATORS:
                ins.read(len(d))
                prec = op.PRECEDENCE[d]
                # get combined operators such as >=
                if d in op.COMBINABLE:
                    nxt = ins.skip_blank()
                    if nxt in op.COMBINABLE:
                        d += ins.read(len(nxt))
                if last in op.OPERATORS or last == '' or d == tk.NOT:
                    # also if last is ( but that leads to recursive call and last == ''
                    nargs = 1
                    # zero operands for a binary operator is always syntax error
                    # because it will be seen as an illegal unary
                    try:
                        oper = op.UNARY[d]
                    except KeyError:
                        raise error.RunError(error.STX)
                else:
                    nargs = 2
                    try:
                        oper = op.BINARY[d]
                        self._drain(prec)
                    except (KeyError, IndexError):
                        # illegal combined ops like == raise syntax error
                        # incomplete expression also raises syntax error
                        raise error.RunError(error.STX)
                self._stack.append((oper, nargs, prec))
            elif not (last in op.OPERATORS or last == ''):
                # repeated unit ends expression
                # repeated literals or variables or non-keywords like 'AS'
                break
            elif d == '(':
                ins.read(len(d))
                # we need to create a new object or we'll overwrite our own stacks
                # this will not be needed if we localise stacks in the expression parser
                # either a separate class of just as local variables
                expr = self.new().parse(ins)
                self._units.append(expr.evaluate())
                ins.require_read((')',))
            elif d and d in string.ascii_letters:
                name = ins.read_name()
                error.throw_if(not name, error.STX)
                indices = self.parse_indices(ins)
                self._units.append(self._memory.get_variable(name, indices))
            elif d in self._functions:
                self._units.append(self._functions.parse_function(ins, d))
            elif d in tk.END_STATEMENT:
                break
            elif d in tk.END_EXPRESSION:
                # missing operand inside brackets or before comma is syntax error
                self._final = False
                break
            elif d == '"':
                self._units.append(self.read_string_literal(ins))
            else:
                self._units.append(self.read_number_literal(ins))
        return self

    def _drain(self, precedence):
        """Drain evaluation stack until an operator of low precedence on top."""
        while self._stack:
            # this raises IndexError if there are not enough operators
            if precedence > self._stack[-1][2]:
                break
            oper, narity, _ = self._stack.pop()
            args = reversed([self._units.pop() for _ in range(narity)])
            self._units.append(oper(*args))

    def evaluate(self):
        """Evaluate expression and return result."""
        # raises IndexError for insufficient operators
        try:
            self._drain(0)
            return self._units[0]
        except IndexError:
            # empty expression is a syntax error (inside brackets)
            # or Missing Operand (in an assignment)
            if self._final:
                raise error.RunError(error.MISSING_OPERAND)
            raise error.RunError(error.STX)


    def read_string_literal(self, ins):
        """Read a quoted string literal (no leading blanks), return as String."""
        # record the address of the first byte of the string's payload
        if ins == self._program.bytecode:
            address = ins.tell() + 1 + self._memory.code_start
        else:
            address = None
        value = ins.read_string().strip('"')
        # if this is a program, create a string pointer to code space
        # don't reserve space in string memory
        return self._values.from_str_at(value, address)

    def read_number_literal(self, ins):
        """Return the value of a numeric literal (no leading blanks)."""
        d = ins.peek()
        # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
        # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
        if d in string.digits:
            return self._values.from_repr(ins.read_number(), allow_nonnum=False)
        # number literals
        elif d in tk.NUMBER:
            return self._values.from_token(ins.read_number_token())
        elif d == tk.T_UINT:
            # gw-basic allows adding line numbers to numbers
            # convert to signed integer
            value = struct.unpack('<h', ins.read(2))[0]
            return self._values.new_integer().from_int(value)
        else:
            raise error.RunError(error.STX)

    def parse_indices(self, ins):
        """Parse array indices."""
        indices = []
        if ins.skip_blank_read_if(('[', '(')):
            # it's an array, read indices
            while True:
                # new Expression object, see above
                expr = self.new().parse(ins)
                indices.append(values.to_int(expr.evaluate()))
                if not ins.skip_blank_read_if((',',)):
                    break
            ins.require_read((']', ')'))
        return indices
