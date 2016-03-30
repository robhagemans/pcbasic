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

import console
import debug
import disk
import error
import events
import expressions
import flow
import fp
import devices
import machine
import memory
import ports
import print_and_input
import program
import representation
import reset
import rnd
import shell
import sound
import state
import timedate
import basictoken as tk
import util
import var
import vartypes


class Parser(object):
    """ Statement parser. """

    def __init__(self, session, syntax, term):
        """ Initialise parser. """
        self.session = session
        # syntax: advanced, pcjr, tandy
        self.syntax = syntax
        # program for TERM command
        self.term = term

    def parse_statement(self):
        """ Parse one statement at the current pointer in current codestream.
            Return False if stream has ended, True otherwise.
            """
        self.ins = flow.get_codestream()
        state.basic_state.current_statement = self.ins.tell()
        c = util.skip_white(self.ins)
        if c == '':
            # stream has ended.
            return False
        # parse line number or : at start of statement
        elif c == '\0':
            # save position for error message
            prepos = self.ins.tell()
            self.ins.read(1)
            # line number marker, new statement
            linenum = util.parse_line_number(self.ins)
            if linenum == -1:
                if state.basic_state.error_resume:
                    # unfinished error handler: no RESUME (don't trap this)
                    state.basic_state.error_handle_mode = True
                    # get line number right
                    raise error.RunError(error.NO_RESUME, prepos-1)
                # stream has ended
                return False
            if state.basic_state.tron:
                console.write('[' + ('%i' % linenum) + ']')
            debug.debug_step(linenum)
        elif c == ':':
            self.ins.read(1)
        c = util.skip_white(self.ins)
        # empty statement, return to parse next
        if c in tk.end_statement:
            return True
        # implicit LET
        elif c in string.ascii_letters:
            self.exec_let()
        # token
        else:
            self.ins.read(1)
            if c in tk.twobyte:
                c += self.ins.read(1)
            # don't use try-block to avoid catching other KeyErrors in statement
            if c not in self.statements:
                raise error.RunError(error.STX)
            self.statements[c](self)
        return True


    #################################################################
    #################################################################

    def exec_system(self):
        """ SYSTEM: exit interpreter. """
        # SYSTEM LAH does not execute
        util.require(self.ins, tk.end_statement)
        raise error.Exit()

    def exec_tron(self):
        """ TRON: turn on line number tracing. """
        state.basic_state.tron = True
        # TRON LAH gives error, but TRON has been executed
        util.require(self.ins, tk.end_statement)

    def exec_troff(self):
        """ TROFF: turn off line number tracing. """
        state.basic_state.tron = False
        util.require(self.ins, tk.end_statement)

    def exec_rem(self):
        """ REM: comment. """
        # skip the rest of the line, but parse numbers to avoid triggering EOL
        util.skip_to(self.ins, tk.end_line)

    def exec_lcopy(self):
        """ LCOPY: do nothing but check for syntax errors. """
        # See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY
        if util.skip_white(self.ins) not in tk.end_statement:
            util.range_check(0, 255, vartypes.pass_int_unpack(expressions.parse_expression(self.ins)))
            util.require(self.ins, tk.end_statement)

    def exec_motor(self):
        """ MOTOR: do nothing but check for syntax errors. """
        self.exec_lcopy(self.ins)

    def exec_debug(self):
        """ DEBUG: execute Python command. """
        # this is not a GW-BASIC behaviour, but helps debugging.
        # this is parsed like a REM by the tokeniser.
        # rest of the line is considered to be a python statement
        util.skip_white(self.ins)
        debug_cmd = ''
        while util.peek(self.ins) not in tk.end_line:
            debug_cmd += self.ins.read(1)
        debug.debug_exec(debug_cmd)

    def exec_term(self):
        """ TERM: load and run PCjr buitin terminal emulator program. """
        try:
            util.require(self.ins, tk.end_statement)
            with disk.create_file_object(open(self.term, 'rb'), 'A', 'I', 'TERM') as f:
                program.load(f)
        except EnvironmentError:
            # on Tandy, raises Internal Error
            raise error.RunError(error.INTERNAL_ERROR)
        flow.init_program()
        reset.clear()
        flow.jump(None)
        state.basic_state.error_handle_mode = False
        state.basic_state.tron = False


    ##########################################################
    # statements that require further qualification

    def exec_def(self):
        """ DEF: select DEF FN, DEF USR, DEF SEG. """
        c = util.skip_white(self.ins)
        if util.read_if(self.ins, c, (tk.FN,)):
            self.exec_def_fn()
        elif util.read_if(self.ins, c, (tk.USR,)):
            self.exec_def_usr()
        # must be uppercase in tokenised form, otherwise syntax error
        elif util.skip_white_read_if(self.ins, ('SEG',)):
            self.exec_def_seg()
        else:
            raise error.RunError(error.STX)

    def exec_view(self):
        """ VIEW: select VIEW PRINT, VIEW (graphics). """
        if util.skip_white_read_if(self.ins, (tk.PRINT,)):
            self.exec_view_print()
        else:
            self.exec_view_graph()

    def exec_line(self):
        """ LINE: select LINE INPUT, LINE (graphics). """
        if util.skip_white_read_if(self.ins, (tk.INPUT,)):
            self.exec_line_input()
        else:
            self.exec_line_graph()

    def exec_get(self):
        """ GET: select GET (graphics), GET (files). """
        if util.skip_white(self.ins) == '(':
            self.exec_get_graph()
        else:
            self.exec_get_file()

    def exec_put(self):
        """ PUT: select PUT (graphics), PUT (files). """
        if util.skip_white(self.ins) == '(':
            self.exec_put_graph()
        else:
            self.exec_put_file()

    def exec_on(self):
        """ ON: select ON ERROR, ON KEY, ON TIMER, ON PLAY, ON COM, ON PEN, ON STRIG
            or ON (jump statement). """
        c = util.skip_white(self.ins)
        if util.read_if(self.ins, c, (tk.ERROR,)):
            self.exec_on_error()
        elif util.read_if(self.ins, c, (tk.KEY,)):
            self.exec_on_key()
        elif c in ('\xFE', '\xFF'):
            c = util.peek(self.ins, 2)
            if util.read_if(self.ins, c, (tk.TIMER,)):
                self.exec_on_timer()
            elif util.read_if(self.ins, c, (tk.PLAY,)):
                self.exec_on_play()
            elif util.read_if(self.ins, c, (tk.COM,)):
                self.exec_on_com()
            elif util.read_if(self.ins, c, (tk.PEN,)):
                self.exec_on_pen()
            elif util.read_if(self.ins, c, (tk.STRIG,)):
                self.exec_on_strig()
            else:
                self.exec_on_jump()
        else:
            self.exec_on_jump()

    ##########################################################
    # event switches (except PLAY) and event definitions

    def exec_pen(self):
        """ PEN: switch on/off light pen event handling. """
        if state.basic_state.events.pen.command(util.skip_white(self.ins)):
            self.ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(self.ins, tk.end_statement)

    def exec_strig(self):
        """ STRIG: switch on/off fire button event handling. """
        d = util.skip_white(self.ins)
        if d == '(':
            # strig (n)
            num = vartypes.pass_int_unpack(expressions.parse_bracket(self.ins))
            if num not in (0,2,4,6):
                raise error.RunError(error.IFC)
            if state.basic_state.events.strig[num//2].command(util.skip_white(self.ins)):
                self.ins.read(1)
            else:
                raise error.RunError(error.STX)
        elif d == tk.ON:
            self.ins.read(1)
            state.console_state.stick.switch(True)
        elif d == tk.OFF:
            self.ins.read(1)
            state.console_state.stick.switch(False)
        else:
            raise error.RunError(error.STX)
        util.require(self.ins, tk.end_statement)

    def exec_com(self):
        """ COM: switch on/off serial port event handling. """
        util.require(self.ins, ('(',))
        num = vartypes.pass_int_unpack(expressions.parse_bracket(self.ins))
        util.range_check(1, 2, num)
        if state.basic_state.events.com[num-1].command(util.skip_white(self.ins)):
            self.ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(self.ins, tk.end_statement)

    def exec_timer(self):
        """ TIMER: switch on/off timer event handling. """
        if state.basic_state.events.timer.command(util.skip_white(self.ins)):
            self.ins.read(1)
        else:
            raise error.RunError(error.STX)
        util.require(self.ins, tk.end_statement)

    def exec_key_events(self):
        """ KEY: switch on/off keyboard events. """
        num = vartypes.pass_int_unpack(expressions.parse_bracket(self.ins))
        util.range_check(0, 255, num)
        d = util.skip_white(self.ins)
        # others are ignored
        if num >= 1 and num <= 20:
            if state.basic_state.events.key[num-1].command(d):
                self.ins.read(1)
            else:
                raise error.RunError(error.STX)

    def _parse_on_event(self, bracket=True):
        """ Helper function for ON event trap definitions. """
        num = None
        if bracket:
            num = expressions.parse_bracket(self.ins)
        util.require_read(self.ins, (tk.GOSUB,))
        jumpnum = util.parse_jumpnum(self.ins)
        if jumpnum == 0:
            jumpnum = None
        elif jumpnum not in state.basic_state.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        util.require(self.ins, tk.end_statement)
        return num, jumpnum

    def exec_on_key(self):
        """ ON KEY: define key event trapping. """
        keynum, jumpnum = self._parse_on_event()
        keynum = vartypes.pass_int_unpack(keynum)
        util.range_check(1, 20, keynum)
        state.basic_state.events.key[keynum-1].set_jump(jumpnum)

    def exec_on_timer(self):
        """ ON TIMER: define timer event trapping. """
        timeval, jumpnum = self._parse_on_event()
        timeval = vartypes.pass_single(timeval)
        period = fp.mul(fp.unpack(timeval), fp.Single.from_int(1000)).round_to_int()
        state.basic_state.events.timer.set_trigger(period)
        state.basic_state.events.timer.set_jump(jumpnum)

    def exec_on_play(self):
        """ ON PLAY: define music event trapping. """
        playval, jumpnum = self._parse_on_event()
        playval = vartypes.pass_int_unpack(playval)
        state.basic_state.events.play.set_trigger(playval)
        state.basic_state.events.play.set_jump(jumpnum)

    def exec_on_pen(self):
        """ ON PEN: define light pen event trapping. """
        _, jumpnum = self._parse_on_event(bracket=False)
        state.basic_state.events.pen.set_jump(jumpnum)

    def exec_on_strig(self):
        """ ON STRIG: define fire button event trapping. """
        strigval, jumpnum = self._parse_on_event()
        strigval = vartypes.pass_int_unpack(strigval)
        ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
        if strigval not in (0,2,4,6):
            raise error.RunError(error.IFC)
        state.basic_state.events.strig[strigval//2].set_jump(jumpnum)

    def exec_on_com(self):
        """ ON COM: define serial port event trapping. """
        keynum, jumpnum = self._parse_on_event()
        keynum = vartypes.pass_int_unpack(keynum)
        util.range_check(1, 2, keynum)
        state.basic_state.events.com[keynum-1].set_jump(jumpnum)

    ##########################################################
    # sound

    def exec_beep(self):
        """ BEEP: produce an alert sound or switch internal speaker on/off. """
        # Tandy/PCjr BEEP ON, OFF
        if self.syntax in ('pcjr', 'tandy') and util.skip_white(self.ins) in (tk.ON, tk.OFF):
            state.console_state.beep_on = (self.ins.read(1) == tk.ON)
            util.require(self.ins, tk.end_statement)
            return
        state.console_state.sound.beep()
        # if a syntax error happens, we still beeped.
        util.require(self.ins, tk.end_statement)
        if state.console_state.sound.foreground:
            state.console_state.sound.wait_music()

    def exec_sound(self):
        """ SOUND: produce an arbitrary sound or switch external speaker on/off. """
        # Tandy/PCjr SOUND ON, OFF
        if self.syntax in ('pcjr', 'tandy') and util.skip_white(self.ins) in (tk.ON, tk.OFF):
            state.console_state.sound.sound_on = (self.ins.read(1) == tk.ON)
            util.require(self.ins, tk.end_statement)
            return
        freq = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.require_read(self.ins, (',',))
        dur = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins)))
        if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
            raise error.RunError(error.IFC)
        # only look for args 3 and 4 if duration is > 0; otherwise those args are a syntax error (on tandy)
        if dur.gt(fp.Single.zero):
            if (util.skip_white_read_if(self.ins, (',',)) and (self.syntax == 'tandy' or
                    (self.syntax == 'pcjr' and state.console_state.sound.sound_on))):
                volume = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
                util.range_check(0, 15, volume)
                if util.skip_white_read_if(self.ins, (',',)):
                    voice = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
                    util.range_check(0, 2, voice) # can't address noise channel here
                else:
                    voice = 0
            else:
                volume, voice = 15, 0
        util.require(self.ins, tk.end_statement)
        if dur.is_zero():
            state.console_state.sound.stop_all_sound()
            return
        # Tandy only allows frequencies below 37 (but plays them as 110 Hz)
        if freq != 0:
            util.range_check(-32768 if self.syntax == 'tandy' else 37, 32767, freq) # 32767 is pause
        # calculate duration in seconds
        one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
        dur_sec = dur.to_value()/18.2
        if one_over_44.gt(dur):
            # play indefinitely in background
            state.console_state.sound.play_sound(freq, dur_sec, loop=True, voice=voice, volume=volume)
        else:
            state.console_state.sound.play_sound(freq, dur_sec, voice=voice, volume=volume)
            if state.console_state.sound.foreground:
                state.console_state.sound.wait_music()

    def exec_play(self):
        """ PLAY: play sound sequence defined by a Music Macro Language string. """
        # PLAY: event switch
        if state.basic_state.events.play.command(util.skip_white(self.ins)):
            self.ins.read(1)
            util.require(self.ins, tk.end_statement)
        else:
            # retrieve Music Macro Language string
            with state.basic_state.strings:
                mml0 = var.copy_str(vartypes.pass_string(
                        expressions.parse_expression(self.ins, allow_empty=True),
                        allow_empty=True))
            mml1, mml2 = '', ''
            if ((self.syntax == 'tandy' or (self.syntax == 'pcjr' and
                                             state.console_state.sound.sound_on))
                    and util.skip_white_read_if(self.ins, (',',))):
                with state.basic_state.strings:
                    mml1 = var.copy_str(vartypes.pass_string(
                            expressions.parse_expression(self.ins, allow_empty=True),
                            allow_empty=True))
                if util.skip_white_read_if(self.ins, (',',)):
                    with state.basic_state.strings:
                        mml2 = var.copy_str(vartypes.pass_string(
                                expressions.parse_expression(self.ins, allow_empty=True),
                                allow_empty=True))
            util.require(self.ins, tk.end_statement)
            if not (mml0 or mml1 or mml2):
                raise error.RunError(error.MISSING_OPERAND)
            state.console_state.sound.play((mml0, mml1, mml2))

    def exec_noise(self):
        """ NOISE: produce sound on the noise generator (Tandy/PCjr). """
        if not state.console_state.sound.sound_on:
            raise error.RunError(error.IFC)
        source = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.require_read(self.ins, (',',))
        volume = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.require_read(self.ins, (',',))
        util.range_check(0, 7, source)
        util.range_check(0, 15, volume)
        dur = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins)))
        if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
            raise error.RunError(error.IFC)
        util.require(self.ins, tk.end_statement)
        one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
        dur_sec = dur.to_value()/18.2
        if one_over_44.gt(dur):
            state.console_state.sound.play_noise(source, volume, dur_sec, loop=True)
        else:
            state.console_state.sound.play_noise(source, volume, dur_sec)


    ##########################################################
    # machine emulation

    def exec_poke(self):
        """ POKE: write to a memory location. Limited implementation. """
        addr = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint=0xffff)
        if state.basic_state.protected and not state.basic_state.run_mode:
            raise error.RunError(error.IFC)
        util.require_read(self.ins, (',',))
        val = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, 255, val)
        machine.poke(addr, val)
        util.require(self.ins, tk.end_statement)

    def exec_def_seg(self):
        """ DEF SEG: set the current memory segment. """
        # &hb800: text screen buffer; &h13d: data segment
        if util.skip_white_read_if(self.ins, (tk.O_EQ,)): #=
            state.basic_state.segment = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint=0xffff)
        else:
            state.basic_state.segment = memory.data_segment
        if state.basic_state.segment < 0:
            state.basic_state.segment += 0x10000
        util.require(self.ins, tk.end_statement)

    def exec_def_usr(self):
        """ DEF USR: Define a machine language function. Not implemented. """
        util.require_read(self.ins, tk.digit)
        util.require_read(self.ins, (tk.O_EQ,))
        vartypes.pass_integer(expressions.parse_expression(self.ins), maxint=0xffff)
        util.require(self.ins, tk.end_statement)
        logging.warning("DEF USR statement not implemented")

    def exec_bload(self):
        """ BLOAD: load a file into a memory location. Limited implementation. """
        if state.basic_state.protected and not state.basic_state.run_mode:
            raise error.RunError(error.IFC)
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        offset = None
        if util.skip_white_read_if(self.ins, (',',)):
            offset = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint=0xffff)
            if offset < 0:
                offset += 0x10000
        util.require(self.ins, tk.end_statement)
        with devices.open_file(0, name, filetype='M', mode='I') as f:
            machine.bload(f, offset)

    def exec_bsave(self):
        """ BSAVE: save a block of memory to a file. Limited implementation. """
        if state.basic_state.protected and not state.basic_state.run_mode:
            raise error.RunError(error.IFC)
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        util.require_read(self.ins, (',',))
        offset = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint = 0xffff)
        if offset < 0:
            offset += 0x10000
        util.require_read(self.ins, (',',))
        length = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint = 0xffff)
        if length < 0:
            length += 0x10000
        util.require(self.ins, tk.end_statement)
        with devices.open_file(0, name, filetype='M', mode='O',
                                seg=state.basic_state.segment,
                                offset=offset, length=length) as f:
            machine.bsave(f, offset, length)

    def exec_call(self):
        """ CALL: call an external procedure. Not implemented. """
        addr_var = util.parse_scalar(self.ins)
        if addr_var[-1] == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        if util.skip_white_read_if(self.ins, ('(',)):
            while True:
                # if we wanted to call a function, we should distinguish varnames
                # (passed by ref) from constants (passed by value) here.
                expressions.parse_expression(self.ins)
                if not util.skip_white_read_if(self.ins, (',',)):
                    break
            util.require_read(self.ins, (')',))
        util.require(self.ins, tk.end_statement)
        # ignore the statement
        logging.warning("CALL or CALLS statement not implemented")

    def exec_calls(self):
        """ CALLS: call an external procedure. Not implemented. """
        self.exec_call()

    def exec_out(self):
        """ OUT: send a byte to a machine port. Limited implementation. """
        addr = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint=0xffff)
        util.require_read(self.ins, (',',))
        val = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, 255, val)
        machine.out(addr, val)
        util.require(self.ins, tk.end_statement)

    def exec_wait(self):
        """ WAIT: wait for a machine port. Limited implementation. """
        addr = vartypes.pass_int_unpack(expressions.parse_expression(self.ins), maxint=0xffff)
        util.require_read(self.ins, (',',))
        ander = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, 255, ander)
        xorer = 0
        if util.skip_white_read_if(self.ins, (',',)):
            xorer = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, 255, xorer)
        util.require(self.ins, tk.end_statement)
        machine.wait(addr, ander, xorer)


    ##########################################################
    # Disk

    def exec_chdir(self):
        """ CHDIR: change working directory. """
        with state.basic_state.strings:
            dev, path = disk.get_diskdevice_and_path(
                var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins))))
        dev.chdir(path)
        util.require(self.ins, tk.end_statement)

    def exec_mkdir(self):
        """ MKDIR: create directory. """
        with state.basic_state.strings:
            dev, path = disk.get_diskdevice_and_path(
                var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins))))
        dev.mkdir(path)
        util.require(self.ins, tk.end_statement)

    def exec_rmdir(self):
        """ RMDIR: remove directory. """
        with state.basic_state.strings:
            dev, path = disk.get_diskdevice_and_path(
                var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins))))
        dev.rmdir(path)
        util.require(self.ins, tk.end_statement)

    def exec_name(self):
        """ NAME: rename file or directory. """
        with state.basic_state.strings:
            oldname = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # AS is not a tokenised word
        word = util.skip_white_read(self.ins) + self.ins.read(1)
        if word.upper() != 'AS':
            raise error.RunError(error.STX)
        with state.basic_state.strings:
            newname = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        dev, oldpath = disk.get_diskdevice_and_path(oldname)
        newdev, newpath = disk.get_diskdevice_and_path(newname)
        # don't rename open files
        dev.check_file_not_open(oldpath)
        if dev != newdev:
            raise error.RunError(error.RENAME_ACROSS_DISKS)
        dev.rename(oldpath, newpath)
        util.require(self.ins, tk.end_statement)

    def exec_kill(self):
        """ KILL: remove file. """
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # don't delete open files
        dev, path = disk.get_diskdevice_and_path(name)
        dev.check_file_not_open(path)
        dev.kill(path)
        util.require(self.ins, tk.end_statement)

    def exec_files(self):
        """ FILES: output directory listing. """
        pathmask = ''
        if util.skip_white(self.ins) not in tk.end_statement:
            with state.basic_state.strings:
                pathmask = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
            if not pathmask:
                raise error.RunError(error.BAD_FILE_NAME)
        dev, path = disk.get_diskdevice_and_path(pathmask)
        dev.files(path)
        util.require(self.ins, tk.end_statement)


    ##########################################################
    # OS

    def exec_shell(self):
        """ SHELL: open OS shell and optionally execute command. """
        # parse optional shell command
        if util.skip_white(self.ins) in tk.end_statement:
            cmd = ''
        else:
            with state.basic_state.strings:
                cmd = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # no SHELL on PCjr.
        if self.syntax == 'pcjr':
            raise error.RunError(error.IFC)
        # force cursor visible in all cases
        state.console_state.screen.cursor.show(True)
        # execute cms or open interactive shell
        shell.shell(cmd)
        # reset cursor visibility to its previous state
        state.console_state.screen.cursor.reset_visibility()
        util.require(self.ins, tk.end_statement)

    def exec_environ(self):
        """ ENVIRON: set environment string. """
        with state.basic_state.strings:
            envstr = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        eqs = envstr.find('=')
        if eqs <= 0:
            raise error.RunError(error.IFC)
        envvar = str(envstr[:eqs])
        val = str(envstr[eqs+1:])
        os.environ[envvar] = val
        util.require(self.ins, tk.end_statement)

    def exec_time(self):
        """ TIME$: set time. """
        util.require_read(self.ins, (tk.O_EQ,)) #time$=
        # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
        with state.basic_state.strings:
            timestr = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        util.require(self.ins, tk.end_statement)
        timedate.set_time(timestr)

    def exec_date(self):
        """ DATE$: set date. """
        util.require_read(self.ins, (tk.O_EQ,)) # date$=
        # allowed formats:
        # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
        # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
        with state.basic_state.strings:
            datestr = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        util.require(self.ins, tk.end_statement)
        timedate.set_date(datestr)

    ##########################################################
    # code

    def _parse_line_range(self):
        """ Helper function: parse line number ranges. """
        from_line = self._parse_jumpnum_or_dot(allow_empty=True)
        if util.skip_white_read_if(self.ins, (tk.O_MINUS,)):
            to_line = self._parse_jumpnum_or_dot(allow_empty=True)
        else:
            to_line = from_line
        return (from_line, to_line)

    def _parse_jumpnum_or_dot(self, allow_empty=False, err=error.STX):
        """ Helper function: parse jump target. """
        c = util.skip_white_read(self.ins)
        if c == tk.T_UINT:
            return vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(self.ins.read(2)))
        elif c == '.':
            return state.basic_state.last_stored
        else:
            if allow_empty:
                self.ins.seek(-len(c), 1)
                return None
            raise error.RunError(err)

    def exec_delete(self):
        """ DELETE: delete range of lines from program. """
        from_line, to_line = self._parse_line_range()
        util.require(self.ins, tk.end_statement)
        # throws back to direct mode
        program.delete(from_line, to_line)
        # clear all variables
        reset.clear()

    def exec_edit(self):
        """ EDIT: output a program line and position cursor for editing. """
        if util.skip_white(self.ins) in tk.end_statement:
            # undefined line number
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        from_line = self._parse_jumpnum_or_dot(err=error.IFC)
        if from_line is None or from_line not in state.basic_state.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        util.require(self.ins, tk.end_statement, err=error.IFC)
        # throws back to direct mode
        flow.set_pointer(False)
        state.basic_state.parse_mode = False
        state.console_state.screen.cursor.reset_visibility()
        # request edit prompt
        self.session.edit_prompt = (from_line, None)

    def exec_auto(self):
        """ AUTO: enter automatic line numbering mode. """
        linenum = self._parse_jumpnum_or_dot(allow_empty=True)
        increment = None
        if util.skip_white_read_if(self.ins, (',',)):
            increment = util.parse_jumpnum(self.ins, allow_empty=True)
        util.require(self.ins, tk.end_statement)
        # reset linenum and increment on each call of AUTO (even in AUTO mode)
        self.session.auto_linenum = linenum if linenum is not None else 10
        self.session.auto_increment = increment if increment is not None else 10
        # move program pointer to end
        flow.set_pointer(False)
        # continue input in AUTO mode
        self.session.auto_mode = True

    def exec_list(self):
        """ LIST: output program lines. """
        from_line, to_line = self._parse_line_range()
        out = None
        if util.skip_white_read_if(self.ins, (',',)):
            with state.basic_state.strings:
                outname = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
            out = devices.open_file(0, outname, filetype='A', mode='O')
            # ignore everything after file spec
            util.skip_to(self.ins, tk.end_line)
        util.require(self.ins, tk.end_statement)
        lines = program.list_lines(from_line, to_line)
        if out:
            with out:
                for l in lines:
                    out.write_line(l)
        else:
            for l in lines:
                # LIST on screen is slightly different from just writing
                console.list_line(l)

    def exec_llist(self):
        """ LLIST: output program lines to LPT1: """
        from_line, to_line = self._parse_line_range()
        util.require(self.ins, tk.end_statement)
        for l in program.list_lines(from_line, to_line):
            state.io_state.lpt1_file.write_line(l)

    def exec_load(self):
        """ LOAD: load program from file. """
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        comma = util.skip_white_read_if(self.ins, (',',))
        if comma:
            util.require_read(self.ins, 'R')
        util.require(self.ins, tk.end_statement)
        with devices.open_file(0, name, filetype='ABP', mode='I') as f:
            program.load(f)
        reset.clear()
        if comma:
            # in ,R mode, don't close files; run the program
            flow.jump(None)
        else:
            devices.close_files()
        state.basic_state.tron = False

    def exec_chain(self):
        """ CHAIN: load program and chain execution. """
        if util.skip_white_read_if(self.ins, (tk.MERGE,)):
            action = program.merge
        else:
            action = program.load
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        jumpnum, common_all, delete_lines = None, False, None
        if util.skip_white_read_if(self.ins, (',',)):
            # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
            expr = expressions.parse_expression(self.ins, allow_empty=True)
            if expr is not None:
                jumpnum = vartypes.pass_int_unpack(expr, maxint=0xffff)
                # negative numbers will be two's complemented into a line number
                if jumpnum < 0:
                    jumpnum = 0x10000 + jumpnum
            if util.skip_white_read_if(self.ins, (',',)):
                if util.skip_white_read_if(self.ins, ('ALL',)):
                    common_all = True
                    # CHAIN "file", , ALL, DELETE
                    if util.skip_white_read_if(self.ins, (',',)):
                        delete_lines = self._parse_delete_clause()
                else:
                    # CHAIN "file", , DELETE
                    delete_lines = self._parse_delete_clause()
        util.require(self.ins, tk.end_statement)
        if state.basic_state.protected and action == program.merge:
                raise error.RunError(error.IFC)
        with devices.open_file(0, name, filetype='ABP', mode='I') as f:
            program.chain(action, f, jumpnum, delete_lines)
        # preserve DEFtype on MERGE
        reset.clear(preserve_common=True, preserve_all=common_all, preserve_deftype=(action==program.merge))

    def _parse_delete_clause(self):
        """ Helper function: parse the DELETE clause of a CHAIN statement. """
        delete_lines = None
        if util.skip_white_read_if(self.ins, (tk.DELETE,)):
            from_line = util.parse_jumpnum(self.ins, allow_empty=True)
            if util.skip_white_read_if(self.ins, (tk.O_MINUS,)):
                to_line = util.parse_jumpnum(self.ins, allow_empty=True)
            else:
                to_line = from_line
            # to_line must be specified and must be an existing line number
            if not to_line or to_line not in state.basic_state.line_numbers:
                raise error.RunError(error.IFC)
            delete_lines = (from_line, to_line)
            # ignore rest if preceded by cmma
            if util.skip_white_read_if(self.ins, (',',)):
                util.skip_to(self.ins, tk.end_statement)
        return delete_lines

    def exec_save(self):
        """ SAVE: save program to a file. """
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        mode = 'B'
        if util.skip_white_read_if(self.ins, (',',)):
            mode = util.skip_white_read(self.ins).upper()
            if mode not in ('A', 'P'):
                raise error.RunError(error.STX)
        with devices.open_file(0, name, filetype=mode, mode='O',
                                seg=memory.data_segment, offset=memory.code_start,
                                length=len(state.basic_state.bytecode.getvalue())-1
                                ) as f:
            program.save(f)
        util.require(self.ins, tk.end_statement)

    def exec_merge(self):
        """ MERGE: merge lines from file into current program. """
        with state.basic_state.strings:
            name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # check if file exists, make some guesses (all uppercase, +.BAS) if not
        with devices.open_file(0, name, filetype='A', mode='I') as f:
            program.merge(f)
        util.require(self.ins, tk.end_statement)

    def exec_new(self):
        """ NEW: clear program from memory. """
        state.basic_state.tron = False
        # deletes the program currently in memory
        program.erase_program()
        # and clears all variables
        reset.clear()

    def exec_renum(self):
        """ RENUM: renumber program line numbers. """
        new, old, step = None, None, None
        if util.skip_white(self.ins) not in tk.end_statement:
            new = self._parse_jumpnum_or_dot(allow_empty=True)
            if util.skip_white_read_if(self.ins, (',',)):
                old = self._parse_jumpnum_or_dot(allow_empty=True)
                if util.skip_white_read_if(self.ins, (',',)):
                    step = util.parse_jumpnum(self.ins, allow_empty=True) # returns -1 if empty
        util.require(self.ins, tk.end_statement)
        if step is not None and step < 1:
            raise error.RunError(error.IFC)
        program.renum(new, old, step)


    ##########################################################
    # file

    def exec_reset(self):
        """ RESET: close all files. """
        devices.close_files()
        util.require(self.ins, tk.end_statement)

    def _parse_read_write(self):
        """ Helper function: parse access mode. """
        d = util.skip_white(self.ins)
        if d == tk.WRITE:
            self.ins.read(1)
            access = 'W'
        elif d == tk.READ:
            self.ins.read(1)
            access = 'RW' if util.skip_white_read_if(self.ins, (tk.WRITE,)) else 'R'
        return access


    def exec_open(self):
        """ OPEN: open a file. """
        long_modes = {tk.INPUT:'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}
        default_access_modes = {'I':'R', 'O':'W', 'A':'RW', 'R':'RW'}
        with state.basic_state.strings:
            first_expr = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        mode, access, lock, reclen = 'R', 'RW', '', 128
        if util.skip_white_read_if(self.ins, (',',)):
            # first syntax
            try:
                mode = first_expr[0].upper()
                access = default_access_modes[mode]
            except (IndexError, KeyError):
                raise error.RunError(error.BAD_FILE_MODE)
            number = expressions.parse_file_number_opthash(self.ins)
            util.require_read(self.ins, (',',))
            with state.basic_state.strings:
                name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
            if util.skip_white_read_if(self.ins, (',',)):
                reclen = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        else:
            # second syntax
            name = first_expr
            # FOR clause
            if util.skip_white_read_if(self.ins, (tk.FOR,)):
                c = util.skip_white(self.ins)
                # read word
                word = ''
                while c and c not in tk.whitespace and c not in tk.end_statement:
                    word += self.ins.read(1)
                    c = util.peek(self.ins).upper()
                try:
                    mode = long_modes[word]
                except KeyError:
                    raise error.RunError(error.STX)
            try:
                access = default_access_modes[mode]
            except (KeyError):
                raise error.RunError(error.BAD_FILE_MODE)
            # ACCESS clause
            if util.skip_white_read_if(self.ins, ('ACCESS',)):
                util.skip_white(self.ins)
                access = self._parse_read_write()
            # LOCK clause
            if util.skip_white_read_if(self.ins, (tk.LOCK,)):
                util.skip_white(self.ins)
                lock = self._parse_read_write()
            elif util.skip_white_read_if(self.ins, ('SHARED',)):
                lock = 'S'
            # AS file number clause
            if not util.skip_white_read_if(self.ins, ('AS',)):
                raise error.RunError(error.STX)
            number = expressions.parse_file_number_opthash(self.ins)
            # LEN clause
            if util.skip_white_read_if(self.ins, (tk.LEN,)):
                util.require_read(self.ins, tk.O_EQ)
                reclen = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        # mode and access must match if not a RANDOM file
        # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
        # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
        if mode == 'A' and access == 'W':
            raise error.RunError(error.PATH_FILE_ACCESS_ERROR)
        elif mode != 'R' and access and access != default_access_modes[mode]:
            raise error.RunError(error.STX)
        util.range_check(1, state.io_state.max_reclen, reclen)
        # can't open file 0, or beyond max_files
        util.range_check_err(1, state.io_state.max_files, number, error.BAD_FILE_NUMBER)
        devices.open_file(number, name, 'D', mode, access, lock, reclen)
        util.require(self.ins, tk.end_statement)

    def exec_close(self):
        """ CLOSE: close a file. """
        if util.skip_white(self.ins) in tk.end_statement:
            # allow empty CLOSE; close all open files
            devices.close_files()
        else:
            while True:
                number = expressions.parse_file_number_opthash(self.ins)
                try:
                    devices.close_file(number)
                except KeyError:
                    pass
                if not util.skip_white_read_if(self.ins, (',',)):
                    break
        util.require(self.ins, tk.end_statement)

    def exec_field(self):
        """ FIELD: link a string variable to record buffer. """
        the_file = devices.get_file(expressions.parse_file_number_opthash(self.ins), 'R')
        if util.skip_white_read_if(self.ins, (',',)):
            offset = 0
            while True:
                width = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
                util.range_check(0, 255, width)
                util.require_read(self.ins, ('AS',), err=error.IFC)
                name, index = expressions.parse_variable(self.ins)
                the_file.field.attach_var(name, index, offset, width)
                offset += width
                if not util.skip_white_read_if(self.ins, (',',)):
                    break
        util.require(self.ins, tk.end_statement)

    def _parse_get_or_put_file(self):
        """ Helper function: PUT and GET syntax. """
        the_file = devices.get_file(expressions.parse_file_number_opthash(self.ins), 'R')
        # for COM files
        num_bytes = the_file.reclen
        if util.skip_white_read_if(self.ins, (',',)):
            pos = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins))).round_to_int()
            # not 2^32-1 as the manual boasts!
            # pos-1 needs to fit in a single-precision mantissa
            util.range_check_err(1, 2**25, pos, err=error.BAD_RECORD_NUMBER)
            if not isinstance(the_file, ports.COMFile):
                the_file.set_pos(pos)
            else:
                num_bytes = pos
        return the_file, num_bytes

    def exec_put_file(self):
        """ PUT: write record to file. """
        thefile, num_bytes = self._parse_get_or_put_file()
        thefile.put(num_bytes)
        util.require(self.ins, tk.end_statement)

    def exec_get_file(self):
        """ GET: read record from file. """
        thefile, num_bytes = self._parse_get_or_put_file()
        thefile.get(num_bytes)
        util.require(self.ins, tk.end_statement)

    def exec_lock_or_unlock(self, action):
        """ LOCK or UNLOCK: set file or record locks. """
        thefile = devices.get_file(expressions.parse_file_number_opthash(self.ins))
        lock_start_rec = 1
        if util.skip_white_read_if(self.ins, (',',)):
            lock_start_rec = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins))).round_to_int()
        lock_stop_rec = lock_start_rec
        if util.skip_white_read_if(self.ins, (tk.TO,)):
            lock_stop_rec = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins))).round_to_int()
        if lock_start_rec < 1 or lock_start_rec > 2**25-2 or lock_stop_rec < 1 or lock_stop_rec > 2**25-2:
            raise error.RunError(error.BAD_RECORD_NUMBER)
        try:
            getattr(thefile, action)(lock_start_rec, lock_stop_rec)
        except AttributeError:
            # not a disk file
            raise error.RunError(error.PERMISSION_DENIED)
        util.require(self.ins, tk.end_statement)

    exec_lock = partial(exec_lock_or_unlock, action = 'lock')
    exec_unlock = partial(exec_lock_or_unlock, action = 'unlock')

    def exec_ioctl(self):
        """ IOCTL: send control string to I/O device. Not implemented. """
        devices.get_file(expressions.parse_file_number_opthash(self.ins))
        logging.warning("IOCTL statement not implemented.")
        raise error.RunError(error.IFC)

    ##########################################################
    # Graphics statements

    def _parse_coord_bare(self):
        """ Helper function: parse coordinate pair. """
        util.require_read(self.ins, ('(',))
        x = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins)))
        util.require_read(self.ins, (',',))
        y = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins)))
        util.require_read(self.ins, (')',))
        return x, y

    def _parse_coord_step(self):
        """ Helper function: parse coordinate pair. """
        step = util.skip_white_read_if(self.ins, (tk.STEP,))
        x, y = self._parse_coord_bare()
        return x, y, step

    def exec_pset(self, c=-1):
        """ PSET: set a pixel to a given attribute, or foreground. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        lcoord = self._parse_coord_step()
        if util.skip_white_read_if(self.ins, (',',)):
            c = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(-1, 255, c)
        util.require(self.ins, tk.end_statement)
        state.console_state.screen.drawing.pset(lcoord, c)

    def exec_preset(self):
        """ PRESET: set a pixel to a given attribute, or background. """
        self.exec_pset(0)

    def exec_line_graph(self):
        """ LINE: draw a line or box between two points. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        if util.skip_white(self.ins) in ('(', tk.STEP):
            coord0 = self._parse_coord_step()
        else:
            coord0 = None
        util.require_read(self.ins, (tk.O_MINUS,))
        coord1 = self._parse_coord_step()
        c, mode, pattern = -1, '', 0xffff
        if util.skip_white_read_if(self.ins, (',',)):
            expr = expressions.parse_expression(self.ins, allow_empty=True)
            if expr:
                c = vartypes.pass_int_unpack(expr)
            if util.skip_white_read_if(self.ins, (',',)):
                if util.skip_white_read_if(self.ins, ('B',)):
                    mode = 'BF' if util.skip_white_read_if(self.ins, ('F',)) else 'B'
                else:
                    util.require(self.ins, (',',))
                if util.skip_white_read_if(self.ins, (',',)):
                    pattern = vartypes.pass_int_unpack(
                                expressions.parse_expression(self.ins), maxint=0x7fff)
            elif not expr:
                raise error.RunError(error.MISSING_OPERAND)
        util.require(self.ins, tk.end_statement)
        state.console_state.screen.drawing.line(coord0, coord1, c, pattern, mode)

    def exec_view_graph(self):
        """ VIEW: set graphics viewport and optionally draw a box. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        absolute = util.skip_white_read_if(self.ins, (tk.SCREEN,))
        if util.skip_white(self.ins) == '(':
            x0, y0 = self._parse_coord_bare()
            x0, y0 = x0.round_to_int(), y0.round_to_int()
            util.require_read(self.ins, (tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare()
            x1, y1 = x1.round_to_int(), y1.round_to_int()
            util.range_check(0, state.console_state.screen.mode.pixel_width-1, x0, x1)
            util.range_check(0, state.console_state.screen.mode.pixel_height-1, y0, y1)
            fill, border = None, None
            if util.skip_white_read_if(self.ins, (',',)):
                fill = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
                util.require_read(self.ins, (',',))
                border = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            state.console_state.screen.drawing.set_view(x0, y0, x1, y1, absolute, fill, border)
        else:
            state.console_state.screen.drawing.unset_view()
        util.require(self.ins, tk.end_statement)

    def exec_window(self):
        """ WINDOW: define logical coordinate system. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        cartesian = not util.skip_white_read_if(self.ins, (tk.SCREEN,))
        if util.skip_white(self.ins) == '(':
            x0, y0 = self._parse_coord_bare()
            util.require_read(self.ins, (tk.O_MINUS,))
            x1, y1 = self._parse_coord_bare()
            if x0.equals(x1) or y0.equals(y1):
                raise error.RunError(error.IFC)
            state.console_state.screen.drawing.set_window(x0, y0, x1, y1, cartesian)
        else:
            state.console_state.screen.drawing.unset_window()
        util.require(self.ins, tk.end_statement)

    def exec_circle(self):
        """ CIRCLE: Draw a circle, ellipse, arc or sector. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        centre = self._parse_coord_step()
        util.require_read(self.ins, (',',))
        r = fp.unpack(vartypes.pass_single(expressions.parse_expression(self.ins)))
        start, stop, c, aspect = None, None, -1, None
        if util.skip_white_read_if(self.ins, (',',)):
            cval = expressions.parse_expression(self.ins, allow_empty=True)
            if cval:
                c = vartypes.pass_int_unpack(cval)
            if util.skip_white_read_if(self.ins, (',',)):
                start = expressions.parse_expression(self.ins, allow_empty=True)
                if util.skip_white_read_if(self.ins, (',',)):
                    stop = expressions.parse_expression(self.ins, allow_empty=True)
                    if util.skip_white_read_if(self.ins, (',',)):
                        aspect = fp.unpack(vartypes.pass_single(
                                                expressions.parse_expression(self.ins)))
                    elif stop is None:
                        # missing operand
                        raise error.RunError(error.MISSING_OPERAND)
                elif start is None:
                    raise error.RunError(error.MISSING_OPERAND)
            elif cval is None:
                raise error.RunError(error.MISSING_OPERAND)
        util.require(self.ins, tk.end_statement)
        state.console_state.screen.drawing.circle(centre, r, start, stop, c, aspect)

    def exec_paint(self):
        """ PAINT: flood fill from point. """
        # if paint *colour* specified, border default = paint colour
        # if paint *attribute* specified, border default = current foreground
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        coord = self._parse_coord_step()
        pattern, c, border, background_pattern = None, -1, -1, None
        if util.skip_white_read_if(self.ins, (',',)):
            cval = expressions.parse_expression(self.ins, allow_empty=True)
            if not cval:
                pass
            elif cval[0] == '$':
                # pattern given; copy
                with state.basic_state.strings:
                    pattern = bytearray(var.copy_str(vartypes.pass_string(cval)))
                if not pattern:
                    # empty pattern "" is illegal function call
                    raise error.RunError(error.IFC)
                # default for border, if pattern is specified as string: foreground attr
            else:
                c = vartypes.pass_int_unpack(cval)
            border = c
            if util.skip_white_read_if(self.ins, (',',)):
                bval = expressions.parse_expression(self.ins, allow_empty=True)
                if bval:
                    border = vartypes.pass_int_unpack(bval)
                if util.skip_white_read_if(self.ins, (',',)):
                    with state.basic_state.strings:
                        background_pattern = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins), err=error.IFC))
                    # only in screen 7,8,9 is this an error (use ega memory as a check)
                    if (pattern and background_pattern[:len(pattern)] == pattern and
                            state.console_state.screen.mode.mem_start == 0xa000):
                        raise error.RunError(error.IFC)
        util.require(self.ins, tk.end_statement)
        state.console_state.screen.drawing.paint(coord, pattern, c, border, background_pattern)

    def exec_get_graph(self):
        """ GET: read a sprite to memory. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP for first coord
        util.require(self.ins, ('('))
        coord0 = self._parse_coord_step()
        util.require_read(self.ins, (tk.O_MINUS,))
        coord1 = self._parse_coord_step()
        util.require_read(self.ins, (',',))
        array = util.parse_scalar(self.ins)
        util.require(self.ins, tk.end_statement)
        if array not in state.basic_state.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            raise error.RunError(error.TYPE_MISMATCH) # type mismatch
        state.console_state.screen.drawing.get(coord0, coord1, array)

    def exec_put_graph(self):
        """ PUT: draw sprite on screen. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        # don't accept STEP
        util.require(self.ins, ('('))
        coord = self._parse_coord_step()
        util.require_read(self.ins, (',',))
        array = util.parse_scalar(self.ins)
        action = tk.XOR
        if util.skip_white_read_if(self.ins, (',',)):
            util.require(self.ins, (tk.PSET, tk.PRESET,
                               tk.AND, tk.OR, tk.XOR))
            action = self.ins.read(1)
        util.require(self.ins, tk.end_statement)
        if array not in state.basic_state.arrays:
            raise error.RunError(error.IFC)
        elif array[-1] == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        state.console_state.screen.drawing.put(coord, array, action)

    def exec_draw(self):
        """ DRAW: draw a figure defined by a Graphics Macro Language string. """
        if state.console_state.screen.mode.is_text_mode:
            raise error.RunError(error.IFC)
        with state.basic_state.strings:
            gml = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        util.require(self.ins, tk.end_statement)
        state.console_state.screen.drawing.draw(gml)

    ##########################################################
    # Flow-control statements

    def exec_end(self):
        """ END: end program execution and return to interpreter. """
        util.require(self.ins, tk.end_statement)
        state.basic_state.stop = state.basic_state.bytecode.tell()
        # jump to end of direct line so execution stops
        flow.set_pointer(False)
        # avoid NO RESUME
        state.basic_state.error_handle_mode = False
        state.basic_state.error_resume = None
        devices.close_files()

    def exec_stop(self):
        """ STOP: break program execution and return to interpreter. """
        util.require(self.ins, tk.end_statement)
        raise error.Break(stop=True)

    def exec_cont(self):
        """ CONT: continue STOPped or ENDed execution. """
        if state.basic_state.stop is None:
            raise error.RunError(error.CANT_CONTINUE)
        else:
            flow.set_pointer(True, state.basic_state.stop)
        # IN GW-BASIC, weird things happen if you do GOSUB nn :PRINT "x"
        # and there's a STOP in the subroutine.
        # CONT then continues and the rest of the original line is executed, printing x
        # However, CONT:PRINT triggers a bug - a syntax error in a nonexistant line number is reported.
        # CONT:PRINT "y" results in neither x nor y being printed.
        # if a command is executed before CONT, x is not printed.
        # It would appear that GW-BASIC only partially overwrites the line buffer and
        # then jumps back to the original return location!
        # in this implementation, the CONT command will fully overwrite the line buffer so x is not printed.

    def exec_for(self):
        """ FOR: enter for-loop. """
        # read variable
        varname = util.parse_scalar(self.ins)
        vartype = varname[-1]
        if vartype in ('$', '#'):
            raise error.RunError(error.TYPE_MISMATCH)
        util.require_read(self.ins, (tk.O_EQ,))
        start = vartypes.pass_type(vartype, expressions.parse_expression(self.ins))
        util.require_read(self.ins, (tk.TO,))
        stop = vartypes.pass_type(vartype, expressions.parse_expression(self.ins))
        if util.skip_white_read_if(self.ins, (tk.STEP,)):
            step = expressions.parse_expression(self.ins)
        else:
            # convert 1 to vartype
            step = vartypes.int_to_integer_signed(1)
        step = vartypes.pass_type(vartype, step)
        util.require(self.ins, tk.end_statement)
        endforpos = self.ins.tell()
        # find NEXT
        nextpos = self._find_next(varname)
        # apply initial condition and jump to nextpos
        flow.loop_init(self.ins, endforpos, nextpos, varname, start, stop, step)
        self.exec_next()

    def _skip_to_next(self, for_char, next_char, allow_comma=False):
        """ Helper function for FOR: skip over bytecode until NEXT. """
        stack = 0
        while True:
            c = util.skip_to_read(self.ins, tk.end_statement+(tk.THEN, tk.ELSE))
            # skip line number, if there
            if c == '\0' and util.parse_line_number(self.ins) == -1:
                break
            # get first keyword in statement
            d = util.skip_white(self.ins)
            if d == '':
                break
            elif d == for_char:
                self.ins.read(1)
                stack += 1
            elif d == next_char:
                if stack <= 0:
                    break
                else:
                    self.ins.read(1)
                    stack -= 1
                    # NEXT I, J
                    if allow_comma:
                        while (util.skip_white(self.ins) not in tk.end_statement):
                            util.skip_to(self.ins, tk.end_statement + (',',))
                            if util.peek(self.ins) == ',':
                                if stack > 0:
                                    self.ins.read(1)
                                    stack -= 1
                                else:
                                    return

    def _find_next(self, varname):
        """ Helper function for FOR: find the right NEXT. """
        current = self.ins.tell()
        self._skip_to_next(tk.FOR, tk.NEXT, allow_comma=True)
        if util.skip_white(self.ins) not in (tk.NEXT, ','):
            # FOR without NEXT marked with FOR line number
            self.ins.seek(current)
            raise error.RunError(error.FOR_WITHOUT_NEXT)
        comma = (self.ins.read(1) == ',')
        # get position and line number just after the NEXT
        nextpos = self.ins.tell()
        # check var name for NEXT
        varname2 = util.parse_scalar(self.ins, allow_empty=True)
        # no-var only allowed in standalone NEXT
        if not varname2:
            util.require(self.ins, tk.end_statement)
        if (comma or varname2) and varname2 != varname:
            # NEXT without FOR marked with NEXT line number, while we're only at FOR
            raise error.RunError(error.NEXT_WITHOUT_FOR)
        self.ins.seek(current)
        return nextpos

    def exec_next(self):
        """ NEXT: iterate for-loop. """
        while True:
            # record the NEXT (or comma) location
            pos = self.ins.tell()
            # optional variable - errors in this are checked at the scan during FOR
            name = util.parse_scalar(self.ins, allow_empty=True)
            # if we haven't read a variable, we shouldn't find something else here
            # but if we have and we iterate, the rest of the line is ignored
            if not name:
                util.require(self.ins, tk.end_statement + (',',))
            # increment counter, check condition
            if flow.loop_iterate(self.ins, pos):
                break
            # done if we're not jumping into a comma'ed NEXT
            if not util.skip_white_read_if(self.ins, (',')):
                break
        # if we're done iterating we no longer ignore the rest of the statement
        util.require(self.ins, tk.end_statement)

    def exec_goto(self):
        """ GOTO: jump to specified line number. """
        # parse line number, ignore rest of line and jump
        flow.jump(util.parse_jumpnum(self.ins))

    def exec_run(self):
        """ RUN: start program execution. """
        jumpnum, close_files = None, True
        c = util.skip_white(self.ins)
        if c == tk.T_UINT:
            # parse line number and ignore rest of line
            jumpnum = util.parse_jumpnum(self.ins)
        elif c not in tk.end_statement:
            with state.basic_state.strings:
                name = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
            if util.skip_white_read_if(self.ins, (',',)):
                util.require_read(self.ins, 'R')
                close_files = False
            util.require(self.ins, tk.end_statement)
            with devices.open_file(0, name, filetype='ABP', mode='I') as f:
                program.load(f)
        flow.init_program()
        reset.clear(close_files=close_files)
        flow.jump(jumpnum)
        state.basic_state.error_handle_mode = False

    def exec_if(self):
        """ IF: enter branching statement. """
        # avoid overflow: don't use bools.
        val = vartypes.pass_single(expressions.parse_expression(self.ins))
        util.skip_white_read_if(self.ins, (',',)) # optional comma
        util.require_read(self.ins, (tk.THEN, tk.GOTO))
        if not fp.unpack(val).is_zero():
            # TRUE: continue after THEN. line number or statement is implied GOTO
            if util.skip_white(self.ins) in (tk.T_UINT,):
                flow.jump(util.parse_jumpnum(self.ins))
            # continue parsing as normal, :ELSE will be ignored anyway
        else:
            # FALSE: find ELSE block or end of line; ELSEs are nesting on the line
            nesting_level = 0
            while True:
                d = util.skip_to_read(self.ins, tk.end_statement + (tk.IF,))
                if d == tk.IF:
                    # nexting step on IF. (it's less convenient to count THENs because they could be THEN, GOTO or THEN GOTO.)
                    nesting_level += 1
                elif d == ':':
                    if util.skip_white_read_if(self.ins, tk.ELSE): # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                        if nesting_level > 0:
                            nesting_level -= 1
                        else:
                            # line number: jump
                            if util.skip_white(self.ins) in (tk.T_UINT,):
                                flow.jump(util.parse_jumpnum(self.ins))
                            # continue execution from here
                            break
                else:
                    self.ins.seek(-len(d), 1)
                    break

    def exec_else(self):
        """ ELSE: part of branch statement; ignore. """
        # any else statement by itself means the THEN has already been executed, so it's really like a REM.
        util.skip_to(self.ins, tk.end_line)

    def exec_while(self):
        """ WHILE: enter while-loop. """
        # just after WHILE opcode
        whilepos = self.ins.tell()
        # evaluate the 'boolean' expression
        # use double to avoid overflows
        # find matching WEND
        self._skip_to_next(tk.WHILE, tk.WEND)
        if self.ins.read(1) == tk.WEND:
            util.skip_to(self.ins, tk.end_statement)
            wendpos = self.ins.tell()
            state.basic_state.while_wend_stack.append((whilepos, wendpos))
        else:
            # WHILE without WEND
            self.ins.seek(whilepos)
            raise error.RunError(error.WHILE_WITHOUT_WEND)
        self._check_while_condition(whilepos)
        util.require(self.ins, tk.end_statement)

    def _check_while_condition(self, whilepos):
        """ Check condition of while-loop. """
        self.ins.seek(whilepos)
        # WHILE condition is zero?
        if not fp.unpack(vartypes.pass_double(expressions.parse_expression(self.ins))).is_zero():
            # statement start is before WHILE token
            state.basic_state.current_statement = whilepos-2
            util.require(self.ins, tk.end_statement)
        else:
            # ignore rest of line and jump to WEND
            _, wendpos = state.basic_state.while_wend_stack.pop()
            self.ins.seek(wendpos)

    def exec_wend(self):
        """ WEND: iterate while-loop. """
        # while will actually syntax error on the first run if anything is in the way.
        util.require(self.ins, tk.end_statement)
        pos = self.ins.tell()
        while True:
            if not state.basic_state.while_wend_stack:
                # WEND without WHILE
                raise error.RunError(error.WEND_WITHOUT_WHILE)
            whilepos, wendpos = state.basic_state.while_wend_stack[-1]
            if pos == wendpos:
                break
            # not the expected WEND, we must have jumped out
            state.basic_state.while_wend_stack.pop()
        self._check_while_condition(whilepos)

    def exec_on_jump(self):
        """ ON: calculated jump. """
        onvar = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, 255, onvar)
        command = util.skip_white_read(self.ins)
        jumps = []
        while True:
            d = util.skip_white_read(self.ins)
            if d in tk.end_statement:
                self.ins.seek(-len(d), 1)
                break
            elif d in (tk.T_UINT,):
                jumps.append( self.ins.tell()-1 )
                self.ins.read(2)
            elif d == ',':
                pass
            else:
                raise error.RunError(error.STX)
        if jumps == []:
            raise error.RunError(error.STX)
        elif onvar > 0 and onvar <= len(jumps):
            self.ins.seek(jumps[onvar-1])
            if command == tk.GOTO:
                flow.jump(util.parse_jumpnum(self.ins))
            elif command == tk.GOSUB:
                self.exec_gosub()
        util.skip_to(self.ins, tk.end_statement)

    def exec_on_error(self):
        """ ON ERROR: define error trapping routine. """
        util.require_read(self.ins, (tk.GOTO,))  # GOTO
        linenum = util.parse_jumpnum(self.ins)
        if linenum != 0 and linenum not in state.basic_state.line_numbers:
            raise error.RunError(error.UNDEFINED_LINE_NUMBER)
        state.basic_state.on_error = linenum
        # ON ERROR GOTO 0 in error handler
        if state.basic_state.on_error == 0 and state.basic_state.error_handle_mode:
            # re-raise the error so that execution stops
            raise error.RunError(state.basic_state.errn, state.basic_state.errp)
        # this will be caught by the trapping routine just set
        util.require(self.ins, tk.end_statement)

    def exec_resume(self):
        """ RESUME: resume program flow after error-trap. """
        if state.basic_state.error_resume is None:
            # unset error handler
            state.basic_state.on_error = 0
            raise error.RunError(error.RESUME_WITHOUT_ERROR)
        c = util.skip_white(self.ins)
        if c == tk.NEXT:
            self.ins.read(1)
            jumpnum = -1
        elif c not in tk.end_statement:
            jumpnum = util.parse_jumpnum(self.ins)
        else:
            jumpnum = 0
        util.require(self.ins, tk.end_statement)
        flow.resume(jumpnum)

    def exec_error(self):
        """ ERRROR: simulate an error condition. """
        errn = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(1, 255, errn)
        raise error.RunError(errn)

    def exec_gosub(self):
        """ GOSUB: jump into a subroutine. """
        jumpnum = util.parse_jumpnum(self.ins)
        # ignore rest of statement ('GOSUB 100 LAH' works just fine..); we need to be able to RETURN
        util.skip_to(self.ins, tk.end_statement)
        flow.jump_gosub(jumpnum)

    def exec_return(self):
        """ RETURN: return from a subroutine. """
        # return *can* have a line number
        if util.skip_white(self.ins) not in tk.end_statement:
            jumpnum = util.parse_jumpnum(self.ins)
            # rest of line is ignored
            util.skip_to(self.ins, tk.end_statement)
        else:
            jumpnum = None
        flow.jump_return(jumpnum)

    ################################################
    # Variable & array statements

    def _parse_var_list(self):
        """ Helper function: parse variable list.  """
        readvar = []
        while True:
            readvar.append(list(expressions.parse_variable(self.ins)))
            if not util.skip_white_read_if(self.ins, (',',)):
                break
        return readvar

    def exec_clear(self):
        """ CLEAR: clear memory and redefine memory limits. """
        # integer expression allowed but ignored
        intexp = expressions.parse_expression(self.ins, allow_empty=True)
        if intexp:
            expr = vartypes.pass_int_unpack(intexp)
            if expr < 0:
                raise error.RunError(error.IFC)
        if util.skip_white_read_if(self.ins, (',',)):
            exp1 = expressions.parse_expression(self.ins, allow_empty=True)
            if exp1:
                # this produces a *signed* int
                mem_size = vartypes.pass_int_unpack(exp1, maxint=0xffff)
                if mem_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                else:
                    if not memory.set_basic_memory_size(mem_size):
                        raise error.RunError(error.OUT_OF_MEMORY)
            if util.skip_white_read_if(self.ins, (',',)):
                # set aside stack space for GW-BASIC. The default is the previous stack space size.
                exp2 = expressions.parse_expression(self.ins, allow_empty=True)
                if exp2:
                    stack_size = vartypes.pass_int_unpack(exp2, maxint=0xffff)
                    # this should be an unsigned int
                    if stack_size < 0:
                        stack_size += 0x10000
                    if stack_size == 0:
                        #  0 leads to illegal fn call
                        raise error.RunError(error.IFC)
                    memory.set_stack_size(stack_size)
                if self.syntax in ('pcjr', 'tandy') and util.skip_white_read_if(self.ins, (',',)):
                    # Tandy/PCjr: select video memory size
                    if not state.console_state.screen.set_video_memory_size(
                        fp.unpack(vartypes.pass_single(
                                     expressions.parse_expression(self.ins)
                                 )).round_to_int()):
                        state.console_state.screen.screen(0, 0, 0, 0)
                        console.init_mode()
                elif not exp2:
                    raise error.RunError(error.STX)
        util.require(self.ins, tk.end_statement)
        reset.clear()

    def exec_common(self):
        """ COMMON: define variables to be preserved on CHAIN. """
        varlist, arraylist = [], []
        while True:
            name = util.parse_scalar(self.ins)
            # array?
            if util.skip_white_read_if(self.ins, ('[', '(')):
                util.require_read(self.ins, (']', ')'))
                arraylist.append(name)
            else:
                varlist.append(name)
            if not util.skip_white_read_if(self.ins, (',',)):
                break
        state.basic_state.common_names += varlist
        state.basic_state.common_array_names += arraylist

    def exec_data(self):
        """ DATA: data definition; ignore. """
        # ignore rest of statement after DATA
        util.skip_to(self.ins, tk.end_statement)

    def exec_dim(self):
        """ DIM: dimension arrays. """
        while True:
            name, dimensions = expressions.parse_variable(self.ins)
            if not dimensions:
                dimensions = [10]
            var.dim_array(name, dimensions)
            if not util.skip_white_read_if(self.ins, (',',)):
                break
        util.require(self.ins, tk.end_statement)

    def exec_deftype(self, typechar):
        """ DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables. """
        start, stop = -1, -1
        while True:
            d = util.skip_white_read(self.ins)
            if d not in string.ascii_letters:
                raise error.RunError(error.STX)
            else:
                start = ord(d.upper()) - ord('A')
                stop = start
            if util.skip_white_read_if(self.ins, (tk.O_MINUS,)):
                d = util.skip_white_read(self.ins)
                if d not in string.ascii_letters:
                    raise error.RunError(error.STX)
                else:
                    stop = ord(d.upper()) - ord('A')
            state.basic_state.deftype[start:stop+1] = [typechar] * (stop-start+1)
            if not util.skip_white_read_if(self.ins, (',',)):
                break
        util.require(self.ins, tk.end_statement)

    exec_defstr = partial(exec_deftype, typechar='$')
    exec_defint = partial(exec_deftype, typechar='%')
    exec_defsng = partial(exec_deftype, typechar='!')
    exec_defdbl = partial(exec_deftype, typechar='#')

    def exec_erase(self):
        """ ERASE: erase an array. """
        while True:
            var.erase_array(util.parse_scalar(self.ins))
            if not util.skip_white_read_if(self.ins, (',',)):
                break
        util.require(self.ins, tk.end_statement)

    def exec_let(self):
        """ LET: assign value to variable or array. """
        name, indices = expressions.parse_variable(self.ins)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
            var.check_dim_array(name, indices)
        util.require_read(self.ins, (tk.O_EQ,))
        var.set_variable(name, indices, expressions.parse_expression(self.ins))
        util.require(self.ins, tk.end_statement)

    def exec_mid(self):
        """ MID$: set part of a string. """
        # do not use require_read as we don't allow whitespace here
        if self.ins.read(1) != '(':
            raise error.RunError(error.STX)
        name, indices = expressions.parse_variable(self.ins)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            var.check_dim_array(name, indices)
        util.require_read(self.ins, (',',))
        start = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        num = 255
        if util.skip_white_read_if(self.ins, (',',)):
            num = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.require_read(self.ins, (')',))
        with state.basic_state.strings:
            s = var.copy_str(vartypes.pass_string(var.get_variable(name, indices)))
        util.range_check(0, 255, num)
        if num > 0:
            util.range_check(1, len(s), start)
        util.require_read(self.ins, (tk.O_EQ,))
        with state.basic_state.strings:
            val = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        util.require(self.ins, tk.end_statement)
        # we need to decrement basic offset by 1 to get python offset
        offset = start-1
        # don't overwrite more of the old string than the length of the new string
        num = min(num, len(val))
        basic_str = var.get_variable(name, indices)
        # ensure the length of source string matches target
        length = vartypes.string_length(basic_str)
        if offset + num > length:
            num = length - offset
        if num <= 0:
            return
        # cut new string to size if too long
        val = val[:num]
        # copy new value into existing buffer if possible
        var.set_variable(name, indices, var.set_str(basic_str, val, offset, num))

    def exec_lset(self, justify_right=False):
        """ LSET: assign string value in-place; left justified. """
        name, index = expressions.parse_variable(self.ins)
        v = vartypes.pass_string(var.get_variable(name, index))
        util.require_read(self.ins, (tk.O_EQ,))
        with state.basic_state.strings:
            s = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        # v is empty string if variable does not exist
        # trim and pad to size of target buffer
        length = vartypes.string_length(v)
        s = s[:length]
        if justify_right:
            s = ' '*(length-len(s)) + s
        else:
            s += ' '*(length-len(s))
        # copy new value into existing buffer if possible
        var.set_variable(name, index, var.set_str(v, s))

    def exec_rset(self):
        """ RSET: assign string value in-place; right justified. """
        self.exec_lset(justify_right=True)

    def exec_option(self):
        """ OPTION BASE: set array indexing convention. """
        if util.skip_white_read_if(self.ins, ('BASE',)):
            # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
            d = util.skip_white_read(self.ins)
            if d == '0':
                var.base_array(0)
            elif d == '1':
                var.base_array(1)
            else:
                raise error.RunError(error.STX)
        else:
            raise error.RunError(error.STX)
        util.skip_to(self.ins, tk.end_statement)

    def exec_read(self):
        """ READ: read values from DATA statement. """
        # reading loop
        for name, indices in self._parse_var_list():
            entry = flow.read_entry()
            if name[-1] == '$':
                if self.ins == state.basic_state.bytecode:
                    address = state.basic_state.data_pos + memory.code_start
                else:
                    address = None
                value = state.basic_state.strings.store(entry, address)
            else:
                value = representation.str_to_number(entry, allow_nonnum=False)
                if value is None:
                    # set pointer for EDIT gadget to position in DATA statement
                    state.basic_state.bytecode.seek(state.basic_state.data_pos)
                    # syntax error in DATA line (not type mismatch!) if can't convert to var type
                    raise error.RunError(error.STX, state.basic_state.data_pos-1)
            var.set_variable(name, indices, value=value)
        util.require(self.ins, tk.end_statement)

    def _parse_prompt(self, question_mark):
        """ Helper function for INPUT: parse prompt definition. """
        # parse prompt
        if util.skip_white_read_if(self.ins, ('"',)):
            prompt = ''
            # only literal allowed, not a string expression
            d = self.ins.read(1)
            while d not in tk.end_line + ('"',)  :
                prompt += d
                d = self.ins.read(1)
            if d == '\0':
                self.ins.seek(-1, 1)
            following = util.skip_white_read(self.ins)
            if following == ';':
                prompt += question_mark
            elif following != ',':
                raise error.RunError(error.STX)
        else:
            prompt = question_mark
        return prompt

    def exec_input(self):
        """ INPUT: request input from user. """
        finp = expressions.parse_file_number(self.ins, 'IR')
        if finp is not None:
            for v in self._parse_var_list():
                value, _ = finp.read_var(v)
                var.set_variable(v[0], v[1], value)
        else:
            # ; to avoid echoing newline
            newline = not util.skip_white_read_if(self.ins, (';',))
            prompt = self._parse_prompt('? ')
            readvar = self._parse_var_list()
            # move the program pointer to the start of the statement to ensure correct behaviour for CONT
            pos = self.ins.tell()
            self.ins.seek(state.basic_state.current_statement)
            # read the input
            self.session.input_mode = True
            varlist = print_and_input.input_console(prompt, readvar, newline)
            self.session.input_mode = False
            for v in varlist:
                var.set_variable(*v)
            self.ins.seek(pos)
        util.require(self.ins, tk.end_statement)

    def exec_line_input(self):
        """ LINE INPUT: request input from user. """
        finp = expressions.parse_file_number(self.ins, 'IR')
        if not finp:
            # ; to avoid echoing newline
            newline = not util.skip_white_read_if(self.ins, (';',))
            # get prompt
            prompt = self._parse_prompt('')
        # get string variable
        readvar, indices = expressions.parse_variable(self.ins)
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
            console.write(prompt)
            line = console.wait_screenline(write_endl=newline)
            self.session.input_mode = False
        var.set_variable(readvar, indices, state.basic_state.strings.store(line))

    def exec_restore(self):
        """ RESTORE: reset DATA pointer. """
        if not util.skip_white(self.ins) in tk.end_statement:
            datanum = util.parse_jumpnum(self.ins, err=error.UNDEFINED_LINE_NUMBER)
        else:
            datanum = -1
        # undefined line number for all syntax errors
        util.require(self.ins, tk.end_statement, err=error.UNDEFINED_LINE_NUMBER)
        flow.restore(datanum)

    def exec_swap(self):
        """ SWAP: swap values of two variables. """
        name1, index1 = expressions.parse_variable(self.ins)
        util.require_read(self.ins, (',',))
        name2, index2 = expressions.parse_variable(self.ins)
        var.swap(name1, index1, name2, index2)
        # if syntax error. the swap has happened
        util.require(self.ins, tk.end_statement)

    def exec_def_fn(self):
        """ DEF FN: define a function. """
        fnname = util.parse_scalar(self.ins)
        fntype = fnname[-1]
        # read parameters
        fnvars = []
        util.skip_white(self.ins)
        pointer_loc = memory.code_start + self.ins.tell()
        if util.skip_white_read_if(self.ins, ('(',)):
            while True:
                fnvars.append(util.parse_scalar(self.ins))
                if util.skip_white(self.ins) in tk.end_statement + (')',):
                    break
                util.require_read(self.ins, (',',))
            util.require_read(self.ins, (')',))
        # read code
        fncode = ''
        util.require_read(self.ins, (tk.O_EQ,)) #=
        startloc = self.ins.tell()
        util.skip_to(self.ins, tk.end_statement)
        endloc = self.ins.tell()
        self.ins.seek(startloc)
        fncode = self.ins.read(endloc - startloc)
        if not state.basic_state.run_mode:
            # GW doesn't allow DEF FN in direct mode, neither do we
            # (for no good reason, works fine)
            raise error.RunError(error.ILLEGAL_DIRECT)
        state.basic_state.functions[fnname] = [fnvars, fncode]
        # update memory model
        # allocate function pointer
        pointer = vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(pointer_loc))
        pointer += '\0'*(vartypes.byte_size[fntype]-2)
        # function name is represented with first char shifted by 128
        var.set_scalar(chr(128+ord(fnname[0]))+fnname[1:], (fntype, bytearray(pointer)))
        for name in fnvars:
            # allocate but don't set variables
            var.set_scalar(name)


    def exec_randomize(self):
        """ RANDOMIZE: set random number generator seed. """
        val = expressions.parse_expression(self.ins, allow_empty=True)
        if val:
            # don't convert to int if provided in the code
            val = vartypes.pass_number(val)
        else:
            # prompt for random seed if not specified
            while not val:
                console.write("Random number seed (-32768 to 32767)? ")
                seed = console.wait_screenline()
                # seed entered on prompt is rounded to int
                val = representation.str_to_number(seed)
            val = vartypes.pass_integer(val)
        rnd.randomize(val)
        util.require(self.ins, tk.end_statement)

    ################################################
    # Console statements

    def exec_cls(self):
        """ CLS: clear the screen. """
        if (self.syntax == 'pcjr' or
                        util.skip_white(self.ins) in (',',) + tk.end_statement):
            if state.console_state.screen.drawing.view_is_set():
                val = 1
            elif state.console_state.view_set:
                val = 2
            else:
                val = 0
        else:
            val = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            if self.syntax == 'tandy':
                # tandy gives illegal function call on CLS number
                raise error.RunError(error.IFC)
        util.range_check(0, 2, val)
        if self.syntax != 'pcjr':
            if util.skip_white_read_if(self.ins, (',',)):
                # comma is ignored, but a number after means syntax error
                util.require(self.ins, tk.end_statement)
            else:
                util.require(self.ins, tk.end_statement, err=error.IFC)
        # cls is only executed if no errors have occurred
        if val == 0:
            console.clear()
            state.console_state.screen.drawing.reset()
        elif val == 1:
            state.console_state.screen.drawing.clear_view()
            state.console_state.screen.drawing.reset()
        elif val == 2:
            state.console_state.screen.clear_view()
        if self.syntax == 'pcjr':
            util.require(self.ins, tk.end_statement)

    def exec_color(self):
        """ COLOR: set colour attributes. """
        screen = state.console_state.screen
        mode = screen.mode
        fore = expressions.parse_expression(self.ins, allow_empty=True)
        if fore is None:
            fore = (screen.attr>>7)*0x10 + (screen.attr&0xf)
        else:
            fore = vartypes.pass_int_unpack(fore)
        back, bord = None, 0
        if util.skip_white_read_if(self.ins, (',')):
            back = expressions.parse_expression(self.ins, allow_empty=True)
            back = None if back is None else vartypes.pass_int_unpack(back)
            if util.skip_white_read_if(self.ins, (',')):
                bord = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        if back is None:
            # graphics mode bg is always 0; sets palette self.instead
            if mode.is_text_mode:
                back = (screen.attr>>4) & 0x7
            else:
                back = screen.palette.get_entry(0)
        if mode.name == '320x200x4':
            self.exec_color_mode_1(fore, back, bord)
            util.require(self.ins, tk.end_statement)
            return
        elif mode.name in ('640x200x2', '720x348x2'):
            # screen 2; hercules: illegal fn call
            raise error.RunError(error.IFC)
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
        util.require(self.ins, tk.end_statement)

    def exec_color_mode_1(self, back, pal, override):
        """ Helper function for COLOR in SCREEN 1. """
        screen = state.console_state.screen
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

    def exec_palette(self):
        """ PALETTE: set colour palette entry. """
        d = util.skip_white(self.ins)
        if d in tk.end_statement:
            # reset palette
            state.console_state.screen.palette.set_all(state.console_state.screen.mode.palette)
        elif d == tk.USING:
            self.ins.read(1)
            self.exec_palette_using()
        else:
            # can't set blinking colours separately
            mode = state.console_state.screen.mode
            num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
            attrib = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            util.require_read(self.ins, (',',))
            colour = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            if attrib is None or colour is None:
                raise error.RunError(error.STX)
            util.range_check(0, num_palette_entries-1, attrib)
            util.range_check(-1, len(mode.colours)-1, colour)
            if colour != -1:
                state.console_state.screen.palette.set_entry(attrib, colour)
            util.require(self.ins, tk.end_statement)

    def exec_palette_using(self):
        """ PALETTE USING: set full colour palette. """
        screen = state.console_state.screen
        mode = screen.mode
        num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
        array_name, start_indices = expressions.parse_variable(self.ins)
        try:
            dimensions, lst, _ = state.basic_state.arrays[array_name]
        except KeyError:
            raise error.RunError(error.IFC)
        if array_name[-1] != '%':
            raise error.RunError(error.TYPE_MISMATCH)
        start = var.index_array(start_indices, dimensions)
        if var.array_len(dimensions) - start < num_palette_entries:
            raise error.RunError(error.IFC)
        new_palette = []
        for i in range(num_palette_entries):
            val = vartypes.pass_int_unpack(('%', lst[(start+i)*2:(start+i+1)*2]))
            util.range_check(-1, len(mode.colours)-1, val)
            new_palette.append(val if val > -1 else screen.palette.get_entry(i))
        screen.palette.set_all(new_palette)
        util.require(self.ins, tk.end_statement)

    def exec_key(self):
        """ KEY: switch on/off or list function-key row on screen. """
        d = util.skip_white_read(self.ins)
        if d == tk.ON:
            # tandy can have VIEW PRINT 1 to 25, should raise IFC in that case
            if state.console_state.scroll_height == 25:
                raise error.RunError(error.IFC)
            if not state.console_state.keys_visible:
                console.show_keys(True)
        elif d == tk.OFF:
            if state.console_state.keys_visible:
                console.show_keys(False)
        elif d == tk.LIST:
            console.list_keys()
        elif d == '(':
            # key (n)
            self.ins.seek(-1, 1)
            self.exec_key_events()
        else:
            # key n, "TEXT"
            self.ins.seek(-len(d), 1)
            self.exec_key_define()
        util.require(self.ins, tk.end_statement)

    def exec_key_define(self):
        """ KEY: define function-key shortcut or scancode for event trapping. """
        keynum = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(1, 255, keynum)
        util.require_read(self.ins, (',',), err=error.IFC)
        with state.basic_state.strings:
            text = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        if keynum <= events.num_fn_keys:
            # macro starting with NUL is empty macro
            if text and str(text)[0] == '\0':
                text = ''
            state.console_state.key_replace[keynum-1] = str(text)
            if state.console_state.keys_visible:
                console.show_keys(True)
        else:
            # only length-2 expressions can be assigned to KEYs over 10
            # in which case it's a key scancode definition
            if len(text) != 2:
                raise error.RunError(error.IFC)
            state.basic_state.events.key[keynum-1].set_trigger(str(text))

    def exec_locate(self):
        """ LOCATE: Set cursor position, shape and visibility."""
        cmode = state.console_state.screen.mode
        row = expressions.parse_expression(self.ins, allow_empty=True)
        row = None if row is None else vartypes.pass_int_unpack(row)
        col, cursor, start, stop = None, None, None, None
        if util.skip_white_read_if(self.ins, (',',)):
            col = expressions.parse_expression(self.ins, allow_empty=True)
            col = None if col is None else vartypes.pass_int_unpack(col)
            if util.skip_white_read_if(self.ins, (',',)):
                cursor = expressions.parse_expression(self.ins, allow_empty=True)
                cursor = None if cursor is None else vartypes.pass_int_unpack(cursor)
                if util.skip_white_read_if(self.ins, (',',)):
                    start = expressions.parse_expression(self.ins, allow_empty=True)
                    start = None if start is None else vartypes.pass_int_unpack(start)
                    if util.skip_white_read_if(self.ins, (',',)):
                        stop = expressions.parse_expression(self.ins, allow_empty=True)
                        stop = None if stop is None else vartypes.pass_int_unpack(stop)
                        if util.skip_white_read_if(self.ins, (',',)):
                            # can end on a 5th comma but no stuff allowed after it
                            pass
        row = state.console_state.row if row is None else row
        col = state.console_state.col if col is None else col
        if row == cmode.height and state.console_state.keys_visible:
            raise error.RunError(error.IFC)
        elif state.console_state.view_set:
            util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
        else:
            util.range_check(1, cmode.height, row)
        util.range_check(1, cmode.width, col)
        if row == cmode.height:
            # temporarily allow writing on last row
            state.console_state.bottom_row_allowed = True
        console.set_pos(row, col, scroll_ok=False)
        if cursor is not None:
            util.range_check(0, (255 if self.syntax in ('pcjr', 'tandy') else 1), cursor)
            # set cursor visibility - this should set the flag but have no effect in graphics modes
            state.console_state.screen.cursor.set_visibility(cursor != 0)
        if stop is None:
            stop = start
        if start is not None:
            util.range_check(0, 31, start, stop)
            # cursor shape only has an effect in text mode
            if cmode.is_text_mode:
                state.console_state.screen.cursor.set_shape(start, stop)
        util.require(self.ins, tk.end_statement)

    def exec_write(self, output=None):
        """ WRITE: Output machine-readable expressions to the screen or a file. """
        output = expressions.parse_file_number(self.ins, 'OAR')
        output = state.io_state.scrn_file if output is None else output
        expr = expressions.parse_expression(self.ins, allow_empty=True)
        outstr = ''
        if expr:
            while True:
                if expr[0] == '$':
                    with state.basic_state.strings:
                        outstr += '"' + var.copy_str(expr) + '"'
                else:
                    outstr += representation.number_to_str(expr, screen=True, write=True)
                if util.skip_white_read_if(self.ins, (',', ';')):
                    outstr += ','
                else:
                    break
                expr = expressions.parse_expression(self.ins)
        util.require(self.ins, tk.end_statement)
        # write the whole thing as one thing (this affects line breaks)
        output.write_line(outstr)

    def exec_print(self, output=None):
        """ PRINT: Write expressions to the screen or a file. """
        if output is None:
            output = expressions.parse_file_number(self.ins, 'OAR')
            output = state.io_state.scrn_file if output is None else output
        number_zones = max(1, int(output.width/14))
        newline = True
        while True:
            d = util.skip_white(self.ins)
            if d in tk.end_statement + (tk.USING,):
                break
            elif d in (',', ';', tk.SPC, tk.TAB):
                self.ins.read(1)
                newline = False
                if d == ',':
                    next_zone = int((output.col-1)/14)+1
                    if next_zone >= number_zones and output.width >= 14 and output.width != 255:
                        output.write_line()
                    else:
                        output.write(' '*(1+14*next_zone-output.col))
                elif d == tk.SPC:
                    numspaces = max(0, vartypes.pass_int_unpack(expressions.parse_expression(self.ins), 0xffff)) % output.width
                    util.require_read(self.ins, (')',))
                    output.write(' ' * numspaces)
                elif d == tk.TAB:
                    pos = max(0, vartypes.pass_int_unpack(expressions.parse_expression(self.ins), 0xffff) - 1) % output.width + 1
                    util.require_read(self.ins, (')',))
                    if pos < output.col:
                        output.write_line()
                        output.write(' '*(pos-1))
                    else:
                        output.write(' '*(pos-output.col))
            else:
                newline = True
                with state.basic_state.strings:
                    expr = expressions.parse_expression(self.ins)
                    # numbers always followed by a space
                    if expr[0] in ('%', '!', '#'):
                        word = representation.number_to_str(expr, screen=True) + ' '
                    else:
                        word = var.copy_str(expr)
                # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
                output.write(word)
        if util.skip_white_read_if(self.ins, (tk.USING,)):
            return self.exec_print_using(output)
        if newline:
            if output == state.io_state.scrn_file and state.console_state.overflow:
                output.write_line()
            output.write_line()
        util.require(self.ins, tk.end_statement)

    def exec_print_using(self, output):
        """ PRINT USING: Write expressions to screen or file using a formatting string. """
        with state.basic_state.strings:
            format_expr = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
        if format_expr == '':
            raise error.RunError(error.IFC)
        util.require_read(self.ins, (';',))
        fors = StringIO(format_expr)
        semicolon, format_chars = False, False
        while True:
            data_ends = util.skip_white(self.ins) in tk.end_statement
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
                        with state.basic_state.strings:
                            s = var.copy_str(vartypes.pass_string(expressions.parse_expression(self.ins)))
                        if string_field == '&':
                            output.write(s)
                        else:
                            output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
                else:
                    number_field, digits_before, decimals = print_and_input.get_number_tokens(fors)
                    if number_field:
                        if not data_ends:
                            num = vartypes.pass_float(expressions.parse_expression(self.ins))
                            output.write(representation.format_number(num, number_field, digits_before, decimals))
                    else:
                        output.write(fors.read(1))
                if string_field or number_field:
                    format_chars = True
                    semicolon = util.skip_white_read_if(self.ins, (';', ','))
        if not semicolon:
            output.write_line()
        util.require(self.ins, tk.end_statement)

    def exec_lprint(self):
        """ LPRINT: Write expressions to printer LPT1. """
        self.exec_print(state.io_state.lpt1_file)

    def exec_view_print(self):
        """ VIEW PRINT: set scroll region. """
        if util.skip_white(self.ins) in tk.end_statement:
            state.console_state.screen.unset_view()
        else:
            start = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            util.require_read(self.ins, (tk.TO,))
            stop = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            util.require(self.ins, tk.end_statement)
            max_line = 25 if (self.syntax in ('pcjr', 'tandy') and not state.console_state.keys_visible) else 24
            util.range_check(1, max_line, start, stop)
            state.console_state.screen.set_view(start, stop)

    def exec_width(self):
        """ WIDTH: set width of screen or device. """
        d = util.skip_white(self.ins)
        if d == '#':
            dev = expressions.parse_file_number(self.ins)
            w = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        elif d == tk.LPRINT:
            self.ins.read(1)
            dev = state.io_state.lpt1_file
            w = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        else:
            # we can do calculations, but they must be bracketed...
            if d in tk.number:
                expr = expressions.parse_literal(self.ins)
            else:
                expr = expressions.parse_expression(self.ins)
            if expr[0] == '$':
                with state.basic_state.strings:
                    devname = var.copy_str(vartypes.pass_string(expr)).upper()
                try:
                    dev = state.io_state.devices[devname].device_file
                except (KeyError, AttributeError):
                    # bad file name
                    raise error.RunError(error.BAD_FILE_NAME)
                util.require_read(self.ins, (',',))
                w = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
            else:
                dev = state.io_state.scrn_file
                w = vartypes.pass_int_unpack(expr)
                if util.skip_white_read_if(self.ins, (',',)):
                    # pare dummy number rows setting
                    num_rows_dummy = expressions.parse_expression(self.ins, allow_empty=True)
                    if num_rows_dummy is not None:
                        min_num_rows = 0 if self.syntax in ('pcjr', 'tandy') else 25
                        util.range_check(min_num_rows, 25, vartypes.pass_int_unpack(num_rows_dummy))
                    # trailing comma is accepted
                    util.skip_white_read_if(self.ins, (',',))
                # gives illegal function call, not syntax error
            util.require(self.ins, tk.end_statement, err=error.IFC)
        util.require(self.ins, tk.end_statement)
        dev.set_width(w)

    def exec_screen(self):
        """ SCREEN: change video mode or page. """
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        mode = expressions.parse_expression(self.ins, allow_empty=True)
        mode = None if mode is None else vartypes.pass_int_unpack(mode)
        color, apagenum, vpagenum, erase = None, None, None, 1
        if util.skip_white_read_if(self.ins, (',',)):
            color = expressions.parse_expression(self.ins, allow_empty=True)
            color = None if color is None else vartypes.pass_int_unpack(color)
            if util.skip_white_read_if(self.ins, (',',)):
                apagenum = expressions.parse_expression(self.ins, allow_empty=True)
                apagenum = None if apagenum is None else vartypes.pass_int_unpack(apagenum)
                if util.skip_white_read_if(self.ins, (',',)):
                    vpagenum = expressions.parse_expression(self.ins,
                                allow_empty=self.syntax in ('pcjr', 'tandy'))
                    vpagenum = None if vpagenum is None else vartypes.pass_int_unpack(vpagenum)
                    if self.syntax in ('pcjr', 'tandy') and util.skip_white_read_if(self.ins, (',',)):
                        erase = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        # if any parameter not in [0,255], error 5 without doing anything
        # if the parameters are outside narrow ranges
        # (e.g. not implemented screen mode, pagenum beyond max)
        # then the error is only raised after changing the palette.
        util.range_check(0, 255, mode, color, apagenum, vpagenum)
        util.range_check(0, 2, erase)
        util.require(self.ins, tk.end_statement)
        # decide whether to redraw the screen
        screen = state.console_state.screen
        oldmode, oldcolor = screen.mode, screen.colorswitch
        screen.screen(mode, color, apagenum, vpagenum, erase)
        if ((not screen.mode.is_text_mode and screen.mode.name != oldmode.name) or
                (screen.mode.is_text_mode and not oldmode.is_text_mode) or
                (screen.mode.width != oldmode.width) or
                (screen.colorswitch != oldcolor)):
            # rebuild the console if we've switched modes or colorswitch
            console.init_mode()

    def exec_pcopy(self):
        """ PCOPY: copy video pages. """
        src = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.range_check(0, state.console_state.screen.mode.num_pages-1, src)
        util.require_read(self.ins, (',',))
        dst = vartypes.pass_int_unpack(expressions.parse_expression(self.ins))
        util.require(self.ins, tk.end_statement)
        util.range_check(0, state.console_state.screen.mode.num_pages-1, dst)
        state.console_state.screen.copy_page(src, dst)

    statements = {
        tk.END: exec_end,
        tk.FOR: exec_for,
        tk.NEXT: exec_next,
        tk.DATA: exec_data,
        tk.INPUT: exec_input,
        tk.DIM: exec_dim,
        tk.READ: exec_read,
        tk.LET: exec_let,
        tk.GOTO: exec_goto,
        tk.RUN: exec_run,
        tk.IF: exec_if,
        tk.RESTORE: exec_restore,
        tk.GOSUB: exec_gosub,
        tk.RETURN: exec_return,
        tk.REM: exec_rem,
        tk.STOP: exec_stop,
        tk.PRINT: exec_print,
        tk.CLEAR: exec_clear,
        tk.LIST: exec_list,
        tk.NEW: exec_new,
        tk.ON: exec_on,
        tk.WAIT: exec_wait,
        tk.DEF: exec_def,
        tk.POKE: exec_poke,
        tk.CONT: exec_cont,
        tk.OUT: exec_out,
        tk.LPRINT: exec_lprint,
        tk.LLIST: exec_llist,
        tk.WIDTH: exec_width,
        tk.ELSE: exec_else,
        tk.TRON: exec_tron,
        tk.TROFF: exec_troff,
        tk.SWAP: exec_swap,
        tk.ERASE: exec_erase,
        tk.EDIT: exec_edit,
        tk.ERROR: exec_error,
        tk.RESUME: exec_resume,
        tk.DELETE: exec_delete,
        tk.AUTO: exec_auto,
        tk.RENUM: exec_renum,
        tk.DEFSTR: exec_defstr,
        tk.DEFINT: exec_defint,
        tk.DEFSNG: exec_defsng,
        tk.DEFDBL: exec_defdbl,
        tk.LINE: exec_line,
        tk.WHILE: exec_while,
        tk.WEND: exec_wend,
        tk.CALL: exec_call,
        tk.WRITE: exec_write,
        tk.OPTION: exec_option,
        tk.RANDOMIZE: exec_randomize,
        tk.OPEN: exec_open,
        tk.CLOSE: exec_close,
        tk.LOAD: exec_load,
        tk.MERGE: exec_merge,
        tk.SAVE: exec_save,
        tk.COLOR: exec_color,
        tk.CLS: exec_cls,
        tk.MOTOR: exec_motor,
        tk.BSAVE: exec_bsave,
        tk.BLOAD: exec_bload,
        tk.SOUND: exec_sound,
        tk.BEEP: exec_beep,
        tk.PSET: exec_pset,
        tk.PRESET: exec_preset,
        tk.SCREEN: exec_screen,
        tk.KEY: exec_key,
        tk.LOCATE: exec_locate,
        tk.FILES: exec_files,
        tk.FIELD: exec_field,
        tk.SYSTEM: exec_system,
        tk.NAME: exec_name,
        tk.LSET: exec_lset,
        tk.RSET: exec_rset,
        tk.KILL: exec_kill,
        tk.PUT: exec_put,
        tk.GET: exec_get,
        tk.RESET: exec_reset,
        tk.COMMON: exec_common,
        tk.CHAIN: exec_chain,
        tk.DATE: exec_date,
        tk.TIME: exec_time,
        tk.PAINT: exec_paint,
        tk.COM: exec_com,
        tk.CIRCLE: exec_circle,
        tk.DRAW: exec_draw,
        tk.PLAY: exec_play,
        tk.TIMER: exec_timer,
        tk.IOCTL: exec_ioctl,
        tk.CHDIR: exec_chdir,
        tk.MKDIR: exec_mkdir,
        tk.RMDIR: exec_rmdir,
        tk.SHELL: exec_shell,
        tk.ENVIRON: exec_environ,
        tk.VIEW: exec_view,
        tk.WINDOW: exec_window,
        tk.PALETTE: exec_palette,
        tk.LCOPY: exec_lcopy,
        tk.CALLS: exec_calls,
        tk.NOISE: exec_noise,
        tk.PCOPY: exec_pcopy,
        tk.TERM: exec_term,
        tk.LOCK: exec_lock,
        tk.UNLOCK: exec_unlock,
        tk.MID: exec_mid,
        tk.PEN: exec_pen,
        tk.STRIG: exec_strig,
        tk.DEBUG: exec_debug,
    }
