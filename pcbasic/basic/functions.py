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

    def init_functions(self):
        """Initialise functions."""
        self.with_presign = {
            # token   range   optional   function
            tk.USR: {
                None: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_0: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_1: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_2: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_3: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_4: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_5: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_6: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_7: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_8: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
                tk.C_9: partial(self.value_unary, fn=self.session.machine.usr_, to_type=values.SNG),
            },
            tk.IOCTL: {
                '$': self.value_ioctl,
            },
            tk.ENVIRON: {
                '$': partial(self.value_unary, fn=dos.environ_, to_type=values.STR),
            },
            tk.INPUT: {
                '$': self.value_input,
            },
            tk.ERDEV: {
                '$': partial(self.value_unary, fn=self.session.devices.erdev_str_, to_type=values.STR),
                None: partial(self.value_unary, fn=self.session.devices.erdev_, to_type=values.INT),
            },
            tk.VARPTR: {
                '$': self.value_varptr_str,
                None: self.value_varptr,
            },
        }
        self.functions = {
            tk.SCREEN: self.value_screen,
            tk.FN: self.value_fn,
            tk.ERL: partial(self.value_nullary, fn=self.parser.erl_, to_type=values.SNG),
            tk.ERR: partial(self.value_nullary, fn=self.parser.err_, to_type=values.INT),
            tk.STRING: self.value_string,
            tk.INSTR: self.value_instr,
            tk.CSRLIN: partial(self.value_nullary, fn=self.session.screen.csrlin_, to_type=values.INT),
            tk.POINT: self.value_point,
            tk.INKEY: partial(self.value_nullary, fn=self.session.keyboard.get_char, to_type=values.STR),
            tk.CVI: partial(self.value_func, fn=values.cvi_),
            tk.CVS: partial(self.value_func, fn=values.cvs_),
            tk.CVD: partial(self.value_func, fn=values.cvd_),
            tk.MKI: partial(self.value_func, fn=values.mki_),
            tk.MKS: partial(self.value_func, fn=values.mks_),
            tk.MKD: partial(self.value_func, fn=values.mkd_),
            tk.EXTERR: partial(self.value_unary, fn=self.session.devices.exterr_, to_type=values.INT),
            tk.DATE: partial(self.value_nullary, fn=self.session.clock.date_fn_, to_type=values.STR),
            tk.TIME: partial(self.value_nullary, fn=self.session.clock.time_fn_, to_type=values.STR),
            tk.PLAY: partial(self.value_unary, fn=self.session.sound.play_fn_, to_type=values.INT),
            tk.TIMER: partial(self.value_nullary, fn=self.session.clock.timer_, to_type=values.SNG),
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
            tk.FRE: partial(self.value_unary, fn=self.session.memory.fre_, to_type=values.SNG),
            tk.INP: partial(self.value_unary, fn=self.session.machine.inp_, to_type=values.INT),
            tk.POS: partial(self.value_unary, fn=self.session.screen.pos_, to_type=values.INT),
            tk.LEN: partial(self.value_func, fn=values.len_),
            tk.STR: partial(self.value_func, fn=values.str_),
            tk.VAL: partial(self.value_func, fn=values.val_),
            tk.ASC: partial(self.value_func, fn=values.asc_),
            tk.CHR: partial(self.value_func, fn=values.chr_),
            tk.PEEK: partial(self.value_unary, fn=self.session.all_memory.peek_, to_type=values.INT),
            tk.SPACE: partial(self.value_func, fn=values.space_),
            tk.OCT: partial(self.value_func, fn=values.oct_),
            tk.HEX: partial(self.value_func, fn=values.hex_),
            tk.LPOS: partial(self.value_unary, fn=self.session.files.lpos_, to_type=values.INT),
            tk.CINT: partial(self.value_func, fn=values.cint_),
            tk.CSNG: partial(self.value_func, fn=values.csng_),
            tk.CDBL: partial(self.value_func, fn=values.cdbl_),
            tk.FIX: partial(self.value_func, fn=values.fix_),
            tk.PEN: partial(self.value_unary, fn=self.session.events.pen.pen_, to_type=values.INT),
            tk.STICK: partial(self.value_unary, fn=self.session.stick.stick_, to_type=values.INT),
            tk.STRIG: partial(self.value_unary, fn=self.session.stick.strig_, to_type=values.INT),
            tk.EOF: partial(self.value_unary, fn=self.session.files.eof_, to_type=values.INT),
            tk.LOC: partial(self.value_unary, fn=self.session.files.loc_, to_type=values.SNG),
            tk.LOF: partial(self.value_unary, fn=self.session.files.lof_, to_type=values.SNG),
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # functools.partial objects and functions can't be pickled
        pickle_dict['functions'] = None
        pickle_dict['with_presign'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)

    ###########################################################
    # generalised calls

    def value_nullary(self, dummy_ins, fn, to_type):
        """Get value of a function with no arguments and convert to BASIC value."""
        # NOTE that this wrapper is only necessary to introduce a dummy argument
        # for the dictionary-based call
        return self.values.from_value(fn(), to_type)

    def value_unary(self, ins, fn, to_type):
        """Get value of a function with one arguments and convert to BASIC value."""
        return self.values.from_value(fn(self.parser.parse_bracket(ins)), to_type)

    def value_func(self, ins, fn):
        """Return value of unary function requiring no conversion."""
        return fn(self.parser.parse_bracket(ins))

    #######################################################
    # user-defined functions

    def value_fn(self, ins):
        """FN: get value of user-defined function."""
        fnname = self.parser.parse_scalar(ins)
        return self.session.user_functions.value(fnname, self.parser, ins)

    ###########################################################
    # special cases

    def value_varptr(self, ins):
        """VARPTR: get memory address for variable or FCB."""
        ins.require_read(('(',))
        if ins.skip_blank() == '#':
            # params holds a number
            params = self.parser.parse_file_number(ins, opt_hash=False)
        else:
            # params holds a tuple
            params = self.parser.parse_variable(ins)
        ins.require_read((')',))
        var_ptr = self.session.memory.varptr_(params)
        return self.values.from_value(var_ptr, values.INT)

    def value_varptr_str(self, ins):
        """VARPTR$: get memory address for variable."""
        ins.require_read(('(',))
        name, indices = self.parser.parse_variable(ins)
        ins.require_read((')',))
        var_ptr_str = self.session.memory.varptr_str_(name, indices)
        return self.values.from_value(var_ptr_str, values.STR)

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        ins.require_read(('(',))
        num = self.parser.parse_file_number(ins, opt_hash=True)
        ins.require_read((')',))
        return self.session.files.ioctl_(num)

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

    ######################################################################
    # binary functions

    def value_left(self, ins):
        """LEFT$: get substring at the start of string."""
        s, stop = self.parser.parse_argument_list(ins, values.pass_string, values.cint_)
        return values.left_(s, stop)

    def value_right(self, ins):
        """RIGHT$: get substring at the end of string."""
        s, stop = self.parser.parse_argument_list(ins, values.pass_string, values.cint_)
        return values.right_(s, stop)

    def value_pmap(self, ins):
        """PMAP: convert between logical and physical coordinates."""
        coord, mode = self.parser.parse_argument_list(ins, values.cint_, values.cint_)
        return self.session.screen.drawing.pmap_(coord, mode)

    ###########################################################################
    # functions with optional arguments

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if ins.skip_blank() == '(':
            return self.session.randomiser.rnd(values.csng_(self.parser.parse_bracket(ins)))
        else:
            return self.session.randomiser.rnd()

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
        ins.require_read(('(',))
        num = values.to_int(self.parser.parse_expression(ins))
        error.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if ins.skip_blank_read_if((',',)):
            infile = self.session.files.get(self.parser.parse_file_number(ins, opt_hash=True))
        ins.require_read((')',))
        word = infile.input_(num)
        return self.values.from_value(word, values.STR)

    def value_point(self, ins):
        """POINT: get pixel attribute at screen location."""
        ins.require_read(('(',))
        arg0 = self.parser.parse_expression(ins)
        if ins.skip_blank_read_if((',',)):
            # two-argument mode
            arg1 = self.parser.parse_expression(ins)
            ins.require_read((')',))
            screen = self.session.screen.drawing.point_2_(arg0, arg1)
            return self.values.from_value(screen, values.INT)
        else:
            # single-argument mode
            ins.require_read((')',))
            screen = self.session.screen.drawing.point_1_(arg0)
            return self.values.from_value(screen, values.SNG)
