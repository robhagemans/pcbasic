"""
PC-BASIC - statements.py
Statement parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
from functools import partial
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import string

from . import error
from . import fp
from . import vartypes
from . import values
from . import ports
from . import print_and_input
from . import basictoken as tk
from . import util


class Statements(object):
    """BASIC statements."""

    def __init__(self, parser):
        """Initialise statement context."""
        self.parser = parser
        self.session = parser.session
        self._init_statements()

    def _init_statements(self):
        """Initialise statements."""
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
        self._init_statements()


    def exec_system(self, ins):
        """SYSTEM: exit interpreter."""
        # SYSTEM LAH does not execute
        util.require(ins, tk.end_statement)
        raise error.Exit()

    def exec_tron(self, ins):
        """TRON: turn on line number tracing."""
        self.parser.tron = True
        # TRON LAH gives error, but TRON has been executed
        util.require(ins, tk.end_statement)

    def exec_troff(self, ins):
        """TROFF: turn off line number tracing."""
        self.tron = False
        util.require(ins, tk.end_statement)

    def exec_rem(self, ins):
        """REM: comment."""
        # skip the rest of the line, but parse numbers to avoid triggering EOL
        util.skip_to(ins, tk.end_line)

    def exec_lcopy(self, ins):
        """LCOPY: do nothing but check for syntax errors."""
        # See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY
        if util.skip_white(ins) not in tk.end_statement:
            util.range_check(0, 255, vartypes.pass_int_unpack(
                    self.parser.parse_expression(ins, self.session)))
            util.require(ins, tk.end_statement)

    def exec_motor(self, ins):
        """MOTOR: do nothing but check for syntax errors."""
        self.exec_lcopy(ins)

    def exec_debug(self, ins):
        """DEBUG: execute Python command."""
        # this is not a GW-BASIC behaviour, but helps debugging.
        # this is parsed like a REM by the tokeniser.
        # rest of the line is considered to be a python statement
        util.skip_white(ins)
        debug_cmd = ''
        while util.peek(ins) not in tk.end_line:
            debug_cmd += ins.read(1)
        self.session.debugger.debug_exec(debug_cmd)

    def exec_term(self, ins):
        """TERM: load and run PCjr buitin terminal emulator program."""
        try:
            util.require(ins, tk.end_statement)
            self.session.load_program(self.parser.term)
        except EnvironmentError:
            # on Tandy, raises Internal Error
            raise error.RunError(error.INTERNAL_ERROR)
        self.parser.clear_stacks_and_pointers()
        self.session.clear()
        self.parser.jump(None)
        self.parser.error_handle_mode = False
        self.parser.tron = False


    ##########################################################
    # statements that require further qualification

    def exec_def(self, ins):
        """DEF: select DEF FN, DEF USR, DEF SEG."""
        c = util.skip_white(ins)
        if util.read_if(ins, c, (tk.FN,)):
            self.exec_def_fn(ins)
        elif util.read_if(ins, c, (tk.USR,)):
            self.exec_def_usr(ins)
        # must be uppercase in tokenised form, otherwise syntax error
        elif util.skip_white_read_if(ins, ('SEG',)):
            self.exec_def_seg(ins)
        else:
            raise error.RunError(error.STX)

    def exec_view(self, ins):
        """VIEW: select VIEW PRINT, VIEW (graphics)."""
        if util.skip_white_read_if(ins, (tk.PRINT,)):
            self.exec_view_print(ins)
        else:
            self.exec_view_graph(ins)

    def exec_line(self, ins):
        """LINE: select LINE INPUT, LINE (graphics)."""
        if util.skip_white_read_if(ins, (tk.INPUT,)):
            self.exec_line_input(ins)
        else:
            self.exec_line_graph(ins)

    def exec_get(self, ins):
        """GET: select GET (graphics), GET (files)."""
        if util.skip_white(ins) == '(':
            self.exec_get_graph(ins)
        else:
            self.exec_get_file(ins)

    def exec_put(self, ins):
        """PUT: select PUT (graphics), PUT (files)."""
        if util.skip_white(ins) == '(':
            self.exec_put_graph(ins)
        else:
            self.exec_put_file(ins)

    def exec_on(self, ins):
        """ON: select ON ERROR, ON KEY, ON TIMER, ON PLAY, ON COM, ON PEN, ON STRIG
            or ON (jump statement)."""
        c = util.skip_white(ins)
        if util.read_if(ins, c, (tk.ERROR,)):
            self.exec_on_error(ins)
        elif util.read_if(ins, c, (tk.KEY,)):
            self.exec_on_key(ins)
        elif c in ('\xFE', '\xFF'):
            c = util.peek(ins, 2)
            if util.read_if(ins, c, (tk.TIMER,)):
                self.exec_on_timer(ins)
            elif util.read_if(ins, c, (tk.PLAY,)):
                self.exec_on_play(ins)
            elif util.read_if(ins, c, (tk.COM,)):
                self.exec_on_com(ins)
            elif util.read_if(ins, c, (tk.PEN,)):
                self.exec_on_pen(ins)
            elif util.read_if(ins, c, (tk.STRIG,)):
                self.exec_on_strig(ins)
            else:
                self.exec_on_jump(ins)
        else:
            self.exec_on_jump(ins)

    ##########################################################
    # event switches (except PLAY) and event definitions

    def exec_pen(self, ins):
        """PEN: switch on/off light pen event handling."""
        if self.session.events.pen.command(util.skip_white(ins)):
            ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(ins, tk.end_statement)

    def exec_strig(self, ins):
        """STRIG: switch on/off fire button event handling."""
        d = util.skip_white(ins)
        if d == '(':
            # strig (n)
            num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
            if num not in (0,2,4,6):
                raise error.RunError(error.IFC)
            if self.session.events.strig[num//2].command(util.skip_white(ins)):
                ins.read(1)
            else:
                raise error.RunError(error.STX)
        elif d == tk.ON:
            ins.read(1)
            self.session.stick.switch(True)
        elif d == tk.OFF:
            ins.read(1)
            self.session.stick.switch(False)
        else:
            raise error.RunError(error.STX)
        util.require(ins, tk.end_statement)

    def exec_com(self, ins):
        """COM: switch on/off serial port event handling."""
        util.require(ins, ('(',))
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(1, 2, num)
        if self.session.events.com[num-1].command(util.skip_white(ins)):
            ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(ins, tk.end_statement)

    def exec_timer(self, ins):
        """TIMER: switch on/off timer event handling."""
        if self.session.events.timer.command(util.skip_white(ins)):
            ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(ins, tk.end_statement)

    def exec_key_events(self, ins):
        """KEY: switch on/off keyboard events."""
        num = vartypes.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        util.range_check(0, 255, num)
        d = util.skip_white(ins)
        # others are ignored
        if num >= 1 and num <= 20:
            if self.session.events.key[num-1].command(d):
                ins.read(1)
            else:
                raise error.RunError(error.STX)

    def _parse_on_event(self, ins, bracket=True):
        """Helper function for ON event trap definitions."""
        num = None
        if bracket:
            num = self.parser.parse_bracket(ins, self.session)
        util.require_read(ins, (tk.GOSUB,))
        jumpnum = util.parse_jumpnum(ins)
        if jumpnum == 0:
            jumpnum = None
        elif jumpnum not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        util.require(ins, tk.end_statement)
        return num, jumpnum

    def exec_on_key(self, ins):
        """ON KEY: define key event trapping."""
        keynum, jumpnum = self._parse_on_event(ins)
        keynum = vartypes.pass_int_unpack(keynum)
        util.range_check(1, 20, keynum)
        self.session.events.key[keynum-1].set_jump(jumpnum)

    def exec_on_timer(self, ins):
        """ON TIMER: define timer event trapping."""
        timeval, jumpnum = self._parse_on_event(ins)
        timeval = vartypes.pass_single(timeval)
        period = fp.mul(fp.unpack(timeval), fp.Single.from_int(1000)).round_to_int()
        self.session.events.timer.set_trigger(period)
        self.session.events.timer.set_jump(jumpnum)

    def exec_on_play(self, ins):
        """ON PLAY: define music event trapping."""
        playval, jumpnum = self._parse_on_event(ins)
        playval = vartypes.pass_int_unpack(playval)
        self.session.events.play.set_trigger(playval)
        self.session.events.play.set_jump(jumpnum)

    def exec_on_pen(self, ins):
        """ON PEN: define light pen event trapping."""
        _, jumpnum = self._parse_on_event(ins, bracket=False)
        self.session.events.pen.set_jump(jumpnum)

    def exec_on_strig(self, ins):
        """ON STRIG: define fire button event trapping."""
        strigval, jumpnum = self._parse_on_event(ins)
        strigval = vartypes.pass_int_unpack(strigval)
        ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
        if strigval not in (0,2,4,6):
            raise error.RunError(error.IFC)
        self.session.events.strig[strigval//2].set_jump(jumpnum)

    def exec_on_com(self, ins):
        """ON COM: define serial port event trapping."""
        keynum, jumpnum = self._parse_on_event(ins)
        keynum = vartypes.pass_int_unpack(keynum)
        util.range_check(1, 2, keynum)
        self.session.events.com[keynum-1].set_jump(jumpnum)

    ##########################################################
    # sound

    def exec_beep(self, ins):
        """BEEP: produce an alert sound or switch internal speaker on/off."""
        # Tandy/PCjr BEEP ON, OFF
        if self.parser.syntax in ('pcjr', 'tandy') and util.skip_white(ins) in (tk.ON, tk.OFF):
            # this is ignored
            #self.session.sound.beep_on = (ins.read(1) == tk.ON)
            util.require(ins, tk.end_statement)
            return
        self.session.sound.beep()
        # if a syntax error happens, we still beeped.
        util.require(ins, tk.end_statement)
        if self.session.sound.foreground:
            self.session.sound.wait_music()

    def exec_sound(self, ins):
        """SOUND: produce an arbitrary sound or switch external speaker on/off."""
        # Tandy/PCjr SOUND ON, OFF
        if self.parser.syntax in ('pcjr', 'tandy') and util.skip_white(ins) in (tk.ON, tk.OFF):
            self.session.sound.sound_on = (ins.read(1) == tk.ON)
            util.require(ins, tk.end_statement)
            return
        freq = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (',',))
        dur = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session)))
        if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
            raise error.RunError(error.IFC)
        # only look for args 3 and 4 if duration is > 0; otherwise those args are a syntax error (on tandy)
        volume, voice = 15, 0
        if dur.gt(fp.Single.zero):
            if (util.skip_white_read_if(ins, (',',)) and (self.parser.syntax == 'tandy' or
                    (self.parser.syntax == 'pcjr' and self.session.sound.sound_on))):
                volume = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
                util.range_check(0, 15, volume)
                if util.skip_white_read_if(ins, (',',)):
                    voice = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
                    util.range_check(0, 2, voice) # can't address noise channel here
        util.require(ins, tk.end_statement)
        if dur.is_zero():
            self.session.sound.stop_all_sound()
            return
        # Tandy only allows frequencies below 37 (but plays them as 110 Hz)
        if freq != 0:
            util.range_check(-32768 if self.parser.syntax == 'tandy' else 37, 32767, freq) # 32767 is pause
        # calculate duration in seconds
        one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
        dur_sec = dur.to_value()/18.2
        if one_over_44.gt(dur):
            # play indefinitely in background
            self.session.sound.play_sound(freq, 1, loop=True, voice=voice, volume=volume)
        else:
            self.session.sound.play_sound(freq, dur_sec, voice=voice, volume=volume)
            if self.session.sound.foreground:
                self.session.sound.wait_music()

    def exec_play(self, ins):
        """PLAY: play sound sequence defined by a Music Macro Language string."""
        # PLAY: event switch
        if self.session.events.play.command(util.skip_white(ins)):
            ins.read(1)
            util.require(ins, tk.end_statement)
        else:
            # retrieve Music Macro Language string
            with self.session.strings:
                mml0 = self.session.strings.copy(vartypes.pass_string(
                        self.parser.parse_expression(ins, self.session, allow_empty=True),
                        allow_empty=True))
            mml1, mml2 = '', ''
            if ((self.parser.syntax == 'tandy' or (self.parser.syntax == 'pcjr' and
                                             self.session.sound.sound_on))
                    and util.skip_white_read_if(ins, (',',))):
                with self.session.strings:
                    mml1 = self.session.strings.copy(vartypes.pass_string(
                            self.parser.parse_expression(ins, self.session, allow_empty=True),
                            allow_empty=True))
                if util.skip_white_read_if(ins, (',',)):
                    with self.session.strings:
                        mml2 = self.session.strings.copy(vartypes.pass_string(
                                self.parser.parse_expression(ins, self.session, allow_empty=True),
                                allow_empty=True))
            util.require(ins, tk.end_statement)
            if not (mml0 or mml1 or mml2):
                raise error.RunError(error.MISSING_OPERAND)
            self.session.sound.play(self.session.memory, (mml0, mml1, mml2))

    def exec_noise(self, ins):
        """NOISE: produce sound on the noise generator (Tandy/PCjr)."""
        if not self.session.sound.sound_on:
            raise error.RunError(error.IFC)
        source = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (',',))
        volume = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (',',))
        util.range_check(0, 7, source)
        util.range_check(0, 15, volume)
        dur = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session)))
        if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
            raise error.RunError(error.IFC)
        util.require(ins, tk.end_statement)
        one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
        dur_sec = dur.to_value()/18.2
        if one_over_44.gt(dur):
            self.session.sound.play_noise(source, volume, dur_sec, loop=True)
        else:
            self.session.sound.play_noise(source, volume, dur_sec)


    ##########################################################
    # machine emulation

    def exec_poke(self, ins):
        """POKE: write to a memory location. Limited implementation."""
        addr = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint=0xffff)
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        util.require_read(ins, (',',))
        val = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, val)
        self.session.all_memory.poke(addr, val)
        util.require(ins, tk.end_statement)

    def exec_def_seg(self, ins):
        """DEF SEG: set the current memory segment."""
        # &hb800: text screen buffer; &h13d: data segment
        if util.skip_white_read_if(ins, (tk.O_EQ,)):
            # def_seg() accepts signed values
            self.session.all_memory.def_seg(vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint=0xffff))
        else:
            self.session.all_memory.def_seg(self.session.memory.data_segment)
        util.require(ins, tk.end_statement)

    def exec_def_usr(self, ins):
        """DEF USR: Define a machine language function. Not implemented."""
        util.require_read(ins, tk.digit)
        util.require_read(ins, (tk.O_EQ,))
        vartypes.pass_integer(self.parser.parse_expression(ins, self.session), maxint=0xffff)
        util.require(ins, tk.end_statement)
        logging.warning("DEF USR statement not implemented")

    def exec_bload(self, ins):
        """BLOAD: load a file into a memory location. Limited implementation."""
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        offset = None
        if util.skip_white_read_if(ins, (',',)):
            offset = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint=0xffff)
            if offset < 0:
                offset += 0x10000
        util.require(ins, tk.end_statement)
        with self.session.files.open(0, name, filetype='M', mode='I') as f:
            self.session.all_memory.bload(f, offset)

    def exec_bsave(self, ins):
        """BSAVE: save a block of memory to a file. Limited implementation."""
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        util.require_read(ins, (',',))
        offset = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint = 0xffff)
        if offset < 0:
            offset += 0x10000
        util.require_read(ins, (',',))
        length = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint = 0xffff)
        if length < 0:
            length += 0x10000
        util.require(ins, tk.end_statement)
        with self.session.files.open(0, name, filetype='M', mode='O',
                                seg=self.session.all_memory.segment,
                                offset=offset, length=length) as f:
            self.session.all_memory.bsave(f, offset, length)

    def exec_call(self, ins):
        """CALL: call an external procedure. Not implemented."""
        addr_var = self.parser.parse_scalar(ins)
        if addr_var[-1] == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        if util.skip_white_read_if(ins, ('(',)):
            while True:
                # if we wanted to call a function, we should distinguish varnames
                # (passed by ref) from constants (passed by value) here.
                self.parser.parse_expression(ins, self.session)
                if not util.skip_white_read_if(ins, (',',)):
                    break
            util.require_read(ins, (')',))
        util.require(ins, tk.end_statement)
        # ignore the statement
        logging.warning("CALL or CALLS statement not implemented")

    def exec_calls(self, ins):
        """CALLS: call an external procedure. Not implemented."""
        self.exec_call(ins)

    def exec_out(self, ins):
        """OUT: send a byte to a machine port. Limited implementation."""
        addr = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint=0xffff)
        util.require_read(ins, (',',))
        val = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, val)
        self.session.machine.out(addr, val)
        util.require(ins, tk.end_statement)

    def exec_wait(self, ins):
        """WAIT: wait for a machine port. Limited implementation."""
        addr = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), maxint=0xffff)
        util.require_read(ins, (',',))
        ander = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, ander)
        xorer = 0
        if util.skip_white_read_if(ins, (',',)):
            xorer = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, xorer)
        util.require(ins, tk.end_statement)
        self.session.machine.wait(addr, ander, xorer)


    ##########################################################
    # Disk

    def exec_chdir(self, ins):
        """CHDIR: change working directory."""
        with self.session.strings:
            dev, path = self.session.devices.get_diskdevice_and_path(
                self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session))))
        dev.chdir(path)
        util.require(ins, tk.end_statement)

    def exec_mkdir(self, ins):
        """MKDIR: create directory."""
        with self.session.strings:
            dev, path = self.session.devices.get_diskdevice_and_path(
                self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session))))
        dev.mkdir(path)
        util.require(ins, tk.end_statement)

    def exec_rmdir(self, ins):
        """RMDIR: remove directory."""
        with self.session.strings:
            dev, path = self.session.devices.get_diskdevice_and_path(
                self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session))))
        dev.rmdir(path)
        util.require(ins, tk.end_statement)

    def exec_name(self, ins):
        """NAME: rename file or directory."""
        with self.session.strings:
            oldname = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # AS is not a tokenised word
        word = util.skip_white_read(ins) + ins.read(1)
        if word.upper() != 'AS':
            raise error.RunError(error.STX)
        with self.session.strings:
            newname = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        dev, oldpath = self.session.devices.get_diskdevice_and_path(oldname)
        newdev, newpath = self.session.devices.get_diskdevice_and_path(newname)
        # don't rename open files
        dev.check_file_not_open(oldpath)
        if dev != newdev:
            raise error.RunError(error.RENAME_ACROSS_DISKS)
        dev.rename(oldpath, newpath)
        util.require(ins, tk.end_statement)

    def exec_kill(self, ins):
        """KILL: remove file."""
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # don't delete open files
        dev, path = self.session.devices.get_diskdevice_and_path(name)
        dev.check_file_not_open(path)
        dev.kill(path)
        util.require(ins, tk.end_statement)

    def exec_files(self, ins):
        """FILES: output directory listing."""
        pathmask = ''
        if util.skip_white(ins) not in tk.end_statement:
            with self.session.strings:
                pathmask = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
            if not pathmask:
                raise error.RunError(error.BAD_FILE_NAME)
        dev, path = self.session.devices.get_diskdevice_and_path(pathmask)
        dev.files(self.session.screen, path)
        util.require(ins, tk.end_statement)


    ##########################################################
    # OS

    def exec_shell(self, ins):
        """SHELL: open OS shell and optionally execute command."""
        # parse optional shell command
        cmd = b''
        if util.skip_white(ins) not in tk.end_statement:
            with self.session.strings:
                cmd = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # no SHELL on PCjr.
        if self.parser.syntax == 'pcjr':
            raise error.RunError(error.IFC)
        # force cursor visible in all cases
        self.session.screen.cursor.show(True)
        # sound stops playing and is forgotten
        self.session.sound.stop_all_sound()
        # no user events
        with self.session.events.suspend():
            # run the os-specific shell
            self.session.shell.launch(cmd)
        # reset cursor visibility to its previous state
        self.session.screen.cursor.reset_visibility()
        util.require(ins, tk.end_statement)

    def exec_environ(self, ins):
        """ENVIRON: set environment string."""
        with self.session.strings:
            envstr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        eqs = envstr.find('=')
        if eqs <= 0:
            raise error.RunError(error.IFC)
        envvar = str(envstr[:eqs])
        val = str(envstr[eqs+1:])
        os.environ[envvar] = val
        util.require(ins, tk.end_statement)

    def exec_time(self, ins):
        """TIME$: set time."""
        util.require_read(ins, (tk.O_EQ,)) #time$=
        # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
        with self.session.strings:
            timestr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require(ins, tk.end_statement)
        self.session.clock.set_time(timestr)

    def exec_date(self, ins):
        """DATE$: set date."""
        util.require_read(ins, (tk.O_EQ,)) # date$=
        # allowed formats:
        # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
        # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
        with self.session.strings:
            datestr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require(ins, tk.end_statement)
        self.session.clock.set_date(datestr)

    ##########################################################
    # code

    def _parse_line_range(self, ins):
        """Helper function: parse line number ranges."""
        from_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        if util.skip_white_read_if(ins, (tk.O_MINUS,)):
            to_line = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        else:
            to_line = from_line
        return (from_line, to_line)

    def _parse_jumpnum_or_dot(self, ins, allow_empty=False, err=error.STX):
        """Helper function: parse jump target."""
        c = util.skip_white_read(ins)
        if c == tk.T_UINT:
            return vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(ins.read(2)))
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
        util.require(ins, tk.end_statement)
        # throws back to direct mode
        self.session.program.delete(from_line, to_line)
        # clear all program stacks
        self.parser.clear_stacks_and_pointers()
        # clear all variables
        self.session.clear()

    def exec_edit(self, ins):
        """EDIT: output a program line and position cursor for editing."""
        if util.skip_white(ins) in tk.end_statement:
            # undefined line number
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        from_line = self._parse_jumpnum_or_dot(ins, err=error.IFC)
        if from_line is None or from_line not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        util.require(ins, tk.end_statement, err=error.IFC)
        # throws back to direct mode
        # jump to end of direct line so execution stops
        self.parser.set_pointer(False)
        self.session.screen.cursor.reset_visibility()
        # request edit prompt
        self.session.edit_prompt = (from_line, None)

    def exec_auto(self, ins):
        """AUTO: enter automatic line numbering mode."""
        linenum = self._parse_jumpnum_or_dot(ins, allow_empty=True)
        increment = None
        if util.skip_white_read_if(ins, (',',)):
            increment = util.parse_jumpnum(ins, allow_empty=True)
        util.require(ins, tk.end_statement)
        # reset linenum and increment on each call of AUTO (even in AUTO mode)
        self.session.auto_linenum = linenum if linenum is not None else 10
        self.session.auto_increment = increment if increment is not None else 10
        # move program pointer to end
        self.parser.set_pointer(False)
        # continue input in AUTO mode
        self.session.auto_mode = True

    def exec_list(self, ins):
        """LIST: output program lines."""
        from_line, to_line = self._parse_line_range(ins)
        out = None
        if util.skip_white_read_if(ins, (',',)):
            with self.session.strings:
                outname = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
            out = self.session.files.open(0, outname, filetype='A', mode='O')
            # ignore everything after file spec
            util.skip_to(ins, tk.end_line)
        util.require(ins, tk.end_statement)
        lines = self.session.program.list_lines(from_line, to_line)
        if out:
            with out:
                for l in lines:
                    out.write_line(l)
        else:
            for l in lines:
                # flow of listing is visible on screen
                # and interruptible
                self.session.events.wait()
                # LIST on screen is slightly different from just writing
                self.session.screen.list_line(l)
        # return to direct mode
        self.parser.set_pointer(False)

    def exec_llist(self, ins):
        """LLIST: output program lines to LPT1: """
        from_line, to_line = self._parse_line_range(ins)
        util.require(ins, tk.end_statement)
        for l in self.session.program.list_lines(from_line, to_line):
            self.session.devices.lpt1_file.write_line(l)
        # return to direct mode
        self.parser.set_pointer(False)

    def exec_load(self, ins):
        """LOAD: load program from file."""
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        comma = util.skip_white_read_if(ins, (',',))
        if comma:
            util.require_read(ins, 'R')
        util.require(ins, tk.end_statement)
        with self.session.files.open(0, name, filetype='ABP', mode='I') as f:
            self.session.program.load(f)
        # reset stacks
        self.parser.clear_stacks_and_pointers()
        # clear variables
        self.session.clear()
        if comma:
            # in ,R mode, don't close files; run the program
            self.parser.jump(None)
        else:
            self.session.files.close_all()
        self.parser.tron = False

    def exec_chain(self, ins):
        """CHAIN: load program and chain execution."""
        if util.skip_white_read_if(ins, (tk.MERGE,)):
            action = self.session.program.merge
        else:
            action = self.session.program.load
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        jumpnum, common_all, delete_lines = None, False, None
        if util.skip_white_read_if(ins, (',',)):
            # check for an expression that indicates a line in the other self.session.program. This is not stored as a jumpnum (to avoid RENUM)
            expr = self.parser.parse_expression(ins, self.session, allow_empty=True)
            if expr is not None:
                jumpnum = vartypes.pass_int_unpack(expr, maxint=0xffff)
                # negative numbers will be two's complemented into a line number
                if jumpnum < 0:
                    jumpnum = 0x10000 + jumpnum
            if util.skip_white_read_if(ins, (',',)):
                if util.skip_white_read_if(ins, ('ALL',)):
                    common_all = True
                    # CHAIN "file", , ALL, DELETE
                    if util.skip_white_read_if(ins, (',',)):
                        delete_lines = self._parse_delete_clause(ins)
                else:
                    # CHAIN "file", , DELETE
                    delete_lines = self._parse_delete_clause(ins)
        util.require(ins, tk.end_statement)
        if self.session.program.protected and action == self.session.program.merge:
                raise error.RunError(error.IFC)
        with self.session.files.open(0, name, filetype='ABP', mode='I') as f:
            if delete_lines:
                # delete lines from existing code before merge (without MERGE, this is pointless)
                self.session.program.delete(*delete_lines)
            action(f)
            # clear all program stacks
            self.parser.clear_stacks_and_pointers()
            # don't close files!
            # RUN
            self.parser.jump(jumpnum, err=error.IFC)
        # preserve DEFtype on MERGE
        self.session.clear(preserve_common=True, preserve_all=common_all, preserve_deftype=(action==self.session.program.merge))

    def _parse_delete_clause(self, ins):
        """Helper function: parse the DELETE clause of a CHAIN statement."""
        delete_lines = None
        if util.skip_white_read_if(ins, (tk.DELETE,)):
            from_line = util.parse_jumpnum(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (tk.O_MINUS,)):
                to_line = util.parse_jumpnum(ins, allow_empty=True)
            else:
                to_line = from_line
            # to_line must be specified and must be an existing line number
            if not to_line or to_line not in self.session.program.line_numbers:
                raise error.RunError(error.IFC)
            delete_lines = (from_line, to_line)
            # ignore rest if preceded by cmma
            if util.skip_white_read_if(ins, (',',)):
                util.skip_to(ins, tk.end_statement)
        return delete_lines

    def exec_save(self, ins):
        """SAVE: save program to a file."""
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        mode = 'B'
        if util.skip_white_read_if(ins, (',',)):
            mode = util.skip_white_read(ins).upper()
            if mode not in ('A', 'P'):
                raise error.RunError(error.STX)
        with self.session.files.open(0, name, filetype=mode, mode='O',
                                seg=self.session.memory.data_segment, offset=self.session.memory.code_start,
                                length=len(self.parser.program_code.getvalue())-1
                                ) as f:
            self.session.program.save(f)
        util.require(ins, tk.end_statement)

    def exec_merge(self, ins):
        """MERGE: merge lines from file into current program."""
        with self.session.strings:
            name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        with self.session.files.open(0, name, filetype='A', mode='I') as f:
            self.session.program.merge(f)
        # clear all program stacks
        self.parser.clear_stacks_and_pointers()
        util.require(ins, tk.end_statement)

    def exec_new(self, ins):
        """NEW: clear program from memory."""
        self.parser.tron = False
        # deletes the program currently in memory
        self.session.program.erase()
        # reset stacks
        self.parser.clear_stacks_and_pointers()
        # and clears all variables
        self.session.clear()
        self.parser.set_pointer(False)

    def exec_renum(self, ins):
        """RENUM: renumber program line numbers."""
        new, old, step = None, None, None
        if util.skip_white(ins) not in tk.end_statement:
            new = self._parse_jumpnum_or_dot(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                old = self._parse_jumpnum_or_dot(ins, allow_empty=True)
                if util.skip_white_read_if(ins, (',',)):
                    step = util.parse_jumpnum(ins, allow_empty=True) # returns -1 if empty
        util.require(ins, tk.end_statement)
        if step is not None and step < 1:
            raise error.RunError(error.IFC)
        old_to_new = self.session.program.renum(
                self.session.screen, new, old, step)
        # stop running if we were
        self.parser.set_pointer(False)
        # reset loop stacks
        self.parser.clear_stacks()
        # renumber error handler
        if self.parser.on_error:
            self.parser.on_error = old_to_new[self.parser.on_error]
        # renumber event traps
        for handler in self.session.events.all:
            if handler.gosub:
                handler.set_jump(old_to_new[handler.gosub])

    ##########################################################
    # file

    def exec_reset(self, ins):
        """RESET: close all files."""
        self.session.files.close_all()
        util.require(ins, tk.end_statement)

    def _parse_read_write(self, ins):
        """Helper function: parse access mode."""
        d = util.skip_white(ins)
        if d == tk.WRITE:
            ins.read(1)
            access = 'W'
        elif d == tk.READ:
            ins.read(1)
            access = 'RW' if util.skip_white_read_if(ins, (tk.WRITE,)) else 'R'
        return access


    def exec_open(self, ins):
        """OPEN: open a file."""
        long_modes = {tk.INPUT:'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}
        default_access_modes = {'I':'R', 'O':'W', 'A':'RW', 'R':'RW'}
        with self.session.strings:
            first_expr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        mode, access, lock, reclen = 'R', 'RW', '', 128
        if util.skip_white_read_if(ins, (',',)):
            # first syntax
            try:
                mode = first_expr[0].upper()
                access = default_access_modes[mode]
            except (IndexError, KeyError):
                raise error.RunError(error.BAD_FILE_MODE)
            number = self.parser.parse_file_number_opthash(ins, self.session)
            util.require_read(ins, (',',))
            with self.session.strings:
                name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
            if util.skip_white_read_if(ins, (',',)):
                reclen = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        else:
            # second syntax
            name = first_expr
            # FOR clause
            if util.skip_white_read_if(ins, (tk.FOR,)):
                c = util.skip_white(ins)
                # read word
                word = ''
                while c and c not in tk.whitespace and c not in tk.end_statement:
                    word += ins.read(1)
                    c = util.peek(ins).upper()
                try:
                    mode = long_modes[word]
                except KeyError:
                    raise error.RunError(error.STX)
            try:
                access = default_access_modes[mode]
            except (KeyError):
                raise error.RunError(error.BAD_FILE_MODE)
            # ACCESS clause
            if util.skip_white_read_if(ins, ('ACCESS',)):
                util.skip_white(ins)
                access = self._parse_read_write(ins)
            # LOCK clause
            if util.skip_white_read_if(ins, (tk.LOCK,)):
                util.skip_white(ins)
                lock = self._parse_read_write(ins)
            elif util.skip_white_read_if(ins, ('SHARED',)):
                lock = 'S'
            # AS file number clause
            if not util.skip_white_read_if(ins, ('AS',)):
                raise error.RunError(error.STX)
            number = self.parser.parse_file_number_opthash(ins, self.session)
            # LEN clause
            if util.skip_white_read_if(ins, (tk.LEN,)):
                util.require_read(ins, tk.O_EQ)
                reclen = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        # mode and access must match if not a RANDOM file
        # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
        # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
        if mode == 'A' and access == 'W':
            raise error.RunError(error.PATH_FILE_ACCESS_ERROR)
        elif mode != 'R' and access and access != default_access_modes[mode]:
            raise error.RunError(error.STX)
        util.range_check(1, self.session.memory.max_reclen, reclen)
        # can't open file 0, or beyond max_files
        util.range_check_err(1, self.session.memory.max_files, number, error.BAD_FILE_NUMBER)
        self.session.files.open(number, name, 'D', mode, access, lock, reclen)
        util.require(ins, tk.end_statement)

    def exec_close(self, ins):
        """CLOSE: close a file."""
        if util.skip_white(ins) in tk.end_statement:
            # allow empty CLOSE; close all open files
            self.session.files.close_all()
        else:
            while True:
                number = self.parser.parse_file_number_opthash(ins, self.session)
                try:
                    self.session.files.close(number)
                except KeyError:
                    pass
                if not util.skip_white_read_if(ins, (',',)):
                    break
        util.require(ins, tk.end_statement)

    def exec_field(self, ins):
        """FIELD: link a string variable to record buffer."""
        the_file = self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session), 'R')
        if util.skip_white_read_if(ins, (',',)):
            offset = 0
            while True:
                width = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
                util.range_check(0, 255, width)
                util.require_read(ins, ('AS',), err=error.IFC)
                name, index = self.parser.parse_variable(ins, self.session)
                the_file.field.attach_var(name, index, offset, width)
                offset += width
                if not util.skip_white_read_if(ins, (',',)):
                    break
        util.require(ins, tk.end_statement)

    def _parse_get_or_put_file(self, ins):
        """Helper function: PUT and GET syntax."""
        the_file = self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session), 'R')
        # for COM files
        num_bytes = the_file.reclen
        if util.skip_white_read_if(ins, (',',)):
            pos = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session))).round_to_int()
            # not 2^32-1 as the manual boasts!
            # pos-1 needs to fit in a single-precision mantissa
            util.range_check_err(1, 2**25, pos, err=error.BAD_RECORD_NUMBER)
            if not isinstance(the_file, ports.COMFile):
                the_file.set_pos(pos)
            else:
                num_bytes = pos
        return the_file, num_bytes

    def exec_put_file(self, ins):
        """PUT: write record to file."""
        thefile, num_bytes = self._parse_get_or_put_file(ins)
        thefile.put(num_bytes)
        util.require(ins, tk.end_statement)

    def exec_get_file(self, ins):
        """GET: read record from file."""
        thefile, num_bytes = self._parse_get_or_put_file(ins)
        thefile.get(num_bytes)
        util.require(ins, tk.end_statement)

    def exec_lock_or_unlock(self, ins, action):
        """LOCK or UNLOCK: set file or record locks."""
        thefile = self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session))
        lock_start_rec = 1
        if util.skip_white_read_if(ins, (',',)):
            lock_start_rec = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session))).round_to_int()
        lock_stop_rec = lock_start_rec
        if util.skip_white_read_if(ins, (tk.TO,)):
            lock_stop_rec = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session))).round_to_int()
        if lock_start_rec < 1 or lock_start_rec > 2**25-2 or lock_stop_rec < 1 or lock_stop_rec > 2**25-2:
            raise error.RunError(error.BAD_RECORD_NUMBER)
        try:
            getattr(thefile, action)(lock_start_rec, lock_stop_rec)
        except AttributeError:
            # not a disk file
            raise error.RunError(error.PERMISSION_DENIED)
        util.require(ins, tk.end_statement)

    exec_lock = partial(exec_lock_or_unlock, action = 'lock')
    exec_unlock = partial(exec_lock_or_unlock, action = 'unlock')

    def exec_ioctl(self, ins):
        """IOCTL: send control string to I/O device. Not implemented."""
        self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session))
        logging.warning("IOCTL statement not implemented.")
        raise error.RunError(error.IFC)

    ##########################################################
    # Graphics statements

    def _parse_coord_bare(self, ins):
        """Helper function: parse coordinate pair."""
        util.require_read(ins, ('(',))
        x = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        y = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (')',))
        return x, y

    def _parse_coord_step(self, ins):
        """Helper function: parse coordinate pair."""
        step = util.skip_white_read_if(ins, (tk.STEP,))
        x, y = self._parse_coord_bare(ins)
        return x, y, step

    def exec_pset(self, ins, c=-1):
        """PSET: set a pixel to a given attribute, or foreground."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        lcoord = self._parse_coord_step(ins)
        if util.skip_white_read_if(ins, (',',)):
            c = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(-1, 255, c)
        util.require(ins, tk.end_statement)
        self.session.screen.drawing.pset(lcoord, c)

    def exec_preset(self, ins):
        """PRESET: set a pixel to a given attribute, or background."""
        self.exec_pset(ins, 0)

    def exec_line_graph(self, ins):
        """LINE: draw a line or box between two points."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        if util.skip_white(ins) in ('(', tk.STEP):
            coord0 = self._parse_coord_step(ins)
        else:
            coord0 = None
        util.require_read(ins, (tk.O_MINUS,))
        coord1 = self._parse_coord_step(ins)
        c, mode, pattern = -1, '', 0xffff
        if util.skip_white_read_if(ins, (',',)):
            expr = self.parser.parse_expression(ins, self.session, allow_empty=True)
            if expr:
                c = vartypes.pass_int_unpack(expr)
            if util.skip_white_read_if(ins, (',',)):
                if util.skip_white_read_if(ins, ('B',)):
                    mode = 'BF' if util.skip_white_read_if(ins, ('F',)) else 'B'
                else:
                    util.require(ins, (',',))
                if util.skip_white_read_if(ins, (',',)):
                    pattern = vartypes.pass_int_unpack(
                                self.parser.parse_expression(ins, self.session), maxint=0x7fff)
            elif not expr:
                raise error.RunError(error.MISSING_OPERAND)
        util.require(ins, tk.end_statement)
        self.session.screen.drawing.line(coord0, coord1, c, pattern, mode)

    def exec_view_graph(self, ins):
        """VIEW: set graphics viewport and optionally draw a box."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        absolute = util.skip_white_read_if(ins, (tk.SCREEN,))
        if util.skip_white(ins) == '(':
            x0, y0 = self._parse_coord_bare(ins)
            x0, y0 = x0.round_to_int(), y0.round_to_int()
            util.require_read(ins, (tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare(ins)
            x1, y1 = x1.round_to_int(), y1.round_to_int()
            util.range_check(0, self.session.screen.mode.pixel_width-1, x0, x1)
            util.range_check(0, self.session.screen.mode.pixel_height-1, y0, y1)
            fill, border = None, None
            if util.skip_white_read_if(ins, (',',)):
                fill = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
                util.require_read(ins, (',',))
                border = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            self.session.screen.drawing.set_view(x0, y0, x1, y1, absolute, fill, border)
        else:
            self.session.screen.drawing.unset_view()
        util.require(ins, tk.end_statement)

    def exec_window(self, ins):
        """WINDOW: define logical coordinate system."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        cartesian = not util.skip_white_read_if(ins, (tk.SCREEN,))
        if util.skip_white(ins) == '(':
            x0, y0 = self._parse_coord_bare(ins)
            util.require_read(ins, (tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare(ins)
            if x0.equals(x1) or y0.equals(y1):
                raise error.RunError(error.IFC)
            self.session.screen.drawing.set_window(x0, y0, x1, y1, cartesian)
        else:
            self.session.screen.drawing.unset_window()
        util.require(ins, tk.end_statement)

    def exec_circle(self, ins):
        """CIRCLE: Draw a circle, ellipse, arc or sector."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        centre = self._parse_coord_step(ins)
        util.require_read(ins, (',',))
        r = fp.unpack(vartypes.pass_single(self.parser.parse_expression(ins, self.session)))
        start, stop, c, aspect = None, None, -1, None
        if util.skip_white_read_if(ins, (',',)):
            cval = self.parser.parse_expression(ins, self.session, allow_empty=True)
            if cval:
                c = vartypes.pass_int_unpack(cval)
            if util.skip_white_read_if(ins, (',',)):
                start = self.parser.parse_expression(ins, self.session, allow_empty=True)
                if util.skip_white_read_if(ins, (',',)):
                    stop = self.parser.parse_expression(ins, self.session, allow_empty=True)
                    if util.skip_white_read_if(ins, (',',)):
                        aspect = fp.unpack(vartypes.pass_single(
                                                self.parser.parse_expression(ins, self.session)))
                    elif stop is None:
                        # missing operand
                        raise error.RunError(error.MISSING_OPERAND)
                elif start is None:
                    raise error.RunError(error.MISSING_OPERAND)
            elif cval is None:
                raise error.RunError(error.MISSING_OPERAND)
        util.require(ins, tk.end_statement)
        self.session.screen.drawing.circle(centre, r, start, stop, c, aspect)

    def exec_paint(self, ins):
        """PAINT: flood fill from point."""
        # if paint *colour* specified, border default = paint colour
        # if paint *attribute* specified, border default = current foreground
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        coord = self._parse_coord_step(ins)
        pattern, c, border, background_pattern = None, -1, -1, None
        if util.skip_white_read_if(ins, (',',)):
            cval = self.parser.parse_expression(ins, self.session, allow_empty=True)
            if not cval:
                pass
            elif cval[0] == '$':
                # pattern given; copy
                with self.session.strings:
                    pattern = bytearray(self.session.strings.copy(vartypes.pass_string(cval)))
                if not pattern:
                    # empty pattern "" is illegal function call
                    raise error.RunError(error.IFC)
                # default for border, if pattern is specified as string: foreground attr
            else:
                c = vartypes.pass_int_unpack(cval)
            border = c
            if util.skip_white_read_if(ins, (',',)):
                bval = self.parser.parse_expression(ins, self.session, allow_empty=True)
                if bval:
                    border = vartypes.pass_int_unpack(bval)
                if util.skip_white_read_if(ins, (',',)):
                    with self.session.strings:
                        background_pattern = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session), err=error.IFC))
                    # only in screen 7,8,9 is this an error (use ega memory as a check)
                    if (pattern and background_pattern[:len(pattern)] == pattern and
                            self.session.screen.mode.mem_start == 0xa000):
                        raise error.RunError(error.IFC)
        util.require(ins, tk.end_statement)
        self.session.screen.drawing.paint(coord, pattern, c, border, background_pattern, self.session.events)

    def exec_get_graph(self, ins):
        """GET: read a sprite to memory."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP for first coord
        util.require(ins, ('('))
        coord0 = self._parse_coord_step(ins)
        util.require_read(ins, (tk.O_MINUS,))
        coord1 = self._parse_coord_step(ins)
        util.require_read(ins, (',',))
        array = self.parser.parse_scalar(ins)
        util.require(ins, tk.end_statement)
        if array not in self.session.arrays.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            raise error.RunError(error.TYPE_MISMATCH) # type mismatch
        self.session.screen.drawing.get(coord0, coord1, self.session.arrays.arrays, array)

    def exec_put_graph(self, ins):
        """PUT: draw sprite on screen."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP
        util.require(ins, ('('))
        coord = self._parse_coord_step(ins)
        util.require_read(ins, (',',))
        array = self.parser.parse_scalar(ins)
        action = tk.XOR
        if util.skip_white_read_if(ins, (',',)):
            util.require(ins, (tk.PSET, tk.PRESET,
                               tk.AND, tk.OR, tk.XOR))
            action = ins.read(1)
        util.require(ins, tk.end_statement)
        if array not in self.session.arrays.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        self.session.screen.drawing.put(coord, self.session.arrays.arrays, array, action)

    def exec_draw(self, ins):
        """DRAW: draw a figure defined by a Graphics Macro Language string."""
        if self.session.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        with self.session.strings:
            gml = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require(ins, tk.end_statement)
        self.session.screen.drawing.draw(gml, self.session.memory, self.session.events)

    ##########################################################
    # Flow-control statements

    def exec_end(self, ins):
        """END: end program execution and return to interpreter."""
        util.require(ins, tk.end_statement)
        self.parser.stop = self.parser.program_code.tell()
        # jump to end of direct line so execution stops
        self.parser.set_pointer(False)
        # avoid NO RESUME
        self.parser.error_handle_mode = False
        self.parser.error_resume = None
        self.session.files.close_all()

    def exec_stop(self, ins):
        """STOP: break program execution and return to interpreter."""
        util.require(ins, tk.end_statement)
        raise error.Break(stop=True)

    def exec_cont(self, ins):
        """CONT: continue STOPped or ENDed execution."""
        if self.parser.stop is None:
            raise error.RunError(error.CANT_CONTINUE)
        else:
            self.parser.set_pointer(True, self.parser.stop)
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
        varname = self.parser.parse_scalar(ins)
        vartype = varname[-1]
        if vartype in ('$', '#'):
            raise error.RunError(error.TYPE_MISMATCH)
        util.require_read(ins, (tk.O_EQ,))
        start = vartypes.pass_type(vartype, self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (tk.TO,))
        stop = vartypes.pass_type(vartype, self.parser.parse_expression(ins, self.session))
        if util.skip_white_read_if(ins, (tk.STEP,)):
            step = self.parser.parse_expression(ins, self.session)
        else:
            # convert 1 to vartype
            step = vartypes.int_to_integer_signed(1)
        step = vartypes.pass_type(vartype, step)
        util.require(ins, tk.end_statement)
        endforpos = ins.tell()
        # find NEXT
        nextpos = self._find_next(ins, varname)
        # apply initial condition and jump to nextpos
        self.parser.loop_init(ins, endforpos, nextpos, varname, start, stop, step)
        self.exec_next(ins)

    def _skip_to_next(self, ins, for_char, next_char, allow_comma=False):
        """Helper function for FOR: skip over bytecode until NEXT."""
        stack = 0
        while True:
            c = util.skip_to_read(ins, tk.end_statement+(tk.THEN, tk.ELSE))
            # skip line number, if there
            if c == '\0' and util.parse_line_number(ins) == -1:
                break
            # get first keyword in statement
            d = util.skip_white(ins)
            if d == '':
                break
            elif d == for_char:
                ins.read(1)
                stack += 1
            elif d == next_char:
                if stack <= 0:
                    break
                else:
                    ins.read(1)
                    stack -= 1
                    # NEXT I, J
                    if allow_comma:
                        while (util.skip_white(ins) not in tk.end_statement):
                            util.skip_to(ins, tk.end_statement + (',',))
                            if util.peek(ins) == ',':
                                if stack > 0:
                                    ins.read(1)
                                    stack -= 1
                                else:
                                    return

    def _find_next(self, ins, varname):
        """Helper function for FOR: find the right NEXT."""
        current = ins.tell()
        self._skip_to_next(ins, tk.FOR, tk.NEXT, allow_comma=True)
        if util.skip_white(ins) not in (tk.NEXT, ','):
            # FOR without NEXT marked with FOR line number
            ins.seek(current)
            raise error.RunError(error.FOR_WITHOUT_NEXT)
        comma = (ins.read(1) == ',')
        # get position and line number just after the NEXT
        nextpos = ins.tell()
        # check var name for NEXT
        varname2 = self.parser.parse_scalar(ins, allow_empty=True)
        # no-var only allowed in standalone NEXT
        if not varname2:
            util.require(ins, tk.end_statement)
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
            name = self.parser.parse_scalar(ins, allow_empty=True)
            # if we haven't read a variable, we shouldn't find something else here
            # but if we have and we iterate, the rest of the line is ignored
            if not name:
                util.require(ins, tk.end_statement + (',',))
            # increment counter, check condition
            if self.parser.loop_iterate(ins, pos):
                break
            # done if we're not jumping into a comma'ed NEXT
            if not util.skip_white_read_if(ins, (',')):
                break
        # if we're done iterating we no longer ignore the rest of the statement
        util.require(ins, tk.end_statement)

    def exec_goto(self, ins):
        """GOTO: jump to specified line number."""
        # parse line number, ignore rest of line and jump
        self.parser.jump(util.parse_jumpnum(ins))

    def exec_run(self, ins):
        """RUN: start program execution."""
        jumpnum, close_files = None, True
        c = util.skip_white(ins)
        if c == tk.T_UINT:
            # parse line number and ignore rest of line
            jumpnum = util.parse_jumpnum(ins)
        elif c not in tk.end_statement:
            with self.session.strings:
                name = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
            if util.skip_white_read_if(ins, (',',)):
                util.require_read(ins, 'R')
                close_files = False
            util.require(ins, tk.end_statement)
            with self.session.files.open(0, name, filetype='ABP', mode='I') as f:
                self.session.program.load(f)
        self.parser.clear_stacks_and_pointers()
        self.session.clear(close_files=close_files)
        self.parser.jump(jumpnum)
        self.parser.error_handle_mode = False

    def exec_if(self, ins):
        """IF: enter branching statement."""
        # avoid overflow: don't use bools.
        val = vartypes.pass_single(self.parser.parse_expression(ins, self.session))
        util.skip_white_read_if(ins, (',',)) # optional comma
        util.require_read(ins, (tk.THEN, tk.GOTO))
        if not fp.unpack(val).is_zero():
            # TRUE: continue after THEN. line number or statement is implied GOTO
            if util.skip_white(ins) in (tk.T_UINT,):
                self.parser.jump(util.parse_jumpnum(ins))
            # continue parsing as normal, :ELSE will be ignored anyway
        else:
            # FALSE: find ELSE block or end of line; ELSEs are nesting on the line
            nesting_level = 0
            while True:
                d = util.skip_to_read(ins, tk.end_statement + (tk.IF,))
                if d == tk.IF:
                    # nexting step on IF. (it's less convenient to count THENs because they could be THEN, GOTO or THEN GOTO.)
                    nesting_level += 1
                elif d == ':':
                    if util.skip_white_read_if(ins, tk.ELSE): # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                        if nesting_level > 0:
                            nesting_level -= 1
                        else:
                            # line number: jump
                            if util.skip_white(ins) in (tk.T_UINT,):
                                self.parser.jump(util.parse_jumpnum(ins))
                            # continue execution from here
                            break
                else:
                    ins.seek(-len(d), 1)
                    break

    def exec_else(self, ins):
        """ELSE: part of branch statement; ignore."""
        # any else statement by itself means the THEN has already been executed, so it's really like a REM.
        util.skip_to(ins, tk.end_line)

    def exec_while(self, ins):
        """WHILE: enter while-loop."""
        # just after WHILE opcode
        whilepos = ins.tell()
        # evaluate the 'boolean' expression
        # use double to avoid overflows
        # find matching WEND
        self._skip_to_next(ins, tk.WHILE, tk.WEND)
        if ins.read(1) == tk.WEND:
            util.skip_to(ins, tk.end_statement)
            wendpos = ins.tell()
            self.parser.while_stack.append((whilepos, wendpos))
        else:
            # WHILE without WEND
            ins.seek(whilepos)
            raise error.RunError(error.WHILE_WITHOUT_WEND)
        self._check_while_condition(ins, whilepos)
        util.require(ins, tk.end_statement)

    def _check_while_condition(self, ins, whilepos):
        """Check condition of while-loop."""
        ins.seek(whilepos)
        # WHILE condition is zero?
        if not fp.unpack(vartypes.pass_double(self.parser.parse_expression(ins, self.session))).is_zero():
            # statement start is before WHILE token
            self.parser.current_statement = whilepos-2
            util.require(ins, tk.end_statement)
        else:
            # ignore rest of line and jump to WEND
            _, wendpos = self.parser.while_stack.pop()
            ins.seek(wendpos)

    def exec_wend(self, ins):
        """WEND: iterate while-loop."""
        # while will actually syntax error on the first run if anything is in the way.
        util.require(ins, tk.end_statement)
        pos = ins.tell()
        while True:
            if not self.parser.while_stack:
                # WEND without WHILE
                raise error.RunError(error.WEND_WITHOUT_WHILE)
            whilepos, wendpos = self.parser.while_stack[-1]
            if pos == wendpos:
                break
            # not the expected WEND, we must have jumped out
            self.parser.while_stack.pop()
        self._check_while_condition(ins, whilepos)

    def exec_on_jump(self, ins):
        """ON: calculated jump."""
        onvar = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, 255, onvar)
        command = util.skip_white_read(ins)
        jumps = []
        while True:
            d = util.skip_white_read(ins)
            if d in tk.end_statement:
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
                self.parser.jump(util.parse_jumpnum(ins))
            elif command == tk.GOSUB:
                self.exec_gosub(ins)
        util.skip_to(ins, tk.end_statement)

    def exec_on_error(self, ins):
        """ON ERROR: define error trapping routine."""
        util.require_read(ins, (tk.GOTO,))  # GOTO
        linenum = util.parse_jumpnum(ins)
        if linenum != 0 and linenum not in self.session.program.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        self.parser.on_error = linenum
        # pause soft-handling math errors so that we can catch them
        self.parser.math_error_handler.pause_handling(linenum != 0)
        # ON ERROR GOTO 0 in error handler
        if self.parser.on_error == 0 and self.parser.error_handle_mode:
            # re-raise the error so that execution stops
            raise error.RunError(self.parser.error_num, self.parser.error_pos)
        # this will be caught by the trapping routine just set
        util.require(ins, tk.end_statement)

    def exec_resume(self, ins):
        """RESUME: resume program flow after error-trap."""
        if self.parser.error_resume is None:
            # unset error handler
            self.parser.on_error = 0
            raise error.RunError(error.RESUME_WITHOUT_ERROR)
        c = util.skip_white(ins)
        if c == tk.NEXT:
            ins.read(1)
            jumpnum = -1
        elif c not in tk.end_statement:
            jumpnum = util.parse_jumpnum(ins)
        else:
            jumpnum = 0
        util.require(ins, tk.end_statement)
        start_statement, runmode = self.parser.error_resume
        self.parser.error_num = 0
        self.parser.error_handle_mode = False
        self.parser.error_resume = None
        self.session.events.suspend_all = False
        if jumpnum == 0:
            # RESUME or RESUME 0
            self.parser.set_pointer(runmode, start_statement)
        elif jumpnum == -1:
            # RESUME NEXT
            self.parser.set_pointer(runmode, start_statement)
            util.skip_to(self.parser.get_codestream(), tk.end_statement, break_on_first_char=False)
        else:
            # RESUME n
            self.parser.jump(jumpnum)

    def exec_error(self, ins):
        """ERRROR: simulate an error condition."""
        errn = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(1, 255, errn)
        raise error.RunError(errn)

    def exec_gosub(self, ins):
        """GOSUB: jump into a subroutine."""
        jumpnum = util.parse_jumpnum(ins)
        # ignore rest of statement ('GOSUB 100 LAH' works just fine..); we need to be able to RETURN
        util.skip_to(ins, tk.end_statement)
        self.parser.jump_gosub(jumpnum)

    def exec_return(self, ins):
        """RETURN: return from a subroutine."""
        # return *can* have a line number
        if util.skip_white(ins) not in tk.end_statement:
            jumpnum = util.parse_jumpnum(ins)
            # rest of line is ignored
            util.skip_to(ins, tk.end_statement)
        else:
            jumpnum = None
        self.parser.jump_return(jumpnum)

    ################################################
    # Variable & array statements

    def _parse_var_list(self, ins):
        """Helper function: parse variable list.  """
        readvar = []
        while True:
            readvar.append(list(self.parser.parse_variable(ins, self.session)))
            if not util.skip_white_read_if(ins, (',',)):
                break
        return readvar

    def exec_clear(self, ins):
        """CLEAR: clear memory and redefine memory limits."""
        # integer expression allowed but ignored
        intexp = self.parser.parse_expression(ins, self.session, allow_empty=True)
        if intexp:
            expr = vartypes.pass_int_unpack(intexp)
            if expr < 0:
                raise error.RunError(error.IFC)
        if util.skip_white_read_if(ins, (',',)):
            exp1 = self.parser.parse_expression(ins, self.session, allow_empty=True)
            if exp1:
                # this produces a *signed* int
                mem_size = vartypes.pass_int_unpack(exp1, maxint=0xffff)
                if mem_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                else:
                    if not self.session.memory.set_basic_memory_size(mem_size):
                        raise error.RunError(error.OUT_OF_MEMORY)
            if util.skip_white_read_if(ins, (',',)):
                # set aside stack space for GW-BASIC. The default is the previous stack space size.
                exp2 = self.parser.parse_expression(ins, self.session, allow_empty=True)
                if exp2:
                    stack_size = vartypes.pass_int_unpack(exp2, maxint=0xffff)
                    # this should be an unsigned int
                    if stack_size < 0:
                        stack_size += 0x10000
                    if stack_size == 0:
                        #  0 leads to illegal fn call
                        raise error.RunError(error.IFC)
                    self.session.memory.set_stack_size(stack_size)
                if self.parser.syntax in ('pcjr', 'tandy') and util.skip_white_read_if(ins, (',',)):
                    # Tandy/PCjr: select video memory size
                    if not self.session.screen.set_video_memory_size(
                        fp.unpack(vartypes.pass_single(
                                     self.parser.parse_expression(ins, self.session)
                                 )).round_to_int()):
                        self.session.screen.screen(0, 0, 0, 0)
                        self.session.screen.init_mode()
                elif not exp2:
                    raise error.RunError(error.STX)
        util.require(ins, tk.end_statement)
        self.session.clear()

    def exec_common(self, ins):
        """COMMON: define variables to be preserved on CHAIN."""
        common_scalars, common_arrays = set(), set()
        while True:
            name = self.parser.parse_scalar(ins)
            # array?
            if util.skip_white_read_if(ins, ('[', '(')):
                util.require_read(ins, (']', ')'))
                common_arrays.add(name)
            else:
                common_scalars.add(name)
            if not util.skip_white_read_if(ins, (',',)):
                break
        self.session.common_scalars |= common_scalars
        self.session.common_arrays |= common_arrays

    def exec_data(self, ins):
        """DATA: data definition; ignore."""
        # ignore rest of statement after DATA
        util.skip_to(ins, tk.end_statement)

    def exec_dim(self, ins):
        """DIM: dimension arrays."""
        while True:
            name, dimensions = self.parser.parse_variable(ins, self.session)
            if not dimensions:
                dimensions = [10]
            self.session.arrays.dim(name, dimensions)
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require(ins, tk.end_statement)

    def exec_deftype(self, ins, typechar):
        """DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables."""
        while True:
            start = util.skip_white_read(ins)
            if start not in string.ascii_letters:
                raise error.RunError(error.STX)
            stop = start
            if util.skip_white_read_if(ins, (tk.O_MINUS,)):
                stop = util.skip_white_read(ins)
                if stop not in string.ascii_letters:
                    raise error.RunError(error.STX)
            self.session.memory.set_deftype(start, stop, typechar)
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require(ins, tk.end_statement)

    def exec_erase(self, ins):
        """ERASE: erase an array."""
        while True:
            self.session.arrays.erase(self.parser.parse_scalar(ins))
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require(ins, tk.end_statement)

    def exec_let(self, ins):
        """LET: assign value to variable or array."""
        name, indices = self.parser.parse_variable(ins, self.session)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
            self.session.arrays.check_dim(name, indices)
        util.require_read(ins, (tk.O_EQ,))
        self.session.memory.set_variable(name, indices, self.parser.parse_expression(ins, self.session))
        util.require(ins, tk.end_statement)

    def exec_mid(self, ins):
        """MID$: set part of a string."""
        # do not use require_read as we don't allow whitespace here
        if ins.read(1) != '(':
            raise error.RunError(error.STX)
        name, indices = self.parser.parse_variable(ins, self.session)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            self.session.arrays.check_dim(name, indices)
        util.require_read(ins, (',',))
        start = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        num = 255
        if util.skip_white_read_if(ins, (',',)):
            num = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        with self.session.strings:
            s = self.session.strings.copy(vartypes.pass_string(self.session.memory.get_variable(name, indices)))
        util.range_check(0, 255, num)
        if num > 0:
            util.range_check(1, len(s), start)
        util.require_read(ins, (tk.O_EQ,))
        with self.session.strings:
            val = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require(ins, tk.end_statement)
        # we need to decrement basic offset by 1 to get python offset
        offset = start-1
        # don't overwrite more of the old string than the length of the new string
        num = min(num, len(val))
        basic_str = self.session.memory.get_variable(name, indices)
        # ensure the length of source string matches target
        length = vartypes.string_length(basic_str)
        if offset + num > length:
            num = length - offset
        if num <= 0:
            return
        # cut new string to size if too long
        val = val[:num]
        # copy new value into existing buffer if possible
        self.session.memory.set_variable(name, indices,
                self.session.strings.modify(basic_str, val, offset, num))

    def exec_lset(self, ins, justify_right=False):
        """LSET: assign string value in-place; left justified."""
        name, index = self.parser.parse_variable(ins, self.session)
        v = vartypes.pass_string(self.session.memory.get_variable(name, index))
        util.require_read(ins, (tk.O_EQ,))
        with self.session.strings:
            s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        # v is empty string if variable does not exist
        # trim and pad to size of target buffer
        length = vartypes.string_length(v)
        s = s[:length]
        if justify_right:
            s = ' '*(length-len(s)) + s
        else:
            s += ' '*(length-len(s))
        # copy new value into existing buffer if possible
        self.session.memory.set_variable(name, index, self.session.strings.modify(v, s))

    def exec_rset(self, ins):
        """RSET: assign string value in-place; right justified."""
        self.exec_lset(ins, justify_right=True)

    def exec_option(self, ins):
        """OPTION BASE: set array indexing convention."""
        if util.skip_white_read_if(ins, ('BASE',)):
            # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
            d = util.skip_white_read(ins)
            if d == '0':
                self.session.arrays.base(0)
            elif d == '1':
                self.session.arrays.base(1)
            else:
                raise error.RunError(error.STX)
        else:
            raise error.RunError(error.STX)
        util.skip_to(ins, tk.end_statement)

    def exec_read(self, ins):
        """READ: read values from DATA statement."""
        # reading loop
        for name, indices in self._parse_var_list(ins):
            entry = self.parser.read_entry()
            if name[-1] == '$':
                if ins == self.parser.program_code:
                    address = self.parser.data_pos + self.session.memory.code_start
                else:
                    address = None
                value = self.session.strings.store(entry, address)
            else:
                value = values.str_to_number(entry, allow_nonnum=False)
                if value is None:
                    # set pointer for EDIT gadget to position in DATA statement
                    self.parser.program_code.seek(self.parser.data_pos)
                    # syntax error in DATA line (not type mismatch!) if can't convert to var type
                    raise error.RunError(error.STX, self.parser.data_pos-1)
            self.session.memory.set_variable(name, indices, value=value)
        util.require(ins, tk.end_statement)

    def _parse_prompt(self, ins, question_mark):
        """Helper function for INPUT: parse prompt definition."""
        # parse prompt
        if util.skip_white_read_if(ins, ('"',)):
            prompt = ''
            # only literal allowed, not a string expression
            d = ins.read(1)
            while d not in tk.end_line + ('"',)  :
                prompt += d
                d = ins.read(1)
            if d == '\0':
                ins.seek(-1, 1)
            following = util.skip_white_read(ins)
            if following == ';':
                prompt += question_mark
            elif following != ',':
                raise error.RunError(error.STX)
        else:
            prompt = question_mark
        return prompt

    def exec_input(self, ins):
        """INPUT: request input from user."""
        finp = self.parser.parse_file_number(ins, self.session, 'IR')
        if finp is not None:
            for v in self._parse_var_list(ins):
                name, indices = v
                word, _ = finp.input_entry(name[-1], allow_past_end=False)
                value = self.session.strings.str_to_type(name[-1], word)
                if value is None:
                    value = vartypes.null(name[-1])
                self.session.memory.set_variable(name, indices, value)
        else:
            # ; to avoid echoing newline
            newline = not util.skip_white_read_if(ins, (';',))
            prompt = self._parse_prompt(ins, '? ')
            readvar = self._parse_var_list(ins)
            # move the program pointer to the start of the statement to ensure correct behaviour for CONT
            pos = ins.tell()
            ins.seek(self.parser.current_statement)
            # read the input
            self.session.input_mode = True
            varlist = print_and_input.input_console(
                    self.session.editor, self.session.strings,
                    prompt, readvar, newline)
            self.session.input_mode = False
            for v in varlist:
                self.session.memory.set_variable(*v)
            ins.seek(pos)
        util.require(ins, tk.end_statement)

    def exec_line_input(self, ins):
        """LINE INPUT: request input from user."""
        finp = self.parser.parse_file_number(ins, self.session, 'IR')
        if not finp:
            # ; to avoid echoing newline
            newline = not util.skip_white_read_if(ins, (';',))
            # get prompt
            prompt = self._parse_prompt(ins, '')
        # get string variable
        readvar, indices = self.parser.parse_variable(ins, self.session)
        if not readvar or readvar[0] == '':
            raise error.RunError(error.STX)
        elif readvar[-1] != '$':
            raise error.RunError(error.TYPE_MISMATCH)
        # read the input
        if finp:
            line = finp.read_line()
            if line is None:
                raise error.RunError(error.INPUT_PAST_END)
        else:
            self.session.input_mode = True
            self.session.screen.write(prompt)
            line = self.session.editor.wait_screenline(write_endl=newline)
            self.session.input_mode = False
        self.session.memory.set_variable(readvar, indices, self.session.strings.store(line))

    def exec_restore(self, ins):
        """RESTORE: reset DATA pointer."""
        if not util.skip_white(ins) in tk.end_statement:
            datanum = util.parse_jumpnum(ins, err=error.UNDEFINED_LINE_NUMBER)
        else:
            datanum = -1
        # undefined line number for all syntax errors
        util.require(ins, tk.end_statement, err=error.UNDEFINED_LINE_NUMBER)
        self.parser.restore(datanum)

    def exec_swap(self, ins):
        """SWAP: swap values of two variables."""
        name1, index1 = self.parser.parse_variable(ins, self.session)
        util.require_read(ins, (',',))
        name2, index2 = self.parser.parse_variable(ins, self.session)
        self.session.memory.swap(name1, index1, name2, index2)
        # if syntax error. the swap has happened
        util.require(ins, tk.end_statement)

    def exec_def_fn(self, ins):
        """DEF FN: define a function."""
        fnname = self.parser.parse_scalar(ins)
        fntype = fnname[-1]
        # read parameters
        fnvars = []
        util.skip_white(ins)
        pointer_loc = self.session.memory.code_start + ins.tell()
        if util.skip_white_read_if(ins, ('(',)):
            while True:
                fnvars.append(self.parser.parse_scalar(ins))
                if util.skip_white(ins) in tk.end_statement + (')',):
                    break
                util.require_read(ins, (',',))
            util.require_read(ins, (')',))
        # read code
        fncode = ''
        util.require_read(ins, (tk.O_EQ,)) #=
        startloc = ins.tell()
        util.skip_to(ins, tk.end_statement)
        endloc = ins.tell()
        ins.seek(startloc)
        fncode = ins.read(endloc - startloc)
        if not self.parser.run_mode:
            # GW doesn't allow DEF FN in direct mode, neither do we
            # (for no good reason, works fine)
            raise error.RunError(error.ILLEGAL_DIRECT)
        self.session.user_functions[fnname] = fnvars, fncode
        # update memory model
        # allocate function pointer
        pointer = vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(pointer_loc))
        pointer += '\0'*(vartypes.byte_size[fntype]-2)
        # function name is represented with first char shifted by 128
        self.session.scalars.set(chr(128+ord(fnname[0]))+fnname[1:], (fntype, bytearray(pointer)))
        for name in fnvars:
            # allocate but don't set variables
            self.session.scalars.set(name)


    def exec_randomize(self, ins):
        """RANDOMIZE: set random number generator seed."""
        val = self.parser.parse_expression(ins, self.session, allow_empty=True)
        if val:
            # don't convert to int if provided in the code
            val = vartypes.pass_number(val)
        else:
            # prompt for random seed if not specified
            while not val:
                self.session.screen.write("Random number seed (-32768 to 32767)? ")
                seed = self.session.editor.wait_screenline()
                # seed entered on prompt is rounded to int
                val = values.str_to_number(seed)
            val = vartypes.pass_integer(val)
        self.session.randomiser.reseed(val)
        util.require(ins, tk.end_statement)

    ################################################
    # Console statements

    def exec_cls(self, ins):
        """CLS: clear the screen."""
        if (self.parser.syntax == 'pcjr' or
                        util.skip_white(ins) in (',',) + tk.end_statement):
            if self.session.screen.drawing.view_is_set():
                val = 1
            elif self.session.screen.view_set:
                val = 2
            else:
                val = 0
        else:
            val = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            if self.parser.syntax == 'tandy':
                # tandy gives illegal function call on CLS number
                raise error.RunError(error.IFC)
        util.range_check(0, 2, val)
        if self.parser.syntax != 'pcjr':
            if util.skip_white_read_if(ins, (',',)):
                # comma is ignored, but a number after means syntax error
                util.require(ins, tk.end_statement)
            else:
                util.require(ins, tk.end_statement, err=error.IFC)
        # cls is only executed if no errors have occurred
        if val == 0:
            self.session.screen.clear()
            self.session.fkey_macros.redraw_keys(self.session.screen)
            self.session.screen.drawing.reset()
        elif val == 1:
            self.session.screen.drawing.clear_view()
            self.session.screen.drawing.reset()
        elif val == 2:
            self.session.screen.clear_view()
        if self.parser.syntax == 'pcjr':
            util.require(ins, tk.end_statement)

    def exec_color(self, ins):
        """COLOR: set colour attributes."""
        screen = self.session.screen
        mode = screen.mode
        fore = self.parser.parse_expression(ins, self.session, allow_empty=True)
        if fore is None:
            fore = (screen.attr>>7)*0x10 + (screen.attr&0xf)
        else:
            fore = vartypes.pass_int_unpack(fore)
        back, bord = None, None
        if util.skip_white_read_if(ins, (',')):
            back = self.parser.parse_expression(ins, self.session, allow_empty=True)
            back = None if back is None else vartypes.pass_int_unpack(back)
            if util.skip_white_read_if(ins, (',')):
                bord = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        if back is None:
            # graphics mode bg is always 0; sets palette instead
            if mode.is_text_mode:
                back = (screen.attr>>4) & 0x7
            else:
                back = screen.palette.get_entry(0)
        if mode.name == '320x200x4':
            self.exec_color_mode_1(ins, fore, back, bord)
            util.require(ins, tk.end_statement)
            return
        elif mode.name in ('640x200x2', '720x348x2'):
            # screen 2; hercules: illegal fn call
            raise error.RunError(error.IFC)
        # for screens other than 1, no distinction between 3rd parm zero and not supplied
        bord = bord or 0
        util.range_check(0, 255, bord)
        if mode.is_text_mode:
            util.range_check(0, mode.num_attr-1, fore)
            util.range_check(0, 15, back, bord)
            screen.set_attr(((0x8 if (fore > 0xf) else 0x0) + (back & 0x7))*0x10
                            + (fore & 0xf))
            screen.set_border(bord)
        elif mode.name in ('160x200x16', '320x200x4pcjr', '320x200x16pcjr'
                            '640x200x4', '320x200x16', '640x200x16'):
            util.range_check(1, mode.num_attr-1, fore)
            util.range_check(0, mode.num_attr-1, back)
            screen.set_attr(fore)
            # in screen 7 and 8, only low intensity palette is used.
            screen.palette.set_entry(0, back % 8, check_mode=False)
        elif mode.name in ('640x350x16', '640x350x4'):
            util.range_check(0, mode.num_attr-1, fore)
            util.range_check(0, len(mode.colours)-1, back)
            screen.set_attr(fore)
            screen.palette.set_entry(0, back, check_mode=False)
        elif mode.name == '640x400x2':
            util.range_check(0, len(mode.colours)-1, fore)
            if back != 0:
                raise error.RunError(error.IFC)
            screen.palette.set_entry(1, fore, check_mode=False)
        util.require(ins, tk.end_statement)

    def exec_color_mode_1(self, ins, back, pal, override):
        """Helper function for COLOR in SCREEN 1."""
        screen = self.session.screen
        back = screen.palette.get_entry(0) if back is None else back
        if override is not None:
            # uses last entry as palette if given
            pal = override
        util.range_check(0, 255, back)
        if pal is not None:
            util.range_check(0, 255, pal)
            screen.set_cga4_palette(pal%2)
            palette = list(screen.mode.palette)
            palette[0] = back&0xf
            # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
            # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15
            screen.palette.set_all(palette, check_mode=False)
        else:
            screen.palette.set_entry(0, back & 0xf, check_mode=False)

    def exec_palette(self, ins):
        """PALETTE: set colour palette entry."""
        d = util.skip_white(ins)
        if d in tk.end_statement:
            # reset palette
            self.session.screen.palette.set_all(self.session.screen.mode.palette)
        elif d == tk.USING:
            ins.read(1)
            self.exec_palette_using(ins)
        else:
            # can't set blinking colours separately
            mode = self.session.screen.mode
            num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
            attrib = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            util.require_read(ins, (',',))
            colour = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            if attrib is None or colour is None:
                raise error.RunError(error.STX)
            util.range_check(0, num_palette_entries-1, attrib)
            util.range_check(-1, len(mode.colours)-1, colour)
            if colour != -1:
                self.session.screen.palette.set_entry(attrib, colour)
            util.require(ins, tk.end_statement)

    def exec_palette_using(self, ins):
        """PALETTE USING: set full colour palette."""
        screen = self.session.screen
        mode = screen.mode
        num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
        array_name, start_indices = self.parser.parse_variable(ins, self.session)
        try:
            dimensions, lst, _ = self.session.arrays.arrays[array_name]
        except KeyError:
            raise error.RunError(error.IFC)
        if array_name[-1] != '%':
            raise error.RunError(error.TYPE_MISMATCH)
        start = self.session.arrays.index(start_indices, dimensions)
        if self.session.arrays.array_len(dimensions) - start < num_palette_entries:
            raise error.RunError(error.IFC)
        new_palette = []
        for i in range(num_palette_entries):
            val = vartypes.pass_int_unpack(('%', lst[(start+i)*2:(start+i+1)*2]))
            util.range_check(-1, len(mode.colours)-1, val)
            new_palette.append(val if val > -1 else screen.palette.get_entry(i))
        screen.palette.set_all(new_palette)
        util.require(ins, tk.end_statement)

    def exec_key(self, ins):
        """KEY: switch on/off or list function-key row on screen."""
        d = util.skip_white_read(ins)
        if d == tk.ON:
            # tandy can have VIEW PRINT 1 to 25, should raise IFC in that case
            if self.session.screen.scroll_height == 25:
                raise error.RunError(error.IFC)
            if not self.session.fkey_macros.keys_visible:
                self.session.fkey_macros.show_keys(self.session.screen, True)
        elif d == tk.OFF:
            if self.session.fkey_macros.keys_visible:
                self.session.fkey_macros.show_keys(self.session.screen, False)
        elif d == tk.LIST:
            self.session.fkey_macros.list_keys(self.session.screen)
        elif d == '(':
            # key (n)
            ins.seek(-1, 1)
            self.exec_key_events(ins)
        else:
            # key n, "TEXT"
            ins.seek(-len(d), 1)
            self.exec_key_define(ins)
        util.require(ins, tk.end_statement)

    def exec_key_define(self, ins):
        """KEY: define function-key shortcut or scancode for event trapping."""
        keynum = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(1, 255, keynum)
        util.require_read(ins, (',',), err=error.IFC)
        with self.session.strings:
            text = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        if keynum <= self.session.events.num_fn_keys:
            self.session.fkey_macros.set(keynum, text)
            self.session.fkey_macros.redraw_keys(self.session.screen)
        else:
            # only length-2 expressions can be assigned to KEYs over 10
            # in which case it's a key scancode definition
            if len(text) != 2:
                raise error.RunError(error.IFC)
            self.session.events.key[keynum-1].set_trigger(str(text))

    def exec_locate(self, ins):
        """LOCATE: Set cursor position, shape and visibility."""
        cmode = self.session.screen.mode
        row = self.parser.parse_expression(ins, self.session, allow_empty=True)
        row = None if row is None else vartypes.pass_int_unpack(row)
        col, cursor, start, stop = None, None, None, None
        if util.skip_white_read_if(ins, (',',)):
            col = self.parser.parse_expression(ins, self.session, allow_empty=True)
            col = None if col is None else vartypes.pass_int_unpack(col)
            if util.skip_white_read_if(ins, (',',)):
                cursor = self.parser.parse_expression(ins, self.session, allow_empty=True)
                cursor = None if cursor is None else vartypes.pass_int_unpack(cursor)
                if util.skip_white_read_if(ins, (',',)):
                    start = self.parser.parse_expression(ins, self.session, allow_empty=True)
                    start = None if start is None else vartypes.pass_int_unpack(start)
                    if util.skip_white_read_if(ins, (',',)):
                        stop = self.parser.parse_expression(ins, self.session, allow_empty=True)
                        stop = None if stop is None else vartypes.pass_int_unpack(stop)
                        if util.skip_white_read_if(ins, (',',)):
                            # can end on a 5th comma but no stuff allowed after it
                            pass
        row = self.session.screen.current_row if row is None else row
        col = self.session.screen.current_col if col is None else col
        if row == cmode.height and self.session.fkey_macros.keys_visible:
            raise error.RunError(error.IFC)
        elif self.session.screen.view_set:
            util.range_check(self.session.screen.view_start, self.session.screen.scroll_height, row)
        else:
            util.range_check(1, cmode.height, row)
        util.range_check(1, cmode.width, col)
        if row == cmode.height:
            # temporarily allow writing on last row
            self.session.screen.bottom_row_allowed = True
        self.session.screen.set_pos(row, col, scroll_ok=False)
        if cursor is not None:
            util.range_check(0, (255 if self.parser.syntax in ('pcjr', 'tandy') else 1), cursor)
            # set cursor visibility - this should set the flag but have no effect in graphics modes
            self.session.screen.cursor.set_visibility(cursor != 0)
        if stop is None:
            stop = start
        if start is not None:
            util.range_check(0, 31, start, stop)
            # cursor shape only has an effect in text mode
            if cmode.is_text_mode:
                self.session.screen.cursor.set_shape(start, stop)
        util.require(ins, tk.end_statement)

    def exec_write(self, ins, output=None):
        """WRITE: Output machine-readable expressions to the screen or a file."""
        output = self.parser.parse_file_number(ins, self.session, 'OAR')
        output = self.session.devices.scrn_file if output is None else output
        expr = self.parser.parse_expression(ins, self.session, allow_empty=True)
        outstr = ''
        if expr:
            while True:
                if expr[0] == '$':
                    with self.session.strings:
                        outstr += '"' + self.session.strings.copy(expr) + '"'
                else:
                    outstr += values.number_to_str(expr, screen=True, write=True)
                if util.skip_white_read_if(ins, (',', ';')):
                    outstr += ','
                else:
                    break
                expr = self.parser.parse_expression(ins, self.session)
        util.require(ins, tk.end_statement)
        # write the whole thing as one thing (this affects line breaks)
        output.write_line(outstr)

    def exec_print(self, ins, output=None):
        """PRINT: Write expressions to the screen or a file."""
        if output is None:
            output = self.parser.parse_file_number(ins, self.session, 'OAR')
            output = self.session.devices.scrn_file if output is None else output
        number_zones = max(1, int(output.width/14))
        newline = True
        while True:
            d = util.skip_white(ins)
            if d in tk.end_statement + (tk.USING,):
                break
            elif d in (',', ';', tk.SPC, tk.TAB):
                ins.read(1)
                newline = False
                if d == ',':
                    next_zone = int((output.col-1)/14)+1
                    if next_zone >= number_zones and output.width >= 14 and output.width != 255:
                        output.write_line()
                    else:
                        output.write(' '*(1+14*next_zone-output.col))
                elif d == tk.SPC:
                    numspaces = max(0, vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), 0xffff)) % output.width
                    util.require_read(ins, (')',))
                    output.write(' ' * numspaces)
                elif d == tk.TAB:
                    pos = max(0, vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session), 0xffff) - 1) % output.width + 1
                    util.require_read(ins, (')',))
                    if pos < output.col:
                        output.write_line()
                        output.write(' '*(pos-1))
                    else:
                        output.write(' '*(pos-output.col))
            else:
                newline = True
                with self.session.strings:
                    expr = self.parser.parse_expression(ins, self.session)
                    # numbers always followed by a space
                    if expr[0] in ('%', '!', '#'):
                        word = values.number_to_str(expr, screen=True) + ' '
                    else:
                        word = self.session.strings.copy(expr)
                # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
                output.write(word)
        if util.skip_white_read_if(ins, (tk.USING,)):
            return self.exec_print_using(ins, output)
        if newline:
            if output == self.session.devices.scrn_file and self.session.screen.overflow:
                output.write_line()
            output.write_line()
        util.require(ins, tk.end_statement)

    def exec_print_using(self, ins, output):
        """PRINT USING: Write expressions to screen or file using a formatting string."""
        with self.session.strings:
            format_expr = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
        if format_expr == '':
            raise error.RunError(error.IFC)
        util.require_read(ins, (';',))
        fors = StringIO(format_expr)
        semicolon, format_chars = False, False
        while True:
            data_ends = util.skip_white(ins) in tk.end_statement
            c = util.peek(fors)
            if c == '':
                if not format_chars:
                    # there were no format chars in the string, illegal fn call (avoids infinite loop)
                    raise error.RunError(error.IFC)
                if data_ends:
                    break
                # loop the format string if more variables to come
                fors.seek(0)
            elif c == '_':
                # escape char; write next char in fors or _ if this is the last char
                output.write(fors.read(2)[-1])
            else:
                string_field = print_and_input.get_string_tokens(fors)
                if string_field:
                    if not data_ends:
                        with self.session.strings:
                            s = self.session.strings.copy(vartypes.pass_string(self.parser.parse_expression(ins, self.session)))
                        if string_field == '&':
                            output.write(s)
                        else:
                            output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
                else:
                    number_field, digits_before, decimals = print_and_input.get_number_tokens(fors)
                    if number_field:
                        if not data_ends:
                            num = vartypes.pass_float(self.parser.parse_expression(ins, self.session))
                            output.write(values.format_number(num, number_field, digits_before, decimals))
                    else:
                        output.write(fors.read(1))
                if string_field or number_field:
                    format_chars = True
                    semicolon = util.skip_white_read_if(ins, (';', ','))
        if not semicolon:
            output.write_line()
        util.require(ins, tk.end_statement)

    def exec_lprint(self, ins):
        """LPRINT: Write expressions to printer LPT1."""
        self.exec_print(ins, self.session.devices.lpt1_file)

    def exec_view_print(self, ins):
        """VIEW PRINT: set scroll region."""
        if util.skip_white(ins) in tk.end_statement:
            self.session.screen.unset_view()
        else:
            start = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            util.require_read(ins, (tk.TO,))
            stop = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            util.require(ins, tk.end_statement)
            max_line = 25 if (self.parser.syntax in ('pcjr', 'tandy') and not self.session.fkey_macros.keys_visible) else 24
            util.range_check(1, max_line, start, stop)
            self.session.screen.set_view(start, stop)

    def exec_width(self, ins):
        """WIDTH: set width of screen or device."""
        d = util.skip_white(ins)
        if d == '#':
            dev = self.parser.parse_file_number(ins, self.session)
            w = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        elif d == tk.LPRINT:
            ins.read(1)
            dev = self.session.devices.lpt1_file
            w = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        else:
            # we can do calculations, but they must be bracketed...
            if d in tk.number:
                expr = self.parser.parse_literal(ins, self.session)
            else:
                expr = self.parser.parse_expression(ins, self.session)
            if expr[0] == '$':
                with self.session.strings:
                    devname = self.session.strings.copy(vartypes.pass_string(expr)).upper()
                try:
                    dev = self.session.devices.devices[devname].device_file
                except (KeyError, AttributeError):
                    # bad file name
                    raise error.RunError(error.BAD_FILE_NAME)
                util.require_read(ins, (',',))
                w = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
            else:
                dev = self.session.devices.scrn_file
                w = vartypes.pass_int_unpack(expr)
                if util.skip_white_read_if(ins, (',',)):
                    # pare dummy number rows setting
                    num_rows_dummy = self.parser.parse_expression(ins, self.session, allow_empty=True)
                    if num_rows_dummy is not None:
                        min_num_rows = 0 if self.parser.syntax in ('pcjr', 'tandy') else 25
                        util.range_check(min_num_rows, 25, vartypes.pass_int_unpack(num_rows_dummy))
                    # trailing comma is accepted
                    util.skip_white_read_if(ins, (',',))
                # gives illegal function call, not syntax error
            util.require(ins, tk.end_statement, err=error.IFC)
        util.require(ins, tk.end_statement)
        dev.set_width(w)

    def exec_screen(self, ins):
        """SCREEN: change video mode or page."""
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        mode = self.parser.parse_expression(ins, self.session, allow_empty=True)
        mode = None if mode is None else vartypes.pass_int_unpack(mode)
        color, apagenum, vpagenum, erase = None, None, None, 1
        if util.skip_white_read_if(ins, (',',)):
            color = self.parser.parse_expression(ins, self.session, allow_empty=True)
            color = None if color is None else vartypes.pass_int_unpack(color)
            if util.skip_white_read_if(ins, (',',)):
                apagenum = self.parser.parse_expression(ins, self.session, allow_empty=True)
                apagenum = None if apagenum is None else vartypes.pass_int_unpack(apagenum)
                if util.skip_white_read_if(ins, (',',)):
                    vpagenum = self.parser.parse_expression(ins, self.session,
                                allow_empty=self.parser.syntax in ('pcjr', 'tandy'))
                    vpagenum = None if vpagenum is None else vartypes.pass_int_unpack(vpagenum)
                    if self.parser.syntax in ('pcjr', 'tandy') and util.skip_white_read_if(ins, (',',)):
                        erase = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        # if any parameter not in [0,255], error 5 without doing anything
        # if the parameters are outside narrow ranges
        # (e.g. not implemented screen mode, pagenum beyond max)
        # then the error is only raised after changing the palette.
        util.range_check(0, 255, mode, color, apagenum, vpagenum)
        util.range_check(0, 2, erase)
        util.require(ins, tk.end_statement)
        # decide whether to redraw the screen
        screen = self.session.screen
        oldmode, oldcolor = screen.mode, screen.colorswitch
        screen.screen(mode, color, apagenum, vpagenum, erase)
        if ((not screen.mode.is_text_mode and screen.mode.name != oldmode.name) or
                (screen.mode.is_text_mode and not oldmode.is_text_mode) or
                (screen.mode.width != oldmode.width) or
                (screen.colorswitch != oldcolor)):
            # rebuild the console if we've switched modes or colorswitch
            self.session.screen.init_mode()

    def exec_pcopy(self, ins):
        """PCOPY: copy video pages."""
        src = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.range_check(0, self.session.screen.mode.num_pages-1, src)
        util.require_read(ins, (',',))
        dst = vartypes.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require(ins, tk.end_statement)
        util.range_check(0, self.session.screen.mode.num_pages-1, dst)
        self.session.screen.copy_page(src, dst)
