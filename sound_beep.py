#
# PC-BASIC 3.23 - sound_beep.py
#
# Sound implementation through the linux beep utility
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import subprocess
import state

now_playing = None
now_loop = None

def init_sound():
    return subprocess.call("command -v beep >/dev/null 2>&1", shell=True) == 0
    
def stop_all_sound():
    global now_loop
    if now_playing and now_playing.poll() == None:
        now_playing.terminate()   
        now_loop = None
        subprocess.call('beep -f 1 -l 0'.split()) 
    
def play_sound(frequency, duration, fill, loop):
    pass
        
def check_sound():
    global now_loop
    length = len(state.console_state.music_queue)
    if now_loop:
        if state.console_state.music_queue and now_playing and now_playing.poll() == None:
            now_playing.terminate()
            now_loop = None
            subprocess.call('beep -f 1 -l 0'.split())
        elif not now_playing or now_playing.poll() != None:
            play_now(*now_loop)
    if length and (not now_playing or now_playing.poll() != None):
        play_now(*state.console_state.music_queue[0])
        length -= 1
    return length
    
def busy():
    return (not now_loop) and now_playing and now_playing.poll() == None

def play_now(frequency, duration, fill, loop):
    global now_playing, now_loop
    frequency = max(1, min(19999, frequency))
    if loop:
        duration = 5
        fill = 1
        now_loop = (frequency, duration, fill, loop)
    now_playing = subprocess.Popen(('beep -f %f -l %d -D %d' % (frequency, duration*fill*1000, duration*(1-fill)*1000) ).split())
    
      
