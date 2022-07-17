"""
PC-BASIC - compat
Cross-platform compatibility utilities

(c) 2018--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# pylint: disable=no-name-in-module, import-error, undefined-variable, used-before-assignment

import sys
import os
import io

from .base import PLATFORM, WIN32, MACOS, X64
from .base import USER_CONFIG_HOME, USER_DATA_HOME, BASE_DIR, HOME_DIR
from .base import split_quoted, split_pair, iter_chunks

import configparser, queue, copyreg
from shutil import which
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from .python3 import int2byte, add_str, iterchar, iterbytes
from .python3 import xrange, zip, iteritems, itervalues, iterkeys
from .python3 import getcwdu, getenvu, setenvu, iterenvu
unichr, text_type = chr, str
argv = sys.argv


if WIN32:
    from .win32_console import console, read_all_available, IS_CONSOLE_APP
    from .win32_console import stdio
    from .win32 import set_dpi_aware, line_print
    from .win32 import get_free_bytes, get_short_pathname, is_hidden
    from .win32 import EOL, EOF
    from .win32 import SHELL_ENCODING, HIDE_WINDOW
else:
    from .posix_console import console, read_all_available, IS_CONSOLE_APP
    from .posix_console import stdio
    from .posix import set_dpi_aware, line_print
    from .posix import get_free_bytes, get_short_pathname, is_hidden
    from .posix import EOL, EOF
    from .posix import SHELL_ENCODING, HIDE_WINDOW


if MACOS:
    # on MacOS, if launched from Finder, ignore the additional "process serial number" argument
    argv = [_arg for _arg in argv if not _arg.startswith('-psn_')]
    # for macOS - if no console, presumably we're launched as a bundle
    # set working directory to user home
    # bit of a hack but I don't know a better way
    if not IS_CONSOLE_APP:
        os.chdir(HOME_DIR)
