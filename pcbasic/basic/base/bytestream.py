"""
PC-BASIC - bytestream.py
BytesIO extension with externally provided buffer

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from _pyio import BytesIO

from ...compat import PY2


class ByteStream(BytesIO):
    """BytesIO over external buffer."""

    def __init__(self, initial_bytes):
        """Create new ByteStream."""
        BytesIO.__init__(self)
        # use the actual object as a buffer, do not copy
        self._buffer = memoryview(initial_bytes)

    def write(self, b):
        if self._pos + len(b) > len(self._buffer):
            raise ValueError("Can't change size of buffer.")
        return BytesIO.write(self, b)

    if PY2:
        def read(self, n=None):
            if self.closed:
                raise ValueError("read from closed file")
            if n is None:
                n = -1
            if not isinstance(n, (int, long)):
                raise TypeError("integer argument expected, got {0!r}".format(
                    type(n)))
            if n < 0:
                n = len(self._buffer)
            if len(self._buffer) <= self._pos:
                return b""
            newpos = min(len(self._buffer), self._pos + n)
            b = self._buffer[self._pos : newpos]
            self._pos = newpos
            return bytes(bytearray(b))
