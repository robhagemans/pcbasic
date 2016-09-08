"""
PC-BASIC - functions.py
BASIC functions.

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from functools import partial
import logging
import struct

from . import values
from . import dos
from . import error
from . import tokens as tk


class Functions(object):
    """BASIC functions."""

    def __init__(self, parser):
        """Initialise function context."""
        self.parser = parser
        self.session = parser.session
        self.values = self.session.values
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
            tk.CVI: partial(self.value_func, fn=values.cvi_),
            tk.CVS: partial(self.value_func, fn=values.cvs_),
            tk.CVD: partial(self.value_func, fn=values.cvd_),
            tk.MKI: partial(self.value_func, fn=values.mki_),
            tk.MKS: partial(self.value_func, fn=values.mks_),
            tk.MKD: partial(self.value_func, fn=values.mkd_),
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
            tk.SGN: partial(self.value_func, fn=values.sgn_),
            tk.INT: partial(self.value_func, fn=values.int_),
            tk.ABS: partial(self.value_func, fn=values.abs_),
            tk.SQR: partial(self.value_func, fn=values.sqr_),
            tk.RND: self.value_rnd,
            tk.SIN: partial(self.value_func, fn=values.sin_),
            tk.LOG: partial(self.value_func, fn=values.log_),
            tk.EXP: partial(self.value_func, fn=values.exp_),
            tk.COS: partial(self.value_func, fn=values.cos_),
            tk.TAN: partial(self.value_func, fn=values.tan_),
            tk.ATN: partial(self.value_func, fn=values.atn_),
            tk.FRE: self.value_fre,
            tk.INP: self.value_inp,
            tk.POS: self.value_pos,
            tk.LEN: partial(self.value_func, fn=values.len_),
            tk.STR: partial(self.value_func, fn=values.str_),
            tk.VAL: partial(self.value_func, fn=values.val_),
            tk.ASC: partial(self.value_func, fn=values.asc_),
            tk.CHR: partial(self.value_func, fn=values.chr_),
            tk.PEEK: self.value_peek,
            tk.SPACE: partial(self.value_func, fn=values.space_),
            tk.OCT: partial(self.value_func, fn=values.oct_),
            tk.HEX: partial(self.value_func, fn=values.hex_),
            tk.LPOS: self.value_lpos,
            tk.CINT: partial(self.value_func, fn=values.cint_),
            tk.CSNG: partial(self.value_func, fn=values.csng_),
            tk.CDBL: partial(self.value_func, fn=values.cdbl_),
            tk.FIX: partial(self.value_func, fn=values.fix_),
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


    ###########################################################
    # unary functions

    def value_func(self, ins, fn):
        """Return value of unary function."""
        return fn(self.parser.parse_bracket(ins))

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if ins.skip_blank() == '(':
            return self.session.randomiser.rnd(values.csng_(self.parser.parse_bracket(ins)))
        else:
            return self.session.randomiser.rnd()


    ######################################################################
    # string functions

    def value_instr(self, ins):
        """INSTR: find substring in string."""
        ins.require_read(('(',))
        # followed by comma so empty will raise STX
        s = self.parser.parse_expression(ins)
        n = 1
        if s[0] != '$':
            n = values.to_int(s)
            error.range_check(1, 255, n)
            ins.require_read((',',))
            s = self.parser.parse_expression(ins, empty_err=error.STX)
        big = values.pass_string(s)
        ins.require_read((',',))
        s = self.parser.parse_expression(ins, empty_err=error.STX)
        small = values.pass_string(s)
        ins.require_read((')',))
        return big.instr(small)

    def value_mid(self, ins):
        """MID$: get substring."""
        ins.require_read(('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        ins.require_read((',',))
        start = values.cint_(self.parser.parse_expression(ins))
        num = None
        if ins.skip_blank_read_if((',',)):
            num = values.cint_(self.parser.parse_expression(ins))
        ins.require_read((')',))
        return s.mid(start, num)

    def value_left(self, ins):
        """LEFT$: get substring at the start of string."""
        ins.require_read(('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        ins.require_read((',',))
        stop = values.cint_(self.parser.parse_expression(ins))
        ins.require_read((')',))
        return s.left(stop)

    def value_right(self, ins):
        """RIGHT$: get substring at the end of string."""
        ins.require_read(('(',))
        s = values.pass_string(self.parser.parse_expression(ins))
        ins.require_read((',',))
        stop = values.cint_(self.parser.parse_expression(ins))
        ins.require_read((')',))
        return s.right(stop)

    def value_string(self, ins):
        """STRING$: repeat characters."""
        ins.require_read(('(',))
        n = values.to_int(self.parser.parse_expression(ins))
        error.range_check(0, 255, n)
        ins.require_read((',',))
        asc_value_or_char = self.parser.parse_expression(ins)
        strstr = self.values.new_string().repeat(asc_value_or_char, n)
        ins.require_read((')',))
        return strstr

    ######################################################################
    # console functions

    def value_screen(self, ins):
        """SCREEN: get char or attribute at a location."""
        ins.require_read(('(',))
        row = values.to_int(self.parser.parse_expression(ins))
        ins.require_read((',',), err=error.IFC)
        col = values.to_int(self.parser.parse_expression(ins))
        z = 0
        if ins.skip_blank_read_if((',',)):
            z = values.to_int(self.parser.parse_expression(ins))
        cmode = self.session.screen.mode
        error.range_check(1, cmode.height, row)
        if self.session.screen.view_set:
            error.range_check(self.session.screen.view_start, self.session.screen.scroll_height, row)
        error.range_check(1, cmode.width, col)
        error.range_check(0, 255, z)
        ins.require_read((')',))
        if z and not cmode.is_text_mode:
            return self.values.new_integer()
        else:
            return self.values.from_value(self.session.screen.apage.get_char_attr(row, col, z!=0), values.INT)

    def value_input(self, ins):
        """INPUT$: get characters from the keyboard or a file."""
        ins.require_read(('$',))
        ins.require_read(('(',))
        num = values.to_int(self.parser.parse_expression(ins))
        error.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if ins.skip_blank_read_if((',',)):
            infile = self.session.files.get(self.parser.parse_file_number(ins, opt_hash=True))
        ins.require_read((')',))
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
        return self.values.from_value(row, values.INT)

    def value_pos(self, ins):
        """POS: get the current screen column."""
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        self.parser.parse_bracket(ins)
        col = self.session.screen.current_col
        if col == self.session.screen.mode.width and self.session.screen.overflow:
            # in overflow position, return column 1.
            col = 1
        return self.values.from_value(col, values.INT)

    def value_lpos(self, ins):
        """LPOS: get the current printer column."""
        num = values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, num)
        printer = self.session.devices.devices['LPT' + max(1, num) + ':']
        if printer.device_file:
            return self.values.from_value(printer.device_file.col, values.INT)
        return self.values.from_value(1, values.INT)

    ######################################################################
    # file access

    def value_loc(self, ins):
        """LOC: get file pointer."""
        ins.skip_blank()
        num = values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return self.values.from_value(the_file.loc(), '!')

    def value_eof(self, ins):
        """EOF: get end-of-file."""
        ins.skip_blank()
        num = values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        if num == 0:
            return self.values.new_integer()
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num, 'IR')
        return self.values.from_bool(the_file.eof())

    def value_lof(self, ins):
        """LOF: get length of file."""
        ins.skip_blank()
        num = values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return self.values.from_value(the_file.lof(), '!')


    ######################################################################
    # env, time and date functions

    def value_environ(self, ins):
        """ENVIRON$: get environment string."""
        ins.require_read(('$',))
        expr = self.parser.parse_bracket(ins)
        if isinstance(expr, values.String):
            return self.values.from_value(dos.get_env(expr.to_str()), values.STR)
        else:
            expr = values.to_int(expr)
            error.range_check(1, 255, expr)
            return self.values.from_value(dos.get_env_entry(expr), values.STR)

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
        return self.session.user_functions.value(fnname, self.parser, ins)

    ###############################################################
    # graphics

    def value_point(self, ins):
        """POINT: get pixel attribute at screen location."""
        ins.require_read(('(',))
        arg0 = self.parser.parse_expression(ins)
        screen = self.session.screen
        if ins.skip_blank_read_if((',',)):
            # two-argument mode
            arg1 = self.parser.parse_expression(ins)
            ins.require_read((')',))
            if screen.mode.is_text_mode:
                raise error.RunError(error.IFC)
            return self.values.from_value(
                        screen.drawing.point((
                            values.csng_(arg0).to_value(), values.csng_(arg1).to_value(), False)
                        ), values.INT)
        else:
            # single-argument mode
            ins.require_read((')',))
            try:
                x, y = screen.drawing.last_point
                fn = values.to_int(arg0)
                if fn == 0:
                    return self.values.from_value(x, values.INT)
                elif fn == 1:
                    return self.values.from_value(y, values.INT)
                elif fn == 2:
                    fx, _ = screen.drawing.get_window_logical(x, y)
                    return self.values.from_value(fx, '!')
                elif fn == 3:
                    _, fy = screen.drawing.get_window_logical(x, y)
                    return self.values.from_value(fy, '!')
            except AttributeError:
                return self.values.new_integer()

    def value_pmap(self, ins):
        """PMAP: convert between logical and physical coordinates."""
        ins.require_read(('(',))
        coord = self.parser.parse_expression(ins)
        ins.require_read((',',))
        mode = values.to_int(self.parser.parse_expression(ins))
        ins.require_read((')',))
        error.range_check(0, 3, mode)
        screen = self.session.screen
        if screen.mode.is_text_mode:
            return self.values.new_integer()
        if mode == 0:
            value, _ = screen.drawing.get_window_physical(values.csng_(coord).to_value(), 0.)
            return self.values.from_value(value, values.INT)
        elif mode == 1:
            _, value = screen.drawing.get_window_physical(0., values.csng_(coord).to_value())
            return self.values.from_value(value, values.INT)
        elif mode == 2:
            value, _ = screen.drawing.get_window_logical(values.to_int(coord), 0)
            return self.values.from_value(value, '!')
        elif mode == 3:
            _, value = screen.drawing.get_window_logical(0, values.to_int(coord))
            return self.values.from_value(value, '!')

    #####################################################################
    # sound functions

    def value_play(self, ins):
        """PLAY: get length of music queue."""
        voice = values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 255, voice)
        if not(self.parser.syntax in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return self.values.from_value(self.session.sound.queue_length(voice), values.INT)

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
        return self.values.from_value(self.parser.error_num, values.INT)

    #####################################################################
    # pen, stick and strig

    def value_pen(self, ins):
        """PEN: poll the light pen."""
        fn = values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 9, fn)
        pen = self.session.pen.poll(fn)
        if pen is None or not self.session.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return self.values.from_value(pen, values.INT)

    def value_stick(self, ins):
        """STICK: poll the joystick."""
        fn = values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, fn)
        return self.values.from_value(self.session.stick.poll(fn), values.INT)

    def value_strig(self, ins):
        """STRIG: poll the joystick fire button."""
        fn = values.to_int(self.parser.parse_bracket(ins))
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        error.range_check(0, 7, fn)
        return self.values.from_bool(self.session.stick.poll_trigger(fn))

    #########################################################
    # memory and machine

    def value_fre(self, ins):
        """FRE: get free memory and optionally collect garbage."""
        val = self.parser.parse_bracket(ins)
        if isinstance(val, values.String):
            # grabge collection if a string-valued argument is specified.
            self.session.memory.collect_garbage()
        return self.values.from_value(self.session.memory.get_free(), '!')

    def value_peek(self, ins):
        """PEEK: read memory location."""
        addr = values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        return self.values.from_value(self.session.all_memory.peek(addr), values.INT)

    def value_varptr(self, ins):
        """VARPTR, VARPTR$: get memory address for variable or FCB."""
        dollar = ins.skip_blank_read_if(('$',))
        ins.require_read(('(',))
        if (not dollar) and ins.skip_blank() == '#':
            filenum = self.parser.parse_file_number(ins, opt_hash=False)
            var_ptr = self.session.memory.varptr_file(filenum)
        else:
            name, indices = self.parser.parse_variable(ins)
            var_ptr = self.session.memory.varptr(name, indices)
        ins.require_read((')',))
        if var_ptr < 0:
            raise error.RunError(error.IFC)
        if dollar:
            var_ptr_str = struct.pack('<BH', values.size_bytes(name), var_ptr)
            return self.values.from_value(var_ptr_str, values.STR)
        else:
            return self.values.new_integer().from_int(var_ptr, unsigned=True)

    def value_usr(self, ins):
        """USR: get value of machine-code function; not implemented."""
        ins.require_read(tk.DIGIT)
        self.parser.parse_bracket(ins)
        logging.warning("USR function not implemented.")
        return self.values.new_integer()

    def value_inp(self, ins):
        """INP: get value from machine port."""
        port = values.to_int(self.parser.parse_bracket(ins), unsigned=True)
        return self.values.new_integer().from_int(self.session.machine.inp(port), unsigned=True)

    def value_erdev(self, ins):
        """ERDEV$: device error string; not implemented."""
        if ins.skip_blank_read_if(('$',)):
            logging.warning("ERDEV$ function not implemented.")
            return self.values.new_string()
        else:
            logging.warning("ERDEV function not implemented.")
            return self.values.new_integer()

    def value_exterr(self, ins):
        """EXTERR: device error information; not implemented."""
        x = values.to_int(self.parser.parse_bracket(ins))
        error.range_check(0, 3, x)
        logging.warning("EXTERR function not implemented.")
        return self.values.new_integer()

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        ins.require_read(('$',))
        ins.require_read(('(',))
        num = self.parser.parse_file_number(ins, opt_hash=True)
        ins.require_read((')',))
        self.session.files.get(num)
        logging.warning("IOCTL$ function not implemented.")
        raise error.RunError(error.IFC)
