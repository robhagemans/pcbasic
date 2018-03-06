"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter
Windows console entry point

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import subprocess


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
        from .main import main
        main()
    args = get_unicode_argv()
    startdir = os.path.join(os.path.dirname(os.path.realpath(__file__)))
    launcher = os.path.join(startdir, 'lib', 'ansipipe-launcher.exe')
    if os.path.isfile(launcher):
        # subprocess.call is not unicode-aware in Python 2
        # https://stackoverflow.com/questions/1910275/unicode-filenames-on-windows-with-python-subprocess-popen
        # see also https://gist.github.com/vaab/2ad7051fc193167f15f85ef573e54eb9 for a workaround
        # instead just encode in utf-8 and make our main entry point assume that on Windows
        # note that all this would be much easier if we didn't go though anispipe launcher
        args = [arg.encode('utf-8') for arg in args]
        os.chdir('..')
        subprocess.call([launcher, sys.executable, '-m', 'pcbasic'] + args[1:])
    else:
        from .main import main
        main(*args)
