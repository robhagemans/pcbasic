"""
PC-BASIC - compat.posix
Interface for Unix-like system calls

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
"""
PC-BASIC - win32
DLL interface for Windows system libraries

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import locale
import select


def key_pressed():
    """Return whether a character is ready to be read from the keyboard."""
    return select.select([sys.stdin], [], [], 0)[0] != []

def set_dpi_aware():
    """Enable HiDPI awareness."""

def get_free_bytes(path):
    """Return the number of free bytes on the drive."""
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize

def get_short_pathname(native_path):
    """Return Windows short path name or None if not available."""
    return None

def get_unicode_argv():
    """Convert command-line arguments to unicode."""
    # the official parameter should be LC_CTYPE but that's None in my locale
    # on Windows, this would only work if the mbcs CP_ACP includes the characters we need;
    return [arg.decode(locale.getpreferredencoding(), errors='replace') for arg in sys.argv]
