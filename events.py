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


import glob
import sound
import vartypes
import oslayer
import deviceio
import console
import program


# create variables    
reset_events()    

# default codes for KEY autotext
key_replace = [ 'LIST ', 'RUN\x0d', 'LOAD"', 'SAVE"', 'CONT\x0d', ',"LPT1:"\x0d','TRON\x0d', 'TROFF\x0d', 'KEY ', 'SCREEN 0,0,0\x0d' ]

# ON KEY handling
events_stopped = False    


def reset_events():
    global key_events, key_numbers, key_enabled, key_stopped, key_triggered
    global timer_enabled, timer_event, timer_period, timer_start, timer_stopped
    global play_enabled, play_stopped, play_event, play_last, play_trig
    global com_enabled, com_stopped, com_event

    key_events = [-1]*20    
    key_numbers = [ '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',     # F1-F5 
                    '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44',     # F6-F10
                    '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50',                 # up, left, right, down
                    '', '', '', '', '', '' ]                                        # user definable
    key_enabled = [False]*20
    key_stopped = [False]*20
    key_triggered = [False]*20

    timer_event = -1
    timer_period = ('%', 0)
    timer_start = ('%', 0)
    timer_enabled = False
    timer_stopped = False
    
    play_enabled = False
    play_stopped = False
    play_event = -1
    play_last = 0
    play_trig = 1
    
    com_enabled = [False,False]
    com_stopped = [False, False]
    com_event = [-1,-1]
    


# KEY replacement    
# apply KEY autotext to scancodes
def replace_key(c):
    if len(c) < 2 or c[0]!='\x00':
        return c
    
    # only check F1-F10
    for keynum in range(10):
        if c==key_numbers[keynum] and (not program.runmode() or not key_enabled[keynum]): # enabled means enabled for ON KEY events 
            return key_replace[keynum]
    
    return c
    
    
    
def check_events():
    global key_numbers, key_enabled, key_triggered
    
    if not program.runmode():
        return
    
    c = console.peek_char()
    if len(c) >0:
        keynum=-1
        if c in key_numbers:
            keynum = key_numbers.index(c)
        if keynum >-1 and keynum<20:
            if key_enabled[keynum]: #and not key_disabled[keynum]:
                # remove the char from buffer
                console.pass_char(c)
                
                # trigger only once at most
                key_triggered[keynum] = True
     
    
    
def handle_events():
    global events_stopped, key_events, key_stopped, key_triggered
    global timer_enabled, timer_event, timer_stopped, timer_start, timer_period
    global play_enabled, play_event, play_stopped, play_last, play_trig
    global com_enabled, com_event, com_stopped
    
    if not program.runmode():
        return
        
    if events_stopped:
        return
    
    if timer_enabled and timer_event!=-1 and not timer_stopped: # != []:
        mutimer = oslayer.timer_milliseconds() #stat_os.value_timer(0)
        if mutimer >= timer_start+timer_period:
            timer_start = mutimer
            jumpnum = timer_event
            timer_stopped=True 
            
            # execute 'on key' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, 0])
            program.jump(jumpnum)
                
            
    # key events are not handled FIFO but first 11-20 in that order, then 1-10.
    keyrange = range(10,20)+range(10)
    for keynum in keyrange:
        if key_triggered[keynum] and key_events[keynum] != -1 and not key_stopped[keynum]:
            jumpnum = key_events[keynum]   
            # temporarily turn off key event
            key_stopped[keynum] = True 
            key_triggered[keynum] = False 
            
            # execute 'on key' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, keynum+1])
            program.jump(jumpnum)
   
    if play_enabled and play_event !=-1 and not play_stopped:
        play_now = sound.music_queue_length()
        
        if play_last >= play_trig and play_now < play_trig:    
            jumpnum = play_event
            
            # execute 'on play' subroutine
            program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, keynum+1])
            program.jump(jumpnum)
               
        play_last = play_now
                
    for comport in (0, 1):
        if com_enabled[comport] and com_event[comport] !=-1 and not com_stopped[comport]:
            
            comc = ''
            if comport == 0 and deviceio.com1!=None:
                comc = deviceio.com1.peek_chars(1)
            elif comport == 1 and deviceio.com2!=None:
                comc = deviceio.com2.peek_chars(1)
            
            if comc != '':    
                jumpnum = com_event[comport]
                
                # execute 'on play' subroutine
                program.gosub_return.append([program.current_codestream.tell(), program.linenum, program.current_codestream, keynum+1])
                program.jump(jumpnum)
                   
            
        
        
