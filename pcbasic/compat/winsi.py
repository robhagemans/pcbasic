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
    import ctypes
    import os

    try:
        _dll = ctypes.CDLL(os.path.join(BASE_DIR, 'lib', 'winsi.dll'))
    except OSError as e:
        WINSI = False

if WINSI:
    import atexit
    import logging

    BUFFER_LENGTH = 1024
    BUFFER = ctypes.create_string_buffer(BUFFER_LENGTH)

    _init = _dll.winsi_init
    _init.argtypes = []
    _init.restype = None

    _close = _dll.winsi_close
    _close.argtypes = []
    _close.restype = None

    _read = _dll.winsi_read
    _read.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_long]
    _read.restype = ctypes.c_long

    _write = _dll.winsi_write
    _write.argtypes = [ctypes.POINTER(ctypes.c_char)]
    _write.restype = None


    class _WinsiWrapper(object):

        encoding = 'utf-8'

        def __init__(self, wrapped_stream):
            self._wrapped_stream = wrapped_stream

        def __getattr__(self, attr):
            return getattr(self._wrapped_stream, attr)


    class _WinsiInputWrapper(_WinsiWrapper):

        def __init__(self, wrapped_stream):
            _WinsiWrapper.__init__(self, wrapped_stream)
            self._multichar_buffer = []

        def read(self, num=-1):
            if num == -1:
                # save some space at the end as it may return multibyte sequences
                num = BUFFER_LENGTH-10
            n_to_read = max(0, num - len(self._multichar_buffer))
            if n_to_read:
                _read(BUFFER, n_to_read)
                self._multichar_buffer.extend(BUFFER.value)
            out, self._multichar_buffer = self._multichar_buffer[:num], self._multichar_buffer[num:]
            return b''.join(out)


    class _WinsiOutputWrapper(_WinsiWrapper):

        def write(self, s):
            _write(s)


    def enable_ansi_console():
        """Initialise ANSI console."""
        global _stdin, _stdout
        _init()
        sys.stdout, _stdout = _WinsiOutputWrapper(sys.stdout), sys.stdout
        sys.stdin, _stdin = _WinsiInputWrapper(sys.stdin), sys.stdin
        atexit.register(_close)

    ##########################################################################
    # minimal replacements for tty.setraw() and termios.tcsa
    # using ansipipe-only escape sequences

    def set_raw_console():
        """Enter raw terminal mode."""
        _set_terminal_state(echo=False, icrnl=False, onlcr=False)

    def unset_raw_console():
        """Leave raw terminal mode."""
        _set_terminal_state(echo=True, icrnl=True, onlcr=False)

    def _set_terminal_state(echo, icrnl, onlcr):
        """Set ansipipe terminal state (echo, CR/LF substitutions)."""
        num = 254
        sys.stdout.write('\x1b]%d;ECHO\x07' % (num + echo))
        sys.stdout.write('\x1b]%d;ICRNL\x07' % (num + icrnl))
        sys.stdout.write('\x1b]%d;ONLCR\x07' % (num + onlcr))
        sys.stdout.flush()

else:
    if not WIN32:
        import termios
        import tty

        # we're supporting everything
        WINSI = True
        # save termios state
        _term_attr = None

        def enable_ansi_console():
            """Initialise ANSI console."""

        def set_raw_console():
            """Enter raw terminal mode."""
            global _term_attr
            fd = sys.stdin.fileno()
            _term_attr = termios.tcgetattr(fd)
            tty.setraw(fd)

        def unset_raw_console():
            """Leave raw terminal mode."""
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _term_attr)

    else:
        def enable_ansi_console():
            """Initialise ANSI console."""

        def set_raw_console():
            """Enter raw terminal mode."""

        def unset_raw_console():
            """Leave raw terminal mode."""
