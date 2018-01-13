# -*- coding: utf-8 -*-

print "importing extension"

def output(*args):
    with open('python-output.txt', 'a') as g:
        g.write(repr(list(args)))

def add(x, y):
    return x + y
