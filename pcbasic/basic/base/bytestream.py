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
        self._buffer = initial_bytes

    def write(self, b):
        if self._pos + len(b) > len(self._buffer):
            raise ValueError("Can't change size of buffer.")
        return BytesIO.write(self, b)
