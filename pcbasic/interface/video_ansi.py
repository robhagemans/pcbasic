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
from .video_cli import ENCODING
from . import ansi


@video_plugins.register('ansi')
class VideoANSI(video_cli.VideoCLI):
    """Text interface implemented with ANSI escape sequences."""

    def __init__(self, input_queue, video_queue, caption=u'', **kwargs):
        """Initialise the text interface."""
        self.caption = caption
        self.set_caption_message('')
        # cursor is visible
        self.cursor_visible = True
        # 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
        self.cursor_shape = 1
        # current cursor position
        self.cursor_row = 1
        self.cursor_col = 1
        # last used colour attributes
        self.last_attributes = None
        # last position
        self.last_pos = None
        # text and colour buffer
        self.num_pages = 1
        self.vpagenum, self.apagenum = 0, 0
        self.height = 25
        self.width = 80
        self._set_default_colours(16)
        video_cli.VideoCLI.__init__(self, input_queue, video_queue)
        self.text = [[[(u' ', (7, 0, False, False))]*80 for _ in range(25)]]
        # prevent logger from defacing the screen
        self.logger = logging.getLogger()
        if logging.getLogger().handlers[0].stream.name == sys.stderr.name:
            self.logger.disabled = True

    def __exit__(self, type, value, traceback):
        """Close the text interface."""
        VideoPlugin.__exit__(self, type, value, traceback)
        sys.stdout.write(ansi.SET_COLOUR % 0)
        sys.stdout.write(ansi.CLEAR_SCREEN)
        sys.stdout.write(ansi.MOVE_CURSOR % (1, 1))
        self.show_cursor(True)
        sys.stdout.flush()
        # re-enable logger
        self.logger.disabled = False
        self._term_echo()

    def _work(self):
        """Handle screen and interface events."""
        if self.cursor_visible and self.last_pos != (self.cursor_row, self.cursor_col):
            sys.stdout.write(ansi.MOVE_CURSOR % (self.cursor_row, self.cursor_col))
            sys.stdout.flush()
            self.last_pos = (self.cursor_row, self.cursor_col)

    def _redraw(self):
        """Redraw the screen."""
        sys.stdout.write(ansi.CLEAR_SCREEN)
        for row, textrow in enumerate(self.text[self.vpagenum]):
            sys.stdout.write(ansi.MOVE_CURSOR % (row+1, 1))
            for col, charattr in enumerate(textrow):
                self._set_attributes(*charattr[1])
                sys.stdout.write(charattr[0].encode(ENCODING, 'replace'))
        sys.stdout.write(ansi.MOVE_CURSOR % (self.cursor_row, self.cursor_col))
        sys.stdout.flush()

    def _set_default_colours(self, num_attr):
        """Set colours for default palette."""
        if num_attr == 2:
            self.default_colours = ansi.COLOURS_2
        elif num_attr == 4:
            self.default_colours = ansi.COLOURS_4
        else:
            self.default_colours = ansi.COLOURS_8

    def _set_attributes(self, fore, back, blink, underline):
        """Set ANSI colours based on split attribute."""
        if self.last_attributes == (fore, back, blink, underline):
            return
        self.last_attributes = fore, back, blink, underline
        bright = (fore & 8)
        if bright == 0:
            fore = 30 + self.default_colours[fore%8]
        else:
            fore = 90 + self.default_colours[fore%8]
        back = 40 + self.default_colours[back%8]
        sys.stdout.write(ansi.SET_COLOUR % 0)
        sys.stdout.write(ansi.SET_COLOUR % back)
        sys.stdout.write(ansi.SET_COLOUR % fore)
        if blink:
            sys.stdout.write(ansi.SET_COLOUR % 5)
        sys.stdout.flush()

    def set_mode(self, mode_info):
        """Change screen mode."""
        self.height = mode_info.height
        self.width = mode_info.width
        self.num_pages = mode_info.num_pages
        self.text = [[[(u' ', (7, 0, False, False))]*self.width
                            for _ in range(self.height)]
                            for _ in range(self.num_pages)]
        self._set_default_colours(len(mode_info.palette))
        sys.stdout.write(ansi.RESIZE_TERM % (self.height, self.width))
        self._set_attributes(7, 0, False, False)
        sys.stdout.write(ansi.CLEAR_SCREEN)
        sys.stdout.flush()
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
            [(u' ', (7, 0, False, False))]*len(self.text[self.apagenum][0])
                        for _ in range(start-1, stop)]
        if self.vpagenum == self.apagenum:
            self._set_attributes(7, back_attr, False, False)
            for r in range(start, stop+1):
                sys.stdout.write(ansi.MOVE_CURSOR % (r, 1))
                sys.stdout.write(ansi.CLEAR_LINE)
            sys.stdout.write(ansi.MOVE_CURSOR % (self.cursor_row, self.cursor_col))
            self.last_pos = (self.cursor_row, self.cursor_col)
            sys.stdout.flush()

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        #sys.stdout.write(ansi.SET_CURSOR_COLOUR % ansi.COLOUR_NAMES[attr%16])

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        if cursor_on:
            sys.stdout.write(ansi.SHOW_CURSOR)
            #sys.stdout.write(ansi.SET_CURSOR_SHAPE % cursor_shape)
        else:
            # force move when made visible again
            sys.stdout.write(ansi.HIDE_CURSOR)
            self.last_pos = None
        sys.stdout.flush()

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Set the cursor shape."""
        if (to_line-from_line) >= 4:
            self.cursor_shape = 1
        else:
            self.cursor_shape = 3
        # 1 blinking block 2 block 3 blinking line 4 line
        if self.cursor_visible:
            #sys.stdout.write(ansi.SET_CURSOR_SHAPE % cursor_shape)
            sys.stdout.flush()

    def put_glyph(
            self, pagenum, row, col, char, is_fullwidth,
            fore, back, blink, underline, suppress_cli):
        """Put a character at a given position."""
        if char == u'\0':
            char = u' '
        self.text[pagenum][row-1][col-1] = char, (fore, back, blink, underline)
        if is_fullwidth:
            self.text[pagenum][row-1][col] = u'', (fore, back, blink, underline)
        if self.vpagenum != pagenum:
            return
        sys.stdout.write(ansi.MOVE_CURSOR % (row, col))
        self._set_attributes(fore, back, blink, underline)
        sys.stdout.write(char.encode(ENCODING, 'replace'))
        if is_fullwidth:
            sys.stdout.write(' ')
        sys.stdout.write(ansi.MOVE_CURSOR % (self.cursor_row, self.cursor_col))
        self.last_pos = (self.cursor_row, self.cursor_col)
        sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height] +
                [[(u' ', 0)]*len(self.text[self.apagenum][0])])
        if self.apagenum != self.vpagenum:
            return
        sys.stdout.write(ansi.SET_SCROLL_REGION % (from_line, scroll_height))
        sys.stdout.write(ansi.SCROLL_UP % 1)
        sys.stdout.write(ansi.SET_SCROLL_SCREEN)
        self.clear_rows(back_attr, scroll_height, scroll_height)

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
                [[(u' ', 0)]*len(self.text[self.apagenum][0])] +
                self.text[self.apagenum][from_line-1:scroll_height-1])
        if self.apagenum != self.vpagenum:
            return
        sys.stdout.write(ansi.SET_SCROLL_REGION % (from_line, scroll_height))
        sys.stdout.write(ansi.SCROLL_DOWN % 1)
        sys.stdout.write(ansi.SET_SCROLL_SCREEN)
        self.clear_rows(back_attr, from_line, from_line)

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        if msg:
            sys.stdout.write(ansi.SET_TITLE % (self.caption + ' - ' + msg))
        else:
            sys.stdout.write(ansi.SET_TITLE % self.caption)
        sys.stdout.flush()
