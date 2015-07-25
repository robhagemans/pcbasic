"""
PC-BASIC - ports.py
Serial and parallel port handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.

SocketSerialWrapper.read is modelled on Python 2.7 licensed code from PySerial
PySerial (c) 2001-2013 Chris Liechtl <cliechti(at)gmx.net>; All Rights Reserved.
"""

import logging
import os
import socket

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import serial
    from serial import SerialException, serialutil
except Exception:
    serial = None
    SerialException = IOError

try:
    import parallel
except Exception:
    parallel = None

import config
import error
import backend
import devices
import printer


# buffer sizes (/c switch in GW-BASIC)
serial_in_size = 256
serial_out_size = 128

# maximum record length (-s)
max_reclen = 128

def prepare():
    # parallel devices - LPT1: must always be defined
    print_trigger = config.options['print-trigger']
    backend.devices['LPT1:'] = LPTDevice(config.options['lpt1'], devices.nullstream, print_trigger)
    backend.devices['LPT2:'] = LPTDevice(config.options['lpt2'], None, print_trigger)
    backend.devices['LPT3:'] = LPTDevice(config.options['lpt3'], None, print_trigger)
    backend.lpt1_file = backend.devices['LPT1:'].device_file
    # serial devices
    global max_reclen, serial_in_size
    if config.options['max-reclen'] != None:
        max_reclen = config.options['max-reclen']
        max_reclen = max(1, min(32767, max_reclen))
    if config.options['serial-buffer-size'] != None:
        serial_in_size = config.options['serial-buffer-size']
    backend.devices['COM1:'] = COMDevice(config.options['com1'], max_reclen, serial_in_size)
    backend.devices['COM2:'] = COMDevice(config.options['com2'], max_reclen, serial_in_size)


###############################################################################
# COM ports

class COMDevice(devices.Device):
    """ Serial port device (COMn:). """

    allowed_protocols = ('PORT', 'SOCKET')
    allowed_modes = 'IOAR'

    def __init__(self, arg, max_reclen, serial_in_size):
        """ Initialise COMn: device. """
        devices.Device.__init__(self)
        addr, val = devices.parse_protocol_string(arg)
        self.stream = None
        if (not val):
            pass
        elif (addr and addr not in self.allowed_protocols):
            logging.warning('Could not attach %s to COM device', arg)
        elif addr == 'SOCKET':
            self.stream = serial_for_url('socket://'+val)
        else:
            # 'PORT' is default
            # port can be e.g. /dev/ttyS1 on Linux or COM1 on Windows. Or anything supported by serial_for_url (RFC 2217 etc)
            self.stream = serial_for_url(val)
        # wait until socket is open to open file on it
        # as opening a text file atomatically reads a byte
        self.device_file = None

    def open(self, number, param, filetype, mode, access, lock,
                       reclen, seg, offset, length):
        """ Open a file on COMn: """
        if not self.stream:
            # device unavailable
            raise error.RunError(68)
        # open the COM port
        if self.stream._isOpen:
            # file already open
            raise error.RunError(55)
        else:
            try:
                self.stream.open()
            except EnvironmentError as e:
                # device timeout
                logging.debug("Serial exception: %s", e)
                raise error.RunError(24)
        try:
            self.set_parameters(param)
        except Exception:
            self.stream.close()
            raise
        # only open file on socket once socket is open
        if not self.device_file:
            self.device_file = COMFile(self.stream)
        return devices.Device.open(self, number, param, filetype, mode, access, lock,
                            reclen, seg, offset, length)

    def set_parameters(self, param):
        """ Set serial port connection parameters """
        max_param = 10
        param_list = param.upper().split(',')
        if len(param_list) > max_param:
            # Bad file name
            raise error.RunError(64)
        param_list += ['']*(max_param-len(param_list))
        speed, parity, data, stop = param_list[:4]
        # set speed
        if speed not in ('75', '110', '150', '300', '600', '1200',
                          '1800', '2400', '4800', '9600', ''):
            # Bad file name
            raise error.RunError(64)
        speed = int(speed) if speed else 300
        self.stream.baudrate = speed
        # set parity
        if parity not in ('S', 'M', 'O', 'E', 'N', ''):
            raise error.RunError(64)
        parity = parity or 'E'
        self.stream.parity = parity
        # set data bits
        if data not in ('4', '5', '6', '7', '8', ''):
            raise error.RunError(64)
        data = int(data) if data else 7
        bytesize = data + (parity != 'N')
        if bytesize not in range(5, 9):
            raise error.RunError(64)
        self.stream.bytesize = bytesize
        # set stopbits
        if stop not in ('1', '2', ''):
            raise error.RunError(64)
        if not stop:
            stop = 2 if (speed in (75, 110)) else 1
        else:
            stop = int(stop)
        self.stream.stopbits = stop
        self.stream.linefeed = False
        for named_param in param_list[4:]:
            if not named_param:
                continue
            elif named_param == 'RS':
                # suppress request to send
                pass
            elif named_param[:2] == 'CS':
                # control CTS - clear to send
                pass
            elif named_param[:2] == 'DS':
                # control DSR - data set ready
                pass
            elif named_param[:2] == 'CD':
                # control CD - carrier detect
                pass
            elif named_param == 'LF':
                # send a line feed at each return
                self.stream.linefeed = True
            elif named_param == 'PE':
                # enable parity checking
                pass
            else:
                raise error.RunError(64)

    def char_waiting(self):
        """ Whether a char is present in buffer. For ON COM(n). """
        if not self.device_file:
            return False
        return self.device_file.in_buffer != ''


class COMFile(devices.CRLFTextFileBase):
    """ COMn: device - serial port. """

    def __init__(self, fhandle):
        """ Initialise COMn: file. """
        # note that for random files, fhandle must be a seekable stream.
        devices.CRLFTextFileBase.__init__(self, fhandle, 'D', 'R')
        # create a FIELD for GET and PUT. no text file operations on COMn: FIELD
        self.field = devices.Field(0)
        self.field.reset(serial_in_size)
        self.in_buffer = bytearray()
        self.linefeed = False

    def check_read(self):
        """ Fill buffer at most up to buffer size; non blocking. """
        try:
            self.in_buffer += self.fhandle.read(serial_in_size - len(self.in_buffer))
        except (EnvironmentError, ValueError):
            # device I/O
            raise error.RunError(57)

    def read_raw(self, num=-1):
        """ Read num characters from the port as a string; blocking """
        if num == -1:
            # read whole buffer, non-blocking
            self.check_read()
            out = self.in_buffer
            del self.in_buffer[:]
        else:
            out = ''
            while len(out) < num:
                # non blocking read
                self.check_read()
                to_read = min(len(self.in_buffer), num - len(out))
                out += str(self.in_buffer[:to_read])
                del self.in_buffer[:to_read]
                # allow for break & screen updates
                backend.wait()
        return out

    def read_line(self):
        """ Blocking read line from the port (not the FIELD buffer!). """
        out = bytearray('')
        while len(out) < 255:
            c = self.read(1)
            if c == '\r':
                if self.linefeed:
                    c = self.read(1)
                    if c == '\n':
                        break
                    out += ''.join(c)
                else:
                    break
            out += ''.join(c)
        return out

    def write_line(self, s=''):
        """ Write string or bytearray and newline to port. """
        self.write(str(s) + '\r')

    def write(self, s):
        """ Write string to port. """
        try:
            if self.linefeed:
                s = s.replace('\r', '\r\n')
            self.fhandle.write(s)
        except (EnvironmentError, ValueError):
            # device I/O
            raise error.RunError(57)

    def get(self, num):
        """ Read a record - GET. """
        # blocking read of num bytes
        self.field.buffer[:] = self.read(num)

    def put(self, num):
        """ Write a record - PUT. """
        self.write(self.field.buffer[:num])

    def loc(self):
        """ LOC: Returns number of chars waiting to be read. """
        # don't use inWaiting() as SocketSerial.inWaiting() returns dummy 0
        # fill up buffer insofar possible
        self.check_read()
        return len(self.in_buffer)

    def eof(self):
        """ EOF: no chars waiting. """
        # for EOF(i)
        return self.loc() <= 0

    def lof(self):
        """ Returns number of bytes free in buffer. """
        return serial_in_size - self.loc()


def serial_for_url(url):
    """ Return a Serial object for a given url. """
    if not serial:
        logging.warning('Serial module not found. Serial port and socket communication not available.')
        return None
    try:
        stream = serial.serial_for_url(url, timeout=0, do_not_open=True)
    except ValueError as e:
        return None
    if url.split(':', 1)[0] == 'socket':
        return SocketSerialWrapper(stream)
    else:
        return stream


class SocketSerialWrapper(object):
    """ Wrapper object for SocketSerial to work around timeout==0 issues. """

    def __init__(self, socketserial):
        """ initialise the wrapper. """
        self._serial = socketserial

    def read(self, num=1):
        """ Non-blocking read from socket. """
        # this is the raison d'etre of the wrapper.
        # SocketSerial.read always returns '' if timeout==0
        self._serial._socket.setblocking(0)
        if not self._serial._isOpen:
            raise serialutil.portNotOpenError
        try:
            # fill buffer at most up to buffer size
            return self._serial._socket.recv(num)
        except socket.timeout:
            return ''
        except socket.error as e:
            # a timeout in fact raises a socket.error 11
            # rather than a socket.timeout (at least on Linux)
            if e.errno == 11:
                return ''
            raise SerialException('connection failed (%s)' % e)

    # delegation doesn't play ball nicely with Pickle
    # def __getattr__(self, attr):
    #     return getattr(self._serial, attr)

    @property
    def _isOpen(self):
        return self._serial._isOpen

    def open(self):
        """ Open the serial connection. """
        self._serial.open()

    def close(self):
        """ Close the serial connection. """
        self._serial.close()

    def flush(self):
        """ No buffer to flush. """
        pass

    def write(self, s):
        """ Write to socket. """
        self._serial.write(s)


###############################################################################
# LPT ports

class LPTDevice(devices.Device):
    """ Parallel port or printer device (LPTn:) """

    allowed_protocols = ('PRINTER', 'PARPORT', 'FILE')
    allowed_modes = 'OR'

    def __init__(self, arg, default_stream, flush_trigger):
        """ Initialise LPTn: device. """
        devices.Device.__init__(self)
        addr, val = devices.parse_protocol_string(arg)
        self.stream = default_stream
        if (addr and addr not in self.allowed_protocols):
            logging.warning('Could not attach %s to LPT device', arg)
        elif addr == 'FILE':
            try:
                if not os.path.exists(val):
                    open(val, 'wb').close()
                self.stream = open(val, 'r+b')
            except (IOError, OSError) as e:
                logging.warning('Could not attach file %s to LPT device: %s', val, str(e))
        elif addr == 'PARPORT':
            # port can be e.g. /dev/parport0 on Linux or LPT1 on Windows. Just a number counting from 0 would also work.
           self.stream = parallel_port(val)
        else:
            # 'PRINTER' is default
            self.stream = printer.PrinterStream(val)
        if self.stream:
            self.device_file = LPTFile(self.stream, flush_trigger)
            self.device_file.flush_trigger = flush_trigger

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on LPTn: """
        # don't trigger flushes on LPT files, just on the device directly
        f = LPTFile(self.stream, 'close')
        # inherit width settings from device file
        f.width = self.device_file.width
        f.col = self.device_file.col
        return f


class LPTFile(devices.TextFileBase):
    """ LPTn: device - line printer or parallel port. """

    def __init__(self, stream, filetype='D', flush_trigger='close'):
        """ Initialise LPTn. """
        devices.TextFileBase.__init__(self, StringIO(), filetype, mode='A')
        # width=255 means line wrap
        self.width = 255
        self.col = 1
        self.output_stream = stream
        self.flush_trigger = flush_trigger

    def flush(self):
        """ Flush the printer buffer to the underlying stream. """
        if self.fhandle:
            val = self.fhandle.getvalue()
            self.output_stream.write(val)
            self.fhandle.truncate(0)

    def write(self, s):
        """ Write a string to the printer buffer. """
        for c in str(s):
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                self.fhandle.write('\r\n')
                self.flush()
                self.col = 1
            if c in ('\n', '\r', '\f'):
                # don't replace CR or LF with CRLF when writing to files
                self.fhandle.write(c)
                self.flush()
                self.col = 1
                # do the actual printing if we're on a short trigger
                if (self.flush_trigger == 'line' and c == '\n') or (self.flush_trigger == 'page' and c == '\f'):
                    self.output_stream.flush()
            elif c == '\b':   # BACKSPACE
                if self.col > 1:
                    self.col -= 1
                    self.fhandle.seek(-1, 1)
                    self.fhandle.truncate()
            else:
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                # for lpt1 and files , nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                if ord(c) >= 32:
                    self.col += 1

    def write_line(self, s=''):
        """ Write string or bytearray and newline to file. """
        self.write(str(s) + '\r\n')

    def lof(self):
        """ LOF: bad file mode """
        raise error.RunError(54)

    def loc(self):
        """ LOC: bad file mode """
        raise error.RunError(54)

    def eof(self):
        """ EOF: bad file mode """
        raise error.RunError(54)

    def close(self):
        """ Close the printer device and actually print the output. """
        self.flush()
        self.output_stream.flush()
        self.fhandle.close()
        self.fhandle = None


def parallel_port(port):
    """ Return a ParallelStream object for a given port. """
    if not parallel:
        logging.warning('Parallel module not found. Parallel port communication not available.')
        return None
    try:
        return ParallelStream(port)
    except EnvironmentError:
        logging.warning('Could not open parallel port %s.', port)
        return None


class ParallelStream(object):
    """ Wrapper for Parallel object to implement stream-like API. """

    def __init__(self, port):
        """ Initialise the ParallelStream. """
        self.parallel = parallel.Parallel(port)

    def flush(self):
        """ No buffer to flush. """
        pass

    def write(self, s):
        """ Write to the parallel port. """
        for c in s:
            self.parallel.setData(ord(c))

    def close(self):
        """ Close the stream. """
        pass

prepare()
