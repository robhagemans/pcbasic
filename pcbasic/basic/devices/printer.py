"""
PC-BASIC - printer.py
Line printer output

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io
from ...compat import line_print


# flush triggers
TRIGGERS = {'page': b'\f', 'line': b'\n', 'close': None, '': None}


class PrinterStream(io.BytesIO):
    """Base stream for printing."""

    def __init__(self, printer_name, flush_trigger, codepage, temp_dir):
        """Initialise the printer stream."""
        self.printer_name = printer_name
        self.codepage = codepage
        # flush_trigger can be a char or a code word
        self._flush_trigger = TRIGGERS.get(flush_trigger.lower(), flush_trigger)
        io.BytesIO.__init__(self)
        # temp file in temp dir
        self._printfile = os.path.join(temp_dir, u'pcbasic_print.txt')

    def close(self):
        """Close the printer stream."""
        self.flush()

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
        line_print(utf8buf, self.printer_name, self._printfile)

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""

    def get_status(self):
        """Get the values of the status pins."""
        return False, False, False, False, False


def get_printer_stream(val, codepage, temp_dir):
    """Return the appropriate printer stream for this platform."""
    options = val.split(b':')
    printer_name = options[0]
    flush_trigger = (options[1:] or [''])[0]
    return PrinterStream(printer_name, flush_trigger, codepage, temp_dir)
