"""
PC-BASIC - compat
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import WIN32, MACOS, USER_CONFIG_HOME, USER_DATA_HOME, BASE_DIR
from .python2 import which
from . import winsi as console

if WIN32:
    from . import win_subprocess
    from .win32 import set_dpi_aware, key_pressed, line_print
    from .win32 import get_free_bytes, get_short_pathname, get_unicode_argv
    from .win32 import EOL, EOF, UEOF
    from .win32 import SHELL_ENCODING, HIDE_WINDOW
else:
    from .posix import set_dpi_aware, key_pressed, line_print
    from .posix import get_free_bytes, get_short_pathname, get_unicode_argv
    from .posix import EOL, EOF, UEOF
    from .posix import SHELL_ENCODING, HIDE_WINDOW
