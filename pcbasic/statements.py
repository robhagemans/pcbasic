"""
PC-BASIC - statements.py
Statement parser

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
from functools import partial
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import string

import plat
import config
# for num_fn_keys
import backend
import console
import debug
import disk
import error
import expressions
import flow
import fp
import graphics
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

def prepare():
    """ Initialise statements module. """
    global pcjr_syntax, pcjr_term
    if config.get('syntax') in ('pcjr', 'tandy'):
        pcjr_syntax = config.get('syntax')
    else:
        pcjr_syntax = None
    # find program for PCjr TERM command
    pcjr_term = config.get('pcjr-term')
    if pcjr_term and not os.path.exists(pcjr_term):
        pcjr_term = os.path.join(plat.info_dir, pcjr_term)
    if not os.path.exists(pcjr_term):
        pcjr_term = ''
    state.basic_state.edit_prompt = False

def parse_statement():
    """ Parse one statement at the current pointer in current codestream.
        Return False if stream has ended, True otherwise.
        """
    try:
        ins = flow.get_codestream()
        state.basic_state.current_statement = ins.tell()
        c = util.skip_white(ins).upper()
        if c == '':
            # stream has ended.
            return False
        # parse line number or : at start of statement
        elif c == '\0':
            # save position for error message
            prepos = ins.tell()
            ins.read(1)
            # line number marker, new statement
            linenum = util.parse_line_number(ins)
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
            ins.read(1)
        c = util.skip_white(ins).upper()
        # empty statement, return to parse next
        if c in tk.end_statement:
            return True
        # implicit LET
        elif c in string.ascii_uppercase:
            exec_let(ins)
        # token
        else:
            ins.read(1)
            if   c == tk.END:       exec_end(ins)
            elif c == tk.FOR:       exec_for(ins)
            elif c == tk.NEXT:      exec_next(ins)
            elif c == tk.DATA:      exec_data(ins)
            elif c == tk.INPUT:     exec_input(ins)
            elif c == tk.DIM:       exec_dim(ins)
            elif c == tk.READ:      exec_read(ins)
            elif c == tk.LET:       exec_let(ins)
            elif c == tk.GOTO:      exec_goto(ins)
            elif c == tk.RUN:       exec_run(ins)
            elif c == tk.IF:        exec_if(ins)
            elif c == tk.RESTORE:   exec_restore(ins)
            elif c == tk.GOSUB:     exec_gosub(ins)
            elif c == tk.RETURN:    exec_return(ins)
            elif c == tk.REM:       exec_rem(ins)
            elif c == tk.STOP:      exec_stop(ins)
            elif c == tk.PRINT:     exec_print(ins)
            elif c == tk.CLEAR:     exec_clear(ins)
            elif c == tk.LIST:      exec_list(ins)
            elif c == tk.NEW:       exec_new(ins)
            elif c == tk.ON:        exec_on(ins)
            elif c == tk.WAIT:      exec_wait(ins)
            elif c == tk.DEF:       exec_def(ins)
            elif c == tk.POKE:      exec_poke(ins)
            elif c == tk.CONT:      exec_cont(ins)
            elif c == tk.OUT:       exec_out(ins)
            elif c == tk.LPRINT:    exec_lprint(ins)
            elif c == tk.LLIST:     exec_llist(ins)
            elif c == tk.WIDTH:     exec_width(ins)
            elif c == tk.ELSE:      exec_else(ins)
            elif c == tk.TRON:      exec_tron(ins)
            elif c == tk.TROFF:     exec_troff(ins)
            elif c == tk.SWAP:      exec_swap(ins)
            elif c == tk.ERASE:     exec_erase(ins)
            elif c == tk.EDIT:      exec_edit(ins)
            elif c == tk.ERROR:     exec_error(ins)
            elif c == tk.RESUME:    exec_resume(ins)
            elif c == tk.DELETE:    exec_delete(ins)
            elif c == tk.AUTO:      exec_auto(ins)
            elif c == tk.RENUM:     exec_renum(ins)
            elif c == tk.DEFSTR:    exec_defstr(ins)
            elif c == tk.DEFINT:    exec_defint(ins)
            elif c == tk.DEFSNG:    exec_defsng(ins)
            elif c == tk.DEFDBL:    exec_defdbl(ins)
            elif c == tk.LINE:      exec_line(ins)
            elif c == tk.WHILE:     exec_while(ins)
            elif c == tk.WEND:      exec_wend(ins)
            elif c == tk.CALL:      exec_call(ins)
            elif c == tk.WRITE:     exec_write(ins)
            elif c == tk.OPTION:    exec_option(ins)
            elif c == tk.RANDOMIZE: exec_randomize(ins)
            elif c == tk.OPEN:      exec_open(ins)
            elif c == tk.CLOSE:     exec_close(ins)
            elif c == tk.LOAD:      exec_load(ins)
            elif c == tk.MERGE:     exec_merge(ins)
            elif c == tk.SAVE:      exec_save(ins)
            elif c == tk.COLOR:     exec_color(ins)
            elif c == tk.CLS:       exec_cls(ins)
            elif c == tk.MOTOR:     exec_motor(ins)
            elif c == tk.BSAVE:     exec_bsave(ins)
            elif c == tk.BLOAD:     exec_bload(ins)
            elif c == tk.SOUND:     exec_sound(ins)
            elif c == tk.BEEP:      exec_beep(ins)
            elif c == tk.PSET:      exec_pset(ins)
            elif c == tk.PRESET:    exec_preset(ins)
            elif c == tk.SCREEN:    exec_screen(ins)
            elif c == tk.KEY:       exec_key(ins)
            elif c == tk.LOCATE:    exec_locate(ins)
            # two-byte tokens
            elif c == '\xFD':
                ins.read(1)
                # syntax error; these are all expression tokens, not statement tokens.
                raise error.RunError(error.STX)
            # two-byte tokens
            elif c == '\xFE':
                c += ins.read(1)
                if   c == tk.FILES:   exec_files(ins)
                elif c == tk.FIELD:   exec_field(ins)
                elif c == tk.SYSTEM:  exec_system(ins)
                elif c == tk.NAME:    exec_name(ins)
                elif c == tk.LSET:    exec_lset(ins)
                elif c == tk.RSET:    exec_rset(ins)
                elif c == tk.KILL:    exec_kill(ins)
                elif c == tk.PUT:     exec_put(ins)
                elif c == tk.GET:     exec_get(ins)
                elif c == tk.RESET:   exec_reset(ins)
                elif c == tk.COMMON:  exec_common(ins)
                elif c == tk.CHAIN:   exec_chain(ins)
                elif c == tk.DATE:    exec_date(ins)
                elif c == tk.TIME:    exec_time(ins)
                elif c == tk.PAINT:   exec_paint(ins)
                elif c == tk.COM:     exec_com(ins)
                elif c == tk.CIRCLE:  exec_circle(ins)
                elif c == tk.DRAW:    exec_draw(ins)
                elif c == tk.PLAY:    exec_play(ins)
                elif c == tk.TIMER:   exec_timer(ins)
                elif c == tk.IOCTL:   exec_ioctl(ins)
                elif c == tk.CHDIR:   exec_chdir(ins)
                elif c == tk.MKDIR:   exec_mkdir(ins)
                elif c == tk.RMDIR:   exec_rmdir(ins)
                elif c == tk.SHELL:   exec_shell(ins)
                elif c == tk.ENVIRON: exec_environ(ins)
                elif c == tk.VIEW:    exec_view(ins)
                elif c == tk.WINDOW:  exec_window(ins)
                elif c == tk.PALETTE: exec_palette(ins)
                elif c == tk.LCOPY:   exec_lcopy(ins)
                elif c == tk.CALLS:   exec_calls(ins)
                elif c == tk.NOISE:   exec_noise(ins)
                elif c == tk.PCOPY:   exec_pcopy(ins)
                elif c == tk.TERM:    exec_term(ins)
                elif c == tk.LOCK:    exec_lock(ins)
                elif c == tk.UNLOCK:  exec_unlock(ins)
                else: raise error.RunError(error.STX)
            # two-byte tokens
            elif c == '\xFF':
                c += ins.read(1)
                if   c == tk.MID:    exec_mid(ins)
                elif c == tk.PEN:    exec_pen(ins)
                elif c == tk.STRIG:  exec_strig(ins)
                elif c == tk.DEBUG:  exec_debug(ins)
                else: raise error.RunError(error.STX)
            else:
                raise error.RunError(error.STX)
        return True
    except error.RunError as e:
        error.set_err(e)
        # don't jump if we're already busy handling an error
        if state.basic_state.on_error is not None and state.basic_state.on_error != 0 and not state.basic_state.error_handle_mode:
            state.basic_state.error_resume = state.basic_state.current_statement, state.basic_state.run_mode
            flow.jump(state.basic_state.on_error)
            state.basic_state.error_handle_mode = True
            state.basic_state.events.suspend_all = True
            return True
        else:
            raise e

#################################################################
#################################################################

def exec_system(ins):
    """ SYSTEM: exit interpreter. """
    # SYSTEM LAH does not execute
    util.require(ins, tk.end_statement)
    raise error.Exit()

def exec_tron(ins):
    """ TRON: turn on line number tracing. """
    state.basic_state.tron = True
    # TRON LAH gives error, but TRON has been executed
    util.require(ins, tk.end_statement)

def exec_troff(ins):
    """ TROFF: turn off line number tracing. """
    state.basic_state.tron = False
    util.require(ins, tk.end_statement)

def exec_rem(ins):
    """ REM: comment. """
    # skip the rest of the line, but parse numbers to avoid triggering EOL
    util.skip_to(ins, tk.end_line)

def exec_lcopy(ins):
    """ LCOPY: do nothing but check for syntax errors. """
    # See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY
    if util.skip_white(ins) not in tk.end_statement:
        util.range_check(0, 255, vartypes.pass_int_unpack(expressions.parse_expression(ins)))
        util.require(ins, tk.end_statement)

def exec_motor(ins):
    """ MOTOR: do nothing but check for syntax errors. """
    exec_lcopy(ins)

def exec_debug(ins):
    """ DEBUG: execute Python command. """
    # this is not a GW-BASIC behaviour, but helps debugging.
    # this is parsed like a REM by the tokeniser.
    # rest of the line is considered to be a python statement
    util.skip_white(ins)
    debug_cmd = ''
    while util.peek(ins) not in tk.end_line:
        debug_cmd += ins.read(1)
    debug.debug_exec(debug_cmd)

def exec_term(ins):
    """ TERM: load and run PCjr buitin terminal emulator program. """
    try:
        util.require(ins, tk.end_statement)
        print pcjr_term
        with disk.open_diskfile(open(pcjr_term, 'rb'), 'A', 'I', 'TERM') as f:
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

def exec_def(ins):
    """ DEF: select DEF FN, DEF USR, DEF SEG. """
    c = util.skip_white(ins)
    if util.read_if(ins, c, (tk.FN,)):
        exec_def_fn(ins)
    elif util.read_if(ins, c, (tk.USR,)):
        exec_def_usr(ins)
    elif util.skip_white_read_if(ins, ('SEG',)):
        exec_def_seg(ins)
    else:
        raise error.RunError(error.STX)

def exec_view(ins):
    """ VIEW: select VIEW PRINT, VIEW (graphics). """
    if util.skip_white_read_if(ins, (tk.PRINT,)):
        exec_view_print(ins)
    else:
        exec_view_graph(ins)

def exec_line(ins):
    """ LINE: select LINE INPUT, LINE (graphics). """
    if util.skip_white_read_if(ins, (tk.INPUT,)):
        exec_line_input(ins)
    else:
        exec_line_graph(ins)

def exec_get(ins):
    """ GET: select GET (graphics), GET (files). """
    if util.skip_white(ins) == '(':
        exec_get_graph(ins)
    else:
        exec_get_file(ins)

def exec_put(ins):
    """ PUT: select PUT (graphics), PUT (files). """
    if util.skip_white(ins) == '(':
        exec_put_graph(ins)
    else:
        exec_put_file(ins)

def exec_on(ins):
    """ ON: select ON ERROR, ON KEY, ON TIMER, ON PLAY, ON COM, ON PEN, ON STRIG
        or ON (jump statement). """
    c = util.skip_white(ins)
    if util.read_if(ins, c, (tk.ERROR,)):
        exec_on_error(ins)
    elif util.read_if(ins, c, (tk.KEY,)):
        exec_on_key(ins)
    elif c in ('\xFE', '\xFF'):
        c = util.peek(ins, 2)
        if util.read_if(ins, c, (tk.TIMER,)):
            exec_on_timer(ins)
        elif util.read_if(ins, c, (tk.PLAY,)):
            exec_on_play(ins)
        elif util.read_if(ins, c, (tk.COM,)):
            exec_on_com(ins)
        elif util.read_if(ins, c, (tk.PEN,)):
            exec_on_pen(ins)
        elif util.read_if(ins, c, (tk.STRIG,)):
            exec_on_strig(ins)
        else:
            exec_on_jump(ins)
    else:
        exec_on_jump(ins)

##########################################################
# event switches (except PLAY) and event definitions

def exec_pen(ins):
    """ PEN: switch on/off light pen event handling. """
    if state.basic_state.events.pen.command(util.skip_white(ins)):
        ins.read(1)
    else:
        raise error.RunError(error.STX)
    util.require(ins, tk.end_statement)

def exec_strig(ins):
    """ STRIG: switch on/off fire button event handling. """
    d = util.skip_white(ins)
    if d == '(':
        # strig (n)
        num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        if num not in (0,2,4,6):
            raise error.RunError(error.IFC)
        if state.basic_state.events.strig[num//2].command(util.skip_white(ins)):
            ins.read(1)
        else:
            raise error.RunError(error.STX)
    elif d == tk.ON:
        ins.read(1)
        state.console_state.stick.switch(True)
    elif d == tk.OFF:
        ins.read(1)
        state.console_state.stick.switch(False)
    else:
        raise error.RunError(error.STX)
    util.require(ins, tk.end_statement)

def exec_com(ins):
    """ COM: switch on/off serial port event handling. """
    util.require(ins, ('(',))
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(1, 2, num)
    if state.basic_state.events.com[num].command(util.skip_white(ins)):
        ins.read(1)
    else:
        raise error.RunError(error.STX)
    util.require(ins, tk.end_statement)

def exec_timer(ins):
    """ TIMER: switch on/off timer event handling. """
    if state.basic_state.events.timer.command(util.skip_white(ins)):
        ins.read(1)
    else:
        raise error.RunError(error.STX)
    util.require(ins, tk.end_statement)

def exec_key_events(ins):
    """ KEY: switch on/off keyboard events. """
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(0, 255, num)
    d = util.skip_white(ins)
    # others are ignored
    if num >= 1 and num <= 20:
        if state.basic_state.events.key[num-1].command(d):
            ins.read(1)
        else:
            raise error.RunError(error.STX)

def parse_on_event(ins, bracket=True):
    """ Helper function for ON event trap definitions. """
    num = None
    if bracket:
        num = expressions.parse_bracket(ins)
    util.require_read(ins, (tk.GOSUB,))
    jumpnum = util.parse_jumpnum(ins)
    if jumpnum == 0:
        jumpnum = None
    elif jumpnum not in state.basic_state.line_numbers:
        raise error.RunError(error.UNDEFINED_LINE_NUMBER)
    util.require(ins, tk.end_statement)
    return num, jumpnum

def exec_on_key(ins):
    """ ON KEY: define key event trapping. """
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 20, keynum)
    state.basic_state.events.key[keynum-1].set_jump(jumpnum)

def exec_on_timer(ins):
    """ ON TIMER: define timer event trapping. """
    timeval, jumpnum = parse_on_event(ins)
    timeval = vartypes.pass_single_keep(timeval)
    period = fp.mul(fp.unpack(timeval), fp.Single.from_int(1000)).round_to_int()
    state.basic_state.events.timer.set_trigger(period)
    state.basic_state.events.timer.set_jump(jumpnum)

def exec_on_play(ins):
    """ ON PLAY: define music event trapping. """
    playval, jumpnum = parse_on_event(ins)
    playval = vartypes.pass_int_unpack(playval)
    state.basic_state.events.play.set_trigger(playval)
    state.basic_state.events.play.set_jump(jumpnum)

def exec_on_pen(ins):
    """ ON PEN: define light pen event trapping. """
    _, jumpnum = parse_on_event(ins, bracket=False)
    state.basic_state.events.pen.set_jump(jumpnum)

def exec_on_strig(ins):
    """ ON STRIG: define fire button event trapping. """
    strigval, jumpnum = parse_on_event(ins)
    strigval = vartypes.pass_int_unpack(strigval)
    ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
    if strigval not in (0,2,4,6):
        raise error.RunError(error.IFC)
    state.basic_state.events.strig[strigval//2].set_jump(jumpnum)

def exec_on_com(ins):
    """ ON COM: define serial port event trapping. """
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 2, keynum)
    state.basic_state.events.com[keynum-1].set_jump(jumpnum)

##########################################################
# sound

def exec_beep(ins):
    """ BEEP: produce an alert sound or switch internal speaker on/off. """
    # Tandy/PCjr BEEP ON, OFF
    if pcjr_syntax and util.skip_white(ins) in (tk.ON, tk.OFF):
        state.console_state.beep_on = (ins.read(1) == tk.ON)
        util.require(ins, tk.end_statement)
        return
    state.console_state.sound.beep()
    # if a syntax error happens, we still beeped.
    util.require(ins, tk.end_statement)
    if state.console_state.sound.foreground:
        state.console_state.sound.wait_music()

def exec_sound(ins):
    """ SOUND: produce an arbitrary sound or switch external speaker on/off. """
    # Tandy/PCjr SOUND ON, OFF
    if pcjr_syntax and util.skip_white(ins) in (tk.ON, tk.OFF):
        state.console_state.sound.sound_on = (ins.read(1) == tk.ON)
        util.require(ins, tk.end_statement)
        return
    freq = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(error.IFC)
    # only look for args 3 and 4 if duration is > 0; otherwise those args are a syntax error (on tandy)
    if dur.gt(fp.Single.zero):
        if (util.skip_white_read_if(ins, (',',)) and (pcjr_syntax == 'tandy' or
                (pcjr_syntax == 'pcjr' and state.console_state.sound.sound_on))):
            volume = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            util.range_check(0, 15, volume)
            if util.skip_white_read_if(ins, (',',)):
                voice = vartypes.pass_int_unpack(expressions.parse_expression(ins))
                util.range_check(0, 2, voice) # can't address noise channel here
            else:
                voice = 0
        else:
            volume, voice = 15, 0
    util.require(ins, tk.end_statement)
    if dur.is_zero():
        state.console_state.sound.stop_all_sound()
        return
    # Tandy only allows frequencies below 37 (but plays them as 110 Hz)
    if freq != 0:
        util.range_check(-32768 if sound.pcjr_sound == 'tandy' else 37, 32767, freq) # 32767 is pause
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

def exec_play(ins):
    """ PLAY: play sound sequence defined by a Music Macro Language string. """
    # PLAY: event switch
    if state.basic_state.events.play.command(util.skip_white(ins)):
        ins.read(1)
        util.require(ins, tk.end_statement)
    else:
        # retrieve Music Macro Language string
        mml0 = vartypes.pass_string_unpack(
                    expressions.parse_expression(ins, allow_empty=True),
                    allow_empty=True)
        mml1, mml2 = '', ''
        if ((pcjr_syntax == 'tandy' or (pcjr_syntax == 'pcjr' and
                                         state.console_state.sound.sound_on))
                and util.skip_white_read_if(ins, (',',))):
            mml1 = vartypes.pass_string_unpack(
                        expressions.parse_expression(ins, allow_empty=True),
                        allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                mml2 = vartypes.pass_string_unpack(
                            expressions.parse_expression(ins, allow_empty=True),
                            allow_empty=True)
        util.require(ins, tk.end_statement)
        if not (mml0 or mml1 or mml2):
            raise error.RunError(error.MISSING_OPERAND)
        state.console_state.sound.play((mml0, mml1, mml2))

def exec_noise(ins):
    """ NOISE: produce sound on the noise generator (Tandy/PCjr). """
    if not state.console_state.sound.sound_on:
        raise error.RunError(error.IFC)
    source = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    volume = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    util.range_check(0, 7, source)
    util.range_check(0, 15, volume)
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(error.IFC)
    util.require(ins, tk.end_statement)
    one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
    dur_sec = dur.to_value()/18.2
    if one_over_44.gt(dur):
        state.console_state.sound.play_noise(source, volume, dur_sec, loop=True)
    else:
        state.console_state.sound.play_noise(source, volume, dur_sec)


##########################################################
# machine emulation

def exec_poke(ins):
    """ POKE: write to a memory location. Limited implementation. """
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(error.IFC)
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    machine.poke(addr, val)
    util.require(ins, tk.end_statement)

def exec_def_seg(ins):
    """ DEF SEG: set the current memory segment. """
    # &hb800: text screen buffer; &h13d: data segment
    if util.skip_white_read_if(ins, (tk.O_EQ,)): #=
        state.basic_state.segment = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    else:
        state.basic_state.segment = memory.data_segment
    if state.basic_state.segment < 0:
        state.basic_state.segment += 0x10000
    util.require(ins, tk.end_statement)

def exec_def_usr(ins):
    """ DEF USR: Define a machine language function. Not implemented. """
    util.require_read(ins, tk.digit)
    util.require_read(ins, (tk.O_EQ,))
    vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=0xffff)
    util.require(ins, tk.end_statement)
    logging.warning("DEF USR statement not implemented")

def exec_bload(ins):
    """ BLOAD: load a file into a memory location. Limited implementation. """
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(error.IFC)
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    offset = None
    if util.skip_white_read_if(ins, (',',)):
        offset = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
        if offset < 0:
            offset += 0x10000
    util.require(ins, tk.end_statement)
    with devices.open_file(0, name, filetype='M', mode='I') as f:
        machine.bload(f, offset)

def exec_bsave(ins):
    """ BSAVE: save a block of memory to a file. Limited implementation. """
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(error.IFC)
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    util.require_read(ins, (',',))
    offset = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint = 0xffff)
    if offset < 0:
        offset += 0x10000
    util.require_read(ins, (',',))
    length = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint = 0xffff)
    if length < 0:
        length += 0x10000
    util.require(ins, tk.end_statement)
    with devices.open_file(0, name, filetype='M', mode='O',
                            seg=state.basic_state.segment,
                            offset=offset, length=length) as f:
        machine.bsave(f, offset, length)

def exec_call(ins):
    """ CALL: call an external procedure. Not implemented. """
    addr_var = util.get_var_name(ins)
    if addr_var[-1] == '$':
        # type mismatch
        raise error.RunError(error.TYPE_MISMATCH)
    if util.skip_white_read_if(ins, ('(',)):
        while True:
            # if we wanted to call a function, we should distinguish varnames
            # (passed by ref) from constants (passed by value) here.
            expressions.parse_expression(ins)
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require_read(ins, (')',))
    util.require(ins, tk.end_statement)
    # ignore the statement
    logging.warning("CALL or CALLS statement not implemented")

def exec_calls(ins):
    """ CALLS: call an external procedure. Not implemented. """
    exec_call(ins)

def exec_out(ins):
    """ OUT: send a byte to a machine port. Limited implementation. """
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    machine.out(addr, val)
    util.require(ins, tk.end_statement)

def exec_wait(ins):
    """ WAIT: wait for a machine port. Limited implementation. """
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    ander = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, ander)
    xorer = 0
    if util.skip_white_read_if(ins, (',',)):
        xorer = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, xorer)
    util.require(ins, tk.end_statement)
    machine.wait(addr, ander, xorer)


##########################################################
# Disk

def exec_chdir(ins):
    """ CHDIR: change working directory. """
    dev, path = disk.get_diskdevice_and_path(
            vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    dev.chdir(path)
    util.require(ins, tk.end_statement)

def exec_mkdir(ins):
    """ MKDIR: create directory. """
    dev, path = disk.get_diskdevice_and_path(
            vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    dev.mkdir(path)
    util.require(ins, tk.end_statement)

def exec_rmdir(ins):
    """ RMDIR: remove directory. """
    dev, path = disk.get_diskdevice_and_path(
            vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    dev.rmdir(path)
    util.require(ins, tk.end_statement)

def exec_name(ins):
    """ NAME: rename file or directory. """
    oldname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # AS is not a tokenised word
    word = util.skip_white_read(ins) + ins.read(1)
    if word.upper() != 'AS':
        raise error.RunError(error.STX)
    newname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    dev, oldpath = disk.get_diskdevice_and_path(oldname)
    newdev, newpath = disk.get_diskdevice_and_path(newname)
    # don't rename open files
    dev.check_file_not_open(oldpath)
    if dev != newdev:
        raise error.RunError(error.RENAME_ACROSS_DISKS)
    dev.rename(oldpath, newpath)
    util.require(ins, tk.end_statement)

def exec_kill(ins):
    """ KILL: remove file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # don't delete open files
    dev, path = disk.get_diskdevice_and_path(name)
    dev.check_file_not_open(path)
    dev.kill(path)
    util.require(ins, tk.end_statement)

def exec_files(ins):
    """ FILES: output directory listing. """
    pathmask = ''
    if util.skip_white(ins) not in tk.end_statement:
        pathmask = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        if not pathmask:
            raise error.RunError(error.BAD_FILE_NAME)
    dev, path = disk.get_diskdevice_and_path(pathmask)
    dev.files(path)
    util.require(ins, tk.end_statement)


##########################################################
# OS

def exec_shell(ins):
    """ SHELL: open OS shell and optionally execute command. """
    # parse optional shell command
    if util.skip_white(ins) in tk.end_statement:
        cmd = ''
    else:
        cmd = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # no SHELL on PCjr.
    if pcjr_syntax == 'pcjr':
        raise error.RunError(error.IFC)
    # force cursor visible in all cases
    state.console_state.screen.cursor.show(True)
    # execute cms or open interactive shell
    shell.shell(cmd)
    # reset cursor visibility to its previous state
    state.console_state.screen.cursor.reset_visibility()
    util.require(ins, tk.end_statement)

def exec_environ(ins):
    """ ENVIRON: set environment string. """
    envstr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    eqs = envstr.find('=')
    if eqs <= 0:
        raise error.RunError(error.IFC)
    envvar = str(envstr[:eqs])
    val = str(envstr[eqs+1:])
    os.environ[envvar] = val
    util.require(ins, tk.end_statement)

def exec_time(ins):
    """ TIME$: set time. """
    util.require_read(ins, (tk.O_EQ,)) #time$=
    # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
    timestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, tk.end_statement)
    timedate.set_time(timestr)

def exec_date(ins):
    """ DATE$: set date. """
    util.require_read(ins, (tk.O_EQ,)) # date$=
    # allowed formats:
    # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
    # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
    datestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, tk.end_statement)
    timedate.set_date(datestr)

##########################################################
# code

def parse_line_range(ins):
    """ Helper function: parse line number ranges. """
    from_line = parse_jumpnum_or_dot(ins, allow_empty=True)
    if util.skip_white_read_if(ins, (tk.O_MINUS,)):
        to_line = parse_jumpnum_or_dot(ins, allow_empty=True)
    else:
        to_line = from_line
    return (from_line, to_line)

def parse_jumpnum_or_dot(ins, allow_empty=False, err=error.STX):
    """ Helper function: parse jump target. """
    c = util.skip_white_read(ins)
    if c == tk.T_UINT:
        return vartypes.uint_to_value(bytearray(ins.read(2)))
    elif c == '.':
        return state.basic_state.last_stored
    else:
        if allow_empty:
            ins.seek(-len(c), 1)
            return None
        raise error.RunError(err)

def exec_delete(ins):
    """ DELETE: delete range of lines from program. """
    from_line, to_line = parse_line_range(ins)
    util.require(ins, tk.end_statement)
    # throws back to direct mode
    program.delete(from_line, to_line)
    # clear all variables
    reset.clear()

def exec_edit(ins):
    """ EDIT: output a program line and position cursor for editing. """
    if util.skip_white(ins) in tk.end_statement:
        # undefined line number
        raise error.RunError(error.UNDEFINED_LINE_NUMBER)
    from_line = parse_jumpnum_or_dot(ins, err=error.IFC)
    if from_line is None or from_line not in state.basic_state.line_numbers:
        raise error.RunError(error.UNDEFINED_LINE_NUMBER)
    util.require(ins, tk.end_statement, err=error.IFC)
    # throws back to direct mode
    flow.set_pointer(False)
    state.basic_state.execute_mode = False
    state.console_state.screen.cursor.reset_visibility()
    # request edit prompt
    state.basic_state.edit_prompt = (from_line, None)

def exec_auto(ins):
    """ AUTO: enter automatic line numbering mode. """
    linenum = parse_jumpnum_or_dot(ins, allow_empty=True)
    increment = None
    if util.skip_white_read_if(ins, (',',)):
        increment = util.parse_jumpnum(ins, allow_empty=True)
    util.require(ins, tk.end_statement)
    # reset linenum and increment on each call of AUTO (even in AUTO mode)
    state.basic_state.auto_linenum = linenum if linenum is not None else 10
    state.basic_state.auto_increment = increment if increment is not None else 10
    # move program pointer to end
    flow.set_pointer(False)
    # continue input in AUTO mode
    state.basic_state.auto_mode = True

def exec_list(ins):
    """ LIST: output program lines. """
    from_line, to_line = parse_line_range(ins)
    out = None
    if util.skip_white_read_if(ins, (',',)):
        outname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        out = devices.open_file(0, outname, filetype='A', mode='O')
    util.require(ins, tk.end_statement)
    lines = program.list_lines(from_line, to_line)
    if out:
        with out:
            for l in lines:
                out.write_line(l)
    else:
        for l in lines:
            # LIST on screen is slightly different from just writing
            console.list_line(l)

def exec_llist(ins):
    """ LLIST: output program lines to LPT1: """
    from_line, to_line = parse_line_range(ins)
    util.require(ins, tk.end_statement)
    for l in program.list_lines(from_line, to_line):
        state.io_state.lpt1_file.write_line(l)

def exec_load(ins):
    """ LOAD: load program from file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    comma = util.skip_white_read_if(ins, (',',))
    if comma:
        util.require_read(ins, 'R')
    util.require(ins, tk.end_statement)
    with devices.open_file(0, name, filetype='ABP', mode='I') as f:
        program.load(f)
    reset.clear()
    if comma:
        # in ,R mode, don't close files; run the program
        flow.jump(None)
    else:
        devices.close_files()
    state.basic_state.tron = False

def exec_chain(ins):
    """ CHAIN: load program and chain execution. """
    if util.skip_white_read_if(ins, (tk.MERGE,)):
        action = program.merge
    else:
        action = program.load
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    jumpnum, common_all, delete_lines = None, False, None
    if util.skip_white_read_if(ins, (',',)):
        # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
        expr = expressions.parse_expression(ins, allow_empty=True)
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
                    delete_lines = parse_delete_clause(ins)
            else:
                # CHAIN "file", , DELETE
                delete_lines = parse_delete_clause(ins)
    util.require(ins, tk.end_statement)
    if state.basic_state.protected and action == program.merge:
            raise error.RunError(error.IFC)
    with devices.open_file(0, name, filetype='ABP', mode='I') as f:
        program.chain(action, f, jumpnum, delete_lines)
    # preserve DEFtype on MERGE
    reset.clear(preserve_common=True, preserve_all=common_all, preserve_deftype=(action==program.merge))

def parse_delete_clause(ins):
    """ Helper function: parse the DELETE clause of a CHAIN statement. """
    delete_lines = None
    if util.skip_white_read_if(ins, (tk.DELETE,)):
        from_line = util.parse_jumpnum(ins, allow_empty=True)
        if util.skip_white_read_if(ins, (tk.O_MINUS,)):
            to_line = util.parse_jumpnum(ins, allow_empty=True)
        else:
            to_line = from_line
        # to_line must be specified and must be an existing line number
        if not to_line or to_line not in state.basic_state.line_numbers:
            raise error.RunError(error.IFC)
        delete_lines = (from_line, to_line)
        # ignore rest if preceded by cmma
        if util.skip_white_read_if(ins, (',',)):
            util.skip_to(ins, tk.end_statement)
    return delete_lines

def exec_save(ins):
    """ SAVE: save program to a file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    mode = 'B'
    if util.skip_white_read_if(ins, (',',)):
        mode = util.skip_white_read(ins).upper()
        if mode not in ('A', 'P'):
            raise error.RunError(error.STX)
    with devices.open_file(0, name, filetype=mode, mode='O',
                            seg=memory.data_segment, offset=memory.code_start,
                            length=len(state.basic_state.bytecode.getvalue())-1
                            ) as f:
        program.save(f)
    util.require(ins, tk.end_statement)

def exec_merge(ins):
    """ MERGE: merge lines from file into current program. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    with devices.open_file(0, name, filetype='A', mode='I') as f:
        program.merge(f)
    util.require(ins, tk.end_statement)

def exec_new(ins):
    """ NEW: clear program from memory. """
    state.basic_state.tron = False
    # deletes the program currently in memory
    program.erase_program()
    # and clears all variables
    reset.clear()

def exec_renum(ins):
    """ RENUM: renumber program line numbers. """
    new, old, step = None, None, None
    if util.skip_white(ins) not in tk.end_statement:
        new = parse_jumpnum_or_dot(ins, allow_empty=True)
        if util.skip_white_read_if(ins, (',',)):
            old = parse_jumpnum_or_dot(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                step = util.parse_jumpnum(ins, allow_empty=True) # returns -1 if empty
    util.require(ins, tk.end_statement)
    if step is not None and step < 1:
        raise error.RunError(error.IFC)
    program.renum(new, old, step)


##########################################################
# file

def exec_reset(ins):
    """ RESET: close all files. """
    devices.close_files()
    util.require(ins, tk.end_statement)

def parse_read_write(ins):
    """ Helper function: parse access mode. """
    d = util.skip_white(ins)
    if d == tk.WRITE:
        ins.read(1)
        access = 'W'
    elif d == tk.READ:
        ins.read(1)
        access = 'RW' if util.skip_white_read_if(ins, (tk.WRITE,)) else 'R'
    return access

long_modes = {tk.INPUT:'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}
default_access_modes = {'I':'R', 'O':'W', 'A':'RW', 'R':'RW'}

def exec_open(ins):
    """ OPEN: open a file. """
    first_expr = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    mode, access, lock, reclen = 'R', 'RW', '', 128
    if util.skip_white_read_if(ins, (',',)):
        # first syntax
        try:
            mode = first_expr[0].upper()
            access = default_access_modes[mode]
        except (IndexError, KeyError):
            raise error.RunError(error.BAD_FILE_MODE)
        number = expressions.parse_file_number_opthash(ins)
        util.require_read(ins, (',',))
        name = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
        if util.skip_white_read_if(ins, (',',)):
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        # second syntax
        name = first_expr
        # FOR clause
        if util.skip_white_read_if(ins, (tk.FOR,)):
            c = util.skip_white_read(ins)
            # read word
            word = ''
            while c not in tk.whitespace:
                word += c
                c = ins.read(1).upper()
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
            access = parse_read_write(ins)
        # LOCK clause
        if util.skip_white_read_if(ins, (tk.LOCK,)):
            util.skip_white(ins)
            lock = parse_read_write(ins)
        elif util.skip_white_read_if(ins, ('SHARED',)):
            lock = 'S'
        # AS file number clause
        if not util.skip_white_read_if(ins, ('AS',)):
            raise error.RunError(error.STX)
        number = expressions.parse_file_number_opthash(ins)
        # LEN clause
        if util.skip_white_read_if(ins, (tk.LEN,)):
            util.require_read(ins, tk.O_EQ)
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    # mode and access must match if not a RANDOM file
    # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
    # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
    if mode == 'A' and access == 'W':
        raise error.RunError(error.PATH_FILE_ACCESS_ERROR)
    elif mode != 'R' and access and access != default_access_modes[mode]:
        raise error.RunError(error.STX)
    util.range_check(1, ports.max_reclen, reclen)
    devices.open_file(number, name, 'D', mode, access, lock, reclen)
    util.require(ins, tk.end_statement)

def exec_close(ins):
    """ CLOSE: close a file. """
    if util.skip_white(ins) in tk.end_statement:
        # allow empty CLOSE; close all open files
        devices.close_files()
    else:
        while True:
            number = expressions.parse_file_number_opthash(ins)
            try:
                devices.close_file(number)
            except KeyError:
                pass
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, tk.end_statement)

def exec_field(ins):
    """ FIELD: link a string variable to record buffer. """
    the_file = devices.get_file(expressions.parse_file_number_opthash(ins), 'R')
    if util.skip_white_read_if(ins, (',',)):
        offset = 0
        while True:
            width = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            util.range_check(0, 255, width)
            util.require_read(ins, ('AS',), err=error.IFC)
            name, index = expressions.get_var_or_array_name(ins)
            var.set_field_var_or_array(the_file, name, index, offset, width)
            offset += width
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, tk.end_statement)

def parse_get_or_put_file(ins):
    """ Helper function: PUT and GET syntax. """
    the_file = devices.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, (',',)):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
        # not 2^32-1 as the manual boasts!
        # pos-1 needs to fit in a single-precision mantissa
        util.range_check_err(1, 2**25, pos, err=error.BAD_RECORD_NUMBER)
        if not isinstance(the_file, ports.COMFile):
            the_file.set_pos(pos)
        else:
            num_bytes = pos
    return the_file, num_bytes

def exec_put_file(ins):
    """ PUT: write record to file. """
    thefile, num_bytes = parse_get_or_put_file(ins)
    thefile.put(num_bytes)
    util.require(ins, tk.end_statement)

def exec_get_file(ins):
    """ GET: read record from file. """
    thefile, num_bytes = parse_get_or_put_file(ins)
    thefile.get(num_bytes)
    util.require(ins, tk.end_statement)

def exec_lock_or_unlock(ins, action):
    """ LOCK or UNLOCK: set file or record locks. """
    thefile = devices.get_file(expressions.parse_file_number_opthash(ins))
    lock_start_rec = 1
    if util.skip_white_read_if(ins, (',',)):
        lock_start_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
    lock_stop_rec = lock_start_rec
    if util.skip_white_read_if(ins, (tk.TO,)):
        lock_stop_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
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

def exec_ioctl(ins):
    """ IOCTL: send control string to I/O device. Not implemented. """
    devices.get_file(expressions.parse_file_number_opthash(ins))
    logging.warning("IOCTL statement not implemented.")
    raise error.RunError(error.IFC)

##########################################################
# Graphics statements

def parse_coord_bare(ins):
    """ Helper function: parse coordinate pair. """
    util.require_read(ins, ('(',))
    x = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (',',))
    y = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (')',))
    return x, y

def parse_coord_step(ins):
    """ Helper function: parse coordinate pair. """
    step = util.skip_white_read_if(ins, (tk.STEP,))
    x, y = parse_coord_bare(ins)
    return x, y, step

def exec_pset(ins, c=-1):
    """ PSET: set a pixel to a given attribute, or foreground. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    lcoord = parse_coord_step(ins)
    if util.skip_white_read_if(ins, (',',)):
        c = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(-1, 255, c)
    util.require(ins, tk.end_statement)
    state.console_state.screen.drawing.pset(lcoord, c)

def exec_preset(ins):
    """ PRESET: set a pixel to a given attribute, or background. """
    exec_pset(ins, 0)

def exec_line_graph(ins):
    """ LINE: draw a line or box between two points. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    if util.skip_white(ins) in ('(', tk.STEP):
        coord0 = parse_coord_step(ins)
    else:
        coord0 = None
    util.require_read(ins, (tk.O_MINUS,))
    coord1 = parse_coord_step(ins)
    c, mode, pattern = -1, '', 0xffff
    if util.skip_white_read_if(ins, (',',)):
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr:
            c = vartypes.pass_int_unpack(expr)
        if util.skip_white_read_if(ins, (',',)):
            if util.skip_white_read_if(ins, ('B',)):
                mode = 'BF' if util.skip_white_read_if(ins, ('F',)) else 'B'
            else:
                util.require(ins, (',',))
            if util.skip_white_read_if(ins, (',',)):
                pattern = vartypes.pass_int_unpack(expressions.parse_expression(
                                    ins, empty_err=error.MISSING_OPERAND),
                                    maxint=0x7fff)
        elif not expr:
            raise error.RunError(error.MISSING_OPERAND)
    util.require(ins, tk.end_statement)
    state.console_state.screen.drawing.line(coord0, coord1, c, pattern, mode)

def exec_view_graph(ins):
    """ VIEW: set graphics viewport and optionally draw a box. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    absolute = util.skip_white_read_if(ins, (tk.SCREEN,))
    if util.skip_white(ins) == '(':
        x0, y0 = parse_coord_bare(ins)
        x0, y0 = x0.round_to_int(), y0.round_to_int()
        util.require_read(ins, (tk.O_MINUS,))
        x1, y1 = parse_coord_bare(ins)
        x1, y1 = x1.round_to_int(), y1.round_to_int()
        util.range_check(0, state.console_state.screen.mode.pixel_width-1, x0, x1)
        util.range_check(0, state.console_state.screen.mode.pixel_height-1, y0, y1)
        fill, border = None, None
        if util.skip_white_read_if(ins, (',',)):
            fill, border = expressions.parse_int_list(ins, 2, err=error.STX)
        state.console_state.screen.drawing.set_view(x0, y0, x1, y1, absolute, fill, border)
    else:
        state.console_state.screen.drawing.unset_view()
    util.require(ins, tk.end_statement)

def exec_window(ins):
    """ WINDOW: define logical coordinate system. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    cartesian = not util.skip_white_read_if(ins, (tk.SCREEN,))
    if util.skip_white(ins) == '(':
        x0, y0 = parse_coord_bare(ins)
        util.require_read(ins, (tk.O_MINUS,))
        x1, y1 = parse_coord_bare(ins)
        if x0.equals(x1) or y0.equals(y1):
            raise error.RunError(error.IFC)
        state.console_state.screen.drawing.set_window(x0, y0, x1, y1, cartesian)
    else:
        state.console_state.screen.drawing.unset_window()
    util.require(ins, tk.end_statement)

def exec_circle(ins):
    """ CIRCLE: Draw a circle, ellipse, arc or sector. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    centre = parse_coord_step(ins)
    util.require_read(ins, (',',))
    r = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    start, stop, c, aspect = None, None, -1, None
    if util.skip_white_read_if(ins, (',',)):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if cval:
            c = vartypes.pass_int_unpack(cval)
        if util.skip_white_read_if(ins, (',',)):
            start = expressions.parse_expression(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                stop = expressions.parse_expression(ins, allow_empty=True)
                if util.skip_white_read_if(ins, (',',)):
                    aspect = fp.unpack(vartypes.pass_single_keep(
                                            expressions.parse_expression(ins)))
                elif stop is None:
                    # missing operand
                    raise error.RunError(error.MISSING_OPERAND)
            elif start is None:
                raise error.RunError(error.MISSING_OPERAND)
        elif cval is None:
            raise error.RunError(error.MISSING_OPERAND)
    util.require(ins, tk.end_statement)
    state.console_state.screen.drawing.circle(centre, r, start, stop, c, aspect)

def exec_paint(ins):
    """ PAINT: flood fill from point. """
    # if paint *colour* specified, border default = paint colour
    # if paint *attribute* specified, border default = current foreground
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    coord = parse_coord_step(ins)
    pattern, c, border, background_pattern = None, -1, -1, None
    if util.skip_white_read_if(ins, (',',)):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if not cval:
            pass
        elif cval[0] == '$':
            # pattern given; copy
            pattern = bytearray(vartypes.pass_string_unpack(cval))
            if not pattern:
                # empty pattern "" is illegal function call
                raise error.RunError(error.IFC)
            # default for border, if pattern is specified as string: foreground attr
        else:
            c = vartypes.pass_int_unpack(cval)
        border = c
        if util.skip_white_read_if(ins, (',',)):
            bval = expressions.parse_expression(ins, allow_empty=True)
            if bval:
                border = vartypes.pass_int_unpack(bval)
            if util.skip_white_read_if(ins, (',',)):
                background_pattern = vartypes.pass_string_unpack(expressions.parse_expression(ins), err=error.IFC)
                # only in screen 7,8,9 is this an error (use ega memory as a check)
                if (pattern and background_pattern[:len(pattern)] == pattern and
                        state.console_state.screen.mode.mem_start == 0xa000):
                    raise error.RunError(error.IFC)
    util.require(ins, tk.end_statement)
    state.console_state.screen.drawing.paint(coord, pattern, c, border, background_pattern)

def exec_get_graph(ins):
    """ GET: read a sprite to memory. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    # don't accept STEP for first coord
    util.require(ins, ('('))
    coord0 = parse_coord_step(ins)
    util.require_read(ins, (tk.O_MINUS,))
    coord1 = parse_coord_step(ins)
    util.require_read(ins, (',',))
    array = util.get_var_name(ins)
    util.require(ins, tk.end_statement)
    if array not in state.basic_state.arrays:
        raise error.RunError(error.IFC)
    elif array[-1] == '$':
        raise error.RunError(error.TYPE_MISMATCH) # type mismatch
    state.console_state.screen.drawing.get(coord0, coord1, array)

def exec_put_graph(ins):
    """ PUT: draw sprite on screen. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    # don't accept STEP
    util.require(ins, ('('))
    coord = parse_coord_step(ins)
    util.require_read(ins, (',',))
    array = util.get_var_name(ins)
    action = tk.XOR
    if util.skip_white_read_if(ins, (',',)):
        util.require(ins, (tk.PSET, tk.PRESET,
                           tk.AND, tk.OR, tk.XOR))
        action = ins.read(1)
    util.require(ins, tk.end_statement)
    if array not in state.basic_state.arrays:
        raise error.RunError(error.IFC)
    elif array[-1] == '$':
        # type mismatch
        raise error.RunError(error.TYPE_MISMATCH)
    state.console_state.screen.drawing.put(coord, array, action)

def exec_draw(ins):
    """ DRAW: draw a figure defined by a Graphics Macro Language string. """
    if state.console_state.screen.mode.is_text_mode:
        raise error.RunError(error.IFC)
    gml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, tk.end_expression)
    state.console_state.screen.drawing.draw(gml)

##########################################################
# Flow-control statements

def exec_end(ins):
    """ END: end program execution and return to interpreter. """
    util.require(ins, tk.end_statement)
    state.basic_state.stop = state.basic_state.bytecode.tell()
    # jump to end of direct line so execution stops
    flow.set_pointer(False)
    # avoid NO RESUME
    state.basic_state.error_handle_mode = False
    state.basic_state.error_resume = None
    devices.close_files()

def exec_stop(ins):
    """ STOP: break program execution and return to interpreter. """
    util.require(ins, tk.end_statement)
    raise error.Break(stop=True)

def exec_cont(ins):
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

def exec_for(ins):
    """ FOR: enter for-loop. """
    # read variable
    varname = util.get_var_name(ins)
    vartype = varname[-1]
    if vartype == '$':
        raise error.RunError(error.TYPE_MISMATCH)
    util.require_read(ins, (tk.O_EQ,)) # =
    start = expressions.parse_expression(ins)
    util.require_read(ins, (tk.TO,))  # TO
    stop = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))
    if util.skip_white_read_if(ins, (tk.STEP,)): # STEP
        step = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))
    else:
        # convert 1 to vartype
        step = vartypes.pass_type_keep(vartype, vartypes.pack_int(1))
    util.require(ins, tk.end_statement)
    endforpos = ins.tell()
    # find NEXT
    nextpos = find_next(ins, varname)
    # apply initial condition and jump to nextpos
    flow.loop_init(ins, endforpos, nextpos, varname, start, stop, step)
    exec_next(ins)

def skip_to_next(ins, for_char, next_char, allow_comma=False):
    """ Helper function for FOR: skip over bytecode until NEXT. """
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

def find_next(ins, varname):
    """ Helper function for FOR: find the right NEXT. """
    current = ins.tell()
    skip_to_next(ins, tk.FOR, tk.NEXT, allow_comma=True)
    util.require(ins, (tk.NEXT, ','), err=error.FOR_WITHOUT_NEXT)
    comma = (ins.read(1)==',')
    # get position and line number just after the NEXT
    nextpos = ins.tell()
    # check var name for NEXT
    varname2 = util.get_var_name(ins, allow_empty=True)
    # no-var only allowed in standalone NEXT
    if varname2 == '':
        util.require(ins, tk.end_statement)
    if (comma or varname2) and varname2 != varname:
        # NEXT without FOR
        errline = program.get_line_number(nextpos-1) if state.basic_state.run_mode else -1
        raise error.RunError(error.NEXT_WITHOUT_FOR, errline)
    ins.seek(current)
    return nextpos

def exec_next(ins):
    """ NEXT: iterate for-loop. """
    # jump to end of FOR, increment counter, check condition.
    if flow.loop_iterate(ins):
        util.skip_to(ins, tk.end_statement+(',',))
        if util.skip_white_read_if(ins, (',')):
            # we're jumping into a comma'ed NEXT, call exec_next
            return exec_next(ins)

def exec_goto(ins):
    """ GOTO: jump to specified line number. """
    # parse line number, ignore rest of line and jump
    flow.jump(util.parse_jumpnum(ins))

def exec_run(ins):
    """ RUN: start program execution. """
    comma = util.skip_white_read_if(ins, (',',))
    if comma:
        util.require_read(ins, 'R')
    c = util.skip_white(ins)
    jumpnum = None
    if c == tk.T_UINT:
        # parse line number, ignore rest of line and jump
        jumpnum = util.parse_jumpnum(ins)
    elif c not in tk.end_statement:
        name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, tk.end_statement)
        with devices.open_file(0, name, filetype='ABP', mode='I') as f:
            program.load(f)
    flow.init_program()
    reset.clear(close_files=not comma)
    flow.jump(jumpnum)
    state.basic_state.error_handle_mode = False

def exec_if(ins):
    """ IF: enter branching statement. """
    # avoid overflow: don't use bools.
    val = vartypes.pass_single_keep(expressions.parse_expression(ins))
    util.skip_white_read_if(ins, (',',)) # optional comma
    util.require_read(ins, (tk.THEN, tk.GOTO))
    if not fp.unpack(val).is_zero():
        # TRUE: continue after THEN. line number or statement is implied GOTO
        if util.skip_white(ins) in (tk.T_UINT,):
            flow.jump(util.parse_jumpnum(ins))
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
                            flow.jump(util.parse_jumpnum(ins))
                        # continue execution from here
                        break
            else:
                ins.seek(-len(d), 1)
                break

def exec_else(ins):
    """ ELSE: part of branch statement; ignore. """
    # any else statement by itself means the THEN has already been executed, so it's really like a REM.
    util.skip_to(ins, tk.end_line)

def exec_while(ins, first=True):
    """ WHILE: enter while-loop. """
    # just after WHILE opcode
    whilepos = ins.tell()
    # evaluate the 'boolean' expression
    # use double to avoid overflows
    if first:
        # find matching WEND
        skip_to_next(ins, tk.WHILE, tk.WEND)
        if ins.read(1) == tk.WEND:
            util.skip_to(ins, tk.end_statement)
            wendpos = ins.tell()
            state.basic_state.while_wend_stack.append((whilepos, wendpos))
        else:
            # WHILE without WEND
            raise error.RunError(error.WHILE_WITHOUT_WEND)
        ins.seek(whilepos)
    boolvar = vartypes.pass_double_keep(expressions.parse_expression(ins))
    # condition is zero?
    if fp.unpack(boolvar).is_zero():
        # jump to WEND
        whilepos, wendpos = state.basic_state.while_wend_stack.pop()
        ins.seek(wendpos)

def exec_wend(ins):
    """ WEND: iterate while-loop. """
    # while will actually syntax error on the first run if anything is in the way.
    util.require(ins, tk.end_statement)
    pos = ins.tell()
    while True:
        if not state.basic_state.while_wend_stack:
            # WEND without WHILE
            raise error.RunError(error.WEND_WITHOUT_WHILE)
        whilepos, wendpos = state.basic_state.while_wend_stack[-1]
        if pos != wendpos:
            # not the expected WEND, we must have jumped out
            state.basic_state.while_wend_stack.pop()
        else:
            # found it
            break
    ins.seek(whilepos)
    return exec_while(ins, False)

def exec_on_jump(ins):
    """ ON: calculated jump. """
    onvar = vartypes.pass_int_unpack(expressions.parse_expression(ins))
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
            flow.jump(util.parse_jumpnum(ins))
        elif command == tk.GOSUB:
            exec_gosub(ins)
    util.skip_to(ins, tk.end_statement)

def exec_on_error(ins):
    """ ON ERROR: define error trapping routine. """
    util.require_read(ins, (tk.GOTO,))  # GOTO
    linenum = util.parse_jumpnum(ins)
    if linenum != 0 and linenum not in state.basic_state.line_numbers:
        raise error.RunError(error.UNDEFINED_LINE_NUMBER)
    state.basic_state.on_error = linenum
    # ON ERROR GOTO 0 in error handler
    if state.basic_state.on_error == 0 and state.basic_state.error_handle_mode:
        # re-raise the error so that execution stops
        raise error.RunError(state.basic_state.errn, state.basic_state.errp)
    # this will be caught by the trapping routine just set
    util.require(ins, tk.end_statement)

def exec_resume(ins):
    """ RESUME: resume program flow after error-trap. """
    if state.basic_state.error_resume is None:
        # unset error handler
        state.basic_state.on_error = 0
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
    flow.resume(jumpnum)

def exec_error(ins):
    """ ERRROR: simulate an error condition. """
    errn = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(1, 255, errn)
    raise error.RunError(errn)

def exec_gosub(ins):
    """ GOSUB: jump into a subroutine. """
    jumpnum = util.parse_jumpnum(ins)
    # ignore rest of statement ('GOSUB 100 LAH' works just fine..); we need to be able to RETURN
    util.skip_to(ins, tk.end_statement)
    flow.jump_gosub(jumpnum)

def exec_return(ins):
    """ RETURN: return from a subroutine. """
    # return *can* have a line number
    if util.skip_white(ins) not in tk.end_statement:
        jumpnum = util.parse_jumpnum(ins)
        # rest of line is ignored
        util.skip_to(ins, tk.end_statement)
    else:
        jumpnum = None
    flow.jump_return(jumpnum)

################################################
# Variable & array statements

def parse_var_list(ins):
    """ Helper function: parse variable list.  """
    readvar = []
    while True:
        readvar.append(list(expressions.get_var_or_array_name(ins)))
        if not util.skip_white_read_if(ins, (',',)):
            break
    return readvar

def exec_clear(ins):
    """ CLEAR: clear memory and redefine memory limits. """
    # integer expression allowed but ignored
    intexp = expressions.parse_expression(ins, allow_empty=True)
    if intexp:
        expr = vartypes.pass_int_unpack(intexp)
        if expr < 0:
            raise error.RunError(error.IFC)
    if util.skip_white_read_if(ins, (',',)):
        exp1 = expressions.parse_expression(ins, allow_empty=True)
        if exp1:
            # this produces a *signed* int
            mem_size = vartypes.pass_int_unpack(exp1, maxint=0xffff)
            if mem_size == 0:
                #  0 leads to illegal fn call
                raise error.RunError(error.IFC)
            else:
                if not memory.set_basic_memory_size(mem_size):
                    raise error.RunError(error.OUT_OF_MEMORY)
        if util.skip_white_read_if(ins, (',',)):
            # set aside stack space for GW-BASIC. The default is the previous stack space size.
            exp2 = expressions.parse_expression(ins, allow_empty = True)
            if exp2:
                stack_size = vartypes.pass_int_unpack(exp2, maxint=0xffff)
                if stack_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(error.IFC)
                memory.set_stack_size(stack_size)
            if pcjr_syntax and util.skip_white_read_if(ins, (',',)):
                # Tandy/PCjr: select video memory size
                if not state.console_state.screen.set_video_memory_size(
                    fp.unpack(vartypes.pass_single_keep(
                                 expressions.parse_expression(ins, empty_err=error.STX)
                             )).round_to_int()):
                    state.console_state.screen.screen(0, 0, 0, 0)
                    console.init_mode()
            elif not exp2:
                raise error.RunError(error.STX)
    util.require(ins, tk.end_statement)
    reset.clear()

def exec_common(ins):
    """ COMMON: define variables to be preserved on CHAIN. """
    varlist, arraylist = [], []
    while True:
        name = util.get_var_name(ins)
        # array?
        if util.skip_white_read_if(ins, ('[', '(')):
            util.require_read(ins, (']', ')'))
            arraylist.append(name)
        else:
            varlist.append(name)
        if not util.skip_white_read_if(ins, (',',)):
            break
    state.basic_state.common_names += varlist
    state.basic_state.common_array_names += arraylist

def exec_data(ins):
    """ DATA: data definition; ignore. """
    # ignore rest of statement after DATA
    util.skip_to(ins, tk.end_statement)

def parse_int_list_var(ins):
    """ Helper function for DIM: parse list of integers. """
    output = [ vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=error.STX)) ]
    while True:
        d = util.skip_white(ins)
        if d == ',':
            ins.read(1)
            c = util.peek(ins)
            if c in tk.end_statement:
                # missing operand
                raise error.RunError(error.MISSING_OPERAND)
            # if end_expression, syntax error
            output.append(vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=error.STX)))
        elif d in tk.end_statement:
            # statement ends - syntax error
            raise error.RunError(error.STX)
        elif d in tk.end_expression:
            break
        else:
            raise error.RunError(error.STX)
    return output

def exec_dim(ins):
    """ DIM: dimension arrays. """
    while True:
        name = util.get_var_name(ins)
        dimensions = [ 10 ]
        if util.skip_white_read_if(ins, ('[', '(')):
            # at most 255 indices, but there's no way to fit those in a 255-byte command line...
            dimensions = parse_int_list_var(ins)
            while len(dimensions) > 0 and dimensions[-1] is None:
                dimensions = dimensions[:-1]
            if None in dimensions:
                raise error.RunError(error.STX)
            util.require_read(ins, (')', ']'))
            # yes, we can write dim gh[5)
        var.dim_array(name, dimensions)
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, tk.end_statement)

def exec_deftype(ins, typechar):
    """ DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables. """
    start, stop = -1, -1
    while True:
        d = util.skip_white_read(ins).upper()
        if d < 'A' or d > 'Z':
            raise error.RunError(error.STX)
        else:
            start = ord(d) - ord('A')
            stop = start
        if util.skip_white_read_if(ins, (tk.O_MINUS,)):
            d = util.skip_white_read(ins).upper()
            if d < 'A' or d > 'Z':
                raise error.RunError(error.STX)
            else:
                stop = ord(d) - ord('A')
        state.basic_state.deftype[start:stop+1] = [typechar] * (stop-start+1)
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, tk.end_statement)

exec_defstr = partial(exec_deftype, typechar='$')
exec_defint = partial(exec_deftype, typechar='%')
exec_defsng = partial(exec_deftype, typechar='!')
exec_defdbl = partial(exec_deftype, typechar='#')

def exec_erase(ins):
    """ ERASE: erase an array. """
    while True:
        var.erase_array(util.get_var_name(ins))
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, tk.end_statement)

def exec_let(ins):
    """ LET: assign value to variable or array. """
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:
        # pre-dim even if this is not a legal statement!
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
        var.check_dim_array(name, indices)
    util.require_read(ins, (tk.O_EQ,))
    var.set_var_or_array(name, indices, expressions.parse_expression(ins))
    util.require(ins, tk.end_statement)

def exec_mid(ins):
    """ MID$: set part of a string. """
    util.require_read(ins, ('(',))
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:
        # pre-dim even if this is not a legal statement!
        var.check_dim_array(name, indices)
    util.require_read(ins, (',',))
    arglist = expressions.parse_int_list(ins, size=2, err=error.STX)
    if arglist[0] is None:
        raise error.RunError(error.STX)
    start = arglist[0]
    num = arglist[1] if arglist[1] is not None else 255
    util.require_read(ins, (')',))
    s = vartypes.pass_string_unpack(var.get_var_or_array(name, indices))
    util.range_check(0, 255, num)
    if num > 0:
        util.range_check(1, len(s), start)
    util.require_read(ins, (tk.O_EQ,))
    val = vartypes.pass_string_keep(expressions.parse_expression(ins))
    util.require(ins, tk.end_statement)
    var.string_assign_into(name, indices, start - 1, num, val)

def exec_lset(ins, justify_right=False):
    """ LSET: assign string value in-place; left justified. """
    name, index = expressions.get_var_or_array_name(ins)
    util.require_read(ins, (tk.O_EQ,))
    val = expressions.parse_expression(ins)
    var.assign_field_var_or_array(name, index, val, justify_right)

def exec_rset(ins):
    """ RSET: assign string value in-place; right justified. """
    exec_lset(ins, justify_right=True)

def exec_option(ins):
    """ OPTION BASE: set array indexing convention. """
    if util.skip_white_read_if(ins, ('BASE',)):
        # MUST be followed by ASCII '1' or '0', num constants or expressions are an error!
        d = util.skip_white_read(ins)
        if d == '0':
            var.base_array(0)
        elif d == '1':
            var.base_array(1)
        else:
            raise error.RunError(error.STX)
    else:
        raise error.RunError(error.STX)
    util.skip_to(ins, tk.end_statement)

def exec_read(ins):
    """ READ: read values from DATA statement. """
    # reading loop
    for v in parse_var_list(ins):
        # syntax error in DATA line (not type mismatch!) if can't convert to var type
        entry = vartypes.pack_string(bytearray(flow.read_entry()))
        if v[0][-1] != '$':
            entry = representation.str_to_value_keep(entry, allow_nonnum=False)
        if entry is None:
            # set pointer for EDIT gadget to position in DATA statement
            state.basic_state.bytecode.seek(state.basic_state.data_pos)
            raise error.RunError(error.STX, state.basic_state.data_pos-1)
        var.set_var_or_array(*v, value=entry)
    util.require(ins, tk.end_statement)

def parse_prompt(ins, question_mark):
    """ Helper function for INPUT: parse prompt definition. """
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

def exec_input(ins):
    """ INPUT: request input from user. """
    finp = expressions.parse_file_number(ins, 'IR')
    if finp is not None:
        for v in parse_var_list(ins):
            value, _ = finp.read_var(v)
            var.set_var_or_array(v[0], v[1], value)
    else:
        # ; to avoid echoing newline
        newline = not util.skip_white_read_if(ins, (';',))
        prompt = parse_prompt(ins, '? ')
        readvar = parse_var_list(ins)
        # move the program pointer to the start of the statement to ensure correct behaviour for CONT
        pos = ins.tell()
        ins.seek(state.basic_state.current_statement)
        # read the input
        state.basic_state.input_mode = True
        varlist = print_and_input.input_console(prompt, readvar, newline)
        state.basic_state.input_mode = False
        for v in varlist:
            var.set_var_or_array(*v)
        ins.seek(pos)
    util.require(ins, tk.end_statement)

def exec_line_input(ins):
    """ LINE INPUT: request input from user. """
    finp = expressions.parse_file_number(ins, 'IR')
    if not finp:
        # ; to avoid echoing newline
        newline = not util.skip_white_read_if(ins, (';',))
        # get prompt
        prompt = parse_prompt(ins, '')
    # get string variable
    readvar, indices = expressions.get_var_or_array_name(ins)
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
        state.basic_state.input_mode = True
        console.write(prompt)
        line = console.wait_screenline(write_endl=newline)
        state.basic_state.input_mode = False
    var.set_var_or_array(readvar, indices, vartypes.pack_string(bytearray(line)))

def exec_restore(ins):
    """ RESTORE: reset DATA pointer. """
    if not util.skip_white(ins) in tk.end_statement:
        datanum = util.parse_jumpnum(ins, err=error.UNDEFINED_LINE_NUMBER)
    else:
        datanum = -1
    # undefined line number for all syntax errors
    util.require(ins, tk.end_statement, err=error.UNDEFINED_LINE_NUMBER)
    flow.restore(datanum)

def exec_swap(ins):
    """ SWAP: swap values of two variables. """
    name1, index1 = expressions.get_var_or_array_name(ins)
    util.require_read(ins, (',',))
    name2, index2 = expressions.get_var_or_array_name(ins)
    var.swap_var(name1, index1, name2, index2)
    # if syntax error. the swap has happened
    util.require(ins, tk.end_statement)

def exec_def_fn(ins):
    """ DEF FN: define a function. """
    fnname = util.get_var_name(ins)
    # read parameters
    fnvars = []
    if util.skip_white_read_if(ins, ('(',)):
        while True:
            fnvars.append(util.get_var_name(ins))
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
    if not state.basic_state.run_mode:
        # GW doesn't allow DEF FN in direct mode, neither do we
        # (for no good reason, works fine)
        raise error.RunError(error.ILLEGAL_DIRECT)
    state.basic_state.functions[fnname] = [fnvars, fncode]

def exec_randomize(ins):
    """ RANDOMIZE: set random number generator seed. """
    val = expressions.parse_expression(ins, allow_empty=True)
    if val:
        # don't convert to int if provided in the code
        val = vartypes.pass_number_keep(val)
    else:
        # prompt for random seed if not specified
        while not val:
            console.write("Random number seed (-32768 to 32767)? ")
            seed = console.wait_screenline()
            # seed entered on prompt is rounded to int
            val = representation.str_to_value_keep(vartypes.pack_string(seed))
        val = vartypes.pass_int_keep(val)
    rnd.randomize(val)
    util.require(ins, tk.end_statement)

################################################
# Console statements

def exec_cls(ins):
    """ CLS: clear the screen. """
    if (pcjr_syntax == 'pcjr' or
                    util.skip_white(ins) in (',',) + tk.end_statement):
        if state.console_state.screen.drawing.view_is_set():
            val = 1
        elif state.console_state.view_set:
            val = 2
        else:
            val = 0
    else:
        val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        if pcjr_syntax == 'tandy':
            # tandy gives illegal function call on CLS number
            raise error.RunError(error.IFC)
    util.range_check(0, 2, val)
    if pcjr_syntax != 'pcjr':
        if util.skip_white_read_if(ins, (',',)):
            # comma is ignored, but a number after means syntax error
            util.require(ins, tk.end_statement)
        else:
            util.require(ins, tk.end_statement, err=error.IFC)
    # cls is only executed if no errors have occurred
    if val == 0:
        console.clear()
        state.console_state.screen.drawing.reset()
    elif val == 1:
        state.console_state.screen.drawing.clear_view()
        state.console_state.screen.drawing.reset()
    elif val == 2:
        console.clear_view()
    if pcjr_syntax == 'pcjr':
        util.require(ins, tk.end_statement)

def exec_color(ins):
    """ COLOR: set colour attributes. """
    fore, back, bord = expressions.parse_int_list(ins, 3, 5)
    screen = state.console_state.screen
    mode = screen.mode
    if mode.name == '320x200x4':
        return exec_color_mode_1(fore, back, bord)
    elif mode.name in ('640x200x2', '720x348x2'):
        # screen 2; hercules: illegal fn call
        raise error.RunError(error.IFC)
    fore_old = (screen.attr>>7)*0x10 + (screen.attr&0xf)
    back_old = (screen.attr>>4) & 0x7
    bord = 0 if bord is None else bord
    util.range_check(0, 255, bord)
    fore = fore_old if fore is None else fore
    # graphics mode bg is always 0; sets palette instead
    if mode.is_text_mode and back is None:
        back = back_old
    else:
        back = screen.palette.get_entry(0) if back is None else back
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


def exec_color_mode_1(back, pal, override):
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

def exec_palette(ins):
    """ PALETTE: set colour palette entry. """
    d = util.skip_white(ins)
    if d in tk.end_statement:
        # reset palette
        state.console_state.screen.palette.set_all(state.console_state.screen.mode.palette)
    elif d == tk.USING:
        ins.read(1)
        exec_palette_using(ins)
    else:
        # can't set blinking colours separately
        mode = state.console_state.screen.mode
        num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
        pair = expressions.parse_int_list(ins, 2, err=error.IFC)
        if pair[0] is None or pair[1] is None:
            raise error.RunError(error.STX)
        util.range_check(0, num_palette_entries-1, pair[0])
        util.range_check(-1, len(mode.colours)-1, pair[1])
        if pair[1] > -1:
            state.console_state.screen.palette.set_entry(pair[0], pair[1])
        util.require(ins, tk.end_statement)

def exec_palette_using(ins):
    """ PALETTE USING: set full colour palette. """
    screen = state.console_state.screen
    mode = screen.mode
    num_palette_entries = mode.num_attr if mode.num_attr != 32 else 16
    array_name, start_indices = expressions.get_var_or_array_name(ins)
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
    util.require(ins, tk.end_statement)

def exec_key(ins):
    """ KEY: switch on/off or list function-key row on screen. """
    d = util.skip_white_read(ins)
    if d == tk.ON:
        # tandy can have VIEW PRINT 1 to 25, should raise ILLEGAN FUNCTION CALL then
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
        ins.seek(-1, 1)
        exec_key_events(ins)
    else:
        # key n, "TEXT"
        ins.seek(-len(d), 1)
        exec_key_define(ins)
    util.require(ins, tk.end_statement)

def exec_key_define(ins):
    """ KEY: define function-key shortcut or scancode for event trapping. """
    keynum = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(1, 255, keynum)
    util.require_read(ins, (',',), err=error.IFC)
    text = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if keynum <= backend.num_fn_keys:
        state.console_state.key_replace[keynum-1] = str(text)
        if state.console_state.keys_visible:
            console.show_keys(True)
    else:
        # only length-2 expressions can be assigned to KEYs over 10
        # in which case it's a key scancode definition
        if len(text) != 2:
            raise error.RunError(error.IFC)
        state.basic_state.events.key[keynum-1].set_trigger(str(text))

def exec_locate(ins):
    """ LOCATE: Set cursor position, shape and visibility."""
    cmode = state.console_state.screen.mode
    row, col, cursor, start, stop, dummy = expressions.parse_int_list(ins, 6, 2, allow_last_empty=True)
    if dummy is not None:
        # can end on a 5th comma but no stuff allowed after it
        raise error.RunError(error.STX)
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
        util.range_check(0, (255 if pcjr_syntax else 1), cursor)
        # set cursor visibility - this should set the flag but have no effect in graphics modes
        state.console_state.screen.cursor.set_visibility(cursor != 0)
    if stop is None:
        stop = start
    if start is not None:
        util.range_check(0, 31, start, stop)
        # cursor shape only has an effect in text mode
        if cmode.is_text_mode:
            state.console_state.screen.cursor.set_shape(start, stop)

def exec_write(ins, output=None):
    """ WRITE: Output machine-readable expressions to the screen or a file. """
    output = expressions.parse_file_number(ins, 'OAR')
    output = state.io_state.scrn_file if output is None else output
    expr = expressions.parse_expression(ins, allow_empty=True)
    outstr = ''
    if expr:
        while True:
            if expr[0] == '$':
                outstr += '"' + str(vartypes.unpack_string(expr)) + '"'
            else:
                outstr += str(vartypes.unpack_string(representation.value_to_str_keep(expr, screen=True, write=True)))
            if util.skip_white_read_if(ins, (',', ';')):
                outstr += ','
            else:
                break
            expr = expressions.parse_expression(ins)
    util.require(ins, tk.end_statement)
    # write the whole thing as one thing (this affects line breaks)
    output.write_line(outstr)

def exec_print(ins, output=None):
    """ PRINT: Write expressions to the screen or a file. """
    if output is None:
        output = expressions.parse_file_number(ins, 'OAR')
        output = state.io_state.scrn_file if output is None else output
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
                if next_zone >= number_zones and output.width >= 14:
                    output.write_line()
                else:
                    output.write(' '*(1+14*next_zone-output.col))
            elif d == tk.SPC: #SPC(
                numspaces = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=error.STX), 0xffff)) % output.width
                util.require_read(ins, (')',))
                output.write(' ' * numspaces)
            elif d == tk.TAB: #TAB(
                pos = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=error.STX), 0xffff) - 1) % output.width + 1
                util.require_read(ins, (')',))
                if pos < output.col:
                    output.write_line()
                    output.write(' '*(pos-1))
                else:
                    output.write(' '*(pos-output.col))
        else:
            newline = True
            expr = expressions.parse_expression(ins)
            word = vartypes.unpack_string(representation.value_to_str_keep(expr, screen=True))
            # numbers always followed by a space
            if expr[0] in ('%', '!', '#'):
                word += ' '
            # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
            output.write(str(word))
    if util.skip_white_read_if(ins, (tk.USING,)):
        return exec_print_using(ins, output)
    if newline:
        if output == state.io_state.scrn_file and state.console_state.overflow:
            output.write_line()
        output.write_line()
    util.require(ins, tk.end_statement)

def exec_print_using(ins, output):
    """ PRINT USING: Write expressions to screen or file using a formatting string. """
    format_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
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
                    s = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
                    if string_field == '&':
                        output.write(s)
                    else:
                        output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
            else:
                number_field, digits_before, decimals = print_and_input.get_number_tokens(fors)
                if number_field:
                    if not data_ends:
                        num = vartypes.pass_float_keep(expressions.parse_expression(ins))
                        output.write(representation.format_number(num, number_field, digits_before, decimals))
                else:
                    output.write(fors.read(1))
            if string_field or number_field:
                format_chars = True
                semicolon = util.skip_white_read_if(ins, (';', ','))
    if not semicolon:
        output.write_line()
    util.require(ins, tk.end_statement)

def exec_lprint(ins):
    """ LPRINT: Write expressions to printer LPT1. """
    exec_print(ins, state.io_state.lpt1_file)

def exec_view_print(ins):
    """ VIEW PRINT: set scroll region. """
    if util.skip_white(ins) in tk.end_statement:
        console.unset_view()
    else:
        start = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, (tk.TO,))
        stop = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require(ins, tk.end_statement)
        max_line = 25 if (pcjr_syntax and not state.console_state.keys_visible) else 24
        util.range_check(1, max_line, start, stop)
        console.set_view(start, stop)

def exec_width(ins):
    """ WIDTH: set width of screen or device. """
    d = util.skip_white(ins)
    if d == '#':
        dev = expressions.parse_file_number(ins)
        w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    elif d == tk.LPRINT:
        ins.read(1)
        dev = state.io_state.lpt1_file
        w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        if d in tk.number:
            expr = expressions.parse_expr_unit(ins)
        else:
            expr = expressions.parse_expression(ins)
        if expr[0] == '$':
            devname = str(vartypes.pass_string_unpack(expr)).upper()
            try:
                dev = state.io_state.devices[devname].device_file
            except (KeyError, AttributeError):
                # bad file name
                raise error.RunError(error.BAD_FILE_NAME)
            util.require_read(ins, (',',))
            w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        else:
            dev = state.io_state.scrn_file
            # IN GW-BASIC, we can do calculations, but they must be bracketed...
            #w = vartypes.pass_int_unpack(expressions.parse_expr_unit(ins))
            w = vartypes.pass_int_unpack(expr)
            if util.skip_white_read_if(ins, (',',)):
                # pare dummy number rows setting
                num_rows_dummy = expressions.parse_expression(ins, allow_empty=True)
                if num_rows_dummy is not None:
                    min_num_rows = 0 if pcjr_syntax else 25
                    util.range_check(min_num_rows, 25, vartypes.pass_int_unpack(num_rows_dummy))
                # trailing comma is accepted
                util.skip_white_read_if(ins, (',',))
            # gives illegal function call, not syntax error
        util.require(ins, tk.end_statement, err=error.IFC)
    util.require(ins, tk.end_statement)
    dev.set_width(w)

def exec_screen(ins):
    """ SCREEN: change video mode or page. """
    if pcjr_syntax:
        mode, color, apagenum, vpagenum, erase = expressions.parse_int_list(ins, 5)
    else:
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before:
        mode, color, apagenum, vpagenum = expressions.parse_int_list(ins, 4)
        erase = 1
    # if any parameter not in [0,255], error 5 without doing anything
    # if the parameters are outside narrow ranges
    # (e.g. not implemented screen mode, pagenum beyond max)
    # then the error is only raised after changing the palette.
    util.range_check(0, 255, mode, color, apagenum, vpagenum)
    util.range_check(0, 2, erase)
    util.require(ins, tk.end_statement)
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

def exec_pcopy(ins):
    """ PCOPY: copy video pages. """
    src = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, state.console_state.screen.mode.num_pages-1, src)
    util.require_read(ins, (',',))
    dst = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require(ins, tk.end_statement)
    util.range_check(0, state.console_state.screen.mode.num_pages-1, dst)
    state.console_state.screen.copy_page(src, dst)


prepare()
