"""
PC-BASIC - functions.py
BASIC functions.

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from functools import partial
import logging

import fp
import vartypes
import representation
import shell
import util
import error
import state
import basictoken as tk
import console



class Functions(object):
    """ BASIC functions. """

    def __init__(self, parser, double_math):
        """ Initialise function context. """
        self.parser = parser
        self.session = parser.session
        # double-precision EXP, SIN, COS, TAN, ATN, LOG
        self.double_math = double_math
        # state variable for detecting recursion
        self.user_function_parsing = set()
        self._init_functions()

    def _init_functions(self):
        """ Initialise functions. """
        self.functions = {
            tk.INPUT: self.value_input,
            tk.SCREEN: self.value_screen,
            tk.USR: self.value_usr,
            tk.FN: self.value_fn,
            tk.ERL: self.value_erl,
            tk.ERR: self.value_err,
            tk.STRING: self.value_string,
            tk.INSTR: self.value_instr,
            tk.VARPTR: self.value_varptr,
            tk.CSRLIN: self.value_csrlin,
            tk.POINT: self.value_point,
            tk.INKEY: self.value_inkey,
            tk.CVI: self.value_cvi,
            tk.CVS: self.value_cvs,
            tk.CVD: self.value_cvd,
            tk.MKI: self.value_mki,
            tk.MKS: self.value_mks,
            tk.MKD: self.value_mkd,
            tk.EXTERR: self.value_exterr,
            tk.DATE: self.value_date,
            tk.TIME: self.value_time,
            tk.PLAY: self.value_play,
            tk.TIMER: self.value_timer,
            tk.ERDEV: self.value_erdev,
            tk.IOCTL: self.value_ioctl,
            tk.ENVIRON: self.value_environ,
            tk.PMAP: self.value_pmap,
            tk.LEFT: self.value_left,
            tk.RIGHT: self.value_right,
            tk.MID: self.value_mid,
            tk.SGN: self.value_sgn,
            tk.INT: self.value_int,
            tk.ABS: self.value_abs,
            tk.SQR: partial(self.value_func, fn=fp.sqrt),
            tk.RND: self.value_rnd,
            tk.SIN: partial(self.value_func, fn=fp.sin),
            tk.LOG: partial(self.value_func, fn=fp.log),
            tk.EXP: partial(self.value_func, fn=fp.exp),
            tk.COS: partial(self.value_func, fn=fp.cos),
            tk.TAN: partial(self.value_func, fn=fp.tan),
            tk.ATN: partial(self.value_func, fn=fp.atn),
            tk.FRE: self.value_fre,
            tk.INP: self.value_inp,
            tk.POS: self.value_pos,
            tk.LEN: self.value_len,
            tk.STR: self.value_str,
            tk.VAL: self.value_val,
            tk.ASC: self.value_asc,
            tk.CHR: self.value_chr,
            tk.PEEK: self.value_peek,
            tk.SPACE: self.value_space,
            tk.OCT: self.value_oct,
            tk.HEX: self.value_hex,
            tk.LPOS: self.value_lpos,
            tk.CINT: self.value_cint,
            tk.CSNG: self.value_csng,
            tk.CDBL: self.value_cdbl,
            tk.FIX: self.value_fix,
            tk.PEN: self.value_pen,
            tk.STICK: self.value_stick,
            tk.STRIG: self.value_strig,
            tk.EOF: self.value_eof,
            tk.LOC: self.value_loc,
            tk.LOF: self.value_lof,
        }

    def __getstate__(self):
        """ Pickle. """
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['functions'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """ Unpickle. """
        self.__dict__.update(pickle_dict)
        self._init_functions()


    ##########################################################################
    # conversion

    def value_cvi(self, ins):
        """ CVI: return the int value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_bracket(ins, self.session)))
        if len(cstr) < 2:
            raise error.RunError(error.IFC)
        return vartypes.bytes_to_integer(cstr[:2])

    def value_cvs(self, ins):
        """ CVS: return the single-precision value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_bracket(ins, self.session)))
        if len(cstr) < 4:
            raise error.RunError(error.IFC)
        return ('!', bytearray(cstr[:4]))

    def value_cvd(self, ins):
        """ CVD: return the double-precision value of a byte representation. """
        cstr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_bracket(ins, self.session)))
        if len(cstr) < 8:
            raise error.RunError(error.IFC)
        return ('#', bytearray(cstr[:8]))

    def value_mki(self, ins):
        """ MKI$: return the byte representation of an int. """
        return self.session.strings.store(vartypes.integer_to_bytes(vartypes.pass_integer(self.parser.parse_bracket(ins, self.session))))

    def value_mks(self, ins):
        """ MKS$: return the byte representation of a single. """
        return self.session.strings.store(vartypes.pass_single(self.parser.parse_bracket(ins, self.session))[1])

    def value_mkd(self, ins):
        """ MKD$: return the byte representation of a double. """
        return self.session.strings.store(vartypes.pass_double(self.parser.parse_bracket(ins, self.session))[1])

    def value_cint(self, ins):
        """ CINT: convert a number to integer. """
        return vartypes.pass_integer(self.parser.parse_bracket(ins, self.session))

    def value_csng(self, ins):
        """ CSNG: convert a number to single. """
        return vartypes.pass_single(self.parser.parse_bracket(ins, self.session))

    def value_cdbl(self, ins):
        """ CDBL: convert a number to double. """
        return vartypes.pass_double(self.parser.parse_bracket(ins, self.session))

    def value_str(self, ins):
        """ STR$: string representation of a number. """
        s = vartypes.pass_number(self.parser.parse_bracket(ins, self.session))
        return self.session.strings.store(representation.number_to_str(s, screen=True))

    def value_val(self, ins):
        """ VAL: number value of a string. """
        return representation.str_to_number(self.session.strings.copy(vartypes.pass_string(self.parser.parse_bracket(ins, self.session))))

    def value_chr(self, ins):
        """ CHR$: character for ASCII value. """
        val = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 255, val)
        return self.session.strings.store(chr(val))

    def value_oct(self, ins):
        """ OCT$: octal representation of int. """
        # allow range -32768 to 65535
        val = vartypes.pass_integer(self.parser.parse_bracket(ins, self.session), 0xffff)
        return self.session.strings.store(representation.integer_to_str_oct(val))

    def value_hex(self, ins):
        """ HEX$: hexadecimal representation of int. """
        # allow range -32768 to 65535
        val = vartypes.pass_integer(self.parser.parse_bracket(ins, self.session), 0xffff)
        return self.session.strings.store(representation.integer_to_str_hex(val))


    ######################################################################
    # string maniulation

    def value_len(self, ins):
        """ LEN: length of string. """
        return vartypes.int_to_integer_signed(
                    vartypes.string_length(vartypes.pass_string(self.parser.parse_bracket(ins, self.session))))

    def value_asc(self, ins):
        """ ASC: ordinal ASCII value of a character. """
        s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_bracket(ins, self.session)))
        if not s:
            raise error.RunError(error.IFC)
        return vartypes.int_to_integer_signed(ord(s[0]))

    def value_instr(self, ins):
        """ INSTR: find substring in string. """
        util.require_read(ins, ('(',))
        big, small, n = '', '', 1
        # followed by coma so empty will raise STX
        s = self.parser.parse_expression(ins, self.session)
        if s[0] != '$':
            n = vartypes.pass_int_unpack(s)
            util.range_check(1, 255, n)
            util.require_read(ins, (',',))
            big = vartypes.pass_string(self.parser.parse_expression(ins, self.session, allow_empty=True))
        else:
            big = vartypes.pass_string(s)
        util.require_read(ins, (',',))
        small = vartypes.pass_string(self.parser.parse_expression(ins, self.session, allow_empty=True))
        util.require_read(ins, (')',))
        big, small = self.session.strings.copy(big), self.session.strings.copy(small)
        if big == '' or n > len(big):
            return vartypes.null('%')
        # BASIC counts string positions from 1
        find = big[n-1:].find(small)
        if find == -1:
            return vartypes.null('%')
        return vartypes.int_to_integer_signed(n + find)

    def value_mid(self, ins):
        """ MID$: get substring. """
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        start = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        if util.skip_white_read_if(ins, (',',)):
            num = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        else:
            num = len(s)
        util.require_read(ins, (')',))
        util.range_check(1, 255, start)
        util.range_check(0, 255, num)
        if num == 0 or start > len(s):
            return vartypes.null('$')
        start -= 1
        stop = start + num
        stop = min(stop, len(s))
        return self.session.strings.store(s[start:stop])

    def value_left(self, ins):
        """ LEFT$: get substring at the start of string. """
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        stop = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        util.range_check(0, 255, stop)
        if stop == 0:
            return vartypes.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[:stop])

    def value_right(self, ins):
        """ RIGHT$: get substring at the end of string. """
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        stop = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        util.range_check(0, 255, stop)
        if stop == 0:
            return vartypes.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[-stop:])

    def value_string(self, ins):
        """ STRING$: repeat characters. """
        util.require_read(ins, ('(',))
        n = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, n)
        util.require_read(ins, (',',))
        j = self.parser.parse_expression(ins, self.session)
        if j[0] == '$':
            j = self.session.strings.copy(j)
            util.range_check(1, 255, len(j))
            j = ord(j[0])
        else:
            j = vartypes.pass_int_unpack(j)
            util.range_check(0, 255, j)
        util.require_read(ins, (')',))
        return self.session.strings.store(chr(j)*n)

    def value_space(self, ins):
        """ SPACE$: repeat spaces. """
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 255, num)
        return self.session.strings.store(' '*num)

    ######################################################################
    # console functions

    def value_screen(self, ins):
        """ SCREEN: get char or attribute at a location. """
        util.require_read(ins, ('(',))
        row = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (',',), err=error.IFC)
        col = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        z = 0
        if util.skip_white_read_if(ins, (',',)):
            z = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        cmode = self.session.screen.mode
        util.range_check(1, cmode.height, row)
        if state.console_state.view_set:
            util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
        util.range_check(1, cmode.width, col)
        util.range_check(0, 255, z)
        util.require_read(ins, (')',))
        if z and not cmode.is_text_mode:
            return vartypes.null('%')
        else:
            return vartypes.int_to_integer_signed(self.session.screen.apage.get_char_attr(row, col, z!=0))

    def value_input(self, ins):
        """ INPUT$: get characters from the keyboard or a file. """
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if util.skip_white_read_if(ins, (',',)):
            infile = self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session))
        util.require_read(ins, (')',))
        word = bytearray(infile.read_raw(num))
        if len(word) < num:
            # input past end
            raise error.RunError(error.INPUT_PAST_END)
        return self.session.strings.store(word)

    def value_inkey(self, ins):
        """ INKEY$: get a character from the keyboard. """
        return self.session.strings.store(state.console_state.keyb.get_char())

    def value_csrlin(self, ins):
        """ CSRLIN: get the current screen row. """
        row, col = state.console_state.row, state.console_state.col
        if (col == self.session.screen.mode.width and
                state.console_state.overflow and
                row < state.console_state.scroll_height):
            # in overflow position, return row+1 except on the last row
            row += 1
        return vartypes.int_to_integer_signed(row)

    def value_pos(self, ins):
        """ POS: get the current screen column. """
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        self.parser.parse_bracket(ins, self.session)
        col = state.console_state.col
        if col == self.session.screen.mode.width and state.console_state.overflow:
            # in overflow position, return column 1.
            col = 1
        return vartypes.int_to_integer_signed(col)

    def value_lpos(self, ins):
        """ LPOS: get the current printer column. """
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 3, num)
        printer = self.session.devices.devices['LPT' + max(1, num) + ':']
        if printer.device_file:
            return vartypes.int_to_integer_signed(printer.device_file.col)
        else:
            return vartypes.int_to_integer_signed(1)

    ######################################################################
    # file access

    def value_loc(self, ins):
        """ LOC: get file pointer. """
        util.skip_white(ins)
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        util.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return fp.pack(fp.Single.from_int(the_file.loc()))

    def value_eof(self, ins):
        """ EOF: get end-of-file. """
        util.skip_white(ins)
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        if num == 0:
            return vartypes.null('%')
        util.range_check(0, 255, num)
        the_file = self.session.files.get(num, 'IR')
        return vartypes.bool_to_integer(the_file.eof())

    def value_lof(self, ins):
        """ LOF: get length of file. """
        util.skip_white(ins)
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        util.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return fp.pack(fp.Single.from_int(the_file.lof()))


    ######################################################################
    # env, time and date functions

    def value_environ(self, ins):
        """ ENVIRON$: get environment string. """
        util.require_read(ins, ('$',))
        expr = self.parser.parse_bracket(ins, self.session)
        if expr[0] == '$':
            return self.session.strings.store(shell.get_env(self.session.strings.copy(expr)))
        else:
            expr = vartypes.pass_int_unpack(expr)
            util.range_check(1, 255, expr)
            return self.session.strings.store(shell.get_env_entry(expr))

    def value_timer(self, ins):
        """ TIMER: get clock ticks since midnight. """
        # precision of GWBASIC TIMER is about 1/20 of a second
        return fp.pack(fp.div( fp.Single.from_int(
                self.session.timer.timer_milliseconds()/50), fp.Single.from_int(20)))

    def value_time(self, ins):
        """ TIME$: get current system time. """
        return self.session.strings.store(self.session.timer.get_time())

    def value_date(self, ins):
        """ DATE$: get current system date. """
        return self.session.strings.store(self.session.timer.get_date())

    #######################################################
    # user-defined functions

    def value_fn(self, ins):
        """ FN: get value of user-defined function. """
        fnname = self.parser.parse_scalar(ins)
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
        if util.skip_white_read_if(ins, ('(',)):
            exprs = []
            while True:
                exprs.append(self.parser.parse_expression(ins, self.session))
                if not util.skip_white_read_if(ins, (',',)):
                    break
            if len(exprs) != len(varnames):
                raise error.RunError(error.STX)
            for name, value in zip(varnames, exprs):
                self.session.scalars.set(name, value)
            util.require_read(ins, (')',))
        # execute the code
        fns = StringIO(fncode)
        fns.seek(0)
        self.user_function_parsing.add(fnname)
        value = self.parser.parse_expression(fns, self.session)
        self.user_function_parsing.remove(fnname)
        # restore existing vars
        for name in varsave:
            # re-assign the stored value
            self.session.scalars.variables[name][:] = varsave[name]
        return vartypes.pass_type(fnname[-1], value)

    ###############################################################
    # graphics

    def value_point(self, ins):
        """ POINT: get pixel attribute at screen location. """
        util.require_read(ins, ('(',))
        arg0 = self.parser.parse_expression(ins, self.session)
        screen = self.session.screen
        if util.skip_white_read_if(ins, (',',)):
            # two-argument mode
            arg1 = self.parser.parse_expression(ins, self.session)
            util.require_read(ins, (')',))
            if screen.mode.is_text_mode:
                raise error.RunError(error.IFC)
            return vartypes.int_to_integer_signed(screen.drawing.point(
                            (fp.unpack(vartypes.pass_single(arg0)),
                             fp.unpack(vartypes.pass_single(arg1)), False)))
        else:
            # single-argument mode
            util.require_read(ins, (')',))
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

    def value_pmap(self, ins):
        """ PMAP: convert between logical and physical coordinates. """
        util.require_read(ins, ('(',))
        coord = self.parser.parse_expression(ins, self.session)
        util.require_read(ins, (',',))
        mode = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        util.range_check(0, 3, mode)
        screen = self.session.screen
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

    def value_play(self, ins):
        """ PLAY: get length of music queue. """
        voice = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 255, voice)
        if not(self.parser.syntax in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return vartypes.int_to_integer_signed(state.console_state.sound.queue_length(voice))

    #####################################################################
    # error functions

    def value_erl(self, ins):
        """ ERL: get line number of last error. """
        if self.parser.error_pos == 0:
            erl = 0
        elif self.parser.error_pos == -1:
            erl = 65535
        else:
            erl = self.session.program.get_line_number(self.parser.error_pos)
        return fp.pack(fp.Single.from_int(erl))

    def value_err(self, ins):
        """ ERR: get error code of last error. """
        return vartypes.int_to_integer_signed(self.parser.error_num)

    #####################################################################
    # pen, stick and strig

    def value_pen(self, ins):
        """ PEN: poll the light pen. """
        fn = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 9, fn)
        pen = self.session.pen.poll(fn)
        if pen is None or not self.parser.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return vartypes.int_to_integer_signed(pen)

    def value_stick(self, ins):
        """ STICK: poll the joystick. """
        fn = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 3, fn)
        return vartypes.int_to_integer_signed(state.console_state.stick.poll(fn))

    def value_strig(self, ins):
        """ STRIG: poll the joystick fire button. """
        fn = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        util.range_check(0, 7, fn)
        return vartypes.bool_to_integer(state.console_state.stick.poll_trigger(fn))

    #########################################################
    # memory and machine

    def value_fre(self, ins):
        """ FRE: get free memory and optionally collect garbage. """
        val = self.parser.parse_bracket(ins, self.session)
        if val[0] == '$':
            # grabge collection if a string-valued argument is specified.
            self.session.memory.collect_garbage()
        return fp.pack(fp.Single.from_int(self.session.memory.get_free()))

    def value_peek(self, ins):
        """ PEEK: read memory location. """
        addr = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        return vartypes.int_to_integer_signed(self.session.all_memory.peek(addr))

    def value_varptr(self, ins):
        """ VARPTR, VARPTR$: get memory address for variable or FCB. """
        dollar = util.skip_white_read_if(ins, ('$',))
        util.require_read(ins, ('(',))
        if (not dollar) and util.skip_white(ins) == '#':
            filenum = self.parser.parse_file_number_opthash(ins, self.session)
            var_ptr = self.session.memory.varptr_file(filenum)
        else:
            name, indices = self.parser.parse_variable(ins, self.session)
            var_ptr = self.session.memory.varptr(name, indices)
        util.require_read(ins, (')',))
        if var_ptr < 0:
            raise error.RunError(error.IFC)
        var_ptr = vartypes.int_to_integer_unsigned(var_ptr)
        if dollar:
            return self.session.strings.store(chr(vartypes.byte_size[name[-1]]) + vartypes.integer_to_bytes(var_ptr))
        else:
            return var_ptr

    def value_usr(self, ins):
        """ USR: get value of machine-code function; not implemented. """
        util.require_read(ins, tk.digit)
        self.parser.parse_bracket(ins, self.session)
        logging.warning("USR() function not implemented.")
        return vartypes.null('%')

    def value_inp(self, ins):
        """ INP: get value from machine port. """
        port = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        return vartypes.int_to_integer_signed(self.session.machine.inp(port))

    def value_erdev(self, ins):
        """ ERDEV$: device error string; not implemented. """
        logging.warning("ERDEV or ERDEV$ function not implemented.")
        if util.skip_white_read_if(ins, ('$',)):
            return vartypes.null('$')
        else:
            return vartypes.null('%')

    def value_exterr(self, ins):
        """ EXTERR: device error information; not implemented. """
        x = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 3, x)
        logging.warning("EXTERR() function not implemented.")
        return vartypes.null('%')

    def value_ioctl(self, ins):
        """ IOCTL$: read device control string response; not implemented. """
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = self.parser.parse_file_number_opthash(ins, self.session)
        util.require_read(ins, (')',))
        self.session.files.get(num)
        logging.warning("IOCTL$() function not implemented.")
        raise error.RunError(error.IFC)

    ###########################################################
    # double_math regulated single & double precision math

    def value_func(self, ins, fn):
        """ Return value of unary math function. """
        return fp.pack(fn(fp.unpack(vartypes.pass_float(
            self.parser.parse_bracket(ins, self.session), self.double_math))))

    def value_rnd(self, ins):
        """ RND: get pseudorandom value. """
        if util.skip_white(ins) == '(':
            return self.session.randomiser.get(fp.unpack(vartypes.pass_single(self.parser.parse_bracket(ins, self.session))))
        else:
            return self.session.randomiser.get_int(1)

    def value_abs(self, ins):
        """ ABS: get absolute value. """
        inp = self.parser.parse_bracket(ins, self.session)
        return inp if inp[0] == '$' else self.parser.operators.number_abs(inp)

    def value_int(self, ins):
        """ INT: get floor value. """
        inp = vartypes.pass_number(self.parser.parse_bracket(ins, self.session))
        return inp if inp[0] == '%' else fp.pack(fp.unpack(inp).ifloor())

    def value_sgn(self, ins):
        """ SGN: get sign. """
        inp = vartypes.pass_number(self.parser.parse_bracket(ins, self.session))
        if inp[0] == '%':
            inp_int = vartypes.integer_to_int_signed(inp)
            return vartypes.int_to_integer_signed(0 if inp_int==0 else (1 if inp_int > 0 else -1))
        else:
            return vartypes.int_to_integer_signed(fp.unpack(inp).sign())

    def value_fix(self, ins):
        """ FIX: round towards zero. """
        inp = vartypes.pass_number(self.parser.parse_bracket(ins, self.session))
        if inp[0] == '%':
            return inp
        elif inp[0] == '!':
            # needs to be a float to avoid overflow
            return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int()))
        elif inp[0] == '#':
            return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int()))
