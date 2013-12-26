#
# PC-BASIC 3.23 - stat_sound.py
#
# Sound implementation
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

music_foreground=True
sound_queue = []

backend = None

def music_queue_length():
    global sound_queue
    return len(sound_queue)       
    
def beep():
    play_sound(800, 0.25)


def init_sound():
    return backend.init_sound()
    
def stop_all_sound():
    backend.stop_all_sound()

def play_sound(frequency, duration):
    backend.append_sound(frequency, duration)
     
def play_pause(duration):
    backend.append_pause(duration)
    
def check_sound():
    backend.check_sound()    

def wait_music():
    backend.wait_music()    


    

