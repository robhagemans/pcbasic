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
from . import parseprint
from . import parseinput
from . import tokens as tk
from . import expressions
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
            return self.statements[c](ins)
        ins.seek(-len(c), 1)
        if c in string.ascii_letters:
            # implicit LET
            return self.exec_let(ins)
        elif c not in tk.END_STATEMENT:
            raise error.RunError(error.STX)

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

    def parse_file_number(self, ins, opt_hash):
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

    def parse_variable(self, ins):
        """Helper function: parse a scalar or array element."""
        name = ins.read_name()
        error.throw_if(not name, error.STX)
        # this is an evaluation-time determination
        # as we could have passed another DEFtype statement
        name = self.memory.complete_name(name)
        indices = self.expression_parser.parse_indices(ins)
        return name, indices

    def parse_jumpnum(self, ins):
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
        return self.parse_jumpnum(ins)

    def parse_expression(self, ins, allow_empty=False):
        """Compute the value of the expression at the current code pointer."""
        if allow_empty and ins.skip_blank() in tk.END_EXPRESSION:
            return None
        return self.expression_parser.parse(ins)

    ###########################################################################

    def set_runmode(self, new_runmode):
        """Keep track of runmode for protected and program-only statements."""
        self.run_mode = new_runmode

    def init_statements(self, session):
        """Initialise statements."""
        self.session = session
        self.statements = {
            tk.END: self.exec_end,
            tk.FOR: self.exec_for,
            tk.NEXT: self.exec_next,
            tk.DATA: self.exec_data,
            tk.INPUT: self.exec_input,
            tk.DIM: self.exec_dim,
            tk.READ: self.exec_read,
            tk.LET: self.exec_let,
            tk.GOTO: self.exec_goto,
            tk.RUN: self.exec_run,
            tk.IF: self.exec_if,
            tk.RESTORE: self.exec_restore,
            tk.GOSUB: self.exec_gosub,
            tk.RETURN: self.exec_return,
            tk.REM: self.exec_rem,
            tk.STOP: self.exec_stop,
            tk.PRINT: self.exec_print,
            tk.CLEAR: self.exec_clear,
            tk.LIST: self.exec_list,
            tk.NEW: self.exec_new,
            tk.ON: self.exec_on,
            tk.WAIT: self.exec_wait,
            tk.DEF: self.exec_def,
            tk.POKE: self.exec_poke,
            tk.CONT: self.exec_cont,
            tk.OUT: self.exec_out,
            tk.LPRINT: self.exec_lprint,
            tk.LLIST: self.exec_llist,
            tk.WIDTH: self.exec_width,
            tk.ELSE: self.exec_else,
            tk.TRON: self.exec_tron,
            tk.TROFF: self.exec_troff,
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
            tk.WHILE: self.exec_while,
            tk.WEND: self.exec_wend,
            tk.CALL: self.exec_call,
            tk.WRITE: self.exec_write,
            tk.OPTION: self.exec_option,
            tk.RANDOMIZE: self.exec_randomize,
            tk.OPEN: self.exec_open,
            tk.CLOSE: self.exec_close,
            tk.LOAD: self.exec_load,
            tk.MERGE: self.exec_merge,
            tk.SAVE: self.exec_save,
            tk.COLOR: self.exec_color,
            tk.CLS: self.exec_cls,
            tk.MOTOR: self.exec_motor,
            tk.BSAVE: self.exec_bsave,
            tk.BLOAD: self.exec_bload,
            tk.SOUND: self.exec_sound,
            tk.BEEP: self.exec_beep,
            tk.PSET: self.exec_pset,
            tk.PRESET: self.exec_preset,
            tk.SCREEN: self.exec_screen,
            tk.KEY: self.exec_key,
            tk.LOCATE: self.exec_locate,
            tk.FILES: self.exec_files,
            tk.FIELD: self.exec_field,
            tk.SYSTEM: self.exec_system,
            tk.NAME: self.exec_name,
            tk.LSET: self.exec_lset,
            tk.RSET: self.exec_rset,
            tk.KILL: self.exec_kill,
            tk.PUT: self.exec_put,
            tk.GET: self.exec_get,
            tk.RESET: self.exec_reset,
            tk.COMMON: self.exec_common,
            tk.CHAIN: self.exec_chain,
            tk.DATE: self.exec_date,
            tk.TIME: self.exec_time,
            tk.PAINT: self.exec_paint,
            tk.COM: self.exec_com,
            tk.CIRCLE: self.exec_circle,
            tk.DRAW: self.exec_draw,
            tk.PLAY: self.exec_play,
            tk.TIMER: self.exec_timer,
            tk.IOCTL: self.exec_ioctl,
            tk.CHDIR: self.exec_chdir,
            tk.MKDIR: self.exec_mkdir,
            tk.RMDIR: self.exec_rmdir,
            tk.SHELL: self.exec_shell,
            tk.ENVIRON: self.exec_environ,
            tk.VIEW: self.exec_view,
            tk.WINDOW: self.exec_window,
            tk.PALETTE: self.exec_palette,
            tk.LCOPY: self.exec_lcopy,
            tk.CALLS: self.exec_calls,
            tk.NOISE: self.exec_noise,
            tk.PCOPY: self.exec_pcopy,
            tk.TERM: self.exec_term,
            tk.LOCK: self.exec_lock,
            tk.UNLOCK: self.exec_unlock,
            tk.MID: self.exec_mid,
            tk.PEN: self.exec_pen,
            tk.STRIG: self.exec_strig,
            tk.DEBUG: self.exec_debug,
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['statements'] = None
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
                self.exec_on_error(ins)
            else:
                self.exec_on_event(ins, token)
        else:
            self.exec_on_jump(ins)

    ###########################################################################
    # interpreter commands and no-op statements

    def exec_system(self, ins):
        """SYSTEM: exit interpreter."""
        # SYSTEM LAH does not execute
        ins.require_end()
        self.session.interpreter.system_()

    def exec_tron(self, ins):
        """TRON: turn on line number tracing."""
        self.session.interpreter.tron_()
        # TRON LAH gives error, but TRON has been executed
        ins.require_end()

    def exec_troff(self, ins):
        """TROFF: turn off line number tracing."""
        self.session.interpreter.troff_()
        ins.require_end()

    def exec_rem(self, ins):
        """REM: comment."""
        # skip the rest of the line, but parse numbers to avoid triggering EOL
        ins.skip_to(tk.END_LINE)

    def exec_lcopy(self, ins):
        """LCOPY: do nothing but check for syntax errors."""
        val = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            val = values.to_int(self.parse_expression(ins))
            error.range_check(0, 255, val)
            ins.require_end()
        self.session.devices.lcopy_(val)

    def exec_motor(self, ins):
        """MOTOR: drive cassette motor."""
        val = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            val = values.to_int(self.parse_expression(ins))
            error.range_check(0, 255, val)
            ins.require_end()
        self.session.devices.motor_(val)

    def exec_debug(self, ins):
        """DEBUG: execute Python command."""
        # this is not a GW-BASIC behaviour, but helps debugging.
        # this is parsed like a REM by the tokeniser.
        # rest of the line is considered to be a python statement
        ins.skip_blank()
        debug_cmd = ''
        while ins.peek() not in tk.END_LINE:
            debug_cmd += ins.read(1)
        self.session.debugger.debug_(debug_cmd)

    def exec_term(self, ins):
        """TERM: load and run PCjr buitin terminal emulator program."""
        ins.require_end()
        self.session.interpreter.term_()

    ###########################################################################
    # event switches (except PLAY)

    def exec_pen(self, ins):
        """PEN: switch on/off light pen event handling."""
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.pen_(command)
        ins.require_end()

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
        ins.require_end()

    def exec_com(self, ins):
        """COM: switch on/off serial port event handling."""
        num = values.to_int(self.parse_bracket(ins))
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.com_(num, command)
        ins.require_end()

    def exec_timer(self, ins):
        """TIMER: switch on/off timer event handling."""
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.timer_(command)
        ins.require_end()

    def exec_key_events(self, ins):
        """KEY: switch on/off keyboard events."""
        num = values.to_int(self.parse_bracket(ins))
        error.range_check(0, 255, num)
        command = ins.require_read((tk.ON, tk.OFF, tk.STOP))
        self.session.events.key_(num, command)
        ins.require_end()

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
        jumpnum = self.parse_jumpnum(ins)
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
        ins.require_end()

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
        ins.require_end()

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
        ins.require_end()

    def exec_def_seg(self, ins):
        """DEF SEG: set the current memory segment."""
        seg = None
        if ins.skip_blank_read_if((tk.O_EQ,)):
            # def_seg() accepts signed values
            seg = values.to_int(self.parse_expression(ins), unsigned=True)
        self.session.all_memory.def_seg_(seg)
        ins.require_end()

    def exec_def_usr(self, ins):
        """DEF USR: Define a machine language function."""
        usr = ins.skip_blank_read_if(tk.DIGIT)
        ins.require_read((tk.O_EQ,))
        addr = values.cint_(self.parse_expression(ins), unsigned=True)
        self.session.all_memory.def_usr_(usr, addr)
        ins.require_end()

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
        ins.require_end()

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

    def exec_chdir(self, ins):
        """CHDIR: change working directory."""
        self.session.devices.chdir_(self.parse_temporary_string(ins))
        ins.require_end()

    def exec_mkdir(self, ins):
        """MKDIR: create directory."""
        self.session.devices.mkdir_(self.parse_temporary_string(ins))
        ins.require_end()

    def exec_rmdir(self, ins):
        """RMDIR: remove directory."""
        self.session.devices.rmdir_(self.parse_temporary_string(ins))
        ins.require_end()

    def exec_name(self, ins):
        """NAME: rename file or directory."""
        oldname = self.parse_temporary_string(ins)
        # AS is not a tokenised word
        ins.require_read(('AS',))
        newname = self.parse_temporary_string(ins)
        self.session.devices.name_(oldname, newname)
        ins.require_end()

    def exec_kill(self, ins):
        """KILL: remove file."""
        self.session.devices.kill_(self.parse_temporary_string(ins))
        ins.require_end()

    def exec_files(self, ins):
        """FILES: output directory listing."""
        pathmask = None
        if ins.skip_blank() not in tk.END_STATEMENT:
            pathmask = self.parse_temporary_string(ins)
        self.session.devices.files_(pathmask)
        ins.require_end()

    ###########################################################################
    # OS

    def exec_shell(self, ins):
        """SHELL: open OS shell and optionally execute command."""
        # parse optional shell command
        cmd = b''
        if ins.skip_blank() not in tk.END_STATEMENT:
            cmd = self.parse_temporary_string(ins)
        self.session.shell_(cmd)
        ins.require_end()

    def exec_environ(self, ins):
        """ENVIRON: set environment string."""
        envstr = self.parse_temporary_string(ins)
        dos.environ_statement_(envstr)
        ins.require_end()

    def exec_time(self, ins):
        """TIME$: set time."""
        ins.require_read((tk.O_EQ,))
        timestr = self.parse_temporary_string(ins)
        ins.require_end()
        self.session.clock.time_(timestr)

    def exec_date(self, ins):
        """DATE$: set date."""
        ins.require_read((tk.O_EQ,))
        datestr = self.parse_temporary_string(ins)
        ins.require_end()
        self.session.clock.date_(datestr)

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
        ins.require_end()

    def exec_merge(self, ins):
        """MERGE: merge lines from file into current program."""
        name = self.parse_temporary_string(ins)
        self.session.merge_(name)
        ins.require_end()

    def exec_new(self, ins):
        """NEW: clear program from memory."""
        ins.require_end()
        self.session.new_()

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

    def exec_reset(self, ins):
        """RESET: close all files."""
        self.session.files.reset_()
        ins.require_end()

    def exec_open(self, ins):
        """OPEN: open a file."""
        first_expr = self.parse_temporary_string(ins)
        if ins.skip_blank_read_if((',',)):
            args = self._parse_open_first(ins, first_expr)
        else:
            args = self._parse_open_second(ins, first_expr)
        self.session.files.open_(*args)
        ins.require_end()

    def _parse_open_first(self, ins, first_expr):
        """Parse OPEN first ('old') syntax."""
        mode = first_expr[:1].upper()
        if mode not in ('I', 'O', 'A', 'R'):
            raise error.RunError(error.BAD_FILE_MODE)
        number = self.parse_file_number(ins, opt_hash=True)
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
                    mode = {'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}[word]
                except KeyError:
                    ins.seek(-len(word), 1)
                    raise error.RunError(error.STX)
        # ACCESS clause
        access = None
        if ins.skip_blank_read_if(('ACCESS',), 6):
            access = self._parse_read_write(ins)
        # LOCK clause
        if ins.skip_blank_read_if((tk.LOCK,), 2):
            lock = self._parse_read_write(ins)
        else:
            lock = ins.skip_blank_read_if(('SHARED'), 6)
        # AS file number clause
        ins.require_read(('AS',))
        number = self.parse_file_number(ins, opt_hash=True)
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
                number = self.parse_file_number(ins, opt_hash=True)
                self.session.files.close_(number)
                if not ins.skip_blank_read_if((',',)):
                    break
        ins.require_end()

    def exec_field(self, ins):
        """FIELD: link a string variable to record buffer."""
        the_file = self.session.files.get(self.parse_file_number(ins, opt_hash=True), 'R')
        if ins.skip_blank_read_if((',',)):
            offset = 0
            while True:
                width = values.to_int(self.parse_expression(ins))
                error.range_check(0, 255, width)
                ins.require_read(('AS',), err=error.IFC)
                name, index = self.parse_variable(ins)
                self.session.files.field_(the_file, name, index, offset, width)
                offset += width
                if not ins.skip_blank_read_if((',',)):
                    break
        ins.require_end()

    def _parse_put_get_file(self, ins):
        """Parse record number for PUT and GET."""
        the_file = self.session.files.get(self.parse_file_number(ins, opt_hash=True), 'R')
        pos = None
        if ins.skip_blank_read_if((',',)):
            pos = self.parse_expression(ins)
        return (the_file, pos)

    def exec_put_file(self, ins):
        """PUT: write record to file."""
        self.session.files.put_(*self._parse_put_get_file(ins))
        ins.require_end()

    def exec_get_file(self, ins):
        """GET: read record from file."""
        self.session.files.get_(*self._parse_put_get_file(ins))
        ins.require_end()

    def _parse_lock_unlock(self, ins):
        """Parse lock records for LOCK or UNLOCK."""
        thefile = self.session.files.get(self.parse_file_number(ins, opt_hash=True))
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
        ins.require_end()

    def exec_unlock(self, ins):
        """UNLOCK: unset file or record locks."""
        self.session.files.unlock_(*self._parse_lock_unlock(ins))
        ins.require_end()

    def exec_ioctl(self, ins):
        """IOCTL: send control string to I/O device."""
        thefile = self.session.files.get(self.parse_file_number(ins, opt_hash=True))
        ins.require_read((',',))
        control_string = self.parse_temporary_string(ins)
        self.session.files.ioctl_statement_(thefile, control_string)
        ins.require_end()

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
        ins.require_end()

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
        ins.require_end()

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
        ins.require_end()

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
        if array not in self.session.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            raise error.RunError(error.TYPE_MISMATCH) # type mismatch
        self.session.screen.drawing.get(coord0, coord1, self.session.arrays, array)

    def exec_put_graph(self, ins):
        """PUT: draw sprite on screen."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP
        x, y = self._parse_coord_bare(ins)
        ins.require_read((',',))
        array = self._parse_name(ins)
        action = tk.XOR
        if ins.skip_blank_read_if((',',)):
            action = ins.require_read((tk.PSET, tk.PRESET, tk.AND, tk.OR, tk.XOR))
        ins.require_end()
        if array not in self.session.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        self.session.screen.drawing.put((x, y), self.session.arrays, array, action)

    def exec_draw(self, ins):
        """DRAW: draw a figure defined by a Graphics Macro Language string."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        gml = self.parse_temporary_string(ins)
        ins.require_end()
        self.session.screen.drawing.draw(gml, self.memory, self.values, self.session.events)

    ##########################################################
    # Flow-control statements

    def exec_end(self, ins):
        """END: end program execution and return to interpreter."""
        ins.require_end()
        self.session.interpreter.stop = self.session.program.bytecode.tell()
        # jump to end of direct line so execution stops
        self.session.interpreter.set_pointer(False)
        # avoid NO RESUME
        self.session.interpreter.error_handle_mode = False
        self.session.interpreter.error_resume = None
        self.session.files.close_all()

    def exec_stop(self, ins):
        """STOP: break program execution and return to interpreter."""
        ins.require_end()
        raise error.Break(stop=True)

    def exec_cont(self, ins):
        """CONT: continue STOPped or ENDed execution."""
        if self.session.interpreter.stop is None:
            raise error.RunError(error.CANT_CONTINUE)
        else:
            self.session.interpreter.set_pointer(True, self.session.interpreter.stop)
        # IN GW-BASIC, weird things happen if you do GOSUB nn :PRINT "x"
        # and there's a STOP in the subroutine.
        # CONT then continues and the rest of the original line is executed, printing x
        # However, CONT:PRINT triggers a bug - a syntax error in a nonexistant line number is reported.
        # CONT:PRINT "y" results in neither x nor y being printed.
        # if a command is executed before CONT, x is not printed.
        # It would appear that GW-BASIC only partially overwrites the line buffer and
        # then jumps back to the original return location!
        # in this implementation, the CONT command will fully overwrite the line buffer so x is not printed.

    def exec_for(self, ins):
        """FOR: enter for-loop."""
        # read variable
        varname = self._parse_name(ins)
        vartype = varname[-1]
        if vartype in ('$', '#'):
            raise error.RunError(error.TYPE_MISMATCH)
        ins.require_read((tk.O_EQ,))
        start = values.to_type(vartype, self.parse_expression(ins))
        ins.require_read((tk.TO,))
        stop = values.to_type(vartype, self.parse_expression(ins))
        if ins.skip_blank_read_if((tk.STEP,)):
            step = self.parse_expression(ins)
        else:
            # convert 1 to vartype
            step = self.values.from_value(1, vartype)
        step = values.to_type(vartype, step)
        ins.require_end()
        endforpos = ins.tell()
        # find NEXT
        nextpos = self._find_next(ins, varname)
        # apply initial condition and jump to nextpos
        self.session.interpreter.loop_init(ins, endforpos, nextpos, varname, start, stop, step)
        self.exec_next(ins)

    def _find_next(self, ins, varname):
        """Helper function for FOR: find the right NEXT."""
        current = ins.tell()
        ins.skip_block(tk.FOR, tk.NEXT, allow_comma=True)
        if ins.skip_blank() not in (tk.NEXT, ','):
            # FOR without NEXT marked with FOR line number
            ins.seek(current)
            raise error.RunError(error.FOR_WITHOUT_NEXT)
        comma = (ins.read(1) == ',')
        # get position and line number just after the NEXT
        nextpos = ins.tell()
        # check var name for NEXT
        # no-var only allowed in standalone NEXT
        if ins.skip_blank() not in tk.END_STATEMENT:
            varname2 = self._parse_name(ins)
        else:
            varname2 = None
        if (comma or varname2) and varname2 != varname:
            # NEXT without FOR marked with NEXT line number, while we're only at FOR
            raise error.RunError(error.NEXT_WITHOUT_FOR)
        ins.seek(current)
        return nextpos

    def exec_next(self, ins):
        """NEXT: iterate for-loop."""
        while True:
            # record the NEXT (or comma) location
            pos = ins.tell()
            # optional variable - errors in this are checked at the scan during FOR
            # if we haven't read a variable, we shouldn't find something else here
            # but if we have and we iterate, the rest of the line is ignored
            if ins.skip_blank() not in tk.END_STATEMENT + (',',):
                name = self._parse_name(ins)
            else:
                name = None
            # increment counter, check condition
            if self.session.interpreter.loop_iterate(ins, pos):
                break
            # done if we're not jumping into a comma'ed NEXT
            if not ins.skip_blank_read_if((',')):
                break
        # if we're done iterating we no longer ignore the rest of the statement
        ins.require_end()

    def exec_goto(self, ins):
        """GOTO: jump to specified line number."""
        # parse line number, ignore rest of line and jump
        self.session.interpreter.jump(self.parse_jumpnum(ins))

    def exec_run(self, ins):
        """RUN: start program execution."""
        jumpnum, close_files = None, True
        c = ins.skip_blank()
        if c == tk.T_UINT:
            # parse line number and ignore rest of line
            jumpnum = self.parse_jumpnum(ins)
        elif c not in tk.END_STATEMENT:
            name = self.parse_temporary_string(ins)
            if ins.skip_blank_read_if((',',)):
                ins.require_read('R')
                close_files = False
            ins.require_end()
            with self.session.files.open(0, name, filetype='ABP', mode='I') as f:
                self.session.program.load(f)
        self.session.interpreter.clear_stacks_and_pointers()
        self.session.clear_(close_files=close_files)
        self.session.interpreter.jump(jumpnum)
        self.session.interpreter.error_handle_mode = False

    def exec_if(self, ins):
        """IF: enter branching statement."""
        # avoid overflow: don't use bools.
        val = values.csng_(self.parse_expression(ins))
        ins.skip_blank_read_if((',',)) # optional comma
        ins.require_read((tk.THEN, tk.GOTO))
        if not val.is_zero():
            # TRUE: continue after THEN. line number or statement is implied GOTO
            if ins.skip_blank() in (tk.T_UINT,):
                self.session.interpreter.jump(self.parse_jumpnum(ins))
            # continue parsing as normal, :ELSE will be ignored anyway
        else:
            # FALSE: find ELSE block or end of line; ELSEs are nesting on the line
            nesting_level = 0
            while True:
                d = ins.skip_to_read(tk.END_STATEMENT + (tk.IF,))
                if d == tk.IF:
                    # nexting step on IF. (it's less convenient to count THENs because they could be THEN, GOTO or THEN GOTO.)
                    nesting_level += 1
                elif d == ':':
                    if ins.skip_blank_read_if((tk.ELSE,)): # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                        if nesting_level > 0:
                            nesting_level -= 1
                        else:
                            # line number: jump
                            if ins.skip_blank() in (tk.T_UINT,):
                                self.session.interpreter.jump(self.parse_jumpnum(ins))
                            # continue execution from here
                            break
                else:
                    ins.seek(-len(d), 1)
                    break

    def exec_else(self, ins):
        """ELSE: part of branch statement; ignore."""
        # any else statement by itself means the THEN has already been executed, so it's really like a REM.
        ins.skip_to(tk.END_LINE)

    def exec_while(self, ins):
        """WHILE: enter while-loop."""
        # just after WHILE opcode
        whilepos = ins.tell()
        # evaluate the 'boolean' expression
        # use double to avoid overflows
        # find matching WEND
        ins.skip_block(tk.WHILE, tk.WEND)
        if ins.read(1) == tk.WEND:
            ins.skip_to(tk.END_STATEMENT)
            wendpos = ins.tell()
            self.session.interpreter.while_stack.append((whilepos, wendpos))
        else:
            # WHILE without WEND
            ins.seek(whilepos)
            raise error.RunError(error.WHILE_WITHOUT_WEND)
        self._check_while_condition(ins, whilepos)
        ins.require_end()

    def _check_while_condition(self, ins, whilepos):
        """Check condition of while-loop."""
        ins.seek(whilepos)
        # WHILE condition is zero?
        if not values.pass_number(self.parse_expression(ins)).is_zero():
            # statement start is before WHILE token
            self.session.interpreter.current_statement = whilepos-2
            ins.require_end()
        else:
            # ignore rest of line and jump to WEND
            _, wendpos = self.session.interpreter.while_stack.pop()
            ins.seek(wendpos)

    def exec_wend(self, ins):
        """WEND: iterate while-loop."""
        # while will actually syntax error on the first run if anything is in the way.
        ins.require_end()
        pos = ins.tell()
        while True:
            if not self.session.interpreter.while_stack:
                # WEND without WHILE
                raise error.RunError(error.WEND_WITHOUT_WHILE)
            whilepos, wendpos = self.session.interpreter.while_stack[-1]
            if pos == wendpos:
                break
            # not the expected WEND, we must have jumped out
            self.session.interpreter.while_stack.pop()
        self._check_while_condition(ins, whilepos)

    def exec_on_jump(self, ins):
        """ON: calculated jump."""
        onvar = values.to_int(self.parse_expression(ins))
        error.range_check(0, 255, onvar)
        command = ins.skip_blank_read()
        jumps = []
        while True:
            d = ins.skip_blank_read()
            if d in tk.END_STATEMENT:
                ins.seek(-len(d), 1)
                break
            elif d in (tk.T_UINT,):
                jumps.append( ins.tell()-1 )
                ins.read(2)
            elif d == ',':
                pass
            else:
                raise error.RunError(error.STX)
        if jumps == []:
            raise error.RunError(error.STX)
        elif onvar > 0 and onvar <= len(jumps):
            ins.seek(jumps[onvar-1])
            if command == tk.GOTO:
                self.session.interpreter.jump(self.parse_jumpnum(ins))
            elif command == tk.GOSUB:
                self.exec_gosub(ins)
        ins.skip_to(tk.END_STATEMENT)

    def exec_on_error(self, ins):
        """ON ERROR: define error trapping routine."""
        ins.require_read((tk.GOTO,))  # GOTO
        linenum = self.parse_jumpnum(ins)
        if linenum != 0 and linenum not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        self.session.interpreter.on_error = linenum
        # pause soft-handling math errors so that we can catch them
        self.values.error_handler.suspend(linenum != 0)
        # ON ERROR GOTO 0 in error handler
        if self.session.interpreter.on_error == 0 and self.session.interpreter.error_handle_mode:
            # re-raise the error so that execution stops
            raise error.RunError(self.session.interpreter.error_num, self.session.interpreter.error_pos)
        # this will be caught by the trapping routine just set
        ins.require_end()

    def exec_resume(self, ins):
        """RESUME: resume program flow after error-trap."""
        if self.session.interpreter.error_resume is None:
            # unset error handler
            self.session.interpreter.on_error = 0
            raise error.RunError(error.RESUME_WITHOUT_ERROR)
        c = ins.skip_blank()
        if c == tk.NEXT:
            ins.read(1)
            jumpnum = -1
        elif c not in tk.END_STATEMENT:
            jumpnum = self.parse_jumpnum(ins)
        else:
            jumpnum = 0
        ins.require_end()
        start_statement, runmode = self.session.interpreter.error_resume
        self.session.interpreter.error_num = 0
        self.session.interpreter.error_handle_mode = False
        self.session.interpreter.error_resume = None
        self.session.events.suspend_all = False
        if jumpnum == 0:
            # RESUME or RESUME 0
            self.session.interpreter.set_pointer(runmode, start_statement)
        elif jumpnum == -1:
            # RESUME NEXT
            self.session.interpreter.set_pointer(runmode, start_statement)
            self.session.interpreter.get_codestream().skip_to(tk.END_STATEMENT, break_on_first_char=False)
        else:
            # RESUME n
            self.session.interpreter.jump(jumpnum)

    def exec_error(self, ins):
        """ERRROR: simulate an error condition."""
        errn = values.to_int(self.parse_expression(ins))
        error.range_check(1, 255, errn)
        raise error.RunError(errn)

    def exec_gosub(self, ins):
        """GOSUB: jump into a subroutine."""
        jumpnum = self.parse_jumpnum(ins)
        # ignore rest of statement ('GOSUB 100 LAH' works just fine..); we need to be able to RETURN
        ins.skip_to(tk.END_STATEMENT)
        self.session.interpreter.jump_gosub(jumpnum)

    def exec_return(self, ins):
        """RETURN: return from a subroutine."""
        # return *can* have a line number
        if ins.skip_blank() not in tk.END_STATEMENT:
            jumpnum = self.parse_jumpnum(ins)
            # rest of line is ignored
            ins.skip_to(tk.END_STATEMENT)
        else:
            jumpnum = None
        self.session.interpreter.jump_return(jumpnum)

    ################################################
    # Variable & array statements

    def _parse_var_list(self, ins):
        """Helper function: parse variable list.  """
        readvar = []
        while True:
            readvar.append(list(self.parse_variable(ins)))
            if not ins.skip_blank_read_if((',',)):
                break
        return readvar

    def exec_clear(self, ins):
        """CLEAR: clear memory and redefine memory limits."""
        # integer expression allowed but ignored
        intexp = self.parse_expression(ins, allow_empty=True)
        if intexp is not None:
            expr = values.to_int(intexp)
            if expr < 0:
                raise error.RunError(error.IFC)
        if ins.skip_blank_read_if((',',)):
            exp1 = self.parse_expression(ins, allow_empty=True)
            if exp1 is not None:
                # this produces a *signed* int
                mem_size = values.to_int(exp1, unsigned=True)
                if mem_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                else:
                    if not self.memory.set_basic_memory_size(mem_size):
                        raise error.RunError(error.OUT_OF_MEMORY)
            if ins.skip_blank_read_if((',',)):
                # set aside stack space for GW-BASIC. The default is the previous stack space size.
                exp2 = self.parse_expression(ins, allow_empty=True)
                if exp2 is not None:
                    stack_size = values.to_int(exp2, unsigned=True)
                    # this should be an unsigned int
                    if stack_size < 0:
                        stack_size += 0x10000
                    if stack_size == 0:
                        #  0 leads to illegal fn call
                        raise error.RunError(error.IFC)
                    self.memory.set_stack_size(stack_size)
                if self.syntax in ('pcjr', 'tandy') and ins.skip_blank_read_if((',',)):
                    # Tandy/PCjr: select video memory size
                    video_size = values.round(self.parse_expression(ins)).to_value()
                    if not self.session.screen.set_video_memory_size(video_size):
                        self.session.screen.screen(0, 0, 0, 0)
                        self.session.screen.init_mode()
                elif not exp2:
                    raise error.RunError(error.STX)
        ins.require_end()
        self.session.clear_()

    def exec_common(self, ins):
        """COMMON: define variables to be preserved on CHAIN."""
        common_scalars, common_arrays = set(), set()
        while True:
            name = self._parse_name(ins)
            # array?
            if ins.skip_blank_read_if(('[', '(')):
                ins.require_read((']', ')'))
                common_arrays.add(name)
            else:
                common_scalars.add(name)
            if not ins.skip_blank_read_if((',',)):
                break
        self.session.common_scalars |= common_scalars
        self.session.common_arrays |= common_arrays

    def exec_data(self, ins):
        """DATA: data definition; ignore."""
        # ignore rest of statement after DATA
        ins.skip_to(tk.END_STATEMENT)

    def exec_dim(self, ins):
        """DIM: dimension arrays."""
        while True:
            name, dimensions = self.parse_variable(ins)
            if not dimensions:
                dimensions = [10]
            self.session.arrays.dim(name, dimensions)
            if not ins.skip_blank_read_if((',',)):
                break
        ins.require_end()

    def exec_deftype(self, ins, typechar):
        """DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables."""
        while True:
            start = ins.skip_blank_read()
            if start not in string.ascii_letters:
                raise error.RunError(error.STX)
            stop = start
            if ins.skip_blank_read_if((tk.O_MINUS,)):
                stop = ins.skip_blank_read()
                if stop not in string.ascii_letters:
                    raise error.RunError(error.STX)
            self.memory.set_deftype(start, stop, typechar)
            if not ins.skip_blank_read_if((',',)):
                break
        ins.require_end()

    def exec_erase(self, ins):
        """ERASE: erase an array."""
        while True:
            self.session.arrays.erase(self._parse_name(ins))
            if not ins.skip_blank_read_if((',',)):
                break
        ins.require_end()

    def exec_let(self, ins):
        """LET: assign value to variable or array."""
        name, indices = self.parse_variable(ins)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out of range afterwards
            self.session.arrays.check_dim(name, indices)
        ins.require_read((tk.O_EQ,))
        self.memory.set_variable(name, indices, self.parse_expression(ins))
        ins.require_end()

    def exec_mid(self, ins):
        """MID$: set part of a string."""
        # do not use require_read as we don't allow whitespace here
        if ins.read(1) != '(':
            raise error.RunError(error.STX)
        name, indices = self.parse_variable(ins)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            self.session.arrays.check_dim(name, indices)
        ins.require_read((',',))
        start = self.parse_value(ins, values.INT)
        num = None
        if ins.skip_blank_read_if((',',)):
            num = self.parse_value(ins, values.INT)
        ins.require_read((')',))
        with self.temp_string:
            s = values.pass_string(self.memory.get_variable(name, indices)).to_str()
        num = 255 if num is None else num
        error.range_check(0, 255, num)
        if num > 0:
            error.range_check(1, len(s), start)
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by midset if applied to a code literal
        val = values.pass_string(self.parse_expression(ins))
        ins.require_end()
        # copy new value into existing buffer if possible
        basic_str = self.memory.get_variable(name, indices)
        self.memory.set_variable(name, indices, basic_str.midset(start, num, val))

    def exec_lset(self, ins, justify_right=False):
        """LSET: assign string value in-place; left justified."""
        name, index = self.parse_variable(ins)
        v = values.pass_string(self.memory.get_variable(name, index))
        ins.require_read((tk.O_EQ,))
        # we're not using a temp string here
        # as it would delete the new string generated by lset if applied to a code literal
        s = values.pass_string(self.parse_expression(ins))
        # copy new value into existing buffer if possible
        self.memory.set_variable(name, index, v.lset(s, justify_right))

    def exec_rset(self, ins):
        """RSET: assign string value in-place; right justified."""
        self.exec_lset(ins, justify_right=True)

    def exec_option(self, ins):
        """OPTION BASE: set array indexing convention."""
        ins.require_read(('BASE',))
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = ins.require_read(('0', '1'))
        self.session.arrays.base(int(d))
        ins.skip_to(tk.END_STATEMENT)

    def exec_read(self, ins):
        """READ: read values from DATA statement."""
        # reading loop
        for name, indices in self._parse_var_list(ins):
            entry = self.session.interpreter.read_entry()
            if name[-1] == '$':
                if ins == self.session.program.bytecode:
                    address = self.session.interpreter.data_pos + self.memory.code_start
                else:
                    address = None
                value = self.values.from_str_at(entry, address)
            else:
                value = self.values.from_repr(entry, allow_nonnum=False)
                if value is None:
                    # set pointer for EDIT gadget to position in DATA statement
                    self.session.program.bytecode.seek(self.session.interpreter.data_pos)
                    # syntax error in DATA line (not type mismatch!) if can't convert to var type
                    raise error.RunError(error.STX, self.session.interpreter.data_pos-1)
            self.memory.set_variable(name, indices, value=value)
        ins.require_end()

    def exec_input(self, ins):
        """INPUT: request input from user."""
        file_number = self.parse_file_number(ins, opt_hash=False)
        if file_number is not None:
            finp = self.session.files.get(file_number, mode='IR')
            ins.require_read((',',))
            readvar = self._parse_var_list(ins)
            parseinput.input_file_(self.memory, self.values, finp, readvar)
        else:
            # ; to avoid echoing newline
            newline = not ins.skip_blank_read_if((';',))
            prompt = parseinput.parse_prompt(ins, '? ')
            readvar = self._parse_var_list(ins)
            # move the program pointer to the start of the statement to ensure correct behaviour for CONT
            pos = ins.tell()
            ins.seek(self.session.interpreter.current_statement)
            parseinput.input_(self.session, self.values, prompt, readvar, newline)
            ins.seek(pos)
        ins.require_end()

    def exec_line_input(self, ins):
        """LINE INPUT: request line of input from user."""
        prompt, newline, finp = None, None, None
        file_number = self.parse_file_number(ins, opt_hash=False)
        if file_number is None:
            # ; to avoid echoing newline
            newline = not ins.skip_blank_read_if((';',))
            # get prompt
            prompt = parseinput.parse_prompt(ins, '')
        else:
            finp = self.session.files.get(file_number, mode='IR')
            ins.require_read((',',))
        # get string variable
        readvar, indices = self.parse_variable(ins)
        parseinput.line_input_(
            self.session, self.values, finp, prompt, readvar, indices, newline)

    def exec_restore(self, ins):
        """RESTORE: reset DATA pointer."""
        if not ins.skip_blank() in tk.END_STATEMENT:
            ins.require_read((tk.T_UINT,), err=error.UNDEFINED_LINE_NUMBER)
            datanum = self.parse_jumpnum(ins)
        else:
            datanum = -1
        # undefined line number for all syntax errors
        ins.require_end(err=error.UNDEFINED_LINE_NUMBER)
        self.session.interpreter.restore(datanum)

    def exec_swap(self, ins):
        """SWAP: swap values of two variables."""
        name1, index1 = self.parse_variable(ins)
        ins.require_read((',',))
        name2, index2 = self.parse_variable(ins)
        self.memory.swap(name1, index1, name2, index2)
        # if syntax error. the swap has happened
        ins.require_end()

    def exec_def_fn(self, ins):
        """DEF FN: define a function."""
        # don't allow DEF FN in direct mode, as we point to the code in the stored program
        # this is raised before further syntax errors
        if not self.run_mode:
            raise error.RunError(error.ILLEGAL_DIRECT)
        fnname = self._parse_name(ins)
        ins.skip_blank()
        self.expression_parser.user_functions.define(fnname, ins)

    def exec_randomize(self, ins):
        """RANDOMIZE: set random number generator seed."""
        val = self.parse_expression(ins, allow_empty=True)
        if val is not None:
            # don't convert to int if provided in the code
            val = values.pass_number(val)
        else:
            # prompt for random seed if not specified
            while val is None:
                self.session.screen.write("Random number seed (-32768 to 32767)? ")
                seed = self.session.editor.wait_screenline()
                val = self.values.from_repr(seed, allow_nonnum=False)
            # seed entered on prompt is rounded to int
            val = values.cint_(val)
        self.session.randomiser.randomize_(val)
        ins.require_end()

    ################################################
    # Console statements

    def exec_cls(self, ins):
        """CLS: clear the screen."""
        val = None
        if not (self.syntax == 'pcjr' or
                        ins.skip_blank() in (',',) + tk.END_STATEMENT):
            val = self.parse_value(ins, values.INT)
            # tandy gives illegal function call on CLS number
            error.throw_if(self.syntax == 'tandy')
            error.range_check(0, 2, val)
        if self.syntax != 'pcjr':
            if ins.skip_blank_read_if((',',)):
                # comma is ignored, but a number after means syntax error
                ins.require_end()
            else:
                ins.require_end(err=error.IFC)
        self.session.screen.cls_(val)
        if self.syntax == 'pcjr':
            ins.require_end()

    def exec_color(self, ins):
        """COLOR: set colour attributes."""
        fore, back, bord = None, None, None
        fore = self.parse_value(ins, values.INT, allow_empty=True)
        if ins.skip_blank_read_if((',',)):
            back = self.parse_value(ins, values.INT, allow_empty=True)
            if ins.skip_blank_read_if((',',)):
                bord = self.parse_value(ins, values.INT)
        self.session.screen.color_(fore, back, bord)
        ins.require_end()

    def exec_palette(self, ins):
        """PALETTE: set colour palette entry."""
        d = ins.skip_blank()
        if d in tk.END_STATEMENT:
            # reset palette
            self.session.screen.palette.set_all(self.session.screen.mode.palette)
        elif d == tk.USING:
            ins.read(1)
            self.exec_palette_using(ins)
        else:
            attrib = self.parse_value(ins, values.INT, allow_empty=True)
            ins.require_read((',',))
            colour = self.parse_value(ins, values.INT, allow_empty=True)
            error.throw_if(attrib is None or colour is None, error.STX)
            self.session.screen.palette.palette_(attrib, colour)
            ins.require_end()

    def exec_palette_using(self, ins):
        """PALETTE USING: set full colour palette."""
        array_name, start_indices = self.parse_variable(ins)
        # brackets are not optional
        error.throw_if(not start_indices, error.STX)
        self.session.screen.palette.palette_using_(array_name, start_indices, self.session.arrays)
        ins.require_end()

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
        ins.require_end()

    def exec_key_define(self, ins):
        """KEY: define function-key shortcut or scancode for event trapping."""
        keynum = values.to_int(self.parse_expression(ins))
        error.range_check(1, 255, keynum)
        ins.require_read((',',), err=error.IFC)
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

    def exec_write(self, ins, output=None):
        """WRITE: Output machine-readable expressions to the screen or a file."""
        file_number = self.parse_file_number(ins, opt_hash=False)
        if file_number is None:
            output = self.session.devices.scrn_file
        else:
            output = self.session.files.get(file_number, 'OAR')
            ins.require_read((',',))
        outstr = parseprint.write_(self, ins)
        ins.require_end()
        # write the whole thing as one thing (this affects line breaks)
        output.write_line(outstr)

    def exec_print(self, ins, output=None):
        """PRINT: Write expressions to the screen or a file."""
        # if no output specified (i.e. not LPRINT), check for a file number
        if output is None:
            file_number = self.parse_file_number(ins, opt_hash=False)
            if file_number is not None:
                output = self.session.files.get(file_number, 'OAR')
                ins.require_read((',',))
        if output is None:
            # neither LPRINT not a file number: print to screen
            output = self.session.devices.scrn_file
        newline = parseprint.print_(self, ins, output)
        if newline:
            if output == self.session.devices.scrn_file and self.session.screen.overflow:
                output.write_line()
            output.write_line()
        ins.require_end()

    def exec_lprint(self, ins):
        """LPRINT: Write expressions to printer LPT1."""
        self.exec_print(ins, self.session.devices.lpt1_file)

    def exec_view_print(self, ins):
        """VIEW PRINT: set scroll region."""
        if ins.skip_blank() in tk.END_STATEMENT:
            self.session.screen.unset_view()
        else:
            start = values.to_int(self.parse_expression(ins))
            ins.require_read((tk.TO,))
            stop = values.to_int(self.parse_expression(ins))
            ins.require_end()
            max_line = 25 if (self.syntax in ('pcjr', 'tandy') and not self.session.fkey_macros.keys_visible) else 24
            error.range_check(1, max_line, start, stop)
            self.session.screen.set_view(start, stop)

    def exec_width(self, ins):
        """WIDTH: set width of screen or device."""
        d = ins.skip_blank()
        if d == '#':
            file_number = self.parse_file_number(ins, opt_hash=False)
            dev = self.session.files.get(file_number, mode='IOAR')
            ins.require_read((',',))
            w = self.parse_value(ins, values.INT)
            error.range_check(0, 255, w)
            ins.require_end()
            dev.set_width(w)
        elif d == tk.LPRINT:
            ins.read(1)
            dev = self.session.devices.lpt1_file
            w = self.parse_value(ins, values.INT)
            error.range_check(0, 255, w)
            ins.require_end()
            dev.set_width(w)
        else:
            with self.temp_string:
                if d in string.digits or d in tk.NUMBER:
                    expr = self.expression_parser.read_number_literal(ins)
                else:
                    expr = self.parse_expression(ins)
                if isinstance(expr, values.String):
                    devname = expr.to_str().upper()
                    ins.require_read((',',))
                    w = self.parse_value(ins, values.INT)
                    try:
                        dev = self.session.devices.devices[devname].device_file
                    except (KeyError, AttributeError):
                        # bad file name
                        raise error.RunError(error.BAD_FILE_NAME)
                    ins.require_end()
                    dev.set_width(w)
                else:
                    w = values.to_int(expr)
                    if not ins.skip_blank_read_if((',',)):
                        ins.require_end(error.IFC)
                    else:
                        # parse dummy number rows setting
                        num_rows_dummy = self.parse_value(ins, values.INT, allow_empty=True)
                        # trailing comma is accepted
                        ins.skip_blank_read_if((',',))
                        ins.require_end()
                        if num_rows_dummy is not None:
                            min_num_rows = 0 if self.syntax in ('pcjr', 'tandy') else 25
                            error.range_check(min_num_rows, 25, num_rows_dummy)
                    self.session.devices.scrn_file.set_width(w)

    def exec_screen(self, ins):
        """SCREEN: change video mode or page."""
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        # mode, color, apagenum, vpagenum, erase=1
        args = [None] * 4 + [1]
        # erase can only be set on pcjr/tandy 5-argument syntax
        n_args = 4 + (self.syntax in ('pcjr', 'tandy'))
        # all but last arguments are optional and may be followed by a comma
        for i in range(len(args) - 1):
            args[i] = self.parse_value(ins, values.INT, allow_empty=True)
            if not ins.skip_blank_read_if((',',)):
                break
        else:
            # last argument is not optional (neither in 4- nor 5-argument syntax)
            # and may not be followed by a comma
            args[-1] = self.parse_value(ins, values.INT, allow_empty=False)
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
        self.session.screen.copy_page(src, dst)
