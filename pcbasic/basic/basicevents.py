"""
PC-BASIC - basicevents.py
Handlers for BASIC events

(c) 2013--2023 Rob Hagemans
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

    def __init__(self, sound, clock, files, program, num_fn_keys, tandy_fn_keys):
        """Initialise event triggers."""
        self._sound = sound
        self._clock = clock
        # files for com1 and com2
        self._files = files
        # for on_event_gosub_
        self._program = program
        # 10 or 12 definable function keys
        self._num_fn_keys = num_fn_keys
        # key codes are shifted by 2 on Tandy
        self._tandy_fn_keys = tandy_fn_keys
        self.reset()

    def reset(self):
        """Reset event triggers."""
        # KEY: init key events
        keys = [
            scancode.F1, scancode.F2, scancode.F3, scancode.F4, scancode.F5,
            scancode.F6, scancode.F7, scancode.F8, scancode.F9, scancode.F10]
        # on late IBM BASICA and BASICJ versions:
        # * KEY 30 and KEY 31 refer to F11 and F12, as in QBASIC
        # * there are 10 definable functions 15-25
        # on classic GW-BASIC:
        # * F11 and F12 are not accessible
        # * the definable range is 15-20
        # on Tandy:
        # * F11 and F12 are accessible trough keys 11 and 12,
        # * the arrow keys codes are shifted by 2
        # * the definable range is 17-20
        if self._tandy_fn_keys:
            # Tandy only
            keys += [scancode.F11, scancode.F12]
            keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
            keys += [None] * 4
        elif self._num_fn_keys == 12:
            # keys 11-14
            keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
            # keys 15-25
            keys += [None] * 11
            # keys 26-29 - these should not be accessible but are
            keys += [None] * 4
            # non-Tandy F11 and F12 mapped to 30, 31
            keys += [scancode.F11, scancode.F12]
        else:
            keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
            keys += [None] * 6
        self.key = [KeyHandler(sc) for sc in keys]
        # other events
        self.timer = TimerHandler(self._clock)
        self.play = PlayHandler(self._sound)
        self.com = [
            ComHandler(self._files.get_device(b'COM1:')),
            ComHandler(self._files.get_device(b'COM2:'))]
        self.pen = PenHandler()
        # joy*2 + button
        self.strig = [
            StrigHandler(joy, button)
            for joy in range(2) for button in range(2)
        ]
        # key events are not handled FIFO but first arrow keys and definable keys, then function keys
        if self._tandy_fn_keys:
            ordered_keys = self.key[12:] + self.key[:12]
        elif self._num_fn_keys == 12:
            ordered_keys = self.key[10:29] + self.key[:10] + self.key[29:]
        else:
            ordered_keys = self.key[10:] + self.key[:10]
        # all handlers in order of handling; TIMER first
        self.all = [self.timer] + ordered_keys + [self.play] + self.com + [self.pen] + self.strig
        # keep a list of enabled events
        self.enabled = set()
        # set suspension off
        self.suspend_all = False

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
        """ON .. GOSUB: define event trapping subroutine."""
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
            error.range_check(1, len(self.key), keynum)
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

    def __init__(self, sound):
        """Initialise PLAY trigger."""
        EventHandler.__init__(self)
        self.trig = 1
        self._sound = sound
        # set to a number higher than the maximum buffer length?
        self.last = 0 #34 if multivoice else 0

    def check_input(self, signal):
        """Check and trigger PLAY (music queue) events."""
        play_now = self._sound.tones_waiting()
        if self._sound.multivoice:
            if (self.last > play_now and play_now < self.trig):
                self.trigger()
        else:
            if (self.last >= self.trig and play_now < self.trig):
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
    #
    # "extended keys" are the additional keys brought in with the 101-key Type M keyboard
    # for example the arrow keys, ins, del, home, end, pgp, pgdn on the *non-numerical* keyboard
    #
    # for predefined keys, modifier is ignored

    # modifier flags, merging left-shift and right-shift and excluding the "extended" flag
    # we cannot reliably detect whether a key supplied by the interface is "extended".
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
        # only length-2 expressions can be assigned as scancode triggers
        if len(keystr) != 2:
            raise error.BASICError(error.IFC)
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self._predefined:
            # some modifier codes are different from the ones used internally & seen in peek(1047):
            #
            # value | on key   | peek (1047)
            # ------|----------|------------
            # 0x80  | Extended | Insert
            # 0x10  | not used | Scroll Lock
            #
            # exclude 0x10 and 0x80 from the modifier mask
            # this means we're ignoring the "extended" flag
            self._modcode = bytearray(keystr)[0] & 0x6f
            self._scancode = bytearray(keystr)[1]
            # per the docs, &h02 is left-shift and &h01 is right-shift
            # in reality, all shifts are equal
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
