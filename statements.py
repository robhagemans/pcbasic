"""
PC-BASIC 3.23 - statements.py
Statement parser
 
(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import os
from functools import partial
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import plat
import config
import backend
import console
import debug
import draw_and_play
import error
import expressions
import flow
import fp
import graphics
import iolayer
import machine
import memory
import oslayer
import program
import representation
import reset
import rnd
import state
import timedate
import tokenise
import util
import var
import vartypes
import backend

def prepare():
    """ Initialise statements module. """
    global pcjr_syntax, pcjr_term
    if config.options['syntax'] in ('pcjr', 'tandy'):
        pcjr_syntax = config.options['syntax']
    else:
        pcjr_syntax = None    
    # find program for PCjr TERM command    
    pcjr_term = config.options['pcjr-term']
    if pcjr_term and not os.path.exists(pcjr_term):
        pcjr_term = os.path.join(plat.info_dir, pcjr_term)
    if not os.path.exists(pcjr_term):
        pcjr_term = ''
        

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
        elif c == '\x00':
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
                    raise error.RunError(19, prepos-1) 
                # stream has ended
                return False
            if state.basic_state.tron:
                console.write('[' + ('%i' % linenum) + ']')
            debug.debug_step(linenum)
        elif c == ':':
            ins.read(1)    
        c = util.skip_white(ins).upper()
        # empty statement, return to parse next
        if c in util.end_statement:
            return True
        # implicit LET
        elif c >= 'A' and c <= 'Z' :
            exec_let(ins)
        # token
        else:
            ins.read(1)        
            if   c == '\x81':     exec_end(ins)
            elif c == '\x82':     exec_for(ins)
            elif c == '\x83':     exec_next(ins)
            elif c == '\x84':     exec_data(ins)
            elif c == '\x85':     exec_input(ins)
            elif c == '\x86':     exec_dim(ins)
            elif c == '\x87':     exec_read(ins)
            elif c == '\x88':     exec_let(ins)
            elif c == '\x89':     exec_goto(ins)
            elif c == '\x8A':     exec_run(ins)
            elif c == '\x8B':     exec_if(ins)
            elif c == '\x8C':     exec_restore(ins)
            elif c == '\x8D':     exec_gosub(ins)
            elif c == '\x8E':     exec_return(ins)
            elif c == '\x8F':     exec_rem(ins)
            elif c == '\x90':     exec_stop(ins)
            elif c == '\x91':     exec_print(ins)
            elif c == '\x92':     exec_clear(ins)  
            elif c == '\x93':     exec_list(ins)      
            elif c == '\x94':     exec_new(ins)
            elif c == '\x95':     exec_on(ins)
            elif c == '\x96':     exec_wait(ins)
            elif c == '\x97':     exec_def(ins)
            elif c == '\x98':     exec_poke(ins)
            elif c == '\x99':     exec_cont(ins)
            elif c == '\x9C':     exec_out(ins)
            elif c == '\x9D':     exec_lprint(ins)
            elif c == '\x9E':     exec_llist(ins)    
            elif c == '\xA0':     exec_width(ins)    
            elif c == '\xA1':     exec_else(ins)    
            elif c == '\xA2':     exec_tron(ins)
            elif c == '\xA3':     exec_troff(ins)
            elif c == '\xA4':     exec_swap(ins)
            elif c == '\xA5':     exec_erase(ins)
            elif c == '\xA6':     exec_edit(ins)
            elif c == '\xA7':     exec_error(ins)
            elif c == '\xA8':     exec_resume(ins)
            elif c == '\xA9':     exec_delete(ins)
            elif c == '\xAA':     exec_auto(ins)
            elif c == '\xAB':     exec_renum(ins)
            elif c == '\xAC':     exec_defstr(ins)
            elif c == '\xAD':     exec_defint(ins)
            elif c == '\xAE':     exec_defsng(ins)
            elif c == '\xAF':     exec_defdbl(ins)    
            elif c == '\xB0':     exec_line(ins)
            elif c == '\xB1':     exec_while(ins)
            elif c == '\xB2':     exec_wend(ins)
            elif c == '\xB3':     exec_call(ins)
            elif c == '\xB7':     exec_write(ins)
            elif c == '\xB8':     exec_option(ins)
            elif c == '\xB9':     exec_randomize(ins)
            elif c == '\xBA':     exec_open(ins)
            elif c == '\xBB':     exec_close(ins)
            elif c == '\xBC':     exec_load(ins)
            elif c == '\xBD':     exec_merge(ins)
            elif c == '\xBE':     exec_save(ins)
            elif c == '\xBF':     exec_color(ins)
            elif c == '\xC0':     exec_cls(ins)
            elif c == '\xC1':     exec_motor(ins)        
            elif c == '\xC2':     exec_bsave(ins)        
            elif c == '\xC3':     exec_bload(ins)        
            elif c == '\xC4':     exec_sound(ins)        
            elif c == '\xC5':     exec_beep(ins)        
            elif c == '\xC6':     exec_pset(ins)        
            elif c == '\xC7':     exec_preset(ins)        
            elif c == '\xC8':     exec_screen(ins)
            elif c == '\xC9':     exec_key(ins)
            elif c == '\xCA':     exec_locate(ins)
            # two-byte tokens
            elif c == '\xFD':
                ins.read(1)
                # syntax error; these are all expression tokens, not statement tokens.
                raise error.RunError(2)
            # two-byte tokens
            elif c == '\xFE':
                c = ins.read(1)
                if   c == '\x81':    exec_files(ins)
                elif c == '\x82':    exec_field(ins)
                elif c == '\x83':    exec_system(ins)
                elif c == '\x84':    exec_name(ins)
                elif c == '\x85':    exec_lset(ins)
                elif c == '\x86':    exec_rset(ins)
                elif c == '\x87':    exec_kill(ins)
                elif c == '\x88':    exec_put(ins)
                elif c == '\x89':    exec_get(ins)
                elif c == '\x8A':    exec_reset(ins)
                elif c == '\x8B':    exec_common(ins)
                elif c == '\x8C':    exec_chain(ins)
                elif c == '\x8D':    exec_date(ins)
                elif c == '\x8E':    exec_time(ins)
                elif c == '\x8F':    exec_paint(ins)
                elif c == '\x90':    exec_com(ins)
                elif c == '\x91':    exec_circle(ins)
                elif c == '\x92':    exec_draw(ins)
                elif c == '\x93':    exec_play(ins)
                elif c == '\x94':    exec_timer(ins)
                elif c == '\x96':    exec_ioctl(ins)
                elif c == '\x97':    exec_chdir(ins)
                elif c == '\x98':    exec_mkdir(ins)
                elif c == '\x99':    exec_rmdir(ins)
                elif c == '\x9A':    exec_shell(ins)
                elif c == '\x9B':    exec_environ(ins)
                elif c == '\x9C':    exec_view(ins)
                elif c == '\x9D':    exec_window(ins)
                elif c == '\x9F':    exec_palette(ins)
                elif c == '\xA0':    exec_lcopy(ins)
                elif c == '\xA1':    exec_calls(ins)
                elif c == '\xA4':    exec_noise(ins)
                elif c == '\xA5':    exec_pcopy(ins)
                elif c == '\xA6':    exec_term(ins)
                elif c == '\xA7':    exec_lock(ins)
                elif c == '\xA8':    exec_unlock(ins)
                else: raise error.RunError(2)
            # two-byte tokens    
            elif c == '\xFF':
                c = ins.read(1)
                if   c == '\x83':   exec_mid(ins)
                elif c == '\xA0':   exec_pen(ins)
                elif c == '\xA2':   exec_strig(ins)
                elif c == '\xFF':   exec_debug(ins)
                else: raise error.RunError(2)
            else:
                raise error.RunError(2)
        return True
    except error.RunError as e:
        error.set_err(e)
        # don't jump if we're already busy handling an error
        if state.basic_state.on_error != None and state.basic_state.on_error != 0 and not state.basic_state.error_handle_mode:
            state.basic_state.error_resume = state.basic_state.current_statement, state.basic_state.run_mode
            flow.jump(state.basic_state.on_error)
            state.basic_state.error_handle_mode = True
            state.basic_state.suspend_all_events = True
            return True
        else:    
            raise e
        
#################################################################    
#################################################################

def exec_system(ins): 
    """ SYSTEM: exit interpreter. """
    # SYSTEM LAH does not execute 
    util.require(ins, util.end_statement)
    raise error.Exit()
        
def exec_tron(ins):
    """ TRON: turn on line number tracing. """
    state.basic_state.tron = True
    # TRON LAH gives error, but TRON has been executed
    util.require(ins, util.end_statement)

def exec_troff(ins):
    """ TROFF: turn off line number tracing. """
    state.basic_state.tron = False
    util.require(ins, util.end_statement)

def exec_rem(ins):
    """ REM: comment. """
    # skip the rest of the line, but parse numbers to avoid triggering EOL
    util.skip_to(ins, util.end_line)

def exec_lcopy(ins):    
    """ LCOPY: do nothing but check for syntax errors. """
    # See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY    
    if util.skip_white(ins) not in util.end_statement:
        util.range_check(0, 255, vartypes.pass_int_unpack(expressions.parse_expression(ins)))
        util.require(ins, util.end_statement)

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
    while util.peek(ins) not in util.end_line:
        debug_cmd += ins.read(1)
    debug.debug_exec(debug_cmd)

def exec_term(ins):
    """ TERM: load and run PCjr buitin terminal emulator program. """
    try:
        f = open(pcjr_term, 'rb')
    except (OSError, IOError):
        # on Tandy, raises Internal Error
        raise error.RunError(51)   
    util.require(ins, util.end_statement)
    program.load(f)
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
    if util.read_if(ins, c, ('\xD1',)): #FN
        exec_def_fn(ins)
    elif util.read_if(ins, c, ('\xD0',)): #USR
        exec_def_usr(ins)
    elif util.skip_white_read_if(ins, ('SEG',)):
        exec_def_seg(ins)
    else:        
        raise error.RunError(2)      

def exec_view(ins):
    """ VIEW: select VIEW PRINT, VIEW (graphics). """
    if util.skip_white_read_if(ins, ('\x91',)):  # PRINT
        exec_view_print(ins)
    else:
        exec_view_graph(ins)
    
def exec_line(ins):
    """ LINE: select LINE INPUT, LINE (graphics). """
    if util.skip_white_read_if(ins, ('\x85',)):  # INPUT
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
    if util.read_if(ins, c, ('\xA7',)):             # ERROR
        exec_on_error(ins)
    elif util.read_if(ins, c, ('\xC9',)):           # KEY
        exec_on_key(ins)
    elif c in ('\xFE', '\xFF'):
        c = util.peek(ins, 2)
        if util.read_if(ins, c, ('\xFE\x94',)):     # TIMER
            exec_on_timer(ins)
        elif util.read_if(ins, c, ('\xFE\x93',)):   # PLAY
            exec_on_play(ins)
        elif util.read_if(ins, c, ('\xFE\x90',)):   # COM
            exec_on_com(ins)
        elif util.read_if(ins, c, ('\xFF\xA0',)):  # PEN
            exec_on_pen(ins)
        elif util.read_if(ins, c, ('\xFF\xA2',)):  # STRIG
            exec_on_strig(ins)
        else:
            raise error.RunError(2)
    else:        
        exec_on_jump(ins)

##########################################################
# event switches (except PLAY, KEY) and event definitions

def exec_pen(ins):
    """ PEN: switch on/off light pen event handling. """
    if state.basic_state.pen_handler.command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)

def exec_strig(ins):
    """ STRIG: switch on/off fire button event handling. """
    d = util.skip_white(ins)
    if d == '(':
        # strig (n)
        num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        if num not in (0,2,4,6):
            raise error.RunError(5)
        if state.basic_state.strig_handlers[num//2].command(util.skip_white(ins)):
            ins.read(1)
        else:    
            raise error.RunError(2)
    elif d == '\x95': # ON
        ins.read(1)
        state.console_state.stick_is_on = True
    elif d == '\xDD': # OFF
        ins.read(1)
        state.console_state.stick_is_on = False
    else:
        raise error.RunError(2)
    util.require(ins, util.end_statement)

def exec_com(ins):    
    """ COM: switch on/off serial port event handling. """
    util.require(ins, ('(',))
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(1, 2, num)
    if state.basic_state.com_handlers[num].command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)

def exec_timer(ins):
    """ TIMER: switch on/off timer event handling. """
    if state.basic_state.timer_handler.command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)      


def parse_on_event(ins, bracket=True):
    """ Helper function for ON event trap definitions. """
    num = None
    if bracket:
        num = expressions.parse_bracket(ins)
    util.require_read(ins, ('\x8D',)) # GOSUB
    jumpnum = util.parse_jumpnum(ins)
    if jumpnum == 0:
        jumpnum = None
    elif jumpnum not in state.basic_state.line_numbers:
        raise error.RunError(8)    
    util.require(ins, util.end_statement)    
    return num, jumpnum   

def exec_on_key(ins):
    """ ON KEY: define key event trapping. """
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 20, keynum)
    state.basic_state.key_handlers[keynum-1].gosub = jumpnum

def exec_on_timer(ins):
    """ ON TIMER: define timer event trapping. """
    timeval, jumpnum = parse_on_event(ins)
    timeval = vartypes.pass_single_keep(timeval)
    state.basic_state.timer_period = fp.mul(fp.unpack(timeval), fp.Single.from_int(1000)).round_to_int()
    state.basic_state.timer_handler.gosub = jumpnum

def exec_on_play(ins):
    """ ON PLAY: define music event trapping. """
    playval, jumpnum = parse_on_event(ins)
    playval = vartypes.pass_int_unpack(playval)
    state.basic_state.play_trig = playval
    state.basic_state.play_handler.gosub = jumpnum
    
def exec_on_pen(ins):
    """ ON PEN: define light pen event trapping. """
    _, jumpnum = parse_on_event(ins, bracket=False)
    state.basic_state.pen_handler.gosub = jumpnum
    
def exec_on_strig(ins):
    """ ON STRIG: define fire button event trapping. """
    strigval, jumpnum = parse_on_event(ins)
    strigval = vartypes.pass_int_unpack(strigval)
    ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
    if strigval not in (0,2,4,6):
        raise error.RunError(5)
    state.basic_state.strig_handlers[strigval//2].gosub = jumpnum
    
def exec_on_com(ins):
    """ ON COM: define serial port event trapping. """
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 2, keynum)
    state.basic_state.com_handlers[keynum-1].gosub = jumpnum

##########################################################
# sound

def exec_beep(ins):
    """ BEEP: produce an alert sound or switch internal speaker on/off. """
    # Tandy/PCjr BEEP ON, OFF
    if pcjr_syntax and util.skip_white(ins) in ('\x95', '\xDD'):
        state.console_state.beep_on = (ins.read(1) == '\x95')
        util.require(ins, util.end_statement)
        return
    state.console_state.sound.beep() 
    # if a syntax error happens, we still beeped.
    util.require(ins, util.end_statement)
    if state.console_state.sound.foreground:
        state.console_state.sound.wait_music(wait_last=False)
    
def exec_sound(ins):
    """ SOUND: produce an arbitrary sound or switch external speaker on/off. """
    # Tandy/PCjr SOUND ON, OFF
    if pcjr_syntax and util.skip_white(ins) in ('\x95', '\xDD'):
        state.console_state.sound.sound_on = (ins.read(1) == '\x95')
        util.require(ins, util.end_statement)
        return
    freq = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(5)
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
    util.require(ins, util.end_statement)
    if dur.is_zero():
        state.console_state.sound.stop_all_sound()
        return
    # Tandy only allows frequencies below 37 (but plays them as 110 Hz)    
    if freq != 0:
        util.range_check(-32768 if backend.pcjr_sound == 'tandy' else 37, 32767, freq) # 32767 is pause
    # calculate duration in seconds   
    one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
    dur_sec = dur.to_value()/18.2
    if one_over_44.gt(dur):
        # play indefinitely in background
        state.console_state.sound.play_sound(freq, dur_sec, loop=True, voice=voice, volume=volume)
    else:
        state.console_state.sound.play_sound(freq, dur_sec, voice=voice, volume=volume)
        if state.console_state.sound.foreground:
            state.console_state.sound.wait_music(wait_last=False)
    
def exec_play(ins):
    """ PLAY: play sound sequence defined by a Music Macro Language string. """
    if state.basic_state.play_handler.command(util.skip_white(ins)):
        ins.read(1)
        util.require(ins, util.end_statement)
    else:    
        # retrieve Music Macro Language string
        mml0 = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        mml1, mml2 = '', ''
        if ((pcjr_syntax == 'tandy' or (pcjr_syntax == 'pcjr' and 
                                         state.console_state.sound.sound_on))
                and util.skip_white_read_if(ins, (',',))):
            mml1 = vartypes.pass_string_unpack(expressions.parse_expression(ins))
            if util.skip_white_read_if(ins, (',',)):
                mml2 = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_expression)
        draw_and_play.play_parse_mml((mml0, mml1, mml2))
          
def exec_noise(ins):
    """ NOISE: produce sound on the noise generator (Tandy/PCjr). """
    if not state.console_state.sound.sound_on:
        raise error.RunError(5)
    source = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    volume = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    util.range_check(0, 7, source)
    util.range_check(0, 15, volume)
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(5)
    util.require(ins, util.end_statement)        
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
        raise error.RunError(5)
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    machine.poke(addr, val)
    util.require(ins, util.end_statement)
    
def exec_def_seg(ins):
    """ DEF SEG: set the current memory segment. """
    # &hb800: text screen buffer; &h13d: data segment
    if util.skip_white_read_if(ins, ('\xE7',)): #=
        state.basic_state.segment = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    else:
        state.basic_state.segment = memory.data_segment   
    if state.basic_state.segment < 0:
        state.basic_state.segment += 0x10000     
    util.require(ins, util.end_statement)

def exec_def_usr(ins):
    """ DEF USR: Define a machine language function. Not implemented. """
    if util.peek(ins) in ('\x11','\x12','\x13','\x14','\x15','\x16','\x17','\x18','\x19','\x1a'): # digits 0--9
        ins.read(1)
    util.require_read(ins, ('\xE7',))     
    vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=0xffff)
    util.require(ins, util.end_statement)
    logging.warning("DEF USR statement not implemented")

def exec_bload(ins):
    """ BLOAD: load a file into a memory location. Limited implementation. """
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(5)
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    offset = None
    if util.skip_white_read_if(ins, (',',)):
        offset = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
        if offset < 0:
            offset += 0x10000           
    util.require(ins, util.end_statement)
    machine.bload(iolayer.open_file_or_device(0, name, mode='L', defext=''), offset)
    
def exec_bsave(ins):
    """ BSAVE: save a block of memory to a file. Limited implementation. """
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(5)
    namade = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    util.require_read(ins, (',',))
    offset = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint = 0xffff) 
    if offset < 0:
        offset += 0x10000         
    util.require_read(ins, (',',))
    length = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint = 0xffff)        
    if length < 0:
        length += 0x10000         
    util.require(ins, util.end_statement)
    machine.bsave(iolayer.open_file_or_device(0, name, mode='S', defext=''), offset, length)

def exec_call(ins):
    """ CALL: call an external procedure. Not implemented. """
    addr_var = util.get_var_name(ins)
    if addr_var[-1] == '$':
        # type mismatch
        raise error.RunError(13)
    if util.skip_white_read_if(ins, ('(',)):
        while True:
            # if we wanted to call a function, we should distinguish varnames 
            # (passed by ref) from constants (passed by value) here.
            expressions.parse_expression(ins)
            if not util.skip_white_read_if(ins, (',',)):
                break
        util.require_read(ins, (')',))        
    util.require(ins, util.end_statement)
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
    util.require(ins, util.end_statement)

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
    util.require(ins, util.end_statement)
    machine.wait(addr, ander, xorer)

##########################################################
# OS
    
def exec_chdir(ins):
    """ CHDIR: change working directory. """
    oslayer.chdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_mkdir(ins):
    """ MKDIR: create directory. """
    oslayer.mkdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_rmdir(ins):
    """ RMDIR: remove directory. """
    oslayer.rmdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_name(ins):
    """ NAME: rename file or directory. """
    oldname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # don't rename open files
    iolayer.check_file_not_open(oldname)
    # AS is not a tokenised word
    word = util.skip_white_read(ins) + ins.read(1)
    if word.upper() != 'AS':
        raise error.RunError(2)
    newname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oslayer.rename(oldname, newname)
    util.require(ins, util.end_statement)

def exec_kill(ins):
    """ KILL: remove file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # don't delete open files
    iolayer.check_file_not_open(name)
    oslayer.kill(name)
    util.require(ins, util.end_statement)

def exec_files(ins):
    """ FILES: output directory listing. """
    pathmask = ''
    if util.skip_white(ins) not in util.end_statement:
        pathmask = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        if not pathmask:
            # bad file name
            raise error.RunError(64)
    oslayer.files(pathmask)
    util.require(ins, util.end_statement)
    
def exec_shell(ins):
    """ SHELL: open OS shell and optionally execute command. """
    # parse optional shell command
    if util.skip_white(ins) in util.end_statement:
        cmd = ''
    else:
        cmd = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # no SHELL on PCjr.
    if pcjr_syntax == 'pcjr':
        raise error.RunError(5)
    # force cursor visible in all cases
    backend.show_cursor(True)
    # execute cms or open interactive shell
    oslayer.shell(cmd) 
    # reset cursor visibility to its previous state
    backend.update_cursor_visibility()
    util.require(ins, util.end_statement)
        
def exec_environ(ins):
    """ ENVIRON: set environment string. """
    envstr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    eqs = envstr.find('=')
    if eqs <= 0:
        raise error.RunError(5)
    envvar = str(envstr[:eqs])
    val = str(envstr[eqs+1:])
    os.environ[envvar] = val
    util.require(ins, util.end_statement)
       
def exec_time(ins):
    """ TIME$: set time. """
    util.require_read(ins, ('\xE7',)) #time$=
    # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
    timestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    timedate.set_time(timestr)

def exec_date(ins):
    """ DATE$: set date. """
    util.require_read(ins, ('\xE7',)) # date$=
    # allowed formats:
    # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
    # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
    datestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    timedate.set_date(datestr)

##########################################################
# code
    
def parse_line_range(ins):
    """ Helper function: parse line number ranges. """
    from_line = parse_jumpnum_or_dot(ins, allow_empty=True)    
    if util.skip_white_read_if(ins, ('\xEA',)):   # -
        to_line = parse_jumpnum_or_dot(ins, allow_empty=True)
    else:
        to_line = from_line
    return (from_line, to_line)    

def parse_jumpnum_or_dot(ins, allow_empty=False, err=2):
    """ Helper function: parse jump target. """
    c = util.skip_white_read(ins)
    if c == '\x0E':
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
    util.require(ins, util.end_statement)
    # throws back to direct mode
    program.delete(from_line, to_line)
    # clear all variables
    reset.clear()

def exec_edit(ins):
    """ EDIT: output a program line and position cursor for editing. """
    if util.skip_white(ins) in util.end_statement:
        # undefined line number
        raise error.RunError(8)    
    from_line = parse_jumpnum_or_dot(ins, err=5)
    if from_line == None or from_line not in state.basic_state.line_numbers:
        raise error.RunError(8)
    util.require(ins, util.end_statement, err=5)
    # throws back to direct mode
    flow.set_pointer(False)
    state.basic_state.execute_mode = False    
    # request edit prompt
    state.basic_state.prompt = (from_line, None)
    
def exec_auto(ins):
    """ AUTO: enter automatic line numbering mode. """
    linenum = parse_jumpnum_or_dot(ins, allow_empty=True)
    increment = None
    if util.skip_white_read_if(ins, (',',)): 
        increment = util.parse_jumpnum(ins, allow_empty=True)
    util.require(ins, util.end_statement)
    # reset linenum and increment on each call of AUTO (even in AUTO mode)
    state.basic_state.auto_linenum = linenum if linenum != None else 10
    state.basic_state.auto_increment = increment if increment != None else 10    
    # move program pointer to end
    flow.set_pointer(False)
    # continue input in AUTO mode
    state.basic_state.auto_mode = True
    
def exec_list(ins):
    """ LIST: output program lines. """
    from_line, to_line = parse_line_range(ins)
    if util.skip_white_read_if(ins, (',',)):
        out = iolayer.open_file_or_device(0, vartypes.pass_string_unpack(expressions.parse_expression(ins)), 'O')
    else:
        out = backend.devices['SCRN:']
    util.require(ins, util.end_statement)
    program.list_lines(out, from_line, to_line)    

def exec_llist(ins):
    """ LLIST: output program lines to LPT1: """
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    program.list_lines(backend.devices['LPT1:'], from_line, to_line)
        
def exec_load(ins):
    """ LOAD: load program from file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    comma = util.skip_white_read_if(ins, (',',))
    if comma:
        util.require_read(ins, 'R')
    util.require(ins, util.end_statement)
    program.load(iolayer.open_file_or_device(0, name, mode='L', defext='BAS'))
    reset.clear()
    if comma:
        # in ,R mode, don't close files; run the program
        flow.jump(None)
    else:
        iolayer.close_all()
    state.basic_state.tron = False    
        
def exec_chain(ins):
    """ CHAIN: load program and chain execution. """
    if util.skip_white_read_if(ins, ('\xBD',)): # MERGE
        action = program.merge
    else:   
        action = program.load
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    jumpnum, common_all, delete_lines = None, False, None    
    if util.skip_white_read_if(ins, (',',)):
        # check for an expression that indicates a line in the other program. This is not stored as a jumpnum (to avoid RENUM)
        expr = expressions.parse_expression(ins, allow_empty=True)
        if expr != None:
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
    util.require(ins, util.end_statement)
    if state.basic_state.protected and action == program.merge:
            raise error.RunError(5)
    program.chain(action, iolayer.open_file_or_device(0, name, mode='L', defext='BAS'), jumpnum, delete_lines)
    # preserve DEFtype on MERGE
    reset.clear(preserve_common=True, preserve_all=common_all, preserve_deftype=(action==program.merge))

def parse_delete_clause(ins):
    """ Helper function: parse the DELETE clause of a CHAIN statement. """
    delete_lines = None
    if util.skip_white_read_if(ins, ('\xa9',)): # DELETE
        from_line = util.parse_jumpnum(ins, allow_empty=True)    
        if util.skip_white_read_if(ins, ('\xEA',)):   # -
            to_line = util.parse_jumpnum(ins, allow_empty=True)
        else:
            to_line = from_line
        # to_line must be specified and must be an existing line number
        if not to_line or to_line not in state.basic_state.line_numbers:
            raise error.RunError(5)    
        delete_lines = (from_line, to_line)
        # ignore rest if preceded by cmma
        if util.skip_white_read_if(ins, (',',)):
            util.skip_to(ins, util.end_statement)
    return delete_lines

def exec_save(ins):
    """ SAVE: save program to a file. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    mode = 'B'
    if util.skip_white_read_if(ins, (',',)):
        mode = util.skip_white_read(ins).upper()
        if mode not in ('A', 'P'):
            raise error.RunError(2)
    program.save(iolayer.open_file_or_device(0, name, mode='S', defext='BAS'), mode)
    util.require(ins, util.end_statement)
    
def exec_merge(ins):
    """ MERGE: merge lines from file into current program. """
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    program.merge(iolayer.open_file_or_device(0, name, mode='L', defext='BAS') )
    util.require(ins, util.end_statement)
    
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
    if util.skip_white(ins) not in util.end_statement: 
        new = parse_jumpnum_or_dot(ins, allow_empty=True)
        if util.skip_white_read_if(ins, (',',)):
            old = parse_jumpnum_or_dot(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                step = util.parse_jumpnum(ins, allow_empty=True) # returns -1 if empty
    util.require(ins, util.end_statement)            
    if step != None and step < 1: 
        raise error.RunError(5)
    program.renum(new, old, step)
    

##########################################################
# file

def exec_reset(ins):
    """ RESET: close all files. """
    iolayer.close_all()
    util.require(ins, util.end_statement)

def parse_read_write(ins):
    """ Helper function: parse access mode. """
    d = util.skip_white(ins)
    if d == '\xB7': # WRITE
        ins.read(1)
        access = 'W'        
    elif d == '\x87': # READ
        ins.read(1)
        access = 'RW' if util.skip_white_read_if(ins, ('\xB7',)) else 'R' # WRITE
    return access

long_modes = {'\x85':'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}  # \x85 is INPUT
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
            # Bad file mode
            raise error.RunError(54)
        number = expressions.parse_file_number_opthash(ins)
        util.require_read(ins, (',',))
        name = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
        if util.skip_white_read_if(ins, (',',)):
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        # second syntax
        name = first_expr
        # FOR clause
        if util.skip_white_read_if(ins, ('\x82',)): # FOR
            c = util.skip_white_read(ins)
            # read word
            word = ''
            while c not in util.whitespace:
                word += c
                c = ins.read(1).upper()
            try:
                mode = long_modes[word]
            except KeyError:
                raise error.RunError(2)
        try:
            access = default_access_modes[mode]    
        except (KeyError):
            # Bad file mode
            raise error.RunError(54)        
        # ACCESS clause
        if util.skip_white_read_if(ins, ('ACCESS',)):
            util.skip_white(ins)
            access = parse_read_write(ins)
        # LOCK clause
        if util.skip_white_read_if(ins, ('\xFE\xA7',)): # LOCK
            util.skip_white(ins)
            lock = parse_read_write(ins)
        elif util.skip_white_read_if(ins, ('SHARED',)):
            lock = 'S'  
        # AS file number clause       
        if not util.skip_white_read_if(ins, ('AS',)):
            raise error.RunError(2)
        number = expressions.parse_file_number_opthash(ins)
        # LEN clause
        if util.skip_white_read_if(ins, ('\xFF\x92',)):  # LEN
            util.require_read(ins, '\xE7') # =
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    # mode and access must match if not a RANDOM file
    # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
    # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
    if mode == 'A' and access == 'W':
        raise error.RunError(75)
    elif mode != 'R' and access and access != default_access_modes[mode]:
        raise error.RunError(2)        
    util.range_check(1, iolayer.max_reclen, reclen)        
    iolayer.open_file_or_device(number, name, mode, access, lock, reclen) 
    util.require(ins, util.end_statement)
                
def exec_close(ins):
    """ CLOSE: close a file. """
    if util.skip_white(ins) in util.end_statement:
        # allow empty CLOSE; close all open files
        iolayer.close_all()
    else:    
        while True:
            number = expressions.parse_file_number_opthash(ins)
            try:    
                state.io_state.files[number].close()
            except KeyError:
                pass    
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, util.end_statement)
            
def exec_field(ins):
    """ FIELD: link a string variable to record buffer. """
    the_file = iolayer.get_file(expressions.parse_file_number_opthash(ins), 'R')
    if util.skip_white_read_if(ins, (',',)):
        offset = 0    
        while True:
            width = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            util.range_check(0, 255, width)
            util.require_read(ins, ('AS',), err=5)
            name, index = expressions.get_var_or_array_name(ins)
            var.set_field_var_or_array(the_file, name, index, offset, width)         
            offset += width
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, util.end_statement)

def parse_get_or_put_file(ins):
    """ Helper function: PUT and GET syntax. """
    the_file = iolayer.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, (',',)):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
        util.range_check_err(1, 2**25, pos, err=63) # not 2^32-1 as the manual boasts! pos-1 needs to fit in a single-prec mantissa
        if not isinstance(the_file, iolayer.COMFile):
            the_file.set_pos(pos)    
        else:
            num_bytes = pos    
    return the_file, num_bytes        
    
def exec_put_file(ins):
    """ PUT: write record to file. """
    thefile, num_bytes = parse_get_or_put_file(ins) 
    thefile.write_field(num_bytes)
    util.require(ins, util.end_statement)

def exec_get_file(ins):
    """ GET: read record from file. """
    thefile, num_bytes = parse_get_or_put_file(ins) 
    thefile.read_field(num_bytes)
    util.require(ins, util.end_statement)
    
def exec_lock_or_unlock(ins, action):
    """ LOCK or UNLOCK: set file or record locks. """
    thefile = iolayer.get_file(expressions.parse_file_number_opthash(ins))
    lock_start_rec = 1
    if util.skip_white_read_if(ins, (',',)):
        lock_start_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
    lock_stop_rec = lock_start_rec
    if util.skip_white_read_if(ins, ('\xCC',)): # TO
        lock_stop_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
    if lock_start_rec < 1 or lock_start_rec > 2**25-2 or lock_stop_rec < 1 or lock_stop_rec > 2**25-2:   
        raise error.RunError(63)
    action(thefile.number, lock_start_rec, lock_stop_rec)
    util.require(ins, util.end_statement)

exec_lock = partial(exec_lock_or_unlock, action = iolayer.lock_records)
exec_unlock = partial(exec_lock_or_unlock, action = iolayer.unlock_records)
    
def exec_ioctl(ins):
    """ IOCTL: send control string to I/O device. Not implemented. """
    iolayer.get_file(expressions.parse_file_number_opthash(ins))
    logging.warning("IOCTL statement not implemented.")
    raise error.RunError(5)   
    
##########################################################
# Graphics statements

def parse_coord(ins, absolute=False):
    """ Helper function: parse coordinate pair. """
    step = not absolute and util.skip_white_read_if(ins, ('\xCF',)) # STEP
    util.require_read(ins, ('(',))
    x = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (',',))
    y = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    util.require_read(ins, (')',))
    if absolute:
        return x, y
    state.console_state.last_point = graphics.window_coords(x, y, step)
    return state.console_state.last_point

def exec_pset(ins, c=-1):
    """ PSET: set a pixel to a given attribute, or foreground. """
    graphics.require_graphics_mode()
    x, y = parse_coord(ins)
    state.console_state.last_point = x, y
    if util.skip_white_read_if(ins, (',',)):
        c = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(-1, 255, c)
    util.require(ins, util.end_statement)    
    graphics.put_point(x, y, c)

def exec_preset(ins):
    """ PRESET: set a pixel to a given attribute, or background. """
    exec_pset(ins, 0)   

def exec_line_graph(ins):
    """ LINE: draw a line between two points. """
    graphics.require_graphics_mode()
    if util.skip_white(ins) in ('(', '\xCF'):
        x0, y0 = parse_coord(ins)
        state.console_state.last_point = x0, y0
    else:
        x0, y0 = state.console_state.last_point
    util.require_read(ins, ('\xEA',)) # -
    x1, y1 = parse_coord(ins)
    state.console_state.last_point = x1, y1
    c, mode, mask = -1, '', 0xffff
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
                mask = vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=22), maxint=0x7fff)
        elif not expr:
            raise error.RunError(22)        
    util.require(ins, util.end_statement)    
    if mode == '':
        graphics.draw_line(x0, y0, x1, y1, c, mask)
    elif mode == 'B':
        graphics.draw_box(x0, y0, x1, y1, c, mask)
    elif mode == 'BF':
        graphics.draw_box_filled(x0, y0, x1, y1, c)
            
def exec_view_graph(ins):
    """ VIEW: set graphics viewport. """
    graphics.require_graphics_mode()
    absolute = util.skip_white_read_if(ins, ('\xC8',)) #SCREEN
    if util.skip_white_read_if(ins, '('):
        x0 = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, (',',))
        y0 = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, (')',))
        util.require_read(ins, ('\xEA',)) #-
        util.require_read(ins, ('(',))
        x1 = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, (',',))
        y1 = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, (')',))
        util.range_check(0, state.console_state.screen.mode.pixel_width-1, x0, x1)
        util.range_check(0, state.console_state.screen.mode.pixel_height-1, y0, y1)
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        fill, border = None, None
        if util.skip_white_read_if(ins, (',',)):
            fill, border = expressions.parse_int_list(ins, 2, err=2)
        state.console_state.screen.set_view(x0-1, y0-1, x1+1, y1+1, True)
        if fill != None:
            graphics.draw_box_filled(x0, y0, x1, y1, fill)
        if border != None:
            graphics.draw_box(x0-1, y0-1, x1+1, y1+1, border)
        state.console_state.screen.set_view(x0, y0, x1, y1, absolute)
    else:
        state.console_state.screen.unset_view()
    util.require(ins, util.end_statement)        
    
def exec_window(ins):
    """ WINDOW: define logical coordinate system. """
    graphics.require_graphics_mode()
    cartesian = not util.skip_white_read_if(ins, ('\xC8',)) #SCREEN
    if util.skip_white(ins) == '(':
        x0, y0 = parse_coord(ins, absolute=True)
        util.require_read(ins, ('\xEA',)) #-
        x1, y1 = parse_coord(ins, absolute=True)
        if x0.equals(x1) or y0.equals(y1):
            raise error.RunError(5)
        graphics.set_graph_window(x0, y0, x1, y1, cartesian)
    else:
        graphics.unset_graph_window()
    util.require(ins, util.end_statement)        
        
def exec_circle(ins):
    """ CIRCLE: Draw a circle, ellipse, arc or sector. """
    graphics.require_graphics_mode()
    x0, y0 = parse_coord(ins)
    state.console_state.last_point = x0, y0
    util.require_read(ins, (',',))
    r = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    start, stop, c = None, None, -1
    aspect = fp.div(
        fp.Single.from_int(state.console_state.pixel_aspect_ratio[0]), 
        fp.Single.from_int(state.console_state.pixel_aspect_ratio[1]))
    if util.skip_white_read_if(ins, (',',)):
        cval = expressions.parse_expression(ins, allow_empty=True)
        if cval:
            c = vartypes.pass_int_unpack(cval)
        if util.skip_white_read_if(ins, (',',)):
            start = expressions.parse_expression(ins, allow_empty=True)
            if util.skip_white_read_if(ins, (',',)):
                stop = expressions.parse_expression(ins, allow_empty=True)
                if util.skip_white_read_if(ins, (',',)):
                    aspect = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
                elif stop == None:
                    raise error.RunError(22) # missing operand
            elif start == None:
                raise error.RunError(22) 
        elif cval == None:
            raise error.RunError(22)                     
    util.require(ins, util.end_statement)    
    graphics.draw_circle_or_ellipse(x0, y0, r, start, stop, c, aspect)
      
def exec_paint(ins):
    """ PAINT: flood fill from point. """
    # if paint *colour* specified, border default = paint colour
    # if paint *attribute* specified, border default = current foreground      
    graphics.require_graphics_mode()
    x0, y0 = parse_coord(ins)
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
                raise error.RunError(5)
            # default for border, if pattern is specified as string: foreground attr
        else:
            c = vartypes.pass_int_unpack(cval)
        border = c    
        if util.skip_white_read_if(ins, (',',)):
            bval = expressions.parse_expression(ins, allow_empty=True)
            if bval:
                border = vartypes.pass_int_unpack(bval)
            if util.skip_white_read_if(ins, (',',)):
                background_pattern = vartypes.pass_string_unpack(expressions.parse_expression(ins), err=5)
                # only in screen 7,8,9 is this an error (use ega memory as a check)
                if (pattern and background_pattern[:len(pattern)] == pattern and 
                        state.console_state.screen.mode.mem_start == 0xa000):
                    raise error.RunError(5)
    util.require(ins, util.end_statement)  
    graphics.flood_fill(x0, y0, pattern, c, border, background_pattern)
                
def exec_get_graph(ins):
    """ GET: read a sprite to memory. """
    graphics.require_graphics_mode()
    util.require(ins, ('(')) # don't accept STEP
    x0,y0 = parse_coord(ins)
    util.require_read(ins, ('\xEA',)) #-
    util.require(ins, ('(', '\xCF')) # STEP
    x1,y1 = parse_coord(ins)
    util.require_read(ins, (',',)) 
    array = util.get_var_name(ins)    
    util.require(ins, util.end_statement)
    if array not in state.basic_state.arrays:
        raise error.RunError(5)
    elif array[-1] == '$':
        raise error.RunError(13) # type mismatch    
    graphics.get_area(x0, y0, x1, y1, array)
    
def exec_put_graph(ins):
    """ PUT: draw sprite on screen. """
    graphics.require_graphics_mode()
    util.require(ins, ('(')) # don't accept STEP
    x0,y0 = parse_coord(ins)
    util.require_read(ins, (',',)) 
    array = util.get_var_name(ins)    
    action = '\xF0' # graphics.operation_xor
    if util.skip_white_read_if(ins, (',',)):
        util.require(ins, ('\xC6', '\xC7', '\xEE', '\xEF', '\xF0')) #PSET, PRESET, AND, OR, XOR
        action = ins.read(1)
    util.require(ins, util.end_statement)
    if array not in state.basic_state.arrays:
        raise error.RunError(5)
    elif array[-1] == '$':
        raise error.RunError(13) # type mismatch    
    graphics.set_area(x0, y0, array, action)
    
def exec_draw(ins):
    """ DRAW: draw a figure defined by a Graphics Macro Language string. """
    graphics.require_graphics_mode()
    gml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_expression)
    draw_and_play.draw_parse_gml(gml)
    
##########################################################
# Flow-control statements

def exec_end(ins):
    """ END: end program execution and return to interpreter. """
    util.require(ins, util.end_statement)
    state.basic_state.stop = state.basic_state.bytecode.tell()
    # jump to end of direct line so execution stops
    flow.set_pointer(False)
    # avoid NO RESUME
    state.basic_state.error_handle_mode = False
    state.basic_state.error_resume = None
    iolayer.close_all()
    
def exec_stop(ins):
    """ STOP: break program execution and return to interpreter. """
    util.require(ins, util.end_statement)
    raise error.Break(stop=True)
    
def exec_cont(ins):
    """ CONT: continue STOPped or ENDed execution. """
    if state.basic_state.stop == None:
        raise error.RunError(17)
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
        raise error.RunError(13)
    util.require_read(ins, ('\xE7',)) # =
    start = expressions.parse_expression(ins)
    util.require_read(ins, ('\xCC',))  # TO    
    stop = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))
    if util.skip_white_read_if(ins, ('\xCF',)): # STEP
        step = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))
    else:
        # convert 1 to vartype
        step = vartypes.pass_type_keep(vartype, vartypes.pack_int(1))
    util.require(ins, util.end_statement)
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
        c = util.skip_to_read(ins, util.end_statement + ('\xCD', '\xA1')) # THEN, ELSE
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
                    while (util.skip_white(ins) not in util.end_statement):
                        util.skip_to(ins, util.end_statement + (',',))
                        if util.peek(ins) == ',':
                            if stack > 0:
                                ins.read(1)
                                stack -= 1
                            else:
                                return
                                
def find_next(ins, varname):
    """ Helper function for FOR: find the right NEXT. """
    current = ins.tell()
    skip_to_next(ins, '\x82', '\x83', allow_comma=True)  # FOR, NEXT
    # FOR without NEXT
    util.require(ins, ('\x83', ','), err=26)
    comma = (ins.read(1)==',')
    # get position and line number just after the NEXT
    nextpos = ins.tell()
    # check var name for NEXT
    varname2 = util.get_var_name(ins, allow_empty=True)
    # no-var only allowed in standalone NEXT   
    if varname2 == '':
        util.require(ins, util.end_statement)
    if (comma or varname2) and varname2 != varname:
        # NEXT without FOR 
        errline = program.get_line_number(nextpos-1) if state.basic_state.run_mode else -1
        raise error.RunError(1, errline)    
    ins.seek(current)
    return nextpos 

def exec_next(ins):
    """ NEXT: iterate for-loop. """
    # jump to end of FOR, increment counter, check condition.
    if flow.loop_iterate(ins):
        util.skip_to(ins, util.end_statement+(',',))
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
    if c == '\x0e':   
        # parse line number, ignore rest of line and jump
        jumpnum = util.parse_jumpnum(ins)
    elif c not in util.end_statement:
        name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        program.load(iolayer.open_file_or_device(0, name, mode='L', defext='BAS'))
    flow.init_program()
    reset.clear(close_files=not comma)
    flow.jump(jumpnum)
    state.basic_state.error_handle_mode = False
                
def exec_if(ins):
    """ IF: enter branching statement. """
    # avoid overflow: don't use bools.
    val = vartypes.pass_single_keep(expressions.parse_expression(ins))
    util.skip_white_read_if(ins, (',',)) # optional comma
    util.require_read(ins, ('\xCD', '\x89')) # THEN, GOTO
    if not fp.unpack(val).is_zero(): 
        # TRUE: continue after THEN. line number or statement is implied GOTO
        if util.skip_white(ins) in ('\x0e',):  
            flow.jump(util.parse_jumpnum(ins))    
        # continue parsing as normal, :ELSE will be ignored anyway
    else:
        # FALSE: find ELSE block or end of line; ELSEs are nesting on the line
        nesting_level = 0
        while True:    
            d = util.skip_to_read(ins, util.end_statement + ('\x8B',)) # IF 
            if d == '\x8B': # IF
                # nexting step on IF. (it's less convenient to count THENs because they could be THEN, GOTO or THEN GOTO.)
                nesting_level += 1            
            elif d == ':':
                if util.skip_white_read_if(ins, '\xa1'): # :ELSE is ELSE; may be whitespace in between. no : means it's ignored.
                    if nesting_level > 0:
                        nesting_level -= 1
                    else:    
                        # line number: jump
                        if util.skip_white(ins) in ('\x0e',):
                            flow.jump(util.parse_jumpnum(ins))
                        # continue execution from here    
                        break
            else:
                ins.seek(-len(d), 1)
                break
              
def exec_else(ins):
    """ ELSE: part of branch statement; ignore. """
    # any else statement by itself means the THEN has already been executed, so it's really like a REM.
    util.skip_to(ins, util.end_line)  
    
def exec_while(ins, first=True):
    """ WHILE: enter while-loop. """
    # just after WHILE opcode
    whilepos = ins.tell()
    # evaluate the 'boolean' expression 
    # use double to avoid overflows  
    if first:
        # find matching WEND
        skip_to_next(ins, '\xB1', '\xB2')  # WHILE, WEND
        if ins.read(1) == '\xB2':
            util.skip_to(ins, util.end_statement)
            wendpos = ins.tell()
            state.basic_state.while_wend_stack.append((whilepos, wendpos)) 
        else: 
            # WHILE without WEND
            raise error.RunError(29)
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
    util.require(ins, util.end_statement)
    pos = ins.tell()
    while True:
        if not state.basic_state.while_wend_stack:
            # WEND without WHILE
            raise error.RunError(30) #1  
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
        if d in util.end_statement:
            ins.seek(-len(d), 1)
            break
        elif d in ('\x0e',):
            jumps.append( ins.tell()-1 ) 
            ins.read(2)
        elif d == ',':
            pass    
        else:  
            raise error.RunError(2)
    if jumps == []:
        raise error.RunError(2)
    elif onvar > 0 and onvar <= len(jumps):
        ins.seek(jumps[onvar-1])        
        if command == '\x89': # GOTO
            flow.jump(util.parse_jumpnum(ins))
        elif command == '\x8d': # GOSUB
            exec_gosub(ins)
    util.skip_to(ins, util.end_statement)    

def exec_on_error(ins):
    """ ON ERROR: define error trapping routine. """
    util.require_read(ins, ('\x89',))  # GOTO
    linenum = util.parse_jumpnum(ins)
    if linenum != 0 and linenum not in state.basic_state.line_numbers:
        # undefined line number
        raise error.RunError(8)
    state.basic_state.on_error = linenum
    # ON ERROR GOTO 0 in error handler
    if state.basic_state.on_error == 0 and state.basic_state.error_handle_mode:
        # re-raise the error so that execution stops
        raise error.RunError(state.basic_state.errn, state.basic_state.errp)
    # this will be caught by the trapping routine just set
    util.require(ins, util.end_statement)

def exec_resume(ins):
    """ RESUME: resume program flow after error-trap. """
    if state.basic_state.error_resume == None: 
        # unset error handler
        state.basic_state.on_error = 0
        # resume without error
        raise error.RunError(20)
    c = util.skip_white(ins)
    if c == '\x83': # NEXT
        ins.read(1)
        jumpnum = -1
    elif c not in util.end_statement:
        jumpnum = util.parse_jumpnum(ins)
    else:
        jumpnum = 0    
    util.require(ins, util.end_statement)
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
    util.skip_to(ins, util.end_statement)
    flow.jump_gosub(jumpnum)

def exec_return(ins):
    """ RETURN: return from a subroutine. """
    # return *can* have a line number
    if util.skip_white(ins) not in util.end_statement:    
        jumpnum = util.parse_jumpnum(ins)    
        # rest of line is ignored
        util.skip_to(ins, util.end_statement)    
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
            raise error.RunError(5)
    if util.skip_white_read_if(ins, (',',)):
        exp1 = expressions.parse_expression(ins, allow_empty=True)
        if exp1:
            # this produces a *signed* int
            mem_size = vartypes.pass_int_unpack(exp1, maxint=0xffff)
            if mem_size == 0:
                #  0 leads to illegal fn call
                raise error.RunError(5)
            else:
                if not memory.set_basic_memory_size(mem_size):
                    # out of memory    
                    raise error.RunError(7)    
        if util.skip_white_read_if(ins, (',',)):
            # set aside stack space for GW-BASIC. The default is the previous stack space size. 
            exp2 = expressions.parse_expression(ins, allow_empty = True)
            if exp2:
                stack_size = vartypes.pass_int_unpack(exp2, maxint=0xffff) 
                if stack_size == 0:
                    #  0 leads to illegal fn call
                    raise error.RunError(5)
                memory.set_stack_size(stack_size)    
            if pcjr_syntax and util.skip_white_read_if(ins, (',',)):
                # Tandy/PCjr: select video memory size
                if not state.console_state.screen.set_video_memory_size(
                    fp.unpack(vartypes.pass_single_keep(
                                 expressions.parse_expression(ins, empty_err=2)
                             )).round_to_int()):
                    state.console_state.screen.screen(0, 0, 0, 0)
                    console.init_mode()
            elif not exp2:
                raise error.RunError(2)    
    util.require(ins, util.end_statement)
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
    util.skip_to(ins, util.end_statement)

def parse_int_list_var(ins):
    """ Helper function for DIM: parse list of integers. """
    output = [ vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2)) ]   
    while True:
        d = util.skip_white(ins)
        if d == ',': 
            ins.read(1)
            c = util.peek(ins)
            if c in util.end_statement:
                # missing operand
                raise error.RunError(22)
            # if end_expression, syntax error    
            output.append(vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2)))
        elif d in util.end_statement:
            # statement ends - syntax error
            raise error.RunError(2)        
        elif d in util.end_expression:
            break
        else:  
            raise error.RunError(2)
    return output
    
def exec_dim(ins):
    """ DIM: dimension arrays. """
    while True:
        name = util.get_var_name(ins) 
        dimensions = [ 10 ]   
        if util.skip_white_read_if(ins, ('[', '(')):
            # at most 255 indices, but there's no way to fit those in a 255-byte command line...
            dimensions = parse_int_list_var(ins)
            while len(dimensions) > 0 and dimensions[-1] == None:
                dimensions = dimensions[:-1]
            if None in dimensions:
                raise error.RunError(2)
            util.require_read(ins, (')', ']'))   
            # yes, we can write dim gh[5) 
        var.dim_array(name, dimensions)            
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)

def exec_deftype(ins, typechar):
    """ DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables. """
    start, stop = -1, -1
    while True:
        d = util.skip_white_read(ins).upper()
        if d < 'A' or d > 'Z':
            raise error.RunError(2)
        else:
            start = ord(d) - ord('A')
            stop = start
        if util.skip_white_read_if(ins, ('\xEA',)):  # token for -
            d = util.skip_white_read(ins).upper()
            if d < 'A' or d > 'Z':
                raise error.RunError(2)
            else:
                stop = ord(d) - ord('A')
        state.basic_state.deftype[start:stop+1] = [typechar] * (stop-start+1)    
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)

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
    util.require(ins, util.end_statement)

def exec_let(ins):
    """ LET: assign value to variable or array. """
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:    
        # pre-dim even if this is not a legal statement!
        # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out fo range afterwards
        var.check_dim_array(name, indices)
    util.require_read(ins, ('\xE7',))   # =
    var.set_var_or_array(name, indices, expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
   
def exec_mid(ins):
    """ MID$: set part of a string. """
    util.require_read(ins, ('(',))
    name, indices = expressions.get_var_or_array_name(ins)
    if indices != []:    
        # pre-dim even if this is not a legal statement!
        var.check_dim_array(name, indices)
    util.require_read(ins, (',',))
    arglist = expressions.parse_int_list(ins, size=2, err=2)
    if arglist[0] == None:
        raise error.RunError(2)
    start = arglist[0]
    num = arglist[1] if arglist[1] != None else 255
    util.require_read(ins, (')',))
    s = vartypes.pass_string_unpack(var.get_var_or_array(name, indices))
    util.range_check(0, 255, num)
    if num > 0:
        util.range_check(1, len(s), start)
    util.require_read(ins, ('\xE7',)) # =
    val = vartypes.pass_string_keep(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    var.string_assign_into(name, indices, start - 1, num, val)     
    
def exec_lset(ins, justify_right=False):
    """ LSET: assign string value in-place; left justified. """
    name, index = expressions.get_var_or_array_name(ins)
    util.require_read(ins, ('\xE7',))
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
            raise error.RunError(2)
    else:
        raise error.RunError(2)
    util.skip_to(ins, util.end_statement)

def exec_read(ins):
    """ READ: read values from DATA statement. """
    # reading loop
    for v in parse_var_list(ins):
        # syntax error in DATA line (not type mismatch!) if can't convert to var type
        num = representation.str_to_type(flow.read_entry(), v[0][-1])
        if num == None: 
            # set pointer for EDIT gadget
            state.basic_state.bytecode.seek(state.basic_state.data_pos)
            raise error.RunError(2, state.basic_state.data_pos-1)
        var.set_var_or_array(*v, value=num)
    util.require(ins, util.end_statement)

def parse_prompt(ins, question_mark):
    """ Helper function for INPUT: parse prompt definition. """
    # parse prompt
    if util.skip_white_read_if(ins, ('"',)):
        prompt = ''
        # only literal allowed, not a string expression
        d = ins.read(1)
        while d not in util.end_line + ('"',)  : 
            prompt += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1, 1)  
        following = util.skip_white_read(ins)
        if following == ';':
            prompt += question_mark
        elif following != ',':
            raise error.RunError(2)
    else:
        prompt = question_mark
    return prompt

def exec_input(ins):
    """ INPUT: request input from user. """
    finp = expressions.parse_file_number(ins, 'IR')
    if finp != None:
        varlist = representation.input_vars_file(parse_var_list(ins), finp)
        for v in varlist:
            var.set_var_or_array(*v)
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
        while True:
            console.write(prompt) 
            line = console.wait_screenline(write_endl=newline)
            varlist = [ v[:] for v in readvar ]
            varlist = representation.input_vars(varlist, iolayer.BaseFile(StringIO(line), mode='I'))
            if not varlist:
                console.write_line('?Redo from start')  # ... good old Redo!
            else:
                break
        state.basic_state.input_mode = False
        for v in varlist:
            var.set_var_or_array(*v)
        ins.seek(pos)        
    util.require(ins, util.end_statement)
    
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
        raise error.RunError(2)
    elif readvar[-1] != '$':
        raise error.RunError(13)    
    # read the input
    if finp:
        line = finp.read_line()
    else:    
        state.basic_state.input_mode = True
        console.write(prompt) 
        line = console.wait_screenline(write_endl=newline)
        state.basic_state.input_mode = False
    var.set_var_or_array(readvar, indices, vartypes.pack_string(bytearray(line)))

def exec_restore(ins):
    """ RESTORE: reset DATA pointer. """
    if not util.skip_white(ins) in util.end_statement:
        datanum = util.parse_jumpnum(ins, err=8)
    else:
        datanum = -1
    # undefined line number for all syntax errors
    util.require(ins, util.end_statement, err=8)
    flow.restore(datanum)

def exec_swap(ins):
    """ SWAP: swap values of two variables. """
    name1, index1 = expressions.get_var_or_array_name(ins)
    util.require_read(ins, (',',))
    name2, index2 = expressions.get_var_or_array_name(ins)
    var.swap_var(name1, index1, name2, index2)
    # if syntax error. the swap has happened
    util.require(ins, util.end_statement)
                             
def exec_def_fn(ins):
    """ DEF FN: define a function. """
    fnname = util.get_var_name(ins)
    # read parameters
    fnvars = []
    if util.skip_white_read_if(ins, ('(',)):
        while True:
            fnvars.append(util.get_var_name(ins))
            if util.skip_white(ins) in util.end_statement + (')',):
                break    
            util.require_read(ins, (',',))
        util.require_read(ins, (')',))
    # read code
    fncode = ''
    util.require_read(ins, ('\xE7',)) #=
    startloc = ins.tell()
    util.skip_to(ins, util.end_statement)
    endloc = ins.tell()
    ins.seek(startloc)
    fncode = ins.read(endloc - startloc)
    if not state.basic_state.run_mode:
        # GW doesn't allow DEF FN in direct mode, neither do we (for no good reason, works fine)
        raise error.RunError(12)
    state.basic_state.functions[fnname] = [fnvars, fncode]
                             
def exec_randomize(ins):
    """ RANDOMIZE: set random number generator seed. """
    val = expressions.parse_expression(ins, allow_empty=True)
    # prompt for random seed if not specified
    if not val:
        console.write("Random number seed (-32768 to 32767)? ")
        seed = console.wait_screenline()
        # seed entered on prompt is rounded to int
        val = vartypes.pass_int_keep(representation.str_to_value_keep(vartypes.pack_string(seed)))
    elif val[0] == '$':
        raise error.RunError(5)
    rnd.randomize(val)
    util.require(ins, util.end_statement)
    
################################################
# Console statements

def exec_cls(ins):
    """ CLS: clear the screen. """
    if (pcjr_syntax == 'pcjr' or 
                    util.skip_white(ins) in (',',) + util.end_statement):
        if state.console_state.screen.view != None:
            val = 1
        elif state.console_state.view_set:
            val = 2
        else:
            val = 0
    else:
        val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        if pcjr_syntax == 'tandy':
            # tandy gives illegal function call on CLS number
            raise error.RunError(5)
    util.range_check(0, 2, val)
    if pcjr_syntax != 'pcjr':
        if util.skip_white_read_if(ins, (',',)):
            # comma is ignored, but a number after means syntax error
            util.require(ins, util.end_statement)    
        else:
            util.require(ins, util.end_statement, err=5)    
    # cls is only executed if no errors have occurred    
    if val == 0:
        console.clear()  
        graphics.reset_graphics()
    elif val == 1:
        state.console_state.screen.clear_view()
        graphics.reset_graphics()
    elif val == 2:
        console.clear_view()  
    if pcjr_syntax == 'pcjr':
        util.require(ins, util.end_statement)

def exec_color(ins):
    """ COLOR: set colour attributes. """
    fore, back, bord = expressions.parse_int_list(ins, 3, 5)          
    mode = state.console_state.screen.mode
    if mode.name == '320x200x4':
        return exec_color_mode_1(fore, back, bord)
    elif mode.name in ('640x200x2', '720x348x2'): 
        # screen 2; hercules: illegal fn call
        raise error.RunError(5)
    attr = state.console_state.screen.attr
    fore_old, back_old = (attr>>7)*0x10 + (attr&0xf), (attr>>4) & 0x7
    bord = 0 if bord == None else bord
    util.range_check(0, 255, bord)
    fore = fore_old if fore == None else fore
    # graphics mode bg is always 0; sets palette instead
    back = back_old if mode.is_text_mode and back == None else (backend.get_palette_entry(0) if back == None else back)
    if mode.is_text_mode:
        util.range_check(0, mode.num_attr-1, fore)
        util.range_check(0, 15, back, bord)
        state.console_state.screen.set_attr(((0x8 if (fore > 0xf) else 0x0) + (back & 0x7))*0x10 + (fore & 0xf)) 
        backend.set_border(bord)
    elif mode.name in ('160x200x16', '320x200x4pcjr', '320x200x16pcjr'
                        '640x200x4', '320x200x16', '640x200x16'):
        util.range_check(1, mode.num_attr-1, fore)
        util.range_check(0, mode.num_attr-1, back)
        state.console_state.screen.set_attr(fore)
        # in screen 7 and 8, only low intensity palette is used.
        backend.set_palette_entry(0, back % 8, check_mode=False)    
    elif mode.name in ('640x350x16', '640x350x4'):
        util.range_check(0, mode.num_attr-1, fore)
        util.range_check(0, len(state.console_state.colours)-1, back)
        state.console_state.screen.set_attr(fore)
        backend.set_palette_entry(0, back, check_mode=False)
    elif mode.name == '640x400x2':
        util.range_check(0, len(state.console_state.colours)-1, fore)
        if back != 0:
            raise error.RunError(5)    
        backend.set_palette_entry(1, fore, check_mode=False)
        
    
def exec_color_mode_1(back, pal, override):
    """ Helper function for COLOR in SCREEN 1. """
    back = backend.get_palette_entry(0) if back == None else back
    if override != None:
        # uses last entry as palette if given
        pal = override
    util.range_check(0, 255, back)
    if pal != None:
        util.range_check(0, 255, pal)
        backend.set_cga4_palette(pal%2)
        palette = list(backend.cga4_palette)
        palette[0] = back&0xf
        # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
        # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
        backend.set_palette(palette, check_mode=False)
    else:
        backend.set_palette_entry(0, back & 0xf, check_mode=False)        
    
def exec_palette(ins):
    """ PALETTE: set colour palette entry. """
    d = util.skip_white(ins)
    if d in util.end_statement:
        # reset palette
        backend.set_palette()
    elif d == '\xD7': # USING
        ins.read(1)
        exec_palette_using(ins)
    else:
        # can't set blinking colours separately
        num_attr = state.console_state.screen.mode.num_attr
        num_palette_entries = num_attr if num_attr != 32 else 16
        pair = expressions.parse_int_list(ins, 2, err=5)
        if pair[0] == None or pair[1] == None:
            raise error.RunError(2)
        util.range_check(0, num_palette_entries-1, pair[0])
        util.range_check(-1, len(state.console_state.colours)-1, pair[1])
        if pair[1] > -1:
            backend.set_palette_entry(pair[0], pair[1])
        util.require(ins, util.end_statement)    

def exec_palette_using(ins):
    """ PALETTE USING: set full colour palette. """
    num_attr = state.console_state.screen.mode.num_attr
    num_palette_entries = num_attr if num_attr != 32 else 16
    array_name, start_indices = expressions.get_var_or_array_name(ins)
    try:     
        dimensions, lst, _ = state.basic_state.arrays[array_name]    
    except KeyError:
        raise error.RunError(5)    
    if array_name[-1] != '%':
        raise error.RunError(13)
    start = var.index_array(start_indices, dimensions)
    if var.array_len(dimensions) - start  < num_palette_entries:
        raise error.RunError(5)
    new_palette = []
    for i in range(num_palette_entries):
        val = vartypes.pass_int_unpack(('%', lst[(start+i)*2:(start+i+1)*2]))
        util.range_check(-1, len(state.console_state.colours)-1, val)
        new_palette.append(val if val > -1 else backend.get_palette_entry(i))
    backend.set_palette(new_palette)
    util.require(ins, util.end_statement) 

def exec_key(ins):
    """ KEY: switch on/off function-key row on screen. """
    d = util.skip_white_read(ins)
    if d == '\x95': # ON
        # tandy can have VIEW PRINT 1 to 25, should raise ILLEGAN FUNCTION CALL then
        if state.console_state.scroll_height == 25:
            raise error.RunError(5)
        if not state.console_state.keys_visible:
            console.show_keys(True)
    elif d == '\xdd': # OFF
        if state.console_state.keys_visible:
            console.show_keys(False)   
    elif d == '\x93': # LIST
        console.list_keys()
    elif d == '(':
        # key (n)
        ins.seek(-1, 1)
        exec_key_events(ins)
    else:
        # key n, "TEXT"    
        ins.seek(-len(d), 1)
        exec_key_define(ins)
    util.require(ins, util.end_statement)        

def exec_key_events(ins):
    """ KEY: switch on/off keyboard events. """
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(0, 255, num)
    d = util.skip_white(ins)
    # others are ignored
    if num >= 1 and num <= 20:
        if state.basic_state.key_handlers[num-1].command(d):
            ins.read(1)
        else:    
            raise error.RunError(2)

def exec_key_define(ins):
    """ KEY: define function-key shortcut or scancode for event trapping. """
    keynum = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(1, 255, keynum)
    util.require_read(ins, (',',), err=5)
    text = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if keynum <= backend.num_fn_keys:
        state.console_state.key_replace[keynum-1] = str(text)
        if state.console_state.keys_visible:
            console.show_keys(True)
    else:
        # only length-2 expressions can be assigned to KEYs over 10
        # in which case it's a key scancode definition
        if len(text) != 2:
            raise error.RunError(5)
        # can't redefine scancodes for keys 1-14 (pc) 1-16 (tandy)
        if keynum > backend.num_fn_keys + 4 and keynum <= 20:    
            state.basic_state.event_keys[keynum-1] = str(text)
    
def exec_locate(ins):
    """ LOCATE: Set cursor position, shape and visibility."""
    cmode = state.console_state.screen.mode
    row, col, cursor, start, stop, dummy = expressions.parse_int_list(ins, 6, 2, allow_last_empty=True)          
    if dummy != None:
        # can end on a 5th comma but no stuff allowed after it
        raise error.RunError(2)
    row = state.console_state.row if row == None else row
    col = state.console_state.col if col == None else col
    if row == cmode.height and state.console_state.keys_visible:
        raise error.RunError(5)
    elif state.console_state.view_set:
        util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
    else:
        util.range_check(1, cmode.height, row)
    util.range_check(1, cmode.width, col)
    if row == cmode.height:
        # temporarily allow writing on last row
        state.console_state.bottom_row_allowed = True       
    console.set_pos(row, col, scroll_ok=False) 
    if cursor != None:
        util.range_check(0, (255 if pcjr_syntax else 1), cursor)   
        # set cursor visibility - this should set the flag but have no effect in graphics modes
        state.console_state.cursor = (cursor != 0)
        backend.update_cursor_visibility()
    if stop == None:
        stop = start
    if start != None:    
        util.range_check(0, 31, start, stop)
        # cursor shape only has an effect in text mode    
        if cmode.is_text_mode:    
            backend.set_cursor_shape(start, stop)

def exec_write(ins, output=None):
    """ WRITE: Output machine-readable expressions to the screen or a file. """
    output = expressions.parse_file_number(ins, 'OAR')
    output = backend.devices['SCRN:'] if output == None else output
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
    util.require(ins, util.end_statement)        
    # write the whole thing as one thing (this affects line breaks)
    output.write_line(outstr)

def exec_print(ins, output=None):
    """ PRINT: Write expressions to the screen or a file. """
    if output == None:
        output = expressions.parse_file_number(ins, 'OAR')
        output = backend.devices['SCRN:'] if output == None else output
    number_zones = max(1, int(output.width/14))
    newline = True
    while True:
        d = util.skip_white(ins)
        if d in util.end_statement + ('\xD7',): # USING
            break 
        elif d in (',', ';', '\xD2', '\xCE'):    
            ins.read(1)
            newline = False
            if d == ',':
                next_zone = int((output.col-1)/14)+1
                if next_zone >= number_zones and output.width >= 14:
                    output.write_line()
                else:            
                    output.write(' '*(1+14*next_zone-output.col))
            elif d == '\xD2': #SPC(
                numspaces = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2), 0xffff)) % output.width
                util.require_read(ins, (')',))
                output.write(' ' * numspaces)
            elif d == '\xCE': #TAB(
                pos = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2), 0xffff) - 1) % output.width + 1
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
            # output file (iolayer) takes care of width management; we must send a whole string at a time for this to be correct.
            output.write(str(word))
    if util.skip_white_read_if(ins, ('\xD7',)): # USING
        return exec_print_using(ins, output)     
    if newline:
        if output == backend.devices['SCRN:'] and state.console_state.overflow:
            output.write_line()
        output.write_line()
    util.require(ins, util.end_statement)      
            
def exec_print_using(ins, output):
    """ PRINT USING: Write expressions to screen or file using a formatting string. """
    format_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if format_expr == '':
        raise error.RunError(5)
    util.require_read(ins, (';',))
    fors = StringIO(format_expr)
    semicolon, format_chars = False, False
    while True:
        data_ends = util.skip_white(ins) in util.end_statement
        c = util.peek(fors)
        if c == '':
            if not format_chars:
                # there were no format chars in the string, illegal fn call (avoids infinite loop)
                raise error.RunError(5) 
            if data_ends:
                break
            # loop the format string if more variables to come
            fors.seek(0)
        elif c == '_':
            # escape char; write next char in fors or _ if this is the last char
            output.write(fors.read(2)[-1])
        else:
            string_field = representation.get_string_tokens(fors)
            if string_field:
                if not data_ends:
                    s = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
                    if string_field == '&':
                        output.write(s)    
                    else:
                        output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
            else:
                number_field, digits_before, decimals = representation.get_number_tokens(fors)
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
    util.require(ins, util.end_statement)

def exec_lprint(ins):
    """ LPRINT: Write expressions to printer LPT1. """
    exec_print(ins, backend.devices['LPT1:'])
                             
def exec_view_print(ins):
    """ VIEW PRINT: set scroll region. """
    if util.skip_white(ins) in util.end_statement:
        console.unset_view()
    else:  
        start = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, ('\xCC',)) # TO
        stop = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        max_line = 25 if (pcjr_syntax and not state.console_state.keys_visible) else 24
        util.range_check(1, max_line, start, stop)
        console.set_view(start, stop)
    
def exec_width(ins):
    """ WIDTH: set width of screen or device. """
    d = util.skip_white(ins)
    if d == '#':
        dev = expressions.parse_file_number(ins)
        w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    elif d == '\x9D': # LPRINT
        ins.read(1)
        dev = backend.devices['LPT1:']
        w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        if d in tokenise.tokens_number:
            expr = expressions.parse_expr_unit(ins)
        else:         
            expr = expressions.parse_expression(ins)
        if expr[0] == '$':
            try:
                dev = backend.devices[str(vartypes.pass_string_unpack(expr)).upper()]
            except KeyError:
                # bad file name
                raise error.RunError(64)           
            util.require_read(ins, (',',))
            w = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        else:
            dev = backend.devices['SCRN:']
            # IN GW-BASIC, we can do calculations, but they must be bracketed...
            #w = vartypes.pass_int_unpack(expressions.parse_expr_unit(ins))
            w = vartypes.pass_int_unpack(expr)
            if util.skip_white_read_if(ins, (',',)):
                # pare dummy number rows setting
                num_rows_dummy = expressions.parse_expression(ins, allow_empty=True)
                if num_rows_dummy != None:
                    min_num_rows = 0 if pcjr_syntax else 25
                    util.range_check(min_num_rows, 25, vartypes.pass_int_unpack(num_rows_dummy))
                # trailing comma is accepted
                util.skip_white_read_if(ins, (',',))
            # gives illegal function call, not syntax error
        util.require(ins, util.end_statement, err=5)        
    util.require(ins, util.end_statement)        
    dev.set_width(w)
    
def exec_screen(ins):
    """ SCREEN: change video mode or page. """
    erase = 1
    if pcjr_syntax:
        mode, colorswitch, apagenum, vpagenum, erase = expressions.parse_int_list(ins, 5)
    else:    
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette... this raises error before:
        mode, colorswitch, apagenum, vpagenum = expressions.parse_int_list(ins, 4)
    # set defaults to avoid err 5 on range check
    mode = mode if mode != None else state.console_state.screen.screen_mode
    colorswitch = colorswitch if colorswitch != None else state.console_state.screen.colorswitch    
    # if any parameter not in [0,255], error 5 without doing anything 
    util.range_check(0, 255, mode, colorswitch)
    if apagenum != None:
        util.range_check(0, 255, apagenum)
    if vpagenum != None:
        util.range_check(0, 255, vpagenum)
    util.range_check(0, 2, erase)
    # if the parameters are outside narrow ranges (e.g. not implemented screen mode, pagenum beyond max)
    # then the error is only raised after changing the palette.
    util.require(ins, util.end_statement)        
    # decide whether to redraw the screen    
    do_redraw = ((mode != state.console_state.screen.screen_mode) or 
                 (colorswitch != state.console_state.screen.colorswitch))
    if do_redraw:             
        if not state.console_state.screen.screen(mode, colorswitch, apagenum, vpagenum, erase):
            raise error.RunError(5)
        console.init_mode()    
    else:
        state.console_state.screen.set_page(vpagenum, apagenum)
    
def exec_pcopy(ins):
    """ PCOPY: copy video pages. """
    src = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, state.console_state.screen.mode.num_pages-1, src)
    util.require_read(ins, (',',))
    dst = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    util.range_check(0, state.console_state.screen.mode.num_pages-1, dst)
    state.console_state.text.copy_page(src, dst)
        
        
prepare()
        
