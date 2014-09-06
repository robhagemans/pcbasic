#
# PC-BASIC 3.23 - backend.py
#
# Backend modules and events
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
import novideo
import nosound
import nopenstick
import backend_cli
import backend_curses
import backend_pygame
import sound_beep
    
# backend implementations
video = None
sound = None 
penstick = None 

def prepare():
    """ Initialise backend module. """
    global penstick, sound, video
    # set backends
    penstick = nopenstick
    sound = nosound
    if config.options['filter'] or config.options['conv'] or (
            not config.options['graphical'] and not config.options['ansi'] and (not plat.stdin_is_tty or not plat.stdout_is_tty)):
        # redirected input or output leads to dumbterm use
        video = novideo
        sound = nosound
    elif config.options['cli'] and plat.stdout_is_tty:
        video = backend_cli
        sound = sound_beep
    elif config.options['ansi'] and plat.stdout_is_tty:
        video = backend_curses
        sound = sound_beep
    else:   
        video = backend_pygame   
        penstick = backend_pygame
        sound = backend_pygame
    if config.options['nosound']:
        sound = nosound
            
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
    global sound
    if sound.init_sound():
        return True
    logging.warning('Failed to initialise sound. Sound will be disabled.')
    sound = nosound
    return sound.init_sound()
    
def check_events():
    # manage sound queue
    sound.check_sound()
    # check console events
    video.check_events()   

def idle():
    video.idle()

def wait():
    video.idle()
    check_events()    

prepare()
