"""
PC-BASIC - expressions.py
Expression parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from functools import partial
import logging
import string
from collections import deque

import config
import fp
import vartypes
import representation
import shell
import util
import error
import var
import devices
import state
import machine
import basictoken as tk
import memory
import operators as op
# math error output
import console

# can be combined like <> >=
combinable = (tk.O_LT, tk.O_EQ, tk.O_GT)


def parse_expression(ins, session, allow_empty=False):
    """ Compute the value of the expression at a given code pointer. """
    return Evaluator(ins, session).evaluate(allow_empty)

def parse_bracket(ins, session):
    """ Compute the value of the bracketed expression. """
    util.require_read(ins, ('(',))
    # we'll get a Syntax error, not a Missing operand, if we close with )
    val = parse_expression(ins, session)
    util.require_read(ins, (')',))
    return val

def parse_literal(ins, session):
    """ Compute the value of the literal at the current code pointer. """
    d = util.skip_white(ins)
    # string literal
    if d == '"':
        ins.read(1)
        if ins == session.program.bytecode:
            address = ins.tell() + session.memory.code_start
        else:
            address = None
        output = bytearray()
        # while tokenised numbers inside a string literal will be printed as tokenised numbers, they don't actually execute as such:
        # a \00 character, even if inside a tokenised number, will break a string literal (and make the parser expect a
        # line number afterwards, etc. We follow this.
        d = ins.read(1)
        while d not in tk.end_line + ('"',):
            output += d
            d = ins.read(1)
        if d == '\0':
            ins.seek(-1, 1)
        # store for easy retrieval, but don't reserve space in string memory
        return session.strings.store(output, address)
    # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
    # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
    elif d in string.digits:
        outs = StringIO()
        representation.tokenise_number(ins, outs)
        outs.seek(0)
        return representation.parse_value(outs)
    # number literals
    elif d in tk.number:
        return representation.parse_value(ins)
    # gw-basic allows adding line numbers to numbers
    elif d == tk.T_UINT:
        return vartypes.int_to_integer_unsigned(util.parse_jumpnum(ins))
    else:
        raise error.RunError(error.STX)

def parse_variable(ins, session):
    """ Helper function: parse a variable or array element. """
    name = util.parse_scalar(ins)
    indices = []
    if util.skip_white_read_if(ins, ('[', '(')):
        # it's an array, read indices
        while True:
            indices.append(vartypes.pass_int_unpack(parse_expression(ins, session)))
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require_read(ins, (']', ')'))
    return name, indices


######################################################################
# expression parsing utility functions


def parse_file_number(ins, session, file_mode='IOAR'):
    """ Helper function: parse a file number and retrieve the file object. """
    screen = None
    if util.skip_white_read_if(ins, ('#',)):
        number = vartypes.pass_int_unpack(parse_expression(ins, session))
        util.range_check(0, 255, number)
        screen = devices.get_file(number, file_mode)
        util.require_read(ins, (',',))
    return screen

def parse_file_number_opthash(ins, session):
    """ Helper function: parse a file number, with optional hash. """
    util.skip_white_read_if(ins, ('#',))
    number = vartypes.pass_int_unpack(parse_expression(ins, session))
    util.range_check(0, 255, number)
    return number



class Evaluator(object):
    """ Expression parser. """

    def __init__(self, codestream, session, user_fn_parsing=None):
        """ Initialise evaluator. """
        self.ins = codestream
        self.session = session
        self.operators = op.Operators(session.strings)
        # state variable for detecting recursion
        if user_fn_parsing:
            self.user_function_parsing = user_fn_parsing
        else:
            self.user_function_parsing = set()

    def evaluate(self, allow_empty=False):
        """ Compute the value of the expression at the current code pointer. """
        stack = deque()
        units = deque()
        d = ''
        missing_error = error.MISSING_OPERAND
        # see https://en.wikipedia.org/wiki/Shunting-yard_algorithm
        while True:
            last = d
            d = util.skip_white(self.ins)
            # two-byte function tokens
            if d in tk.twobyte:
                d = util.peek(self.ins, n=2)
            if d == tk.NOT and not (last in op.operators or last == ''):
                # unary NOT ends expression except after another operator or at start
                break
            elif d in op.operators:
                self.ins.read(len(d))
                # get combined operators such as >=
                if d in combinable:
                    nxt = util.skip_white(self.ins)
                    if nxt in combinable:
                        d += self.ins.read(len(nxt))
                if last in op.operators or last == '' or d == tk.NOT:
                    # also if last is ( but that leads to recursive call and last == ''
                    nargs = 1
                    # zero operands for a binary operator is always syntax error
                    # because it will be seen as an illegal unary
                    if d not in self.operators.unary:
                        raise error.RunError(error.STX)
                else:
                    nargs = 2
                    self._evaluate_stack(stack, units, op.precedence[d], error.STX)
                stack.append((d, nargs))
            elif not (last in op.operators or last == ''):
                # repeated unit ends expression
                # repeated literals or variables or non-keywords like 'AS'
                break
            elif d == '(':
                units.append(parse_bracket(self.ins, self.session))
            elif d and d in string.ascii_letters:
                # variable name
                name, indices = parse_variable(self.ins, self.session)
                units.append(self.session.memory.get_variable(name, indices))
            elif d in self.functions:
                # apply functions
                self.ins.read(len(d))
                try:
                    units.append(self.functions[d](self))
                except (ValueError, ArithmeticError) as e:
                    units.append(self._handle_math_error(e))
            elif d in tk.end_statement:
                break
            elif d in tk.end_expression or d in tk.keyword:
                # missing operand inside brackets or before comma is syntax error
                missing_error = error.STX
                break
            else:
                # literal
                units.append(parse_literal(self.ins, self.session))
        # empty expression is a syntax error (inside brackets)
        # or Missing Operand (in an assignment)
        # or not an error (in print and many functions)
        if units or stack:
            self._evaluate_stack(stack, units, 0, missing_error)
            return units[0]
        elif allow_empty:
            return None
        else:
            raise error.RunError(missing_error)

    def _evaluate_stack(self, stack, units, precedence, missing_err):
        """ Drain evaluation stack until an operator of low precedence on top. """
        while stack:
            if precedence > op.precedence[stack[-1][0]]:
                break
            oper, narity = stack.pop()
            try:
                right = units.pop()
                if narity == 1:
                    units.append(self.operators.unary[oper](right))
                else:
                    left = units.pop()
                    units.append(self.operators.binary[oper](left, right))
            except IndexError:
                # insufficient operators, error depends on context
                raise error.RunError(missing_err)
            except (ValueError, ArithmeticError) as e:
                units.append(self._handle_math_error(e))

    def _handle_math_error(self, e):
        """ Handle Overflow or Division by Zero. """
        if isinstance(e, ValueError):
            # math domain errors such as SQR(-1)
            raise error.RunError(error.IFC)
        elif isinstance(e, OverflowError):
            math_error = error.OVERFLOW
        elif isinstance(e, ZeroDivisionError):
            math_error = error.DIVISION_BY_ZERO
        else:
            raise e
        if self.session.parser.on_error:
            # also raises exception in error_handle_mode!
            # in that case, prints a normal error message
            raise error.RunError(math_error)
        else:
            # write a message & continue as normal
            console.write_line(error.RunError(math_error).message)
        # return max value for the appropriate float type
        if e.args and e.args[0] and isinstance(e.args[0], fp.Float):
            return fp.pack(e.args[0])
        return fp.pack(fp.Single.max.copy())

    ######################################################################
    # conversion

    def value_cvi(self):
        """ CVI: return the int value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(parse_bracket(self.ins, self.session)))
        if len(cstr) < 2:
            raise error.RunError(error.IFC)
        return vartypes.bytes_to_integer(cstr[:2])

    def value_cvs(self):
        """ CVS: return the single-precision value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(parse_bracket(self.ins, self.session)))
        if len(cstr) < 4:
            raise error.RunError(error.IFC)
        return ('!', bytearray(cstr[:4]))

    def value_cvd(self):
        """ CVD: return the double-precision value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(parse_bracket(self.ins, self.session)))
        if len(cstr) < 8:
            raise error.RunError(error.IFC)
        return ('#', bytearray(cstr[:8]))

    def value_mki(self):
        """ MKI$: return the byte representation of an int. """
        return self.session.strings.store(vartypes.integer_to_bytes(vartypes.pass_integer(parse_bracket(self.ins, self.session))))

    def value_mks(self):
        """ MKS$: return the byte representation of a single. """
        return self.session.strings.store(vartypes.pass_single(parse_bracket(self.ins, self.session))[1])

    def value_mkd(self):
        """ MKD$: return the byte representation of a double. """
        return self.session.strings.store(vartypes.pass_double(parse_bracket(self.ins, self.session))[1])

    def value_cint(self):
        """ CINT: convert a number to integer. """
        return vartypes.pass_integer(parse_bracket(self.ins, self.session))

    def value_csng(self):
        """ CSNG: convert a number to single. """
        return vartypes.pass_single(parse_bracket(self.ins, self.session))

    def value_cdbl(self):
        """ CDBL: convert a number to double. """
        return vartypes.pass_double(parse_bracket(self.ins, self.session))

    def value_str(self):
        """ STR$: string representation of a number. """
        s = vartypes.pass_number(parse_bracket(self.ins, self.session))
        return self.session.strings.store(representation.number_to_str(s, screen=True))

    def value_val(self):
        """ VAL: number value of a string. """
        return representation.str_to_number(self.session.strings.copy(vartypes.pass_string(parse_bracket(self.ins, self.session))))

    def value_chr(self):
        """ CHR$: character for ASCII value. """
        val = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 255, val)
        return self.session.strings.store(chr(val))

    def value_oct(self):
        """ OCT$: octal representation of int. """
        # allow range -32768 to 65535
        val = vartypes.pass_integer(parse_bracket(self.ins, self.session), 0xffff)
        return self.session.strings.store(representation.integer_to_str_oct(val))

    def value_hex(self):
        """ HEX$: hexadecimal representation of int. """
        # allow range -32768 to 65535
        val = vartypes.pass_integer(parse_bracket(self.ins, self.session), 0xffff)
        return self.session.strings.store(representation.integer_to_str_hex(val))


    ######################################################################
    # string maniulation

    def value_len(self):
        """ LEN: length of string. """
        return vartypes.int_to_integer_signed(
                    vartypes.string_length(vartypes.pass_string(parse_bracket(self.ins, self.session))))

    def value_asc(self):
        """ ASC: ordinal ASCII value of a character. """
        s = self.session.strings.copy(vartypes.pass_string(parse_bracket(self.ins, self.session)))
        if not s:
            raise error.RunError(error.IFC)
        return vartypes.int_to_integer_signed(ord(s[0]))

    def value_instr(self):
        """ INSTR: find substring in string. """
        util.require_read(self.ins, ('(',))
        big, small, n = '', '', 1
        # followed by coma so empty will raise STX
        s = parse_expression(self.ins, self.session)
        if s[0] != '$':
            n = vartypes.pass_int_unpack(s)
            util.range_check(1, 255, n)
            util.require_read(self.ins, (',',))
            big = vartypes.pass_string(parse_expression(self.ins, self.session, allow_empty=True))
        else:
            big = vartypes.pass_string(s)
        util.require_read(self.ins, (',',))
        small = vartypes.pass_string(parse_expression(self.ins, self.session, allow_empty=True))
        util.require_read(self.ins, (')',))
        big, small = self.session.strings.copy(big), self.session.strings.copy(small)
        if big == '' or n > len(big):
            return vartypes.null('%')
        # BASIC counts string positions from 1
        find = big[n-1:].find(small)
        if find == -1:
            return vartypes.null('%')
        return vartypes.int_to_integer_signed(n + find)

    def value_mid(self):
        """ MID$: get substring. """
        util.require_read(self.ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(parse_expression(self.ins, self.session)))
        util.require_read(self.ins, (',',))
        start = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        if util.skip_white_read_if(self.ins, (',',)):
            num = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        else:
            num = len(s)
        util.require_read(self.ins, (')',))
        util.range_check(1, 255, start)
        util.range_check(0, 255, num)
        if num == 0 or start > len(s):
            return vartypes.null('$')
        start -= 1
        stop = start + num
        stop = min(stop, len(s))
        return self.session.strings.store(s[start:stop])

    def value_left(self):
        """ LEFT$: get substring at the start of string. """
        util.require_read(self.ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(parse_expression(self.ins, self.session)))
        util.require_read(self.ins, (',',))
        stop = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.require_read(self.ins, (')',))
        util.range_check(0, 255, stop)
        if stop == 0:
            return vartypes.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[:stop])

    def value_right(self):
        """ RIGHT$: get substring at the end of string. """
        util.require_read(self.ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(parse_expression(self.ins, self.session)))
        util.require_read(self.ins, (',',))
        stop = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.require_read(self.ins, (')',))
        util.range_check(0, 255, stop)
        if stop == 0:
            return vartypes.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[-stop:])

    def value_string(self):
        """ STRING$: repeat characters. """
        util.require_read(self.ins, ('(',))
        n = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.range_check(0, 255, n)
        util.require_read(self.ins, (',',))
        j = parse_expression(self.ins, self.session)
        if j[0] == '$':
            j = self.session.strings.copy(j)
            util.range_check(1, 255, len(j))
            j = ord(j[0])
        else:
            j = vartypes.pass_int_unpack(j)
            util.range_check(0, 255, j)
        util.require_read(self.ins, (')',))
        return self.session.strings.store(chr(j)*n)

    def value_space(self):
        """ SPACE$: repeat spaces. """
        num = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 255, num)
        return self.session.strings.store(' '*num)

    ######################################################################
    # console functions

    def value_screen(self):
        """ SCREEN: get char or attribute at a location. """
        util.require_read(self.ins, ('(',))
        row = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.require_read(self.ins, (',',), err=error.IFC)
        col = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        z = 0
        if util.skip_white_read_if(self.ins, (',',)):
            z = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        cmode = state.console_state.screen.mode
        util.range_check(1, cmode.height, row)
        if state.console_state.view_set:
            util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
        util.range_check(1, cmode.width, col)
        util.range_check(0, 255, z)
        util.require_read(self.ins, (')',))
        if z and not cmode.is_text_mode:
            return vartypes.null('%')
        else:
            return vartypes.int_to_integer_signed(state.console_state.screen.apage.get_char_attr(row, col, z!=0))

    def value_input(self):
        """ INPUT$: get characters from the keyboard or a file. """
        util.require_read(self.ins, ('$',))
        util.require_read(self.ins, ('(',))
        num = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.range_check(1, 255, num)
        infile = state.io_state.kybd_file
        if util.skip_white_read_if(self.ins, (',',)):
            infile = devices.get_file(parse_file_number_opthash(self.ins, self.session))
        util.require_read(self.ins, (')',))
        word = bytearray(infile.read_raw(num))
        if len(word) < num:
            # input past end
            raise error.RunError(error.INPUT_PAST_END)
        return self.session.strings.store(word)

    def value_inkey(self):
        """ INKEY$: get a character from the keyboard. """
        return self.session.strings.store(state.console_state.keyb.get_char())

    def value_csrlin(self):
        """ CSRLIN: get the current screen row. """
        row, col = state.console_state.row, state.console_state.col
        if (col == state.console_state.screen.mode.width and
                state.console_state.overflow and
                row < state.console_state.scroll_height):
            # in overflow position, return row+1 except on the last row
            row += 1
        return vartypes.int_to_integer_signed(row)

    def value_pos(self):
        """ POS: get the current screen column. """
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        parse_bracket(self.ins, self.session)
        col = state.console_state.col
        if col == state.console_state.screen.mode.width and state.console_state.overflow:
            # in overflow position, return column 1.
            col = 1
        return vartypes.int_to_integer_signed(col)

    def value_lpos(self):
        """ LPOS: get the current printer column. """
        num = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 3, num)
        printer = state.io_state.devices['LPT' + max(1, num) + ':']
        if printer.device_file:
            return vartypes.int_to_integer_signed(printer.device_file.col)
        else:
            return vartypes.int_to_integer_signed(1)

    ######################################################################
    # file access

    def value_loc(self):
        """ LOC: get file pointer. """
        util.skip_white(self.ins)
        num = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session), maxint=0xffff)
        util.range_check(0, 255, num)
        the_file = devices.get_file(num)
        return fp.pack(fp.Single.from_int(the_file.loc()))

    def value_eof(self):
        """ EOF: get end-of-file. """
        util.skip_white(self.ins)
        num = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session), maxint=0xffff)
        if num == 0:
            return vartypes.null('%')
        util.range_check(0, 255, num)
        the_file = devices.get_file(num, 'IR')
        return vartypes.bool_to_integer(the_file.eof())

    def value_lof(self):
        """ LOF: get length of file. """
        util.skip_white(self.ins)
        num = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session), maxint=0xffff)
        util.range_check(0, 255, num)
        the_file = devices.get_file(num)
        return fp.pack(fp.Single.from_int(the_file.lof()))


    ######################################################################
    # env, time and date functions

    def value_environ(self):
        """ ENVIRON$: get environment string. """
        util.require_read(self.ins, ('$',))
        expr = parse_bracket(self.ins, self.session)
        if expr[0] == '$':
            return self.session.strings.store(shell.get_env(self.session.strings.copy(expr)))
        else:
            expr = vartypes.pass_int_unpack(expr)
            util.range_check(1, 255, expr)
            return self.session.strings.store(shell.get_env_entry(expr))

    def value_timer(self):
        """ TIMER: get clock ticks since midnight. """
        # precision of GWBASIC TIMER is about 1/20 of a second
        return fp.pack(fp.div( fp.Single.from_int(
                self.session.timer.timer_milliseconds()/50), fp.Single.from_int(20)))

    def value_time(self):
        """ TIME$: get current system time. """
        return self.session.strings.store(self.session.timer.get_time())

    def value_date(self):
        """ DATE$: get current system date. """
        return self.session.strings.store(self.session.timer.get_date())

    #######################################################
    # user-defined functions

    def value_fn(self):
        """ FN: get value of user-defined function. """
        fnname = util.parse_scalar(self.ins)
        # recursion is not allowed as there's no way to terminate it
        if fnname in self.user_function_parsing:
            raise error.RunError(error.OUT_OF_MEMORY)
        try:
            varnames, fncode = self.session.user_functions[fnname]
        except KeyError:
            raise error.RunError(error.UNDEFINED_USER_FUNCTION)
        # save existing vars
        varsave = {}
        for name in varnames:
            if name in self.session.scalars.variables:
                # copy the *value* - set_var is in-place it's safe for FOR loops
                varsave[name] = self.session.scalars.variables[name][:]
        # read variables
        if util.skip_white_read_if(self.ins, ('(',)):
            exprs = []
            while True:
                exprs.append(parse_expression(self.ins, self.session))
                if not util.skip_white_read_if(self.ins, (',',)):
                    break
            if len(exprs) != len(varnames):
                raise error.RunError(error.STX)
            for name, value in zip(varnames, exprs):
                self.session.scalars.set(name, value)
            util.require_read(self.ins, (')',))
        # execute the code
        fns = StringIO(fncode)
        fns.seek(0)
        ev = Evaluator(fns, self.session,
                user_fn_parsing=self.user_function_parsing | set((fnname, )))
        value = ev.evaluate()
        # restore existing vars
        for name in varsave:
            # re-assign the stored value
            self.session.scalars.variables[name][:] = varsave[name]
        return vartypes.pass_type(fnname[-1], value)

    ###############################################################
    # graphics

    def value_point(self):
        """ POINT: get pixel attribute at screen location. """
        util.require_read(self.ins, ('(',))
        arg0 = parse_expression(self.ins, self.session)
        screen = state.console_state.screen
        if util.skip_white_read_if(self.ins, (',',)):
            # two-argument mode
            arg1 = parse_expression(self.ins, self.session)
            util.require_read(self.ins, (')',))
            if screen.mode.is_text_mode:
                raise error.RunError(error.IFC)
            return vartypes.int_to_integer_signed(screen.drawing.point(
                            (fp.unpack(vartypes.pass_single(arg0)),
                             fp.unpack(vartypes.pass_single(arg1)), False)))
        else:
            # single-argument mode
            util.require_read(self.ins, (')',))
            try:
                x, y = screen.drawing.last_point
                fn = vartypes.pass_int_unpack(arg0)
                if fn == 0:
                    return vartypes.int_to_integer_signed(x)
                elif fn == 1:
                    return vartypes.int_to_integer_signed(y)
                elif fn == 2:
                    fx, _ = screen.drawing.get_window_logical(x, y)
                    return fp.pack(fx)
                elif fn == 3:
                    _, fy = screen.drawing.get_window_logical(x, y)
                    return fp.pack(fy)
            except AttributeError:
                return vartypes.null('%')

    def value_pmap(self):
        """ PMAP: convert between logical and physical coordinates. """
        util.require_read(self.ins, ('(',))
        coord = parse_expression(self.ins, self.session)
        util.require_read(self.ins, (',',))
        mode = vartypes.pass_int_unpack(parse_expression(self.ins, self.session))
        util.require_read(self.ins, (')',))
        util.range_check(0, 3, mode)
        screen = state.console_state.screen
        if screen.mode.is_text_mode:
            return vartypes.null('%')
        if mode == 0:
            value, _ = screen.drawing.get_window_physical(fp.unpack(vartypes.pass_single(coord)), fp.Single.zero)
            return vartypes.int_to_integer_signed(value)
        elif mode == 1:
            _, value = screen.drawing.get_window_physical(fp.Single.zero, fp.unpack(vartypes.pass_single(coord)))
            return vartypes.int_to_integer_signed(value)
        elif mode == 2:
            value, _ = screen.drawing.get_window_logical(vartypes.pass_int_unpack(coord), 0)
            return fp.pack(value)
        elif mode == 3:
            _, value = screen.drawing.get_window_logical(0, vartypes.pass_int_unpack(coord))
            return fp.pack(value)

    #####################################################################
    # sound functions

    def value_play(self):
        """ PLAY: get length of music queue. """
        voice = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 255, voice)
        if not(self.session.parser.syntax in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return vartypes.int_to_integer_signed(state.console_state.sound.queue_length(voice))

    #####################################################################
    # error functions

    def value_erl(self):
        """ ERL: get line number of last error. """
        if self.session.parser.error_pos == 0:
            erl = 0
        elif self.session.parser.error_pos == -1:
            erl = 65535
        else:
            erl = self.session.program.get_line_number(self.session.parser.error_pos)
        return fp.pack(fp.Single.from_int(erl))

    def value_err(self):
        """ ERR: get error code of last error. """
        return vartypes.int_to_integer_signed(self.session.parser.error_num)

    #####################################################################
    # pen, stick and strig

    def value_pen(self):
        """ PEN: poll the light pen. """
        fn = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 9, fn)
        pen = state.console_state.pen.poll(fn)
        if pen is None or not self.session.parser.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return vartypes.int_to_integer_signed(pen)

    def value_stick(self):
        """ STICK: poll the joystick. """
        fn = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 3, fn)
        return vartypes.int_to_integer_signed(state.console_state.stick.poll(fn))

    def value_strig(self):
        """ STRIG: poll the joystick fire button. """
        fn = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        util.range_check(0, 7, fn)
        return vartypes.bool_to_integer(state.console_state.stick.poll_trigger(fn))

    #########################################################
    # memory and machine

    def value_fre(self):
        """ FRE: get free memory and optionally collect garbage. """
        val = parse_bracket(self.ins, self.session)
        if val[0] == '$':
            # grabge collection if a string-valued argument is specified.
            self.session.memory.collect_garbage()
        return fp.pack(fp.Single.from_int(self.session.memory.get_free()))

    def value_peek(self):
        """ PEEK: read memory location. """
        addr = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session), maxint=0xffff)
        if self.session.program.protected and not self.session.parser.run_mode:
            raise error.RunError(error.IFC)
        return vartypes.int_to_integer_signed(self.session.all_memory.peek(addr))

    def value_varptr(self):
        """ VARPTR, VARPTR$: get memory address for variable or FCB. """
        dollar = util.skip_white_read_if(self.ins, ('$',))
        util.require_read(self.ins, ('(',))
        if (not dollar) and util.skip_white(self.ins) == '#':
            filenum = parse_file_number_opthash(self.ins, self.session)
            var_ptr = self.session.memory.varptr_file(filenum)
        else:
            name, indices = parse_variable(self.ins, self.session)
            var_ptr = self.session.memory.varptr(name, indices)
        util.require_read(self.ins, (')',))
        if var_ptr < 0:
            raise error.RunError(error.IFC)
        var_ptr = vartypes.int_to_integer_unsigned(var_ptr)
        if dollar:
            return self.session.strings.store(chr(vartypes.byte_size[name[-1]]) + vartypes.integer_to_bytes(var_ptr))
        else:
            return var_ptr

    def value_usr(self):
        """ USR: get value of machine-code function; not implemented. """
        util.require_read(self.ins, tk.digit)
        parse_bracket(self.ins, self.session)
        logging.warning("USR() function not implemented.")
        return vartypes.null('%')

    def value_inp(self):
        """ INP: get value from machine port. """
        port = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session), maxint=0xffff)
        return vartypes.int_to_integer_signed(machine.inp(port))

    def value_erdev(self):
        """ ERDEV$: device error string; not implemented. """
        logging.warning("ERDEV or ERDEV$ function not implemented.")
        if util.skip_white_read_if(self.ins, ('$',)):
            return vartypes.null('$')
        else:
            return vartypes.null('%')

    def value_exterr(self):
        """ EXTERR: device error information; not implemented. """
        x = vartypes.pass_int_unpack(parse_bracket(self.ins, self.session))
        util.range_check(0, 3, x)
        logging.warning("EXTERR() function not implemented.")
        return vartypes.null('%')

    def value_ioctl(self):
        """ IOCTL$: read device control string response; not implemented. """
        util.require_read(self.ins, ('$',))
        util.require_read(self.ins, ('(',))
        num = parse_file_number_opthash(self.ins, self.session)
        util.require_read(self.ins, (')',))
        devices.get_file(num)
        logging.warning("IOCTL$() function not implemented.")
        raise error.RunError(error.IFC)

    ###########################################################
    # option_double regulated single & double precision math

    def value_func(self, fn):
        """ Return value of unary math function. """
        return fp.pack(fn(fp.unpack(vartypes.pass_float(parse_bracket(self.ins, self.session), vartypes.option_double))))

    value_sqr = partial(value_func, fn=fp.sqrt)
    value_exp = partial(value_func, fn=fp.exp)
    value_sin = partial(value_func, fn=fp.sin)
    value_cos = partial(value_func, fn=fp.cos)
    value_tan = partial(value_func, fn=fp.tan)
    value_atn = partial(value_func, fn=fp.atn)
    value_log = partial(value_func, fn=fp.log)

    def value_rnd(self):
        """ RND: get pseudorandom value. """
        if util.skip_white(self.ins) == '(':
            return self.session.randomiser.get(fp.unpack(vartypes.pass_single(parse_bracket(self.ins, self.session))))
        else:
            return self.session.randomiser.get_int(1)

    def value_abs(self):
        """ ABS: get absolute value. """
        inp = parse_bracket(self.ins, self.session)
        return inp if inp[0] == '$' else self.operators.number_abs(inp)

    def value_int(self):
        """ INT: get floor value. """
        inp = vartypes.pass_number(parse_bracket(self.ins, self.session))
        return inp if inp[0] == '%' else fp.pack(fp.unpack(inp).ifloor())

    def value_sgn(self):
        """ SGN: get sign. """
        inp = vartypes.pass_number(parse_bracket(self.ins, self.session))
        if inp[0] == '%':
            inp_int = vartypes.integer_to_int_signed(inp)
            return vartypes.int_to_integer_signed(0 if inp_int==0 else (1 if inp_int > 0 else -1))
        else:
            return vartypes.int_to_integer_signed(fp.unpack(inp).sign())

    def value_fix(self):
        """ FIX: round towards zero. """
        inp = vartypes.pass_number(parse_bracket(self.ins, self.session))
        if inp[0] == '%':
            return inp
        elif inp[0] == '!':
            # needs to be a float to avoid overflow
            return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int()))
        elif inp[0] == '#':
            return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int()))


    functions = {
        tk.INPUT: value_input,
        tk.SCREEN: value_screen,
        tk.USR: value_usr,
        tk.FN: value_fn,
        tk.ERL: value_erl,
        tk.ERR: value_err,
        tk.STRING: value_string,
        tk.INSTR: value_instr,
        tk.VARPTR: value_varptr,
        tk.CSRLIN: value_csrlin,
        tk.POINT: value_point,
        tk.INKEY: value_inkey,
        tk.CVI: value_cvi,
        tk.CVS: value_cvs,
        tk.CVD: value_cvd,
        tk.MKI: value_mki,
        tk.MKS: value_mks,
        tk.MKD: value_mkd,
        tk.EXTERR: value_exterr,
        tk.DATE: value_date,
        tk.TIME: value_time,
        tk.PLAY: value_play,
        tk.TIMER: value_timer,
        tk.ERDEV: value_erdev,
        tk.IOCTL: value_ioctl,
        tk.ENVIRON: value_environ,
        tk.PMAP: value_pmap,
        tk.LEFT: value_left,
        tk.RIGHT: value_right,
        tk.MID: value_mid,
        tk.SGN: value_sgn,
        tk.INT: value_int,
        tk.ABS: value_abs,
        tk.SQR: value_sqr,
        tk.RND: value_rnd,
        tk.SIN: value_sin,
        tk.LOG: value_log,
        tk.EXP: value_exp,
        tk.COS: value_cos,
        tk.TAN: value_tan,
        tk.ATN: value_atn,
        tk.FRE: value_fre,
        tk.INP: value_inp,
        tk.POS: value_pos,
        tk.LEN: value_len,
        tk.STR: value_str,
        tk.VAL: value_val,
        tk.ASC: value_asc,
        tk.CHR: value_chr,
        tk.PEEK: value_peek,
        tk.SPACE: value_space,
        tk.OCT: value_oct,
        tk.HEX: value_hex,
        tk.LPOS: value_lpos,
        tk.CINT: value_cint,
        tk.CSNG: value_csng,
        tk.CDBL: value_cdbl,
        tk.FIX: value_fix,
        tk.PEN: value_pen,
        tk.STICK: value_stick,
        tk.STRIG: value_strig,
        tk.EOF: value_eof,
        tk.LOC: value_loc,
        tk.LOF: value_lof,
    }
