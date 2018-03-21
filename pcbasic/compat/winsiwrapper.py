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

WINSI = WIN32 and sys.stdin.isatty()


if WINSI:
    try:
        from . import winsi
    except ImportError as e:
        WINSI = False

if WINSI:

    class _WinsiWrapper(object):

        encoding = 'utf-8'

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


    ##########################################################################
    # minimal replacements for tty.setraw() and termios.tcsa
    # using ansipipe-only escape sequences

    def set_raw_console():
        """Enter raw terminal mode."""
        winsi.setraw()

    def unset_raw_console():
        """Leave raw terminal mode."""
        winsi.unsetraw()

    def enable_ansi_console():
        """Initialise ANSI console."""
        sys.stdin = _WinsiInputWrapper(sys.stdin)
        print sys.stdin.encoding
        sys.stdout = _WinsiOutputWrapper(sys.stdout)
        print sys.stdout.encoding


else:
    if not WIN32:
        import termios
        import tty

        # we're supporting everything
        WINSI = True
        # save termios state
        _term_attr = None

        def set_raw_console():
            """Enter raw terminal mode."""
            global _term_attr
            fd = sys.stdin.fileno()
            _term_attr = termios.tcgetattr(fd)
            tty.setraw(fd)

        def unset_raw_console():
            """Leave raw terminal mode."""
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _term_attr)

        def read(self, num=-1):
            return sys.stdin.read(num)

        def write(self, s):
            sys.stdout.write(s)



        def enable_ansi_console():
            """Initialise ANSI console."""


    else:

        def set_raw_console():
            """Enter raw terminal mode."""

        def unset_raw_console():
            """Leave raw terminal mode."""


        def read(self, num=-1):
            return sys.stdin.read(num)

        def write(self, s):
            sys.stdout.write(s)



        def enable_ansi_console():
            """Initialise ANSI console."""
