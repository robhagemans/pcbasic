#
# PC-BASIC 3.23 - nosound.py
#
# Null sound implementation
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import datetime
import state

music_queue = [ [], [], [], [] ]

def init_sound():
    return True
    
def stop_all_sound():
    global music_queue
    music_queue = [ [], [], [], [] ]
    
def play_sound(frequency, duration, fill=1, loop=False, voice=0, volume=15):
    if music_queue[voice]:
        latest = max(music_queue[voice])
    else:    
        latest = datetime.datetime.now()
    music_queue[voice].append(latest + datetime.timedelta(seconds=duration))
        
def check_sound():
    now = datetime.datetime.now()
    for voice in range(4):
        while music_queue[voice] and now >= music_queue[voice][0]:
            music_queue[voice].pop(0)
        # remove the notes that have been played
        while len(state.console_state.music_queue[voice]) > len(music_queue[voice]):
            state.console_state.music_queue[voice].pop(0)
    
def busy():
    return False        
      
