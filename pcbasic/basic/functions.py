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
import struct

from . import values
from . import numbers
from . import strings
from . import shell
from . import util
from . import error
from . import basictoken as tk


class Functions(object):
    """BASIC functions."""

    def __init__(self, parser):
        """Initialise function context."""
        self.parser = parser
        self.session = parser.session
        self.values = self.session.values
        # state variable for detecting recursion
        self.user_function_parsing = set()
        self._init_functions()

    def _init_functions(self):
        """Initialise functions."""
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
            tk.CVI: partial(self.value_func, fn=self.values.cvi),
            tk.CVS: partial(self.value_func, fn=self.values.cvs),
            tk.CVD: partial(self.value_func, fn=self.values.cvd),
            tk.MKI: partial(self.value_func, fn=self.values.mki),
            tk.MKS: partial(self.value_func, fn=self.values.mks),
            tk.MKD: partial(self.value_func, fn=self.values.mkd),
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
            tk.SGN: partial(self.value_func, fn=self.values.sgn),
            tk.INT: partial(self.value_func, fn=self.values.floor),
            tk.ABS: partial(self.value_func, fn=self.values.abs),
            tk.SQR: partial(self.value_func, fn=self.values.sqr),
            tk.RND: self.value_rnd,
            tk.SIN: partial(self.value_func, fn=self.values.sin),
            tk.LOG: partial(self.value_func, fn=self.values.log),
            tk.EXP: partial(self.value_func, fn=self.values.exp),
            tk.COS: partial(self.value_func, fn=self.values.cos),
            tk.TAN: partial(self.value_func, fn=self.values.tan),
            tk.ATN: partial(self.value_func, fn=self.values.atn),
            tk.FRE: self.value_fre,
            tk.INP: self.value_inp,
            tk.POS: self.value_pos,
            tk.LEN: partial(self.value_func, fn=self.values.length),
            tk.STR: partial(self.value_func, fn=self.values.representation),
            tk.VAL: partial(self.value_func, fn=self.values.val),
            tk.ASC: partial(self.value_func, fn=self.values.asc),
            tk.CHR: partial(self.value_func, fn=self.values.character),
            tk.PEEK: self.value_peek,
            tk.SPACE: partial(self.value_func, fn=self.values.space),
            tk.OCT: partial(self.value_func, fn=self.values.octal),
            tk.HEX: partial(self.value_func, fn=self.values.hexadecimal),
            tk.LPOS: self.value_lpos,
            tk.CINT: partial(self.value_func, fn=self.values.to_integer),
            tk.CSNG: partial(self.value_func, fn=self.values.to_single),
            tk.CDBL: partial(self.value_func, fn=self.values.to_double),
            tk.FIX: partial(self.value_func, fn=self.values.fix),
            tk.PEN: self.value_pen,
            tk.STICK: self.value_stick,
            tk.STRIG: self.value_strig,
            tk.EOF: self.value_eof,
            tk.LOC: self.value_loc,
            tk.LOF: self.value_lof,
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['functions'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_functions()


    ######################################################################
    # string functions

    def value_instr(self, ins):
        """INSTR: find substring in string."""
        util.require_read(ins, ('(',))
        # followed by comma so empty will raise STX
        s = self.parser.parse_expression(ins)
        n = 1
        if s[0] != '$':
            n = self.values.to_int(s)
            error.range_check(1, 255, n)
            util.require_read(ins, (',',))
            s = self.parser.parse_expression(ins, empty_err=error.STX)
        big = values.pass_string(s)
        util.require_read(ins, (',',))
        s = self.parser.parse_expression(ins, empty_err=error.STX)
        small = values.pass_string(s)
        util.require_read(ins, (')',))
        return self.values.instr(big, small)

    def value_mid(self, ins):
        """MID$: get substring."""
        util.require_read(ins, ('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        util.require_read(ins, (',',))
        start = self.values.to_integer(self.parser.parse_expression(ins))
        num = None
        if util.skip_white_read_if(ins, (',',)):
            num = self.values.to_integer(self.parser.parse_expression(ins))
        util.require_read(ins, (')',))
        return self.values.mid(s, start, num)

    def value_left(self, ins):
        """LEFT$: get substring at the start of string."""
        util.require_read(ins, ('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        util.require_read(ins, (',',))
        stop = self.values.to_integer(self.parser.parse_expression(ins))
        util.require_read(ins, (')',))
        return self.values.left(s, stop)

    def value_right(self, ins):
        """RIGHT$: get substring at the end of string."""
        util.require_read(ins, ('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        util.require_read(ins, (',',))
        stop = self.values.to_integer(self.parser.parse_expression(ins))
        util.require_read(ins, (')',))
        return self.values.right(s, stop)

    def value_string(self, ins):
        """STRING$: repeat characters."""
        util.require_read(ins, ('(',))
        n = self.values.to_int(self.parser.parse_expression(ins))
        error.range_check(0, 255, n)
        util.require_read(ins, (',',))
        j = self.parser.parse_expression(ins)
        if isinstance(j, strings.String):
            j = ord(j.to_str()[0])
        else:
            j = self.values.to_int(j)
            error.range_check(0, 255, j)
        util.require_read(ins, (')',))
        return self.values.from_value(chr(j)*n, '$')

    ######################################################################
    # console functions

    def value_screen(self, ins):
        """SCREEN: get char or attribute at a location."""
        util.require_read(ins, ('(',))
        row = self.values.to_int(self.parser.parse_expression(ins))
        util.require_read(ins, (',',), err=error.IFC)
        col = self.values.to_int(self.parser.parse_expression(ins))
        z = 0
        if util.skip_white_read_if(ins, (',',)):
            z = self.values.to_int(self.parser.parse_expression(ins))
        cmode = self.session.screen.mode
        error.range_check(1, cmode.height, row)
        if self.session.screen.view_set:
            error.range_check(self.session.screen.view_start, self.session.screen.scroll_height, row)
        error.range_check(1, cmode.width, col)
        error.range_check(0, 255, z)
        util.require_read(ins, (')',))
        if z and not cmode.is_text_mode:
            return self.values.null(values.INT)
        else:
            return numbers.Integer().from_int(self.session.screen.apage.get_char_attr(row, col, z!=0))

    def value_input(self, ins):
        """INPUT$: get characters from the keyboard or a file."""
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = self.values.to_int(self.parser.parse_expression(ins))
        error.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if util.skip_white_read_if(ins, (',',)):
            infile = self.session.files.get(self.parser.parse_file_number_opthash(ins))
        util.require_read(ins, (')',))
        word = bytearray(infile.read_raw(num))
        if len(word) < num:
            # input past end
            raise error.RunError(error.INPUT_PAST_END)
        return self.values.from_value(word, values.STR)

    def value_inkey(self, ins):
        """INKEY$: get a character from the keyboard."""
        return self.values.from_value(self.session.keyboard.get_char(), values.STR)

    def value_csrlin(self, ins):
        """CSRLIN: get the current screen row."""
        row, col = self.session.screen.current_row, self.session.screen.current_col
        if (col == self.session.screen.mode.width and
                self.session.screen.overflow and
                row < self.session.screen.scroll_height):
            # in overflow position, return row+1 except on the last row
            row += 1
        return numbers.Integer().from_int(row)

    def value_pos(self, ins):
        """POS: get the current screen column."""
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        self.parser.parse_bracket(ins)
        col = self.session.screen.current_col
        if col == self.session.screen.mode.width and self.session.screen.overflow:
            # in overflow position, return column 1.
            col = 1
        return numbers.Integer().from_int(col)

    def value_lpos(self, ins):
        """LPOS: get the current printer column."""
        num = self.values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, num)
        printer = self.session.devices.devices['LPT' + max(1, num) + ':']
        if printer.device_file:
            return numbers.Integer().from_int(printer.device_file.col)
        else:
            return numbers.Integer().from_int(1)

    ######################################################################
    # file access

    def value_loc(self, ins):
        """LOC: get file pointer."""
        util.skip_white(ins)
        num = self.values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return self.values.from_value(the_file.loc(), '!')

    def value_eof(self, ins):
        """EOF: get end-of-file."""
        util.skip_white(ins)
        num = self.values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        if num == 0:
            return self.values.null(values.INT)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num, 'IR')
        return self.values.from_bool(the_file.eof())

    def value_lof(self, ins):
        """LOF: get length of file."""
        util.skip_white(ins)
        num = self.values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return self.values.from_value(the_file.lof(), '!')


    ######################################################################
    # env, time and date functions

    def value_environ(self, ins):
        """ENVIRON$: get environment string."""
        util.require_read(ins, ('$',))
        expr = self.parser.parse_bracket(ins)
        if isinstance(expr, strings.String):
            return self.values.from_value(shell.get_env(expr.to_str()), values.STR)
        else:
            expr = self.values.to_int(expr)
            error.range_check(1, 255, expr)
            return self.values.from_value(shell.get_env_entry(expr), values.STR)

    def value_timer(self, ins):
        """TIMER: get clock ticks since midnight."""
        # precision of GWBASIC TIMER is about 1/20 of a second
        return self.values.from_value(
                    float(self.session.clock.get_time_ms()//50) / 20., '!')

    def value_time(self, ins):
        """TIME$: get current system time."""
        return self.values.from_value(self.session.clock.get_time(), values.STR)

    def value_date(self, ins):
        """DATE$: get current system date."""
        return self.values.from_value(self.session.clock.get_date(), values.STR)

    #######################################################
    # user-defined functions

    def value_fn(self, ins):
        """FN: get value of user-defined function."""
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
            if name in self.session.scalars:
                # copy the buffer
                varsave[name] = self.session.scalars.view(name).clone()
        # read variables
        if util.skip_white_read_if(ins, ('(',)):
            exprs = []
            while True:
                exprs.append(self.parser.parse_expression(ins))
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
        value = self.parser.parse_expression(fns)
        self.user_function_parsing.remove(fnname)
        # restore existing vars
        for name in varsave:
            # re-assign the stored value
            self.session.scalars.view(name).copy_from(varsave[name])
        return self.values.to_type(fnname[-1], value)

    ###############################################################
    # graphics

    def value_point(self, ins):
        """POINT: get pixel attribute at screen location."""
        util.require_read(ins, ('(',))
        arg0 = self.parser.parse_expression(ins)
        screen = self.session.screen
        if util.skip_white_read_if(ins, (',',)):
            # two-argument mode
            arg1 = self.parser.parse_expression(ins)
            util.require_read(ins, (')',))
            if screen.mode.is_text_mode:
                raise error.RunError(error.IFC)
            return numbers.Integer().from_int(screen.drawing.point(
                            (self.values.to_value(self.values.to_single(arg0)),
                             self.values.to_value(self.values.to_single(arg1)), False)
                             ))
        else:
            # single-argument mode
            util.require_read(ins, (')',))
            try:
                x, y = screen.drawing.last_point
                fn = self.values.to_int(arg0)
                if fn == 0:
                    return numbers.Integer().from_int(x)
                elif fn == 1:
                    return numbers.Integer().from_int(y)
                elif fn == 2:
                    fx, _ = screen.drawing.get_window_logical(x, y)
                    return self.values.from_value(fx, '!')
                elif fn == 3:
                    _, fy = screen.drawing.get_window_logical(x, y)
                    return self.values.from_value(fy, '!')
            except AttributeError:
                return self.values.null(values.INT)

    def value_pmap(self, ins):
        """PMAP: convert between logical and physical coordinates."""
        util.require_read(ins, ('(',))
        coord = self.parser.parse_expression(ins)
        util.require_read(ins, (',',))
        mode = self.values.to_int(self.parser.parse_expression(ins))
        util.require_read(ins, (')',))
        error.range_check(0, 3, mode)
        screen = self.session.screen
        if screen.mode.is_text_mode:
            return self.values.null(values.INT)
        if mode == 0:
            value, _ = screen.drawing.get_window_physical(self.values.to_value(self.values.to_single(coord)), 0.)
            return numbers.Integer().from_int(value)
        elif mode == 1:
            _, value = screen.drawing.get_window_physical(0., self.values.to_value(self.values.to_single(coord)))
            return numbers.Integer().from_int(value)
        elif mode == 2:
            value, _ = screen.drawing.get_window_logical(self.values.to_int(coord), 0)
            return self.values.from_value(value, '!')
        elif mode == 3:
            _, value = screen.drawing.get_window_logical(0, self.values.to_int(coord))
            return self.values.from_value(value, '!')

    #####################################################################
    # sound functions

    def value_play(self, ins):
        """PLAY: get length of music queue."""
        voice = self.values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 255, voice)
        if not(self.parser.syntax in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return numbers.Integer().from_int(self.session.sound.queue_length(voice))

    #####################################################################
    # error functions

    def value_erl(self, ins):
        """ERL: get line number of last error."""
        if self.parser.error_pos == 0:
            erl = 0
        elif self.parser.error_pos == -1:
            erl = 65535
        else:
            erl = self.session.program.get_line_number(self.parser.error_pos)
        return self.values.from_value(erl, '!')

    def value_err(self, ins):
        """ERR: get error code of last error."""
        return numbers.Integer().from_int(self.parser.error_num)

    #####################################################################
    # pen, stick and strig

    def value_pen(self, ins):
        """PEN: poll the light pen."""
        fn = self.values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 9, fn)
        pen = self.session.pen.poll(fn)
        if pen is None or not self.session.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return numbers.Integer().from_int(pen)

    def value_stick(self, ins):
        """STICK: poll the joystick."""
        fn = self.values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, fn)
        return numbers.Integer().from_int(self.session.stick.poll(fn))

    def value_strig(self, ins):
        """STRIG: poll the joystick fire button."""
        fn = self.values.to_int(self.parser.parse_bracket(ins))
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        error.range_check(0, 7, fn)
        return self.values.from_bool(self.session.stick.poll_trigger(fn))

    #########################################################
    # memory and machine

    def value_fre(self, ins):
        """FRE: get free memory and optionally collect garbage."""
        val = self.parser.parse_bracket(ins)
        if isinstance(val, strings.String):
            # grabge collection if a string-valued argument is specified.
            self.session.memory.collect_garbage()
        return self.values.from_value(self.session.memory.get_free(), '!')

    def value_peek(self, ins):
        """PEEK: read memory location."""
        addr = self.values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        return numbers.Integer().from_int(self.session.all_memory.peek(addr))

    def value_varptr(self, ins):
        """VARPTR, VARPTR$: get memory address for variable or FCB."""
        dollar = util.skip_white_read_if(ins, ('$',))
        util.require_read(ins, ('(',))
        if (not dollar) and util.skip_white(ins) == '#':
            filenum = self.parser.parse_file_number_opthash(ins)
            var_ptr = self.session.memory.varptr_file(filenum)
        else:
            name, indices = self.parser.parse_variable(ins)
            var_ptr = self.session.memory.varptr(name, indices)
        util.require_read(ins, (')',))
        if var_ptr < 0:
            raise error.RunError(error.IFC)
        if dollar:
            var_ptr_str = struct.pack('<BH', values.size_bytes(name), var_ptr)
            return self.values.from_value(var_ptr_str, values.STR)
        else:
            return numbers.Integer().from_int(var_ptr, unsigned=True)

    def value_usr(self, ins):
        """USR: get value of machine-code function; not implemented."""
        util.require_read(ins, tk.digit)
        self.parser.parse_bracket(ins)
        logging.warning("USR function not implemented.")
        return self.values.null(values.INT)

    def value_inp(self, ins):
        """INP: get value from machine port."""
        port = self.values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        return numbers.Integer().from_int(self.session.machine.inp(port))

    def value_erdev(self, ins):
        """ERDEV$: device error string; not implemented."""
        if util.skip_white_read_if(ins, ('$',)):
            logging.warning("ERDEV$ function not implemented.")
            return self.values.null(values.STR)
        else:
            logging.warning("ERDEV function not implemented.")
            return self.values.null(values.INT)

    def value_exterr(self, ins):
        """EXTERR: device error information; not implemented."""
        x = self.values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, x)
        logging.warning("EXTERR function not implemented.")
        return self.values.null(values.INT)

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = self.parser.parse_file_number_opthash(ins)
        util.require_read(ins, (')',))
        self.session.files.get(num)
        logging.warning("IOCTL$ function not implemented.")
        raise error.RunError(error.IFC)

    ###########################################################
    # unary functions

    def value_func(self, ins, fn):
        """Return value of unary function."""
        return fn(self.parser.parse_bracket(ins))

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if util.skip_white(ins) == '(':
            return self.session.randomiser.rnd(self.values.to_single(self.parser.parse_bracket(ins)))
        else:
            return self.session.randomiser.rnd()
