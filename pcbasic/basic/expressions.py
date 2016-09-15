"""
PC-BASIC - expressions.py
Expression stack

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
from functools import partial
import logging
import string
import struct

from . import operators as op
from . import tokens as tk
from . import error
from . import values
from . import dos



# AIMS
# separate expression parsing from statement parsing (done)
# complete the implementation of action callbacks (get var, pointer, file)
# remove Functions class and/or combine with UserFunctions
# perhaps Functions (holding callbacks and user function state) should become ExpressionParser/ExpressionManager

# separate parsing from evaluation (ExpressionParser creates Expression, which can then evaluate)
# difficulty: reproduce sequence of errors (syntax checks during evaluation)
# approach: build an evaluation tree with operation and value nodes
#   def OperationNode.evaluate(self):
#       args = (arg.evaluate() for arg in self._args)
#       return self._oper(*args)
#
# in the code below, this could be implemented by replacing evaluate steps
# operation[token](*args) --> OperationNode(token, args)
# adding the OperationNodes to the unit stack as we currently do values
# when popped off the stack, they end up in the tree (through the argument list)
# but are not yet evaluated.


class ExpressionParser(object):
    """Expression parser."""

    def __init__(self, values, memory, program):
        """Initialise empty expression."""
        self._values = values
        # for variable retrieval
        self._memory = memory
        # for code strings
        self._program = program

    def init_functions(self, session):
        """Initialise functions."""
        self.session = session
        self._with_presign = {
            tk.USR: {
                None: (1, session.machine.usr_, values.SNG),
                tk.C_0: (1, session.machine.usr_, values.SNG),
                tk.C_1: (1, session.machine.usr_, values.SNG),
                tk.C_2: (1, session.machine.usr_, values.SNG),
                tk.C_3: (1, session.machine.usr_, values.SNG),
                tk.C_4: (1, session.machine.usr_, values.SNG),
                tk.C_5: (1, session.machine.usr_, values.SNG),
                tk.C_6: (1, session.machine.usr_, values.SNG),
                tk.C_7: (1, session.machine.usr_, values.SNG),
                tk.C_8: (1, session.machine.usr_, values.SNG),
                tk.C_9: (1, session.machine.usr_, values.SNG),
            },
            tk.IOCTL: {
                '$': (None, self.value_ioctl, None),
            },
            tk.ENVIRON: {
                '$': (1, dos.environ_, values.STR),
            },
            tk.INPUT: {
                '$': (None, self.value_input, None),
            },
            tk.ERDEV: {
                '$': (1, session.devices.erdev_str_, values.STR),
                None: (1, session.devices.erdev_, values.INT),
            },
            tk.VARPTR: {
                '$': (None, self.value_varptr_str, None),
                None: (None, self.value_varptr, None),
            },
        }
        self._bare = {
            tk.SCREEN: (3, session.screen.screen_fn_, None, (values.cint_, values.cint_, values.cint_), True),
            tk.FN: (None, self.value_fn, None),
            tk.ERL: (0, session.parser.erl_, values.SNG),
            tk.ERR: (0, session.parser.err_, values.INT),
            tk.STRING: (None, self.value_string, None),
            tk.INSTR: (None, self.value_instr, None),
            tk.CSRLIN: (0, session.screen.csrlin_, values.INT),
            tk.POINT: (2, session.screen.point_, None, (values.cint_, values.cint_), True),
            tk.INKEY: (0, session.keyboard.get_char, values.STR),
            tk.CVI: (1, values.cvi_, None),
            tk.CVS: (1, values.cvs_, None),
            tk.CVD: (1, values.cvd_, None),
            tk.MKI: (1, values.mki_, None),
            tk.MKS: (1, values.mks_, None),
            tk.MKD: (1, values.mkd_, None),
            tk.EXTERR: (1, session.devices.exterr_, values.INT),
            tk.DATE: (0, session.clock.date_fn_, values.STR),
            tk.TIME: (0, session.clock.time_fn_, values.STR),
            tk.PLAY: (1, session.sound.play_fn_, values.INT),
            tk.TIMER: (0, session.clock.timer_, values.SNG),
            tk.PMAP: (2, session.screen.pmap_, (values.cint_, values.cint_), False),
            tk.LEFT: (2, values.left_, None, (values.pass_string, values.cint_), False),
            tk.RIGHT: (2, values.right_, None, (values.pass_string, values.cint_), False),
            tk.MID: (3, values.mid_, None, (values.pass_string, values.cint_, values.cint_), True),
            tk.SGN: (1, values.sgn_, None),
            tk.INT: (1, values.int_, None),
            tk.ABS: (1, values.abs_, None),
            tk.SQR: (1, values.sqr_, None),
            tk.RND: (None, self.value_rnd, None),
            tk.SIN: (1, values.sin_, None),
            tk.LOG: (1, values.log_, None),
            tk.EXP: (1, values.exp_, None),
            tk.COS: (1, values.cos_, None),
            tk.TAN: (1, values.tan_, None),
            tk.ATN: (1, values.atn_, None),
            tk.FRE: (1, session.memory.fre_, values.SNG),
            tk.INP: (1, session.machine.inp_, values.INT),
            tk.POS: (1, session.screen.pos_, values.INT),
            tk.LEN: (1, values.len_, None),
            tk.STR: (1, values.str_, None),
            tk.VAL: (1, values.val_, None),
            tk.ASC: (1, values.asc_, None),
            tk.CHR: (1, values.chr_, None),
            tk.PEEK: (1, session.all_memory.peek_, values.INT),
            tk.SPACE: (1, values.space_, None),
            tk.OCT: (1, values.oct_, None),
            tk.HEX: (1, values.hex_, None),
            tk.LPOS: (1, session.files.lpos_, values.INT),
            tk.CINT: (1, values.cint_, None),
            tk.CSNG: (1, values.csng_, None),
            tk.CDBL: (1, values.cdbl_, None),
            tk.FIX: (1, values.fix_, None),
            tk.PEN: (1, session.events.pen.pen_, values.INT),
            tk.STICK: (1, session.stick.stick_, values.INT),
            tk.STRIG: (1, session.stick.strig_, values.INT),
            tk.EOF: (1, session.files.eof_, values.INT),
            tk.LOC: (1, session.files.loc_, values.SNG),
            tk.LOF: (1, session.files.lof_, values.SNG),
        }
        self._functions = set(self._with_presign.keys() + self._bare.keys())

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # functools.partial objects and functions can't be pickled
        pickle_dict['_bare'] = None
        pickle_dict['_with_presign'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)


    def parse(self, ins):
        """Parse and evaluate tokenised expression."""
        stack = deque()
        units = deque()
        final = True
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
                        self._drain(prec, stack, units)
                    except (KeyError, IndexError):
                        # illegal combined ops like == raise syntax error
                        # incomplete expression also raises syntax error
                        raise error.RunError(error.STX)
                stack.append((oper, nargs, prec))
            elif not (last in op.OPERATORS or last == ''):
                # repeated unit ends expression
                # repeated literals or variables or non-keywords like 'AS'
                break
            elif d == '(':
                ins.read(len(d))
                # we need to create a new object or we'll overwrite our own stacks
                # this will not be needed if we localise stacks in the expression parser
                # either a separate class of just as local variables
                units.append(self.parse(ins))
                ins.require_read((')',))
            elif d and d in string.ascii_letters:
                name = ins.read_name()
                error.throw_if(not name, error.STX)
                indices = self.parse_indices(ins)
                units.append(self._memory.get_variable(name, indices))
            elif d in self._functions:
                units.append(self.parse_function(ins, d))
            elif d in tk.END_STATEMENT:
                break
            elif d in tk.END_EXPRESSION:
                # missing operand inside brackets or before comma is syntax error
                final = False
                break
            elif d == '"':
                units.append(self.read_string_literal(ins))
            else:
                units.append(self.read_number_literal(ins))
        # raises IndexError for insufficient operators
        try:
            self._drain(0, stack, units)
            return units[0]
        except IndexError:
            # empty expression is a syntax error (inside brackets)
            # or Missing Operand (in an assignment)
            if final:
                raise error.RunError(error.MISSING_OPERAND)
            raise error.RunError(error.STX)

    def _drain(self, precedence, stack, units):
        """Drain evaluation stack until an operator of low precedence on top."""
        while stack:
            # this raises IndexError if there are not enough operators
            if precedence > stack[-1][2]:
                break
            oper, narity, _ = stack.pop()
            args = reversed([units.pop() for _ in range(narity)])
            units.append(oper(*args))

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
                expr = self.parse(ins)
                indices.append(values.to_int(expr))
                if not ins.skip_blank_read_if((',',)):
                    break
            ins.require_read((']', ')'))
        return indices

    ###########################################################
    # function handling

    def parse_function(self, ins, token):
        """Parse a function starting with the given token."""
        ins.read(len(token))
        if token in self._bare:
            # apply functions
            fn_record = self._bare[token]
        else:
            fndict = self._with_presign[token]
            presign = ins.skip_blank_read_if(fndict)
            try:
                fn_record = fndict[presign]
            except KeyError:
                raise error.RunError(error.STX)
        narity, fn, to_type = fn_record[:3]
        if narity == 0:
            return self._values.from_value(fn(), to_type)
        elif narity == 1:
            ins.require_read(('(',))
            val = self.parse(ins)
            ins.require_read((')',))
            if to_type:
                return self._values.from_value(fn(val), to_type)
            else:
                return fn(val)
        elif narity > 1:
            conv, optional = fn_record[3:]
            # these functions generate type mismatch and overflow errors *before* parsing the closing parenthesis
            # while unary functions generate it *afterwards*. this is to match GW-BASIC
            return fn(*self.parse_argument_list(ins, conv, optional))
        else:
            # special cases
            return fn(ins)

    def parse_argument_list(self, ins, conversions, optional=False):
        """Parse a comma-separated list of arguments and apply type conversions."""
        # required separators
        arg = []
        seps = (('(',),) + ((',',),) * (len(conversions)-1)
        for conv, sep in zip(conversions[:-1], seps[:-1]):
            ins.require_read(sep)
            arg.append(conv(self.parse(ins)))
        if ins.skip_blank_read_if(seps[-1]):
            arg.append(conversions[-1](self.parse(ins)))
        elif not optional:
            raise error.RunError(error.STX)
        if arg:
            ins.require_read((')',))
        return arg

    ###########################################################
    # special cases

    def value_fn(self, ins):
        """FN: get value of user-defined function."""
        fnname = ins.read_name()
        # must not be empty
        error.throw_if(not fnname, error.STX)
        # obtain function
        fn = self.session.user_functions.get(fnname)
        # read variables
        conversions = fn.get_conversions()
        if conversions:
            args = self.parse_argument_list(ins, conversions, optional=False)
        else:
            args = ()
        return fn.evaluate(self, *args)

    def value_varptr(self, ins):
        """VARPTR: get memory address for variable or FCB."""
        ins.require_read(('(',))
        if ins.skip_blank_read_if(('#',)):
            # params holds a number
            params = values.to_int(self.parse(ins))
            error.range_check(0, 255, params)
        else:
            # params holds a tuple
            name = ins.read_name()
            error.throw_if(not name, error.STX)
            # this is an evaluation-time determination
            # as we could have passed another DEFtype statement
            name = self.session.memory.complete_name(name)
            indices = self.parse_indices(ins)
            params = name, indices
        ins.require_read((')',))
        var_ptr = self.session.memory.varptr_(params)
        return self._values.from_value(var_ptr, values.INT)

    def value_varptr_str(self, ins):
        """VARPTR$: get memory address for variable."""
        ins.require_read(('(',))
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        # this is an evaluation-time determination
        # as we could have passed another DEFtype statement
        name = self.session.memory.complete_name(name)
        indices = self.parse_indices(ins)
        ins.require_read((')',))
        var_ptr_str = self.session.memory.varptr_str_(name, indices)
        return self._values.from_value(var_ptr_str, values.STR)

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        ins.require_read(('(',))
        ins.skip_blank_read_if(('#',))
        num = values.to_int(self.parse(ins))
        error.range_check(0, 255, num)
        ins.require_read((')',))
        return self.session.files.ioctl_(num)

    def value_instr(self, ins):
        """INSTR: find substring in string."""
        ins.require_read(('(',))
        # followed by comma so empty will raise STX
        s = self.parse(ins)
        start = 1
        if isinstance(s, values.Number):
            start = values.to_int(s)
            error.range_check(1, 255, start)
            ins.require_read((',',))
            s = self.parse(ins)
        big = values.pass_string(s)
        ins.require_read((',',))
        s = self.parse(ins)
        small = values.pass_string(s)
        ins.require_read((')',))
        return values.instr_(start, big, small)

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if ins.skip_blank_read_if(('(',)):
            val = self.parse(ins)
            ins.require_read((')',))
            return self.session.randomiser.rnd(values.csng_(val))
        else:
            return self.session.randomiser.rnd()

    def value_string(self, ins):
        """STRING$: repeat characters."""
        ins.require_read(('(',))
        n = values.to_int(self.parse(ins))
        error.range_check(0, 255, n)
        ins.require_read((',',))
        asc_value_or_char = self.parse(ins)
        if isinstance(asc_value_or_char, values.Integer):
            error.range_check(0, 255, asc_value_or_char.to_int())
        ins.require_read((')',))
        return values.string_(asc_value_or_char, n)

    def value_input(self, ins):
        """INPUT$: get characters from the keyboard or a file."""
        ins.require_read(('(',))
        num = values.to_int(self.parse(ins))
        error.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if ins.skip_blank_read_if((',',)):
            ins.skip_blank_read_if(('#',))
            num = values.to_int(self.parse(ins))
            error.range_check(0, 255, num)
            infile = self.session.files.get(num)
        ins.require_read((')',))
        word = infile.input_(num)
        return self._values.from_value(word, values.STR)
