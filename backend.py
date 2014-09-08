#
# PC-BASIC 3.23 - backend.py
#
# Backend modules and interface events
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import logging

import config
import state 
import timedate
    
# backend implementations
video = None
audio = None 
penstick = None 

# sound queue
state.console_state.music_queue = [[], [], [], []]
# keyboard queue
state.console_state.keybuf = ''
# key buffer
# INP(&H60) scancode
state.console_state.inp_key = 0
# keypressed status of caps, num, scroll, alt, ctrl, shift
state.console_state.keystatus = 0
# input has closed
input_closed = False


#############################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global pcjr_sound
    # pcjr/tandy sound
    pcjr_sound = config.options['pcjr_syntax']
            
def init_video():
    global video
    name = ''
    if video:
        if video.init():
            return True
        name = video.__name__
    logging.warning('Failed to initialise interface %s. Falling back to command-line interface.', name)
    video = backend_cli
    if video and video.init():
        return True
    logging.warning('Failed to initialise command-line interface. Falling back to filter interface.')
    video = novideo
    return video.init()
    
def init_sound():
    global audio
    if audio.init_sound():
        return True
    logging.warning('Failed to initialise sound. Sound will be disabled.')
    audio = nosound
    # rebuild sound queue
    for voice in range(4):    
        for note in state.console_state.music_queue[voice]:
            audio.play_sound(*note)
    return audio.init_sound()
    
def music_queue_length(voice=0):
    # top of sound_queue is currently playing
    return max(0, len(state.console_state.music_queue[voice])-1)

#############################################
# main event checker
    
def check_events():
    # manage sound queue
    audio.check_sound()
    # check console events
    video.check_events()   
    # trigger & handle BASIC events
    if state.basic_state.run_mode:
        # trigger TIMER, PLAY and COM events
        check_timer_event()
        check_play_event()
        check_com_events()
        # KEY, PEN and STRIG are triggered elsewhere
        # handle all events
        for handler in state.basic_state.all_handlers:
            handler.handle()

def idle():
    video.idle()

def wait():
    video.idle()
    check_events()    

##############################
# keyboard buffer read/write

# insert character into keyboard buffer; apply KEY repacement (for use by backends)
def insert_key(c):
    if len(c) > 0:
        try:
            keynum = state.basic_state.event_keys.index(c)
            if keynum > -1 and keynum < 20:
                if state.basic_state.key_handlers[keynum].enabled:
                    # trigger only once at most
                    state.basic_state.key_handlers[keynum].triggered = True
                    # don't enter into key buffer
                    return
        except ValueError:
            pass
    if state.console_state.caps and not ignore_caps:
        if c >= 'a' and c <= 'z':
            c = chr(ord(c)-32)
        elif c >= 'A' and c <= 'z':
            c = chr(ord(c)+32)
    if len(c) < 2:
        state.console_state.keybuf += c
    else:
        try:
            # only check F1-F10
            keynum = function_key[c]
            # can't be redefined in events - so must be event keys 1-10.
            if state.basic_state.run_mode and state.basic_state.key_handlers[keynum].enabled or keynum > 9:
                # this key is being trapped, don't replace
                state.console_state.keybuf += c
            else:
                state.console_state.keybuf += state.console_state.key_replace[keynum]
        except KeyError:
            state.console_state.keybuf += c

# peek character from keyboard buffer
def peek_char():
    ch = ''
    if len(state.console_state.keybuf)>0:
        ch = state.console_state.keybuf[0]
        if ch == '\x00' and len(state.console_state.keybuf) > 0:
            ch += state.console_state.keybuf[1]
    return ch 

# drop character from keyboard buffer
def pass_char(ch):
    state.console_state.keybuf = state.console_state.keybuf[len(ch):]        
    return ch

# blocking keystroke peek
def wait_char():
    while len(state.console_state.keybuf) == 0 and not input_closed:
        wait()
    return peek_char()

#############################################
# BASIC event triggers        
        
def check_timer_event():
    mutimer = timedate.timer_milliseconds() 
    if mutimer >= state.basic_state.timer_start + state.basic_state.timer_period:
        state.basic_state.timer_start = mutimer
        state.basic_state.timer_handler.triggered = True

def check_play_event():
    play_now = [music_queue_length(voice) for voice in range(3)]
    if pcjr_sound: 
        for voice in range(3):
            if ( play_now[voice] <= state.basic_state.play_trig and play_now[voice] > 0 and 
                    play_now[voice] != state.basic_state.play_last[voice] ):
                state.basic_state.play_handler.triggered = True 
    else:    
        if state.basic_state.play_last[0] >= state.basic_state.play_trig and play_now[0] < state.basic_state.play_trig:    
            state.basic_state.play_handler.triggered = True     
    state.basic_state.play_last = play_now

def check_com_events():
    ports = (state.io_state.devices['COM1:'], state.io_state.devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports[comport].peek_char():
            state.basic_state.com_handlers[comport].triggered = True


prepare()
