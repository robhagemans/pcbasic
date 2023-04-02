"""
PC-BASIC - compat.console
Console and standard I/O setup

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import atexit


from .base import WIN32


if WIN32:
    from .win32_console import Win32Console, IS_CONSOLE_APP
    from .win32_console import StdIO, init_stdio

    if IS_CONSOLE_APP:
        console = Win32Console()
    else:
        console = None

    stdio = StdIO(console)


    ##############################################################################
    # non-blocking input

    def read_all_available(stream):
        """Read all available bytes or unicode from a stream; nonblocking; None if closed."""
        # are we're reading from (wrapped) stdin or not?
        if hasattr(stream, 'isatty') and stream.isatty():
            # this is shaky - try to identify unicode vs bytes stream
            is_unicode_stream = hasattr(stream, 'buffer')
            # console always produces unicode
            unistr = console.read_all_chars()
            # but convert to bytes if the tty stream provides was a bytes stream
            if is_unicode_stream or unistr is None:
                return unistr
            else:
                return unistr.encode(stdio.stdin.encoding, 'replace')
        else:
            # this would work on unix too
            # just read the whole file and be done with it
            # bytes or unicode, depends on stream
            return stream.read() or None

else:
    from .posix_console import PosixConsole, read_all_available, IS_CONSOLE_APP
    from .posix_console import StdIO, init_stdio

    stdio = StdIO()

    try:
        console = PosixConsole(stdio)
    except EnvironmentError:
        console = None


    # don't crash into raw terminal
    def _atexit_unset_raw():
        try:
            console.unset_raw()
        except Exception:
            pass

    atexit.register(_atexit_unset_raw)
