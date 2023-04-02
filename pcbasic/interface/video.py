"""
PC-BASIC - interface.video
Base class for video plugins

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time

from ..compat import queue
from ..basic.base import signals


class VideoPlugin(object):
    """Base class for display/input interface plugins."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Setup the interface."""
        self.alive = True
        self.busy = False
        self._input_queue = input_queue
        self._video_queue = video_queue
        self._handlers = {
            signals.VIDEO_SET_MODE: self.set_mode,
            signals.VIDEO_UPDATE: self.update,
            signals.VIDEO_CLEAR_ROWS: self.clear_rows,
            signals.VIDEO_SCROLL: self.scroll,
            signals.VIDEO_SET_PALETTE: self.set_palette,
            signals.VIDEO_SET_CURSOR_SHAPE: self.set_cursor_shape,
            signals.VIDEO_SHOW_CURSOR: self.show_cursor,
            signals.VIDEO_MOVE_CURSOR: self.move_cursor,
            signals.VIDEO_SET_BORDER_ATTR: self.set_border_attr,
            signals.VIDEO_SET_CAPTION: self.set_caption_message,
            signals.VIDEO_SET_CLIPBOARD_TEXT: self.set_clipboard_text,
        }

    # called by Interface

    def cycle(self):
        """Video/input event cycle."""
        if self.alive:
            self._drain_queue()
        if self.alive:
            self._work()
            self._check_input()

    def sleep(self, ms):
        """Sleep a tick"""
        time.sleep(ms/1000.)

    # private methods

    def _drain_queue(self):
        """Drain signal queue."""
        while True:
            try:
                signal = self._video_queue.get(False)
            except queue.Empty:
                return True
            # putting task_done before the execution avoids hanging on join() after an exception
            self._video_queue.task_done()
            if signal.event_type == signals.QUIT:
                # close thread
                self.alive = False
            else:
                try:
                    self._handlers[signal.event_type](*signal.params)
                except KeyError:
                    pass

    # plugin overrides

    def __exit__(self, type, value, traceback):
        """Close the interface."""

    def __enter__(self):
        """Final initialisation."""
        return self

    def _work(self):
        """Display update cycle."""

    def _check_input(self):
        """Input devices update cycle."""

    # signal handlers

    def set_mode(self, canvas_height, canvas_width, text_height, text_width):
        """Initialise a given text or graphics mode."""

    def set_caption_message(self, msg):
        """Add a message to the window caption."""

    def set_clipboard_text(self, text):
        """Put text on the clipboard."""

    def set_palette(self, attributes, pack_pixels):
        """Build the palette."""

    def set_border_attr(self, attr):
        """Change the border attribute."""

    def clear_rows(self, back_attr, start_row, stop_row):
        """Clear a range of screen rows."""

    def show_cursor(self, cursor_on, cursor_blinks):
        """Change visibility of cursor."""

    def move_cursor(self, row, col, attr, width):
        """Move the cursor to a new position and set attribute and width."""

    def scroll(self, direction, start_row, stop_row, back_attr):
        """Scroll the screen between start_row and stop_row. direction 1 is down, -1 up."""

    def set_cursor_shape(self, from_line, to_line):
        """Build a sprite for the cursor."""

    def update(self, row, col, unicode_matrix, attr_matrix, y0, x0, sprite):
        """Put text or pixels at a given position."""
