"""
PC-BASIC - compat.console
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
from collections import deque

from .base import PY2, WIN32


if PY2:
    import codecs

    if WIN32:
        from .win32_console import bstdin, bstdout, bstderr
        #from .colorama import AnsiToWin32
        #bstdout, bstderr = AnsiToWin32(bstdout).stream, AnsiToWin32(bstderr).stream
    else:
        bstdin, bstdout, bstderr = sys.stdin, sys.stdout, sys.stderr

    def _wrap_output_stream(stream):
        """Wrap std streams to make them behave more like in Python 3."""
        wrapped = codecs.getwriter(stream.encoding or 'utf-8')(stream)
        wrapped.buffer = stream
        return wrapped

    def _wrap_input_stream(stream):
        """Wrap std streams to make them behave more like in Python 3."""
        wrapped = codecs.getreader(stream.encoding or 'utf-8')(stream)
        wrapped.buffer = stream
        return wrapped

    stdin = _wrap_input_stream(bstdin)
    stdout = _wrap_output_stream(bstdout)
    stderr = _wrap_output_stream(bstderr)

else:
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr

if WIN32:
    from .win32 import read_all_available

    def set_raw():
        pass

    def unset_raw():
        pass

else:
    from .posix import read_all_available
    import tty, termios

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


# console is a terminal (tty)
is_tty = sys.stdin.isatty()

# input buffer
_read_buffer = deque()

def read_char():
    """Read unicode char from console, non-blocking."""
    s = read_all_available(sys.stdin)
    if s is None:
        # stream closed, send ctrl-d
        if not _read_buffer:
            return u'\x04'
    else:
        _read_buffer.extend(list(s))
    return _read_buffer.popleft()

def write(unicode_str):
    """Write unicode to console."""
    stdout.write(unicode_str)
    stdout.flush()
