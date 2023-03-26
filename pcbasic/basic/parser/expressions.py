"""
PC-BASIC - expressions.py
Expression stack

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
from functools import partial
import logging
import struct
import types

from ..base import tokens as tk
from ..base.tokens import DIGITS, LETTERS
from ..base import error
from .. import values
from .. import dos
from . import operators as op
from . import userfunctions


class ExpressionParser(object):
    """Expression parser."""

    def __init__(self, values, memory):
        """Initialise empty expression."""
        self._values = values
        # for variable retrieval
        self._memory = memory
        # user-defined functions
        self.user_functions = userfunctions.UserFunctionManager(memory, values, self)
        # initialise syntax tables
        self._init_syntax()
        # callbacks must be initilised later
        self._callbacks = {}
        self._extensions = {}

    def _init_syntax(self):
        """Initialise function syntax tables."""
        self._complex = {
            tk.USR: {
                None: self._gen_parse_arguments,
                tk.C_0: self._gen_parse_arguments,
                tk.C_1: self._gen_parse_arguments,
                tk.C_2: self._gen_parse_arguments,
                tk.C_3: self._gen_parse_arguments,
                tk.C_4: self._gen_parse_arguments,
                tk.C_5: self._gen_parse_arguments,
                tk.C_6: self._gen_parse_arguments,
                tk.C_7: self._gen_parse_arguments,
                tk.C_8: self._gen_parse_arguments,
                tk.C_9: self._gen_parse_arguments,
            },
            tk.IOCTL: {
                b'$': self._gen_parse_ioctl,
            },
            tk.ENVIRON: {
                b'$': self._gen_parse_arguments,
            },
            tk.INPUT: {
                b'$': self._gen_parse_input,
            },
            tk.ERDEV: {
                b'$': self._no_argument,
                None: self._no_argument,
            },
            tk.VARPTR: {
                b'$': self._gen_parse_varptr_str,
                None: self._gen_parse_varptr,
            },
        }
        self._simple = {
            tk.ERL: self._no_argument,
            tk.ERR: self._no_argument,
            tk.CSRLIN: self._no_argument,
            tk.INKEY: self._no_argument,
            tk.DATE: self._no_argument,
            tk.TIME: self._no_argument,
            tk.TIMER: self._no_argument,
            tk.RND: self._gen_parse_one_optional_argument,
            tk.CVI: self._gen_parse_arguments,
            tk.CVS: self._gen_parse_arguments,
            tk.CVD: self._gen_parse_arguments,
            tk.MKI: self._gen_parse_arguments,
            tk.MKS: self._gen_parse_arguments,
            tk.MKD: self._gen_parse_arguments,
            tk.SGN: self._gen_parse_arguments,
            tk.INT: self._gen_parse_arguments,
            tk.FIX: self._gen_parse_arguments,
            tk.ABS: self._gen_parse_arguments,
            tk.SQR: self._gen_parse_arguments,
            tk.SIN: self._gen_parse_arguments,
            tk.LOG: self._gen_parse_arguments,
            tk.EXP: self._gen_parse_arguments,
            tk.COS: self._gen_parse_arguments,
            tk.TAN: self._gen_parse_arguments,
            tk.ATN: self._gen_parse_arguments,
            tk.PEEK: self._gen_parse_arguments,
            tk.FRE: self._gen_parse_arguments,
            tk.INP: self._gen_parse_arguments,
            tk.POS: self._gen_parse_arguments,
            tk.CINT: self._gen_parse_arguments,
            tk.CSNG: self._gen_parse_arguments,
            tk.CDBL: self._gen_parse_arguments,
            tk.LEN: self._gen_parse_arguments,
            tk.STR: self._gen_parse_arguments,
            tk.VAL: self._gen_parse_arguments,
            tk.ASC: self._gen_parse_arguments,
            tk.CHR: self._gen_parse_arguments,
            tk.SPACE: self._gen_parse_arguments,
            tk.OCT: self._gen_parse_arguments,
            tk.HEX: self._gen_parse_arguments,
            tk.PEN: self._gen_parse_arguments,
            tk.STICK: self._gen_parse_arguments,
            tk.STRIG: self._gen_parse_arguments,
            tk.EOF: self._gen_parse_arguments,
            tk.LOC: self._gen_parse_arguments,
            tk.LOF: self._gen_parse_arguments,
            tk.LPOS: self._gen_parse_arguments,
            tk.EXTERR: self._gen_parse_arguments,
            tk.PLAY: self._gen_parse_arguments,
            tk.STRING: partial(self._gen_parse_arguments, length=2),
            tk.PMAP: partial(self._gen_parse_arguments, length=2),
            tk.LEFT: partial(self._gen_parse_arguments, length=2),
            tk.RIGHT: partial(self._gen_parse_arguments, length=2),
            tk.POINT: partial(self._gen_parse_arguments_optional, length=2),
            tk.MID: partial(self._gen_parse_arguments_optional, length=3),
            tk.SCREEN: partial(self._gen_parse_arguments_optional, length=3),
            tk.INSTR: self._gen_parse_instr,
            tk.FN: None,
            b'_': self._gen_parse_call_extension,
        }
        self._functions = set(self._complex.keys()) | set(self._simple.keys())

    def init_functions(self, session):
        """Initialise function callbacks."""
        self._callbacks = {
            tk.USR: session.machine.usr_,
            tk.USR + tk.C_0: session.machine.usr_,
            tk.USR + tk.C_1: session.machine.usr_,
            tk.USR + tk.C_2: session.machine.usr_,
            tk.USR + tk.C_3: session.machine.usr_,
            tk.USR + tk.C_4: session.machine.usr_,
            tk.USR + tk.C_5: session.machine.usr_,
            tk.USR + tk.C_6: session.machine.usr_,
            tk.USR + tk.C_7: session.machine.usr_,
            tk.USR + tk.C_8: session.machine.usr_,
            tk.USR + tk.C_9: session.machine.usr_,
            tk.IOCTL + b'$': session.files.ioctl_,
            tk.ENVIRON + b'$': session.environment.environ_,
            tk.INPUT + b'$': session.files.input_,
            tk.ERDEV: session.files.erdev_,
            tk.ERDEV + b'$': session.files.erdev_str_,
            tk.VARPTR: session.memory.varptr_,
            tk.VARPTR + b'$': session.memory.varptr_str_,
            tk.SCREEN: session.text_screen.screen_fn_,
            tk.FN: None,
            tk.ERL: session.interpreter.erl_,
            tk.ERR: session.interpreter.err_,
            tk.STRING: values.string_,
            tk.INSTR: values.instr_,
            tk.CSRLIN: session.text_screen.csrlin_,
            tk.POINT: session.graphics.point_,
            tk.INKEY: session.keyboard.inkey_,
            tk.CVI: values.cvi_,
            tk.CVS: values.cvs_,
            tk.CVD: values.cvd_,
            tk.MKI: values.mki_,
            tk.MKS: values.mks_,
            tk.MKD: values.mkd_,
            tk.EXTERR: session.files.exterr_,
            tk.DATE: session.clock.date_fn_,
            tk.TIME: session.clock.time_fn_,
            tk.PLAY: session.sound.play_fn_,
            tk.TIMER: session.clock.timer_,
            tk.PMAP: session.graphics.pmap_,
            tk.LEFT: values.left_,
            tk.RIGHT: values.right_,
            tk.MID: values.mid_,
            tk.SGN: values.sgn_,
            tk.INT: values.int_,
            tk.ABS: values.abs_,
            tk.SQR: values.sqr_,
            tk.RND: session.randomiser.rnd_,
            tk.SIN: values.sin_,
            tk.LOG: values.log_,
            tk.EXP: values.exp_,
            tk.COS: values.cos_,
            tk.TAN: values.tan_,
            tk.ATN: values.atn_,
            tk.FRE: session.memory.fre_,
            tk.INP: session.machine.inp_,
            tk.POS: session.text_screen.pos_,
            tk.LEN: values.len_,
            tk.STR: values.str_,
            tk.VAL: values.val_,
            tk.ASC: values.asc_,
            tk.CHR: values.chr_,
            tk.PEEK: session.all_memory.peek_,
            tk.SPACE: values.space_,
            tk.OCT: values.oct_,
            tk.HEX: values.hex_,
            tk.LPOS: session.files.lpos_,
            tk.CINT: values.cint_,
            tk.CSNG: values.csng_,
            tk.CDBL: values.cdbl_,
            tk.FIX: values.fix_,
            tk.PEN: session.pen_fn_,
            tk.STICK: session.stick.stick_,
            tk.STRIG: session.stick.strig_,
            tk.EOF: session.files.eof_,
            tk.LOC: session.files.loc_,
            tk.LOF: session.files.lof_,
            b'_': session.extensions.call_as_function,
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # functools.partial objects and functions can't be pickled
        pickle_dict['_simple'] = None
        pickle_dict['_complex'] = None
        pickle_dict['_callbacks'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_syntax()

    def parse_expression(self, ins):
        """Parse and evaluate tokenised expression."""
        self._memory.strings.reset_temporaries()
        return self.parse(ins)

    def parse(self, ins):
        """Parse and evaluate tokenised (sub-)expression."""
        operations = deque()
        with self._memory.get_stack() as units:
            final = True
            # see https://en.wikipedia.org/wiki/Shunting-yard_algorithm
            d = b''
            while True:
                last = d
                ins.skip_blank()
                d = ins.read_keyword_token()
                ins.seek(-len(d), 1)
                if d == tk.NOT and not (last in op.OPERATORS or last == b''):
                    # unary NOT ends expression except after another operator or at start
                    break
                elif d in op.OPERATORS:
                    ins.read(len(d))
                    # get combined operators such as >=
                    if d in op.COMBINABLE:
                        nxt = ins.skip_blank()
                        if nxt in op.COMBINABLE:
                            d += ins.read(len(nxt))
                    if last in op.OPERATORS or last == b'' or d == tk.NOT:
                        # also if last is ( but that leads to recursive call and last == ''
                        nargs = 1
                        # zero operands for a binary operator is always syntax error
                        # because it will be seen as an illegal unary
                        try:
                            oper = op.UNARY[d]
                            prec = op.PRECEDENCE[(d, nargs)]
                        except KeyError:
                            raise error.BASICError(error.STX)
                    else:
                        nargs = 2
                        try:
                            oper = op.BINARY[d]
                            prec = op.PRECEDENCE[(d, nargs)]
                        except KeyError:
                            # illegal combined ops like == raise syntax error here
                            raise error.BASICError(error.STX)
                        self._drain(prec, operations, units)
                    operations.append((oper, nargs, prec))
                elif not (last in op.OPERATORS or last == b''):
                    # repeated unit ends expression
                    # repeated literals or variables or non-keywords like 'AS'
                    break
                elif d == b'(':
                    ins.read(len(d))
                    # we need to create a new object or we'll overwrite our own stacks
                    # this will not be needed if we localise stacks in the expression parser
                    # either a separate class of just as local variables
                    units.append(self.parse(ins))
                    ins.require_read((b')',))
                elif d and d in LETTERS:
                    name = ins.read_name()
                    error.throw_if(not name, error.STX)
                    indices = self.parse_indices(ins)
                    view = self._memory.view_or_create_variable(name, indices)
                    # should make a shallow copy? but .clone here breaks circular MID$
                    units.append(view)
                elif d in self._functions:
                    units.append(self._parse_function(ins, d))
                    #if not isinstance(units[-1], values.String):
                    #    self._memory.strings.reset_temporaries()
                elif d in tk.END_STATEMENT:
                    break
                elif d in tk.END_EXPRESSION:
                    # missing operand inside brackets or before comma is syntax error
                    final = False
                    break
                elif d == b'"':
                    units.append(self.read_string_literal(ins))
                else:
                    units.append(self.read_number_literal(ins))
            # raises IndexError for insufficient operators
            try:
                self._drain(0, operations, units)
                return units[0]
            except IndexError:
                # empty expression is a syntax error (inside brackets)
                # or Missing Operand (in an assignment)
                if final:
                    raise error.BASICError(error.MISSING_OPERAND)
                raise error.BASICError(error.STX)

    def _drain(self, precedence, operations, units):
        """Drain evaluation stack until an operator of low precedence on top."""
        while operations:
            # this raises IndexError if there are not enough operators
            if precedence > operations[-1][2]:
                break
            oper, narity, _ = operations.pop()
            args = reversed([units.pop() for _ in range(narity)])
            units.append(oper(*args))

    def read_string_literal(self, ins):
        """Read a quoted string literal (no leading blanks), return as String."""
        # address points to initial quote
        address = ins.tell_address()
        value = ins.read_string().strip(b'"')
        # if this is a program, create a string pointer to code space
        # and don't reserve space in string memory
        # +1 to point to start of payload, not intial quote
        return self._values.from_str_at(value, None if address is None else address + 1)

    def read_number_literal(self, ins):
        """Return the value of a numeric literal (no leading blanks)."""
        d = ins.peek()
        # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
        # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
        if d in DIGITS:
            return self._values.from_repr(ins.read_number(), allow_nonnum=False)
        # number literals
        elif d in tk.NUMBER:
            return self._values.from_token(ins.read_number_token())
        elif d == tk.T_UINT:
            # gw-basic allows adding line numbers to numbers
            # drop 0E token, interpret payload to unsigned integer
            value = struct.unpack('<bH', ins.read(3))[1]
            # we need to convert to single to ensure it is interpreted as the unsigned value
            return self._values.new_single().from_int(value)
        else:
            raise error.BASICError(error.STX)

    def parse_indices(self, ins):
        """Parse array indices."""
        indices = []
        if ins.skip_blank_read_if((b'[', b'(')):
            # it's an array, read indices
            while True:
                expr = self.parse(ins)
                indices.append(values.to_int(expr))
                if not ins.skip_blank_read_if((b',',)):
                    break
            ins.require_read((b']', b')'))
        return indices

    ###########################################################################
    # function and argument handling

    def _parse_function(self, ins, token):
        """Parse a function starting with the given token."""
        ins.read(len(token))
        if token in self._simple:
            # apply functions
            parse_args = self._simple[token]
        else:
            fndict = self._complex[token]
            presign = ins.skip_blank_read_if(fndict)
            if presign:
                token += presign
            try:
                parse_args = fndict[presign]
            except KeyError:
                raise error.BASICError(error.STX)
        if token == tk.FN:
            fnname = ins.read_name()
            # must not be empty
            error.throw_if(not fnname, error.STX)
            # obtain function
            function = self.user_functions.get(fnname)
            # get syntax
            parse_args = partial(self._gen_parse_arguments, length=function.number_arguments())
            fn = function.evaluate
        else:
            fn = self._callbacks[token]
        return fn(parse_args(ins))

    ###########################################################################
    # argument generators

    def _no_argument(self, ins):
        """No arguments to parse."""
        return
        yield # pragma: no cover

    def _gen_parse_arguments(self, ins, length=1):
        """Parse a comma-separated list of arguments."""
        if not length:
            return
        ins.require_read((b'(',))
        for i in range(length-1):
            yield self.parse(ins)
            ins.require_read((b',',))
        yield self.parse(ins)
        ins.require_read((b')',))

    def _gen_parse_arguments_optional(self, ins, length):
        """Parse a comma-separated list of arguments, last one optional."""
        ins.require_read((b'(',))
        yield self.parse(ins)
        for _ in range(length-2):
            ins.require_read((b',',))
            yield self.parse(ins)
        if ins.skip_blank_read_if((b',',)):
            yield self.parse(ins)
        else:
            yield None
        ins.require_read((b')',))

    def _gen_parse_one_optional_argument(self, ins):
        """Parse a single, optional argument."""
        if ins.skip_blank_read_if((b'(',)):
            yield self.parse(ins)
            ins.require_read((b')',))
        else:
            yield None

    def _gen_parse_call_extension(self, ins):
        """Parse an extension function."""
        yield ins.read_name()
        if ins.skip_blank_read_if((b'(',)):
            while True:
                yield self.parse(ins)
                if not ins.skip_blank_read_if((b',',)):
                    break
            ins.require_read((b')',))
        else:
            yield None

    ###########################################################################
    # special cases

    def _gen_parse_ioctl(self, ins):
        """Parse IOCTL$ syntax."""
        ins.require_read((b'(',))
        ins.skip_blank_read_if((b'#',))
        yield self.parse(ins)
        ins.require_read((b')',))

    def _gen_parse_instr(self, ins):
        """Parse INSTR syntax."""
        ins.require_read((b'(',))
        # followed by comma so empty will raise STX
        s = self.parse(ins)
        yield s
        if isinstance(s, values.Number):
            ins.require_read((b',',))
            yield self.parse(ins)
        ins.require_read((b',',))
        yield self.parse(ins)
        ins.require_read((b')',))

    def _gen_parse_input(self, ins):
        """Parse INPUT$ syntax."""
        ins.require_read((b'(',))
        yield self.parse(ins)
        if ins.skip_blank_read_if((b',',)):
            ins.skip_blank_read_if((b'#',))
            yield self.parse(ins)
        else:
            yield None
        ins.require_read((b')',))

    def _gen_parse_varptr_str(self, ins):
        """Parse VARPTR$ syntax."""
        ins.require_read((b'(',))
        yield ins.read_name()
        yield self.parse_indices(ins)
        ins.require_read((b')',))

    def _gen_parse_varptr(self, ins):
        """Parse VARPTR syntax."""
        ins.require_read((b'(',))
        if ins.skip_blank_read_if((b'#',)):
            yield self.parse(ins)
        else:
            yield ins.read_name()
            yield self.parse_indices(ins)
        ins.require_read((b')',))
