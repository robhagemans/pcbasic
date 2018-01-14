"""
PC-BASIC - bytestream.py
BytesIO extension with externally provided buffer

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import _pyio

class ByteStream(_pyio.BytesIO):
    """Extension of BytesIO with accessible buffer."""

    def __init__(self, initial_bytes):
        """Create new ByteStream."""
        _pyio.BytesIO.__init__(self)
        # use the actual object as a buffer, do not copy
        self._buffer = initial_bytes
