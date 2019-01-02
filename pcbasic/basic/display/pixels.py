"""
PC-BASIC - pixels.py
Graphics buffer operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import operator

from ...compat import zip, int2byte
from ..base import error
from ..base import tokens as tk
from ..base import bytematrix
from .. import values


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
        # operations closures
        self._operations = {}
        # we need to store the mask so we can reconstruct the operations dict on unpickling
        self._mask = (1 << bitsperpixel) - 1
        self._init_operations(self._mask)

    def _init_operations(self, mask):
        """Initialise operations closures."""
        self._operations = {
            tk.PSET: lambda _x, _y: _y,
            tk.PRESET: lambda _x, _y: _y ^ mask,
            tk.AND: operator.iand,
            tk.OR: operator.ior,
            tk.XOR: operator.ixor,
        }

    def __getstate__(self):
        """Pickle the page."""
        pagedict = self.__dict__.copy()
        # lambdas can't be pickled
        pagedict['_operations'] = None
        return pagedict

    def __setstate__(self, pagedict):
        """Initialise from pickled page."""
        self.__dict__.update(pagedict)
        self._init_operations(self._mask)

    def copy_from(self, src):
        """Copy from another page."""
        self._buffer[:, :] = src._buffer

    def put_pixel(self, x, y, attr):
        """Put a pixel in the buffer."""
        try:
            self._buffer[y, x] = attr
            return self._buffer[y, x:x+1]._rows
        except IndexError:
            pass

    def get_pixel(self, x, y):
        """Get attribute of a pixel in the buffer."""
        try:
            return self._buffer[y, x]
        except IndexError:
            return 0

    def fill_interval(self, x0, x1, y, attr):
        """Write a list of attributes to a scanline interval."""
        try:
            self._buffer[y, x0:x1+1] = attr
            return self._buffer[y, x0:x1+1]._rows
        except IndexError:
            pass

    def put_interval(self, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        if not isinstance(colours, bytematrix.ByteMatrix):
            colours = bytematrix.ByteMatrix._create_from_rows([colours])
        width = colours.width
        result = (colours & mask) | (self._buffer[y, x:x+width] & ~mask)
        self._buffer[y, x:x+width] = result
        return result._rows

    def get_interval(self, x, y, length):
        """Return attributes of a scanline interval."""
        try:
            return self._buffer[y, x:x+length]._rows
        except IndexError:
            return [0] * length

    def fill_rect(self, x0, y0, x1, y1, attr):
        """Apply solid attribute to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            self._buffer[y0: y1+1, x0:x1+1] = attr
            return self._buffer[y0: y1+1, x0:x1+1]._rows
        except IndexError:
            pass

    def put_rect(self, x0, y0, x1, y1, array, operation_token):
        """Apply 2d list [y][x] of attributes to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            if not isinstance(array, bytematrix.ByteMatrix):
                array = bytematrix.ByteMatrix._create_from_rows(array)
            # can use in-place operaton method to avoid second slicing operation?
            # no, we still need a slice assignment after the in-place operation
            # or the result will be discarded along with the slice
            result = self._operations[operation_token](
                self._buffer[y0:y1+1, x0:x1+1], array
            )
            self._buffer[y0:y1+1, x0:x1+1] = result
            return result._rows
        except IndexError:
            return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

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
        if x0 == x1:
            return []
        elif x1 > x0:
            row = self._buffer[y, x0:x1]._rows[0]
            try:
                # pyton2 won't do bytearray.index(int)
                index = row.index(int2byte(c))
                return row[:index]
            except ValueError:
                return row
        else:
            row = self._buffer[y, x1+1:x0+1]._rows[0]
            try:
                index = row.rindex(int2byte(c))
                return row[index+1:]
            except ValueError:
                return row
