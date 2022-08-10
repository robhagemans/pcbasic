"""
PC-BASIC - parports.py
Parallel port handling

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import os
import io

try:
    import parallel
except Exception:
    parallel = None

from ...compat import line_print, iterchar, stdio
from ..base import error
from ..codepage import CONTROL
from .devicebase import Device, DeviceSettings, TextFileBase, parse_protocol_string, safe_io


# flush triggers
TRIGGERS = {'page': b'\f', 'line': b'\n', 'close': None, '': None}


###############################################################################
# LPT ports

class LPTDevice(Device):
    """Parallel port or printer device (LPTn:) """

    # LPT1 can be opened as RANDOM
    # but behaves just like OUTPUT
    # in GW-BASIC, FIELD gives a FIELD OVERFLOW; we get BAD FILE MODE.
    allowed_modes = b'OR'

    def __init__(self, arg, default_stream, codepage):
        """Initialise LPTn: device."""
        Device.__init__(self)
        addr, val = parse_protocol_string(arg)
        self.stream = default_stream
        if addr == u'FILE':
            try:
                self.stream = io.open(val, 'wb')
            except EnvironmentError as e:
                logging.warning(u'Could not attach file %s to LPT device: %s', val, e)
        elif addr == u'PARPORT':
            # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
            try:
                self.stream = ParallelStream(val)
            except EnvironmentError as e:
                logging.warning(u'Could not attach parallel port %s to LPT device: %s', val, e)
        elif addr == u'STDIO' or (not addr and val == u'STDIO'):
            self.stream = StdIOParallelStream()
        elif addr == u'PRINTER' or (val and not addr):
            # 'PRINTER' is default
            # name:parameters (LINE, PAGE, ...)
            options = val.split(u':')
            printer_name = options[0]
            flush_trigger = (options[1:] or [u''])[0]
            self.stream = PrinterStream(printer_name, flush_trigger, codepage)
        elif val:
            logging.warning(u'Could not attach %s to LPT device', arg)
        # column counter is the same across all LPT files
        self.device_settings = DeviceSettings()
        if self.stream:
            self.device_file = LPTFile(self.stream, self.device_settings)

    def open(
            self, number, param, filetype, mode, access, lock,
            reclen, seg, offset, length, fiekd):
        """Open a file on LPTn: """
        # shared position/width settings across files
        return LPTFile(self.stream, self.device_settings, bug=True)

    def available(self):
        """Device is available."""
        return self.stream is not None


###############################################################################
# file on LPT device

class LPTFile(TextFileBase):
    """LPTn: device - line printer or parallel port."""

    def __init__(self, stream, settings, bug=False):
        """Initialise LPTn."""
        # GW-BASIC quirk - different LPOS behaviour on LPRINT and LPT1 files
        self._bug = bug
        self._settings = settings
        TextFileBase.__init__(self, stream, filetype=b'D', mode=b'A')
        # default width is 80
        # width=255 means line wrap
        self.width = 80
        # we need to keep these in sync as self .col is accessed by Formatter (and others)
        # we can't make col a @property as the TextFileBase init tries to set it to a number
        self.col = self._settings.col

    def set_width(self, new_width=255):
        """Set file width."""
        self.width = new_width

    def write(self, s, can_break=True):
        """Write a string to the printer buffer."""
        assert isinstance(s, bytes), type(s)
        with safe_io():
            for c in iterchar(s):
                # don't replace CR or LF with
                self._fhandle.write(c)
                # col reverts to 1 on CR (\r) and LF (\n) but not FF (\f)
                if c in (b'\n', b'\r'):
                    self._settings.col = 1
                elif c == b'\b':
                    if self._settings.col > 1:
                        self._settings.col -= 1
                else:
                    # nonprinting characters including tabs are not counted for LPOS
                    if ord(c) >= 32:
                        self._settings.col += 1
                # width 255 means wrapping enabled
                if can_break and self.width != 255:
                    if self._settings.col > self.width:
                        self._fhandle.write(b'\r\n')
                        # GW-BASIC quirk: on LPT1 files the LPOS goes to width+1, then wraps to 2
                        if not self._bug:
                            self._settings.col = 1
                        elif self._settings.col > self.width + 1:
                            self._settings.col = 2
        self.col = self._settings.col

    def write_line(self, s=b''):
        """Write string or bytearray and newline to file."""
        assert isinstance(s, bytes), type(s)
        self.write(s + b'\r\n')

    def lof(self):
        """LOF: bad file mode """
        raise error.BASICError(error.BAD_FILE_MODE)

    def loc(self):
        """LOC: bad file mode """
        raise error.BASICError(error.BAD_FILE_MODE)

    def eof(self):
        """EOF: bad file mode """
        raise error.BASICError(error.BAD_FILE_MODE)

    def do_print(self):
        """Actually print, reset column position."""
        with safe_io():
            self._fhandle.flush()
        self._settings.col = 1
        self.col = 1

    def close(self):
        """Close the printer device and actually print the output."""
        self.do_print()


##############################################################################
# printers

class PrinterStream(io.BytesIO):
    """LPT output to printer."""

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

    def write(self, s):
        """Write to printer stream."""
        for c in iterchar(s):
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
        utf8buf = self.codepage.bytes_to_unicode(
            printbuf, preserve=CONTROL,
        ).encode('utf-8', 'replace')
        line_print(utf8buf, self.printer_name)

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""

    def get_status(self):
        """Get the values of the status pins."""
        return False, False, False, False, False


##############################################################################
# physical parallel ports

class ParallelStream(object):
    """LPT output to parallel port."""

    def __init__(self, port):
        """Initialise the ParallelStream."""
        if not parallel:
            raise IOError('`parallel` module not found. Parallel port communication not available.')
        try:
            self._parallel = parallel.Parallel(port)
        except TypeError:
            raise IOError('Invalid port specification.')
        self._port = port

    def __getstate__(self):
        """Get pickling dict for stream."""
        return {'port': self._port}

    def __setstate__(self, st):
        """Initialise stream from pickling dict."""
        self.__init__(st['port'])

    def write(self, s):
        """Write to the parallel port."""
        with safe_io():
            if self._parallel.getInPaperOut():
                raise error.BASICError(error.OUT_OF_PAPER)
            for c in iterchar(s):
                self._parallel.setData(ord(c))

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""
        with safe_io():
            self._parallel.setDataStrobe(strobe)
            self._parallel.setAutoFeed(lf)
            self._parallel.setInitOut(init)
            # select-printer pin not implemented

    def get_status(self):
        """Get the values of the status pins."""
        with safe_io():
            paper = self._parallel.getInPaperOut()
            ack = self._parallel.getInAcknowledge()
            select = self._parallel.getInSelected()
        # not implemented: busy, error pins
        busy = False
        err = False
        return busy, ack, paper, select, err

    def close(self):
        """Close the stream."""
        pass


##############################################################################
# standard output

class StdIOParallelStream(object):
    """LPT output to standard output."""

    def __init__(self):
        """Initialise the stream."""

    def close(self):
        """Close the connection."""

    def write(self, s):
        """Write to stdout."""
        stdio.stdout.buffer.write(s)
        self.flush()

    def flush(self):
        """Flush stdout."""
        stdio.stdout.flush()

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""

    def get_status(self):
        """Get the values of the status pins."""
        return False, False, False, False, False
