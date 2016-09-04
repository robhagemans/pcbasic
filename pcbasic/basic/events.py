"""
PC-BASIC - events.py
Input event loop and handlers for BASIC events

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from contextlib import contextmanager
import time
import Queue

from . import scancode
from . import signals
from . import error
from . import tokens as tk


class Events(object):
    """Event management."""

    def __init__(self, session, syntax):
        """Initialise event triggers."""
        self.session = session
        # events start unactivated
        self.active = False
        # 12 definable function keys for Tandy, 10 otherwise
        if syntax == 'tandy':
            self.num_fn_keys = 12
        else:
            self.num_fn_keys = 10
        # tandy and pcjr have multi-voice sound
        self.multivoice = syntax in ('pcjr', 'tandy')

    def reset(self):
        """Initialise or reset event triggers."""
        # KEY: init key events
        keys = [
            scancode.F1, scancode.F2, scancode.F3, scancode.F4, scancode.F5,
            scancode.F6, scancode.F7, scancode.F8, scancode.F9, scancode.F10]
        if self.num_fn_keys == 12:
            # Tandy only
            keys += [scancode.F11, scancode.F12]
        keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
        keys += [None] * (20 - self.num_fn_keys - 4)
        self.key = [KeyHandler(self.session.keyboard, sc) for sc in keys]
        # other events
        self.timer = TimerHandler(self.session.clock)
        self.play = PlayHandler(self.session.sound, self.multivoice)
        self.com = [
            ComHandler(self.session.devices.devices['COM1:']),
            ComHandler(self.session.devices.devices['COM2:'])]
        self.pen = PenHandler(self.session.pen)
        # joy*2 + button
        self.strig = [StrigHandler(self.session.stick, joy, button)
                      for joy in range(2) for button in range(2)]
        # all handlers in order of handling; TIMER first
        # key events are not handled FIFO but first 11-20 in that order, then 1-10
        self.all = ([self.timer]
            + [self.key[num] for num in (range(10, 20) + range(10))]
            + [self.play] + self.com + [self.pen] + self.strig)
        # keep a list of enabled events
        self.enabled = set()
        # set suspension off
        self.suspend_all = False

    def set_active(self, active):
        """Activate or deactivate event checking."""
        self.active = active

    @contextmanager
    def suspend(self):
        """Context guard to suspend events."""
        self.suspend_all, store = True, self.suspend_all
        yield
        self.suspend_all = store


    ##########################################################################
    # main event checker

    tick = 0.006

    def wait(self):
        """Wait and check events."""
        time.sleep(self.tick)
        self.check_events()

    def check_events(self):
        """Main event cycle."""
        # we need this for audio thread to keep up during tight loops
        # but how much does it slow us down otherwise?
        time.sleep(0)
        self._check_input()
        # events are only active if a program is running
        if self.active:
            for e in self.enabled:
                e.check()
        self.session.keyboard.drain_event_buffer()

    def command(self, handler, command_char):
        """Turn the event ON, OFF and STOP."""
        if command_char == tk.ON:
            self.enabled.add(handler)
            handler.stopped = False
        elif command_char == tk.OFF:
            self.enabled -= handler
        elif command_char == tk.STOP:
            handler.stopped = True
        else:
            return False
        return True

    def _check_input(self):
        """Handle input events."""
        while True:
            # pop input queues
            try:
                signal = self.session.input_queue.get(False)
            except Queue.Empty:
                if not self.session.keyboard.pause:
                    break
                else:
                    continue
            self.session.input_queue.task_done()
            # process input events
            if signal.event_type == signals.KEYB_QUIT:
                raise error.Exit()
            elif signal.event_type == signals.KEYB_CHAR:
                # params is a unicode sequence
                self.session.keyboard.insert_chars(*signal.params)
            elif signal.event_type == signals.KEYB_DOWN:
                # params is e-ASCII/unicode character sequence, scancode, modifier
                self.session.keyboard.key_down(*signal.params)
            elif signal.event_type == signals.KEYB_UP:
                self.session.keyboard.key_up(*signal.params)
            elif signal.event_type == signals.STREAM_CHAR:
                self.session.keyboard.insert_chars(*signal.params, check_full=False)
            elif signal.event_type == signals.STREAM_CLOSED:
                self.session.keyboard.close_input()
            elif signal.event_type == signals.PEN_DOWN:
                self.session.pen.down(*signal.params)
            elif signal.event_type == signals.PEN_UP:
                self.session.pen.up()
            elif signal.event_type == signals.PEN_MOVED:
                self.session.pen.moved(*signal.params)
            elif signal.event_type == signals.STICK_DOWN:
                self.session.stick.down(*signal.params)
            elif signal.event_type == signals.STICK_UP:
                self.session.stick.up(*signal.params)
            elif signal.event_type == signals.STICK_MOVED:
                self.session.stick.moved(*signal.params)
            elif signal.event_type == signals.CLIP_PASTE:
                self.session.keyboard.insert_chars(*signal.params, check_full=False)
            elif signal.event_type == signals.CLIP_COPY:
                text = self.session.screen.get_text(*(signal.params[:4]))
                self.session.video_queue.put(signals.Event(
                        signals.VIDEO_SET_CLIPBOARD_TEXT, (text, signal.params[-1])))


###############################################################################
# BASIC event triggers

class EventHandler(object):
    """Manage event triggers."""

    def __init__(self):
        """Initialise untriggered and disabled."""
        self.reset()

    def reset(self):
        """Reset to untriggered and disabled initial state."""
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def set_jump(self, jump):
        """Set the jump line number."""
        self.gosub = jump

    def trigger(self):
        """Trigger the event."""
        self.triggered = True

    def check(self):
        """Stub for event checker."""


class PlayHandler(EventHandler):
    """Manage PLAY (music queue) events."""

    def __init__(self, sound, multivoice):
        """Initialise PLAY trigger."""
        EventHandler.__init__(self)
        self.last = [0, 0, 0]
        self.trig = 1
        self.multivoice = multivoice
        self.sound = sound

    def check(self):
        """Check and trigger PLAY (music queue) events."""
        play_now = [self.sound.queue_length(voice) for voice in range(3)]
        if self.multivoice:
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
        """Set PLAY trigger to n notes."""
        self.trig = n


class TimerHandler(EventHandler):
    """Manage TIMER events."""

    def __init__(self, clock):
        """Initialise TIMER trigger."""
        EventHandler.__init__(self)
        self.period = 0
        self.start = 0
        self.clock = clock

    def set_trigger(self, n):
        """Set TIMER trigger to n milliseconds."""
        self.period = n

    def check(self):
        """Trigger TIMER events."""
        mutimer = self.clock.get_time_ms()
        if mutimer >= self.start + self.period:
            self.start = mutimer
            self.trigger()


class ComHandler(EventHandler):
    """Manage COM-port events."""

    def __init__(self, com_device):
        """Initialise COM trigger."""
        EventHandler.__init__(self)
        self.device = com_device

    def check(self):
        """Trigger COM-port events."""
        if (self.device and self.device.char_waiting()):
            self.trigger()


class KeyHandler(EventHandler):
    """Manage KEY events."""

    def __init__(self, keyboard, scancode=None):
        """Initialise KEY trigger."""
        EventHandler.__init__(self)
        self.modcode = None
        self.scancode = scancode
        self.predefined = (scancode is not None)
        self.keyboard = keyboard

    def check(self):
        """Trigger KEY events."""
        if self.scancode is None:
            return False
        for c, scancode, modifiers, check_full in self.keyboard.prebuf:
            if scancode != self.scancode:
                continue
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
                #if self.enabled:
                self.keyboard.prebuf.remove((c, scancode, modifiers, check_full))
                return True
        return False

    def set_trigger(self, keystr):
        """Set KEY trigger to chr(modcode)+chr(scancode)."""
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self.predefined:
            self.modcode = ord(keystr[0])
            self.scancode = ord(keystr[1])


class PenHandler(EventHandler):
    """Manage PEN events."""

    def __init__(self, pen):
        """Initialise STRIG trigger."""
        EventHandler.__init__(self)
        self.pen = pen

    def check(self):
        """Trigger PEN events."""
        if self.pen.poll_event():
            self.trigger()


class StrigHandler(EventHandler):
    """Manage STRIG events."""

    def __init__(self, stick, joy, button):
        """Initialise STRIG trigger."""
        EventHandler.__init__(self)
        self.joy = joy
        self.button = button
        self.stick = stick

    def check(self):
        """Trigger STRIG events."""
        if self.stick.poll_event(self.joy, self.button):
            self.trigger()
