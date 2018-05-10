import sys

sys.stdout.write('\xff')
for i in range(128, 256):
    sys.stdout.write('\xc0\xde%s\0%s \x0e\x0a\0\0' % (chr(i), chr(i)))
for i in range(128, 256):
    sys.stdout.write('\xc0\xde%s\x01\xfd%s \x0e\x0a\0\0' % (chr(i), chr(i)))
for i in range(128, 256):
    sys.stdout.write('\xc0\xde%s\x02\xfe%s \x0e\x0a\0\0' % (chr(i), chr(i)))
for i in range(128, 256):
    sys.stdout.write('\xc0\xde%s\x03\xff%s \x0e\x0a\0\0' % (chr(i), chr(i)))
sys.stdout.write('\x1a')
