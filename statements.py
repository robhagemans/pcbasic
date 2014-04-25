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
from cStringIO import StringIO
import os

import automode
import console
import debug
import deviceio
import draw_and_play
import error
import events
import expressions
import fileio
import fp
import oslayer
import program
import run
import util
import var
import vartypes

# program flow
from stat_flow import *
# variable manipulation
from stat_var import *
# printing and screen and keys
from stat_print import *
# graphics
from stat_graph import *


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
            elif c == '\xA4':    exec_debug(ins)
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

def exec_debug(ins):
    # this is not a GW-BASIC behaviour, but helps debugging.
    # this is parsed like a REM by the tokeniser.
    # rest of the line is considered to be a python statement
    d = util.skip_white(ins)
    debug_cmd = ''
    while util.peek(ins) not in util.end_line:
        debug_cmd += ins.read(1)
    debug.debug_exec(debug_cmd)

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
    num = None
    if bracket:
        num = expressions.parse_bracket(ins)
    util.require_read(ins, ('\x8D',)) # GOSUB
    jumpnum = util.parse_jumpnum(ins)
    if jumpnum == 0:
        jumpnum = None
    if jumpnum not in program.line_numbers:
        raise error.RunError(8)    
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
    util.range_check(1, 2, keynum)
    events.com_handlers[keynum-1].gosub = jumpnum

##########################################################
# sound

def exec_beep(ins):
    console.sound.beep() 
    # if a syntax error happens, we still beeped.
    util.require(ins, util.end_statement)
    if console.sound.music_foreground:
        console.sound.wait_music(wait_last=False)
    
def exec_sound(ins):
    freq = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dur = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)))
    if fp.Single.from_int(-65535).gt(dur) or dur.gt(fp.Single.from_int(65535)):
        raise error.RunError(5)
    util.require(ins, util.end_statement)
    if dur.is_zero():
        console.sound.stop_all_sound()
        return
    util.range_check(37, 32767, freq) # 32767 is pause
    one_over_44 = fp.Single.from_bytes(bytearray('\x8c\x2e\x3a\x7b')) # 1/44 = 0.02272727248
    dur_sec = dur.to_value()/18.2
    if one_over_44.gt(dur):
        # play indefinitely in background
        console.sound.play_sound(freq, dur_sec, loop=True)
    else:
        console.sound.play_sound(freq, dur_sec)
        if console.sound.music_foreground:
            console.sound.wait_music(wait_last=False)
    
def exec_play(ins):
    if events.play_handler.command(util.skip_white(ins)):
        ins.read(1)
        util.require(ins, util.end_statement)
    else:    
        # retrieve Music Macro Language string
        mml = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_expression)
        draw_and_play.play_parse_mml(mml)
           
##########################################################
# machine emulation
         
# POKE: only video memory implemented
def exec_poke(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff) 
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    if addr < 0: 
        addr += 0x10000
    addr += var.segment*0x10
    if addr >= graphics.video_segment[console.screen_mode]*0x10:
        # graphics and text memory
        graphics.set_memory(addr, val)
#    elif addr >= var.data_segment*0x10 + var.var_mem_start:
#        # variable memory
#        vartypes.set_memory(addr)
    util.require(ins, util.end_statement)
    
# DEF SEG    
def exec_def_seg(ins):
    # &hb800: text screen buffer; &h13d: data segment
    if util.skip_white_read_if(ins, ('\xE7',)): #=
        var.segment = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    else:
        var.segment = var.data_segment   
    if var.segment < 0:
        var.segment += 0x10000     
    util.require(ins, util.end_statement)

# do-nothing DEF USR    
def exec_def_usr(ins):
    if util.peek(ins) in ('\x11','\x12','\x13','\x14','\x15','\x16','\x17','\x18','\x19','\x1a'): # digits 0--9
        ins.read(1)
    util.require_read(ins, ('\xE7',))     
    vartypes.pass_int_keep(expressions.parse_expression(ins), maxint=0xffff)
    util.require(ins, util.end_statement)

# bload: video memory only
def exec_bload(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    offset = None
    if util.skip_white_read_if(ins, (',',)):
        offset = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
        if offset < 0:
            offset += 0x10000           
    util.require(ins, util.end_statement)
    g = fileio.open_file_or_device(0, name, mode='L', defext='')
    if g.read(1) != '\xfd':
        raise error.RunError(54)
    seg = vartypes.uint_to_value(bytearray(g.read(2)))
    foffset = vartypes.uint_to_value(bytearray(g.read(2)))
    if offset == None:
        offset = foffset
    # this gets ignored; even the \x1a at the end gets dumped onto the screen.
    size = vartypes.uint_to_value(bytearray(g.read(2))) 
    buf = bytearray()
    while True:
        c = g.read(1)
        if c == '':
            break
        buf += c    
    g.close()
    addr = seg * 0x10 + offset
    if addr + len(buf) > graphics.video_segment[console.screen_mode]*0x10:
        # graphics and text memory
        graphics.set_memory_block(addr, buf)

# bsave: video memory only
def exec_bsave(ins):
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
    util.require(ins, util.end_statement)
    g = fileio.open_file_or_device(0, name, mode='S', defext='')
    g.write('\xfd')
    g.write(str(vartypes.value_to_uint(var.segment)))
    g.write(str(vartypes.value_to_uint(offset)))
    g.write(str(vartypes.value_to_uint(length)))
    addr = var.segment * 0x10 + offset
    g.write(str(graphics.get_memory_block(addr, length)))
    g.write('\x1a')
    g.close()
        
# call: not implemented        
def exec_call(ins):
    raise error.RunError(73)    

# OUT, implemented only the ports for colour plane selection
def exec_out(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, val)
    if addr == 0x3c5:
        # officially, requires OUT &H3C4, 2 first (not implemented)
        graphics.colour_plane_write_mask = val
    elif addr == 0x3cf:
        # officially, requires OUT &H3CE, 4 first (not implemented)
        graphics.colour_plane = val        
    util.require(ins, util.end_statement)

# only implemented port &h60 (keyboard read)
def exec_wait(ins):
    addr = vartypes.pass_int_unpack(expressions.parse_expression(ins), maxint=0xffff)
    util.require_read(ins, (',',))
    ander = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, ander)
    xorer = 0
    if util.skip_white_read_if(ins, (',',)):
        xorer = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 255, xorer)
    util.require(ins, util.end_statement)
    store_suspend = events.suspend_all_events
    events.suspend_all_events = True
    while (((console.inp_key if addr == 0x60 else 0) ^ xorer) & ander) == 0:
        console.idle()
        console.check_events()
    events.suspend_all_events = store_suspend     

##########################################################
# OS
    
def exec_chdir(ins):
    oslayer.chdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_mkdir(ins):
    oslayer.mkdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_rmdir(ins):
    oslayer.rmdir(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    util.require(ins, util.end_statement)

def exec_name(ins):
    oldname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # don't rename open files
    fileio.check_file_not_open(oldname)
    # AS is not a tokenised word
    word = util.skip_white_read(ins) + ins.read(1)
    if word.upper() != 'AS':
        raise error.RunError(2)
    newname = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    oslayer.rename(oldname, newname)
    util.require(ins, util.end_statement)

def exec_kill(ins):
    name = oslayer.dospath_read(str(vartypes.pass_string_unpack(expressions.parse_expression(ins))), '', 53)
    # don't delete open files
    fileio.check_file_not_open(name)
    oslayer.safe(os.remove, name)
    util.require(ins, util.end_statement)

def exec_files(ins):
    pathmask = ''
    if util.skip_white(ins) not in util.end_statement:
        pathmask = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        if not pathmask:
            # bad file name
            raise error.RunError(64)
    oslayer.files(pathmask, console)
    util.require(ins, util.end_statement)
    
def exec_shell(ins):
    if util.skip_white(ins) in util.end_statement:
        cmd = ''
    else:
        cmd = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    savecurs = console.show_cursor()
    oslayer.shell(cmd) 
    console.show_cursor(savecurs)
    util.require(ins, util.end_statement)
        
def exec_environ(ins):
    envstr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    eqs = envstr.find('=')
    if eqs <= 0:
        raise error.RunError(5)
    var = str(envstr[:eqs])
    val = str(envstr[eqs+1:])
    os.environ[var] = val
    util.require(ins, util.end_statement)
       
def exec_time(ins):
    util.require_read(ins, ('\xE7',)) #time$=
    # allowed formats:  hh   hh:mm   hh:mm:ss  where hh 0-23, mm 0-59, ss 0-59
    timestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    oslayer.set_time(timestr)

def exec_date(ins):
    util.require_read(ins, ('\xE7',)) # date$=
    # allowed formats:
    # mm/dd/yy  or mm-dd-yy  mm 0--12 dd 0--31 yy 80--00--77
    # mm/dd/yyyy  or mm-dd-yyyy  yyyy 1980--2099
    datestr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    oslayer.set_date(datestr)

##########################################################
# code
    
def parse_line_range(ins):
    from_line = parse_jumpnum_or_dot(ins, allow_empty=True)    
    if util.skip_white_read_if(ins, ('\xEA',)):   # -
        to_line = parse_jumpnum_or_dot(ins, allow_empty=True)
    else:
        to_line = from_line
    return (from_line, to_line)    

def parse_jumpnum_or_dot(ins, allow_empty=False, err=2):
    c = util.skip_white_read(ins)
    if c == '\x0E':
        return vartypes.uint_to_value(bytearray(ins.read(2)))
    elif c == '.':
        return program.last_stored
    else:        
        if allow_empty:
            ins.seek(-len(c), 1)
            return None
        raise error.RunError(err)
            
def exec_delete(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    # throws back to direct mode
    program.delete(from_line, to_line)

def exec_edit(ins):
    if util.skip_white(ins) in util.end_statement:
        # undefined line number
        raise error.RunError(8)    
    from_line = parse_jumpnum_or_dot(ins, err=5)
    if from_line == None or from_line not in program.line_numbers:
        raise error.RunError(8)
    util.require(ins, util.end_statement, err=5)
    # print the line, position cursor, back to direct mode. suppress prompt.
    program.edit(from_line)
    
def exec_auto(ins):
    linenum = parse_jumpnum_or_dot(ins, allow_empty=True)
    increment = None
    if util.skip_white_read_if(ins, (',',)): 
        increment = util.parse_jumpnum(ins, allow_empty=True)
    util.require(ins, util.end_statement)
    # do the AUTO mode and go back to direct mode
    automode.auto_loop(linenum, increment)
    
def exec_list(ins):
    from_line, to_line = parse_line_range(ins)
    if util.skip_white_read_if(ins, (',',)):
        out = fileio.open_file_or_device(0, vartypes.pass_string_unpack(expressions.parse_expression(ins)), 'O')
    else:
        out = console
    util.require(ins, util.end_statement)
    program.list_lines(out, from_line, to_line)    

def exec_llist(ins):
    from_line, to_line = parse_line_range(ins)
    util.require(ins, util.end_statement)
    program.list_lines(deviceio.devices['LPT1:'], from_line, to_line)
        
def exec_load(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    comma = util.skip_white_read_if(ins, (',',))
    if comma:
        util.require_read(ins, 'R')
    util.require(ins, util.end_statement)
    program.load(fileio.open_file_or_device(0, name, mode='L', defext='BAS'))
    if comma:
        # in ,R mode, don't close files; run the program
        program.jump(None)
    else:
        fileio.close_all()
    program.tron = False    
        
def exec_chain(ins):
    action = program.merge if util.skip_white_read_if(ins, ('\xBD',)) else program.load     # MERGE
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
            if util.skip_white_read_if(ins, (',',)) and util.skip_white_read_if(ins, ('\xa9',)):
                delete_lines = parse_line_range(ins) # , DELETE
    util.require(ins, util.end_statement)
    program.chain(action, fileio.open_file_or_device(0, name, mode='L', defext='BAS'), jumpnum, common_all, delete_lines)

def exec_save(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    mode = 'B'
    if util.skip_white_read_if(ins, (',',)):
        mode = util.skip_white_read(ins).upper()
        if mode not in ('A', 'P'):
            raise error.RunError(2)
    program.save(fileio.open_file_or_device(0, name, mode='S', defext='BAS'), mode)
    util.require(ins, util.end_statement)
    
def exec_merge(ins):
    name = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # check if file exists, make some guesses (all uppercase, +.BAS) if not
    program.merge(fileio.open_file_or_device(0, name, mode='L', defext='BAS') )
    util.require(ins, util.end_statement)
    
def exec_new(ins):
    program.tron = False
    # deletes the program currently in memory and clears all variables.
    program.new()

def exec_renum(ins):
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

# close all files
def exec_reset(ins):
    fileio.close_all()
    util.require(ins, util.end_statement)

def parse_read_write(ins):
    d = util.skip_white(ins)
    if d == '\xB7': # WRITE
        ins.read(1)
        access = 'W'        
    elif d == '\x87': # READ
        ins.read(1)
        access = 'RW' if util.skip_white_read_if(ins, ('\xB7',)) else 'R' # WRITE
    return access

long_modes = {'\x85': 'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}  # \x85 is INPUT
default_access_modes = { 'I':'R', 'O':'W', 'A':'RW', 'R':'RW' }

def exec_open(ins):
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
            d = util.skip_white(ins)
            access = parse_read_write(ins)
        # LOCK clause
        if util.skip_white_read_if(ins, ('\xFE\xA7',)): # LOCK
            d = util.skip_white(ins)
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
    util.range_check(1, 128, reclen)        
    fileio.open_file_or_device(number, name, mode, access, lock, reclen) 
    util.require(ins, util.end_statement)
                
def exec_close(ins):
    # allow empty CLOSE
    if util.skip_white(ins) in util.end_statement:
        return
    while True:
        number = expressions.parse_file_number_opthash(ins)
        try:    
            fileio.files[number].close()
        except KeyError:
            pass    
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)
            
def exec_field(ins):
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    if util.skip_white_read_if(ins, (',',)):
        field = the_file.field 
        offset = 0    
        while True:
            width = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            util.range_check(0, 255, width)
            util.require_read(ins, ('AS',), err=5)
            name = util.get_var_name(ins)
            var.set_field_var(field, name, offset, width)         
            offset += width
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, util.end_statement)

def parse_get_or_put_file(ins):
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, (',',)):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)).round_to_int())
        util.range_check_err(1, 2**25, pos, err=63) # not 2^32-1 as the manual boasts! pos-1 needs to fit in a single-prec mantissa
        if not isinstance(the_file, deviceio.COMFile):
            the_file.set_pos(pos)    
        else:
            num_bytes = pos    
    return the_file, num_bytes        
    
def exec_put_file(ins):
    thefile, num_bytes = parse_get_or_put_file(ins) 
    thefile.write_field(num_bytes)
    util.require(ins, util.end_statement)

def exec_get_file(ins):
    thefile, num_bytes = parse_get_or_put_file(ins) 
    thefile.read_field(num_bytes)
    util.require(ins, util.end_statement)
    
def exec_lock_or_unlock(ins, action):
    thefile = fileio.get_file(expressions.parse_file_number_opthash(ins))
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

exec_lock = partial(exec_lock_or_unlock, action = fileio.lock_records)
exec_unlock = partial(exec_lock_or_unlock, action = fileio.unlock_records)
    
# ioctl: not implemented
def exec_ioctl(ins):
    fileio.get_file(expressions.parse_file_number_opthash(ins))
    raise error.RunError(5)   
    
