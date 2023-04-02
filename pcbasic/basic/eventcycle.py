"""
PC-BASIC - eventcycle.py
Event queue handling

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time

from ..compat import queue

from .base import error
from .base import scancode
from .base import signals
from .base.eascii import as_bytes as ea
from .base.eascii import as_unicode as uea


# F12 emulator home-key
# also f12+b -> ctrl+break
HOME_KEY_REPLACEMENTS_SCANCODE = {
    scancode.LEFT: (scancode.KP4, u'4'),
    scancode.RIGHT: (scancode.KP6, u'6'),
    scancode.UP: (scancode.KP8, u'8'),
    scancode.DOWN: (scancode.KP2, u'2'),
    # catch numbers by scancode, not eACSII
    # becasue the eASCII for Alt+number is different and that
    # will break inserting Alt+keypad numbers as Alt+F12+numbers
    scancode.N0: (scancode.KP0, u'0'),
    scancode.N1: (scancode.KP1, u'1'),
    scancode.N2: (scancode.KP2, u'2'),
    scancode.N3: (scancode.KP3, u'3'),
    scancode.N4: (scancode.KP4, u'4'),
    scancode.N5: (scancode.KP5, u'5'),
    scancode.N6: (scancode.KP6, u'6'),
    scancode.N7: (scancode.KP7, u'7'),
    scancode.N8: (scancode.KP8, u'8'),
    scancode.N9: (scancode.KP9, u'9'),
}

HOME_KEY_REPLACEMENTS_EASCII = {
    u'+': (scancode.KPPLUS, u'+'),
    u'-': (scancode.KPMINUS, u'-'),
    u'P': (scancode.BREAK, u''),
    u'N': (scancode.NUMLOCK, u''),
    u'S': (scancode.SCROLLOCK, u''),
    u'C': (scancode.CAPSLOCK, u''),
    u'H': (scancode.PRINT, u''),
    # ctrl+H
    u'\x08': (scancode.PRINT, uea.CTRL_PRINT),
}


###############################################################################
# queues

class NullQueue(object):
    """Dummy implementation of Queue interface."""
    def __init__(self, maxsize=0):
        pass
    def qsize(self):
        return 0
    def empty(self):
        return True
    def full(self):
        return False
    def put(self, item, block=False, timeout=False):
        pass
    def put_nowait(self, item):
        pass
    def get(self, block=False, timeout=False):
        # we're ignoring block
        raise queue.Empty
    def task_done(self):
        pass
    def join(self):
        pass


class EventQueues(object):
    """Manage interface queues."""

    tick = 0.006
    max_video_qsize = 200
    #max_audio_qsize = 20

    def __init__(self, ctrl_c_is_break, inputs=None, video=None, audio=None):
        """Initialise; default is NullQueues."""
        # input signal handlers
        self._handlers = []
        # basic event handlers
        self._basic_handlers = ()
        # pause-key halts everything until another keypress
        self._pause = False
        # treat ctrl+c as break interrupt
        self._ctrl_c_is_break = ctrl_c_is_break
        # F12 replacement events
        self._f12_active = False
        self.set(inputs, video, audio)

    def set(self, inputs=None, video=None, audio=None):
        """Set; default is NullQueues."""
        self.inputs = inputs or NullQueue()
        self.video = video or NullQueue()
        self.audio = audio or NullQueue()

    def __getstate__(self):
        """Don't pickle queues."""
        pickle_dict = self.__dict__.copy()
        pickle_dict['inputs'] = None
        pickle_dict['video'] = None
        pickle_dict['audio'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Set to null queues on unpickling."""
        self.__dict__.update(pickle_dict)
        self.set()

    def add_handler(self, handler):
        """Add an input handler."""
        self._handlers.append(handler)

    def set_basic_event_handlers(self, event_check_input):
        """Set the handlers for BASIC events."""
        self._basic_handlers = tuple(event_check_input)

    def wait(self):
        """Wait and check events."""
        time.sleep(self.tick)
        self.check_events()

    def check_events(self):
        """Main event cycle."""
        # sleep(0) is needed for responsiveness, e.g. event trapping in programs with tight loops
        # i.e. 100 goto 100 with event traps active) - needed to allow the input queue to fill
        # this also allows the screen to update between statements
        # it does slow the interpreter down by about 20% in FOR loops
        # note that we always have an input queue, either for the interface of for iostreams
        time.sleep(0)
        # bizarrely, we need sleep(0) twice. I don't know why.
        # note that multiple sleep(0) calls doen't seem to cause more slowdown than just one.
        time.sleep(0)
        time.sleep(0)
        # what I think is happening here is that the sdl2 interface thread,
        # in its loop to process a single queue item, calls C library functions
        # which do not need the GIL. so it releases it. this allows the engine thread to pick up
        # and produce more work for the interface thread. sleep(0) does not wait but it does release
        # the GIL back, so we need a few sleep(0) calls to allow the interface to get through
        # individual items.
        # this would not be a problem if the interface thread did not need the GIL at all
        # (perhaps with numba, nuitka, cython, pypy or jython)
        # but note that the video queue is a Python object so may require the GIL
        # or if it held the GIL for a full cycle
        # wait to for the queue to drain if it excceds a threshold value
        # this allows the interface to catch up with video updates
        if self.video.qsize() > self.max_video_qsize:
            while self.video.qsize():
                time.sleep(self.tick)
        self._check_input()

    def _check_input(self):
        """Handle input events."""
        while True:
            # pop input queues
            try:
                signal = self.inputs.get(False)
            except queue.Empty:
                if self._pause:
                    time.sleep(self.tick)
                    continue
                else:
                    # we still need to handle basic events: not all are inputs
                    for e in self._basic_handlers:
                        e.check_input(signals.Event(None))
                    break
            self.inputs.task_done()
            # effect replacements
            self._replace_inputs(signal)
            # handle input events
            for handle_input in (
                    [self._handle_non_trappable_interrupts] +
                    [e.check_input for e in self._basic_handlers] +
                    [self._handle_trappable_interrupts] +
                    [e.check_input for e in self._handlers]
                ):
                if handle_input(signal):
                    break

    def _handle_non_trappable_interrupts(self, signal):
        """Handle non-trappable interrupts (before BASIC events)."""
        # process input events
        if signal.event_type == signals.QUIT:
            raise error.Exit()
        # exit pause mode on keyboard hit; swallow key
        elif signal.event_type in (signals.KEYB_DOWN, signals.STREAM_CHAR, signals.CLIP_PASTE):
            if self._pause:
                self._pause = False
                return True
        return False

    def _handle_trappable_interrupts(self, signal):
        """Handle trappable interrupts (after BASIC events)."""
        # handle special key combinations
        if signal.event_type == signals.KEYB_DOWN:
            c, scan, mod = signal.params
            if (scan == scancode.DELETE and scancode.CTRL in mod and scancode.ALT in mod):
                # ctrl-alt-del: if not captured by the OS, reset the emulator
                # meaning exit and delete state. This is useful on android.
                raise error.Reset()
            elif scan in (scancode.BREAK, scancode.SCROLLOCK) and scancode.CTRL in mod:
                raise error.Break()
            # pause key handling
            # to ensure this key remains trappable
            elif (scan == scancode.BREAK or
                    (scan == scancode.NUMLOCK and scancode.CTRL in mod)):
                self._pause = True
                return True
        return False

    def _replace_inputs(self, signal):
        """Input event replacements."""
        if signal.event_type == signals.KEYB_DOWN:
            c, scan, mod = signal.params
            if (self._ctrl_c_is_break and c == uea.CTRL_c):
                # replace ctrl+c with ctrl+break if option is enabled
                signal.params = u'', scancode.BREAK, [scancode.CTRL]
            elif scan == scancode.F12:
                # F12 emulator "home key"
                self._f12_active = True
                signal.event_type = None
            elif self._f12_active:
                # F12 replacements
                if c.upper() == u'B':
                    # f12+b -> ctrl+break
                    signal.params = u'', scancode.BREAK, [scancode.CTRL]
                else:
                    scan, c = HOME_KEY_REPLACEMENTS_SCANCODE.get(scan, (scan, c))
                    scan, c = HOME_KEY_REPLACEMENTS_EASCII.get(c.upper(), (scan, c))
                    signal.params = c, scan, mod
        elif (signal.event_type == signals.KEYB_UP) and (signal.params[0] == scancode.F12):
            self._f12_active = False
