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
import backend

state.console_state.music_foreground = True
state.console_state.music_queue = [[], [], [], []]
state.console_state.sound_on = False

def init_sound():
    if not backend.sound.init_sound():
        return False
    # rebuild sound queue
    for voice in range(4):    
        for note in state.console_state.music_queue[voice]:
            backend.sound.play_sound(*note)
    return True
    
def music_queue_length(voice=0):
    # top of sound_queue is currently playing
    return max(0, len(state.console_state.music_queue[voice])-1)
    
def beep():
    play_sound(800, 0.25)

def play_sound(frequency, duration, fill=1, loop=False, voice=0, volume=15):
    state.console_state.music_queue[voice].append((frequency, duration, fill, loop, volume))
    backend.sound.play_sound(frequency, duration, fill, loop, voice, volume) 
    # at most 16 notes in the sound queue (not 32 as the guide says!)
    wait_music(15, wait_last=False)    

def stop_all_sound():
    state.console_state.music_queue = [ [], [], [], [] ]
    backend.sound.stop_all_sound()
        
def wait_music(wait_length=0, wait_last=True):
    while ((wait_last and backend.sound.busy()) 
                or len(state.console_state.music_queue[0]) + wait_last - 1 > wait_length
                or len(state.console_state.music_queue[1]) + wait_last - 1 > wait_length
                or len(state.console_state.music_queue[2]) + wait_last - 1 > wait_length ):
        backend.wait()
        
        
