"""
PC-BASIC - posix_console
POSIX console calls

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
import termios
import select
import tty
import sys

from .posix import read_all_available


# save termios state
_term_attr = None
# input buffer
_read_buffer = deque()

# console is a terminal (tty)
is_tty = sys.stdin.isatty()
# console encoding
# this can be None on macOS if running on console from inside an appdir
encoding = sys.stdout.encoding or 'utf-8'


def set_raw():
    """Enter raw terminal mode."""
    global _term_attr
    fd = sys.stdin.fileno()
    _term_attr = termios.tcgetattr(fd)
    tty.setraw(fd)

def unset_raw():
    """Leave raw terminal mode."""
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _term_attr)

def write(unicode_str):
    """Write unicode to console."""
    sys.stdout.write(unicode_str.encode(encoding))
    sys.stdout.flush()

def read_char():
    """Read unicode char from console, non-blocking."""
    s = read_all_available(sys.stdin)
    if s is None:
        # stream closed
        if not _read_buffer:
            return u'\x04'
    else:
        _read_buffer.extend(list(s))
    output = []
    while _read_buffer:
        output.append(_read_buffer.popleft())
        try:
            return b''.join(output).decode(sys.stdin.encoding or 'utf-8')
        except UnicodeDecodeError:
            pass
    # not enough to decode, keep for next call
    _read_buffer.extendleft(output)
    return u''
