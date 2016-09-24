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
from . import userfunctions



# AIMS
# complete the implementation of action callbacks (get var, pointer, file)
# remove the session member
#       implement callbacks for RND

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

    def __init__(self, values, memory, program, files):
        """Initialise empty expression."""
        self._values = values
        # for variable retrieval
        self._memory = memory
        # for code strings
        self._program = program
        # for file number checks
        self._files = files
        # user-defined functions
        self.user_functions = userfunctions.UserFunctionManager(memory, values, self)
        # initialise syntax tables
        self._init_syntax()
        # callbacks must be initilised later
        self._callbacks = {}

    def _init_syntax(self):
        """Initialise function syntax tables."""
        self._with_presign = {
            tk.USR: {
                None: (1, values.SNG),
                tk.C_0: (1, values.SNG),
                tk.C_1: (1, values.SNG),
                tk.C_2: (1, values.SNG),
                tk.C_3: (1, values.SNG),
                tk.C_4: (1, values.SNG),
                tk.C_5: (1, values.SNG),
                tk.C_6: (1, values.SNG),
                tk.C_7: (1, values.SNG),
                tk.C_8: (1, values.SNG),
                tk.C_9: (1, values.SNG),
            },
            tk.IOCTL: {
                '$': (self._parse_ioctl, None),
            },
            tk.ENVIRON: {
                '$': (1, values.STR),
            },
            tk.INPUT: {
                '$': (self._parse_input, values.STR),
            },
            tk.ERDEV: {
                '$': (1, values.STR),
                None: (1, values.INT),
            },
            tk.VARPTR: {
                '$': (self._parse_varptr_str, values.STR),
                None: (self._parse_varptr, values.INT),
            },
        }
        self._bare = {
            tk.SCREEN: (3, None, (values.cint_, values.cint_, values.cint_), True),
            tk.FN: (None, None),
            tk.ERL: (0, values.SNG),
            tk.ERR: (0, values.INT),
            tk.STRING: (self._parse_string, None),
            tk.INSTR: (self._parse_instr, None),
            tk.CSRLIN: (0, values.INT),
            tk.POINT: (2, None, (values.cint_, values.cint_), True),
            tk.INKEY: (0, values.STR),
            tk.CVI: (1, None),
            tk.CVS: (1, None),
            tk.CVD: (1, None),
            tk.MKI: (1, None),
            tk.MKS: (1, None),
            tk.MKD: (1, None),
            tk.EXTERR: (1, values.INT),
            tk.DATE: (0, values.STR),
            tk.TIME: (0, values.STR),
            tk.PLAY: (1, values.INT),
            tk.TIMER: (0, values.SNG),
            tk.PMAP: (2, None, (values.cint_, values.cint_), False),
            tk.LEFT: (2, None, (values.pass_string, values.cint_), False),
            tk.RIGHT: (2, None, (values.pass_string, values.cint_), False),
            tk.MID: (3, None, (values.pass_string, values.cint_, values.cint_), True),
            tk.SGN: (1, None),
            tk.INT: (1, None),
            tk.ABS: (1, None),
            tk.SQR: (1, None),
            tk.RND: (self._parse_rnd, None),
            tk.SIN: (1, None),
            tk.LOG: (1, None),
            tk.EXP: (1, None),
            tk.COS: (1, None),
            tk.TAN: (1, None),
            tk.ATN: (1, None),
            tk.FRE: (1, values.SNG),
            tk.INP: (1, values.INT),
            tk.POS: (1, values.INT),
            tk.LEN: (1, None),
            tk.STR: (1, None),
            tk.VAL: (1, None),
            tk.ASC: (1, None),
            tk.CHR: (1, None),
            tk.PEEK: (1, values.INT),
            tk.SPACE: (1, None),
            tk.OCT: (1, None),
            tk.HEX: (1, None),
            tk.LPOS: (1, values.INT),
            tk.CINT: (1, None),
            tk.CSNG: (1, None),
            tk.CDBL: (1, None),
            tk.FIX: (1, None),
            tk.PEN: (1, values.INT),
            tk.STICK: (1, values.INT),
            tk.STRIG: (1, values.INT),
            tk.EOF: (1, values.INT),
            tk.LOC: (1, values.SNG),
            tk.LOF: (1, values.SNG),
        }
        self._functions = set(self._with_presign.keys() + self._bare.keys())

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
            tk.IOCTL + '$': session.files.ioctl_,
            tk.ENVIRON + '$': dos.environ_,
            tk.INPUT + '$': session.files.input_,
            tk.ERDEV: session.devices.erdev_,
            tk.ERDEV + '$': session.devices.erdev_str_,
            tk.VARPTR: session.memory.varptr_,
            tk.VARPTR + '$': session.memory.varptr_str_,
            tk.SCREEN: session.screen.screen_fn_,
            tk.FN: None,
            tk.ERL: session.parser.erl_,
            tk.ERR: session.parser.err_,
            tk.STRING: values.string_,
            tk.INSTR: values.instr_,
            tk.CSRLIN: session.screen.csrlin_,
            tk.POINT: session.screen.point_,
            tk.INKEY: session.keyboard.get_char,
            tk.CVI: values.cvi_,
            tk.CVS: values.cvs_,
            tk.CVD: values.cvd_,
            tk.MKI: values.mki_,
            tk.MKS: values.mks_,
            tk.MKD: values.mkd_,
            tk.EXTERR: session.devices.exterr_,
            tk.DATE: session.clock.date_fn_,
            tk.TIME: session.clock.time_fn_,
            tk.PLAY: session.sound.play_fn_,
            tk.TIMER: session.clock.timer_,
            tk.PMAP: session.screen.pmap_,
            tk.LEFT: values.left_,
            tk.RIGHT: values.right_,
            tk.MID: values.mid_,
            tk.SGN: values.sgn_,
            tk.INT: values.int_,
            tk.ABS: values.abs_,
            tk.SQR: values.sqr_,
            tk.RND: session.randomiser.rnd,
            tk.SIN: values.sin_,
            tk.LOG: values.log_,
            tk.EXP: values.exp_,
            tk.COS: values.cos_,
            tk.TAN: values.tan_,
            tk.ATN: values.atn_,
            tk.FRE: session.memory.fre_,
            tk.INP: session.machine.inp_,
            tk.POS: session.screen.pos_,
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
            tk.PEN: session.events.pen.pen_,
            tk.STICK: session.stick.stick_,
            tk.STRIG: session.stick.strig_,
            tk.EOF: session.files.eof_,
            tk.LOC: session.files.loc_,
            tk.LOF: session.files.lof_,
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # functools.partial objects and functions can't be pickled
        pickle_dict['_bare'] = None
        pickle_dict['_with_presign'] = None
        pickle_dict['_callbacks'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_syntax()

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
                units.append(self._parse_function(ins, d))
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
    # function and argument handling

    def _parse_function(self, ins, token):
        """Parse a function starting with the given token."""
        ins.read(len(token))
        if token in self._bare:
            # apply functions
            fn_record = self._bare[token]
        else:
            fndict = self._with_presign[token]
            presign = ins.skip_blank_read_if(fndict)
            if presign:
                token += presign
            try:
                fn_record = fndict[presign]
            except KeyError:
                raise error.RunError(error.STX)
        narity, to_type = fn_record[:2]
        fn = self._callbacks[token]
        if narity == 0:
            args = ()
        elif narity == 1:
            args = self._parse_argument(ins)
        elif narity in (2, 3):
            conv, optional = fn_record[2:]
            args = self._parse_argument_list(ins, conv, optional)
        elif token == tk.FN:
            fn, conv = self._parse_fn(ins)
            args = self._parse_argument_list(ins, conv, optional=False)
        else:
            # special cases
            args = narity(ins)
        result = fn(*args)
        if to_type:
            return self._values.from_value(result, to_type)
        return result

    def _parse_argument(self, ins):
        """Parse a single function argument."""
        ins.require_read(('(',))
        val = self.parse(ins)
        ins.require_read((')',))
        return (val,)

    def _parse_argument_list(self, ins, conversions, optional=False):
        """Parse a comma-separated list of arguments and apply type conversions."""
        # these functions generate type mismatch and overflow errors *before* parsing the closing parenthesis
        # while unary functions generate it *afterwards*. this is to match GW-BASIC
        if not conversions:
            return ()
        arg = []
        # required separators
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

    def _parse_file_number(self, ins):
        """Read a file number."""
        ins.skip_blank_read_if(('#',))
        number = values.to_int(self.parse(ins))
        error.range_check(0, 255, number)
        return number

    ###########################################################
    # special cases

    def _parse_fn(self, ins):
        """FN: get value of user-defined function."""
        fnname = ins.read_name()
        # must not be empty
        error.throw_if(not fnname, error.STX)
        # obtain function
        fn = self.user_functions.get(fnname)
        # read variables
        conversions = fn.get_conversions()
        return fn.evaluate, conversions

    def _parse_varptr_str(self, ins):
        """VARPTR$: get memory address for variable."""
        ins.require_read(('(',))
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        indices = self.parse_indices(ins)
        ins.require_read((')',))
        return (name, indices)

    def _parse_varptr(self, ins):
        """VARPTR: get memory address for variable or FCB."""
        ins.require_read(('(',))
        if ins.skip_blank() == '#':
            # params holds a number
            params = self._parse_file_number(ins)
            error.throw_if(params > self._files.max_files, error.BAD_FILE_NUMBER)
        else:
            # params holds a tuple
            name = ins.read_name()
            error.throw_if(not name, error.STX)
            indices = self.parse_indices(ins)
            params = name, indices
        ins.require_read((')',))
        return (params,)

    def _parse_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        ins.require_read(('(',))
        num = self._parse_file_number(ins)
        # raise BAD FILE NUMBER if the file is not open
        infile = self._files.get(num)
        ins.require_read((')',))
        return (infile,)

    def _parse_input(self, ins):
        """INPUT$: get characters from the keyboard or a file."""
        ins.require_read(('(',))
        num = values.to_int(self.parse(ins))
        error.range_check(1, 255, num)
        infile = None
        if ins.skip_blank_read_if((',',)):
            num = self._parse_file_number(ins)
            # raise BAD FILE MODE (not BAD FILE NUMBER) if the file is not open
            infile = self._files.get(num, mode='IR', not_open=error.BAD_FILE_MODE)
        ins.require_read((')',))
        return (infile, num)

    def _parse_instr(self, ins):
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
        return (start, big, small)

    def _parse_string(self, ins):
        """STRING$: repeat characters."""
        ins.require_read(('(',))
        n = values.to_int(self.parse(ins))
        error.range_check(0, 255, n)
        ins.require_read((',',))
        asc_value_or_char = self.parse(ins)
        if isinstance(asc_value_or_char, values.Integer):
            error.range_check(0, 255, asc_value_or_char.to_int())
        ins.require_read((')',))
        return (asc_value_or_char, n)

    def _parse_rnd(self, ins):
        """RND: get pseudorandom value."""
        if ins.skip_blank_read_if(('(',)):
            val = self.parse(ins)
            ins.require_read((')',))
            return (values.csng_(val),)
        else:
            return ()
