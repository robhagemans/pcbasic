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
import platform

from . import ansi
from .video import VideoPlugin
from .base import video_plugins, InitFailed
from ..basic.base import signals
from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea

if platform.system() == 'Windows':
    from .. import ansipipe
    tty = ansipipe
    termios = ansipipe
    # Ctrl+Z to exit
    EOF = uea.CTRL_z
else:
    import tty, termios
    # Ctrl+D to exit
    EOF = uea.CTRL_d


ENCODING = sys.stdin.encoding or 'utf-8'


@video_plugins.register('cli')
class VideoCLI(VideoPlugin):
    """Command-line interface."""

    def __init__(self, input_queue, video_queue, **kwargs):
        """Initialise command-line interface."""
        try:
            if platform.system() not in (b'Darwin',  b'Windows') and not sys.stdin.isatty():
                raise InitFailed('Text-based interface requires a terminal (tty).')
        except AttributeError:
            pass
        VideoPlugin.__init__(self, input_queue, video_queue)
        self._term_echo_on = True
        self._term_attr = None
        self._term_echo(False)
        # start the stdin thread for non-blocking reads
        self.input_handler = InputHandlerCLI()
        # cursor is visible
        self.cursor_visible = True
        # current row and column for cursor
        self.cursor_row = 1
        self.cursor_col = 1
        # last row and column printed on
        self.last_row = None
        self.last_col = None
        # text buffer
        self.num_pages = 1
        self.vpagenum, self.apagenum = 0, 0
        self.text = [[[u' ']*80 for _ in range(25)]]
        self.f12_active = False

    def __exit__(self, type, value, traceback):
        """Close command-line interface."""
        VideoPlugin.__exit__(self, type, value, traceback)
        self._term_echo()
        if self.last_col and self.cursor_col != self.last_col:
            sys.stdout.write('\n')

    def _work(self):
        """Display update cycle."""
        self._update_position()

    def _check_input(self):
        """Handle keyboard events."""
        while True:
            # s is one unicode char or one scancode
            uc, sc = self.input_handler.get_key()
            if not uc and not sc:
                break
            if uc == EOF:
                # ctrl-D (unix) / ctrl-Z (windows)
                self._input_queue.put(signals.Event(signals.KEYB_QUIT))
            elif uc == u'\x7f':
                # backspace
                self._input_queue.put(signals.Event(signals.KEYB_DOWN,
                                        (uea.BACKSPACE, scancode.BACKSPACE, [])))
            elif sc or uc:
                # check_full=False to allow pasting chunks of text
                self._input_queue.put(signals.Event(
                                        signals.KEYB_DOWN, (uc, sc, [])))
                if sc == scancode.F12:
                    self.f12_active = True
                else:
                    self._input_queue.put(signals.Event(
                                            signals.KEYB_UP, (scancode.F12,)))
                    self.f12_active = False

    def _term_echo(self, on=True):
        """Set/unset raw terminal attributes."""
        # sets raw terminal - no echo, by the character rather than by the line
        fd = sys.stdin.fileno()
        if (not on) and self._term_echo_on:
            self._term_attr = termios.tcgetattr(fd)
            tty.setraw(fd)
        elif not self._term_echo_on and self._term_attr is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._term_attr)
        previous, self._term_echo_on = self._term_echo_on, on
        sys.stdout.flush()
        return previous

    ###############################################################################


    def put_glyph(
            self, pagenum, row, col, char, is_fullwidth,
            fore, back, blink, underline, suppress_cli):
        """Put a character at a given position."""
        if char == u'\0':
            char = u' '
        self.text[pagenum][row-1][col-1] = char
        if is_fullwidth:
            self.text[pagenum][row-1][col] = u''
        if self.vpagenum != pagenum:
            return
        if suppress_cli:
            return
        self._update_position(row, col)
        sys.stdout.write(char.encode(ENCODING, 'replace'))
        sys.stdout.flush()
        self.last_col += 2 if is_fullwidth else 1

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = crow, ccol

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        self.text[self.apagenum][start-1:stop] = [
            [u' ']*len(self.text[self.apagenum][0]) for _ in range(start-1, stop)]
        if (start <= self.cursor_row and stop >= self.cursor_row and
                    self.vpagenum == self.apagenum):
            self._update_position(self.cursor_row, 1)
            sys.stdout.write(ansi.CLEAR_LINE)
            sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height]
                + [[u' ']*len(self.text[self.apagenum][0])])
        if self.vpagenum != self.apagenum:
            return
        sys.stdout.write('\r\n')
        sys.stdout.flush()

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        self.text[self.apagenum][from_line-1:scroll_height] = (
                [[u' ']*len(self.text[self.apagenum][0])] +
                self.text[self.apagenum][from_line-1:scroll_height-1])

    def set_mode(self, mode_info):
        """Initialise video mode """
        self.num_pages = mode_info.num_pages
        self.text = [[[u' ']*mode_info.width for _ in range(mode_info.height)]
                                            for _ in range(self.num_pages)]

    def set_page(self, new_vpagenum, new_apagenum):
        """Set visible and active page."""
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw_row(self.cursor_row)

    def copy_page(self, src, dst):
        """Copy screen pages."""
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw_row(self.cursor_row)

    def _redraw_row(self, row):
        """Draw the stored text in a row."""
        rowtext = u''.join(self.text[self.vpagenum][row-1]).encode(ENCODING, 'replace')
        sys.stdout.write(rowtext)
        sys.stdout.write(ansi.MOVE_LEFT * len(rowtext))
        sys.stdout.flush()

    def _update_position(self, row=None, col=None):
        """Update screen for new cursor position."""
        # this happens on resume
        if self.last_row is None:
            self.last_row = self.cursor_row
            self._redraw_row(self.cursor_row)
        if self.last_col is None:
            self.last_col = self.cursor_col
        # allow updating without moving the cursor
        if row is None:
            row = self.cursor_row
        if col is None:
            col = self.cursor_col
        # move cursor if necessary
        if row != self.last_row:
            sys.stdout.write('\r\n')
            sys.stdout.flush()
            self.last_col = 1
            self.last_row = row
            # show what's on the line where we are.
            self._redraw_row(self.cursor_row)
        if col != self.last_col:
            sys.stdout.write(ansi.MOVE_LEFT*(self.last_col-col))
            sys.stdout.write(ansi.MOVE_RIGHT*(col-self.last_col))
            sys.stdout.flush()
            self.last_col = col



###############################################################################

class InputHandlerCLI(object):
    """Keyboard reader thread."""

    # Note that we use a separate thread implementation because:
    # * sys.stdin.read(1) is a blocking read
    # * we need this to work on Windows as well as Unix, so select() won't do.

    def __init__(self):
        """Start the keyboard reader."""
        self._launch_thread()

    def _launch_thread(self):
        """Start the keyboard reader thread."""
        self.stdin_q = Queue.Queue()
        t = threading.Thread(target=self._read_stdin)
        t.daemon = True
        t.start()

    def _read_stdin(self):
        """Wait for stdin and put any input on the queue."""
        while True:
            self.stdin_q.put(sys.stdin.read(1))
            # don't be a hog
            time.sleep(0.0001)

    def _getc(self):
        """Read character from keyboard, non-blocking."""
        try:
            return self.stdin_q.get_nowait()
        except Queue.Empty:
            return ''

    def get_key(self):
        """Retrieve one scancode sequence or one unicode char from keyboard."""
        s = self._getc()
        if s == '':
            return None, None
        # ansi sequences start with \x1b
        esc = (s == ansi.ESC)
        # escape sequences are at most 5 and UTF-8 at most 4 chars long
        more = 5
        cutoff = 100
        while (more > 0) and (cutoff > 0):
            if esc:
                # return the first recognised escape sequence
                uc = esc_to_eascii.get(s, '')
                scan = esc_to_scan.get(s, None)
                if uc or scan:
                    return uc, scan
            else:
                # return the first recognised encoding sequence
                try:
                    return s.decode(ENCODING), None
                except UnicodeDecodeError:
                    pass
            # give time for the queue to fill up
            time.sleep(0.0005)
            c = self._getc()
            cutoff -= 1
            if c == '':
                continue
            more -= 1
            s += c
        # no sequence or decodable string found
        # decode as good as it gets
        return s.decode(ENCODING, errors='replace'), None



# escape sequence to scancode dictionary
esc_to_scan = {
    ansi.F1: scancode.F1,
    ansi.F2: scancode.F2,
    ansi.F3: scancode.F3,
    ansi.F4: scancode.F4,
    ansi.F1_OLD: scancode.F1,
    ansi.F2_OLD: scancode.F2,
    ansi.F3_OLD: scancode.F3,
    ansi.F4_OLD: scancode.F4,
    ansi.F5: scancode.F5,
    ansi.F6: scancode.F6,
    ansi.F7: scancode.F7,
    ansi.F8: scancode.F8,
    ansi.F9: scancode.F9,
    ansi.F10: scancode.F10,
    ansi.F11: scancode.F11,
    ansi.F12: scancode.F12,
    ansi.END: scancode.END,
    ansi.END2: scancode.END,
    ansi.HOME: scancode.HOME,
    ansi.HOME2: scancode.HOME,
    ansi.UP: scancode.UP,
    ansi.DOWN: scancode.DOWN,
    ansi.RIGHT: scancode.RIGHT,
    ansi.LEFT: scancode.LEFT,
    ansi.INSERT: scancode.INSERT,
    ansi.DELETE: scancode.DELETE,
    ansi.PAGEUP: scancode.PAGEUP,
    ansi.PAGEDOWN: scancode.PAGEDOWN,
    }

esc_to_eascii = {
    ansi.F1: uea.F1,
    ansi.F2: uea.F2,
    ansi.F3: uea.F3,
    ansi.F4: uea.F4,
    ansi.F1_OLD: uea.F1,
    ansi.F2_OLD: uea.F2,
    ansi.F3_OLD: uea.F3,
    ansi.F4_OLD: uea.F4,
    ansi.F5: uea.F5,
    ansi.F6: uea.F6,
    ansi.F7: uea.F7,
    ansi.F8: uea.F8,
    ansi.F9: uea.F9,
    ansi.F10: uea.F10,
    ansi.F11: uea.F11,
    ansi.F12: uea.F12,
    ansi.END: uea.END,
    ansi.END2: uea.END,
    ansi.HOME: uea.HOME,
    ansi.HOME2: uea.HOME,
    ansi.UP: uea.UP,
    ansi.DOWN: uea.DOWN,
    ansi.RIGHT: uea.RIGHT,
    ansi.LEFT: uea.LEFT,
    ansi.INSERT: uea.INSERT,
    ansi.DELETE: uea.DELETE,
    ansi.PAGEUP: uea.PAGEUP,
    ansi.PAGEDOWN: uea.PAGEDOWN,
    }
