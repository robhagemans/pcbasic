#
# PC-BASIC 3.23 - nosound.py
#
# Null sound implementation
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys

def pre_init_sound():
    pass

def init_sound():    
    pass
    
def play_sound(frequency, duration):
    pass
    
def play_pause(duration):
    pass
    
def wait_music():
    pass    

def music_queue_length():
    return 0
    
def beep():
    sys.stdout.write('\x07')

def stop_all_sound():
    pass
    
