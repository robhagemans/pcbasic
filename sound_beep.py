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
import console

music_foreground = True
music_queue = []
now_playing = None

def music_queue_length():
    return len(music_queue)
    
def beep():
    play_sound(800, 0.25)
    
def init_sound():
    return subprocess.call("command beep >/dev/null 2>&1", shell=True) == 0
    
def stop_all_sound():
    music_queue = []
    
def play_sound(frequency, duration, fill=1, loop=False):
    wait_music(15)    
    music_queue.append((frequency, duration, fill))
        
def check_sound():
    if music_queue and (not now_playing or now_playing.poll() != None):
        play_now(*music_queue.pop(0))
    
def wait_music(wait_length=0, wait_last=True):
    while (len(music_queue) > wait_length) or (wait_last and (now_playing and now_playing.poll() == None)):
        console.idle()
        console.check_events()
        check_sound()

def play_now(frequency, duration, fill):
    global now_playing
    now_playing = subprocess.Popen(['beep -f %f -l %d -D %d' % (frequency, duration*fill*1000, duration*(1-fill)*1000) ], shell=True)
    
      
