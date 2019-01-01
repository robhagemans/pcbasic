"""
PC-BASIC - pixels.py
Graphics buffer operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import error
from ..base import tokens as tk
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
        self._buffer = [[0]*width for _ in range(height)]
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
            tk.PSET: lambda x, y: y,
            tk.PRESET: lambda x, y: y ^ mask,
            tk.AND: lambda x, y: x & y,
            tk.OR: lambda x, y: x | y,
            tk.XOR: lambda x, y: x ^ y,
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
        self.init_operations(self._mask)

    def copy_from(self, src):
        """Copy from another page."""
        self._buffer[:] = src._buffer[:]

    def put_pixel(self, x, y, attr):
        """Put a pixel in the buffer."""
        try:
            self._buffer[y][x] = attr
            return self._buffer[y][x:x+1]
        except IndexError:
            pass

    def get_pixel(self, x, y):
        """Get attribute of a pixel in the buffer."""
        try:
            return self._buffer[y][x]
        except IndexError:
            return 0

    def fill_interval(self, x0, x1, y, attr):
        """Write a list of attributes to a scanline interval."""
        try:
            self._buffer[y][x0:x1+1] = [attr]*(x1-x0+1)
            return [self._buffer[y][x0:x1+1]]
        except IndexError:
            pass

    def put_interval(self, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        inv_mask = 0xff ^ mask
        self._buffer[y][x:x+len(colours)] = [
            (c & mask) | (self._buffer[y][x+i] & inv_mask)
            for i, c in enumerate(colours)
        ]
        return [self._buffer[y][x:x+len(colours)]]

    def get_interval(self, x, y, length):
        """Return attributes of a scanline interval."""
        try:
            return self._buffer[y][x:x+length]
        except IndexError:
            return [0] * length

    def fill_rect(self, x0, y0, x1, y1, attr):
        """Apply solid attribute to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            for y in range(y0, y1+1):
                self._buffer[y][x0:x1+1] = [attr] * (x1-x0+1)
            return [self._buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            pass

    def put_rect(self, x0, y0, x1, y1, array, operation_token):
        """Apply 2d list [y][x] of attributes to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            for y in range(y0, y1+1):
                self._buffer[y][x0:x1+1] = [
                    self._operations[operation_token](a, b)
                    for a, b in zip(self._buffer[y][x0:x1+1], array[y-y0])
                ]
            return [self._buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

    def get_rect(self, x0, y0, x1, y1):
        """Get 2d list [y][x] of target area."""
        try:
            return [self._buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

    def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
        """Move pixels from an area to another, replacing with attribute 0."""
        for y in range(0, sy1-sy0+1):
            row = self._buffer[sy0+y][sx0:sx1+1]
            self._buffer[sy0+y][sx0:sx1+1] = [0] * (sx1-sx0+1)
            self._buffer[ty0+y][tx0:tx0+(sx1-sx0+1)] = row

    def get_until(self, x0, x1, y, c):
        """Get the attribute values of a scanline interval [x0, x1-1]."""
        if x0 == x1:
            return []
        elif x1 > x0:
            try:
                index = self._buffer[y][x0:x1].index(c)
            except ValueError:
                index = x1-x0
            return self._buffer[y][x0:x0+index]
        else:
            x0, x1 = x1+1, x0+1
            try:
                index = list(reversed(self._buffer[y][x0:x1])).index(c)
            except ValueError:
                index = x0-x1
            return self._buffer[y][x1-index:x1]
