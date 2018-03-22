"""
PC-BASIC - winsi
Cross-platform console calls (posix version)

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque

from .base import WIN32

if WIN32:
    # if the .pyd had been found, we'd not be loaded.
    raise ImportError('Module `winsi.pyd` not found.')


import sys
import termios
import tty


# save termios state
_term_attr = None

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

def read(n=-1):
    """Read unicode char from console."""
    read_buffer = deque()
    while True:
        read_buffer.append(sys.stdin.read(n))
        try:
            return b''.join(read_buffer).decode(sys.stdin.encoding)
        except UnicodeDecodeError:
            pass

is_tty = sys.stdin.isatty()
encoding = sys.stdout.encoding
