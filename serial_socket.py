#
# serial_socket.py
# workaround for some limitations of SocketSerial with timeout==0

import serial
import socket
import select

def serial_for_url(url):
    stream = serial.serial_for_url(url, timeout=0, do_not_open=True)
    if url.split(':', 1)[0] == 'serial':
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
        
    # non-blocking read   
    # SocketSerial.read always returns '' if timeout==0
    def read(self, num=1):
        self._serial._socket.setblocking(0)
        if not self._serial._isOpen: 
            raise serial.serialutil.portNotOpenError
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
            raise serial.SerialException('connection failed (%s)' % e)
    
    def write(self, s):
        self._serial.write(s)                    


