import sys

sys.stdout.write(b'\xff')
for i in range(128, 256):
    sys.stdout.write(b'\xc0\xde%c\0%c \x0e\x0a\0\0' % (i, i))
for i in range(128, 256):
    sys.stdout.write(b'\xc0\xde%c\x01\xfd%c \x0e\x0a\0\0' % (i, i))
for i in range(128, 256):
    sys.stdout.write(b'\xc0\xde%c\x02\xfe%c \x0e\x0a\0\0' % (i, i))
for i in range(128, 256):
    sys.stdout.write(b'\xc0\xde%c\x03\xff%c \x0e\x0a\0\0' % (i, i))
sys.stdout.write(b'\x1a')
