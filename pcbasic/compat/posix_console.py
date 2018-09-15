"""
PC-BASIC - compat.posix_console
POSIX console support

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import tty
import termios
import select
import fcntl
import array
import struct

from .base import MACOS, PY2, HOME_DIR, wrap_input_stream, wrap_output_stream
from . import ansi


# output buffer for ioctl call
_sock_size = array.array('i', [0])


class PosixConsole(object):
    """POSIX-based console implementation."""

    colours = ansi.Colours

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
        if PY2:
            self.stdin = wrap_input_stream(sys.stdin)
            self.stdout = wrap_output_stream(sys.stdout)
            self.stderr = wrap_output_stream(sys.stderr)
        else:
            self.stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr

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

    def key_pressed(self):
        """Return whether a character is ready to be read from the keyboard."""
        return select.select([sys.stdin], [], [], 0)[0] != []

    def _emit_ansi(self, ansistr):
        """Emit escape code."""
        sys.stdout.write(ansistr)
        sys.stdout.flush()

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
