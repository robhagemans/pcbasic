"""
PC-BASIC - compat.console
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque

from .base import WIN32

if WIN32:
    from .win32_console import stdin, stdout, stderr, TERM_SIZE, HAS_CONSOLE
    from .win32_console import set_raw, unset_raw, key_pressed, read_all_available
else:
    from .posix_console import stdin, stdout, stderr, TERM_SIZE, HAS_CONSOLE
    from .posix_console import set_raw, unset_raw, key_pressed, read_all_available


# console is a terminal (tty)
is_tty = stdin.isatty()

# input buffer
_read_buffer = deque()

def read_char():
    """Read unicode char from console, non-blocking."""
    s = read_all_available(stdin)
    if s is None:
        # stream closed, send ctrl-d
        if not _read_buffer:
            return u'\x04'
    else:
        _read_buffer.extend(list(s))
    if _read_buffer:
        return _read_buffer.popleft()
    return u''

def write(unicode_str):
    """Write unicode to console."""
    stdout.write(unicode_str)
    stdout.flush()
