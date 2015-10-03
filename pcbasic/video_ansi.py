"""
PC-BASIC - video_ansi.py
Text interface implementation for Unix

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import sys
import os
import time
import logging
import threading
import Queue

import plat
import config
import unicodepage
import scancode
import backend

import video
import video_cli

# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards,
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi


###############################################################################


def prepare():
    """ Initialise the video_curses module. """
    global caption
    caption = config.get('caption')
    video.plugin_dict['ansi'] = VideoANSI


def set_attributes(fore, back, blink, underline):
    """ Set ANSI colours based on split attribute. """
    bright = (fore & 8)
    if bright == 0:
        fore = 30 + ansi.colours[fore%8]
    else:
        fore = 90 + ansi.colours[fore%8]
    back = 40 + ansi.colours[back%8]
    sys.stdout.write(ansi.esc_set_colour % 0)
    sys.stdout.write(ansi.esc_set_colour % back)
    sys.stdout.write(ansi.esc_set_colour % fore)
    if blink:
        sys.stdout.write(ansi.esc_set_colour % 5)
    sys.stdout.flush()


class VideoANSI(video_cli.VideoCLI):
    """ Text interface implemented with ANSI escape sequences. """

    def __init__(self):
        """ Initialise the text interface. """
        self.set_caption_message('')
        # prevent logger from defacing the screen
        if logging.getLogger().handlers[0].stream.name == sys.stderr.name:
            self.logger = logging.getLogger()
            self.logger.disabled = True
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
        self.text = [[[(' ', (7, 0, False, False))]*80 for _ in range(25)]]
        video_cli.VideoCLI.__init__(self)

    def _close(self):
        """ Close the text interface. """
        video.VideoPlugin._close(self)
        sys.stdout.write(ansi.esc_set_colour % 0)
        sys.stdout.write(ansi.esc_clear_screen)
        sys.stdout.write(ansi.esc_move_cursor % (1, 1))
        self.show_cursor(True)
        sys.stdout.flush()
        # re-enable logger
        self.logger.disabled = False
        video_cli.term_echo()

    def _check_display(self):
        """ Handle screen and interface events. """
        if self.cursor_visible and self.last_pos != (self.cursor_row, self.cursor_col):
            sys.stdout.write(ansi.esc_move_cursor % (self.cursor_row, self.cursor_col))
            sys.stdout.flush()
            self.last_pos = (self.cursor_row, self.cursor_col)

    def _redraw(self):
        """ Redraw the screen. """
        sys.stdout.write(ansi.esc_clear_screen)
        for row, textrow in enumerate(self.text[self.vpagenum]):
            for col, charattr in enumerate(textrow):
                sys.stdout.write(ansi.esc_move_cursor % (row+1, col+1))
                set_attributes(*charattr[1])
                sys.stdout.write(charattr[0])
        sys.stdout.write(ansi.esc_move_cursor % (self.cursor_row, self.cursor_col))
        sys.stdout.flush()


    def set_mode(self, mode_info=None):
        """ Change screen mode. """
        self.height = mode_info.height
        self.width = mode_info.width
        self.num_pages = mode_info.num_pages
        self.text = [[[(' ', (7, 0, False, False))]*self.width
                            for _ in range(self.height)]
                            for _ in range(self.num_pages)]
        sys.stdout.write(ansi.esc_resize_term % (self.height, self.width))
        sys.stdout.write(ansi.esc_clear_screen)
        sys.stdout.flush()
        return True

    def set_page(self, new_vpagenum, new_apagenum):
        """ Set visible and active page. """
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw()

    def copy_page(self, src, dst):
        """ Copy screen pages. """
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw()

    def clear_rows(self, back_attr, start, stop):
        """ Clear screen rows. """
        self.text[self.apagenum][start-1:stop] = [
            [(' ', (7, 0, False, False))]*len(self.text[self.apagenum][0])
                        for _ in range(start-1, stop)]
        if self.vpagenum == self.apagenum:
            set_attributes(7, back_attr, False, False)
            for r in range(start, stop+1):
                sys.stdout.write(ansi.esc_move_cursor % (r, 1))
                sys.stdout.write(ansi.esc_clear_line)
            sys.stdout.flush()

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """ Change attribute of cursor. """
        #sys.stdout.write(ansi.esc_set_cursor_colour % ansi.colournames[attr%16])

    def show_cursor(self, cursor_on):
        """ Change visibility of cursor. """
        self.cursor_visible = cursor_on
        if cursor_on:
            sys.stdout.write(ansi.esc_show_cursor)
            #sys.stdout.write(ansi.esc_set_cursor_shape % cursor_shape)
        else:
            # force move when made visible again
            sys.stdout.write(ansi.esc_hide_cursor)
            self.last_pos = None
        sys.stdout.flush()

    def set_cursor_shape(self, width, height, from_line, to_line):
        """ Set the cursor shape. """
        if (to_line-from_line) >= 4:
            self.cursor_shape = 1
        else:
            self.cursor_shape = 3
        # 1 blinking block 2 block 3 blinking line 4 line
        if self.cursor_visible:
            #sys.stdout.write(ansi.esc_set_cursor_shape % cursor_shape)
            sys.stdout.flush()

    def put_glyph(self, pagenum, row, col, c, fore, back, blink, underline, for_keys):
        """ Put a single-byte character at a given position. """
        try:
            char = unicodepage.UTF8Converter().to_utf8(c)
        except KeyError:
            char = ' ' * len(c)
        self.text[pagenum][row-1][col-1] = char, (fore, back, blink, underline)
        if len(c) > 1:
            self.text[pagenum][row-1][col] = '', (fore, back, blink, underline)
        if self.vpagenum != pagenum:
            return
        sys.stdout.write(ansi.esc_move_cursor % (row, col))
        if self.last_attributes != (fore, back, blink, underline):
            self.last_attributes = fore, back, blink, underline
            set_attributes(fore, back, blink, underline)
        sys.stdout.write(char)
        if len(c) > 1:
            sys.stdout.write(' ')
        sys.stdout.write(ansi.esc_move_cursor % (self.cursor_row, self.cursor_col))
        self.last_pos = (self.cursor_row, self.cursor_col)
        sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height] +
                [[(' ', 0)]*len(self.text[self.apagenum][0])])
        if self.apagenum != self.vpagenum:
            return
        sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
        sys.stdout.write(ansi.esc_scroll_up % 1)
        sys.stdout.write(ansi.esc_set_scroll_screen)
        if self.cursor_row > 1:
            sys.stdout.write(ansi.esc_move_cursor % (self.cursor_row, self.cursor_col))
            self.last_pos = (self.cursor_row, self.cursor_col)
        self.clear_rows(back_attr, scroll_height, scroll_height)

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                [[(' ', 0)]*len(self.text[self.apagenum][0])] +
                self.text[self.apagenum][from_line-1:scroll_height-1])
        if self.apagenum != self.vpagenum:
            return
        sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
        sys.stdout.write(ansi.esc_scroll_down % 1)
        sys.stdout.write(ansi.esc_set_scroll_screen)
        if self.cursor_row > 1:
            sys.stdout.write(ansi.esc_move_cursor % (self.cursor_row, self.cursor_col))
            self.last_pos = (self.cursor_row, self.cursor_col)
        self.clear_rows(back_attr, from_line, from_line)

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """
        if msg:
            sys.stdout.write(ansi.esc_set_title % (caption + ' - ' + msg))
        else:
            sys.stdout.write(ansi.esc_set_title % caption)
        sys.stdout.flush()


prepare()
