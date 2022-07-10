"""
PC-BASIC - inputs.pen
Light pen handling

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import signals
from .. import values


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

    def poll(self, fn, enabled, video_buffer):
        """PEN: poll the light pen."""
        fn = values.to_int(fn)
        error.range_check(0, 9, fn)
        if not enabled:
            # should return 0 or char pos 1 if PEN not ON
            return 1 if fn >= 6 else 0
        if fn == 0:
            pen_down_old, self._was_down = self._was_down, False
            return -1 if pen_down_old else 0
        elif fn == 1:
            return self._down_pos[0]
        elif fn == 2:
            return self._down_pos[1]
        elif fn == 3:
            return -1 if self._is_down else 0
        elif fn == 4:
            return self._pos[0]
        elif fn == 5:
            return self._pos[1]
        elif fn == 6:
            row, _ = video_buffer.pixel_to_text_pos(*self._down_pos)
            return row
        elif fn == 7:
            _, col = video_buffer.pixel_to_text_pos(*self._down_pos)
            return col
        elif fn == 8:
            row, _ = video_buffer.pixel_to_text_pos(*self._pos)
            return row
        elif fn == 9:
            _, col = video_buffer.pixel_to_text_pos(*self._pos)
            return col
