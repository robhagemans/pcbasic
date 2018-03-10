"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
Windows console entry point

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import subprocess
from .main import main

def get_unicode_argv():
    """Convert Windows command-line arguments to unicode."""
    # we need to go to the Windows API as argv may not be in a full unicode encoding
    # note that this will not be necessary in Python 3 where sys.argv is unicode
    # http://code.activestate.com/recipes/572200-get-sysargv-with-unicode-characters-under-windows/
    from ctypes import cdll, windll, POINTER, c_int, byref
    from ctypes.wintypes import LPCWSTR, LPWSTR
    GetCommandLineW = cdll.kernel32.GetCommandLineW
    GetCommandLineW.argtypes = []
    GetCommandLineW.restype = LPCWSTR
    cmd = GetCommandLineW()
    argc = c_int(0)
    CommandLineToArgvW = windll.shell32.CommandLineToArgvW
    CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
    CommandLineToArgvW.restype = POINTER(LPWSTR)
    argv = CommandLineToArgvW(cmd, byref(argc))
    argv = [argv[i] for i in xrange(argc.value)]
    # clip off the python interpreter call, if we use it
    # anything that didn't get included in sys.argv is not for us either
    argv = argv[-len(sys.argv):]
    return argv

def winmain():
    """Windows console entry point."""
    if sys.platform != 'win32':
        main()
    else:
        args = get_unicode_argv()
        main(*args[1:])
