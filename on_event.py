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

import timedate
import flow
import state
import sound
import backend

class EventHandler(object):
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def handle(self):
        if (state.basic_state.run_mode and self.enabled and self.triggered 
                and not self.stopped and self.gosub != None and not state.basic_state.suspend_all_events):
            self.triggered = False
            # stop event while handling it
            self.stopped = True 
            # execute 'ON ... GOSUB' subroutine; attach self to allow un-stopping event on RETURN
            flow.jump_gosub(self.gosub, self)

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
    state.basic_state.event_keys = [ 
        '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',     # F1-F5 
        '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44',     # F6-F10
        '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50',                 # up, left, right, down
        '', '', '', '', '', '' ]                                        # user definable
    state.basic_state.key_handlers = [ EventHandler() for _ in xrange(20) ]    
    # PLAY
    state.basic_state.play_last, state.basic_state.play_trig = 0, 1 
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
    
reset_events()    
    
def wait():
    backend.idle()
    check_events()
        
def check_events():
    # check backend events
    backend.check_events()
    if state.basic_state.run_mode:
        check_timer_event()
        check_play_event()
        check_com_events()
        # KEY, PEN and STRIG are triggered elsewhere
        # handle all events
        for handler in state.basic_state.all_handlers:
            handler.handle()

def check_timer_event():
    mutimer = timedate.timer_milliseconds() 
    if mutimer >= state.basic_state.timer_start + state.basic_state.timer_period:
        state.basic_state.timer_start = mutimer
        state.basic_state.timer_handler.triggered = True

def check_play_event():
    play_now = [sound.music_queue_length(voice) for voice in range(3)]
    if state.basic_state.machine in ('tandy', 'pcjr'):
        for voice in range(3):
            if ( play_now[voice] <= state.basic_state.play_trig and play_now[voice] > 0 and 
                    play_now[voice] != state.basic_state.play_last[voice] ):
                state.basic_state.play_handler.triggered = True 
    else:    
        if state.basic_state.play_last[0] >= state.basic_state.play_trig and play_now[0] < state.basic_state.play_trig:    
            state.basic_state.play_handler.triggered = True     
    state.basic_state.play_last = play_now

def check_com_events():
    ports = (state.io_state.devices['COM1:'], state.io_state.devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports[comport].peek_char():
            state.basic_state.com_handlers[comport].triggered = True
            
