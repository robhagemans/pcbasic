#
# PC-BASIC 3.23 - events.py
#
# User-defined event handling 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import config
import state

def prepare():
    """ Initialise on_event module. """
    global num_fn_keys
    # function keys: F1-F12 for tandy, F1-F10 for gwbasic and pcjr
    if config.options['pcjr_syntax'] == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10
    reset_events()    

class EventHandler(object):
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def command(self, command_char):
        if command_char == '\x95': 
            # ON
            self.enabled = True
            self.stopped = False
        elif command_char == '\xDD': 
            # OFF
            self.enabled = False
        elif command_char == '\x90': 
            # STOP
            self.stopped = True
        else:
            return False
        return True
        

def reset_events():
    # TIMER
    state.basic_state.timer_period, state.basic_state.timer_start = 0, 0
    state.basic_state.timer_handler = EventHandler()
    # KEY
    state.basic_state.event_keys = [''] * 20
    state.basic_state.event_keys[0:10] = [ 
        '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',     # F1-F5 
        '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44']     # F6-F10
    state.basic_state.event_keys[num_fn_keys:num_fn_keys+4] = [   
        '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50']                 # up, left, right, down
    if num_fn_keys == 12:
        state.basic_state.event_keys[10:12] = [ '\x00\x98', '\x00\x99' ]    # Tandy F11, F12
    # the remaining keys are user definable        
    state.basic_state.key_handlers = [ EventHandler() for _ in xrange(20) ]    
    # PLAY
    state.basic_state.play_last, state.basic_state.play_trig = [0, 0, 0], 1 
    state.basic_state.play_handler = EventHandler()        
    # COM
    state.basic_state.com_handlers = [ EventHandler(), EventHandler() ]        
    # PEN
    state.basic_state.pen_handler = EventHandler()        
    # STRIG
    state.basic_state.strig_handlers = [ EventHandler(), EventHandler(), EventHandler(), EventHandler() ]
    # all handlers in order of handling; TIMER first
    state.basic_state.all_handlers = [state.basic_state.timer_handler]  
    # key events are not handled FIFO but first 11-20 in that order, then 1-10.
    state.basic_state.all_handlers += [state.basic_state.key_handlers[num] for num in (range(10, 20) + range(10))]
    state.basic_state.all_handlers += (
                [state.basic_state.play_handler] + state.basic_state.com_handlers + 
                [state.basic_state.pen_handler] + state.basic_state.strig_handlers )
    state.basic_state.suspend_all_events = False
    
            
prepare()

