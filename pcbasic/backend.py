"""
PC-BASIC - backend.py
Event loop

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import time
import Queue

import plat
import config
import state
import timedate
import scancode
import error


video_queue = Queue.Queue()
input_queue = Queue.Queue()
# audio queues
message_queue = Queue.Queue()
tone_queue = None


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
# break event (an alternative to Ctrl+Break keydown events)
KEYB_BREAK = 1
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
CLIP_PASTE = 255


# 12 definable function keys for Tandy
num_fn_keys = 10


###############################################################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global pcjr_sound
    # we need this for KEY event
    global num_fn_keys
    if config.get('syntax') == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10
    # we need this for PLAY event
    if config.get('syntax') in ('pcjr', 'tandy'):
        pcjr_sound = config.get('syntax')
    else:
        pcjr_sound = None
    global tone_queue
    # persist tone queue
    state.console_state.tone_queue = [PersistentQueue(), PersistentQueue(),
                                      PersistentQueue(), PersistentQueue() ]
    # kludge: link tone queue to global
    # NOTE that we shouldn't assign to either of these queues after this point
    tone_queue = state.console_state.tone_queue
    # set up events
    state.basic_state.events = Events()


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
        elif signal.event_type == KEYB_BREAK:
            raise error.Break()
        elif signal.event_type == KEYB_CHAR:
            state.console_state.keyb.insert_chars(signal.params, check_full=True)
        elif signal.event_type == KEYB_DOWN:
            scan, eascii = signal.params
            state.console_state.keyb.key_down(scan, eascii, check_full=True)
        elif signal.event_type == KEYB_UP:
            state.console_state.keyb.key_up(signal.params)
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
            state.console_state.keyb.insert_chars(signal.params, check_full=False)


###############################################################################
# BASIC event triggers

class EventHandler(object):
    """ Manage event triggers. """

    def __init__(self):
        """ Initialise untriggered and disabled. """
        self.reset()

    def reset(self):
        """ Reset to untriggered and disabled initial state. """
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def set_jump(self, jump):
        """ Set the jump line number. """
        self.gosub = jump

    def command(self, command_char):
        """ Turn the event ON, OFF and STOP. """
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

    def trigger(self):
        """ Trigger the event. """
        self.triggered = True

    def check(self):
        """ Stub for event checker. """


class PlayHandler(EventHandler):
    """ Manage PLAY (music queue) events. """

    def __init__(self):
        """ Initialise PLAY trigger. """
        EventHandler.__init__(self)
        self.last = [0, 0, 0]
        self.trig = 1

    def check(self):
        """ Check and trigger PLAY (music queue) events. """
        play_now = [state.console_state.sound.queue_length(voice) for voice in range(3)]
        if pcjr_sound:
            for voice in range(3):
                if (play_now[voice] <= self.trig and
                        play_now[voice] > 0 and
                        play_now[voice] != self.last[voice]):
                    self.trigger()
        else:
            if (self.last[0] >= self.trig and
                    play_now[0] < self.trig):
                self.trigger()
        self.last = play_now

    def set_trigger(self, n):
        """ Set PLAY trigger to n notes. """
        self.trig = n


class TimerHandler(EventHandler):
    """ Manage TIMER events. """

    def __init__(self):
        """ Initialise TIMER trigger. """
        EventHandler.__init__(self)
        self.period = 0
        self.start = 0

    def set_trigger(self, n):
        """ Set TIMER trigger to n milliseconds. """
        self.period = n

    def check(self):
        """ Trigger TIMER events. """
        mutimer = timedate.timer_milliseconds()
        if mutimer >= self.start + self.period:
            self.start = mutimer
            self.trigger()


class ComHandler(EventHandler):
    """ Manage COM-port events. """

    def __init__(self, port):
        """ Initialise COM trigger. """
        EventHandler.__init__(self)
        # devices aren't initialised at this time so just keep the name
        self.portname = ('COM1:', 'COM2:')[port]

    def check(self):
        """ Trigger COM-port events. """
        if (state.io_state.devices[self.portname] and
                    state.io_state.devices[self.portname].char_waiting()):
            self.trigger()


class KeyHandler(EventHandler):
    """ Manage KEY events. """

    def __init__(self, scancode=None):
        """ Initialise KEY trigger. """
        EventHandler.__init__(self)
        self.modcode = None
        self.scancode = scancode
        self.predefined = (scancode is not None)

    def check(self):
        """ Trigger KEY events. """
        if self.scancode is None:
            return False
        scancode, modifiers = state.console_state.keyb.buf.poll_event(self.scancode)
        if scancode != self.scancode:
            return False
        # build KEY trigger code
        # see http://www.petesqbsite.com/sections/tutorials/tuts/keysdet.txt
        # second byte is scan code; first byte
        #  0       if the key is pressed alone
        #  1 to 3    if any Shift and the key are combined
        #    4       if Ctrl and the key are combined
        #    8       if Alt and the key are combined
        #   32       if NumLock is activated
        #   64       if CapsLock is activated
        #  128       if we are defining some extended key
        # extended keys are for example the arrow keys on the non-numerical keyboard
        # presumably all the keys in the middle region of a standard PC keyboard?
        #
        # for predefined keys, modifier is ignored
        # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
        if (self.predefined) or (modifiers is None or self.modcode == modifiers & 0x6f):
            # trigger event
            self.trigger()
            # drop key from key buffer
            if self.enabled:
                state.console_state.keyb.buf.drop_any(scancode, modifiers)
                return True
        return False

    def set_trigger(self, keystr):
        """ Set KEY trigger to chr(modcode)+chr(scancode). """
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self.predefined:
            self.modcode = ord(keystr[0])
            self.scancode = ord(keystr[1])
        # poll scancode to clear it from keypress dict
        # where it might liger if this scancode has not tbeen polled before
        state.console_state.keyb.buf.poll_event(self.scancode)


class PenHandler(EventHandler):
    """ Manage PEN events. """

    def check(self):
        """ Trigger PEN events. """
        if state.console_state.pen.poll_event():
            self.trigger()


class StrigHandler(EventHandler):
    """ Manage STRIG events. """

    def __init__(self, joy, button):
        """ Initialise STRIG trigger. """
        EventHandler.__init__(self)
        self.joy = joy
        self.button = button

    def check(self):
        """ Trigger STRIG events. """
        if state.console_state.stick.poll_event(self.joy, self.button):
            self.trigger()


class Events(object):
    """ Event management. """

    def __init__(self):
        """ Initialise event triggers. """
        self.reset()

    def reset(self):
        """ Initialise or reset event triggers. """
        # KEY: init key events
        keys = [
            scancode.F1, scancode.F2, scancode.F3, scancode.F4, scancode.F5,
            scancode.F6, scancode.F7, scancode.F8, scancode.F9, scancode.F10]
        if num_fn_keys == 12:
            # Tandy only
            keys += [scancode.F11, scancode.F12]
        keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
        keys += [None] * (20 - num_fn_keys - 4)
        self.key = [KeyHandler(sc) for sc in keys]
        # other events
        self.timer = TimerHandler()
        self.play = PlayHandler()
        self.com = [ComHandler(0), ComHandler(1)]
        self.pen = PenHandler()
        # joy*2 + button
        self.strig = [StrigHandler(joy, button)
                      for joy in range(2) for button in range(2)]
        # all handlers in order of handling; TIMER first
        # key events are not handled FIFO but first 11-20 in that order, then 1-10
        self.all = ([self.timer]
            + [self.key[num] for num in (range(10, 20) + range(10))]
            + [self.play] + self.com + [self.pen] + self.strig)
        # set suspension off
        self.suspend_all = False


###############################################################################

prepare()
