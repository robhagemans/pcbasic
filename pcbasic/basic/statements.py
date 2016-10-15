"""
PC-BASIC - statements.py
Statement parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging
import string
import struct
import io
from functools import partial

from . import error
from . import values
from . import ports
from . import tokens as tk
from . import dos


class StatementParser(object):
    """BASIC statements."""

    def __init__(self, values, temp_string, memory, expression_parser, syntax):
        """Initialise statement context."""
        # syntax: advanced, pcjr, tandy
        self.syntax = syntax
        self.values = values
        self.expression_parser = expression_parser
        # temporary string context guard
        self.temp_string = temp_string
        # data segment
        self.memory = memory
        self.run_mode = False

    def parse_statement(self, ins):
        """Parse and execute a single statement."""
        # read keyword token or one byte
        ins.skip_blank()
        c = ins.read_keyword_token()
        if c in self.statements:
            # statement token
            self.statements[c](ins)
        else:
            # implicit LET
            ins.seek(-len(c), 1)
            if c in string.ascii_letters:
                return self.statements[tk.LET](ins)
        ins.require_end()

    def parse_value(self, ins, sigil=None, allow_empty=False):
        """Read a value of required type and return as Python value, or None if empty."""
        expr = self.parse_expression(ins, allow_empty)
        if expr is not None:
            # this will force into the requested type; e.g. Integers may overflow
            return values.to_type(sigil, expr).to_value()
        return None

    def parse_bracket(self, ins):
        """Compute the value of the bracketed expression."""
        ins.require_read(('(',))
        # we'll get a Syntax error, not a Missing operand, if we close with )
        val = self.parse_expression(ins)
        ins.require_read((')',))
        return val

    def parse_temporary_string(self, ins, allow_empty=False):
        """Parse an expression and return as Python value. Store strings in a temporary."""
        # if allow_empty, a missing value is returned as an empty string
        with self.temp_string:
            expr = self.parse_expression(ins, allow_empty)
            if expr:
                return values.pass_string(expr).to_value()
            return self.values.new_string()

    def _parse_file_number(self, ins, opt_hash):
        """Read a file number."""
        if not ins.skip_blank_read_if(('#',)) and not opt_hash:
            return None
        number = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, number)
        return number

    def _parse_name(self, ins):
        """Get scalar part of variable name from token stream."""
        name = ins.read_name()
        # must not be empty
        error.throw_if(not name, error.STX)
        # append sigil, if missing
        return self.memory.complete_name(name)

    def _parse_variable(self, ins):
        """Helper function: parse a scalar or array element."""
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        # this is an evaluation-time determination
        # as we could have passed another DEFtype statement
        name = self.memory.complete_name(name)
        self.session.redo_on_break = True
        indices = self.expression_parser.parse_indices(ins)
        self.session.redo_on_break = False
        return name, indices

    def _parse_jumpnum(self, ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        ins.require_read((tk.T_UINT,))
        token = ins.read(2)
        assert len(token) == 2, 'Bytecode truncated in line number pointer'
        return struct.unpack('<H', token)[0]

    def _parse_optional_jumpnum(self, ins):
        """Parses a line number pointer as in GOTO, GOSUB, LIST, RENUM, EDIT, etc."""
        # no line number
        if ins.skip_blank() != tk.T_UINT:
            return -1
        return self._parse_jumpnum(ins)

    def parse_expression(self, ins, allow_empty=False):
        """Compute the value of the expression at the current code pointer."""
        if allow_empty and ins.skip_blank() in tk.END_EXPRESSION:
            return None
        self.session.redo_on_break = True
        val = self.expression_parser.parse(ins)
        self.session.redo_on_break = False
        return val

    ###########################################################################

    def set_runmode(self, new_runmode):
        """Keep track of runmode for protected and program-only statements."""
        self.run_mode = new_runmode

    def init_statements(self, session):
        """Initialise statements."""
        self.session = session
        self.statements = {
            tk.END: partial(self.exec_after_end, callback=session.end_),
            tk.FOR: self.exec_for,
            tk.NEXT: self.exec_next,
            tk.DATA: self.skip_statement,
            tk.INPUT: self.exec_input,
            tk.DIM: self.exec_dim,
            tk.READ: self.exec_read,
            tk.LET: partial(self.exec_args_iter, args_iter=self._parse_let_args_iter, callback=session.memory.let_),
            tk.GOTO: partial(self.exec_single_line_number, callback=session.interpreter.goto_),
            tk.RUN: self.exec_run,
            tk.IF: self.exec_if,
            tk.RESTORE: self.exec_restore,
            tk.GOSUB: partial(self.exec_single_line_number, callback=session.interpreter.gosub_),
            tk.RETURN: self.exec_return,
            tk.REM: self.skip_line,
            tk.STOP: partial(self.exec_after_end, callback=session.interpreter.stop_),
            tk.PRINT: partial(self.exec_args_iter, args_iter=partial(self._parse_print_args_iter, parse_file=True), callback=session.files.print_),
            tk.CLEAR: partial(self.exec_args_iter, args_iter=self._parse_clear_args_iter, callback=session.clear_),
            tk.LIST: self.exec_list,
            tk.NEW: partial(self.exec_after_end, callback=session.new_),
            tk.ON: self.exec_on,
            tk.WAIT: self.exec_wait,
            tk.DEF: self.exec_def,
            tk.POKE: self.exec_poke,
            tk.CONT: partial(self.exec_immediate, callback=session.interpreter.cont_),
            tk.OUT: self.exec_out,
            tk.LPRINT: partial(self.exec_args_iter, args_iter=partial(self._parse_print_args_iter, parse_file=False), callback=session.devices.lprint_),
            tk.LLIST: self.exec_llist,
            tk.WIDTH: partial(self.exec_args_iter, args_iter=self._parse_width_args_iter, callback=session.files.width_),
            tk.ELSE: self.skip_line,
            tk.TRON: partial(self.exec_immediate, callback=session.interpreter.tron_),
            tk.TROFF: partial(self.exec_immediate, callback=session.interpreter.troff_),
            tk.SWAP: self.exec_swap,
            tk.ERASE: self.exec_erase,
            tk.EDIT: self.exec_edit,
            tk.ERROR: self.exec_error,
            tk.RESUME: self.exec_resume,
            tk.DELETE: self.exec_delete,
            tk.AUTO: self.exec_auto,
            tk.RENUM: self.exec_renum,
            tk.DEFSTR: partial(self.exec_deftype, typechar='$'),
            tk.DEFINT: partial(self.exec_deftype, typechar='%'),
            tk.DEFSNG: partial(self.exec_deftype, typechar='!'),
            tk.DEFDBL: partial(self.exec_deftype, typechar='#'),
            tk.LINE: self.exec_line,
            tk.WHILE: partial(self.exec_immediate, callback=session.interpreter.while_),
            tk.WEND: partial(self.exec_after_end, callback=session.interpreter.wend_),
            tk.CALL: self.exec_call,
            tk.WRITE: partial(self.exec_args_iter, args_iter=self._parse_write_args_iter, callback=session.files.write_),
            tk.OPTION: self.exec_option,
            tk.RANDOMIZE: self.exec_randomize,
            tk.OPEN: self.exec_open,
            tk.CLOSE: self.exec_close,
            tk.LOAD: self.exec_load,
            tk.MERGE: partial(self.exec_single_string_arg, callback=session.merge_),
            tk.SAVE: self.exec_save,
            tk.COLOR: self.exec_color,
            tk.CLS: self.exec_cls,
            tk.MOTOR: partial(self.exec_lcopy_motor, callback=session.devices.motor_),
            tk.BSAVE: self.exec_bsave,
            tk.BLOAD: self.exec_bload,
            tk.SOUND: self.exec_sound,
            tk.BEEP: self.exec_beep,
            tk.PSET: self.exec_pset,
            tk.PRESET: self.exec_preset,
            tk.SCREEN: self.exec_screen,
            tk.KEY: self.exec_key,
            tk.LOCATE: self.exec_locate,
            tk.FILES: partial(self.exec_files_shell, callback=session.devices.files_),
            tk.FIELD: self.exec_field,
            tk.SYSTEM: partial(self.exec_after_end, callback=session.interpreter.system_),
            tk.NAME: self.exec_name,
            tk.LSET: self.exec_lset,
            tk.RSET: self.exec_rset,
            tk.KILL: partial(self.exec_single_string_arg, callback=session.devices.kill_),
            tk.PUT: self.exec_put,
            tk.GET: self.exec_get,
            tk.RESET: partial(self.exec_immediate, callback=session.files.reset_),
            tk.COMMON: self.exec_common,
            tk.CHAIN: self.exec_chain,
            tk.DATE: partial(self.exec_time_date, callback=session.clock.date_),
            tk.TIME: partial(self.exec_time_date, callback=session.clock.time_),
            tk.PAINT: self.exec_paint,
            tk.COM: self.exec_com,
            tk.CIRCLE: self.exec_circle,
            tk.DRAW: self.exec_draw,
            tk.PLAY: self.exec_play,
            tk.TIMER: partial(self.exec_pen_timer, callback=session.events.timer_),
            tk.IOCTL: self.exec_ioctl,
            tk.CHDIR: partial(self.exec_single_string_arg, callback=session.devices.chdir_),
            tk.MKDIR: partial(self.exec_single_string_arg, callback=session.devices.mkdir_),
            tk.RMDIR: partial(self.exec_single_string_arg, callback=session.devices.rmdir_),
            tk.SHELL: partial(self.exec_files_shell, callback=session.shell_),
            tk.ENVIRON: partial(self.exec_single_string_arg, callback=dos.environ_statement_),
            tk.VIEW: self.exec_view,
            tk.WINDOW: self.exec_window,
            tk.PALETTE: self.exec_palette,
            tk.LCOPY: partial(self.exec_lcopy_motor, callback=session.devices.lcopy_),
            tk.CALLS: self.exec_calls,
            tk.NOISE: self.exec_noise,
            tk.PCOPY: self.exec_pcopy,
            tk.TERM: partial(self.exec_after_end, callback=session.term_),
            tk.LOCK: self.exec_lock,
            tk.UNLOCK: self.exec_unlock,
            tk.MID: partial(self.exec_args_iter, args_iter=self._parse_mid_args_iter, callback=session.memory.mid_),
            tk.PEN: partial(self.exec_pen_timer, callback=session.events.pen_),
            tk.STRIG: self.exec_strig,
            '_': self.exec_extension,
        }
        self.extensions = {
            'DEBUG': partial(self.exec_single_string_arg, callback=session.debugger.debug_),
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['statements'] = None
        pickle_dict['extensions'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)

    ##########################################################
    # statements that require further qualification

    def exec_def(self, ins):
        """DEF: select DEF FN, DEF USR, DEF SEG."""
        c = ins.skip_blank()
        if ins.read_if(c, (tk.FN,)):
            self.exec_def_fn(ins)
        elif ins.read_if(c, (tk.USR,)):
            self.exec_def_usr(ins)
        # must be uppercase in tokenised form, otherwise syntax error
        elif ins.skip_blank_read_if(('SEG',), 3):
            self.exec_def_seg(ins)
        else:
            raise error.RunError(error.STX)

    def exec_view(self, ins):
        """VIEW: select VIEW PRINT, VIEW (graphics)."""
        if ins.skip_blank_read_if((tk.PRINT,)):
            self.exec_view_print(ins)
        else:
            self.exec_view_graph(ins)

    def exec_line(self, ins):
        """LINE: select LINE INPUT, LINE (graphics)."""
        if ins.skip_blank_read_if((tk.INPUT,)):
            self.exec_line_input(ins)
        else:
            self.exec_line_graph(ins)

    def exec_get(self, ins):
        """GET: select GET (graphics), GET (files)."""
        if ins.skip_blank() == '(':
            self.exec_get_graph(ins)
        else:
            self.exec_get_file(ins)

    def exec_put(self, ins):
        """PUT: select PUT (graphics), PUT (files)."""
        if ins.skip_blank() == '(':
            self.exec_put_graph(ins)
        else:
            self.exec_put_file(ins)

    def exec_on(self, ins):
        """ON: select ON ERROR, ON KEY, ON TIMER, ON PLAY, ON COM, ON PEN, ON STRIG
            or ON (jump statement)."""
        c = ins.skip_blank()
        if c in (tk.ERROR, tk.KEY, '\xFE', '\xFF'):
            token = ins.read_keyword_token()
            if token == tk.ERROR:
                ins.require_read((tk.GOTO,))
                self.exec_single_line_number(ins, callback=self.session.interpreter.on_error_goto_)
            else:
                self.exec_on_event(ins, token)
        else:
            self.exec_on_jump(ins)

    ###########################################################################
    # extension statements

    def exec_extension(self, ins):
        """Extension statement."""
        # This is not a GW-BASIC behaviour.
        word = ins.read_name()
        try:
            callback = self.extensions[word]
        except KeyError:
            raise error.RunError(error.STX)
        callback(ins)

    ###########################################################################
    # generalised callers

    def exec_immediate(self, ins, callback):
        """Execute before end-of-statement."""
        # e.g. TRON LAH raises error but TRON will have been executed
        callback()

    def exec_after_end(self, ins, callback):
        """Execute after end-of-statement."""
        # e.g. SYSTEM LAH does not execute
        ins.require_end()
        callback()

    ###########################################################################
    # skips

    def skip_line(self, ins):
        """Ignore the rest of the line."""
        ins.skip_to(tk.END_LINE)

    def skip_statement(self, ins):
        """Ignore rest of statement."""
        ins.skip_to(tk.END_STATEMENT)

    ###########################################################################
    # using iterable to parse arguments

    def exec_args_iter(self, ins, args_iter, callback):
        """Execute statement parsed by iterable."""
        callback(args_iter(ins))

    ###########################################################################
    # statements taking a single argument

    def exec_lcopy_motor(self, ins, callback):
        """Parse LCOPY and MOTOR syntax"""
        val = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            val = values.to_int(self.parse_expression(ins))
            error.range_check(0, 255, val)
            ins.require_end()
        callback(val)

    def exec_files_shell(self, ins, callback):
        """Execute statemnt with single optional string-valued argument."""
        arg = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            arg = self.parse_temporary_string(ins)
        callback(arg)

    def exec_single_string_arg(self, ins, callback):
        """Execute statement with single string-valued argument."""
        callback(self.parse_temporary_string(ins))

    def exec_randomize(self, ins):
        """RANDOMIZE: set random number generator seed."""
        val = self.parse_expression(ins, allow_empty=True)
        self.session.randomize_(val)

    def exec_error(self, ins):
        """ERROR: simulate an error condition."""
        errn = values.to_int(self.parse_expression(ins))
        error.error_(errn)

    ###########################################################################
    # Flow-control statements

    def exec_single_line_number(self, ins, callback):
        """Execute statement with single line number."""
        callback(self._parse_jumpnum(ins))

    def exec_return(self, ins):
        """RETURN: return from a subroutine."""
        # return *can* have a line number
        jumpnum = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            jumpnum = self._parse_jumpnum(ins)
        self.session.interpreter.return_(jumpnum)

    def exec_on_jump(self, ins):
        """ON: calculated jump."""
        onvar = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, onvar)
        command = ins.require_read((tk.GOTO, tk.GOSUB))
        skipped = 0
        if onvar in (0, 255):
            # if any provided, check all but jump to none
            while True:
                num = self._parse_optional_jumpnum(ins)
                if num == -1 or not ins.skip_blank_read_if((',',)):
                    ins.require_end()
                    return
        else:
            # only parse jumps (and errors!) up to our choice
            while skipped < onvar-1:
                self._parse_jumpnum(ins)
                skipped += 1
                if not ins.skip_blank_read_if((',',)):
                    ins.require_end()
                    return
            # parse our choice
            jumpnum = self._parse_jumpnum(ins)
            if command == tk.GOTO:
                self.session.interpreter.goto_(jumpnum)
            elif command == tk.GOSUB:
                self.session.interpreter.gosub_(jumpnum)

    def exec_run(self, ins):
        """RUN: start program execution."""
        c = ins.skip_blank()
        if c == tk.T_UINT:
            # parse line number and ignore rest of line
            args = self._parse_jumpnum(ins),
        elif c not in tk.END_STATEMENT:
            name = self.parse_temporary_string(ins)
            comma_r = ins.skip_blank_read_if((',R',))
            ins.require_end()
            args = name, comma_r
        else:
            args = ()
        self.session.run_(*args)

    def exec_resume(self, ins):
        """RESUME: resume program flow after error-trap."""
        if self.session.interpreter.error_resume is None:
            # unset error handler
            self.session.interpreter.on_error = 0
            raise error.RunError(error.RESUME_WITHOUT_ERROR)
        c = ins.skip_blank()
        if c == tk.NEXT:
            where = ins.read(1)
        elif c in tk.END_STATEMENT:
            where = None
        else:
            where = self._parse_jumpnum(ins)
        ins.require_end()
        self.session.interpreter.resume_(where)

    ###########################################################################
    # event switches (except PLAY)

    def exec_pen_timer(self, ins, callback):
        """Parse PEN or TIMER event switch statement."""
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        callback(command)

    def exec_strig(self, ins):
        """STRIG: switch on/off fire button event handling."""
        d = ins.require_read((tk.ON, tk.OFF, '('))
        if d == '(':
            # strig (n)
            num = values.to_int(self.parse_expression(ins))
            ins.require_read((')',))
            command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
            self.session.events.strig_(num, command)
        elif d in (tk.ON, tk.OFF):
            self.session.stick.strig_statement_(d)

    def exec_com(self, ins):
        """COM: switch on/off serial port event handling."""
        num = values.to_int(self.parse_bracket(ins))
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.com_(num, command)

    def exec_key_events(self, ins):
        """KEY: switch on/off keyboard events."""
        num = values.to_int(self.parse_bracket(ins))
        error.range_check(0, 255, num)
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.key_(num, command)

    ###########################################################################
    # event definitions

    def exec_on_event(self, ins, token):
        """Helper function for ON event trap definitions."""
        num = None
        if token != tk.PEN:
            num = self.parse_bracket(ins)
        elif token not in (tk.KEY, tk.TIMER, tk.PLAY, tk.COM, tk.STRIG):
            raise error.RunError(error.STX)
        ins.require_read((tk.GOSUB,))
        jumpnum = self._parse_jumpnum(ins)
        if jumpnum == 0:
            jumpnum = None
        elif jumpnum not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        ins.require_end()
        self.session.events.on_event_gosub_(token, num, jumpnum)

    ###########################################################################
    # sound

    def exec_beep(self, ins):
        """BEEP: produce an alert sound or switch internal speaker on/off."""
        command = None
        if self.syntax in ('pcjr', 'tandy'):
            # Tandy/PCjr BEEP ON, OFF
            command = ins.skip_blank_read_if((tk.ON, tk.OFF))
        self.session.sound.beep_(command)
        # if a syntax error happens, we still beeped.

    def exec_sound(self, ins):
        """SOUND: produce a sound or switch external speaker on/off."""
        command = None
        if self.syntax in ('pcjr', 'tandy'):
            # Tandy/PCjr SOUND ON, OFF
            command = ins.skip_blank_read_if((tk.ON, tk.OFF))
        if command:
            args = command,
            ins.require_end()
        else:
            freq = values.to_int(self.parse_expression(ins))
            ins.require_read((',',))
            dur = values.csng_(self.parse_expression(ins)).to_value()
            error.range_check(-65535, 65535, dur)
            # only look for args 3 and 4 if duration is > 0; otherwise those args are a syntax error (on tandy)
            volume, voice = 15, 0
            if dur > 0:
                if (ins.skip_blank_read_if((',',)) and (self.syntax == 'tandy' or
                        (self.syntax == 'pcjr' and self.session.sound.sound_on))):
                    volume = values.to_int(self.parse_expression(ins))
                    error.range_check(0, 15, volume)
                    if ins.skip_blank_read_if((',',)):
                        voice = values.to_int(self.parse_expression(ins))
                        error.range_check(0, 2, voice) # can't address noise channel here
            ins.require_end()
            args = freq, dur, volume, voice
        self.session.sound.sound_(*args)

    def exec_play(self, ins):
        """PLAY: event switch/play MML string."""
        command = ins.skip_blank_read_if((tk.ON, tk.OFF, tk.STOP))
        if command:
            # PLAY: event switch
            self.session.events.play_(command)
            ins.require_end()
        else:
            # retrieve Music Macro Language string
            mml1, mml2 = '', ''
            mml0 = self.parse_temporary_string(ins, allow_empty=True)
            if ((self.syntax == 'tandy' or (self.syntax == 'pcjr' and
                                             self.session.sound.sound_on))
                    and ins.skip_blank_read_if((',',))):
                mml1 = self.parse_temporary_string(ins, allow_empty=True)
                if ins.skip_blank_read_if((',',)):
                    mml2 = self.parse_temporary_string(ins, allow_empty=True)
            ins.require_end()
            if not (mml0 or mml1 or mml2):
                raise error.RunError(error.MISSING_OPERAND)
            self.session.sound.play_(self.memory, self.values, (mml0, mml1, mml2))

    def exec_noise(self, ins):
        """NOISE: produce sound on the noise generator (Tandy/PCjr)."""
        if not self.session.sound.sound_on:
            raise error.RunError(error.IFC)
        source = values.to_int(self.parse_expression(ins))
        ins.require_read((',',))
        volume = values.to_int(self.parse_expression(ins))
        ins.require_read((',',))
        error.range_check(0, 7, source)
        error.range_check(0, 15, volume)
        dur = values.csng_(self.parse_expression(ins)).to_value()
        error.range_check(-65535, 65535, dur)
        ins.require_end()
        self.session.sound.noise_(source, volume, dur)

    ###########################################################################
    # machine emulation

    def exec_poke(self, ins):
        """POKE: write to a memory location."""
        addr = values.to_int(self.parse_expression(ins), unsigned=True)
        if self.session.program.protected and not self.run_mode:
            raise error.RunError(error.IFC)
        ins.require_read((',',))
        val = self.parse_expression(ins)
        self.session.all_memory.poke_(addr, val)

    def exec_def_seg(self, ins):
        """DEF SEG: set the current memory segment."""
        seg = None
        if ins.skip_blank_read_if((tk.O_EQ,)):
            # def_seg() accepts signed values
            seg = values.to_int(self.parse_expression(ins), unsigned=True)
        self.session.all_memory.def_seg_(seg)

    def exec_def_usr(self, ins):
        """DEF USR: Define a machine language function."""
        usr = ins.skip_blank_read_if(tk.DIGIT)
        ins.require_read((tk.O_EQ,))
        addr = values.cint_(self.parse_expression(ins), unsigned=True)
        self.session.all_memory.def_usr_(usr, addr)

    def exec_bload(self, ins):
        """BLOAD: load a file into a memory location."""
        if self.session.program.protected and not self.run_mode:
            raise error.RunError(error.IFC)
        name = self.parse_temporary_string(ins)
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        offset = None
        if ins.skip_blank_read_if((',',)):
            offset = values.to_int(self.parse_expression(ins), unsigned=True)
        ins.require_end()
        self.session.all_memory.bload_(name, offset)

    def exec_bsave(self, ins):
        """BSAVE: save a block of memory to a file. Limited implementation."""
        if self.session.program.protected and not self.run_mode:
            raise error.RunError(error.IFC)
        name = self.parse_temporary_string(ins)
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        ins.require_read((',',))
        offset = values.to_int(self.parse_expression(ins), unsigned=True)
        ins.require_read((',',))
        length = values.to_int(self.parse_expression(ins), unsigned=True)
        ins.require_end()
        self.session.all_memory.bsave_(name, offset, length)

    def _parse_call(self, ins):
        """Helper function to parse CALL and CALLS."""
        addr_var = self._parse_name(ins)
        if addr_var[-1] == values.STR:
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        vals = []
        if ins.skip_blank_read_if(('(',)):
            while True:
                # if we wanted to call a function, we should distinguish varnames
                # (passed by ref) from constants (passed by value) here.
                # right now we only pass by value.
                vals.append(self.parse_expression(ins))
                if not ins.skip_blank_read_if((',',)):
                    break
            ins.require_read((')',))
        ins.require_end()
        return addr_var, vals

    def exec_call(self, ins):
        """CALL: call an external procedure."""
        self.session.all_memory.call_(*self._parse_call(ins))

    def exec_calls(self, ins):
        """CALLS: call an external procedure."""
        self.session.all_memory.calls_(*self._parse_call(ins))

    def exec_out(self, ins):
        """OUT: send a byte to a machine port. Limited implementation."""
        addr = values.to_int(self.parse_expression(ins), unsigned=True)
        ins.require_read((',',))
        val = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, val)
        self.session.machine.out_(addr, val)

    def exec_wait(self, ins):
        """WAIT: wait for a machine port. Limited implementation."""
        addr = values.to_int(self.parse_expression(ins), unsigned=True)
        ins.require_read((',',))
        ander = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, ander)
        xorer = 0
        if ins.skip_blank_read_if((',',)):
            xorer = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, xorer)
        ins.require_end()
        self.session.machine.wait_(addr, ander, xorer)

    ###########################################################################
    # Disk

    def exec_name(self, ins):
        """NAME: rename file or directory."""
        oldname = self.parse_temporary_string(ins)
        # AS is not a tokenised word
        ins.require_read((tk.W_AS,))
        newname = self.parse_temporary_string(ins)
        self.session.devices.name_(oldname, newname)

    ###########################################################################
    # OS

    def exec_time_date(self, ins, callback):
        """Parse TIME$ or DATE$ syntax."""
        ins.require_read((tk.O_EQ,))
        arg = self.parse_temporary_string(ins)
        ins.require_end()
        callback(arg)

    ##########################################################
    # code

    def _parse_line_range(self, ins):
        """Helper function: parse line number ranges."""
        from_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        if ins.skip_blank_read_if((tk.O_MINUS,)):
            to_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        else:
            to_line = from_line
        return (from_line, to_line)

    def _parse_jumpnum_or_dot(self, ins, allow_empty=False, err=error.STX):
        """Helper function: parse jump target."""
        c = ins.skip_blank_read()
        if c == tk.T_UINT:
            token = ins.read(2)
            assert len(token) == 2, 'bytecode truncated in line number pointer'
            return struct.unpack('<H', token)[0]
        elif c == '.':
            return self.session.program.last_stored
        else:
            if allow_empty:
                ins.seek(-len(c), 1)
                return None
            raise error.RunError(err)

    def exec_delete(self, ins):
        """DELETE: delete range of lines from program."""
        from_line, to_line = self._parse_line_range(ins)
        ins.require_end()
        self.session.delete_(from_line, to_line)

    def exec_edit(self, ins):
        """EDIT: output a program line and position cursor for editing."""
        if ins.skip_blank() in tk.END_STATEMENT:
            # undefined line number
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        from_line = self._parse_jumpnum_or_dot(ins, err=error.IFC)
        if from_line is None or from_line not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        ins.require_end(err=error.IFC)
        self.session.edit_(from_line)

    def exec_auto(self, ins):
        """AUTO: enter automatic line numbering mode."""
        linenum = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        increment = None
        if ins.skip_blank_read_if((',',)):
            increment = self._parse_optional_jumpnum(ins)
            # FIXME: returns -1, auto shld give IFC
        ins.require_end()
        self.session.auto_(linenum, increment)

    def exec_list(self, ins):
        """LIST: output program lines."""
        from_line, to_line = self._parse_line_range(ins)
        out = None
        if ins.skip_blank_read_if((',',)):
            outname = self.parse_temporary_string(ins)
            out = self.session.files.open(0, outname, filetype='A', mode='O')
            # ignore everything after file spec
            ins.skip_to(tk.END_LINE)
        ins.require_end()
        self.session.list_(from_line, to_line, out)

    def exec_llist(self, ins):
        """LLIST: output program lines to LPT1: """
        from_line, to_line = self._parse_line_range(ins)
        ins.require_end()
        self.session.llist_(from_line, to_line)

    def exec_load(self, ins):
        """LOAD: load program from file."""
        name = self.parse_temporary_string(ins)
        comma_r = ins.skip_blank_read_if((',R',), 2)
        ins.require_end()
        self.session.load_(name, comma_r)

    def exec_chain(self, ins):
        """CHAIN: load program and chain execution."""
        merge = ins.skip_blank_read_if((tk.MERGE,)) is not None
        name = self.parse_temporary_string(ins)
        jumpnum, common_all, delete_lines = None, False, None
        if ins.skip_blank_read_if((',',)):
            # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
            expr = self.parse_expression(ins, allow_empty=True)
            if expr is not None:
                jumpnum = values.to_int(expr, unsigned=True)
            if ins.skip_blank_read_if((',',)):
                if ins.skip_blank_read_if(('ALL',), 3):
                    common_all = True
                    # CHAIN "file", , ALL, DELETE
                    if ins.skip_blank_read_if((',',)):
                        delete_lines = self._parse_delete_clause(ins)
                else:
                    # CHAIN "file", , DELETE
                    delete_lines = self._parse_delete_clause(ins)
        ins.require_end()
        self.session.chain_(name, jumpnum, common_all, delete_lines, merge)

    def _parse_delete_clause(self, ins):
        """Helper function: parse the DELETE clause of a CHAIN statement."""
        delete_lines = None
        if ins.skip_blank_read_if((tk.DELETE,)):
            from_line = self._parse_optional_jumpnum(ins)
            if ins.skip_blank_read_if((tk.O_MINUS,)):
                to_line = self._parse_optional_jumpnum(ins)
                #FIXME: returns -1 on missing, not clear what happens in CHAIN
            else:
                to_line = from_line
            # to_line must be specified and must be an existing line number
            if not to_line or to_line not in self.session.program.line_numbers:
                raise error.RunError(error.IFC)
            delete_lines = (from_line, to_line)
            # ignore rest if preceded by comma
            if ins.skip_blank_read_if((',',)):
                ins.skip_to(tk.END_STATEMENT)
        return delete_lines

    def exec_save(self, ins):
        """SAVE: save program to a file."""
        name = self.parse_temporary_string(ins)
        mode = None
        if ins.skip_blank_read_if((',',)):
            mode = ins.skip_blank_read().upper()
            if mode not in ('A', 'P'):
                raise error.RunError(error.STX)
        self.session.save_(name, mode)

    def exec_renum(self, ins):
        """RENUM: renumber program line numbers."""
        new, old, step = None, None, None
        if ins.skip_blank() not in tk.END_STATEMENT:
            new = self._parse_jumpnum_or_dot(ins, allow_empty=True)
            if ins.skip_blank_read_if((',',)):
                old = self._parse_jumpnum_or_dot(ins, allow_empty=True)
                if ins.skip_blank_read_if((',',)):
                    step = self._parse_optional_jumpnum(ins)
                    # FIXME: returns -1 if empty, renum shld give IFC
        ins.require_end()
        self.session.renum_(new, old, step)

    ###########################################################################
    # file

    def exec_open(self, ins):
        """OPEN: open a file."""
        first_expr = self.parse_temporary_string(ins)
        if ins.skip_blank_read_if((',',)):
            args = self._parse_open_first(ins, first_expr)
        else:
            args = self._parse_open_second(ins, first_expr)
        self.session.files.open_(*args)

    def _parse_open_first(self, ins, first_expr):
        """Parse OPEN first ('old') syntax."""
        mode = first_expr[:1].upper()
        if mode not in ('I', 'O', 'A', 'R'):
            raise error.RunError(error.BAD_FILE_MODE)
        number = self._parse_file_number(ins, opt_hash=True)
        ins.require_read((',',))
        name = self.parse_temporary_string(ins)
        reclen = None
        if ins.skip_blank_read_if((',',)):
            reclen = values.to_int(self.parse_expression(ins))
        return number, name, mode, reclen

    def _parse_open_second(self, ins, first_expr):
        """Parse OPEN second ('new') syntax."""
        name = first_expr
        # FOR clause
        mode = None
        if ins.skip_blank_read_if((tk.FOR,)):
            # read mode word
            if ins.skip_blank_read_if((tk.INPUT,)):
                mode = 'I'
            else:
                word = ins.read_name()
                try:
                    mode = {tk.W_OUTPUT:'O', tk.W_RANDOM:'R', tk.W_APPEND:'A'}[word]
                except KeyError:
                    ins.seek(-len(word), 1)
                    raise error.RunError(error.STX)
        # ACCESS clause
        access = None
        if ins.skip_blank_read_if((tk.W_ACCESS,), 6):
            access = self._parse_read_write(ins)
        # LOCK clause
        if ins.skip_blank_read_if((tk.LOCK,), 2):
            lock = self._parse_read_write(ins)
        else:
            lock = ins.skip_blank_read_if((tk.W_SHARED), 6)
        # AS file number clause
        ins.require_read((tk.W_AS,))
        number = self._parse_file_number(ins, opt_hash=True)
        # LEN clause
        reclen = None
        if ins.skip_blank_read_if((tk.LEN,), 2):
            ins.require_read(tk.O_EQ)
            reclen = values.to_int(self.parse_expression(ins))
        return number, name, mode, reclen, access, lock

    def _parse_read_write(self, ins):
        """Helper function: parse access mode."""
        d = ins.skip_blank_read_if((tk.READ, tk.WRITE))
        if d == tk.WRITE:
            return 'W'
        elif d == tk.READ:
            return 'RW' if ins.skip_blank_read_if((tk.WRITE,)) else 'R'
        raise error.RunError(error.STX)

    def exec_close(self, ins):
        """CLOSE: close one or more files."""
        if ins.skip_blank() in tk.END_STATEMENT:
            # close all open files
            self.session.files.close_()
        else:
            while True:
                # if an error occurs, the files parsed before are closed anyway
                number = self._parse_file_number(ins, opt_hash=True)
                self.session.files.close_(number)
                if not ins.skip_blank_read_if((',',)):
                    break

    def exec_field(self, ins):
        """FIELD: link a string variable to record buffer."""
        the_file = self.session.files.get(self._parse_file_number(ins, opt_hash=True), 'R')
        if ins.skip_blank_read_if((',',)):
            offset = 0
            while True:
                width = values.to_int(self.parse_expression(ins))
                error.range_check(0, 255, width)
                ins.require_read((tk.W_AS,), err=error.IFC)
                name, index = self._parse_variable(ins)
                self.session.files.field_(the_file, name, index, offset, width)
                offset += width
                if not ins.skip_blank_read_if((',',)):
                    break

    def _parse_put_get_file(self, ins):
        """Parse record number for PUT and GET."""
        the_file = self.session.files.get(self._parse_file_number(ins, opt_hash=True), 'R')
        pos = None
        if ins.skip_blank_read_if((',',)):
            pos = self.parse_expression(ins)
        return (the_file, pos)

    def exec_put_file(self, ins):
        """PUT: write record to file."""
        self.session.files.put_(*self._parse_put_get_file(ins))

    def exec_get_file(self, ins):
        """GET: read record from file."""
        self.session.files.get_(*self._parse_put_get_file(ins))

    def _parse_lock_unlock(self, ins):
        """Parse lock records for LOCK or UNLOCK."""
        thefile = self.session.files.get(self._parse_file_number(ins, opt_hash=True))
        lock_start_rec = None
        if ins.skip_blank_read_if((',',)):
            lock_start_rec = self.values.csng_(self.parse_expression(ins))
        lock_stop_rec = None
        if ins.skip_blank_read_if((tk.TO,)):
            lock_stop_rec = self.values.csng_(self.parse_expression(ins))
        return (thefile, lock_start_rec, lock_stop_rec)

    def exec_lock(self, ins):
        """LOCK: set file or record locks."""
        self.session.files.lock_(*self._parse_lock_unlock(ins))

    def exec_unlock(self, ins):
        """UNLOCK: unset file or record locks."""
        self.session.files.unlock_(*self._parse_lock_unlock(ins))

    def exec_ioctl(self, ins):
        """IOCTL: send control string to I/O device."""
        thefile = self.session.files.get(self._parse_file_number(ins, opt_hash=True))
        ins.require_read((',',))
        control_string = self.parse_temporary_string(ins)
        self.session.files.ioctl_statement_(thefile, control_string)

    ###########################################################################
    # Graphics statements

    def _parse_coord_bare(self, ins):
        """Helper function: parse coordinate pair."""
        ins.require_read(('(',))
        x = values.csng_(self.parse_expression(ins)).to_value()
        ins.require_read((',',))
        y = values.csng_(self.parse_expression(ins)).to_value()
        ins.require_read((')',))
        return x, y

    def _parse_coord_step(self, ins):
        """Helper function: parse coordinate pair."""
        step = ins.skip_blank_read_if((tk.STEP,))
        x, y = self._parse_coord_bare(ins)
        return x, y, step

    def _parse_pset_preset(self, ins):
        """Parse arguments for PSET and PRESET."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        lcoord = self._parse_coord_step(ins)
        c = None
        if ins.skip_blank_read_if((',',)):
            c = values.to_int(self.parse_expression(ins))
            error.range_check(0, 255, c)
        ins.require_end()
        return lcoord, c

    def exec_pset(self, ins, c=-1):
        """PSET: set a pixel to a given attribute, or foreground."""
        self.session.screen.drawing.pset_(*self._parse_pset_preset(ins))

    def exec_preset(self, ins):
        """PRESET: set a pixel to a given attribute, or background."""
        self.session.screen.drawing.preset_(*self._parse_pset_preset(ins))

    def exec_line_graph(self, ins):
        """LINE: draw a line or box between two points."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        if ins.skip_blank() in ('(', tk.STEP):
            coord0 = self._parse_coord_step(ins)
        else:
            coord0 = None
        ins.require_read((tk.O_MINUS,))
        coord1 = self._parse_coord_step(ins)
        c, mode, pattern = None, None, None
        if ins.skip_blank_read_if((',',)):
            expr = self.parse_expression(ins, allow_empty=True)
            if expr:
                c = values.to_int(expr)
            if ins.skip_blank_read_if((',',)):
                if ins.skip_blank_read_if(('B',)):
                    mode = 'BF' if ins.skip_blank_read_if(('F',)) else 'B'
                if ins.skip_blank_read_if((',',)):
                    pattern = self.parse_value(ins, values.INT)
                else:
                    # mustn't end on a comma
                    # mode == '' if nothing after previous comma
                    error.throw_if(not mode, error.STX)
            elif not expr:
                raise error.RunError(error.MISSING_OPERAND)
        ins.require_end()
        self.session.screen.drawing.line_(coord0, coord1, c, pattern, mode)

    def exec_view_graph(self, ins):
        """VIEW: set graphics viewport and optionally draw a box."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        absolute = ins.skip_blank_read_if((tk.SCREEN,))
        if ins.skip_blank() == '(':
            x0, y0 = self._parse_coord_bare(ins)
            x0, y0 = round(x0), round(y0)
            ins.require_read((tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare(ins)
            x1, y1 = round(x1), round(y1)
            error.range_check(0, self.session.screen.mode.pixel_width-1, x0, x1)
            error.range_check(0, self.session.screen.mode.pixel_height-1, y0, y1)
            fill, border = None, None
            if ins.skip_blank_read_if((',',)):
                fill = values.to_int(self.parse_expression(ins))
                ins.require_read((',',))
                border = values.to_int(self.parse_expression(ins))
            args = (x0, y0, x1, y1, absolute, fill, border)
        else:
            args = ()
        self.session.screen.drawing.view_(*args)

    def exec_window(self, ins):
        """WINDOW: define logical coordinate system."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        cartesian = not ins.skip_blank_read_if((tk.SCREEN,))
        if ins.skip_blank() == '(':
            x0, y0 = self._parse_coord_bare(ins)
            ins.require_read((tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare(ins)
            if x0 == x1 or y0 == y1:
                raise error.RunError(error.IFC)
            args = (x0, y0, x1, y1, cartesian)
        else:
            args = ()
        self.session.screen.drawing.window_(*args)

    def exec_circle(self, ins):
        """CIRCLE: Draw a circle, ellipse, arc or sector."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        centre = self._parse_coord_step(ins)
        ins.require_read((',',))
        r = values.csng_(self.parse_expression(ins)).to_value()
        start, stop, c, aspect = None, None, None, None
        if ins.skip_blank_read_if((',',)):
            cval = self.parse_expression(ins, allow_empty=True)
            if cval is not None:
                c = values.to_int(cval)
            if ins.skip_blank_read_if((',',)):
                start = self.parse_expression(ins, allow_empty=True)
                if start is not None:
                    start = values.csng_(start).to_value()
                if ins.skip_blank_read_if((',',)):
                    stop = self.parse_expression(ins, allow_empty=True)
                    if stop is not None:
                        stop = values.csng_(stop).to_value()
                    if ins.skip_blank_read_if((',',)):
                        aspect = values.csng_(self.parse_expression(ins)).to_value()
                    elif stop is None:
                        # missing operand
                        raise error.RunError(error.MISSING_OPERAND)
                elif start is None:
                    raise error.RunError(error.MISSING_OPERAND)
            elif cval is None:
                raise error.RunError(error.MISSING_OPERAND)
        ins.require_end()
        self.session.screen.drawing.circle_(centre, r, start, stop, c, aspect)

    def exec_paint(self, ins):
        """PAINT: flood fill from point."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        coord = self._parse_coord_step(ins)
        attrib, border, background_pattern = None, None, None
        with self.temp_string:
            if ins.skip_blank_read_if((',',)):
                attrib = self.parse_expression(ins, allow_empty=True)
                if ins.skip_blank_read_if((',',)):
                    bval = self.parse_expression(ins, allow_empty=True)
                    if bval is not None:
                        border = values.to_int(bval)
                    if ins.skip_blank_read_if((',',)):
                        with self.temp_string:
                            background_pattern = values.pass_string(
                                    self.parse_expression(ins), err=error.IFC).to_str()
            self.session.screen.drawing.paint_(coord, attrib, border, background_pattern, self.session.events)

    def exec_get_graph(self, ins):
        """GET: read a sprite to memory."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP for first coord
        coord0 = self._parse_coord_bare(ins)
        ins.require_read((tk.O_MINUS,))
        coord1 = self._parse_coord_step(ins)
        ins.require_read((',',))
        array = self._parse_name(ins)
        ins.require_end()
        self.session.screen.drawing.get_(coord0, coord1, self.session.arrays, array)

    def exec_put_graph(self, ins):
        """PUT: draw sprite on screen."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP
        x, y = self._parse_coord_bare(ins)
        ins.require_read((',',))
        array = self._parse_name(ins)
        action = None
        if ins.skip_blank_read_if((',',)):
            action = ins.require_read((tk.PSET, tk.PRESET, tk.AND, tk.OR, tk.XOR))
        ins.require_end()
        self.session.screen.drawing.put_((x, y), self.session.arrays, array, action)

    def exec_draw(self, ins):
        """DRAW: draw a figure defined by a Graphics Macro Language string."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        gml = self.parse_temporary_string(ins)
        ins.require_end()
        self.session.screen.drawing.draw_(gml, self.memory, self.values, self.session.events)

    ###########################################################################
    # Variable & array statements

    def _parse_clear_args_iter(self, ins):
        """Generator: parse arguments for CLEAR."""
        # integer expression allowed but ignored
        yield self.parse_expression(ins, allow_empty=True)
        if ins.skip_blank_read_if((',',)):
            exp1 = self.parse_expression(ins, allow_empty=True)
            yield exp1
            if not ins.skip_blank_read_if((',',)):
                if not exp1:
                    raise error.RunError(error.STX)
            else:
                # set aside stack space for GW-BASIC. The default is the previous stack space size.
                exp2 = self.parse_expression(ins, allow_empty=True)
                yield exp2
                if self.syntax in ('pcjr', 'tandy') and ins.skip_blank_read_if((',',)):
                    # Tandy/PCjr: select video memory size
                    yield self.parse_expression(ins)
                elif not exp2:
                    raise error.RunError(error.STX)
        ins.require_end()

    def exec_common(self, ins):
        """COMMON: define variables to be preserved on CHAIN."""
        common_vars = []
        while True:
            name = self._parse_name(ins)
            brackets = ins.skip_blank_read_if(('[', '('))
            if brackets:
                ins.require_read((']', ')'))
            common_vars.append((name, brackets))
            if not ins.skip_blank_read_if((',',)):
                break
        self.session.common_(common_vars)

    def _parse_var_list_iter(self, ins):
        """Generator: lazily parse variable list."""
        while True:
            yield self._parse_variable(ins)
            if not ins.skip_blank_read_if((',',)):
                break

    def _parse_var_list(self, ins):
        """Helper function: parse variable list."""
        return list(self._parse_var_list_iter(ins))

    def exec_dim(self, ins):
        """DIM: dimension arrays."""
        for name, dimensions in self._parse_var_list_iter(ins):
            self.session.arrays.dim_(name, dimensions)

    def exec_deftype(self, ins, typechar):
        """DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables."""
        while True:
            start = ins.skip_blank_read()
            if start not in string.ascii_letters:
                raise error.RunError(error.STX)
            stop = None
            if ins.skip_blank_read_if((tk.O_MINUS,)):
                stop = ins.skip_blank_read()
                if stop not in string.ascii_letters:
                    raise error.RunError(error.STX)
            self.memory.deftype_(typechar, start, stop)
            if not ins.skip_blank_read_if((',',)):
                break

    def exec_erase(self, ins):
        """ERASE: erase an array."""
        while True:
            self.session.arrays.erase_(self._parse_name(ins))
            if not ins.skip_blank_read_if((',',)):
                break

    def _parse_let_args_iter(self, ins):
        """Generator: parse arguments for LET."""
        yield self._parse_variable(ins)
        ins.require_read((tk.O_EQ,))
        yield self.parse_expression(ins)

    def _parse_mid_args_iter(self, ins):
        """Generator: parse arguments for MID$."""
        # do not use require_read as we don't allow whitespace here
        if ins.read(1) != '(':
            raise error.RunError(error.STX)
        yield self._parse_variable(ins)
        ins.require_read((',',))
        yield self.parse_value(ins, values.INT)
        if ins.skip_blank_read_if((',',)):
            yield self.parse_value(ins, values.INT)
        else:
            yield None
        ins.require_read((')',))
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by midset if applied to a code literal
        yield self.parse_expression(ins)
        ins.require_end()

    def _parse_lset_or_rset(self, ins):
        """LSET: assign string value in-place; left justified."""
        name, index = self._parse_variable(ins)
        v = values.pass_string(self.memory.get_variable(name, index))
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by lset if applied to a code literal
        s = values.pass_string(self.parse_expression(ins))
        return name, index, v, s

    def exec_lset(self, ins):
        """LSET: assign string value in-place; left justified."""
        name, index, v, s = self._parse_lset_or_rset(ins)
        self.memory.set_variable(name, index, v.lset(s, justify_right=False))

    def exec_rset(self, ins):
        """RSET: assign string value in-place; right justified."""
        name, index, v, s = self._parse_lset_or_rset(ins)
        self.memory.set_variable(name, index, v.lset(s, justify_right=True))

    def exec_option(self, ins):
        """OPTION BASE: set array indexing convention."""
        ins.require_read((tk.W_BASE,))
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = ins.require_read(('0', '1'))
        self.session.arrays.option_base_(d)

    def exec_read(self, ins):
        """READ: read values from DATA statement."""
        # reading loop
        for name, indices in self._parse_var_list(ins):
            self.session.interpreter.read_(name, indices)

    def _parse_prompt(self, ins):
        """Helper function for INPUT: parse prompt definition."""
        # ; to avoid echoing newline
        newline = not ins.skip_blank_read_if((';',))
        # parse prompt
        prompt, following = '', ';'
        if ins.skip_blank() == '"':
            # only literal allowed, not a string expression
            prompt = ins.read_string().strip('"')
            following = ins.require_read((';', ','))
        return newline, prompt, following

    def exec_input(self, ins):
        """INPUT: request input from user."""
        file_number = self._parse_file_number(ins, opt_hash=False)
        if file_number is not None:
            finp = self.session.files.get(file_number, mode='IR')
            ins.require_read((',',))
            readvar = self._parse_var_list(ins)
            self.session.input_file_(finp, readvar)
        else:
            newline, prompt, following = self._parse_prompt(ins)
            readvar = self._parse_var_list_iter(ins)
            self.session.input_(newline, prompt, following, readvar)

    def exec_line_input(self, ins):
        """LINE INPUT: request line of input from user."""
        prompt, newline, finp = None, None, None
        file_number = self._parse_file_number(ins, opt_hash=False)
        if file_number is None:
            # get prompt
            newline, prompt, _ = self._parse_prompt(ins)
        else:
            finp = self.session.files.get(file_number, mode='IR')
            ins.require_read((',',))
        # get string variable
        readvar, indices = self._parse_variable(ins)
        self.session.line_input_(finp, prompt, readvar, indices, newline)

    def exec_restore(self, ins):
        """RESTORE: reset DATA pointer."""
        datanum = None
        if ins.skip_blank() == tk.T_UINT:
            datanum = self._parse_jumpnum(ins)
        # undefined line number for all syntax errors
        ins.require_end(err=error.UNDEFINED_LINE_NUMBER)
        self.session.interpreter.restore_(datanum)

    def exec_swap(self, ins):
        """SWAP: swap values of two variables."""
        name1, index1 = self._parse_variable(ins)
        ins.require_read((',',))
        name2, index2 = self._parse_variable(ins)
        self.memory.swap_(name1, index1, name2, index2)
        # if syntax error, the swap has happened

    ###########################################################################
    # Console statements

    def exec_cls(self, ins):
        """CLS: clear the screen."""
        val = None
        if self.syntax != 'pcjr':
            val = self.parse_value(ins, values.INT, allow_empty=True)
            if val is not None:
                # tandy gives illegal function call on CLS number
                error.throw_if(self.syntax == 'tandy')
                error.range_check(0, 2, val)
            if not ins.skip_blank_read_if((',',)):
                ins.require_end(err=error.IFC)
        self.session.screen.cls_(val)

    def exec_color(self, ins):
        """COLOR: set colour attributes."""
        args = [self.parse_value(ins, values.INT, allow_empty=True)]
        if ins.skip_blank_read_if((',',)):
            # unlike LOCATE, ending in any number of commas is a Missing Operand
            while True:
                args.append(self.parse_value(ins, values.INT, allow_empty=True))
                if ins.skip_blank_read_if((',',)):
                    continue
                elif args[-1] is None:
                    raise error.RunError(error.MISSING_OPERAND)
                else:
                    break
        elif args[0] is None:
            raise error.RunError(error.IFC)
        error.throw_if(len(args) > 3)
        self.session.screen.color_(*args)

    def exec_palette(self, ins):
        """PALETTE: set colour palette entry."""
        if ins.skip_blank_read_if((tk.USING,)):
            return self.exec_palette_using(ins)
        else:
            attrib = self.parse_value(ins, values.INT, allow_empty=True)
            if attrib is None:
                colour = None
                ins.require_end()
            else:
                ins.require_read((',',))
                colour = self.parse_value(ins, values.INT, allow_empty=True)
                error.throw_if(attrib is None or colour is None, error.STX)
            self.session.screen.palette.palette_(attrib, colour)

    def exec_palette_using(self, ins):
        """PALETTE USING: set full colour palette."""
        array_name, start_indices = self._parse_variable(ins)
        # brackets are not optional
        error.throw_if(not start_indices, error.STX)
        self.session.screen.palette.palette_using_(array_name, start_indices, self.session.arrays)

    def exec_key(self, ins):
        """KEY: switch on/off or list function-key row on screen."""
        d = ins.skip_blank_read()
        if d in (tk.ON, tk.OFF, tk.LIST):
            # KEY ON, KEY OFF, KEY LIST
            self.session.fkey_macros.key_(d, self.session.screen)
        elif d == '(':
            # key (n)
            ins.seek(-1, 1)
            self.exec_key_events(ins)
        else:
            # key n, "TEXT"
            ins.seek(-len(d), 1)
            self.exec_key_define(ins)

    def exec_key_define(self, ins):
        """KEY: define function-key shortcut or scancode for event trapping."""
        keynum = values.to_int(self.parse_expression(ins))
        error.range_check(1, 255, keynum)
        ins.require_read((',',))
        text = self.parse_temporary_string(ins)
        if keynum <= self.session.events.num_fn_keys:
            self.session.fkey_macros.set(keynum, text, self.session.screen)
        else:
            # only length-2 expressions can be assigned to KEYs over 10
            # in which case it's a key scancode definition
            if len(text) != 2:
                raise error.RunError(error.IFC)
            self.session.events.key[keynum-1].set_trigger(str(text))

    def exec_locate(self, ins):
        """LOCATE: Set cursor position, shape and visibility."""
        #row, col, cursor, start, stop
        params = [None, None, None, None, None]
        for i in range(5):
            params[i] = self.parse_value(ins, values.INT, allow_empty=True)
            # note that LOCATE can end on a 5th comma but no stuff allowed after it
            if not ins.skip_blank_read_if((',',)):
                break
        ins.require_end()
        self.session.screen.locate_(*params)

    def _parse_write_args_iter(self, ins):
        """Parse WRITE statement arguments."""
        file_number = self._parse_file_number(ins, opt_hash=False)
        yield file_number
        if file_number is not None:
            ins.require_read((',',))
        with self.temp_string:
            expr = self.parse_expression(ins, allow_empty=True)
            if expr is not None:
                yield expr
        if expr is not None:
            while True:
                if not ins.skip_blank_read_if((',', ';')):
                    ins.require_end()
                    break
                with self.temp_string:
                    yield self.parse_expression(ins)

    def exec_view_print(self, ins):
        """VIEW PRINT: set scroll region."""
        start = self.parse_value(ins, values.INT, allow_empty=True)
        stop = None
        if start is not None:
            ins.require_read((tk.TO,))
            stop = self.parse_value(ins, values.INT)
        ins.require_end()
        self.session.screen.view_print_(start, stop)

    def _parse_width_args_iter(self, ins):
        """Parse WIDTH syntax."""
        d = ins.skip_blank_read_if(('#', tk.LPRINT))
        if d:
            if d == '#':
                yield values.to_int(self.parse_expression(ins))
                ins.require_read((',',))
            else:
                yield tk.LPRINT
            yield self.parse_value(ins, values.INT)
        else:
            yield None
            with self.temp_string:
                if ins.peek() in set(string.digits) | set(tk.NUMBER):
                    expr = self.expression_parser.read_number_literal(ins)
                else:
                    expr = self.parse_expression(ins)
                yield expr
            if isinstance(expr, values.String):
                ins.require_read((',',))
                yield self.parse_value(ins, values.INT)
            else:
                if not ins.skip_blank_read_if((',',)):
                    yield None
                    ins.require_end(error.IFC)
                else:
                    # parse dummy number rows setting
                    yield self.parse_value(ins, values.INT, allow_empty=True)
                    # trailing comma is accepted
                    ins.skip_blank_read_if((',',))
        ins.require_end()

    def exec_screen(self, ins):
        """SCREEN: change video mode or page."""
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        # mode, color, apagenum, vpagenum, erase
        # erase can only be set on pcjr/tandy 5-argument syntax
        n_args = 4 + (self.syntax in ('pcjr', 'tandy'))
        args = []
        # all but last arguments are optional and may be followed by a comma
        while True:
            args.append(self.parse_value(ins, values.INT, allow_empty=True))
            if not ins.skip_blank_read_if((',',)):
                break
        if args[-1] is None:
            raise error.RunError(error.MISSING_OPERAND)
        if len(args) > n_args:
            raise error.RunError(error.IFC)
        args += [None] * (5-len(args))
        # if any parameter not in [0,255], error 5 without doing anything
        # if the parameters are outside narrow ranges
        # (e.g. not implemented screen mode, pagenum beyond max)
        # then the error is only raised after changing the palette.
        error.range_check(0, 255, *args[:4])
        error.range_check(0, 2, args[4])
        ins.require_end()
        self.session.screen.screen_(*args)

    def exec_pcopy(self, ins):
        """PCOPY: copy video pages."""
        src = values.to_int(self.parse_expression(ins))
        error.range_check(0, self.session.screen.mode.num_pages-1, src)
        ins.require_read((',',))
        dst = values.to_int(self.parse_expression(ins))
        ins.require_end()
        error.range_check(0, self.session.screen.mode.num_pages-1, dst)
        self.session.screen.pcopy_(src, dst)

    def _parse_print_args_iter(self, ins, parse_file):
        """Parse PRINT or LPRINT syntax."""
        if parse_file:
            # check for a file number
            file_number = self._parse_file_number(ins, opt_hash=False)
            yield file_number
            if file_number is not None:
                ins.require_read((',',))
        while True:
            d = ins.skip_blank_read()
            if d in tk.END_STATEMENT:
                ins.seek(-len(d), 1)
                break
            elif d == tk.USING:
                format_expr = self.parse_temporary_string(ins)
                if format_expr == '':
                    raise error.RunError(error.IFC)
                ins.require_read((';',))
                yield (tk.USING, format_expr)
                has_args = False
                while True:
                    with self.temp_string:
                        expr = self.parse_expression(ins, allow_empty=True)
                        yield expr
                        if expr is None:
                            ins.require_end()
                            # need at least one argument after format string
                            if not has_args:
                                raise error.RunError(error.MISSING_OPERAND)
                            break
                        has_args = True
                    if not ins.skip_blank_read_if((';', ',')):
                        break
                break
            elif d in (',', ';'):
                yield (d, None)
            elif d in (tk.SPC, tk.TAB):
                num = values.to_int(self.parse_expression(ins), unsigned=True)
                ins.require_read((')',))
                yield (d, num)
            else:
                ins.seek(-len(d), 1)
                with self.temp_string:
                    value = self.parse_expression(ins)
                    yield (None, value)

    ###########################################################################
    # Loops and branches

    def exec_if(self, ins):
        """IF: enter branching statement."""
        # avoid overflow: don't use bools.
        val = values.csng_(self.parse_expression(ins))
        ins.skip_blank_read_if((',',)) # optional comma
        ins.require_read((tk.THEN, tk.GOTO))
        if not val.is_zero():
            # TRUE: continue after THEN. line number or statement is implied GOTO
            if ins.skip_blank() in (tk.T_UINT,):
                self.session.interpreter.goto_(self._parse_jumpnum(ins))
            # continue parsing as normal from next statement, :ELSE will be ignored anyway
            self.parse_statement(ins)
        else:
            # FALSE: find ELSE block or end of line; ELSEs are nesting on the line
            nesting_level = 0
            while True:
                d = ins.skip_to_read(tk.END_STATEMENT + (tk.IF,))
                if d == tk.IF:
                    # nexting step on IF. (it's less convenient to count THENs because they could be THEN, GOTO or THEN GOTO.)
                    nesting_level += 1
                elif d == ':':
                    # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                    if ins.skip_blank_read_if((tk.ELSE,)):
                        if nesting_level > 0:
                            nesting_level -= 1
                        else:
                            # line number: jump
                            if ins.skip_blank() in (tk.T_UINT,):
                                self.session.interpreter.goto_(self._parse_jumpnum(ins))
                            # continue execution from here
                            self.parse_statement(ins)
                            break
                else:
                    ins.seek(-len(d), 1)
                    break

    def exec_for(self, ins):
        """FOR: enter for-loop."""
        # read variable
        varname = self._parse_name(ins)
        vartype = varname[-1]
        ins.require_read((tk.O_EQ,))
        start = values.to_type(vartype, self.parse_expression(ins))
        ins.require_read((tk.TO,))
        # only raised after the TO has been parsed
        if vartype in (values.STR, values.DBL):
            raise error.RunError(error.TYPE_MISMATCH)
        stop = values.to_type(vartype, self.parse_expression(ins))
        step = None
        if ins.skip_blank_read_if((tk.STEP,)):
            step = values.to_type(vartype, self.parse_expression(ins))
        ins.require_end()
        # initialise loop
        self.session.interpreter.for_(varname, start, stop, step)

    def exec_next(self, ins):
        """NEXT: iterate for-loop."""
        while True:
            # optional var name, errors have been checked during _find_next scan
            varname = None
            if ins.skip_blank() not in tk.END_STATEMENT + (',',):
                varname = self._parse_name(ins)
            # increment counter, check condition
            if self.session.interpreter.next_(varname):
                break
            # done if we're not jumping into a comma'ed NEXT
            if not ins.skip_blank_read_if((',')):
                break
        # if we're done iterating we no longer ignore the rest of the statement

    ###########################################################################
    # User-defined functions

    def exec_def_fn(self, ins):
        """DEF FN: define a function."""
        fnname = self._parse_name(ins)
        # don't allow DEF FN in direct mode, as we point to the code in the stored program
        # this is raised before further syntax errors
        if not self.run_mode:
            raise error.RunError(error.ILLEGAL_DIRECT)
        # arguments and expression are being read and parsed by UserFunctionManager
        self.expression_parser.user_functions.define(fnname, ins)
