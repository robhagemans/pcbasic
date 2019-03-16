import serial
import sys

s = serial.serial_for_url('socket://localhost:22222', timeout=0)

while True:
    sys.stdout.write(s.read(1))
    sys.stdout.flush()
