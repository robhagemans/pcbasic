"""
PC-BASIC - posix_console
POSIX console calls

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque

from .base import WIN32

if WIN32:
    # if the .pyd had been found, we'd not be loaded.
    raise ImportError('Module `winsi.pyd` not found.')

from .posix import read_all_available

import termios
import select
import tty
import sys


# save termios state
_term_attr = None

# input buffer
_read_buffer = deque()


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
    sys.stdout.write(unicode_str.encode(sys.stdout.encoding))
    sys.stdout.flush()

def read_char():
    """Read unicode char from console, non-blocking."""
    s = read_all_available(sys.stdin)
    if s is None:
        # stream closed
        if not _read_buffer:
            return u'\x04'
    else:
        _read_buffer.append(s)
    output = []
    while _read_buffer:
        output.append(_read_buffer.popleft())
        try:
            return b''.join(output).decode(sys.stdin.encoding)
        except UnicodeDecodeError:
            pass
    # not enough to decode, keep for next call
    _read_buffer.appendleft(output)
    return u''

is_tty = sys.stdin.isatty()
encoding = sys.stdout.encoding
