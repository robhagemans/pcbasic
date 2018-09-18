"""
PC-BASIC - video_ansi.py
Text interface implementation for Unix

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import logging

from .video import VideoPlugin
from .base import video_plugins
from . import video_cli
from ..compat import console


# CGA colours: black, cyan, magenta, white
COLOURS_4 = (0, 3, 5, 7) * 4
# Mono colours: black, white
COLOURS_2 = (0, 7) * 8


@video_plugins.register('ansi')
class VideoANSI(video_cli.VideoTextBase):
    """Text interface implemented with ANSI escape sequences."""

    def __init__(self, input_queue, video_queue, caption=u'', border_width=0, **kwargs):
        """Initialise the text interface."""
        video_cli.VideoTextBase.__init__(self, input_queue, video_queue)
        self.caption = caption
        self.set_caption_message(u'')
        # cursor is visible
        self.cursor_visible = True
        # cursor is block-shaped (vs line-shaped)
        self._block_cursor = False
        # current cursor position
        self.cursor_row = 1
        self.cursor_col = 1
        # last used colour attributes
        self.last_attributes = None
        # text and colour buffer
        self.num_pages = 1
        self.vpagenum, self.apagenum = 0, 0
        self.height = 25
        self.width = 80
        self._border_y = int(round((self.height * border_width)/200.))
        self._border_x = int(round((self.width * border_width)/200.))
        self._border_attr = 0
        self._set_default_colours(16)
        self.text = [[[(u' ', (7, 0, False, False))]*80 for _ in range(25)]]
        self.logger = logging.getLogger()

    def __enter__(self):
        """Open ANSI interface."""
        video_cli.VideoTextBase.__enter__(self)
        # prevent logger from defacing the screen
        if logging.getLogger().handlers[0].stream.name == sys.stderr.name:
            self.logger.disabled = True

    def __exit__(self, type, value, traceback):
        """Close ANSI interface."""
        try:
            console.reset()
            console.clear()
            # re-enable logger
            self.logger.disabled = False
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
            console.clear_row()
        # draw sides
        for row, textrow in enumerate(self.text[self.vpagenum]):
            console.move_cursor_to(row+1 + self._border_y, 1)
            console.write(u' ' * self._border_x)
            console.move_cursor_right(self.width)
            console.write(u' ' * self._border_x)
        # draw bottom
        for row in range(self._border_y):
            console.move_cursor_to(row+1 + self._border_y + self.height, 1)
            console.clear_row()
        console.move_cursor_to(
            self.cursor_row + self._border_y, self.cursor_col + self._border_x
        )

    def _redraw(self):
        """Redraw the screen."""
        console.clear()
        self._redraw_border()
        # redraw screen
        for row, textrow in enumerate(self.text[self.vpagenum]):
            console.move_cursor_to(row+1 + self._border_y, 1 + self._border_x)
            for col, charattr in enumerate(textrow):
                self._set_attributes(*charattr[1])
                console.write(charattr[0])
        console.move_cursor_to(
            self.cursor_row + self._border_y, self.cursor_col + self._border_x
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
        if self.last_attributes == (fore, back, blink, underline):
            return
        self.last_attributes = fore, back, blink, underline
        console.set_attributes(
            self.default_colours[fore%16], self.default_colours[back%16], blink, underline
        )

    def set_border_attr(self, attr):
        """Change border attribute."""
        if attr != self._border_attr:
            self._border_attr = attr
            self._redraw_border()

    def set_palette(self, new_palette, new_palette1):
        """Set the colour palette."""
        for attr, rgb in enumerate(new_palette):
            console.set_palette_entry(attr, *rgb)

    def set_mode(self, mode_info):
        """Change screen mode."""
        self.height = mode_info.height
        self.width = mode_info.width
        self.num_pages = mode_info.num_pages
        self.text = [
            [[(u' ', (7, 0, False, False))] * self.width for _ in range(self.height)]
            for _ in range(self.num_pages)
        ]
        self._set_default_colours(len(mode_info.palette))
        console.resize(self.height + 2*self._border_y, self.width + 2*self._border_x)
        self._redraw()
        return True

    def set_page(self, new_vpagenum, new_apagenum):
        """Set visible and active page."""
        if (self.vpagenum, self.apagenum) == (new_vpagenum, new_apagenum):
            return
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw()

    def copy_page(self, src, dst):
        """Copy screen pages."""
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw()

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        self.text[self.apagenum][start-1:stop] = [
            [(u' ', (7, 0, False, False))] * len(self.text[self.apagenum][0])
            for _ in range(start-1, stop)
        ]
        if self.vpagenum == self.apagenum:
            self._set_attributes(7, back_attr, False, False)
            for row in range(start, stop+1):
                console.move_cursor_to(row + self._border_y, 1 + self._border_x)
                console.clear_row()
            # draw border
            self._set_attributes(
                0, self.default_colours[self._border_attr%16], False, False
            )
            for row in range(start, stop+1):
                console.move_cursor_to(row + self._border_y, 1)
                console.write(u' ' * self._border_x)
                console.move_cursor_to(row + self._border_y, 1 + self.width + self._border_x)
                console.write(u' ' * self._border_x)
            console.move_cursor_to(
                self.cursor_row + self._border_y, self.cursor_col + self._border_x
            )

    def move_cursor(self, row, col):
        """Move the cursor to a new position."""
        if (row, col) != (self.cursor_row, self.cursor_col):
            self.cursor_row, self.cursor_col = row, col
            console.move_cursor_to(
                self.cursor_row + self._border_y, self.cursor_col + self._border_x
            )

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        console.set_cursor_colour(self.default_colours[attr%16])

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        if cursor_on:
            console.show_cursor(block=self._block_cursor)
        else:
            # force move when made visible again
            console.hide_cursor()

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Set the cursor shape."""
        self._block_cursor = (to_line-from_line) >= 4
        if self.cursor_visible:
            console.show_cursor(block=self._block_cursor)

    def put_glyph(self, pagenum, row, col, char, is_fullwidth, fore, back, blink, underline):
        """Put a character at a given position."""
        if char == u'\0':
            char = u' '
        self.text[pagenum][row-1][col-1] = char, (fore, back, blink, underline)
        if is_fullwidth:
            self.text[pagenum][row-1][col] = u'', (fore, back, blink, underline)
        if self.vpagenum != pagenum:
            return
        if (row, col) != (self.cursor_row, self.cursor_col):
            console.move_cursor_to(row + self._border_y, col + self._border_x)
        self._set_attributes(fore, back, blink, underline)
        console.write(char)
        if is_fullwidth:
            console.write(u' ')
        self.cursor_row, self.cursor_col = row, col+1

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
            self.text[self.apagenum][from_line:scroll_height] +
            [[(u' ', 0)] * len(self.text[self.apagenum][0])]
        )
        if self.apagenum != self.vpagenum:
            return
        console.scroll_up(from_line + self._border_y, scroll_height + self._border_y)
        self.clear_rows(back_attr, scroll_height, scroll_height)

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
            [[(u' ', 0)] * len(self.text[self.apagenum][0])] +
            self.text[self.apagenum][from_line-1:scroll_height-1]
        )
        if self.apagenum != self.vpagenum:
            return
        console.scroll_down(from_line + self._border_y, scroll_height + self._border_y)
        self.clear_rows(back_attr, from_line, from_line)

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        if msg:
            console.set_caption(self.caption + u' - ' + msg)
        else:
            console.set_caption(self.caption)
