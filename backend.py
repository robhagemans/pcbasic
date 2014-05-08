#
# PC-BASIC 3.23 - backend.py
#
# Backend modules and events
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# backend implementations
video = None
sound = None 
penstick = None 

def check_events():
    # check console events
    video.check_events()   
    # manage sound queue
    sound.check_sound()

def idle():
    video.idle()

def wait():
    video.idle()
    check_events()    

