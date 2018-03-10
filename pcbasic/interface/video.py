"""
PC-BASIC - interface.video
Base class for video plugins

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import Queue
import time

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
            signals.VIDEO_PUT_GLYPH: self.put_glyph,
            signals.VIDEO_CLEAR_ROWS: self.clear_rows,
            signals.VIDEO_SCROLL_UP: self.scroll_up,
            signals.VIDEO_SCROLL_DOWN: self.scroll_down,
            signals.VIDEO_SET_PALETTE: self.set_palette,
            signals.VIDEO_SET_CURSOR_SHAPE: self.set_cursor_shape,
            signals.VIDEO_SET_CURSOR_ATTR: self.set_cursor_attr,
            signals.VIDEO_SHOW_CURSOR: self.show_cursor,
            signals.VIDEO_MOVE_CURSOR: self.move_cursor,
            signals.VIDEO_SET_PAGE: self.set_page,
            signals.VIDEO_COPY_PAGE: self.copy_page,
            signals.VIDEO_SET_BORDER_ATTR: self.set_border_attr,
            signals.VIDEO_SET_COMPOSITE: self.set_composite,
            signals.VIDEO_BUILD_GLYPHS: self.build_glyphs,
            signals.VIDEO_PUT_PIXEL: self.put_pixel,
            signals.VIDEO_PUT_INTERVAL: self.put_interval,
            signals.VIDEO_FILL_INTERVAL: self.fill_interval,
            signals.VIDEO_PUT_RECT: self.put_rect,
            signals.VIDEO_FILL_RECT: self.fill_rect,
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
            except Queue.Empty:
                return True
            # putting task_done before the execution avoids hanging on join() after an exception
            self._video_queue.task_done()
            if signal.event_type == signals.VIDEO_QUIT:
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

    def set_mode(self, mode_info):
        """Initialise a given text or graphics mode."""

    def set_caption_message(self, msg):
        """Add a message to the window caption."""

    def set_clipboard_text(self, text, mouse):
        """Put text on the clipboard."""

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """Build the palette."""

    def set_border_attr(self, attr):
        """Change the border attribute."""

    def set_composite(self, on, composite_colors):
        """Enable/disable composite artifacts."""

    def clear_rows(self, back_attr, start, stop):
        """Clear a range of screen rows."""

    def set_page(self, vpage, apage):
        """Set the visible and active page."""

    def copy_page(self, src, dst):
        """Copy source to destination page."""

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""

    def put_glyph(self, pagenum, row, col, char, is_fullwidth, fore, back, blink, underline):
        """Put a character at a given position."""

    def build_glyphs(self, new_dict):
        """Build a dict of glyphs for use in text mode."""

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Build a sprite for the cursor."""

    def put_pixel(self, pagenum, x, y, index):
        """Put a pixel on the screen; callback to empty character buffer."""

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""

    def fill_interval(self, pagenum, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""

    def put_interval(self, pagenum, x, y, colours):
        """Write a list of attributes to a scanline interval."""

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """Apply numpy array [y][x] of attribytes to an area."""
