#
# PC-BASIC 3.23 - event_loop.py
#
# Core event handler
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import on_event
import sound
import state
import backend

#############################
# core event handler    

def check_events():
    # check console events
    backend.video.check_events()   
    # manage sound queue
    backend.sound.check_sound()
    # check&handle user events
    on_event.check_events()

def idle():
    backend.video.idle()
    
def wait():
    idle()
    check_events()
        
