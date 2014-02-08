#
# PC-BASIC 3.23 - statements.py
#
# Statement parser
# 
# (c) 2013 Rob Hagemans 
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

tron = False


# debugging
from stat_debug import *
    
    

# parses one statement at the current stream pointer in current_codestream
# return value False: stream ends
def parse_statement():
    global tron
    ins = program.current_codestream
    program.current_statement = ins.tell()
    c = util.skip_white_read(ins).upper()
    if c=='':
        # stream has ended.
        return False
    # code stream should either be at '\x00' or at ':' to start a statement
    elif c=='\x00':
        # line number marker, new statement
        program.linenum = util.parse_line_number(ins)
        if program.linenum == -1:
            # move back to the line-ending \x00 and break
            ins.seek(-1,1)
            program.unset_runmode()
            return False
        if tron:
            console.write('['+('%i' % program.linenum) +']')
        debug_step(program.linenum)
        c = util.skip_white_read(ins).upper()
    elif c==':':
        # new statement
        c = util.skip_white_read(ins).upper()
    if c in util.end_statement:
        # empty statement, return to parse next
        if c!='':
            ins.seek(-1,1)
        return True
    elif c >= 'A' and c <= 'Z' :
        # implicit LET
        ins.seek(-1,1)
        exec_let(ins)
    elif c=='\x81':     # END
        exec_end(ins)
    elif c=='\x82':     # FOR
        exec_for(ins)
    elif c=='\x83':     # NEXT
        exec_next(ins)
    elif c=='\x84':     # DATA
        exec_data(ins)
    elif c=='\x85':     # INPUT
        exec_input(ins)
    elif c=='\x86':     # DIM
        exec_dim(ins)
    elif c=='\x87':     # READ
        exec_read(ins)
    elif c=='\x88':    # LET
        exec_let(ins)
    elif c=='\x89':     # GOTO
        exec_goto(ins)
    elif c=='\x8A':     # RUN
        exec_run(ins)
    elif c=='\x8B':     # IF
        exec_if(ins)
    elif c=='\x8C':     # RESTORE
        exec_restore(ins)
    elif c=='\x8D':     # GOSUB
        exec_gosub(ins)
    elif c=='\x8E':     # RETURN
        exec_return(ins)
    elif c=='\x8F':     # REM
        exec_rem(ins)
    elif c=='\x90':     # STOP
        exec_stop(ins)
    elif c=='\x91':     # PRINT
        exec_print(ins)
    elif c=='\x92':     # CLEAR
        exec_clear(ins)  
    elif c=='\x93':     # LIST
        exec_list(ins)      
    elif c=='\x94':     # NEW
        exec_new(ins)
    elif c=='\x95':     # ON
        exec_on(ins)
    elif c=='\x96':     # WAIT
        exec_wait(ins)
    elif c=='\x97':     # DEF
        exec_def(ins)
    elif c=='\x98':     # POKE
        exec_poke(ins)
    elif c=='\x99':     # CONT
        exec_cont(ins)
    elif c=='\x9C':     # OUT
        exec_out(ins)
    elif c=='\x9D':     # LPRINT
        exec_lprint(ins)
    elif c=='\x9E':     # LLIST
        exec_llist(ins)    
    elif c=='\xA0':     # WIDTH
        exec_width(ins)    
    elif c=='\xA1':     # ELSE
        exec_else(ins)    
    elif c=='\xA2':    # TRON
        exec_tron(ins)
    elif c=='\xA3':    # TROFF
        exec_troff(ins)
    elif c=='\xA4':    # SWAP
        exec_swap(ins)
    elif c=='\xA5':    # ERASE
        exec_erase(ins)
    elif c=='\xA6':    # EDIT
        exec_edit(ins)
    elif c=='\xA7':    # ERROR
        exec_error(ins)
    elif c=='\xA8':    # RESUME
        exec_resume(ins)
    elif c=='\xA9':    # DELETE
        exec_delete(ins)
    elif c=='\xAA':    # AUTO
        exec_auto(ins)
    elif c=='\xAB':    # RENUM
        exec_renum(ins)
    elif c=='\xAC':   # DEFSTR    
        exec_defstr(ins)
    elif c=='\xAD':   # DEFINT   
        exec_defint(ins)
    elif c=='\xAE':   # DEFSNG    
        exec_defsng(ins)
    elif c=='\xAF':   # DEFDBL    
        exec_defdbl(ins)    
    elif c=='\xB0':     # LINE
        exec_line(ins)
    elif c=='\xB1':     # WHILE
        exec_while(ins)
    elif c=='\xB2':     # WEND
        exec_wend(ins)
    elif c=='\xB3':     # CALL
        exec_call(ins)
    elif c=='\xB7':     # WRITE
        exec_write(ins)
    elif c=='\xB8':     # OPTION
        exec_option(ins)
    elif c=='\xB9':     # RANDOMIZE
        exec_randomize(ins)
    elif c=='\xBA':     # OPEN
        exec_open(ins)
    elif c=='\xBB':     # CLOSE
        exec_close(ins)
    elif c=='\xBC':     # LOAD
        exec_load(ins)
    elif c=='\xBD':     # MERGE
        exec_merge(ins)
    elif c=='\xBE':     # SAVE
        exec_save(ins)
    elif c=='\xBF':     # COLOR
        exec_color(ins)
    elif c=='\xC0':     # CLS
        exec_cls(ins)
    elif c=='\xC1':     # MOTOR
        exec_motor(ins)        
    elif c=='\xC2':     # BSAVE
        exec_bsave(ins)        
    elif c=='\xC3':     # BLOAD
        exec_bload(ins)        
    elif c=='\xC4':     # SOUND
        exec_sound(ins)        
    elif c=='\xC5':     # BEEP
        exec_beep(ins)        
    elif c=='\xC6':     # PSET
        exec_pset(ins)        
    elif c=='\xC7':     # PRESET
        exec_preset(ins)        
    elif c=='\xC8':     # SCREEN
        exec_screen(ins)
    elif c=='\xC9':     # KEY
        exec_key(ins)
    elif c=='\xCA':     # LOCATE
        exec_locate(ins)
    # two-byte tokens
    elif c=='\xFD':
        ins.read(1)
        # these are all expression tokens, not statement tokens.
        # syntax error
        raise error.RunError(2)
    # two-byte tokens
    elif c=='\xFE':
        c = ins.read(1)
        if c=='\x81':      # FILES
            exec_files(ins)
        elif c=='\x82':    # FIELD
            exec_field(ins)
        elif c=='\x83':    # SYSTEM
            exec_system(ins)
        elif c=='\x84':    # NAME
            exec_name(ins)
        elif c=='\x85':    # LSET
            exec_lset(ins)
        elif c=='\x86':    # RSET
            exec_rset(ins)
        elif c=='\x87':    # KILL
            exec_kill(ins)
        elif c=='\x88':    # PUT
            exec_put(ins)
        elif c=='\x89':    # GET
            exec_get(ins)
        elif c=='\x8A':    # RESET
            exec_reset(ins)
        elif c=='\x8B':    # COMMON
            exec_common(ins)
        elif c=='\x8C':    # CHAIN
            exec_chain(ins)
        elif c=='\x8D':    # DATE$
            exec_date(ins)
        elif c=='\x8E':    # TIME$
            exec_time(ins)
        elif c=='\x8F':    # PAINT
            exec_paint(ins)
        elif c=='\x90':    # COM
            exec_com(ins)
        elif c=='\x91':    # CIRCLE
            exec_circle(ins)
        elif c=='\x92':    # DRAW
            exec_draw(ins)
        elif c=='\x93':    # PLAY
            exec_play(ins)
        elif c=='\x94':    # TIMER
            exec_timer(ins)
        elif c=='\x96':    # IOCTL
            exec_ioctl(ins)
        elif c=='\x97':    # CHDIR
            exec_chdir(ins)
        elif c=='\x98':    # MKDIR
            exec_mkdir(ins)
        elif c=='\x99':    # RMDIR
            exec_rmdir(ins)
        elif c=='\x9A':    # SHELL
            exec_shell(ins)
        elif c=='\x9B':    # ENVIRON
            exec_environ(ins)
        elif c=='\x9C':    # VIEW
            exec_view(ins)
        elif c=='\x9D':    # WINDOW
            exec_window(ins)
        elif c=='\x9F':    # PALETTE
            exec_palette(ins)
        elif c=='\xA0':    # LCOPY
            exec_lcopy(ins)
        elif c=='\xA4':     # DEBUG
            exec_DEBUG(ins)
        elif c=='\xA5':     # PCOPY
            exec_pcopy(ins)
        elif c== '\xA7':    # LOCK
            exec_lock(ins)
        elif c== '\xA8':    # UNLOCK
            exec_unlock(ins)
        else:
            # syntax error
            raise error.RunError(2)
    # two-byte tokens    
    elif c=='\xFF':
        c = ins.read(1)
        if c == '\x83':       # MID$ statement
            exec_mid(ins)
        elif c == '\xA0':     # PEN statement
            exec_pen(ins)
        elif c == '\xA2':     # STRIG statement
            exec_strig(ins)
        else:
            # syntax error
            raise error.RunError(2)
    else:
        # syntax error
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
    global tron
    tron=True
    # TRON LAH gives error, but TRON has been executed
    util.require(ins, util.end_statement)
    

def exec_troff(ins):
    global tron
    tron = False
    util.require(ins, util.end_statement)
       

def exec_rem(ins):
    # skip the rest of the line, but parse numbers to avoid triggering EOL
    util.skip_to(ins, util.end_line)
    

# MOTOR does nothing
def exec_motor(ins):
    if util.skip_white(ins) in util.end_statement:
        return
    else:
        vartypes.pass_int_keep(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)


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
    if util.skip_white_read_if(ins, '\x91'):  #PRINT
        exec_view_print(ins)
    else:
        exec_view_graph(ins)
        
    
def exec_line(ins):
    if util.skip_white_read_if(ins, '\x85'): #INPUT
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
# pen and stick


# pen        
def exec_pen(ins):
    d = util.skip_white(ins)
    if d=='\x95': # ON
        ins.read(1)
        events.pen_enabled = True
        events.pen_stopped = False
        console.pen_on()
    elif d=='\xDD': # OFF
        ins.read(1)
        events.pen_enabled = False
        console.pen_off()
    elif d=='\x90': # STOP
        ins.read(1)
        events.pen_stopped = True
    util.require(ins, util.end_statement)

# strig: stick trigger        
def exec_strig(ins):
    d = util.skip_white(ins)
    if d=='(':
        # strig (n)
        num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        if num not in (0,2,4,6):
            raise error.RunError(5)
        joy = num//4
        trig = (num//2)%2
        d = util.skip_white_read(ins)
        if d == '\x95': # ON
            events.stick_enabled[joy][trig] = True
            events.stick_stopped[joy][trig] = True
        elif d == '\xDD': # OFF
            events.stick_enabled[joy][trig] = False
        elif d == '\x90': # STOP
            events.stick_stopped[joy][trig] = True
        else:
            raise error.RunError(2)
    else:
        if d == '\x95': # ON
            ins.read(1)
            console.stick_on()
        elif d == '\xDD': # OFF
            ins.read(1)
            console.stick_off()
        else:
            raise error.RunError(2)
    util.require(ins, util.end_statement)
    
    

