"""
PC-BASIC - ports.py
Serial port handling

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import os
import datetime
import io
from contextlib import contextmanager

from ...compat import iteritems
from ...compat import console, stdio

from .devicebase import safe_io

try:
    import serial
    # use the old VERSION constant as __version__ not defined in v2
    if serial.VERSION < '3':
        raise ImportError('PySerial version %s found but >= 3.0.0 required.' % serial.VERSION)
    from serial import serialutil
    logging_msg = ''
except Exception as e:
    serial = None
    logging_msg = str(e)

from ..base import error
from .. import values
from .devicebase import Device, DeviceSettings, TextFileBase, RealTimeInputMixin
from .devicebase import parse_protocol_string


###############################################################################
# COM ports

class COMDevice(Device):
    """Serial port device (COMn:)."""

    allowed_modes = b'IOAR'

    def __init__(self, arg, queues, serial_in_size):
        """Initialise COMn: device."""
        Device.__init__(self)
        # for wait()
        self._queues = queues
        self._serial_in_size = serial_in_size
        self._spec = arg
        self._serial = self._init_serial(arg)
        self.device_file = DeviceSettings()
        # only one file open at a time
        self._file = None

    def open(self, number, param, filetype, mode, access, lock, reclen, seg, offset, length, field):
        """Open a file on COMn: """
        if not self._serial:
            raise error.BASICError(error.DEVICE_UNAVAILABLE)
        # PE setting not implemented
        speed, parity, bytesize, stop, rs, cs, ds, cd, lf, _ = self._parse_params(param)
        # open the COM port
        if self._file and self._file.is_open:
            raise error.BASICError(error.FILE_ALREADY_OPEN)
        else:
            self._open_serial(rs, cs, ds, cd)
        try:
            self.set_params(speed, parity, bytesize, stop)
        except Exception:
            self.close()
            raise
        self._file = COMFile(self._serial, field, lf, self._serial_in_size, self._queues)
        # inherit width settings from device file
        # note that these seem unused for COM files
        self._file.width = self.device_file.width
        self._file.col = self.device_file.col
        return self._file

    def available(self):
        """Device is available."""
        return self._serial is not None

    def _parse_params(self, param):
        """Parse serial port connection parameters """
        max_param = 10
        param_list = param.upper().split(b',')
        if len(param_list) > max_param:
            raise error.BASICError(error.BAD_FILE_NAME)
        param_list += [b''] * (max_param-len(param_list))
        speed, parity, data, stop = param_list[:4]
        # set speed
        if speed not in (
                b'75', b'110', b'150', b'300', b'600', b'1200',
                b'1800', b'2400', b'4800', b'9600', b''
            ):
            # Bad file name
            raise error.BASICError(error.BAD_FILE_NAME)
        speed = int(speed) if speed else 300
        # set parity
        if parity not in (b'S', b'M', b'O', b'E', b'N', b''):
            raise error.BASICError(error.BAD_FILE_NAME)
        parity = parity or b'E'
        # set data bits
        if data not in (b'4', b'5', b'6', b'7', b'8', b''):
            raise error.BASICError(error.BAD_FILE_NAME)
        data = int(data) if data else 7
        bytesize = data + (parity != b'N')
        if bytesize not in range(5, 9):
            raise error.BASICError(error.BAD_FILE_NAME)
        # set stopbits
        if stop not in (b'1', b'2', b''):
            raise error.BASICError(error.BAD_FILE_NAME)
        if not stop:
            stop = 2 if (speed in (75, 110)) else 1
        else:
            stop = int(stop)
        lf, rs, cs, ds, cd, pe = False, False, None, 1000, 0, False
        for named_param in param_list[4:]:
            if not named_param:
                continue
            try:
                if named_param == b'RS':
                    # suppress request to send
                    rs = True
                elif named_param[:2] == b'CS':
                    # set CTS timeout - clear to send
                    # 0 for empty string; BAD FILE NAME if not numeric
                    cs = int(named_param[2:]) if named_param[2:] else 0
                elif named_param[:2] == b'DS':
                    # set DSR timeout - data set ready
                    ds = int(named_param[2:]) if named_param[2:] else 0
                elif named_param[:2] == b'CD':
                    # set CD timeout - carrier detect
                    cd = int(named_param[2:]) if named_param[2:] else 0
                elif named_param == b'LF':
                    # send a line feed at each return
                    lf = True
                elif named_param == b'PE':
                    # enable parity checking
                    # not implemented
                    pe = True
                else:
                    raise error.BASICError(error.BAD_FILE_NAME)
            except ValueError:
                raise error.BASICError(error.BAD_FILE_NAME)
        # CS default depends on RS
        if cs is None:
            cs = 1000 if not rs else 0
        return speed, parity, bytesize, stop, rs, cs, ds, cd, lf, pe

    def char_waiting(self):
        """Whether a char is present in buffer. For ON COM(n)."""
        if not self._serial:
            return False
        with safe_io():
            # ON COM can be set without any OPEN statement
            # so we need to ensure the serial port is opened before querying it
            if not self._serial.is_open:
                self._serial.open()
            return self._serial.in_waiting

    ##########################################################################

    def _init_serial(self, spec):
        """Initialise the serial object."""
        addr, val = parse_protocol_string(spec)
        try:
            if not addr and not val:
                pass
            elif addr == u'STDIO' or (not addr and val.upper() == u'STDIO'):
                return SerialStdIO(val.upper() == u'CRLF')
            else:
                if not serial:
                    logging.warning(
                        u'Could not attach %s to COM device. Module `serial` not available: %s',
                        spec, logging_msg
                    )
                    return None
                if addr in (u'SOCKET', u'RFC2217'):
                    # throws ValueError if too many :s, caught below
                    host, socket = val.split(u':')
                    url = u'%s://%s:%s' % (addr.lower(), host, socket)
                    stream = serial.serial_for_url(url, timeout=0, do_not_open=True)
                    # monkey-patch serial object as SocketSerial does not have this property
                    stream.out_waiting = 0
                    return stream
                elif addr == u'PORT':
                    # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows.
                    return serial.serial_for_url(val, timeout=0, do_not_open=True)
                else:
                    raise ValueError(u'Invalid protocol `%s`' % (addr,))
        except (ValueError, EnvironmentError) as e:
            logging.warning(u'Could not attach %s to COM device: %s', spec, e)
        return None

    def __getstate__(self):
        """Get pickling dict for stream."""
        # copy as we still need _serial for close()
        # which gets called after __getstate__() on shutdown
        pickle_dict = {k:v for k,v in iteritems(self.__dict__)}
        del pickle_dict['_serial']
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Initialise stream from pickling dict."""
        self.__dict__.update(pickle_dict)
        self._serial = self._init_serial(self._spec)

    def _check_open(self):
        """Open the underlying port if necessary."""
        if not self._serial.is_open:
            logging.debug('Opening serial port %s.', self._serial.port)
            self._serial.open()

    def _open_serial(self, rs=False, cs=1000, ds=1000, cd=0):
        """Open the serial connection."""
        with safe_io(error.DEVICE_TIMEOUT):
            self._check_open()
        # handshake - report as timeout if it fails
        # by default, RTS is up, DTR down
        # RTS can be suppressed, DTR only accessible through machine ports
        # https://lbpe.wikispaces.com/AccessingSerialPort
        if not rs:
            with safe_io(error.DEVICE_TIMEOUT):
                self._serial.rts = True
        now = datetime.datetime.now()
        timeout_cts = now + datetime.timedelta(microseconds=cs)
        timeout_dsr = now + datetime.timedelta(microseconds=ds)
        timeout_cd = now + datetime.timedelta(microseconds=cd)
        with safe_io(error.DEVICE_TIMEOUT):
            have_cts, have_dsr, have_cd = self._serial.cts, self._serial.dsr, self._serial.cd
        while ((now < timeout_cts and not have_cts) and
                (now < timeout_dsr and not have_dsr) and
                (now < timeout_cd and not have_cd)):
            now = datetime.datetime.now()
            with safe_io(error.DEVICE_TIMEOUT):
                have_cts = have_cts and self._serial.cts
                have_dsr = have_dsr and self._serial.dsr
                have_cts = have_cd and self._serial.cd
            # give CPU some time off
            self._queues.wait()
        # only check for status if timeouts are set > 0
        # http://www.electro-tech-online.com/threads/qbasic-serial-port-control.19286/
        # https://measurementsensors.honeywell.com/ProductDocuments/Instruments/008-0385-00.pdf
        if ((cs > 0 and not have_cts) or
                (ds > 0 and not have_dsr) or
                (cd > 0 and not have_cd)):
            raise error.BASICError(error.DEVICE_TIMEOUT)

    def set_params(self, speed, parity, bytesize, stop):
        """Set serial port connection parameters."""
        logging.debug(
            'Setting serial port %s parameters to (%d, %s, %s, %s).',
            self._serial.port, speed, parity, bytesize, stop
        )
        with safe_io(error.DEVICE_FAULT):
            self._check_open()
            self._serial.baudrate = speed
            self._serial.parity = parity.decode('ascii')
            self._serial.bytesize = bytesize
            self._serial.stopbits = stop

    def get_params(self):
        """Get serial port connection parameters."""
        with safe_io(error.DEVICE_FAULT):
            self._check_open()
            return (
                self._serial.baudrate, self._serial.parity.encode('ascii'),
                self._serial.bytesize, self._serial.stopbits
            )

    def set_pins(self, rts=None, dtr=None, brk=None):
        """Set signal pins."""
        with safe_io(error.DEVICE_FAULT):
            self._check_open()
            if rts is not None:
                self._serial.rts = rts
            if dtr is not None:
                self._serial.dtr = dtr
            if brk is not None:
                self._serial.break_condition = brk

    def get_pins(self):
        """Get signal pins."""
        with safe_io(error.DEVICE_FAULT):
            self._check_open()
            return (self._serial.cd, self._serial.ri,
                    self._serial.dsr, self._serial.cts)

    def close(self):
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            logging.debug('Closing serial port %s.', self._serial.port)
            self._serial.close()

    def io_waiting(self):
        """ Find out whether bytes are waiting for input or output. """
        # no idea what the appropriate BASIC error would be
        with safe_io(error.DEVICE_FAULT):
            self._check_open()
            # socketserial has no out_waiting, though Serial does
            return self._serial.in_waiting > 0, self._serial.out_waiting > 0


###############################################################################

class COMFile(TextFileBase, RealTimeInputMixin):
    """COMn: device - serial port."""

    def __init__(self, stream, field, linefeed, serial_in_size, queues):
        """Initialise COMn: file."""
        TextFileBase.__init__(self, stream, b'D', b'R')
        self._queues = queues
        # create a FIELD for GET and PUT. no text file operations on COMn: FIELD
        self._field = field
        self._linefeed = linefeed
        self._serial_in_size = serial_in_size
        self.is_open = True

    def close(self):
        """Close the file (but not the port)."""
        # do *not* call the parent close()
        # as this would call close() on our (unique) serial file handle
        #TextFileBase.close(self)
        self.is_open = False

    def peek(self, num):
        """Return only readahead buffer, no blocking peek."""
        return b''.join(self._readahead[:num])

    def read(self, num):
        """Read a number of characters."""
        # take at most num chars out of readahead buffer (holds just one on COM but anyway)
        s, self._readahead = self._readahead[:num], self._readahead[num:]
        while len(s) < num:
            self._queues.wait()
            with safe_io():
                # non-blocking read
                self._current, self._previous = self._fhandle.read(1), self._current
            if self._current:
                s.append(self._current)
        logging.debug('Reading from serial port %s: %r', self._fhandle.port, b''.join(s))
        return b''.join(s)

    def read_one(self):
        """Read a character, replacing CR LF with CR."""
        c = self.read(1)
        # report CRLF as CR
        # are we correct to ignore self._linefeed on input?
        if (c == b'\n' and self._previous == b'\r'):
            c = self.read(1)
        return c

    def read_line(self):
        """Blocking read line from the port (not the FIELD buffer!)."""
        out = []
        while len(out) < 255:
            c = self.read_one()
            if c == b'\r':
                break
            if c:
                out.append(c)
            c = None
        return b''.join(out), c

    def write_line(self, s=b''):
        """Write string or bytearray and newline to port."""
        self.write(s + b'\r')

    def write(self, s):
        """Write string to port."""
        if self._linefeed:
            s = s.replace(b'\r', b'\r\n')
        with safe_io():
            logging.debug('Writing to serial port %s: %r', self._fhandle.port, s)
            self._fhandle.write(s)

    def get(self, num):
        """Read num bytes - GET on COM port."""
        if not num:
            return
        # blocking read of num bytes
        s = self.read(num)
        self._field.view_buffer()[:len(s)] = s

    def put(self, num):
        """Write num bytes - PUT on COM port."""
        if not num:
            return
        self.write(bytes(self._field.view_buffer()[:num]))

    def loc(self):
        """LOC: Returns number of chars waiting to be read."""
        with safe_io():
            return self._fhandle.in_waiting

    def eof(self):
        """EOF: no chars waiting."""
        # for EOF(i)
        return self.loc() <= 0

    def lof(self):
        """Returns number of bytes free in buffer."""
        with safe_io():
            return max(0, self._serial_in_size - self._fhandle.in_waiting)


###############################################################################

class SerialStdIO(object):
    """Wrapper object to route port to stdio."""

    # dummy input pins
    cd = True
    ri = False
    dsr = True
    cts = True

    def __init__(self, crlf):
        """Initialise the stream."""
        self.is_open = False
        self._crlf = crlf
        # dummy parameters
        self.baudrate = 300
        self.parity = 'E'
        self.bytesize = 8
        self.stopbits = 2
        # dummy output pins
        self.rts = False
        self.dtr = False
        self.break_condition = False
        self.port = u'STDIO'

    def open(self):
        """Open a connection."""
        self.is_open = True

    def close(self):
        """Close the connection."""
        self.is_open = False

    def read(self, num=1):
        """Non-blocking read of up to `num` chars from stdin."""
        s = []
        # note that kbhit assumes keyboard
        # so won't work with redirects on Windows
        while console.key_pressed() and len(s) < num:
            c = stdio.stdin.buffer.read(1)
            if self._crlf and c == b'\n':
                c = b'\r'
            if c:
                s.append(c)
        return b''.join(s)

    def write(self, s):
        """Write to stdout."""
        if self._crlf:
            s = s.replace(b'\r', b'\n')
        stdio.stdout.buffer.write(s)
        stdio.stdout.buffer.flush()

    @property
    def in_waiting(self):
        """Number of characters waiting to be read."""
        # we get at most 1 char waiting this way
        return console.key_pressed()

    out_waiting = 0
