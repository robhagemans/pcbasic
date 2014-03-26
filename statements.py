#
# PC-BASIC 3.23 - statements.py
#
# Statement parser
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from functools import partial

import error
import vartypes
import util
import expressions
import program
import run
import console

# OS statements
from stat_os import *
# program flow
from stat_flow import *
# code manipulation
from stat_code import *
# variable manipulation
from stat_var import *
# printing and screen and keys
from stat_print import *
# file i/o
from stat_file import *
# graphics
from stat_graph import *
# sound
from stat_sound import *
# machine access
from stat_machine import *
# debugging
from stat_debug import *

# parses one statement at the current stream pointer in current_codestream
# return value False: stream ends
def parse_statement():
    ins = program.current_codestream
    program.current_statement = ins.tell()
    c = util.skip_white(ins).upper()
    if c == '':
        # stream has ended.
        return False
    # parse line number or : at start of statement    
    elif c == '\x00':
        ins.read(1)
        # line number marker, new statement
        linenum = util.parse_line_number(ins)
        if linenum == -1:
            if error.error_resume:
                # unfinished error handler: no RESUME (don't trap this)
                error.error_handle_mode = True
                raise error.RunError(19) 
            # break
            program.set_runmode(False)
            return False
        if program.tron:
            console.write('['+('%i' % linenum) +']')
        debug_step(linenum)
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
            elif c == '\xA4':    exec_DEBUG(ins)
            elif c == '\xA5':    exec_pcopy(ins)
            elif c == '\xA7':    exec_lock(ins)
            elif c == '\xA8':    exec_unlock(ins)
            else: raise error.RunError(2)
        # two-byte tokens    
        elif c == '\xFF':
            c = ins.read(1)
            if   c == '\x83':   exec_mid(ins)
            elif c == '\xA0':   exec_pen(ins)
            elif c == '\xA2':   exec_strig(ins)
            else: raise error.RunError(2)
        else:
            raise error.RunError(2)
    return True

#################################################################    
#################################################################

exec_defstr = partial(exec_deftype, typechar='$')
exec_defint = partial(exec_deftype, typechar='%')
exec_defsng = partial(exec_deftype, typechar='!')
exec_defdbl = partial(exec_deftype, typechar='#')

def exec_system(ins): 
    # SYSTEM LAH does not execute 
    util.require(ins, util.end_statement)
    run.exit() 
        
def exec_tron(ins):
    program.tron = True
    # TRON LAH gives error, but TRON has been executed
    util.require(ins, util.end_statement)

def exec_troff(ins):
    program.tron = False
    util.require(ins, util.end_statement)

def exec_rem(ins):
    # skip the rest of the line, but parse numbers to avoid triggering EOL
    util.skip_to(ins, util.end_line)

# does nothing in GWBASIC except give some errors. See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY    
def exec_lcopy(ins):    
    if util.skip_white(ins) not in util.end_statement:
        util.range_check(0, 255, vartypes.pass_int_unpack(expressions.parse_expression(ins)))
        util.require(ins, util.end_statement)

# MOTOR does nothing
exec_motor = exec_lcopy

##########################################################
# statements that require further qualification

def exec_def(ins):
    c = util.skip_white(ins)
    if c == '\xD1': #FN
        ins.read(1)
        exec_def_fn(ins)
    elif c == '\xD0': #USR
        ins.read(1)
        exec_def_usr(ins)
    elif util.peek(ins,3) == 'SEG':
        ins.read(3)
        exec_def_seg(ins)
    else:        
        raise error.RunError(2)      

def exec_view(ins):
    if util.skip_white_read_if(ins, ('\x91',)):  # PRINT
        exec_view_print(ins)
    else:
        exec_view_graph(ins)
    
def exec_line(ins):
    if util.skip_white_read_if(ins, ('\x85',)):  # INPUT
        exec_line_input(ins)
    else:
        exec_line_graph(ins)

def exec_get(ins):
    if util.skip_white(ins)=='(':
        exec_get_graph(ins)
    else:    
        exec_get_file(ins)
    
def exec_put(ins):
    if util.skip_white(ins)=='(':
        exec_put_graph(ins)
    else:    
        exec_put_file(ins)

def exec_on(ins):
    c = util.skip_white(ins)
    if c == '\xA7': # ERROR:
        ins.read(1)
        exec_on_error(ins)
        return
    elif c == '\xC9': # KEY
        ins.read(1)
        exec_on_key(ins)
        return
    elif c == '\xFE':
        c = util.peek(ins,2)
        if c== '\xFE\x94': # FE94 TIMER
            ins.read(2)
            exec_on_timer(ins)
            return
        elif c == '\xFE\x93':   # PLAY
            ins.read(2)
            exec_on_play(ins)
            return
        elif c in ('\xFE\x90'):   # COM
            ins.read(2)
            exec_on_com(ins)
            return
    elif c == '\xFF':
        if util.peek(ins,2) == '\xFF\xA0':  # PEN
            ins.read(2)
            exec_on_pen(ins)
            return
        if util.peek(ins,2) == '\xFF\xA2':  # STRIG
            ins.read(2)
            exec_on_strig(ins)
            return
    exec_on_jump(ins)

##########################################################
# event switches (except PLAY, KEY)

# pen        
def exec_pen(ins):
    if events.pen_handler.command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)

# strig: stick trigger        
def exec_strig(ins):
    d = util.skip_white(ins)
    if d == '(':
        # strig (n)
        num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        if num not in (0,2,4,6):
            raise error.RunError(5)
        if events.strig_handlers[num//2].command(util.skip_white(ins)):
            ins.read(1)
        else:    
            raise error.RunError(2)
    elif d == '\x95': # ON
        ins.read(1)
        console.stick_is_on = True
    elif d == '\xDD': # OFF
        ins.read(1)
        console.stick_is_on = False
    else:
        raise error.RunError(2)
    util.require(ins, util.end_statement)

# COM (n) ON, OFF, STOP
def exec_com(ins):    
    util.require(ins, ('(',))
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(1, 2, num)
    if events.com_handlers[num].command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)

# TIMER ON, OFF, STOP
def exec_timer(ins):
    if events.timer_handler.command(util.skip_white(ins)):
        ins.read(1)
    else:    
        raise error.RunError(2)
    util.require(ins, util.end_statement)      

# event definitions

def parse_on_event(ins, bracket=True):
    if bracket:
        num = expressions.parse_bracket(ins)
    util.require_read(ins, ('\x8D',)) # GOSUB
    jumpnum = util.parse_jumpnum(ins)
    if jumpnum == 0:
        jumpnum = None
    util.require(ins, util.end_statement)    
    return num, jumpnum   

def exec_on_key(ins):
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 20, keynum)
    events.key_handlers[keynum-1].gosub = jumpnum

def exec_on_timer(ins):
    timeval, jumpnum = parse_on_event(ins)
    timeval = vartypes.pass_single_keep(timeval)
    events.timer_period = fp.mul(fp.unpack(timeval), fp.Single.from_int(1000)).round_to_int()
    events.timer_handler.gosub = jumpnum

def exec_on_play(ins):
    playval, jumpnum = parse_on_event(ins)
    playval = vartypes.pass_int_unpack(playval)
    events.play_trig = playval
    events.play_handler.gosub = jumpnum
    
def exec_on_pen(ins):
    _, jumpnum = parse_on_event(ins, bracket=False)
    events.pen_handler.gosub = jumpnum
    
def exec_on_strig(ins):
    strigval, jumpnum = parse_on_event(ins)
    strigval = vartypes.pass_int_unpack(strigval)
    ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
    if strigval not in (0,2,4,6):
        raise error.RunError(5)
    events.strig_handlers[strigval//2].gosub = jumpnum
    
def exec_on_com(ins):
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_unpack(keynum)
    util.range_check(1, 2, num)
    events.com_handlers[keynum-1].gosub = jumpnum

