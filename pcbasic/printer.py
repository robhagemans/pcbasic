"""
PC-BASIC - printer.py
Line printer output

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from StringIO import StringIO
import subprocess
import logging

import plat


class PrinterStreamBase(StringIO):
    """ Base stream for printing. """

    def __init__(self, printer_name, codepage):
        """ Initialise the printer stream. """
        self.printer_name = printer_name
        self.codepage = codepage
        StringIO.__init__(self)

    def close(self):
        """ Close the printer stream. """
        self.flush()
        self._wait()

    def flush(self):
        """ Flush the printer buffer to a printer. """
        printbuf = self.getvalue()
        if not printbuf:
            return
        self.truncate(0)
        # any naked lead bytes in DBCS will remain just that - avoid in-line flushes.
        utf8buf = self.codepage.str_to_unicode(
                    printbuf, preserve_control=True).encode('utf-8', 'replace')
        self._line_print(utf8buf)

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """ Set the values of the control pins. """

    def get_status(self):
        """ Get the values of the status pins. """
        return False, False, False, False, False

    def _line_print(self, printbuf):
        """ Don't print anything. """

    def _wait(self):
        """ Wait for process to complete (dummy). """


if plat.system == 'Windows':
    import os
    import win32print
    import win32com
    import win32com.shell.shell
    import win32event

    # temp file in temp dir
    printfile = os.path.join(plat.temp_dir, 'pcbasic_print.txt')

    class PrinterStream(PrinterStreamBase):
        """ Stream that prints to Windows printer. """

        def __init__(self, printer_name, codepage):
            """ Initialise Windows printer stream. """
            PrinterStreamBase.__init__(self, printer_name, codepage)
            # handle for last printing process
            self.handle = -1

        def _line_print(self, printbuf):
            """ Print the buffer to a Windows printer. """
            if self.printer_name == '' or self.printer_name == 'default':
                self.printer_name = win32print.GetDefaultPrinter()
            # open a file in our PC-BASIC temporary directory
            # this will get cleaned up on exit
            with open(printfile, 'wb') as f:
                # write UTF-8 Byte Order mark to ensure Notepad recognises encoding
                f.write('\xef\xbb\xbf')
                f.write(printbuf)
            # fMask = SEE_MASK_NOASYNC(0x00000100) + SEE_MASK_NOCLOSEPROCESS
            try:
                resdict = win32com.shell.shell.ShellExecuteEx(fMask=256+64,
                                lpVerb='printto', lpFile=printfile,
                                lpParameters='"%s"' % self.printer_name)
                self.handle = resdict['hProcess']
            except OSError as e:
                logging.warning('Error while printing: %s', bytes(e))
                self.handle = -1

        def _wait(self):
            """ Give printing process some time to complete. """
            try:
                win32event.WaitForSingleObject(self.handle, 1000)
            except OSError:
                pass

elif subprocess.call("command -v paps >/dev/null 2>&1", shell=True) == 0:

    class PrinterStream(PrinterStreamBase):
        """ Stream that prints to a CUPS printer using PAPS. """

        def _line_print(self, printbuf):
            """ Print the buffer to a LPR printer using PAPS. """
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

else:

    class PrinterStream(PrinterStreamBase):
        """ Stream that prints to a CUPS or LPR printer. """

        def _line_print(self, printbuf):
            """ Print the buffer to a LPR (CUPS or older UNIX) printer. """
            options = ''
            if self.printer_name != '' and self.printer_name != 'default':
                options += '-P ' + self.printer_name
            if printbuf != '':
                # cups defaults to 10 cpi, 6 lpi.
                pr = subprocess.Popen('lpr %s' % options, shell=True,
                                      stdin=subprocess.PIPE)
                pr.stdin.write(printbuf)
                pr.stdin.close()
