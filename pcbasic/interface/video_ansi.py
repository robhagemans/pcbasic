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
from . import ansi
from . import video_cli
from ..compat import console


COL = console.colours
# ANSI colour numbers for EGA colours: black, blue, green, cyan, red, magenta, yellow, white
COLOURS_8 = (
    COL.BLACK, COL.BLUE, COL.GREEN, COL.CYAN,
    COL.RED, COL.MAGENTA, COL.YELLOW, COL.WHITE
) * 2
# CGA colours: black, cyan, magenta, white
COLOURS_4 = (COL.BLACK, COL.CYAN, COL.MAGENTA, COL.WHITE) * 4
# Mono colours: black, white
COLOURS_2 = (COL.BLACK, COL.WHITE) * 8


@video_plugins.register('ansi')
class VideoANSI(video_cli.VideoTextBase):
    """Text interface implemented with ANSI escape sequences."""

    def __init__(self, input_queue, video_queue, caption=u'', **kwargs):
        """Initialise the text interface."""
        video_cli.VideoTextBase.__init__(self, input_queue, video_queue)
        self.caption = caption
        self.set_caption_message(u'')
        # cursor is visible
        self.cursor_visible = True
        # 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
        self.cursor_shape = 1
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
            console.reset_attributes()
            console.resize(*console.original_size)
            console.clear()
            #console.move_cursor_to(1, 1)
            self.show_cursor(True)
            # re-enable logger
            self.logger.disabled = False
        finally:
            video_cli.VideoTextBase.__exit__(self, type, value, traceback)

    def _work(self):
        """Handle screen and interface events."""

    def _redraw(self):
        """Redraw the screen."""
        console.clear()
        for row, textrow in enumerate(self.text[self.vpagenum]):
            console.move_cursor_to(row+1, 1)
            for col, charattr in enumerate(textrow):
                self._set_attributes(*charattr[1])
                console.write(charattr[0])
        console.move_cursor_to(self.cursor_row, self.cursor_col)

    def _set_default_colours(self, num_attr):
        """Set colours for default palette."""
        if num_attr == 2:
            self.default_colours = COLOURS_2
        elif num_attr == 4:
            self.default_colours = COLOURS_4
        else:
            self.default_colours = COLOURS_8

    def _set_attributes(self, fore, back, blink, underline):
        """Set ANSI colours based on split attribute."""
        if self.last_attributes == (fore, back, blink, underline):
            return
        self.last_attributes = fore, back, blink, underline
        bright, fore = divmod(fore, 8)
        console.set_attributes(
            self.default_colours[fore], self.default_colours[back], bright, blink, underline
        )

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
        console.resize(self.height, self.width)
        self._set_attributes(7, 0, False, False)
        console.clear()
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
            for r in range(start, stop+1):
                console.move_cursor_to(r, 1)
                console.clear_row()
            console.move_cursor_to(self.cursor_row, self.cursor_col)

    def move_cursor(self, row, col):
        """Move the cursor to a new position."""
        if (row, col) != (self.cursor_row, self.cursor_col):
            self.cursor_row, self.cursor_col = row, col
            console.move_cursor_to(self.cursor_row, self.cursor_col)

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        #console.write(ansi.SET_CURSOR_COLOUR % ansi.COLOUR_NAMES[attr%16])

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        if cursor_on:
            console.show_cursor()
            #console.write(ansi.SET_CURSOR_SHAPE % cursor_shape)
        else:
            # force move when made visible again
            console.hide_cursor()

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Set the cursor shape."""
        if (to_line-from_line) >= 4:
            self.cursor_shape = 1
        else:
            self.cursor_shape = 3
        # 1 blinking block 2 block 3 blinking line 4 line
        if self.cursor_visible:
            pass
            #console.write(ansi.SET_CURSOR_SHAPE % cursor_shape)

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
            console.move_cursor_to(row, col)
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
        console.scroll_up(from_line, scroll_height)
        self.clear_rows(back_attr, scroll_height, scroll_height)

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
            [[(u' ', 0)] * len(self.text[self.apagenum][0])] +
            self.text[self.apagenum][from_line-1:scroll_height-1]
        )
        if self.apagenum != self.vpagenum:
            return
        console.scroll_down(from_line, scroll_height)
        self.clear_rows(back_attr, from_line, from_line)

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        if msg:
            console.set_caption(self.caption + u' - ' + msg)
        else:
            console.set_caption(self.caption)
