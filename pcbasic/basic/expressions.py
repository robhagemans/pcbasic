"""
PC-BASIC - expressions.py
Expression stack

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
import string

from . import operators as op
from . import tokens as tk
from . import error


class Expression(object):
    """Expression stack."""

    def __init__(self, ins, parser, memory, functions):
        """Initialise empty expression."""
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
                self.push_operator(oper, nargs, prec)
            elif not (last in op.OPERATORS or last == ''):
                # repeated unit ends expression
                # repeated literals or variables or non-keywords like 'AS'
                break
            elif d == '(':
                ins.read(len(d))
                expr = Expression(ins, parser, memory, functions)
                self.push_value(expr.evaluate())
                ins.require_read((')',))
            elif d and d in string.ascii_letters:
                # variable name
                name, indices = parser.parse_variable(ins)
                self.push_value(memory.get_variable(name, indices))
            elif d in functions:
                self.push_value(functions.parse_function(ins, d))
            elif d in tk.END_STATEMENT:
                break
            elif d in tk.END_EXPRESSION:
                # missing operand inside brackets or before comma is syntax error
                self._final = False
                break
            elif d == '"':
                self.push_value(parser.read_string_literal(ins))
            else:
                self.push_value(parser.read_number_literal(ins))

    def push_value(self, value):
        """Push a value onto the unit stack."""
        self._units.append(value)

    def push_operator(self, operator, nargs, precedence):
        """Push an operator onto the stack."""
        self._stack.append((operator, nargs, precedence))

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
