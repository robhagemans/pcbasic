#
# PC-BASIC 3.23 - events.py
#
# User-defined event handling 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sound
import oslayer
import deviceio
import console
import program
import vartypes

# default codes for KEY autotext
key_replace = [ 'LIST ', 'RUN\x0d', 'LOAD"', 'SAVE"', 'CONT\x0d', ',"LPT1:"\x0d','TRON\x0d', 'TROFF\x0d', 'KEY ', 'SCREEN 0,0,0\x0d' ]

# KEY replacement    
# apply KEY autotext to scancodes
def replace_key(c):
    if len(c) < 2 or c[0] != '\x00':
        return c
    # only check F1-F10
    for keynum in range(10):
        if c == key_numbers[keynum] and (not program.runmode() or not key_enabled[keynum]): # enabled means enabled for ON KEY events 
            return key_replace[keynum]
    return c

def reset_events():
    reset_key_events()
    reset_timer_events()
    reset_play_events()
    reset_com_events()
    reset_pen_events()
    reset_strig_events()
    
def reset_key_events():        
    global key_events, key_numbers, key_enabled, key_stopped, key_triggered
    key_events = [-1]*20    
    key_numbers = [ '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',     # F1-F5 
                    '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44',     # F6-F10
                    '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50',                 # up, left, right, down
                    '', '', '', '', '', '' ]                                        # user definable
    key_enabled = [False]*20
    key_stopped = [False]*20
    key_triggered = [False]*20

def reset_timer_events():
    global timer_enabled, timer_event, timer_period, timer_start, timer_stopped
    timer_event = -1
    timer_period = vartypes.null['%']
    timer_start = vartypes.null['%']
    timer_enabled = False
    timer_stopped = False
    
def reset_play_events():
    global play_enabled, play_stopped, play_event, play_last, play_trig
    play_enabled = False
    play_stopped = False
    play_event = -1
    play_last = 0
    play_trig = 1

def reset_com_events():
    global com_enabled, com_stopped, com_event
    com_enabled = [False,False]
    com_stopped = [False, False]
    com_event = [-1,-1]

def reset_pen_events():    
    global pen_enabled, pen_stopped, pen_triggered, pen_event
    pen_enabled = False
    pen_stopped = False
    pen_triggered = False
    pen_event = -1
    
def reset_string_events():        
    global stick_enabled, stick_stopped, stick_triggered, stick_event
    stick_enabled = [[False, False], [False, False]]
    stick_stopped = [[False, False], [False, False]]
    stick_triggered = [[False, False], [False, False]]
    stick_event = [[-1,-1],[-1,-1]]
        
# create variables    
reset_events()    
    
def check_events():
    # events only caught in runmode
    if not program.runmode():
        return
    # handle all events            
    handle_timer_event()    
    handle_key_event()    
    handle_play_event()    
    handle_com_event()
    handle_pen_event()
    handle_strig_event()    

def handle_timer_event():        
    global timer_stopped, timer_start
    if timer_enabled and timer_event != -1 and not timer_stopped: 
        mutimer = oslayer.timer_milliseconds() 
        if mutimer >= timer_start + timer_period:
            timer_start = mutimer
            jumpnum = timer_event
            timer_stopped = True 
            # execute 'on TIMER' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
            program.jump(jumpnum)

def handle_key_event():
    global key_stopped, key_triggered
    # check KEY events    
    c = console.peek_char()
    if len(c) > 0:
        keynum = -1
        if c in key_numbers:
            keynum = key_numbers.index(c)
        if keynum > -1 and keynum < 20:
            if key_enabled[keynum]:
                # remove the char from buffer
                console.pass_char(c)
                # trigger only once at most
                key_triggered[keynum] = True
    # key events are not handled FIFO but first 11-20 in that order, then 1-10.
    keyrange = range(10, 20) + range(10)
    for keynum in keyrange:
        if key_triggered[keynum] and key_events[keynum] != -1 and not key_stopped[keynum]:
            jumpnum = key_events[keynum]   
            # temporarily turn off key event
            key_stopped[keynum] = True 
            key_triggered[keynum] = False 
            # execute 'on KEY' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, keynum+1])
            program.jump(jumpnum)

def handle_play_event():
    global play_stopped, play_last
    if play_enabled and play_event != -1 and not play_stopped:
        play_now = sound.music_queue_length()
        if play_last >= play_trig and play_now < play_trig:    
            jumpnum = play_event
            # TODO: don't we need this?:
            # play_stopped = True
            # execute 'on play' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
            program.jump(jumpnum)
        play_last = play_now

def handle_com_event():
    global com_stopped
    for comport in (0, 1):
        if com_enabled[comport] and com_event[comport] !=-1 and not com_stopped[comport]:
            comc = ''
            if comport == 0 and deviceio.com1 != None:
                comc = deviceio.com1.peek_char()
            elif comport == 1 and deviceio.com2 != None:
                comc = deviceio.com2.peek_char()
            if comc != '':    
                jumpnum = com_event[comport]
                # TODO: don't we need this?:
                # com_stopped = True
                # execute 'on COM' subroutine
                program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
                program.jump(jumpnum)

def handle_pen_event():
    global pen_stopped, pen_triggered
    if not pen_enabled:
        pen_triggered = False
    if pen_enabled and pen_triggered and pen_event != -1 and not pen_stopped:
        pen_triggered = False
        jumpnum = pen_event
        # TODO: don't we need this?:
        # pen_stopped = True
        # execute 'on pen' subroutine
        program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
        program.jump(jumpnum)

def handle_strig_event():
    global stick_enabled, stick_stopped, stick_triggered, stick_event
    for stick in (0,1):
        for trig in (0,1):
            if not stick_enabled[stick][trig]:
                stick_triggered[stick][trig] = False
            if (  stick_enabled[stick][trig] and stick_triggered[stick][trig] 
                  and stick_event[stick][trig] != -1 and not stick_stopped[stick][trig]  ):
                stick_triggered[stick][trig] = False
                # TODO: don't we need this?:
                # stick_stopped = True
                jumpnum = stick_event[stick][trig]
                # execute 'on strig' subroutine
                program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
                program.jump(jumpnum)
        
        
