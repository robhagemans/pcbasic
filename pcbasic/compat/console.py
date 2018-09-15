"""
PC-BASIC - compat.console
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque

from .base import WIN32


if WIN32:
    from .win32_console import read_all_available
    from .win32_console import Win32Console as _BaseConsole
else:
    from .posix_console import read_all_available
    from .posix_console import PosixConsole as _BaseConsole


class Console(_BaseConsole):
    """Cross-platform terminal/console operations."""

    def __init__(self):
        """Set up console."""
        _BaseConsole.__init__(self)
        # input buffer
        self._read_buffer = deque()

    @property
    def is_tty(self):
        return self.stdin.isatty()

    def read_char(self):
        """Read unicode char from console, non-blocking."""
        s = read_all_available(self.stdin)
        if s is None:
            # stream closed, send ctrl-d
            if not self._read_buffer:
                return u'\x04'
        else:
            self._read_buffer.extend(list(s))
        if self._read_buffer:
            return self._read_buffer.popleft()
        return u''

    def write(self, unicode_str):
        """Write unicode to console."""
        self.stdout.write(unicode_str)
        self.stdout.flush()


console = Console()
