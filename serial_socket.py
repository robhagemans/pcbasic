#
# serial_socket.py
# workaround for some limitations of SocketSerial with timeout==0

import sys

try:
    import serial
    from serial import SerialException, serialutil
except Exception:
    serial = None
    
import socket
import select
import oslayer
# import explicitly, or pyinstaller won't bring them along
import serial.urlhandler.protocol_socket
import serial.urlhandler.protocol_rfc2217
import serial.urlhandler.protocol_loop
import serial.urlhandler.protocol_hwgrep

def serial_for_url(url):
    if not serial:
        sys.stderr.write('WARNING: PySerial module not found. Serial port and socket communication not available.\n')
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


