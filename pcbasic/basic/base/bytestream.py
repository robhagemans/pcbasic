"""
PC-BASIC - bytestream.py
BytesIO extension with externally provided buffer

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from _pyio import BytesIO


class ByteStream(BytesIO):
    """BytesIO over external buffer."""

    def __init__(self, initial_bytes):
        """Create new ByteStream."""
        BytesIO.__init__(self)
        # use the actual object as a buffer, do not copy
        self._buffer = memoryview(initial_bytes)

    # slighly modified from python2's _pyio
    def read(self, n=None):
        """Read from bytestream."""
        if self.closed:
            raise ValueError('read from closed file')
        if n is None:
            n = -1
        if not isinstance(n, int):
            raise TypeError('integer argument expected, got {0!r}'.format(type(n)))
        if n < 0:
            n = len(self._buffer)
        if len(self._buffer) <= self._pos:
            return b''
        newpos = min(len(self._buffer), self._pos + n)
        b = self._buffer[self._pos : newpos]
        self._pos = newpos
        # this is necessary for python2, where bytes(memoryview) gives a 'string representation'
        return bytes(bytearray(b))
