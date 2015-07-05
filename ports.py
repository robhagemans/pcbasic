"""
PC-BASIC - ports.py
Serial and parallel port handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.

SocketSerialWrapper.read is modelled on Python 2.7 licensed code from PySerial
PySerial (c) 2001-2013 Chris Liechtl <cliechti(at)gmx.net>; All Rights Reserved.
"""

import logging
import socket

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


###############################################################################
# COM ports

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
