"""
PC-BASIC - ports.py
Serial port handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import sys
import os
import datetime
import platform
import io

# kbhit() also appears in video_none.py
if platform.system() == 'Windows':
    from msvcrt import kbhit
else:
    import select

    def kbhit():
        """Return whether a character is ready to be read from the keyboard."""
        return select.select([sys.stdin], [], [], 0)[0] != []

try:
    import serial
    # use the old VERSION constant as __version__ not defined in v2
    if serial.VERSION < '3':
        logging.warning('PySerial version %s found but >= 3.0.0 required.')
        raise ImportError
    from serial import SerialException, serialutil
except Exception:
    serial = None
    SerialException = IOError

from .base import error
from . import devices


###############################################################################
# COM ports

class COMDevice(devices.Device):
    """Serial port device (COMn:)."""

    allowed_modes = 'IOAR'

    def __init__(self, arg, input_methods, serial_in_size):
        """Initialise COMn: device."""
        devices.Device.__init__(self)
        addr, val = devices.parse_protocol_string(arg)
        self.stream = None
        self.input_methods = input_methods
        self._serial_in_size = serial_in_size
        try:
            if not addr and not val:
                pass
            elif addr == 'STDIO' or (not addr and val.upper() == 'STDIO'):
                crlf = (val.upper() == 'CRLF')
                self.stream = StdIOSerialStream(input_methods, crlf)
            elif addr == 'SOCKET':
                # throws ValueError if too many :s, caught below
                host, socket = val.split(':')
                self.stream = SerialStream('socket://%s:%s' % (host, socket), self.input_methods, do_open=False)
            elif addr == 'PORT':
                # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows.
                self.stream = SerialStream(val, self.input_methods, do_open=False)
            else:
                logging.warning('Could not attach %s to COM device', arg)
        except (ValueError, EnvironmentError) as e:
            logging.warning('Could not attach %s to COM device: %s', arg, e)
        except AttributeError:
            logging.warning('Serial module not available. Could not attach %s to COM device: %s.', arg, e)
        self.device_file = devices.DeviceSettings()

    def open(self, number, param, filetype, mode, access, lock,
                       reclen, seg, offset, length, field):
        """Open a file on COMn: """
        if not self.stream:
            raise error.BASICError(error.DEVICE_UNAVAILABLE)
        # PE setting not implemented
        speed, parity, bytesize, stop, rs, cs, ds, cd, lf, _ = self.get_params(param)
        # open the COM port
        if self.stream.is_open:
            raise error.BASICError(error.FILE_ALREADY_OPEN)
        else:
            try:
                self.stream.open(rs, cs, ds, cd)
            except EnvironmentError as e:
                # device timeout
                logging.debug("Serial exception: %s", e)
                raise error.BASICError(error.DEVICE_TIMEOUT)
        try:
            self.stream.set_params(speed, parity, bytesize, stop)
        except Exception:
            self.stream.close()
            raise
        f = COMFile(self.stream, field, lf, self._serial_in_size)
        # inherit width settings from device file
        f.width = self.device_file.width
        # FIXME: is this ever anything but 1? what uses it? on LPT it's LPOS, but on COM?
        f.col = self.device_file.col
        return f

    def available(self):
        """Device is available."""
        return self.stream is not None

    def get_params(self, param):
        """Parse serial port connection parameters """
        max_param = 10
        param_list = param.upper().split(',')
        if len(param_list) > max_param:
            raise error.BASICError(error.BAD_FILE_NAME)
        param_list += [''] * (max_param-len(param_list))
        speed, parity, data, stop = param_list[:4]
        # set speed
        if speed not in ('75', '110', '150', '300', '600', '1200',
                          '1800', '2400', '4800', '9600', ''):
            # Bad file name
            raise error.BASICError(error.BAD_FILE_NAME)
        speed = int(speed) if speed else 300
        # set parity
        if parity not in ('S', 'M', 'O', 'E', 'N', ''):
            raise error.BASICError(error.BAD_FILE_NAME)
        parity = parity or 'E'
        # set data bits
        if data not in ('4', '5', '6', '7', '8', ''):
            raise error.BASICError(error.BAD_FILE_NAME)
        data = int(data) if data else 7
        bytesize = data + (parity != 'N')
        if bytesize not in range(5, 9):
            raise error.BASICError(error.BAD_FILE_NAME)
        # set stopbits
        if stop not in ('1', '2', ''):
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
                if named_param == 'RS':
                    # suppress request to send
                    rs = True
                elif named_param[:2] == 'CS':
                    # set CTS timeout - clear to send
                    # 0 for empty string; BAD FILE NAME if not numeric
                    cs = int(named_param[2:]) if named_param[2:] else 0
                elif named_param[:2] == 'DS':
                    # set DSR timeout - data set ready
                    ds = int(named_param[2:]) if named_param[2:] else 0
                elif named_param[:2] == 'CD':
                    # set CD timeout - carrier detect
                    cd = int(named_param[2:]) if named_param[2:] else 0
                elif named_param == 'LF':
                    # send a line feed at each return
                    lf = True
                elif named_param == 'PE':
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
        return self.stream and self.stream.in_waiting


class COMFile(devices.TextFileBase):
    """COMn: device - serial port."""

    def __init__(self, stream, field, linefeed, serial_in_size):
        """Initialise COMn: file."""
        # prevent readahead by providing non-empty first char
        # we're ignoring self.char and self.next_char in this class
        devices.TextFileBase.__init__(self, stream, b'D', b'R', first_char=b'DUMMY')
        # create a FIELD for GET and PUT. no text file operations on COMn: FIELD
        self._field = field
        self._linefeed = linefeed
        self._serial_in_size = serial_in_size
        # buffer for the separator character that broke the last INPUT# field
        # to be attached to the next
        self._input_last = b''

    def read_raw(self, num=-1):
        """Read num characters as string."""
        s, c = [], b''
        while not (num > -1 and len(s) >= num):
            c, self.last = self.fhandle.read(1), c
            s.append(c)
        return b''.join(s)

    def read(self, num=-1):
        """Read num characters, replacing CR LF with CR."""
        s = []
        while len(s) < num:
            c = self.read_raw(1)
            if not c:
                break
            s.append(c)
            # report CRLF as CR
            # are we correct to ignore self._linefeed on input?
            if (c == b'\n' and self.last == b'\r'):
                c = self.read_raw(1)
        return b''.join(s)

    def read_line(self):
        """Blocking read line from the port (not the FIELD buffer!)."""
        out = []
        while len(out) < 255:
            c = self.read(1)
            if c == b'\r':
                break
            out.append(c)
        return ''.join(c)

    def write_line(self, s=''):
        """Write string or bytearray and newline to port."""
        self.write(bytes(s) + b'\r')

    def write(self, s):
        """Write string to port."""
        try:
            if self._linefeed:
                s = s.replace(b'\r', b'\r\n')
            self.fhandle.write(s)
        except (EnvironmentError, ValueError) as e:
            raise error.BASICError(error.DEVICE_IO_ERROR)

    def get(self, num):
        """Read a record - GET."""
        # blocking read of num bytes
        s = self.read(num)
        self._field.buffer[:len(s)] = s

    def put(self, num):
        """Write a record - PUT."""
        self.write(self._field.buffer[:num])

    def loc(self):
        """LOC: Returns number of chars waiting to be read."""
        return self.fhandle.in_waiting

    def eof(self):
        """EOF: no chars waiting."""
        # for EOF(i)
        return self.loc() <= 0

    def lof(self):
        """Returns number of bytes free in buffer."""
        return max(0, self._serial_in_size - self.fhandle.in_waiting)

    # use real-time INPUT handling
    input_entry = devices.KYBDFile.input_entry


class SerialStream(object):
    """Wrapper object for Serial to enable pickling."""

    def __init__(self, port, input_methods, do_open):
        """Initialise the stream."""
        self._serial = serial.serial_for_url(port, timeout=0, do_not_open=not do_open)
        # monkey-patch serial object as SocketSerial does not have this property
        if not hasattr(self._serial, 'out_waiting'):
            self._serial.out_waiting = 0
        # for wait()
        self._input_methods = input_methods
        self._url = port
        self.is_open = False

    def __getstate__(self):
        """Get pickling dict for stream."""
        return {'input_methods': self._input_methods, 'url': self._url, 'is_open': self.is_open}

    def __setstate__(self, st):
        """Initialise stream from pickling dict."""
        try:
            SerialStream.__init__(self, st['url'], st['input_methods'], st['is_open'])
        except (EnvironmentError, ValueError) as e:
            logging.warning('Could not resume serial connection: %s', e)
            self.__init__(st['url'], st['input_methods'], False)
            self.is_open = False

    def _check_open(self):
        """Open the underlying port if necessary."""
        if not self._serial.is_open:
            self._serial.open()

    def open(self, rs=False, cs=1000, ds=1000, cd=0):
        """Open the serial connection."""
        self._check_open()
        # handshake
        # by default, RTS is up, DTR down
        # RTS can be suppressed, DTR only accessible through machine ports
        # https://lbpe.wikispaces.com/AccessingSerialPort
        if not rs:
            self._serial.rts = True
        now = datetime.datetime.now()
        timeout_cts = now + datetime.timedelta(microseconds=cs)
        timeout_dsr = now + datetime.timedelta(microseconds=ds)
        timeout_cd = now + datetime.timedelta(microseconds=cd)
        have_cts, have_dsr, have_cd = False, False, False
        while ((now < timeout_cts and not have_cts) and
                (now < timeout_dsr and not have_dsr) and
                (now < timeout_cd and not have_cd)):
            now = datetime.datetime.now()
            have_cts = have_cts and self._serial.cts
            have_dsr = have_dsr and self._serial.dsr
            have_cts = have_cd and self._serial.cd
            # give CPU some time off
            self._input_methods.wait()
        # only check for status if timeouts are set > 0
        # http://www.electro-tech-online.com/threads/qbasic-serial-port-control.19286/
        # https://measurementsensors.honeywell.com/ProductDocuments/Instruments/008-0385-00.pdf
        if ((cs > 0 and not have_cts) or
                (ds > 0 and not have_dsr) or
                (cd > 0 and not have_cd)):
            raise error.BASICError(error.DEVICE_TIMEOUT)
        self.is_open = True

    def set_params(self, speed, parity, bytesize, stop):
        """Set serial port connection parameters."""
        self._check_open()
        self._serial.baudrate = speed
        self._serial.parity = parity
        self._serial.bytesize = bytesize
        self._serial.stopbits = stop

    def get_params(self):
        """Get serial port connection parameters."""
        self._check_open()
        return (self._serial.baudrate, self._serial.parity,
                self._serial.bytesize, self._serial.stopbits)

    def set_pins(self, rts=None, dtr=None, brk=None):
        """Set signal pins."""
        self._check_open()
        if rts is not None:
            self._serial.rts = rts
        if dtr is not None:
            self._serial.dtr = dtr
        if brk is not None:
            self._serial.break_condition = brk

    def get_pins(self):
        """Get signal pins."""
        self._check_open()
        return (self._serial.cd, self._serial.ri,
                self._serial.dsr, self._serial.cts)

    def close(self):
        """Close the serial connection."""
        self._serial.close()
        self.is_open = False

    def flush(self):
        """No buffer to flush."""
        pass

    def read(self, num=1):
        """Non-blocking read from socket."""
        self._check_open()
        self._input_methods.wait()
        # NOTE: num=1 follows PySerial
        # stream default is num=-1 to mean all available
        # but that's ill-defined for ports
        return self._serial.read(num)

    def write(self, s):
        """Write to socket."""
        self._check_open()
        self._serial.write(s)

    def io_waiting(self):
        """ Find out whether bytes are waiting for input or output. """
        self._check_open()
        # socketserial has no out_waiting, though Serial does
        return self._serial.in_waiting > 0, self._serial.out_waiting > 0

    @property
    def in_waiting(self):
        return self._serial.in_waiting

    @property
    def out_waiting(self):
        return self._serial.out_waiting


class StdIOSerialStream(object):
    """Wrapper object to route port to stdio."""

    def __init__(self, input_methods, crlf):
        """Initialise the stream."""
        self.is_open = False
        self._crlf = crlf
        self._input_methods = input_methods

    def open(self, rs=False, cs=1000, ds=1000, cd=0):
        """Open a connection."""
        self.is_open = True

    def close(self):
        """Close the connection."""
        self.is_open = False

    def read(self, num=1):
        """Non-blocking read of up to `num` chars from stdin."""
        s = ''
        while kbhit() and len(s) < num:
            c = sys.stdin.read(1)
            if self._crlf and c == '\n':
                c = '\r'
            s += c
        self._input_methods.wait()
        return s

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

    def set_params(self, speed, parity, bytesize, stop):
        """Set serial port connection parameters """

    def get_params(self):
        """Get serial port connection parameters """
        return 300, 'E', 8, 2

    def set_pins(self, rts=None, dtr=None, brk=None):
        """Set signal pins."""

    def get_pins(self):
        """Get signal pins."""
        return False, False, False, False

    def io_waiting(self):
        """ Find out whether bytes are waiting for input or output. """
        return kbhit(), False

    @property
    def in_waiting(self):
        """Number of characters waiting to be read."""
        # we get at most 1 char waiting this way
        return kbhit()

    out_waiting = False
