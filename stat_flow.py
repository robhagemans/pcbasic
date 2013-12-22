#
# PC-BASIC 3.23 - stat_flow.py
#
# Flow-control statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import glob
import error
import events
import program

import fp
import vartypes
import var
import expressions
import rnd
import fileio
import oslayer

from util import *
from stat_code import exec_load



def exec_cont():
    if program.stop==None:
        raise error.RunError(17)
    else:    
        program.bytecode.seek(program.stop[0])
        program.linenum=program.stop[1]
        program.set_runmode()


    # IN GW-BASIC, weird things happen if you do GOSUB nn :PRINT "x"
    # and there's a STOP in the subroutine. 
    # CONT then continues and the rest of the original line is executed, printing x
    # However, CONT:PRINT triggers a bug - a syntax error in a nonexistant line number is reported.
    # CONT:PRINT "y" results in neither x nor y being printed.
    # if a command is executed before CONT, x is not printed.
    
    # in this implementation, the CONT command will overwrite the line buffer so x is not printed.
    
    

def exec_error(ins):
    errn = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    
    if errn<1 or errn>255:
        # illegal function call
        errn=5 
    
    raise error.RunError(errn)                
 

    

def exec_end():
    program.bytecode.seek(0)
    program.unset_runmode()

    fileio.close_all()
              
def exec_else(ins):
    # any else statement by itself means the THEN has already been executed, so it's really like a REM.
    skip_to(ins, end_line)    


def exec_while(ins, first=True):
    # just after WHILE opcode
    whilepos = ins.tell()
    
    # evaluate the 'boolean' expression 
    # use double to avoid overflows  
    boolvar = vartypes.pass_double_keep(expressions.parse_expression(ins))
    
    if first:
        # find matching WEND
        current = ins.tell()
        skip_to_next(ins, '\xB1', '\xB2')  # WHILE, WEND
        if ins.read(1)=='\xB2':
            skip_to(ins, end_statement)
            wendpos = ins.tell()
            program.while_wend_stack.append([whilepos, program.linenum, wendpos]) 
        else: 
            # WHILE without WEND
            raise error.RunError(29)
        ins.seek(current)    

    # condition is zero?
    if fp.is_zero(fp.unpack(boolvar)) :
        # jump to WEND
        [whilepos, program.linenum, wendpos] = program.while_wend_stack.pop()
        ins.seek(wendpos)


def exec_for(ins): #, first=True):

    # just after FOR opcode
    forpos = ins.tell()
    
    # read variable  
    skip_white(ins)
    varname = var.getvarname(ins)
    if varname=='':
        raise error.RunError(2)
    
    vartype = varname[-1]
    if vartype == '$':
        raise error.RunError(13)
    
    require_read(ins, '\xE7') # =
    start = expressions.parse_expression(ins)

    require_read(ins, '\xCC')  # TO    
    stop = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))

    if skip_white_read_if(ins,'\xCF'): # STEP
        step = vartypes.pass_type_keep(vartype, expressions.parse_expression(ins))
    else:
        # convert 1 to vartype
        step = vartypes.pass_type_keep(vartype, ('%', 1))
    
    require(ins, end_statement)
    
    # set loopvar to start
    # apply initial condition
    loopvar = vartypes.pass_type_keep(vartype, start)
    var.setvar(varname, start)
    
    # find NEXT and push to stack
    for_push_next(ins, forpos, varname, start, stop, step)

    # check condition and jump if necessary
    for_jump_if_ends(ins, loopvar, stop, step)
    

    
def for_push_next(ins, forpos, varname, start, stop, step):    
    # find matching NEXT
    current = ins.tell()
    nextline = skip_to_next(ins, '\x82', '\x83', allow_comma=True)  # FOR, NEXT
    
    # FOR without NEXT
    require(ins, ('\x83', ','), err=26)
    comma = (ins.read(1)==',')
        
    
    # check var name for NEXT
    skip_white(ins)
    varname2 = var.getvarname(ins)
    skip_white(ins)
    nextpos = ins.tell()
    
    # no-var only allowed in standalone NEXT
    if varname2=='':
        if peek(ins) not in end_statement:
            # syntax error
            raise error.RunError(2, nextline)
        #if comma:
        #    # NEXT without FOR
        #    raise error.RunError(1, nextline)
        # this error is only raised on reaching the NEXT statement
            
    if varname2 == varname or varname2 == '':
        program.for_next_stack.append([forpos, program.linenum, varname, nextpos, nextline, start, stop, step]) 
    else:
        # NEXT without FOR
        raise error.RunError(1, nextline)
    ins.seek(current)    
    
    

def for_iterate(ins):    
    # skip to end of FOR statement
    skip_to(ins, end_statement)
    [_, _, varname, _, _, start, stop, step] = program.for_next_stack[-1]

    # increment counter
    loopvar = var.getvar(varname)
    loopvar = vartypes.vplus(loopvar, step)
    var.setvar(varname, loopvar)
    
    # check condition and jump if necessary
    for_jump_if_ends(ins, loopvar, stop, step)
    
    
    
def for_jump_if_ends(ins, loopvar, stop, step):
    if for_loop_ends(loopvar, stop, step):
        # jump to just after NEXT
        [_, program.linenum, _, nextpos, nextline, _, _, _] = program.for_next_stack.pop()
        ins.seek(nextpos)
        
        d = skip_white(ins)
        if d not in end_statement+(',',):
            raise error.RunError(2, nextline)
        elif d==',':
            # we're jumping into a comma'ed NEXT, call exec_next (which may call for_iterate which will call us again)
            ins.read(1)
            exec_next(ins, True)
          
        # we should be at end statement at this point.


    
def for_loop_ends(loopvar, stop, step):
    # check TO condition
    loop_ends=False
    # step 0 is infinite loop
    if vartypes.vsgn(step)[1] < 0:
        loop_ends = vartypes.int_to_bool(vartypes.vgt(stop, loopvar)) 
    elif vartypes.vsgn(step)[1] > 0:
        loop_ends = vartypes.int_to_bool(vartypes.vgt(loopvar, stop)) 
    return loop_ends
            

def exec_next(ins, comma=False):
    curpos = ins.tell()
    skip_to(ins, end_statement+(',',))
    
    while True:
        if len(program.for_next_stack) == 0:
            # next without for
            raise error.RunError(1) #1  
        [forpos, forline, varname, nextpos, nextline, start, stop, step] = program.for_next_stack[-1]
        
        if ins.tell() != nextpos:
            # not the expected next, we must have jumped out
            program.for_next_stack.pop()
        else:
            # found it
            break
    
    ins.seek(curpos)
    
    # check if varname is correct, if provided
    if skip_white(ins) in end_statement and not comma:
        # no varname required if standalone NEXT
        pass
    else:
        varname2 = var.getvarname(ins)
        if varname==varname2:
            skip_to(ins, end_statement)
        #elif varname2=='':
        #    raise error.RunError(2)    
        else:
            # next without for
            raise error.RunError(1, nextline) #1    
    
    
    # JUMP to FOR statement
    program.linenum = forline
    ins.seek(forpos)
    for_iterate(ins)
    



def exec_goto(ins):    
    jumpnum = parse_jumpnum(ins)    
    skip_to(ins, end_statement)
    program.jump(jumpnum)

    
def exec_run(ins):
    
    # reset random number generator
    rnd.clear()

    # close all open files
    fileio.close_all()
    
    c = skip_white(ins)

    
    if c in ('\x0d', '\x0e'):
        jumpnum = parse_jumpnum(ins)
        skip_to(ins, end_statement)
    
        program.reset_program()
    
        program.jump(jumpnum)
    elif c not in end_statement:
        exec_load(ins)
    else:
        program.reset_program()
    
    
    program.set_runmode()
    

                
def exec_gosub(ins):
    jumpnum = parse_jumpnum(ins)
    # ignore rest of statement ('GOSUB 100 LAH' works just fine..) 
    skip_to(ins, end_statement)
    # set return position
    program.gosub_return.append([ins.tell(), program.linenum, ins])
    program.jump(jumpnum)
    


 
def exec_if(ins):
    skip_white(ins) 
    
    # GW-BASIC doesn't overflow in IFs, so uses double rather than bool?
    expr = expressions.parse_expression(ins)
    val = vartypes.pass_single_keep(expr)
    
    d = skip_white_read(ins)
    if d not in ('\xCD', '\x89'): # THEN, GOTO
        raise error.RunError(2)
    
    # if TRUE, continue after THEN
    if not fp.is_zero(fp.unpack(val)): #val != 0:
        # line number or statement is implied GOTO
        d = skip_white(ins)
        
        if d in ('\x0d', '\x0e'):  
            # line number (jump)
            exec_goto(ins)    
        
        # continue parsing as normal, :ELSE will be ignored anyway
        return
            
    else:
        # find ELSE block or end of line
        # ELSEs are nesting on the line
        nesting_counter = 0
        
        while True:    
            d = skip_to_read(ins, end_statement + ('\xCD',))
             
            if d == '\xCD': # THEN
                # another THEN statement means another nesting step
                nesting_counter += 1            
            elif d==':':
                if peek(ins) == '\xa1': # :ELSE is ELSE
                    if  nesting_counter==0:
                        # drop ELSE token and continue from here
                        ins.read(1)
                        break
                    else:
                        nesting_counter -= 1
                
            elif d in end_line:
                if d!='':
                    ins.seek(-1,1)
                break
        return            


def exec_wend(ins):
    #skip_white(ins)                
    
    # while will actually syntax error on the first run if anything is in the way.
    require(ins, end_statement)
    
    #curpos = ins.tell()
    while True:
        if len(program.while_wend_stack) == 0:
            # WEND without WHILE
            raise error.RunError(30) #1  
        [whilepos, whileline, wendpos] = program.while_wend_stack[-1]
        
        if ins.tell() != wendpos:
            # not the expected WEND, we must have jumped out
            program.while_wend_stack.pop()
        else:
            # found it
            break
    
    #ins.seek(curpos)
    
    #if len(program.while_wend_stack) == 0:
    #    # WEND without WHILE
    #    raise error.RunError(30)
    #    
    ## jump to WHILE
    #[whilepos, whileline, wendpos] = program.while_wend_stack[-1]
    
    program.linenum = whileline
    ins.seek(whilepos)
    exec_while(ins, False)

def exec_on(ins):
    c = skip_white(ins)
    command  = ''
    if c =='\xA7': # ERROR:
        ins.read(1)
        exec_on_error(ins)
        return
    elif c=='\xC9': # KEY
        ins.read(1)
        exec_on_key(ins)
        return
    elif c=='\xFE':
        c = peek(ins,2)
        if c== '\xFE\x94': # FE94 TIMER
            ins.read(2)
            exec_on_timer(ins)
            return
        elif c == '\xFE\x93':   # PLAy
            ins.read(2)
            exec_on_play(ins)
            return
        elif c in ('\xFE\x90'):   # COM
            ins.read(2)
            exec_on_com(ins)
            return
    elif c== '\xFF':
        if peek(ins,2) in ('\xFF\xA0','\xFF\xA2'):  # PEN, STRIG
            # TODO: not implemented
            ins.read(2)
            # advanced feature
            raise error.RunError(73)
    
    on = expressions.parse_expression(ins)
    if on==('',''):
        onvar=0
    else:
        onvar = vartypes.pass_int_keep(on)[1]
    command = skip_white_read(ins)

    jumps = []
    while True:
        d = skip_white_read(ins)
        if d in end_statement:
            if d!='':
                ins.seek(-1,1)
            break
        elif d in ('\x0d', '\x0e'):
            jumps.append( ins.tell()-1 ) 
            ins.read(2)
            #uint_to_value(ins.read(2)))
        elif d == ',':
            pass    
        else:  
            raise error.RunError(2)
    
    if jumps == []:
        raise error.RunError(2)
    if onvar < 0:
        raise error.RunError(5)
    elif onvar > 0 and onvar <= len(jumps):
        ins.seek(jumps[onvar-1])        
        
        if command == '\x89': # GOTO
            exec_goto(ins)
        elif command == '\x8d': # GOSUB
            exec_gosub(ins)
        
    skip_to(ins, end_statement)    


def parse_on_event(ins):
    num = expressions.parse_bracket(ins)
    if skip_white_read(ins) != '\x8D': # GOSUB
        raise error.RunError(2)    
    
    jumpnum = parse_jumpnum(ins)
    if jumpnum==0:
        jumpnum=-1
 
    if skip_white(ins) not in end_statement:
        raise error.RunError(2)    
 
    return num, jumpnum   
    


def exec_on_key(ins):
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_keep(keynum)[1]
    if keynum<1 or keynum>20:    
        raise error.RunError(5)
    
    events.key_events[keynum-1] = jumpnum
    

def exec_on_timer(ins):
    timeval, jumpnum = parse_on_event(ins)
    timeval = vartypes.pass_single_keep(timeval)
    events.timer_period = fp.round_to_int(fp.mul(fp.unpack(timeval), fp.from_int(fp.MBF_class, 1000)))
    events.timer_event = jumpnum
    

def exec_on_play(ins):
    playval, jumpnum = parse_on_event(ins)
    playval = vartypes.pass_int_keep(playval)[1]
    events.play_trig = playval
    events.play_event = jumpnum
    
    
def exec_on_com(ins):
    keynum, jumpnum = parse_on_event(ins)
    keynum = vartypes.pass_int_keep(keynum)[1]
    if keynum<1 or keynum>2:    
        raise error.RunError(5)
    
    events.com_event[keynum-1] = jumpnum

def exec_com(ins):    
    if skip_white(ins)=='(':
        # key (n)
        num = vartypes.pass_int_keep(expressions.parse_bracket(ins))[1]
        if num<1 or num>2:
            raise error.RunError(5)

        d=skip_white_read(ins)
        # others are ignored
        if num >=1 and num <= 20:
            if d=='\x95': # ON
                events.key_enabled[num-1] = True
                events.key_stopped[num-1]= False
            elif d=='\xDD': # OFF
                events.key_enabled[num-1] = True
            elif d=='\x90': # STOP
                events.key_stopped[num-1]=True
            else:
                raise error.RunError(2)
    else:
        raise error.RunError(2)

    require(ins, end_statement)

def exec_timer(ins):
    # ON, OFF, STOP
    d = skip_white(ins)
    if d == '\x95': # ON
        ins.read(1)
        events.timer_start = oslayer.timer_milliseconds()
        events.timer_enabled = True
    elif d == '\xdd': # OFF
        ins.read(1)
        events.timer_enabled = False
    elif d== '\x90': #STOP
        ins.read(1)
        events.timer_stopped = True
    else:
        raise error.RunError(2)      

    require(ins, end_statement)      




def exec_on_error(ins):
    if skip_white(ins) != '\x89':  # GOTO
        raise error.RunError(2)
    else:
        ins.read(1)
    error.on_error = parse_jumpnum(ins)
    
    # ON ERROR GOTO 0 in error handler
    if error.on_error==0 and error.error_handle_mode:
        # re-raise the error so that execution stops
        raise error.RunError(error.errn)
    
    if skip_white(ins) not in end_statement:
        #error.on_error=0 
        # this will be caught by the trapping routine just set
        error.RunError(2)        
    
        
def exec_resume(ins):
    if error.error_resume == None: # resume without error
        error.on_error=0
        raise error.RunError(20)
    
    start_statement, codestream, runmode = error.error_resume  
       
    c= skip_white(ins)
    jumpnum=0
    if c == '\x83': # NEXT
        # RESUME NEXT
        codestream.seek(start_statement)        
        skip_to(codestream, end_statement, break_on_first_char=False)
        program.set_runmode(runmode)
        # what happens if something is on the line after NEXT?
        
    elif c not in end_statement:
        jumpnum = parse_jumpnum(ins)
        if jumpnum != 0:
            # RESUME n
            program.jump(jumpnum)
            program.set_runmode()
            
    if c != '\x83' and jumpnum==0: 
        # RESUME or RESUME 0 
        codestream.seek(start_statement)        
        program.set_runmode(runmode)
    
    error.errn=0
    error.error_handle_mode = False
    error.error_resume= None
                 



   
    


def exec_return(ins):
    if program.gosub_return == []: 
        # RETURN without GOSUB
        raise error.RunError(3)
    else:
        # a tad inelegant...
        data = program.gosub_return.pop()
        if len(data) ==3:
            [pos, program.linenum, buf] = data
        elif len(data)==4:
            # returning from ON KEY GOSUB, re-enable key
            [pos, program.linenum, buf, keynum] = data
            if keynum >0:
                events.key_stopped[keynum-1] = False
            else:
                # ON TIMER
                events.timer_stopped =False
                
        if buf != ins:
            # move to end of program to avoid executing anything else on the RETURN line if called from direct mode   
            ins.seek(-1)
            program.unset_runmode()
        
        # go back to position of GOSUB
        buf.seek(pos)
        
        
        

def exec_stop(ins):
    
    d = skip_white_read(ins)
    if d in end_statement:
        raise error.Break()
    else:
        raise error.RunError(2)
     



