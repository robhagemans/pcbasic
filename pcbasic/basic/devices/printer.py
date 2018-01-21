"""
PC-BASIC - printer.py
Line printer output

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import subprocess
import logging
import platform
import os
import io

if platform.system() == 'Windows':
    try:
        import win32print
        import win32com
        import win32com.shell.shell
        import win32event
    except ImportError:
        win32print = None


class PrinterStreamBase(io.BytesIO):
    """Base stream for printing."""

    def __init__(self, printer_name, codepage):
        """Initialise the printer stream."""
        self.printer_name = printer_name
        self.codepage = codepage
        io.BytesIO.__init__(self)

    def close(self):
        """Close the printer stream."""
        self.flush()
        self._wait()

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
    if platform.system() == 'Windows':
        if win32print:
            return WindowsPrinterStream(val, codepage, temp_dir)
        else:
            logging.warning('Could not find win32print module. Printing is disabled.')
            return PrinterStreamBase(val, codepage)
    elif subprocess.call("command -v paps >/dev/null 2>&1", shell=True) == 0:
        return PAPSPrinterStream(val, codepage)
    else:
        return CUPSPrinterStream(val, codepage)


class WindowsPrinterStream(PrinterStreamBase):
    """Stream that prints to Windows printer."""

    def __init__(self, printer_name, codepage, temp_dir):
        """Initialise Windows printer stream."""
        PrinterStreamBase.__init__(self, printer_name, codepage)
        # temp file in temp dir
        self._printfile = os.path.join(temp_dir, 'pcbasic_print.txt')
        # handle for last printing process
        self.handle = -1

    def _line_print(self, printbuf):
        """Print the buffer to a Windows printer."""
        if self.printer_name == '' or self.printer_name == 'default':
            self.printer_name = win32print.GetDefaultPrinter()
        # open a file in our PC-BASIC temporary directory
        # this will get cleaned up on exit
        with open(self._printfile, 'wb') as f:
            # write UTF-8 Byte Order mark to ensure Notepad recognises encoding
            f.write('\xef\xbb\xbf')
            f.write(printbuf)
        # fMask = SEE_MASK_NOASYNC(0x00000100) + SEE_MASK_NOCLOSEPROCESS
        try:
            resdict = win32com.shell.shell.ShellExecuteEx(fMask=256+64,
                            lpVerb='printto', lpFile=self._printfile,
                            lpParameters='"%s"' % self.printer_name)
            self.handle = resdict['hProcess']
        except OSError as e:
            logging.warning('Error while printing: %s', bytes(e))
            self.handle = -1

    def _wait(self):
        """Give printing process some time to complete."""
        try:
            win32event.WaitForSingleObject(self.handle, 1000)
        except OSError:
            pass


class PAPSPrinterStream(PrinterStreamBase):
    """Stream that prints to a CUPS printer using PAPS."""

    def _line_print(self, printbuf):
        """Print the buffer to a LPR printer using PAPS."""
        options = ''
        if self.printer_name != '' and self.printer_name != 'default':
            options += '-P ' + self.printer_name
        if printbuf != '':
            # A4 paper is 595 points wide by 842 points high.
            # Letter paper is 612 by 792 points.
            # the below seems to allow 82 chars horizontally on A4; it appears
            # my PAPS version doesn't quite use cpi correctly as 10cpi should
            # allow 80 chars on A4 with a narrow margin but only does so with a
            # margin of 0.
            pr = subprocess.Popen(
                'paps --cpi=11 --lpi=6 --left-margin=20 --right-margin=20 '
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
        if self.printer_name != '' and self.printer_name != 'default':
            options += '-P ' + self.printer_name
        if printbuf != '':
            # cups defaults to 10 cpi, 6 lpi.
            pr = subprocess.Popen('lpr %s' % options, shell=True,
                                  stdin=subprocess.PIPE)
            pr.stdin.write(printbuf)
            pr.stdin.close()
