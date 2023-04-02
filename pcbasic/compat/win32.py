"""
PC-BASIC - compat.win32
Interface for Windows system calls

(c) 2018--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import ctypes
import codecs
import logging
import threading
import subprocess
import msvcrt
import struct
import tempfile
import time

from ctypes.wintypes import LPCWSTR, LPWSTR, DWORD, HINSTANCE, HANDLE, HKEY, BOOL
from ctypes import cdll, windll, POINTER, pointer, c_int, c_wchar_p, c_ulonglong, byref


# text conventions
# ctrl+Z
EOF = u'\x1A'
# CRLF end-of-line
EOL = u'\r\n'


##############################################################################
# cmd.exe conventions

# register cp65001 as an alias for utf-8
codecs.register(lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None)

# get OEM codepage - the one used when cmd is launched from a non-console application
HKEY_LOCAL_MACHINE = 0x80000002
KEY_QUERY_VALUE = 0x0001

def _get_oem_encoding():
    """Get Windows OEM codepage."""
    hkey = HKEY()
    windll.advapi32.RegOpenKeyExW(
        HKEY_LOCAL_MACHINE, LPWSTR(u'SYSTEM\\CurrentControlSet\\Control\\Nls\\CodePage'),
        DWORD(0), DWORD(KEY_QUERY_VALUE), byref(hkey))
    strval = ctypes.create_unicode_buffer(255)
    # key HKLM SYSTEM\\CurrentControlSet\\Control\\Nls\\CodePage value OEMCP
    size = DWORD(0)
    windll.advapi32.RegQueryValueExW(hkey, LPWSTR(u'OEMCP'), DWORD(0), None, None, byref(size))
    windll.advapi32.RegQueryValueExW(
        hkey, LPWSTR(u'OEMCP'), DWORD(0), None, byref(strval), byref(size)
    )
    windll.advapi32.RegCloseKey(hkey)
    return 'cp' + strval.value


# if starting from a console, shell will inherit its codepage
# if starting from the gui (stdin is None), we're using OEM codepage
OEM_ENCODING = _get_oem_encoding()
SHELL_ENCODING = None
if sys.stdin:
    SHELL_ENCODING = sys.stdin.encoding
SHELL_ENCODING = SHELL_ENCODING or OEM_ENCODING
# there's also an ACP codepage - this seems to be locale.getpreferredencoding()
#_ACP_ENCODING = 'cp' + str(cdll.kernel32.GetACP())


# avoid having an empty CMD window popping up in front of ours
HIDE_WINDOW = subprocess.STARTUPINFO()
HIDE_WINDOW.dwFlags |= 1  # STARTF_USESHOWWINDOW
HIDE_WINDOW.wShowWindow = 0 # SW_HIDE


##############################################################################
# various

# Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
# see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes

try:
    set_dpi_aware = ctypes.windll.user32.SetProcessDPIAware
except AttributeError:
    # old versions of Windows don't have this in user32.dll
    def set_dpi_aware():
        """Enable HiDPI awareness."""
        pass

##############################################################################
# file system

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

def _get_unicode_argv():
    """Convert command-line arguments to unicode."""
    # we need to go to the Windows API as argv may not be in a full unicode encoding
    # note that this will not be necessary in Python 3 where sys.argv is unicode
    # http://code.activestate.com/recipes/572200-get-sysargv-with-unicode-characters-under-windows/
    cmd = _GetCommandLineW()
    argc = c_int(0)
    argv = _CommandLineToArgvW(cmd, byref(argc))
    argv = [argv[i] for i in range(argc.value)]
    # clip off the python interpreter call, if we use it
    # anything that didn't get included in sys.argv is not for us either
    argv = argv[-len(sys.argv):]
    return argv

argv = _get_unicode_argv()


_GetFileAttributesW = windll.kernel32.GetFileAttributesW
_GetFileAttributesW.argtypes = [LPCWSTR]
_GetFileAttributesW.restype = DWORD
_FILE_ATTRIBUTE_HIDDEN = 2

def is_hidden(path):
    """File is hidden."""
    return _GetFileAttributesW(LPCWSTR(path)) & _FILE_ATTRIBUTE_HIDDEN


##############################################################################
# printing

class SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = (
        ('cbSize', DWORD),
        ('fMask', ctypes.c_ulong),
        ('hwnd', HANDLE),
        ('lpVerb', LPCWSTR),
        ('lpFile', LPCWSTR),
        ('lpParameters', LPCWSTR),
        ('lpDirectory', LPCWSTR),
        ('nShow', ctypes.c_int),
        ('hInstApp', HINSTANCE),
        ('lpIDList', ctypes.c_void_p),
        ('lpClass', LPCWSTR),
        ('hKeyClass', HKEY),
        ('dwHotKey', DWORD),
        ('hIconOrMonitor', HANDLE),
        ('hProcess', HANDLE),
    )

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100

_ShellExecuteEx = ctypes.windll.shell32.ShellExecuteExW
_ShellExecuteEx.restype = BOOL
_WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject


def get_default_printer():
    """Get the Windows default printer name."""
    try:
        _GetDefaultPrinterW = ctypes.WinDLL('winspool.drv').GetDefaultPrinterW
        length = DWORD()
        ret = _GetDefaultPrinterW(None, ctypes.byref(length))
        name = ctypes.create_unicode_buffer(length.value)
        ret = _GetDefaultPrinterW(name, ctypes.byref(length))
        return name.value
    except EnvironmentError as e:
        logging.error('Could not get default printer: %s', e)
        return u''

PRINTER_TIMEOUT_MS=1000

def _wait_for_process(handle, filename):
    """Give printing process some time to complete."""
    try:
        _WaitForSingleObject(handle, DWORD(PRINTER_TIMEOUT_MS))
    except EnvironmentError as e:
        logging.warning('Windows error: %s', e)
    # remove temporary
    os.remove(filename)

def line_print(printbuf, printer):
    """Print the buffer to a Windows printer."""
    if not printer or printer == u'default':
        printer = get_default_printer()
    if printbuf:
        with tempfile.NamedTemporaryFile(
                suffix='.txt', prefix='pcbasic-print-', delete=False) as f:
            # write UTF-8 Byte Order mark to ensure Notepad recognises encoding
            f.write(b'\xef\xbb\xbf')
            f.write(printbuf)
        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
        sei.lpVerb = u'printto'
        sei.lpFile = f.name
        sei.lpParameters = u'"%s"' % printer
        sei.hProcess = HANDLE()
        try:
            _ShellExecuteEx(ctypes.byref(sei))
        except EnvironmentError as e:
            logging.error(b'Error while printing: %s', e)
        else:
            # launch non-daemon thread to wait for handle
            # to ensure we don't lose the print if triggered on exit
            threading.Thread(target=_wait_for_process, args=(sei.hProcess, f.name)).start()
