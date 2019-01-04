"""
PC-BASIC - pixels.py
Graphics buffer operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import operator

from ..base import tokens as tk
from ..base import bytematrix


# pixel operations
OPERATIONS = {
    tk.PSET: lambda _x, _y: _y,
    tk.PRESET: lambda _x, _y: _y ^ 0xff,
    tk.AND: operator.iand,
    tk.OR: operator.ior,
    tk.XOR: operator.ixor,
}


class PixelBuffer(object):
    """Buffer for graphics on all screen pages."""

    def __init__(self, width, height, pages, bitsperpixel):
        """Initialise the graphics buffer to given pages and dimensions."""
        self.pages = [PixelPage(width, height, bitsperpixel) for _ in range(pages)]
        self.width = width
        self.height = height


class PixelPage(object):
    """Buffer for a screen page."""

    def __init__(self, width, height, bitsperpixel):
        """Initialise the screen buffer to given dimensions."""
        self._buffer = bytematrix.ByteMatrix(height, width)
        self.width = width
        self.height = height

    def copy_from(self, src):
        """Copy from another page."""
        self._buffer[:, :] = src._buffer

    def put_pixel(self, x, y, attr):
        """Put a pixel in the buffer."""
        self._buffer[y, x] = attr
        return self._buffer[y, x:x+1]

    def get_pixel(self, x, y):
        """Get attribute of a pixel in the buffer."""
        return self._buffer[y, x]

    def fill_interval(self, x0, x1, y, attr):
        """Write a list of attributes to a scanline interval."""
        self._buffer[y, x0:x1+1] = attr
        return self._buffer[y, x0:x1+1]

    def put_interval(self, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        width = colours.width
        result = (colours & mask) | (self._buffer[y, x:x+width] & ~mask)
        self._buffer[y, x:x+width] = result
        return result

    def get_interval(self, x, y, length):
        """Return attributes of a scanline interval."""
        return self._buffer[y, x:x+length]

    def fill_rect(self, x0, y0, x1, y1, attr):
        """Apply solid attribute to an area."""
        self._buffer[y0:y1+1, x0:x1+1] = attr
        return self._buffer[y0:y1+1, x0:x1+1]

    def put_rect(self, x0, y0, x1, y1, array, operation_token):
        """Apply 2d list [y][x] of attributes to an area."""
        # can use in-place operaton method to avoid second slicing operation?
        # no, we still need a slice assignment after the in-place operation
        # or the result will be discarded along with the slice
        result = OPERATIONS[operation_token](
            self._buffer[y0:y1+1, x0:x1+1], array
        )
        self._buffer[y0:y1+1, x0:x1+1] = result
        return result

    def get_rect(self, x0, y0, x1, y1):
        """Get ByteMatrix of target area."""
        return self._buffer[y0:y1+1, x0:x1+1]

    def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
        """Move pixels from an area to another, replacing with attribute 0."""
        clip = self._buffer[sy0:sy1+1, sx0:sx1+1]
        height, width = sy1 - sy0 + 1, sx1 - sx0 + 1
        self._buffer[sy0:sy1+1, sx0:sx1+1] = 0
        self._buffer[ty0 : ty0+height, tx0 : tx0+width] = clip

    def get_until(self, x0, x1, y, c):
        """Get the attribute values of a scanline interval [x0, x1-1]."""
        return self._buffer.row_until(c, y, x0, x1)
