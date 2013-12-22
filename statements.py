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


import sys
import StringIO

import glob
import error
import fp
import vartypes
import var
import rnd
import fileio

from util import *

import expressions
import tokenise
import program

import run

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

tron = False

#######################################################
#
# STATEMENTS
#


# parses one statement at the current stream pointer in glob.current_codestream
# return value False: stream ends
def parse_statement():
    global tron
            
    ins = program.current_codestream
    program.current_statement = ins.tell()

    
    c = skip_white_read(ins).upper()
    if c=='':
        # stream has ended.
        return False
    
    # code stream should either be at '\x00' or at ':' to start a statement
    if c=='\x00':
        # line number marker, new statement
        program.linenum = parse_line_number(ins)

        if program.linenum == -1:
            program.unset_runmode()
            return False
            
        if tron:
            glob.scrn.write('['+('%i' % program.linenum) +']')
            
        c = skip_white_read(ins).upper()
    
    elif c==':':
        # new statement
        c = skip_white_read(ins).upper()
    # else:
        #internal error  
      
        
    if c in end_statement:
        # empty statement, return to parse next
        if c!='':
            ins.seek(-1,1)
        return True
        
    elif c=='\x81':     # END
        exec_end()
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
    elif c=='\x88' or c>= 'A' and c <= 'Z' :
        if c=='\x88':   # LET
            d = skip_white_read(ins)
            if d == '':
                raise error.RunError(2)
        ins.seek(-1,1)
        exec_let(ins)
    elif c=='\x89':     # GOTO
        exec_goto(ins)
    elif c=='\x8A':     # RUN
        exec_run(ins)
    elif c=='\x8B':     # IF
        exec_if(ins)
    elif c=='\x8C':     # RESTORE
        exec_restore()
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
        exec_list(ins, glob.scrn)      
    elif c=='\x94':     # NEW
        exec_new()
    elif c=='\x95':     # ON
        exec_on(ins)
    elif c=='\x96':     # WAIT
        exec_wait(ins)
    elif c=='\x97':     # DEF
        exec_def(ins)
    elif c=='\x98':     # POKE
        exec_poke(ins)
    elif c=='\x99':     # CONT
        exec_cont()
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
        exec_deftype('$', ins)
    elif c=='\xAD':   # DEFINT   
        exec_deftype('%', ins)
    elif c=='\xAE':   # DEFSNG    
        exec_deftype('!', ins)
    elif c=='\xAF':   # DEFDBL    
        exec_deftype('#', ins)    
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
        exec_sound(ins)        
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
    
    elif c=='\xFD':
        c = ins.read(1).upper()
        # syntax error
        raise error.RunError(2)
    
    elif c=='\xFE':
        c = ins.read(1).upper()
        if c=='\x81':    # FILES
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
    
    elif c=='\xFF':
        c = ins.read(1).upper()
        if c == '\x83':     # MID$ statement
            exec_mid(ins)
        elif c == '\xA0':     # PEN statement
            exec_pen(ins)
        elif c == '\xA2':     # Strig statement
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

def exec_system(ins): 
    if skip_white_read(ins) not in end_statement:
        raise error.RunError(2)    
    
    run.exit() 
        
def exec_tron(ins):
    global tron
    tron=True

def exec_troff(ins):
    global tron
    tron=False
   

    
def exec_randomize(ins):
    val = expressions.parse_expression(ins, allow_empty=True)
    if val==('',''):
        # prompt for random seed
        glob.scrn.write("Random number seed (-32768 to 32767)? ")
        line, interrupt = glob.scrn.read_screenline()
        if interrupt:
            raise error.Break()
        
        # should be interpreted as integer sint if it is
        #val = fp.pack(fp.from_str(line))
        val = tokenise.str_to_value_keep(('$', ''.join(line)))
        
    if val[0]=='$':
        raise error.RunError(5)

    if val[0]=='%':
        val = ('$', tokenise.value_to_sint(val[1]))    
    
    #rnd.randomize(val[1])         
    #def randomize(s):
    s = val[1]
    
    # on a program line, if a number outside the signed int range (or -32768) is entered,
    # the number is stored as a MBF double or float. Randomize then:
    #   - ignores the first 4 bytes (if it's a double)
    #   - reads the next two
    #   - xors them with the final two (most signifant including sign bit, and exponent)
    # and interprets them as a signed int 
    # e.g. 1#    = /x00/x00/x00/x00 /x00/x00/x00/x81 gets read as /x00/x00 ^ /x00/x81 = /x00/x81 -> 0x10000-0x8100 = -32512 (sign bit set)
    #      0.25# = /x00/x00/x00/x00 /x00/x00/x00/x7f gets read as /x00/x00 ^ /x00/x7f = /x00/x7F -> 0x7F00 = 32512 (sign bit not set)
    #              /xDE/xAD/xBE/xEF /xFF/x80/x00/x80 gets read as /xFF/x80 ^ /x00/x80 = /xFF/x00 -> 0x00FF = 255   

    final_two = s[-2:]
    mask = '\x00\x00'
    if len(s) >= 4:
        mask = s[-4:-2]
    final_two = chr(ord(final_two[0]) ^ ord(mask[0])) + chr(ord(final_two[1]) ^ ord(mask[1]))
    rnd.randomize_int(sint_to_value(final_two))        
    if skip_white(ins) not in end_statement:
        raise error.RunError(2)
    



def exec_rem(ins):
    # skip the rest, but parse numbers to avoid triggering EOL
    skip_to(ins, end_line)
    

# do-nothing MOTOR
def exec_motor(ins):
    d = skip_white(ins)
    
    if d in end_statement:
        return
    else:
        vartypes.pass_int_keep(expressions.parse_expression(ins))
        require(ins, end_statement)


def exec_def(ins):
    skip_white(ins)
    if peek(ins,1)=='\xD1': #FN
        ins.read(1)
        exec_def_fn(ins)
    elif peek(ins,3)=='SEG':
        ins.read(3)
        exec_def_seg(ins)
    elif peek(ins,3)=='USR':
        ins.read(3)
        exec_def_usr(ins)
    else:        
        raise error.RunError(2)      


def exec_view(ins):
    d=skip_white(ins)
    if d == '\x91':  #PRINT
        ins.read(1)
        exec_view_print(ins)
    else:
        exec_view_graph(ins)
        

    
def exec_line(ins):
    d = skip_white(ins)
       
    if d == '\x85': #INPUT
        ins.read(1)
        return exec_line_input(ins)
    
    exec_line_graph(ins)


def exec_get(ins):
    if skip_white(ins)=='(':
        exec_get_graph(ins)
    else:    
        exec_get_file(ins)
    
def exec_put(ins):
    if skip_white(ins)=='(':
        exec_put_graph(ins)
    else:    
        exec_put_file(ins)


def exec_DEBUG(ins):
    # this is not a GW-BASIC behaviour, but helps debugging.
    # this is parsed like a REM by the tokeniser.
    # rest of the line is considered to be a python statement
    d = skip_white(ins)
    
    debug = ''
    while peek(ins) not in end_line:
        d = ins.read(1)
        debug += d
        
    buf = StringIO.StringIO()
    sys.stdout = buf
    try:
        exec(debug)
    except Exception:
        print "[exception]"
        pass    
    sys.stdout = sys.__stdout__

    glob.scrn.write(buf.getvalue())
    
    
        
    
# do-nothing POKE        
def exec_poke(ins):
    addr = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require_read(ins, ',')
    val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require(ins, end_statement)
    
# do-nothing DEF SEG    
def exec_def_seg(ins):
    if skip_white_read_if(ins, '\xE7'): #=
        vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require(ins, end_statement)
        

# do-nothing DEF USR    
def exec_def_usr(ins):
    if peek(ins) in tokenise.ascii_digits:
        ins.read(1)
    require_read(ins, '\xE7')     
    vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require(ins, end_statement)


        
# bload: not implemented        
def exec_bload(ins):
    raise error.RunError(73)    

# bsave: not implemented        
def exec_bsave(ins):
    raise error.RunError(73)    
        
        
# call: not implemented        
def exec_call(ins):
    raise error.RunError(73)    
    
# strig: not implemented        
def exec_strig(ins):
    raise error.RunError(73)    

# pen: not implemented        
def exec_pen(ins):
    raise error.RunError(73)    
     
# wait: not implemented        
def exec_wait(ins):
    raise error.RunError(73)    
            
# do-nothing out       
def exec_out(ins):
    addr = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require_read(ins, ',')
    val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    require(ins, end_statement)
    
    #raise error.RunError(73)    
       
# ioctl: not implemented        
def exec_ioctl(ins):
    raise error.RunError(73)    
       
            
