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

    #######################################################
    # user-defined functions

    def value_fn(self, ins):
        """FN: get value of user-defined function."""
        fnname = self.parser.parse_scalar(ins)
        return self.session.user_functions.value(fnname, self.parser, ins)

    ###########################################################
    # nullary functions

    def value_inkey(self, ins):
        """INKEY$: get a character from the keyboard."""
        return self.values.from_value(self.session.keyboard.get_char(), values.STR)

    def value_csrlin(self, ins):
        """CSRLIN: get the current screen row."""
        return self.values.from_value(self.session.sceen.csrlin_(), values.INT)

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if ins.skip_blank() == '(':
            return self.session.randomiser.rnd(values.csng_(self.parser.parse_bracket(ins)))
        else:
            return self.session.randomiser.rnd()

    def value_erl(self, ins):
        """ERL: get line number of last error."""
        return self.values.from_value(self.parser.erl_(), values.SNG)

    def value_err(self, ins):
        """ERR: get error code of last error."""
        return self.values.from_value(self.parser.err_(), values.INT)

    def value_timer(self, ins):
        """TIMER: get clock ticks since midnight."""
        # precision of GWBASIC TIMER is about 1/20 of a second
        return self.values.from_value(self.session.clock.timer_(), values.SNG)

    def value_time(self, ins):
        """TIME$: get current system time."""
        return self.values.from_value(self.session.clock.time_fn_(), values.STR)

    def value_date(self, ins):
        """DATE$: get current system date."""
        return self.values.from_value(self.session.clock.date_fn_(), values.STR)

    ###########################################################
    # unary functions

    def value_func(self, ins, fn):
        """Return value of unary function."""
        return fn(self.parser.parse_bracket(ins))

    def value_pos(self, ins):
        """POS: get the current screen column."""
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        dummy = self.parser.parse_bracket(ins)
        pos = self.session.sceen.pos_(dummy)
        return self.values.from_value(pos, values.INT)

    def value_lpos(self, ins):
        """LPOS: get the current printer column."""
        num = self.parser.parse_bracket(ins)
        lpos = self.session.files.lpos_(num)
        return self.values.from_value(lpos, values.INT)

    def value_loc(self, ins):
        """LOC: get file pointer."""
        num = self.parser.parse_bracket(ins)
        loc = self.session.files.loc_(num)
        return self.values.from_value(loc, values.SNG)

    def value_eof(self, ins):
        """EOF: get end-of-file."""
        num = self.parser.parse_bracket(ins)
        eof = self.session.files.eof_(num)
        return self.values.from_bool(eof)

    def value_lof(self, ins):
        """LOF: get length of file."""
        num = self.parser.parse_bracket(ins)
        lof = self.session.files.lof_(num)
        return self.values.from_value(lof, values.SNG)

    def value_inp(self, ins):
        """INP: get value from machine port."""
        num = self.parser.parse_bracket(ins)
        inp = self.session.machine.inp_(num)
        return self.values.new_integer().from_int(inp, unsigned=True)

    def value_fre(self, ins):
        """FRE: get free memory and optionally collect garbage."""
        val = self.parser.parse_bracket(ins)
        fre = self.session.memory.fre_(val)
        return self.values.from_value(fre, values.SNG)

    def value_exterr(self, ins):
        """EXTERR: device error information; not implemented."""
        val = self.parser.parse_bracket(ins)
        exterr = self.session.devices.exterr_(val)
        return self.values.from_value(exterr, values.INT)

    def value_play(self, ins):
        """PLAY: get length of music queue."""
        voice = values.to_int(self.parser.parse_bracket(ins))
        play = self.session.sound.play_(voice)
        return self.values.from_value(play, values.INT)

    def value_stick(self, ins):
        """STICK: poll the joystick."""
        fn = self.parser.parse_bracket(ins)
        stick = self.session.stick.stick_(fn)
        return self.values.from_value(stick, values.INT)

    def value_strig(self, ins):
        """STRIG: poll the joystick fire button."""
        fn = self.parser.parse_bracket(ins)
        strig = self.session.stick.strig_(fn)
        return self.values.from_bool(strig)

    def value_pen(self, ins):
        """PEN: poll the light pen."""
        fn = self.parser.parse_bracket(ins)
        pen = self.session.pen.pen_(fn)
        if not self.session.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return self.values.from_value(pen, values.INT)

    def value_usr(self, ins):
        """USR: get value of machine-code function; not implemented."""
        ins.require_read(tk.DIGIT)
        num = self.parser.parse_bracket(ins)
        usr = self.session.machine.usr_(num)
        return self.values.from_value(usr, values.SNG)

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        ins.require_read(('$',))
        ins.require_read(('(',))
        num = self.parser.parse_file_number(ins, opt_hash=True)
        ins.require_read((')',))
        return self.session.files.ioctl_(num)

    def value_erdev(self, ins):
        """ERDEV$: device error string; not implemented."""
        dollar = ins.skip_blank_read_if(('$',))
        val = self.parser.parse_bracket(ins)
        if dollar:
            erdev = self.session.devices.erdev_str_(val)
            return self.values.from_value(erdev, values.STR)
        else:
            erdev = self.session.devices.erdev_(val)
            return self.values.from_value(erdev, values.INT)

    def value_environ(self, ins):
        """ENVIRON$: get environment string."""
        ins.require_read(('$',))
        expr = self.parser.parse_bracket(ins)
        environ = dos.environ_(expr)
        return self.values.from_value(environ, values.STR)


    ######################################################################
    # binary string functions

    def value_instr(self, ins):
        """INSTR: find substring in string."""
        ins.require_read(('(',))
        # followed by comma so empty will raise STX
        s = self.parser.parse_expression(ins)
        n = 1
        if isinstance(s, values.String):
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
        if isinstance(asc_value_or_char, values.Integer):
            error.range_check(0, 255, asc_value_or_char.to_int())
        ins.require_read((')',))
        return self.values.new_string().string_(asc_value_or_char, n)

    ######################################################################
    # console functions

    def value_screen(self, ins):
        """SCREEN: get char or attribute at a location."""
        ins.require_read(('(',))
        row = values.to_int(self.parser.parse_expression(ins))
        ins.require_read((',',), err=error.IFC)
        col = values.to_int(self.parser.parse_expression(ins))
        want_attr = None
        if ins.skip_blank_read_if((',',)):
            want_attr = values.to_int(self.parser.parse_expression(ins))
        screen = self.session.screen.screen_fn_(row, col, want_attr)
        ins.require_read((')',))
        return self.values.from_value(screen, values.INT)

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
        word = infile.input_(num)
        return self.values.from_value(word, values.STR)

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

    #########################################################
    # memory and machine

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
