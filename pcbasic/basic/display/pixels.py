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

    def __init__(self, bwidth, bheight, bpages, bitsperpixel):
        """Initialise the graphics buffer to given pages and dimensions."""
        self.pages = [PixelPage(bwidth, bheight, num, bitsperpixel) for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        self.pages[dst].buffer[:] = self.pages[src].buffer[:]


class PixelPage(object):
    """Buffer for a screen page."""

    def __init__(self, width, height, pagenum, bitsperpixel):
        """Initialise the screen buffer to given dimensions."""
        self.buffer = [[0]*width for _ in range(height)]
        self.width = width
        self.height = height
        self.pagenum = pagenum
        self.bitsperpixel = bitsperpixel
        self.init_operations()

    def __getstate__(self):
        """Pickle the page."""
        pagedict = self.__dict__.copy()
        # lambdas can't be pickled
        pagedict['operations'] = None
        return pagedict

    def __setstate__(self, pagedict):
        """Initialise from pickled page."""
        self.__dict__.update(pagedict)
        self.init_operations()

    def put_pixel(self, x, y, attr):
        """Put a pixel in the buffer."""
        try:
            self.buffer[y][x] = attr
            return self.buffer[y][x:x+1]
        except IndexError:
            pass

    def get_pixel(self, x, y):
        """Get attribute of a pixel in the buffer."""
        try:
            return self.buffer[y][x]
        except IndexError:
            return 0

    def fill_interval(self, x0, x1, y, attr):
        """Write a list of attributes to a scanline interval."""
        try:
            self.buffer[y][x0:x1+1] = [attr]*(x1-x0+1)
            return [self.buffer[y][x0:x1+1]]
        except IndexError:
            pass

    def init_operations(self):
        """Initialise operations closures."""
        self.operations = {
            tk.PSET: lambda x, y: y,
            tk.PRESET: lambda x, y: y ^ ((1<<self.bitsperpixel)-1),
            tk.AND: lambda x, y: x & y,
            tk.OR: lambda x, y: x | y,
            tk.XOR: lambda x, y: x ^ y,
        }

    def put_interval(self, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        inv_mask = 0xff ^ mask
        self.buffer[y][x:x+len(colours)] = [
            (c & mask) | (self.buffer[y][x+i] & inv_mask)
            for i, c in enumerate(colours)
        ]
        return [self.buffer[y][x:x+len(colours)]]

    def get_interval(self, x, y, length):
        """Return *view of* attributes of a scanline interval."""
        try:
            return self.buffer[y][x:x+length]
        except IndexError:
            return [0] * length

    def fill_rect(self, x0, y0, x1, y1, attr):
        """Apply solid attribute to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            for y in range(y0, y1+1):
                self.buffer[y][x0:x1+1] = [attr] * (x1-x0+1)
            return [self.buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            pass

    def put_rect(self, x0, y0, x1, y1, array, operation_token):
        """Apply 2d list [y][x] of attributes to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        try:
            for y in range(y0, y1+1):
                self.buffer[y][x0:x1+1] = [
                    self.operations[operation_token](a, b)
                    for a, b in zip(self.buffer[y][x0:x1+1], array[y-y0])
                ]
            return [self.buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

    def get_rect(self, x0, y0, x1, y1):
        """Get *copy of* 2d list [y][x] of target area."""
        try:
            return [self.buffer[y][x0:x1+1] for y in range(y0, y1+1)]
        except IndexError:
            return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

    def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
        """Move pixels from an area to another, replacing with attribute 0."""
        for y in range(0, sy1-sy0+1):
            row = self.buffer[sy0+y][sx0:sx1+1]
            self.buffer[sy0+y][sx0:sx1+1] = [0] * (sx1-sx0+1)
            self.buffer[ty0+y][tx0:tx0+(sx1-sx0+1)] = row

    def get_until(self, x0, x1, y, c):
        """Get the attribute values of a scanline interval [x0, x1-1]."""
        if x0 == x1:
            return []
        toright = x1 > x0
        if not toright:
            x0, x1 = x1+1, x0+1
        try:
            index = self.buffer[y][x0:x1].index(c)
        except ValueError:
            index = x1-x0
        return self.buffer[y][x0:x0+index]
