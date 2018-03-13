"""
PC-BASIC - compat
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import WIN32, MACOS, USER_CONFIG_HOME, USER_DATA_HOME
from .base import STDIN_ENCODING, STDOUT_ENCODING

if WIN32:
    from .win32 import set_dpi_aware, key_pressed
    from .win32 import get_free_bytes, get_short_pathname, get_unicode_argv
else:
    from .posix import set_dpi_aware, key_pressed
    from .posix import get_free_bytes, get_short_pathname, get_unicode_argv
