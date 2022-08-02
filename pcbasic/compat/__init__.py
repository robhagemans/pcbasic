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

from .base import PLATFORM, PY2, WIN32, MACOS, X64
from .base import USER_CONFIG_HOME, USER_DATA_HOME, BASE_DIR, HOME_DIR
from .base import split_quoted, split_pair, iter_chunks


##################################################################################################
# not available in Python <= 3.6

try:
    import importlib_resources as resources
except ImportError: # pragma: no cover
    from importlib import resources

try:
    from contextlib import nullcontext
except ImportError: # pragma: no cover

    class nullcontext():
        def __init__(self, enter_result=None):
            self.enter_result = enter_result
        def __enter__(self):
            return self.enter_result
        def __exit__(self, *excinfo):
            pass

##################################################################################################

if PY2: # pragma: no cover
    from .python2 import add_str, iterchar
    from .python2 import xrange, zip, iteritems, itervalues, iterkeys, iterbytes
    from .python2 import getcwdu, getenvu, setenvu, iterenvu
    from .python2 import configparser, queue, copyreg, which
    from .python2 import SimpleNamespace, TemporaryDirectory
    from .python2 import BrokenPipeError, is_broken_pipe
    unichr, int2byte, text_type = unichr, chr, unicode

    if WIN32:
        from . import win32_subprocess
        from .win32 import argv
    else:
        from .posix import argv
else:
    import configparser, queue, copyreg
    from shutil import which
    from types import SimpleNamespace
    from tempfile import TemporaryDirectory
    from .python3 import int2byte, add_str, iterchar, iterbytes
    from .python3 import xrange, zip, iteritems, itervalues, iterkeys
    from .python3 import getcwdu, getenvu, setenvu, iterenvu
    from .python3 import is_broken_pipe
    BrokenPipeError = BrokenPipeError
    unichr, text_type = chr, str
    argv = sys.argv


if WIN32:
    from .win32_console import console, read_all_available, IS_CONSOLE_APP
    from .win32_console import stdio
    from .win32 import set_dpi_aware, line_print
    from .win32 import get_free_bytes, get_short_pathname, is_hidden
    from .win32 import EOL, EOF
    from .win32 import SHELL_ENCODING, OEM_ENCODING, HIDE_WINDOW
else:
    from .posix_console import console, read_all_available, IS_CONSOLE_APP
    from .posix_console import stdio
    from .posix import set_dpi_aware, line_print
    from .posix import get_free_bytes, get_short_pathname, is_hidden
    from .posix import EOL, EOF
    from .posix import SHELL_ENCODING, OEM_ENCODING, HIDE_WINDOW


if MACOS:
    # on MacOS, if launched from Finder, ignore the additional "process serial number" argument
    argv = [_arg for _arg in argv if not _arg.startswith('-psn_')]
    # for macOS - if no console, presumably we're launched as a bundle
    # set working directory to user home
    # bit of a hack but I don't know a better way
    if not IS_CONSOLE_APP:
        os.chdir(HOME_DIR)


##################################################################################################
# deal with broken pipes in scripts

from contextlib import contextmanager

@contextmanager
def script_entry_point_guard():
    """Wrapper for entry points, to deal with Ctrl-C and sigpipe."""
    # see docs.python.org/3/library/signal.html#note-on-sigpipe
    # for cases where shell tools send SIGPIPE
    # e.g. echo -e "?1\r?2\r" | python3.8 -m pcbasic -n | head --lines=1
    exit_code = True
    try:
        yield
        exit_code = False
    except KeyboardInterrupt:
        exit_code = False
    except BrokenPipeError as e:
        # py2 hack
        if not is_broken_pipe(e):
            raise
    # broken pipe usually gets caught above, but flush streams here as a failsafe
    try:
        sys.stdout.flush()
    except Exception:
        exit_code = True
    try:
        sys.stderr.flush()
    except Exception:
        exit_code = True
    if exit_code:
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stderr.fileno())
        except Exception:
            pass
    sys.exit(exit_code)
