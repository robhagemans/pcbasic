"""
PC-BASIC - winsi
DLL interface for ANSI escape sequences on Windows (formerly ansipipe)

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

if sys.platform == 'win32' and sys.stdin.isatty():
    import ctypes
    import atexit
    import os

    if hasattr(sys, 'frozen'):
        # we're a package: get the directory of the packaged executable
        # (__file__ is undefined in pyinstaller packages)
        DLLPATH = os.path.dirname(sys.executable)
    else:
        DLLPATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'lib')

    dll = ctypes.CDLL(os.path.join(DLLPATH, 'winsi.dll'))

    BUFFER_LENGTH = 1024
    BUFFER = ctypes.create_string_buffer(BUFFER_LENGTH)

    _init = dll.winsi_init
    _init.argtypes = []
    _init.restype = None

    _close = dll.winsi_close
    _close.argtypes = []
    _close.restype = None

    _read = dll.winsi_read
    _read.argtypes = [ctypes.POINTER(ctypes.c_char), ctypes.c_long]
    _read.restype = ctypes.c_long

    _write = dll.winsi_write
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


    _init()

    sys.stdout, _stdout = _WinsiOutputWrapper(sys.stdout), sys.stdout
    sys.stdin, _stdin = _WinsiInputWrapper(sys.stdin), sys.stdin

    atexit.register(_close)

    ##########################################################################

    # minimal replacements for tty.setraw() and termios.tcsa
    # using ansipipe-only escape sequences
    ONLCR = 4
    ECHO = 8
    ICRNL = 256

    TCSADRAIN = 1

    termios_state = ICRNL | ECHO

    def setraw(fd, dummy=None):
        """ Set raw terminal mode (Windows stub). """
        tcsetattr(fd, dummy, 0)

    def tcsetattr(fd, dummy, attr):
        """ Set terminal attributes (Windows stub). """
        if (fd == sys.stdin.fileno()):
            num = 254
            sys.stdout.write('\x1b]%d;ECHO\x07' % (num + (attr & ECHO != 0)))
            sys.stdout.write('\x1b]%d;ICRNL\x07' % (num + (attr & ICRNL != 0)))
            sys.stdout.write('\x1b]%d;ONLCR\x07' % (num + (attr & ONLCR != 0)))
            termios_state = attr

    def tcgetattr(fd):
        """ Get terminal attributes (Windows stub). """
        if (fd == sys.stdin.fileno()):
            return termios_state
        else:
            return 0
