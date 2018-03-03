"""
PC-BASIC - parports.py
Parallel port handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import platform
import io

try:
    import parallel
except Exception:
    parallel = None

# kbhit() also appears in video_none.py
if platform.system() == 'Windows':
    from msvcrt import kbhit
else:
    import select

    def kbhit():
        """Return whether a character is ready to be read from the keyboard."""
        return select.select([sys.stdin], [], [], 0)[0] != []

from ..base import error
from . import devicebase
from . import printer


###############################################################################
# LPT ports

class LPTDevice(devicebase.Device):
    """Parallel port or printer device (LPTn:) """

    # LPT1 can be opened as RANDOM
    # but behaves just like OUTPUT
    # in GW-BASIC, FIELD gives a FIELD OVERFLOW; we get BAD FILE MODE.
    allowed_modes = 'OR'

    def __init__(self, arg, default_stream, codepage, temp_dir):
        """Initialise LPTn: device."""
        devicebase.Device.__init__(self)
        addr, val = devicebase.parse_protocol_string(arg)
        self.stream = default_stream
        if addr == 'FILE':
            try:
                self.stream = open(val, 'wb')
            except EnvironmentError as e:
                logging.warning('Could not attach file %s to LPT device: %s', val, str(e))
        elif addr == 'PARPORT':
            # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
            try:
                self.stream = ParallelStream(val)
            except EnvironmentError as e:
                logging.warning('Could not attach parallel port %s to LPT device: %s', val, str(e))
        elif addr == 'STDIO' or (not addr and val == 'STDIO'):
            crlf = (val.upper() == 'CRLF')
            self.stream = StdIOParallelStream(crlf)
        elif addr == 'PRINTER' or (val and not addr):
            # 'PRINTER' is default
            # name:parameters (LINE, PAGE, ...)
            self.stream = printer.get_printer_stream(val, codepage, temp_dir)
        elif val:
            logging.warning('Could not attach %s to LPT device', arg)
        if self.stream:
            self.device_file = LPTFile(self.stream)

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """Open a file on LPTn: """
        # don't trigger flushes on LPT files, just on the device directly
        f = LPTFile(self.stream, 'close')
        # inherit width settings from device file
        f.width = self.device_file.width
        f.col = self.device_file.col
        return f

    def available(self):
        """Device is available."""
        return self.stream is not None


class LPTFile(devicebase.TextFileBase):
    """LPTn: device - line printer or parallel port."""

    def __init__(self, stream, filetype='D'):
        """Initialise LPTn."""
        devicebase.TextFileBase.__init__(self, stream, filetype, mode='A')
        # width=255 means line wrap
        self.width = 255
        self.col = 1

    def flush(self):
        """Flush the buffer to the underlying stream."""

    def write(self, s, can_break=True):
        """Write a string to the printer buffer."""
        for c in bytes(s):
            # width 255 means wrapping enabled
            if can_break and self.col >= self.width and self.width != 255:
                self.fhandle.write(b'\r\n')
                self.col = 1
            # don't replace CR or LF with CRLF
            self.fhandle.write(c)
            if c in (b'\n', b'\r', b'\f'):
                self.col = 1
            elif c == b'\b':
                if self.col > 1:
                    self.col -= 1
            else:
                # nonprinting characters including tabs are not counted for LPOS
                if ord(c) >= 32:
                    self.col += 1

    def write_line(self, s=b''):
        """Write string or bytearray and newline to file."""
        self.write(bytes(s) + b'\r\n')

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
        self.fhandle.flush()
        self.col = 1

    def close(self):
        """Close the printer device and actually print the output."""
        self.do_print()


class ParallelStream(object):
    """Wrapper for Parallel object to implement stream-like API."""

    def __init__(self, port):
        """Initialise the ParallelStream."""
        if not parallel:
            raise IOError('PySerial Parallel module not found. Parallel port communication not available.')
        try:
            self._parallel = parallel.Parallel(port)
        except TypeError:
            raise IOError('Invalid port specification.')
        self._port = port

    def __getstate__(self):
        """Get pickling dict for stream."""
        return { 'port': self._port }

    def __setstate__(self, st):
        """Initialise stream from pickling dict."""
        self.__init__(st['port'])

    def flush(self):
        """No buffer to flush."""
        pass

    def write(self, s):
        """Write to the parallel port."""
        if self._parallel.getInPaperOut():
            raise error.BASICError(error.OUT_OF_PAPER)
        for c in s:
            self._parallel.setData(ord(c))

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""
        self._parallel.setDataStrobe(strobe)
        self._parallel.setAutoFeed(lf)
        self._parallel.setInitOut(init)
        # select-printer pin not implemented

    def get_status(self):
        """Get the values of the status pins."""
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


class StdIOParallelStream(object):
    """Wrapper object to route port to stdio."""

    def __init__(self, crlf=False):
        """Initialise the stream."""
        self._crlf = crlf

    def close(self):
        """Close the connection."""

    def write(self, s):
        """Write to stdout."""
        for c in s:
            if self._crlf and c == '\r':
                c = '\n'
            sys.stdout.write(c)
        self.flush()

    def flush(self):
        """Flush stdout."""
        sys.stdout.flush()

    def set_control(self, select=False, init=False, lf=False, strobe=False):
        """Set the values of the control pins."""

    def get_status(self):
        """Get the values of the status pins."""
        return False, False, False, False, False
