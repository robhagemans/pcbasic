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
import state 
import sound

#############################
# core event handler    

def check_events():
    # check console events
    state.video.check_events()   
    # check&handle user events
    on_event.check_events()
    # manage sound queue
    sound.check_sound()

def idle():
    state.video.idle()
