"""
PC-BASIC - compat.posix_console
POSIX console support

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import tty
import time
import termios
import select
import fcntl
import array
import struct
from collections import deque

from .base import MACOS, PY2, HOME_DIR, wrap_input_stream, wrap_output_stream
from . import ansi


class Keys(object):
    """Key codes -  these can be anythong so long as they're ints."""
    PAGEUP = 0x21
    PAGEDOWN = 0x22
    END = 0x23
    HOME = 0x24
    LEFT = 0x25
    UP = 0x26
    RIGHT = 0x27
    DOWN = 0x28
    INSERT = 0x2d
    DELETE = 0x2e
    F1 = 0x70
    F2 = 0x71
    F3 = 0x72
    F4 = 0x73
    F5 = 0x74
    F6 = 0x75
    F7 = 0x76
    F8 = 0x77
    F9 = 0x78
    F10 = 0x79
    F11 = 0x7a
    F12 = 0x7b


ANSI_TO_KEY = {
    ansi.F1: Keys.F1,  ansi.F2: Keys.F2,  ansi.F3: Keys.F3,  ansi.F4: Keys.F4,
    ansi.F1_OLD: Keys.F1,  ansi.F2_OLD: Keys.F2,  ansi.F3_OLD: Keys.F3,
    ansi.F4_OLD: Keys.F4,  ansi.F5: Keys.F5,  ansi.F6: Keys.F6,  ansi.F7: Keys.F7,
    ansi.F8: Keys.F8,  ansi.F9: Keys.F9,  ansi.F10: Keys.F10,  ansi.F11: Keys.F11,
    ansi.F12: Keys.F12,  ansi.END: Keys.END,  ansi.END2: Keys.END,
    ansi.HOME: Keys.HOME,  ansi.HOME2: Keys.HOME,  ansi.UP: Keys.UP,
    ansi.DOWN: Keys.DOWN,  ansi.RIGHT: Keys.RIGHT,  ansi.LEFT: Keys.LEFT,
    ansi.INSERT: Keys.INSERT,  ansi.DELETE: Keys.DELETE,  ansi.PAGEUP: Keys.PAGEUP,
    ansi.PAGEDOWN: Keys.PAGEDOWN,
}


# output buffer for ioctl call
_sock_size = array.array('i', [0])


if PY2:
    stdin = wrap_input_stream(sys.stdin)
    stdout = wrap_output_stream(sys.stdout)
    stderr = wrap_output_stream(sys.stderr)
else:
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr


class PosixConsole(object):
    """POSIX-based console implementation."""

    colours = ansi.Colours
    keys = Keys

    def __init__(self):
        """Set up the console."""
        # check if we can treat stdin like a tty, file or socket
        self.has_stdin = self._check_stdin_exists()
        if self.has_stdin:
            # buffer to save termios state
            self._term_attr = termios.tcgetattr(sys.stdin.fileno())
        else:
            self._term_attr = None
        # preserve original terminal size
        self.original_size = self.get_size()
        # input buffer
        self._read_buffer = deque()

    ##########################################################################
    # terminal modes

    @property
    def is_tty(self):
        return stdin.isatty()

    def _check_stdin_exists(self):
        """Check if we can treat stdin like a tty, file or socket."""
        if not sys.stdin.isatty():
            try:
                fcntl.ioctl(sys.stdin, termios.FIONREAD, _sock_size)
            except EnvironmentError:
                # maybe /dev/null, but not a real file or console
                return False
        return True

    def get_size(self):
        """Get terminal size."""
        try:
            return struct.unpack(
                'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0'*8)
            )[:2]
        except Exception:
            return 25, 80

    def set_raw(self):
        """Enter raw terminal mode."""
        tty.setraw(sys.stdin.fileno())

    def unset_raw(self):
        """Leave raw terminal mode."""
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._term_attr)


    ##########################################################################
    # ansi output

    def write(self, unicode_str):
        """Write unicode to console."""
        stdout.write(unicode_str)
        stdout.flush()

    def _emit_ansi(self, ansistr):
        """Emit escape code."""
        stdout.write(ansistr)
        stdout.flush()

    def set_caption(self, caption):
        """Set terminal caption."""
        self._emit_ansi(ansi.SET_TITLE % (caption,))

    def resize(self, height, width):
        """Resize terminal."""
        self._emit_ansi(ansi.RESIZE_TERM % (height, width))

    def clear(self):
        """Clear the screen."""
        self._emit_ansi(ansi.CLEAR_SCREEN)

    def clear_row(self):
        """Clear the current row."""
        self._emit_ansi(ansi.CLEAR_LINE)

    def show_cursor(self):
        """Show the cursor."""
        self._emit_ansi(ansi.SHOW_CURSOR)

    def hide_cursor(self):
        """Hide the cursor."""
        self._emit_ansi(ansi.HIDE_CURSOR)

    def move_cursor_left(self, n):
        """Move cursor n cells to the left."""
        self._emit_ansi(ansi.MOVE_N_LEFT % (n,))

    def move_cursor_right(self, n):
        """Move cursor n cells to the right."""
        self._emit_ansi(ansi.MOVE_N_RIGHT % (n,))

    def move_cursor_to(self, row, col):
        """Move cursor to a new position."""
        self._emit_ansi(ansi.MOVE_CURSOR % (row, col))

    def scroll_up(self, top, bottom):
        """Scroll the region between top and bottom one row up."""
        self._emit_ansi(
            ansi.SET_SCROLL_REGION % (top, bottom) +
            ansi.SCROLL_UP % 1 +
            ansi.SET_SCROLL_SCREEN
        )

    def scroll_down(self, top, bottom):
        """Scroll the region between top and bottom one row down."""
        self._emit_ansi(
            ansi.SET_SCROLL_REGION % (top, bottom) +
            ansi.SCROLL_DOWN % 1 +
            ansi.SET_SCROLL_SCREEN
        )

    def set_colour(self, colour):
        """Set the current colour attribute."""
        self._emit_ansi(ansi.SET_COLOUR % colour)

    def reset_attributes(self):
        """Reset to default attributes."""
        self._emit_ansi(ansi.SET_COLOUR % 0)

    def set_attributes(self, fore, back, bright, blink, underline):
        """Set current attributes."""
        style = 90 if bright else 30
        self._emit_ansi(
            ansi.SET_COLOUR % 0 +
            ansi.SET_COLOUR % (40 + back) +
            ansi.SET_COLOUR % (style + fore)
        )
        if blink:
            self._emit_ansi(ansi.SET_COLOUR % 5)

    ##########################################################################
    # input

    def key_pressed(self):
        """Return whether a character is ready to be read from the keyboard."""
        return select.select([sys.stdin], [], [], 0)[0] != []

    def _read_char(self):
        """Read keypress from console. Non-blocking. Returns unicode with ANSI sequences."""
        s = read_all_available(stdin)
        if s is None:
            # stream closed, send ctrl-d
            if not self._read_buffer:
                return u'\x04'
        else:
            self._read_buffer.extend(list(s))
        if self._read_buffer:
            return self._read_buffer.popleft()
        return u''

    def read_key(self):
        """
        Read keypress from console. Non-blocking. Returns:
        - unicode, if character key
        - int out of console.keys, if special key
        - u'\x04' if closed
        """
        sequence = self._read_char()
        if not sequence:
            return u''
        # ansi sequences start with \x1b
        esc = (sequence == ansi.ESC)
        # escape sequences are at most 5 chars long
        more = 5
        cutoff = 100
        if not esc:
            return sequence
        while (more > 0) and (cutoff > 0):
            # see if we have a recognised sequence; if so, return keycode
            try:
                return ANSI_TO_KEY[sequence]
            except KeyError:
                pass
            # give time for the queue to fill up
            time.sleep(0.0005)
            char = self._read_char()
            cutoff -= 1
            if not char:
                continue
            more -= 1
            sequence += char
        return sequence


console = PosixConsole()


def read_all_available(stream):
    """Read all available characters from a stream; nonblocking; None if closed."""
    # this function works for everything on unix, and sockets on Windows
    instr = []
    # we're getting bytes counts for unicode which is pretty useless - so back to bytes
    try:
        encoding = stream.encoding
        stream = stream.buffer
    except:
        encoding = None
    # if buffer has characters/lines to read
    if select.select([stream], [], [], 0)[0]:
        # find number of bytes available
        fcntl.ioctl(stream, termios.FIONREAD, _sock_size)
        count = _sock_size[0]
        # and read them all
        c = stream.read(count)
        if not c and not instr:
            # break out, we're closed
            return None
        instr.append(c)
    if encoding:
        return b''.join(instr).decode(encoding, 'replace')
    return b''.join(instr)
