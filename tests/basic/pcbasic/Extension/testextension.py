# -*- coding: utf-8 -*-

from __future__ import print_function

print('importing extension')

def output(*args):
    with open('python-output.txt', 'ab') as g:
        for arg in args:
            if isinstance(arg, bytes):
                g.write(arg)
            else:
                g.write(b'%d' % (arg,))
            g.write(b' ')

def add(x, y):
    return x + y
