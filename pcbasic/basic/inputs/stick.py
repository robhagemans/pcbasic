"""
PC-BASIC - inputs.stick
Joystick handling

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime

from ..base import error
from ..base import tokens as tk
from ..base import signals
from .. import values


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
        # [stick][button]
        # 0,1 -> [stick 0][button 0] 2,3 -> [1][0]  4,5-> [0][1]  6,7 -> [1][1]
        joy, trig = (fn//2) % 2, fn // 4
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
        return now.second*1000 + now.microsecond//1000
