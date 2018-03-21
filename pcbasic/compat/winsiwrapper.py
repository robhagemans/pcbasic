"""
PC-BASIC - winsi
DLL interface for ANSI escape sequences on Windows (formerly ansipipe)

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

from .base import WIN32, BASE_DIR

ORIG_STDIN_ENCODING = sys.stdin.encoding
ORIG_STDOUT_ENCODING = sys.stdout.encoding

from . import winsi
WINSI = True


class _WinsiWrapper(object):

    encoding = winsi.encoding

    def __init__(self, wrapped_stream):
        self._wrapped_stream = wrapped_stream

    def __getattr__(self, attr):
        return getattr(self._wrapped_stream, attr)


class _WinsiInputWrapper(_WinsiWrapper):
    def read(self, num=-1):
        return winsi.read(num)


class _WinsiOutputWrapper(_WinsiWrapper):
    def write(self, s):
        winsi.write(s)


set_raw_console = winsi.setraw
unset_raw_console = winsi.unsetraw

def enable_ansi_console():
    """Initialise ANSI console."""
    sys.stdin = _WinsiInputWrapper(sys.stdin)
    sys.stdout = _WinsiOutputWrapper(sys.stdout)
