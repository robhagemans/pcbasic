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

now_playing = [None, None, None, None]
now_loop = [None, None, None, None]

def init_sound():
    return subprocess.call("command -v beep >/dev/null 2>&1", shell=True) == 0
    
def stop_all_sound():
    global now_loop
    for voice in now_playing:
        if voice and voice.poll() == None:
            voice.terminate()   
    now_playing = [None, None, None, None]
    now_loop = [None, None, None, None]
    subprocess.call('beep -f 1 -l 0'.split()) 
    
def play_sound(frequency, duration, fill, loop, voice=0, volume=15):
    pass
        
def check_sound():
    global now_loop
    for voice in range(4):
        length = len(state.console_state.music_queue[voice])
        if now_loop[voice]:
            if state.console_state.music_queue[voice] and now_playing[voice] and now_playing[voice].poll() == None:
                now_playing[voice].terminate()
                now_loop[voice] = None
                subprocess.call('beep -f 1 -l 0'.split())
            elif not now_playing[voice] or now_playing[voice].poll() != None:
                play_now(*now_loop[voice], voice=voice)
        if length and (not now_playing[voice] or now_playing[voice].poll() != None):
            play_now(*state.console_state.music_queue[voice][0], voice=voice)
            length -= 1
        # remove the notes that have been played
        while len(state.console_state.music_queue[voice]) > length:
            state.console_state.music_queue[voice].pop(0)
    
def busy():
    is_busy = False
    for voice in range(4):
        is_busy = is_busy or ((not now_loop[voice]) and now_playing[voice] and now_playing[voice].poll() == None)
    return is_busy

def play_now(frequency, duration, fill, loop, volume, voice):
    frequency = max(1, min(19999, frequency))
    if loop:
        duration = 5
        fill = 1
        now_loop[voice] = (frequency, duration, fill, loop, volume)
    if voice == 3:
        # ignore noise channel
        pass
    else:    
        now_playing[voice] = subprocess.Popen(('beep -f %f -l %d -D %d' % (frequency, duration*fill*1000, duration*(1-fill)*1000)).split())
    
def set_noise(is_white):
    pass      
      
