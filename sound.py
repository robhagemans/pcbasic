#
# PC-BASIC 3.23 - sound.py
#
# Sound frontend implementation
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import state
import event_loop

state.console_state.music_foreground = True
state.console_state.music_queue = []

def init_sound():
    if not state.sound.init_sound():
        return False
    # rebuild sound queue    
    for note in state.console_state.music_queue:
        state.sound.play_sound(*note)
    return True
    
def music_queue_length():
    # top of sound_queue is currently playing
    return max(0, len(state.console_state.music_queue)-1)
    
def beep():
    play_sound(800, 0.25)

def play_sound(frequency, duration, fill=1, loop=False):
    state.console_state.music_queue.append((frequency, duration, fill, loop))
    state.sound.play_sound(frequency, duration, fill, loop) 
    # at most 16 notes in the sound queue (not 32 as the guide says!)
    wait_music(15)    

def stop_all_sound():
    state.console_state.music_queue = []
    state.sound.stop_all_sound()
        
def wait_music(wait_length=0, wait_last=True):
    while (wait_last and state.sound.busy()) or len(state.console_state.music_queue) + wait_last - 1 > wait_length:
        event_loop.idle()
        event_loop.check_events()

def check_sound():
    queue_length = state.sound.check_sound()
    # remove the notes that have been played
    while len(state.console_state.music_queue) > queue_length:
        state.console_state.music_queue.pop(0)
    
