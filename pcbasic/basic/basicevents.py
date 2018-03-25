"""
PC-BASIC - basicevents.py
Handlers for BASIC events

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from contextlib import contextmanager

from .base import scancode
from .base import error
from .base import tokens as tk
from .base import signals
from . import values


###############################################################################
# BASIC events

class BasicEvents(object):
    """Manage BASIC events."""

    def __init__(self, values, sound, clock, files, screen, program, syntax):
        """Initialise event triggers."""
        self._values = values
        self._sound = sound
        self._clock = clock
        # files for com1 and com2
        self._files = files
        # for on_event_gosub_
        self._program = program
        # events start unactivated
        self.active = False
        # 12 definable function keys for Tandy, 10 otherwise
        if syntax == 'tandy':
            self.num_fn_keys = 12
        else:
            self.num_fn_keys = 10
        # tandy and pcjr have multi-voice sound
        self.multivoice = syntax in ('pcjr', 'tandy')
        self.reset()

    def reset(self):
        """Reset event triggers."""
        # KEY: init key events
        keys = [
            scancode.F1, scancode.F2, scancode.F3, scancode.F4, scancode.F5,
            scancode.F6, scancode.F7, scancode.F8, scancode.F9, scancode.F10]
        if self.num_fn_keys == 12:
            # Tandy only
            keys += [scancode.F11, scancode.F12]
        keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
        keys += [None] * (20 - self.num_fn_keys - 4)
        self.key = [KeyHandler(sc) for sc in keys]
        # other events
        self.timer = TimerHandler(self._clock)
        self.play = PlayHandler(self._sound, self.multivoice)
        self.com = [
            ComHandler(self._files.get_device('COM1:')),
            ComHandler(self._files.get_device('COM2:'))]
        self.pen = PenHandler()
        # joy*2 + button
        self.strig = [StrigHandler(joy, button)
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

    def command(self, handler, command_char):
        """Turn the event ON, OFF and STOP."""
        if command_char == tk.ON:
            self.enabled.add(handler)
            handler.stopped = False
        elif command_char == tk.OFF:
            # we seem to need to keep ComHandler around to make serial events work correctly
            # i.e. apparently they can be triggered when switched off - I don't understand why
            if not isinstance(handler, ComHandler):
                self.enabled.discard(handler)
        elif command_char == tk.STOP:
            handler.stopped = True
        else:
            return False
        return True


    ##########################################################################
    # callbacks

    def pen_(self, args):
        """PEN: switch on/off light pen event handling."""
        command, = args
        self.command(self.pen, command)

    def strig_(self, args):
        """STRIG: switch on/off fire button event handling."""
        num = values.to_int(next(args))
        command, = args
        error.range_check(0, 255, num)
        if num in (0, 2, 4, 6):
            self.command(self.strig[num//2], command)

    def com_(self, args):
        """COM: switch on/off serial port event handling."""
        num = values.to_int(next(args))
        command, = args
        error.range_check(0, 2, num)
        if num > 0:
            self.command(self.com[num-1], command)

    def timer_(self, args):
        """TIMER: switch on/off timer event handling."""
        command, = args
        self.command(self.timer, command)

    def key_(self, args):
        """KEY: switch on/off keyboard events."""
        num = values.to_int(next(args))
        error.range_check(0, 255, num)
        command, = args
        # others are ignored
        if num >= 1 and num <= 20:
            self.command(self.key[num-1], command)

    def play_(self, args):
        """PLAY: switch on/off sound queue event handling."""
        command, = args
        self.command(self.play, command)

    def on_event_gosub_(self, args):
        """ON KEY: define key event trapping."""
        token = next(args)
        num = next(args)
        jumpnum = next(args)
        if jumpnum == 0:
            jumpnum = None
        elif jumpnum not in self._program.line_numbers:
            raise error.BASICError(error.UNDEFINED_LINE_NUMBER)
        list(args)
        if token == tk.KEY:
            keynum = values.to_int(num)
            error.range_check(1, 20, keynum)
            self.key[keynum-1].set_jump(jumpnum)
        elif token == tk.TIMER:
            timeval = values.to_single(num).to_value()
            error.throw_if(timeval <= 0)
            period = round(timeval * 1000.)
            self.timer.set_trigger(period)
            self.timer.set_jump(jumpnum)
        elif token == tk.PLAY:
            playval = values.to_int(num)
            error.range_check(1, 32, playval)
            self.play.set_trigger(playval)
            self.play.set_jump(jumpnum)
        elif token == tk.PEN:
            self.pen.set_jump(jumpnum)
        elif token == tk.STRIG:
            strigval = values.to_int(num)
            ## 0 -> [0][0] 2 -> [0][1]  4-> [1][0]  6 -> [1][1]
            if strigval not in (0,2,4,6):
                raise error.BASICError(error.IFC)
            self.strig[strigval//2].set_jump(jumpnum)
        elif token == tk.COM:
            comnum = values.to_int(num)
            error.range_check(1, 2, comnum)
            self.com[comnum-1].set_jump(jumpnum)



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

    def check_input(self, signal):
        """Stub for event checker."""
        return False


class PlayHandler(EventHandler):
    """Manage PLAY (music queue) events."""

    def __init__(self, sound, multivoice):
        """Initialise PLAY trigger."""
        EventHandler.__init__(self)
        self.last = [0, 0, 0]
        self.trig = 1
        self.multivoice = multivoice
        self.sound = sound

    def check_input(self, signal):
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
        return False

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
        self.start = self.clock.get_time_ms()
        self.period = n

    def check_input(self, signal):
        """Trigger TIMER events."""
        mutimer = self.clock.get_time_ms()
        if mutimer >= self.start + self.period:
            self.start = mutimer
            self.trigger()
        return False


class ComHandler(EventHandler):
    """Manage COM-port events."""

    def __init__(self, com_device):
        """Initialise COM trigger."""
        EventHandler.__init__(self)
        self.device = com_device

    # treat com-port "trigger" as real-time check

    @property
    def triggered(self):
        return self.device.char_waiting()

    @triggered.setter
    def triggered(self, value):
        pass


class KeyHandler(EventHandler):
    """Manage KEY events."""

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
    _mod_flags = {
        scancode.CAPSLOCK: 0x40, scancode.NUMLOCK: 0x20,
        scancode.ALT: 0x8, scancode.CTRL: 0x4,
        # both shifts are equal for event purposes
        scancode.LSHIFT: 0x3, scancode.RSHIFT: 0x3,
    }

    def __init__(self, scancode=None):
        """Initialise KEY trigger."""
        EventHandler.__init__(self)
        self._modcode = None
        self._scancode = scancode
        self._predefined = (scancode is not None)

    def check_input(self, signal):
        """Trigger KEY events."""
        if (self._scancode is not None) and (signal.event_type == signals.KEYB_DOWN):
            _, scancode, modifiers = signal.params
            if scancode != self._scancode:
                return False
            modcode = 0
            if modifiers and not self._predefined:
                for m in modifiers:
                    modcode |= self._mod_flags.get(m, 0)
            if self._predefined or self._modcode == modcode:
                # trigger event
                self.trigger()
                # drop key from key buffer
                # True removes signal from further processing
                return True
        return False

    def set_trigger(self, keystr):
        """Set KEY trigger to chr(modcode)+chr(scancode)."""
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self._predefined:
            # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
            self._modcode = ord(keystr[0]) & 0x6f
            self._scancode = ord(keystr[1])
            # all shifts are equal
            if self._modcode & 3:
                self._modcode |= 3


class PenHandler(EventHandler):
    """Manage PEN events."""

    def __init__(self):
        """Initialise STRIG trigger."""
        EventHandler.__init__(self)

    def check_input(self, signal):
        """Trigger PEN events."""
        if signal.event_type == signals.PEN_DOWN:
            self.trigger()
        # don't swallow event
        return False


class StrigHandler(EventHandler):
    """Manage STRIG events."""

    def __init__(self, joy, button):
        """Initialise STRIG trigger."""
        EventHandler.__init__(self)
        self._joybutton = joy, button

    def check_input(self, signal):
        """Trigger STRIG events."""
        if (signal.event_type == signals.STICK_DOWN) and (signal.params == self._joybutton):
            self.trigger()
