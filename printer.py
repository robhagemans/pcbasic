"""
PC-BASIC 3.23 - printer.py
Line printer output 
 
(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

from StringIO import StringIO
import subprocess

import unicodepage
import plat

if plat.system == 'Windows':
    import win32print 
    import tempfile
    import win32api

class PrinterStream(StringIO):
    """ Stream that prints to Unix or Windows printer. """
    
    def __init__(self, printer_name=''):
        """ Initialise the printer stream. """
        self.printer_name = printer_name
        StringIO.__init__(self)

    def close(self):
        """ Close the printer stream. """
        self.flush()

    def flush(self):
        """ Flush the printer buffer to a printer. """
        printbuf = self.getvalue()
        if not printbuf:
            return      
        self.truncate(0)
        # any naked lead bytes in DBCS will remain just that - avoid in-line flushes.
        utf8buf = unicodepage.UTF8Converter(preserve_control=True).to_utf8(printbuf)
        line_print(utf8buf, self.printer_name)

if plat.system == 'Windows':
    def line_print(printbuf, printer_name):
        """ Print the buffer to a Windows printer. """
        if printer_name == '' or printer_name=='default':
            printer_name = win32print.GetDefaultPrinter()
        f = tempfile.NamedTemporaryFile(mode='wb', prefix='pcbasic_', 
                                        suffix='.txt', delete=False)
        # write UTF-8 Byte Order mark to ensure Notepad recognises encoding
        f.write('\xef\xbb\xbf')
        f.write(printbuf)
        # fMask = SEE_MASK_NOASYNC(0x00000100) + SEE_MASK_NOCLOSEPROCESS
        resdict = winshell.ShellExecuteEx(fMask=256+64, 
                        lpVerb='printto', lpFile=f.name, 
                        lpParameters='"%s"' % printer_name)
        handle = resdict['hProcess']
        if win32event.WaitForSingleProcess(handle, 500) != win32event.WAIT_OBJECT_0:
            logging.warning('Printing process timeout')
        f.close()
        
elif plat.system == 'Android':
    def line_print(printbuf, printer_name):
        """ Don't print anything on Android. """
        pass          

elif subprocess.call("command -v paps >/dev/null 2>&1", shell=True) == 0:
    def line_print(printbuf, printer_name): 
        """ Print the buffer to a LPR printer using PAPS for conversion. """
        options = ''
        if printer_name != '' and printer_name != 'default':
            options += '-P ' + printer_name
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
    def line_print(printbuf, printer_name): 
        """ Print the buffer to a LPR (CUPS or older UNIX) printer. """
        options = ''
        if printer_name != '' and printer_name != 'default':
            options += '-P ' + printer_name
        if printbuf != '':
            # cups defaults to 10 cpi, 6 lpi.
            pr = subprocess.Popen('lpr %s' % options, shell=True, 
                                  stdin=subprocess.PIPE)
            pr.stdin.write(printbuf)
            pr.stdin.close()


