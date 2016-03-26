"""
PC-BASIC - backend.py
Event loop

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time
import Queue

import config
import state
import error
import clipboard

video_queue = Queue.Queue()
input_queue = Queue.Queue()
# audio queues
message_queue = Queue.Queue()
tone_queue = None
# clipboard handler, to be overridden by input backend
clipboard_handler = clipboard.Clipboard()

class PersistentQueue(Queue.Queue):
    """ Simple picklable Queue. """

    def __getstate__(self):
        """ Get pickling dict for queue. """
        qlist = []
        while True:
            try:
                qlist.append(self.get(False))
                self.task_done()
            except Queue.Empty:
                break
        return { 'qlist': qlist }

    def __setstate__(self, st):
        """ Initialise queue from pickling dict. """
        self.__init__()
        qlist = st['qlist']
        for item in qlist:
            self.put(item)


class Event(object):
    """ Signal object for video queue. """

    def __init__(self, event_type, params=None):
        """ Create signal. """
        self.event_type = event_type
        self.params = params


# audio queue signals
AUDIO_TONE = 0
AUDIO_STOP = 1
AUDIO_NOISE = 2
AUDIO_QUIT = 4
AUDIO_PERSIST = 6

# video queue signals
# save state and quit
VIDEO_QUIT = 0
# change video mode
VIDEO_SET_MODE = 1
# switch page
VIDEO_SET_PAGE = 2
# set cursor shape
VIDEO_SET_CURSOR_SHAPE = 3
# move cursor
VIDEO_MOVE_CURSOR = 5
# set cursor attribute
VIDEO_SET_CURSOR_ATTR = 6
# set border attribute
VIDEO_SET_BORDER_ATTR = 7
# put character glyph
VIDEO_PUT_GLYPH = 8
# clear rows
VIDEO_CLEAR_ROWS = 10
# scroll
VIDEO_SCROLL_UP = 11
VIDEO_SCROLL_DOWN = 12
# set colorburst
VIDEO_SET_COLORBURST = 13
# show/hide cursor
VIDEO_SHOW_CURSOR = 14
# set palette
VIDEO_SET_PALETTE = 15
# build glyphs
VIDEO_BUILD_GLYPHS = 16
# put pixel
VIDEO_PUT_PIXEL = 17
# put interval
VIDEO_PUT_INTERVAL = 18
VIDEO_FILL_INTERVAL = 19
# put rect
VIDEO_PUT_RECT = 20
VIDEO_FILL_RECT = 21
# copy page
VIDEO_COPY_PAGE = 28
# set caption message
VIDEO_SET_CAPTION = 29

# input queue signals
# special keys
KEYB_QUIT = 0
# insert character
KEYB_CHAR = 4
# insert keydown
KEYB_DOWN = 5
# insert keyup
KEYB_UP = 6
# light pen events
PEN_DOWN = 101
PEN_UP = 102
PEN_MOVED = 103
# joystick events
STICK_DOWN = 201
STICK_UP = 202
STICK_MOVED = 203
# clipboard events
CLIP_COPY = 254
CLIP_PASTE = 255




###############################################################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global tone_queue
    # persist tone queue
    state.console_state.tone_queue = [PersistentQueue(), PersistentQueue(),
                                      PersistentQueue(), PersistentQueue() ]
    # kludge: link tone queue to global which is accessed from elsewhere
    # NOTE that we shouldn't assign to either of these queues after this point
    tone_queue = state.console_state.tone_queue


###############################################################################
# main event checker

tick_s = 0.0006
longtick_s = 0.024 - tick_s

icon = None
initial_mode = None

def wait(suppress_events=False):
    """ Wait and check events. """
    time.sleep(longtick_s)
    if not suppress_events:
        check_events()

def check_events():
    """ Main event cycle. """
    time.sleep(tick_s)
    check_input()
    if state.basic_state.run_mode:
        for e in state.basic_state.events.all:
            e.check()
    state.console_state.keyb.drain_event_buffer()

def check_input():
    """ Handle input events. """
    while True:
        try:
            signal = input_queue.get(False)
        except Queue.Empty:
            if not state.console_state.keyb.pause:
                break
            else:
                time.sleep(tick_s)
                continue
        # we're on it
        input_queue.task_done()
        if signal.event_type == KEYB_QUIT:
            raise error.Exit()
        elif signal.event_type == KEYB_CHAR:
            # params is a unicode sequence
            state.console_state.keyb.insert_chars(*signal.params)
        elif signal.event_type == KEYB_DOWN:
            # params is e-ASCII/unicode character sequence, scancode, modifier
            state.console_state.keyb.key_down(*signal.params)
        elif signal.event_type == KEYB_UP:
            state.console_state.keyb.key_up(*signal.params)
        elif signal.event_type == PEN_DOWN:
            state.console_state.pen.down(*signal.params)
        elif signal.event_type == PEN_UP:
            state.console_state.pen.up()
        elif signal.event_type == PEN_MOVED:
            state.console_state.pen.moved(*signal.params)
        elif signal.event_type == STICK_DOWN:
            state.console_state.stick.down(*signal.params)
        elif signal.event_type == STICK_UP:
            state.console_state.stick.up(*signal.params)
        elif signal.event_type == STICK_MOVED:
            state.console_state.stick.moved(*signal.params)
        elif signal.event_type == CLIP_PASTE:
            text = clipboard_handler.paste(*signal.params)
            state.console_state.keyb.insert_chars(text, check_full=False)
        elif signal.event_type == CLIP_COPY:
            text = state.console_state.screen.get_text(*(signal.params[:4]))
            clipboard_handler.copy(text, signal.params[-1])


###############################################################################

prepare()
