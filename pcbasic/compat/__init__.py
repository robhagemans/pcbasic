"""
PC-BASIC - compat
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

from .base import PLATFORM, PY2, PY3, WIN32, MACOS, X64
from .base import USER_CONFIG_HOME, USER_DATA_HOME, BASE_DIR
from .base import split_quoted, suppress_output

from .console import console, read_all_available

stdin, stdout, stderr = console.stdin, console.stdout, console.stderr
HAS_CONSOLE = console.has_stdin

if PY2:
    from .python2 import add_str, iterchar
    from .python2 import xrange, zip, iteritems, itervalues, iterkeys
    from .python2 import getcwdu, getenvu, setenvu, iterenvu
    from .python2 import configparser, queue, copyreg, which
    unichr, int2byte, text_type = unichr, chr, unicode

    if WIN32:
        from . import win32_subprocess
        from .win32 import argv
    else:
        from .posix import argv
else:
    import configparser, queue, copyreg
    from shutil import which
    from .python3 import int2byte, add_str, iterchar
    from .python3 import xrange, zip, iteritems, itervalues, iterkeys
    from .python3 import getcwdu, getenvu, setenvu, iterenvu
    unichr, text_type = chr, str
    argv = sys.argv


if WIN32:
    from .win32 import set_dpi_aware, line_print
    from .win32 import get_free_bytes, get_short_pathname, is_hidden
    from .win32 import EOL, EOF, UEOF
    from .win32 import SHELL_ENCODING, HIDE_WINDOW
else:
    from .posix import set_dpi_aware, line_print
    from .posix import get_free_bytes, get_short_pathname, is_hidden
    from .posix import EOL, EOF, UEOF
    from .posix import SHELL_ENCODING, HIDE_WINDOW


if MACOS:
    # on MacOS, if launched from Finder, ignore the additional "process serial number" argument
    argv = [_arg for _arg in argv if not _arg.startswith(b'-psn_')]
    # for macOS - if no console, presumably we're launched as a bundle
    # set working directory to user home
    # bit of a hack but I don't know a better way
    if not console.HAS_CONSOLE:
        os.chdir(HOME_DIR)
