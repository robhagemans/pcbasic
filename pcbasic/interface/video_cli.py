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
    try:
        from . import winsi
    except ImportError:
        winsi = None
    tty = winsi
    termios = winsi
    # Ctrl+Z to exit
    EOF = uea.CTRL_z
else:
    winsi = True
    import tty, termios
    # Ctrl+D to exit
    EOF = uea.CTRL_d


ENCODING = sys.stdin.encoding or 'utf-8'

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
        try:
            if platform.system() not in (b'Darwin',  b'Windows') and not sys.stdin.isatty():
                raise InitFailed('Text-based interface requires a terminal (tty).')
        except AttributeError:
            pass
        if not winsi:
            raise InitFailed('Module `winsi.dll` not found.')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # start the stdin thread for non-blocking reads
        self._input_handler = InputHandlerCLI(input_queue)
        # terminal attributes (for setraw)
        self._term_attr = None

    def __enter__(self):
        """Open text-based interface."""
        VideoPlugin.__enter__(self)
        fd = sys.stdin.fileno()
        self._term_attr = termios.tcgetattr(fd)
        # raw terminal - no echo, by the character rather than by the line
        tty.setraw(fd)
        sys.stdout.flush()

    def __exit__(self, exc_type, value, traceback):
        """Close text-based interface."""
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._term_attr)
            sys.stdout.flush()
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
                sys.stdout.write(b'\r\n')
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
            sys.stdout.write(char.encode(ENCODING, 'replace'))
            sys.stdout.flush()
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
            sys.stdout.write(ansi.CLEAR_LINE)
            sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        self._text[self._apagenum][from_line-1:scroll_height] = (
                self._text[self._apagenum][from_line:scroll_height]
                + [[u' '] * len(self._text[self._apagenum][0])]
            )
        if self._vpagenum != self._apagenum:
            return
        sys.stdout.write('\r\n')
        sys.stdout.flush()

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
        sys.stdout.write(rowtext.encode(ENCODING, 'replace').replace('\0', ' '))
        self._col = len(self._text[self._vpagenum][row-1])+1
        sys.stdout.flush()

    def _update_position(self, row, col):
        """Move terminal print location."""
        # move cursor if necessary
        if row and row != self._last_row:
            if self._last_row:
                sys.stdout.write(b'\r\n')
                sys.stdout.flush()
                self._col = 1
            self._last_row = row
            # show what's on the line where we are.
            self._redraw_row(row)
        self._update_col(col)

    def _update_col(self, col):
        """Move terminal print column."""
        if col != self._col:
            if self._col > col:
                sys.stdout.write(ansi.MOVE_N_LEFT % (self._col-col))
                sys.stdout.flush()
            elif self._col < col:
                sys.stdout.write(ansi.MOVE_N_RIGHT % (col-self._col))
                sys.stdout.flush()
            self._col = col


###############################################################################

class InputHandlerCLI(object):
    """Keyboard reader thread."""

    # Note that we use a separate thread implementation because:
    # * sys.stdin.read(1) is a blocking read
    # * we need this to work on Windows as well as Unix, so select() won't do.

    def __init__(self, queue):
        """Start the keyboard reader."""
        self._input_queue = queue
        self._f12_active = False
        self._launch_thread()

    def _launch_thread(self):
        """Start the keyboard reader thread."""
        self._stdin_q = Queue.Queue()
        t = threading.Thread(target=self._read_stdin)
        t.daemon = True
        t.start()

    def _read_stdin(self):
        """Wait for stdin and put any input on the queue."""
        while True:
            self._stdin_q.put(sys.stdin.read(1))
            # don't be a hog
            time.sleep(0.0001)

    def _getc(self):
        """Read character from keyboard, non-blocking."""
        try:
            return self._stdin_q.get_nowait()
        except Queue.Empty:
            return ''

    def drain_queue(self):
        """Handle keyboard events."""
        while True:
            # s is one unicode char or one scancode
            uc, sc = self._get_key()
            if not uc and not sc:
                break
            if uc == EOF:
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
                uc = ESC_TO_EASCII.get(s, '')
                scan = ESC_TO_SCAN.get(s, None)
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
