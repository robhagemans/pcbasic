"""
PC-BASIC 3.23 - serial_socket.py
Workaround for some limitations of SocketSerial with timeout==0

Contains code from PySerial (c) 2001-2013 Chris Liechtl <cliechti(at)gmx.net>; All Rights Reserved.
as well as modifications (c) 2013-2014 Rob Hagemans.
This file is released under the Python licence.
"""


import logging

try:
    import serial
    from serial import SerialException, serialutil
except Exception:
    serial = None
    
try:
    import parallel    
except Exception:
    parallel = None
        
import socket
import select

def parallel_port(port):
    if not parallel:
        logging.warning('Parallel module not found. Parallel port communication not available.')
        return None
    try:
        return ParallelStream(port)
    except (OSError, IOError):
        logging.warning('Could not open parallel port %s.', port) 
        return None

def serial_for_url(url):
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
    def __init__(self, socketserial):
        self._serial = socketserial    
        self._isOpen = self._serial._isOpen
    
    def open(self):
        self._serial.open()
        self._isOpen = self._serial._isOpen
    
    def close(self):
        self._serial.close()
        self._isOpen = self._serial._isOpen
    
    def flush(self):
        pass
            
    # non-blocking read   
    # SocketSerial.read always returns '' if timeout==0
    def read(self, num=1):
        self._serial._socket.setblocking(0)
        if not self._serial._isOpen: 
            raise serialutil.portNotOpenError
        # poll for bytes (timeout = 0)
        ready, _, _ = select.select([self._serial._socket], [], [], 0)
        if not ready:
            # no bytes present after poll
            return ''
        try:
            # fill buffer at most up to buffer size  
            return self._serial._socket.recv(num)
        except socket.timeout:
            pass
        except socket.error, e:
            raise SerialException('connection failed (%s)' % e)
    
    def write(self, s):
        self._serial.write(s)                    


class ParallelStream(object):

    def __init__(self, port):
        self.parallel = parallel.Parallel(port)
    
    def flush(self):
        pass
        
    def write(self, s):
        for c in s:
            self.parallel.setData(ord(c))
    
    def close(self):
        pass
                    

        
