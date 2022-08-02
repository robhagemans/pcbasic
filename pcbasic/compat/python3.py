"""
PC-BASIC - compat.python3
Python 2/Python 3 functionality

Contains lines of code from package six, which is
Copyright (c) 2010-2018 Benjamin Peterson
and released under an MIT licence https://opensource.org/licenses/MIT
"""

import sys
import os
import struct


# deal with broken pipes

def is_broken_pipe(e):
    return isinstance(e, BrokenPipeError)

# strings

int2byte = struct.Struct(">B").pack

def add_str(cls):
    """Decorator to implement the correct str() function."""
    try:
        cls.__str__ = cls.__unicode__
    except AttributeError:
        pass
    return cls

# unicode system interfaces

getcwdu = os.getcwd
getenvu = os.getenv
iterenvu = os.environ.keys

def setenvu(key, value):
    os.environ[key] = value

# iterators
zip = zip
xrange = range

def iterchar(s):
    """Iterate over bytes, returning char."""
    return (s[_i:_i+1] for _i in range(len(s)))

def iterbytes(s):
    """Iterate over bytes/bytearray/memoryview, returning int."""
    return s

def iteritems(d, **kw):
    return iter(d.items(**kw))

def itervalues(d, **kw):
    return iter(d.values(**kw))

def iterkeys(d, **kw):
    return iter(d.keys(**kw))
