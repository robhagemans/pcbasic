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

import sys
import logging

import plat
import config
import state 
import timedate

import novideo
import nosound
import nopenstick
import backend_cli
import backend_curses
import backend_pygame
import sound_beep

    
# backend implementations
video = None
audio = None 
penstick = None 

# sound queue
state.console_state.music_queue = [[], [], [], []]


#############################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global penstick, audio, video
    global pcjr_sound
    # set backends
    penstick = nopenstick
    audio = nosound
    if config.options['filter'] or config.options['conv'] or (
            not config.options['graphical'] and not config.options['ansi'] and (not plat.stdin_is_tty or not plat.stdout_is_tty)):
        # redirected input or output leads to dumbterm use
        video = novideo
        audio = nosound
    elif config.options['cli'] and plat.stdout_is_tty:
        video = backend_cli
        audio = sound_beep
    elif config.options['ansi'] and plat.stdout_is_tty:
        video = backend_curses
        audio = sound_beep
    else:   
        video = backend_pygame   
        penstick = backend_pygame
        audio = backend_pygame
    if config.options['nosound']:
        audio = nosound
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
