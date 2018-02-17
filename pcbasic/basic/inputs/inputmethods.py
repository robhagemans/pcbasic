"""
PC-BASIC - inputmethods.py
Keyboard, pen and joystick handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime

from ..base import error
from ..base import scancode
from ..base import tokens as tk
from ..base import signals
from .. import values


###############################################################################
# clipboard copy & print screen handler

# clipboard copy & print screen are special cases:
# they to handle an input signal, read the screen
# and write the text to an output queue or file
# independently of what BASIC is doing

class ScreenCopyHandler(object):
    """Event handler for clipboard copy and print screen."""

    def __init__(self, screen, lpt1_file):
        """Initialise copy handler."""
        self._screen = screen
        self._lpt1_file = lpt1_file

    def check_input(self, signal):
        """Handle input signals."""
        if signal.event_type == signals.CLIP_COPY:
            self._screen.copy_clipboard(*signal.params)
            return True
        elif signal.event_type == signals.KEYB_DOWN:
            c, scan, mod = signal.params
            if scan == scancode.PRINT and (
                    scancode.LSHIFT in mod or scancode.RSHIFT in mod):
                # shift+printscreen triggers a print screen
                self._screen.print_screen(self._lpt1_file)
                return True
        return False


###############################################################################
# light pen

class Pen(object):
    """Light pen support."""

    def __init__(self):
        """Initialise light pen."""
        self._is_down = False
        self._pos = 0, 0
        # signal pen has been down for PEN polls in pen_()
        self._was_down = False
        self._down_pos = (0, 0)

    def check_input(self, signal):
        """Handle pen-related input signals."""
        if signal.event_type == signals.PEN_DOWN:
            self._down(*signal.params)
        elif signal.event_type == signals.PEN_UP:
            self._up()
        elif signal.event_type == signals.PEN_MOVED:
            self._moved(*signal.params)
        else:
            return False
        return True

    def _down(self, x, y):
        """Report a pen-down event at graphical x,y """
        # TRUE until polled
        self._was_down = True
        # TRUE until pen up
        self._is_down = True
        self._down_pos = x, y

    def _up(self):
        """Report a pen-up event at graphical x,y """
        self._is_down = False

    def _moved(self, x, y):
        """Report a pen-move event at graphical x,y """
        self._pos = x, y

    def poll(self, fn, enabled, screen):
        """PEN: poll the light pen."""
        fn = values.to_int(fn)
        error.range_check(0, 9, fn)
        posx, posy = self._pos
        if fn == 0:
            pen_down_old, self._was_down = self._was_down, False
            pen = -1 if pen_down_old else 0
        elif fn == 1:
            pen = self._down_pos[0]
        elif fn == 2:
            pen = self._down_pos[1]
        elif fn == 3:
            pen = -1 if self._is_down else 0
        elif fn == 4:
            pen = posx
        elif fn == 5:
            pen = posy
        elif fn == 6:
            pen = 1 + self._down_pos[1] // screen.mode.font_height
        elif fn == 7:
            pen = 1 + self._down_pos[0] // screen.mode.font_width
        elif fn == 8:
            pen = 1 + posy // screen.mode.font_height
        elif fn == 9:
            pen = 1 + posx // screen.mode.font_width
        if not enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return pen


###############################################################################
# joysticks


class Stick(object):
    """Joystick support."""

    def __init__(self, values):
        """Initialise joysticks."""
        self._values = values
        self.is_firing = [[False, False], [False, False]]
        # axis 0--255; 128 is mid but reports 0, not 128 if no joysticks present
        self.axis = [[0, 0], [0, 0]]
        self.is_on = False
        self._was_fired = [[False, False], [False, False]]
        # timer for reading game port
        self._out_time = self._decay_timer()

    def check_input(self, signal):
        """Handle joystick-related input signals."""
        if signal.event_type == signals.STICK_DOWN:
            self._down(*signal.params)
        elif signal.event_type == signals.STICK_UP:
            self._up(*signal.params)
        elif signal.event_type == signals.STICK_MOVED:
            self._moved(*signal.params)
        else:
            return False
        return True

    def _down(self, joy, button):
        """Report a joystick button down event."""
        try:
            self._was_fired[joy][button] = True
            self.is_firing[joy][button] = True
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def _up(self, joy, button):
        """Report a joystick button up event."""
        try:
            self.is_firing[joy][button] = False
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def _moved(self, joy, axis, value):
        """Report a joystick axis move."""
        try:
            self.axis[joy][axis] = value
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def strig_statement_(self, args):
        """Switch joystick handling on or off."""
        on, = args
        self.is_on = (on == tk.ON)

    def stick_(self, args):
        """STICK: poll the joystick axes."""
        fn, = args
        fn = values.to_int(fn)
        error.range_check(0, 3, fn)
        joy, axis = fn // 2, fn % 2
        try:
            result = self.axis[joy][axis]
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            result = 0
        return self._values.new_integer().from_int(result)

    def strig_(self, args):
        """STRIG: poll the joystick fire button."""
        fn, = args
        fn = values.to_int(fn)
        error.range_check(0, 7, fn)
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        joy, trig = fn // 4, (fn//2) % 2
        if fn % 2 == 0:
            # has been fired
            stick_was_trig = self._was_fired[joy][trig]
            self._was_fired[joy][trig] = False
            result = -1 if stick_was_trig else 0
        else:
            # is currently firing
            result = -1 if self.is_firing[joy][trig] else 0
        return self._values.new_integer().from_int(result)

    def decay(self):
        """Return time since last game port reset."""
        return (self._decay_timer() - self._out_time) % 86400000

    def reset_decay(self):
        """Reset game port."""
        self._out_time = self._decay_timer()

    def _decay_timer(self):
        """Millisecond timer for game port decay."""
        now = datetime.datetime.now()
        return now.second*1000 + now.microsecond/1000
