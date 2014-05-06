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

music_queue = []

def init_sound():
    return True
    
def stop_all_sound():
    global music_queue
    music_queue = []
    
def play_sound(frequency, duration, fill=1, loop=False):
    if music_queue:
        latest = max(music_queue)
    else:    
        latest = datetime.datetime.now()
    music_queue.append(latest + datetime.timedelta(seconds=duration))
        
def check_sound():
    now = datetime.datetime.now()
    while music_queue and now >= music_queue[0]:
        music_queue.pop(0)
    # remove the notes that have been played
    while len(state.console_state.music_queue) > len(music_queue):
        state.console_state.music_queue.pop(0)
    
def busy():
    return False        
      
