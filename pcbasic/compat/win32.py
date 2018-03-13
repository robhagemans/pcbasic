"""
PC-BASIC - compat.win32
Interface for Windows system calls

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import ctypes
from ctypes.wintypes import LPCWSTR, LPWSTR, DWORD
from ctypes import cdll, windll, POINTER, pointer, c_int, c_wchar_p, c_ulonglong, byref


# key pressed on keyboard

from msvcrt import kbhit as key_pressed

# Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
# see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes

try:
    set_dpi_aware = ctypes.windll.user32.SetProcessDPIAware
except AttributeError:
    # old versions of Windows don't have this in user32.dll
    def set_dpi_aware():
        """Enable HiDPI awareness."""
        pass

# free space

_GetDiskFreeSpaceExW = ctypes.windll.kernel32.GetDiskFreeSpaceExW

def get_free_bytes(path):
    """Return the number of free bytes on the drive."""
    free_bytes = c_ulonglong(0)
    _GetDiskFreeSpaceExW(c_wchar_p(path), None, None, pointer(free_bytes))
    return free_bytes.value

# short file names

_GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
_GetShortPathName.argtypes = [LPCWSTR, LPWSTR, DWORD]

def get_short_pathname(native_path):
    """Return Windows short path name or None if not available."""
    try:
        length = _GetShortPathName(native_path, LPWSTR(0), DWORD(0))
        wbuffer = ctypes.create_unicode_buffer(length)
        _GetShortPathName(native_path, wbuffer, DWORD(length))
    except Exception as e:
        # something went wrong - this should be a WindowsError which is an OSError
        # but not clear
        return None
    else:
        # can also be None in wbuffer.value if error
        return wbuffer.value

# command-line arguments

_GetCommandLineW = cdll.kernel32.GetCommandLineW
_GetCommandLineW.argtypes = []
_GetCommandLineW.restype = LPCWSTR

_CommandLineToArgvW = windll.shell32.CommandLineToArgvW
_CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
_CommandLineToArgvW.restype = POINTER(LPWSTR)

def get_unicode_argv():
    """Convert command-line arguments to unicode."""
    # we need to go to the Windows API as argv may not be in a full unicode encoding
    # note that this will not be necessary in Python 3 where sys.argv is unicode
    # http://code.activestate.com/recipes/572200-get-sysargv-with-unicode-characters-under-windows/
    cmd = _GetCommandLineW()
    argc = c_int(0)
    argv = _CommandLineToArgvW(cmd, byref(argc))
    argv = [argv[i] for i in xrange(argc.value)]
    # clip off the python interpreter call, if we use it
    # anything that didn't get included in sys.argv is not for us either
    argv = argv[-len(sys.argv):]
    return argv
