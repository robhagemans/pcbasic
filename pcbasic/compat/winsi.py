"""
PC-BASIC - winsi
Cross-platform console calls (posix version)

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

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

def write(s):
    """Write to console."""
    sys.stdout.write(s)
    sys.stdout.flush()


encoding = sys.stdout.encoding
read = sys.stdin.read

#TODO: isatty; make all args unicode
