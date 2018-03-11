"""
PC-BASIC - printer.py
Line printer output

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import subprocess
import logging
import sys
import os
import io


if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import DWORD, HINSTANCE, HANDLE, HKEY, BOOL

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

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = (
            ('cbSize', DWORD),
            ('fMask', ctypes.c_ulong),
            ('hwnd', HANDLE),
            ('lpVerb', ctypes.c_char_p),
            ('lpFile', ctypes.c_char_p),
            ('lpParameters', ctypes.c_char_p),
            ('lpDirectory', ctypes.c_char_p),
            ('nShow', ctypes.c_int),
            ('hInstApp', HINSTANCE),
            ('lpIDList', ctypes.c_void_p),
            ('lpClass', ctypes.c_char_p),
            ('hKeyClass', HKEY),
            ('dwHotKey', DWORD),
            ('hIconOrMonitor', HANDLE),
            ('hProcess', HANDLE),
        )

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SEE_MASK_NOASYNC = 0x00000100

    _ShellExecuteEx = ctypes.windll.shell32.ShellExecuteEx
    _ShellExecuteEx.restype = BOOL
    _WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject


# flush triggers
TRIGGERS = {'page': b'\f', 'line': b'\n', 'close': None, '': None}


class PrinterStreamBase(io.BytesIO):
    """Base stream for printing."""

    def __init__(self, printer_name, flush_trigger, codepage):
        """Initialise the printer stream."""
        self.printer_name = printer_name
        self.codepage = codepage
        # flush_trigger can be a char or a code word
        self._flush_trigger = TRIGGERS.get(flush_trigger.lower(), flush_trigger)
        io.BytesIO.__init__(self)

    def close(self):
        """Close the printer stream."""
        self.flush()
        self._wait()

    def write(self, s):
        """Write to printer stream."""
        for c in s:
            if c == b'\b':
                # backspace: drop a non-newline character from the buffer
                self.seek(-1, 1)
                if self.read(1) not in (b'\r', b'\n', b'\f'):
                    self.seek(-1, 1)
                    self.truncate()
            io.BytesIO.write(self, c)
            if c == self._flush_trigger:
                self.flush()

    def flush(self):
        """Flush the printer buffer to a printer."""
        printbuf = self.getvalue()
        if not printbuf:
            return
        self.seek(0)
        self.truncate()
        # any naked lead bytes in DBCS will remain just that - avoid in-line flushes.
        utf8buf = self.codepage.str_to_unicode(
                    printbuf, preserve_control=True).encode('utf-8', 'replace')
        self._line_print(utf8buf)

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""

    def get_status(self):
        """Get the values of the status pins."""
        return False, False, False, False, False

    def _line_print(self, printbuf):
        """Don't print anything."""

    def _wait(self):
        """Wait for process to complete (dummy)."""


def get_printer_stream(val, codepage, temp_dir):
    """Return the appropriate printer stream for this platform."""
    options = val.split(b':')
    printer_name = options[0]
    flush_trigger = (options[1:] or [''])[0]
    if sys.platform == 'win32':
        return WindowsPrinterStream(temp_dir, printer_name, flush_trigger, codepage)
    elif subprocess.call(b'command -v paps >/dev/null 2>&1', shell=True) == 0:
        return PAPSPrinterStream(printer_name, flush_trigger, codepage)
    else:
        return CUPSPrinterStream(printer_name, flush_trigger, codepage)


class WindowsPrinterStream(PrinterStreamBase):
    """Stream that prints to Windows printer."""

    def __init__(self, temp_dir, printer_name, flush_trigger, codepage):
        """Initialise Windows printer stream."""
        PrinterStreamBase.__init__(self, printer_name, flush_trigger, codepage)
        # temp file in temp dir
        self._printfile = os.path.join(temp_dir, u'pcbasic_print.txt')
        # handle for last printing process
        self.handle = -1

    def _line_print(self, printbuf):
        """Print the buffer to a Windows printer."""
        if self.printer_name == b'' or self.printer_name == b'default':
            self.printer_name = get_default_printer()
        # open a file in our PC-BASIC temporary directory
        # this will get cleaned up on exit
        with open(self._printfile, 'wb') as f:
            # write UTF-8 Byte Order mark to ensure Notepad recognises encoding
            f.write(b'\xef\xbb\xbf')
            f.write(printbuf)
        try:
            sei = SHELLEXECUTEINFO()
            sei.cbSize = ctypes.sizeof(sei)
            sei.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
            sei.lpVerb = 'printto'
            sei.lpFile = self._printfile
            sei.lpParameters = '"%s"' % self.printer_name
            sei.hProcess = HANDLE()
            _ShellExecuteEx(ctypes.byref(sei))
            self.handle = sei.hProcess
        except EnvironmentError as e:
            logging.error(b'Error while printing: %s', e)
            self.handle = -1

    def _wait(self):
        """Give printing process some time to complete."""
        try:
            _WaitForSingleObject(self.handle, DWORD(1000))
        except EnvironmentError as e:
            logging.warning('Windows error: %s', e)
            pass


class PAPSPrinterStream(PrinterStreamBase):
    """Stream that prints to a CUPS printer using PAPS."""

    def _line_print(self, printbuf):
        """Print the buffer to a LPR printer using PAPS."""
        options = b''
        if self.printer_name != b'' and self.printer_name != b'default':
            options += b'-P ' + self.printer_name
        if printbuf != b'':
            # A4 paper is 595 points wide by 842 points high.
            # Letter paper is 612 by 792 points.
            # the below seems to allow 82 chars horizontally on A4; it appears
            # my PAPS version doesn't quite use cpi correctly as 10cpi should
            # allow 80 chars on A4 with a narrow margin but only does so with a
            # margin of 0.
            pr = subprocess.Popen(
                b'paps --cpi=11 --lpi=6 --left-margin=20 --right-margin=20 '
                '--top-margin=6 --bottom-margin=6 '
                '| lpr %s' % options, shell=True, stdin=subprocess.PIPE)
            # PAPS does not recognise CRLF
            printbuf = printbuf.replace('\r\n', '\n')
            pr.stdin.write(printbuf)
            pr.stdin.close()


class CUPSPrinterStream(PrinterStreamBase):
    """Stream that prints to a CUPS or LPR printer."""

    def _line_print(self, printbuf):
        """Print the buffer to a LPR (CUPS or older UNIX) printer."""
        options = ''
        if self.printer_name != b'' and self.printer_name != b'default':
            options += b'-P ' + self.printer_name
        if printbuf != b'':
            # cups defaults to 10 cpi, 6 lpi.
            pr = subprocess.Popen(b'lpr %s' % options, shell=True, stdin=subprocess.PIPE)
            pr.stdin.write(printbuf)
            pr.stdin.close()
