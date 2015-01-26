"""
PC-BASIC 3.23 - nosound.py
Null sound implementation

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import datetime
import state
import backend

music_queue = [ [], [], [], [] ]


def init_sound():
    """ Initialise sound system. """
    return True
    
def stop_all_sound():
    """ Clear all sound queues. """
    global music_queue
    music_queue = [ [], [], [], [] ]
    
def play_sound(frequency, duration, fill=1, loop=False, voice=0, volume=15):
    """ Queue a sound for playing. """
    if music_queue[voice]:
        latest = max(music_queue[voice])
    else:    
        latest = datetime.datetime.now()
    music_queue[voice].append(latest + datetime.timedelta(seconds=duration))
        
def check_sound():
    """ Update the sound queue. """
    now = datetime.datetime.now()
    for voice in range(4):
        while music_queue[voice] and now >= music_queue[voice][0]:
            music_queue[voice].pop(0)
        # remove the notes that have been played
        backend.sound_done(voice, len(music_queue[voice]))
    
def busy():
    """ Is the mixer busy? """
    return False        

def set_noise(is_white):
    """ Set the character of the noise channel. """
    pass      

def quit_sound():
    """ Shut down the mixer. """
    pass

