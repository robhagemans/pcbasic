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

import oslayer
import deviceio
import console
import program
import vartypes
import state

class EventHandler(object):
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def handle(self):
        if state.basic_state.run_mode and self.enabled and self.triggered and not self.stopped and self.gosub != None and not suspend_all_events:
            self.triggered = False
            # stop event while handling it
            self.stopped = True 
            # execute 'ON ... GOSUB' subroutine; attach self to allow un-stopping event on RETURN
            program.jump_gosub(self.gosub, self)

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
    global event_keys, key_handlers, timer_handler, timer_period, timer_start 
    global com_handlers, play_handler, play_last, play_trig
    global pen_handler, strig_handlers
    global all_handlers
    global suspend_all_events
    # TIMER
    timer_period, timer_start = 0, 0
    timer_handler = EventHandler()
    # KEY
    event_keys = [ 
        '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',     # F1-F5 
        '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44',     # F6-F10
        '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50',                 # up, left, right, down
        '', '', '', '', '', '' ]                                        # user definable
    key_handlers = [ EventHandler() for _ in xrange(20) ]    
    # PLAY
    play_last, play_trig = 0, 1 
    play_handler = EventHandler()        
    # COM
    com_handlers = [ EventHandler(), EventHandler() ]        
    # PEN
    pen_handler = EventHandler()        
    # STRIG
    strig_handlers = [ EventHandler(), EventHandler(), EventHandler(), EventHandler() ]
    # all handlers in order of handling; TIMER first
    all_handlers = [timer_handler]  
    # key events are not handled FIFO but first 11-20 in that order, then 1-10.
    all_handlers += [key_handlers[num] for num in (range(10, 20) + range(10))]
    all_handlers += [play_handler] + com_handlers + [pen_handler] + strig_handlers
    suspend_all_events = False
reset_events()    
    
def check_events():
    if state.basic_state.run_mode:
        check_timer_event()
        check_key_events()
        check_play_event()
        check_com_events()
        # PEN and STRIG are triggered elsewhere
        # handle all events
        for handler in all_handlers:
            handler.handle()

def check_timer_event():
    global timer_start
    mutimer = oslayer.timer_milliseconds() 
    if mutimer >= timer_start + timer_period:
        timer_start = mutimer
        timer_handler.triggered = True

def check_key_events():
    c = console.peek_char()
    if len(c) > 0:
        try:
            keynum = event_keys.index(c)
        except ValueError:
            return
        if keynum > -1 and keynum < 20:
            if key_handlers[keynum].enabled:
                # remove the char from buffer
                console.pass_char(c)
                # trigger only once at most
                key_handlers[keynum].triggered = True

def check_play_event():
    global play_stopped, play_last
    play_now = console.sound.music_queue_length()
    if play_last >= play_trig and play_now < play_trig:    
        play_handler.triggered = True     
    play_last = play_now

def check_com_events():
    ports = (deviceio.devices['COM1:'], deviceio.devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports.comport.peek_char():
            com_handlers[comport].triggered = True
            
