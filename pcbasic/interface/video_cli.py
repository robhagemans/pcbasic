"""
PC-BASIC - video_cli.py
Command-line interface

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import time
import threading
import Queue

from . import ansi
from .video import VideoPlugin
from .base import video_plugins, InitFailed
from ..basic.base import signals
from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea
from ..compat import UEOF, console


# escape sequence to scancode
ESC_TO_SCAN = {
    ansi.F1: scancode.F1,  ansi.F2: scancode.F2,  ansi.F3: scancode.F3,  ansi.F4: scancode.F4,
    ansi.F1_OLD: scancode.F1,  ansi.F2_OLD: scancode.F2,  ansi.F3_OLD: scancode.F3,
    ansi.F4_OLD: scancode.F4,  ansi.F5: scancode.F5,  ansi.F6: scancode.F6,  ansi.F7: scancode.F7,
    ansi.F8: scancode.F8,  ansi.F9: scancode.F9,  ansi.F10: scancode.F10,  ansi.F11: scancode.F11,
    ansi.F12: scancode.F12,  ansi.END: scancode.END,  ansi.END2: scancode.END,
    ansi.HOME: scancode.HOME,  ansi.HOME2: scancode.HOME,  ansi.UP: scancode.UP,
    ansi.DOWN: scancode.DOWN,  ansi.RIGHT: scancode.RIGHT,  ansi.LEFT: scancode.LEFT,
    ansi.INSERT: scancode.INSERT,  ansi.DELETE: scancode.DELETE,  ansi.PAGEUP: scancode.PAGEUP,
    ansi.PAGEDOWN: scancode.PAGEDOWN,
    }

# escape sequence to e-ASCII
ESC_TO_EASCII = {
    ansi.F1: uea.F1,  ansi.F2: uea.F2,  ansi.F3: uea.F3,  ansi.F4: uea.F4,  ansi.F1_OLD: uea.F1,
    ansi.F2_OLD: uea.F2,  ansi.F3_OLD: uea.F3,  ansi.F4_OLD: uea.F4,  ansi.F5: uea.F5,
    ansi.F6: uea.F6,  ansi.F7: uea.F7,  ansi.F8: uea.F8,  ansi.F9: uea.F9,  ansi.F10: uea.F10,
    ansi.F11: uea.F11,  ansi.F12: uea.F12,  ansi.END: uea.END,  ansi.END2: uea.END,
    ansi.HOME: uea.HOME,  ansi.HOME2: uea.HOME,  ansi.UP: uea.UP,  ansi.DOWN: uea.DOWN,
    ansi.RIGHT: uea.RIGHT,  ansi.LEFT: uea.LEFT,  ansi.INSERT: uea.INSERT,
    ansi.DELETE: uea.DELETE,  ansi.PAGEUP: uea.PAGEUP,  ansi.PAGEDOWN: uea.PAGEDOWN,
    }


class VideoTextBase(VideoPlugin):
    """Text-based interface."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Initialise text-based interface."""
        if not console:
            raise InitFailed('Extension module `win32_console` not compiled.')
        if not console.is_tty:
            raise InitFailed('Not a terminal (tty).')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # start the stdin thread for non-blocking reads
        self._input_handler = InputHandlerCLI(input_queue)

    def __enter__(self):
        """Open text-based interface."""
        VideoPlugin.__enter__(self)
        console.set_raw()

    def __exit__(self, exc_type, value, traceback):
        """Close text-based interface."""
        try:
            console.unset_raw()
        finally:
            VideoPlugin.__exit__(self, exc_type, value, traceback)

    def _check_input(self):
        """Handle keyboard events."""
        self._input_handler.drain_queue()


@video_plugins.register('cli')
class VideoCLI(VideoTextBase):
    """Command-line interface."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Initialise command-line interface."""
        VideoTextBase.__init__(self, input_queue, video_queue)
        # current row and column where the cursor should be
        # keep cursor_row and last_row unset at the start to avoid printing extra line on resume
        # as it will see a move frm whatever we set it at here to the actusl cursor row
        self._cursor_row, self._cursor_col = None, 1
        # current actual print column
        self._col = 1
        # cursor row on last cycle
        self._last_row = None
        # text buffer
        self._vpagenum, self._apagenum = 0, 0
        self._text = [[[u' '] * 80 for _ in range(25)]]

    def __exit__(self, type, value, traceback):
        """Close command-line interface."""
        try:
            if self._col != 1:
                console.write(u'\r\n')
        finally:
            VideoTextBase.__exit__(self, type, value, traceback)

    def _work(self):
        """Display update cycle."""
        # update cursor row only if it's changed from last work-cycle
        # or if actual printing takes place on the new cursor row
        if self._cursor_row != self._last_row or self._cursor_col != self._col:
            self._update_position(self._cursor_row, self._cursor_col)

    ###############################################################################

    def put_glyph(self, pagenum, row, col, char, is_fullwidth, fore, back, blink, underline):
        """Put a character at a given position."""
        if char == u'\0':
            char = u' '
        self._text[pagenum][row-1][col-1] = char
        if is_fullwidth:
            self._text[pagenum][row-1][col] = u''
        # show the character only if it's on the cursor row
        if self._vpagenum == pagenum and row == self._cursor_row:
            # may have to update row!
            if row != self._last_row or col != self._col:
                self._update_position(row, col)
            console.write(char)
            #console.flush()
            self._col = (col+2) if is_fullwidth else (col+1)
        # the terminal cursor has moved, so we'll need to move it back later
        # if that's not where we want to be
        # but often it is anyway

    def move_cursor(self, row, col):
        """Move the cursor to a new position."""
        # update cursor row only if it's changed from last work-cycle
        # or if actual printing takes place on the new cursor row
        self._cursor_row, self._cursor_col = row, col

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        self._text[self._apagenum][start-1:stop] = [
                [u' '] * len(self._text[self._apagenum][0])
                for _ in range(start-1, stop)
            ]
        if (self._vpagenum == self._apagenum and
                start <= self._cursor_row and stop >= self._cursor_row):
            self._update_position(self._cursor_row, 1)
            console.write(ansi.CLEAR_LINE.decode('ascii'))
            #console.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        self._text[self._apagenum][from_line-1:scroll_height] = (
                self._text[self._apagenum][from_line:scroll_height]
                + [[u' '] * len(self._text[self._apagenum][0])]
            )
        if self._vpagenum != self._apagenum:
            return
        console.write(u'\r\n')
        #console.flush()

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        self._text[self._apagenum][from_line-1:scroll_height] = (
                [[u' '] * len(self._text[self._apagenum][0])] +
                self._text[self._apagenum][from_line-1:scroll_height-1]
            )

    def set_mode(self, mode_info):
        """Initialise video mode """
        self._text = [
                [[u' '] * mode_info.width for _ in range(mode_info.height)]
                for _ in range(mode_info.num_pages)
            ]

    def set_page(self, new_vpagenum, new_apagenum):
        """Set visible and active page."""
        self._vpagenum, self._apagenum = new_vpagenum, new_apagenum
        self._redraw_row(self._cursor_row)

    def copy_page(self, src, dst):
        """Copy screen pages."""
        self._text[dst] = [row[:] for row in self._text[src]]
        if dst == self._vpagenum:
            self._redraw_row(self._cursor_row)

    def _redraw_row(self, row):
        """Draw the stored text in a row."""
        if not row:
            return
        self._update_col(1)
        rowtext = (u''.join(self._text[self._vpagenum][row-1]))
        console.write(rowtext.replace(u'\0', u' '))
        self._col = len(self._text[self._vpagenum][row-1])+1
        #console.flush()

    def _update_position(self, row, col):
        """Move terminal print location."""
        # move cursor if necessary
        if row and row != self._last_row:
            if self._last_row:
                console.write(u'\r\n')
                #console.flush()
                self._col = 1
            self._last_row = row
            # show what's on the line where we are.
            self._redraw_row(row)
        self._update_col(col)

    def _update_col(self, col):
        """Move terminal print column."""
        if col != self._col:
            if self._col > col:
                console.write(ansi.MOVE_N_LEFT.decode('ascii') % (self._col-col))
                #console.flush()
            elif self._col < col:
                console.write(ansi.MOVE_N_RIGHT.decode('ascii') % (col-self._col))
                #console.flush()
            self._col = col


###############################################################################

class InputHandlerCLI(object):
    """Keyboard reader thread."""

    def __init__(self, queue):
        """Start the keyboard reader."""
        self._input_queue = queue
        self._f12_active = False

    def drain_queue(self):
        """Handle keyboard events."""
        while True:
            # s is one unicode char or one scancode
            uc, sc = self._get_key()
            if not uc and not sc:
                break
            if uc == UEOF:
                # ctrl-D (unix) / ctrl-Z (windows)
                self._input_queue.put(signals.Event(signals.KEYB_QUIT))
            elif uc == u'\x7f':
                # backspace
                self._input_queue.put(
                        signals.Event(signals.KEYB_DOWN, (uea.BACKSPACE, scancode.BACKSPACE, [])))
            elif sc or uc:
                # check_full=False to allow pasting chunks of text
                self._input_queue.put(signals.Event(signals.KEYB_DOWN, (uc, sc, [])))
                # this is needed since we don't send key-up events at all otherwise
                if sc == scancode.F12:
                    self._f12_active = True
                elif self._f12_active:
                    self._input_queue.put(signals.Event(signals.KEYB_UP, (scancode.F12,)))
                    self._f12_active = False

    def _get_key(self):
        """Retrieve one scancode sequence or one unicode char from keyboard."""
        s = console.read_char()
        if s == u'':
            return None, None
        # ansi sequences start with \x1b
        esc = (s == ansi.ESC)
        # escape sequences are at most 5 chars long
        more = 5
        cutoff = 100
        if not esc:
            return s, None
        while (more > 0) and (cutoff > 0):
            if esc:
                # return the first recognised escape sequence
                uc = ESC_TO_EASCII.get(s, u'')
                scan = ESC_TO_SCAN.get(s, None)
                if uc or scan:
                    return uc, scan
            # give time for the queue to fill up
            time.sleep(0.0005)
            c = console.read_char()
            cutoff -= 1
            if c == u'':
                continue
            more -= 1
            s += c
        # no sequence or decodable string found
        # decode as good as it gets
        return s, None
