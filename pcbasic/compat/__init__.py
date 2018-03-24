"""
PC-BASIC - compat
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import WIN32, MACOS, X64, USER_CONFIG_HOME, USER_DATA_HOME, BASE_DIR
from .python2 import which

if WIN32:
    if X64:
        from . import win32_x64_console as console
    else:
        from . import win32_x86_console as console
    from . import win32_subprocess
    from .win32 import set_dpi_aware, line_print, key_pressed, read_all_available
    from .win32 import get_free_bytes, get_short_pathname, get_unicode_argv
    from .win32 import EOL, EOF, UEOF
    from .win32 import SHELL_ENCODING, HIDE_WINDOW
else:
    from . import posix_console as console
    from .posix import set_dpi_aware, line_print, key_pressed, read_all_available
    from .posix import get_free_bytes, get_short_pathname, get_unicode_argv
    from .posix import EOL, EOF, UEOF
    from .posix import SHELL_ENCODING, HIDE_WINDOW
