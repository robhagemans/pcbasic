"""
PC-BASIC - video_ansi.py
Console text interface

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

from .video import VideoPlugin
from .base import video_plugins
from . import video_cli
from ..compat import console, zip
from ..compat import iter_chunks


# CGA colours: black, cyan, magenta, white
COLOURS_4 = (0, 3, 5, 7) * 4
# Mono colours: black, white
COLOURS_2 = (0, 7) * 8


@video_plugins.register('ansi')
class VideoANSI(video_cli.VideoTextBase):
    """Text interface."""

    def __init__(self, input_queue, video_queue, caption=u'', border_width=0, **kwargs):
        """Initialise the text interface."""
        video_cli.VideoTextBase.__init__(self, input_queue, video_queue)
        # don't quit on EOF - it's counterintuitive for the text interface
        self._input_handler.quit_on_eof = False
        # window caption
        self._caption = caption
        # cursor is visible
        self._cursor_visible = True
        # cursor is block-shaped (vs line-shaped)
        self._block_cursor = False
        # current cursor position
        self._cursor_row, self._cursor_col = 1, 1
        # last used colour attributes
        self._last_attributes = None
        self._cursor_attr = None
        # text and colour buffer
        self._height, self._width = 25, 80
        self._border_y = int(round((self._height * border_width)/200.))
        self._border_x = int(round((self._width * border_width)/200.))
        self._border_attr = 0
        self.default_colours = range(16)
        self._attributes = []

    def __enter__(self):
        """Open ANSI interface."""
        video_cli.VideoTextBase.__enter__(self)
        # go into alternate screen buffer
        # stderr continues on the primary buffer
        console.start_screen()
        self.set_caption_message(u'')
        console.set_attributes(0, 0, False, False)

    def __exit__(self, type, value, traceback):
        """Close ANSI interface."""
        try:
            console.close_screen()
        finally:
            video_cli.VideoTextBase.__exit__(self, type, value, traceback)

    def _work(self):
        """Handle screen and interface events."""

    def _redraw_border(self):
        """Redraw the border."""
        if not self._border_x and not self._border_y:
            return
        self._set_attributes(0, self._border_attr, False, False)
        # draw top
        for row in range(self._border_y):
            console.move_cursor_to(row+1, 1)
            console.clear_row(self._width + 2 * self._border_x)
        # draw sides
        for row in range(self._height):
            console.move_cursor_to(row+1 + self._border_y, 1)
            console.write(u' ' * self._border_x)
            console.move_cursor_to(row+1 + self._border_y, self._width + self._border_x + 1)
            console.write(u' ' * self._border_x)
        # draw bottom
        for row in range(self._border_y):
            console.move_cursor_to(row+1 + self._border_y + self._height, 1)
            console.clear_row(self._width + 2 * self._border_x)
        console.move_cursor_to(
            self._cursor_row + self._border_y, self._cursor_col + self._border_x
        )

    def _set_default_colours(self, num_attr):
        """Set colours for default palette."""
        if num_attr == 2:
            self.default_colours = COLOURS_2
        elif num_attr == 4:
            self.default_colours = COLOURS_4
        else:
            self.default_colours = range(16)

    def _set_attributes(self, fore, back, blink, underline):
        """Set ANSI colours based on split attribute."""
        if self._last_attributes == (fore, back, blink, underline):
            return
        self._last_attributes = fore, back, blink, underline
        console.set_attributes(
            self.default_colours[fore%16], self.default_colours[back%16], blink, underline
        )

    def set_border_attr(self, attr):
        """Change border attribute."""
        if attr != self._border_attr:
            self._border_attr = attr
            self._redraw_border()

    def set_palette(self, attributes, dummy_pack_pixels):
        """Set the colour palette."""
        self._set_default_colours(len(attributes))
        rgb_table = [_fore for _fore, _, _, _ in attributes[:16]]
        if len(attributes) > 16:
            # *assume* the first 16 attributes are foreground-on-black
            # this is the usual textmode byte attribute arrangement
            fore = list(range(16)) * 16
            back = tuple(_b for _b in range(8) for _ in range(16)) * 2
        else:
            fore = list(range(len(attributes)))
            # assume black background
            # blink dim-to-bright etc won't work on terminals anyway
            back = (0,) * len(attributes)
        blink = tuple(_blink for _, _, _blink, _ in attributes)
        under = tuple(_under for _, _, _, _under in attributes)
        int_attributes = list(zip(fore, back, blink, under))
        self._attributes = int_attributes
        for index, rgb in enumerate(rgb_table):
            console.set_palette_entry(index, *rgb)

    def set_mode(self, canvas_height, canvas_width, text_height, text_width):
        """Change screen mode."""
        self._height = text_height
        self._width = text_width
        console.set_attributes(0, 0, False, False)
        console.resize(self._height + 2*self._border_y, self._width + 2*self._border_x)
        console.clear()
        self._redraw_border()
        return True

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        self._set_attributes(7, back_attr, False, False)
        for row in range(start, stop+1):
            console.move_cursor_to(row + self._border_y, 1 + self._border_x)
            console.clear_row(self._width + 2 * self._border_x)
        # draw border
        self._set_attributes(
            0, self.default_colours[self._border_attr%16], False, False
        )
        for row in range(start, stop+1):
            console.move_cursor_to(row + self._border_y, 1)
            console.write(u' ' * self._border_x)
            console.move_cursor_to(row + self._border_y, 1 + self._width + self._border_x)
            console.write(u' ' * self._border_x)
        console.move_cursor_to(
            self._cursor_row + self._border_y, self._cursor_col + self._border_x
        )

    def move_cursor(self, row, col, attr, width):
        """Move the cursor to a new position."""
        if (row, col) != (self._cursor_row, self._cursor_col):
            self._cursor_row, self._cursor_col = row, col
            console.move_cursor_to(
                self._cursor_row + self._border_y, self._cursor_col + self._border_x
            )
        # change attribute of cursor
        # cursor width is controlled by terminal
        if attr != self._cursor_attr:
            self._cursor_attr = attr
            console.set_cursor_colour(self.default_colours[attr%16])

    def show_cursor(self, cursor_on, cursor_blinks):
        """Change visibility of cursor."""
        self._cursor_visible = cursor_on
        if cursor_on:
            console.show_cursor(block=self._block_cursor)
        else:
            # force move when made visible again
            console.hide_cursor()

    def set_cursor_shape(self, from_line, to_line):
        """Set the cursor shape."""
        self._block_cursor = (to_line-from_line) >= 4
        if self._cursor_visible:
            console.show_cursor(block=self._block_cursor)

    def update(self, row, col, unicode_matrix, attr_matrix, y0, x0, sprite):
        """Put text or pixels at a given position."""
        start_col = col
        curs_row, curs_col = self._cursor_row, self._cursor_col
        for text, attrs in zip(unicode_matrix, attr_matrix):
            console.move_cursor_to(row + self._border_y, col + self._border_x)
            for unicode_list, attr in iter_chunks(text, attrs):
                fore, back, blink, underline = self._attributes[attr]
                self._set_attributes(fore, back, blink, underline)
                console.write(u''.join(unicode_list).replace(u'\0', u' '))
                col += len(unicode_list)
            row += 1
            col = start_col
        console.move_cursor_to(self._cursor_row + self._border_y, self._cursor_col + self._border_x)

    def scroll(self, direction, from_line, scroll_height, back_attr):
        """Scroll the screen between from_line and scroll_height."""
        # set the default background
        # as some (not all) consoles use the background color when inserting/deleting
        # and if they can't resize this leads to glitches outside the window
        self._set_attributes(7, 0, False, False)
        if direction == -1:
            self._scroll_up(from_line, scroll_height, back_attr)
        else:
            self._scroll_down(from_line, scroll_height, back_attr)

    def _scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        console.scroll(from_line + self._border_y, scroll_height + self._border_y, rows=-1)
        self.clear_rows(back_attr, scroll_height, scroll_height)

    def _scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        console.scroll(from_line + self._border_y, scroll_height + self._border_y, rows=1)
        self.clear_rows(back_attr, from_line, from_line)

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        if msg:
            console.set_caption(self._caption + u' - ' + msg)
        else:
            console.set_caption(self._caption)
