"""
PC-BASIC - display.py
Text and graphics buffer, cursor and screen operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import struct

try:
    import numpy
except ImportError:
    numpy = None

from ..base import signals
from ..base import error
from ..base import tokens as tk
from .. import values


#######################################################################################
# text buffer

class TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, battr, bwidth):
        """Set up screen row empty and unwrapped."""
        # screen buffer, initialised to spaces, dim white on black
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False

    def clear(self, battr):
        """Clear the screen row buffer. Leave wrap untouched."""
        bwidth = len(self.buf)
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0


class TextPage(object):
    """Buffer for a screen page."""

    def __init__(self, battr, bwidth, bheight, pagenum, do_dbcs, codepage):
        """Initialise the screen buffer to given dimensions."""
        self.row = [TextRow(battr, bwidth) for _ in xrange(bheight)]
        self.width = bwidth
        self.height = bheight
        self.pagenum = pagenum
        self.do_dbcs = do_dbcs
        self.codepage = codepage

    def get_char_attr(self, crow, ccol, want_attr):
        """Retrieve a byte from the screen (SBCS or DBCS half-char)."""
        ca = self.row[crow-1].buf[ccol-1][want_attr]
        return ca if want_attr else ord(ca)

    def put_char_attr(self, crow, ccol, c, cattr, one_only=False, force=False):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        # update the screen buffer
        self.row[crow-1].buf[ccol-1] = (c, cattr)
        # mark the replaced char for refreshing
        start, stop = ccol, ccol+1
        self.row[crow-1].double[ccol-1] = 0
        # mark out sbcs and dbcs characters
        if self.codepage.dbcs and self.do_dbcs:
            orig_col = ccol
            # replace chars from here until necessary to update double-width chars
            therow = self.row[crow-1]
            # replacing a trail byte? take one step back
            # previous char could be a lead byte? take a step back
            if (ccol > 1 and therow.double[ccol-2] != 2 and
                    (therow.buf[ccol-1][0] in self.codepage.trail or
                     therow.buf[ccol-2][0] in self.codepage.lead)):
                ccol -= 1
                start -= 1
            # check all dbcs characters between here until it doesn't matter anymore
            while ccol < self.width:
                c = therow.buf[ccol-1][0]
                d = therow.buf[ccol][0]
                if (c in self.codepage.lead and
                        d in self.codepage.trail):
                    if (therow.double[ccol-1] == 1 and
                            therow.double[ccol] == 2 and ccol > orig_col):
                        break
                    therow.double[ccol-1] = 1
                    therow.double[ccol] = 2
                    start, stop = min(start, ccol), max(stop, ccol+2)
                    ccol += 2
                else:
                    if therow.double[ccol-1] == 0 and ccol > orig_col:
                        break
                    therow.double[ccol-1] = 0
                    start, stop = min(start, ccol), max(stop, ccol+1)
                    ccol += 1
                if (ccol >= self.width or
                        (one_only and ccol > orig_col)):
                    break
            # check for box drawing
            if self.codepage.box_protect:
                ccol = start-2
                connecting = 0
                bset = -1
                while ccol < stop+2 and ccol < self.width:
                    c = therow.buf[ccol-1][0]
                    d = therow.buf[ccol][0]
                    if bset > -1 and self.codepage.connects(c, d, bset):
                        connecting += 1
                    else:
                        connecting = 0
                        bset = -1
                    if bset == -1:
                        for b in (0, 1):
                            if self.codepage.connects(c, d, b):
                                bset = b
                                connecting = 1
                    if connecting >= 2:
                        therow.double[ccol] = 0
                        therow.double[ccol-1] = 0
                        therow.double[ccol-2] = 0
                        start = min(start, ccol-1)
                        if ccol > 2 and therow.double[ccol-3] == 1:
                            therow.double[ccol-3] = 0
                            start = min(start, ccol-2)
                        if (ccol < self.width-1 and
                                therow.double[ccol+1] == 2):
                            therow.double[ccol+1] = 0
                            stop = max(stop, ccol+2)
                    ccol += 1
        return start, stop

class TextBuffer(object):
    """Buffer for text on all screen pages."""

    def __init__(self, battr, bwidth, bheight, bpages, do_dbcs, codepage):
        """Initialise the screen buffer to given pages and dimensions."""
        self.pages = [TextPage(battr, bwidth, bheight, num, do_dbcs, codepage)
                      for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap


#######################################################################################
# Pixel buffer

class PixelBuffer(object):
    """Buffer for graphics on all screen pages."""

    def __init__(self, bwidth, bheight, bpages, bitsperpixel):
        """Initialise the graphics buffer to given pages and dimensions."""
        self.pages = [ PixelPage(bwidth, bheight, num, bitsperpixel) for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]

class PixelPage(object):
    """Buffer for a screen page."""

    def __init__(self, bwidth, bheight, pagenum, bitsperpixel):
        """Initialise the screen buffer to given dimensions."""
        if numpy:
            self.buffer = numpy.zeros((bheight, bwidth), dtype=numpy.int8)
        else:
            self.buffer = [[0]*bwidth for _ in range(bheight)]
        self.width = bwidth
        self.height = bheight
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
        except IndexError:
            pass

    if numpy:
        def init_operations(self):
            """Initialise operations closures."""
            self.operations = {
                tk.PSET: lambda x, y: x.__setitem__(slice(len(x)), y),
                tk.PRESET: lambda x, y: x.__setitem__(slice(len(x)), y.__xor__((1<<self.bitsperpixel) - 1)),
                tk.AND: lambda x, y: x.__iand__(y),
                tk.OR: lambda x, y: x.__ior__(y),
                tk.XOR: lambda x, y: x.__ixor__(y),
            }

        def put_interval(self, x, y, colours, mask=0xff):
            """Write a list of attributes to a scanline interval."""
            colours = numpy.array(colours).astype(int)
            inv_mask = 0xff ^ mask
            colours &= mask
            try:
                self.buffer[y, x:x+len(colours)] &= inv_mask
                self.buffer[y, x:x+len(colours)] |= colours
                return self.buffer[y, x:x+len(colours)]
            except IndexError:
                return numpy.zeros(len(colours), dtype=numpy.int8)

        def get_interval(self, x, y, length):
            """Return *view of* attributes of a scanline interval."""
            try:
                return self.buffer[y, x:x+length]
            except IndexError:
                return numpy.zeros(length, dtype=numpy.int8)

        def fill_rect(self, x0, y0, x1, y1, attr):
            """Apply solid attribute to an area."""
            if (x1 < x0) or (y1 < y0):
                return
            try:
                self.buffer[y0:y1+1, x0:x1+1].fill(attr)
            except IndexError:
                pass

        def put_rect(self, x0, y0, x1, y1, array, operation_token):
            """Apply numpy array [y][x] of attributes to an area."""
            if (x1 < x0) or (y1 < y0):
                return
            try:
                self.operations[operation_token](self.buffer[y0:y1+1, x0:x1+1], numpy.asarray(array))
                return self.buffer[y0:y1+1, x0:x1+1]
            except IndexError:
                return numpy.zeros((y1-y0+1, x1-x0+1), dtype=numpy.int8)

        def get_rect(self, x0, y0, x1, y1):
            """Get *copy of* numpy array [y][x] of target area."""
            try:
                # our only user in module graphics needs a copy, so copy.
                return numpy.array(self.buffer[y0:y1+1, x0:x1+1])
            except IndexError:
                return numpy.zeros((y1-y0+1, x1-x0+1), dtype=numpy.int8)

        def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
            """Move pixels from an area to another, replacing with attribute 0."""
            w, h = sx1-sx0+1, sy1-sy0+1
            area = numpy.array(self.buffer[sy0:sy1+1, sx0:sx1+1])
            self.buffer[sy0:sy1+1, sx0:sx1+1] = numpy.zeros((h, w), dtype=numpy.int8)
            self.buffer[ty0:ty0+h, tx0:tx0+w] = area

        def get_until(self, x0, x1, y, c):
            """Get the attribute values of a scanline interval [x0, x1-1]."""
            if x0 == x1:
                return []
            toright = x1 > x0
            if not toright:
                x0, x1 = x1+1, x0+1
            try:
                arr = self.buffer[y, x0:x1]
            except IndexError:
                return []
            found = numpy.where(arr == c)
            if len(found[0]) > 0:
                if toright:
                    arr = arr[:found[0][0]]
                else:
                    arr = arr[found[0][-1]+1:]
            return list(arr.flatten())

    else:
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
            if mask != 0xff:
                inv_mask = 0xff ^ mask
                self.buffer[y][x:x+len(colours)] = [(c & mask) |
                                                (self.buffer[y][x+i] & inv_mask)
                                                for i,c in enumerate(colours)]
            return self.buffer[y][x:x+len(colours)]

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
            except IndexError:
                pass

        def put_rect(self, x0, y0, x1, y1, array, operation_token):
            """Apply 2d list [y][x] of attributes to an area."""
            if (x1 < x0) or (y1 < y0):
                return
            try:
                for y in range(y0, y1+1):
                    self.buffer[y][x0:x1+1] = [
                        [self.operations[operation_token](a, b)
                        for a, b in zip(self.buffer[y][x0:x1+1], array)]]
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


#######################################################################################
# function key macro guide

class BottomBar(object):
    """Key guide bar at bottom line."""

    def __init__(self):
        """Initialise bottom bar."""
        # use 80 here independent of screen width
        # we store everything in a buffer and only show what fits
        self.clear()
        self.visible = False

    def clear(self):
        """Clear the contents."""
        self._contents = [(b'\0', 0)] * 80

    def write(self, s, col, reverse):
        """Write chars on virtual bottom bar."""
        for i, c in enumerate(s):
            self._contents[col + i] = (c, reverse)

    def show(self, on, screen):
        """Switch bottom bar visibility."""
        self.visible, was_visible = on, self.visible
        if self.visible != was_visible:
            self.redraw(screen)

    def redraw(self, screen):
        """Redraw bottom bar if visible, clear if not."""
        key_row = screen.mode.height
        # Keys will only be visible on the active page at which KEY ON was given,
        # and only deleted on page at which KEY OFF given.
        screen.clear_rows(key_row, key_row)
        if not screen.mode.is_text_mode:
            reverse_attr = screen.attr
        elif (screen.attr >> 4) & 0x7 == 0:
            reverse_attr = 0x70
        else:
            reverse_attr = 0x07
        if self.visible:
            error.throw_if(screen.scroll_height == key_row)
            # always show only complete 8-character cells
            # this matters on pcjr/tandy width=20 mode
            for i in range((screen.mode.width//8) * 8):
                c, reverse = self._contents[i]
                a = reverse_attr if reverse else screen.attr
                screen.put_char_attr(screen.apagenum, key_row, i+1, c, a, suppress_cli=True)
            screen.apage.row[key_row-1].end = screen.mode.width


#######################################################################################
# palette

class Palette(object):
    """Colour palette."""

    def __init__(self, queues, mode, capabilities, memory):
        """Initialise palette."""
        self.capabilities = capabilities
        self._memory = memory
        self._queues = queues
        self.mode = mode
        self.set_all(mode.palette, check_mode=False)

    def init_mode(self, mode):
        """Initialise for new mode."""
        self.mode = mode
        self.set_all(mode.palette, check_mode=False)

    def set_entry(self, index, colour, check_mode=True):
        """Set a new colour for a given attribute."""
        mode = self.mode
        if check_mode and not self.mode_allows_palette(mode):
            return
        self.palette[index] = colour
        self.rgb_palette[index] = mode.colours[colour]
        if mode.colours1:
            self.rgb_palette1[index] = mode.colours1[colour]
        self._queues.video.put(
            signals.Event(signals.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def get_entry(self, index):
        """Retrieve the colour for a given attribute."""
        return self.palette[index]

    def set_all(self, new_palette, check_mode=True):
        """Set the colours for all attributes."""
        if check_mode and new_palette and not self.mode_allows_palette(self.mode):
            return
        self.palette = list(new_palette)
        self.rgb_palette = [self.mode.colours[i] for i in self.palette]
        if self.mode.colours1:
            self.rgb_palette1 = [self.mode.colours1[i] for i in self.palette]
        else:
            self.rgb_palette1 = None
        self._queues.video.put(
            signals.Event(signals.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def mode_allows_palette(self, mode):
        """Check if the video mode allows palette change."""
        # effective palette change is an error in CGA
        if self.capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.BASICError(error.IFC)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif self.capabilities in ('tandy', 'pcjr') and mode.is_text_mode:
            return False
        else:
            return True

    def palette_(self, args):
        """PALETTE: assign colour to attribute."""
        attrib = next(args)
        if attrib is not None:
            attrib = values.to_int(attrib)
        colour = next(args)
        if colour is not None:
            colour = values.to_int(colour)
        list(args)
        if attrib is None and colour is None:
            self.set_all(self.mode.palette)
        else:
            # can't set blinking colours separately
            num_palette_entries = self.mode.num_attr if self.mode.num_attr != 32 else 16
            error.range_check(0, num_palette_entries-1, attrib)
            colour = (colour+1) % 256 -1
            error.range_check(-1, len(self.mode.colours)-1, colour)
            if colour != -1:
                self.set_entry(attrib, colour)

    def palette_using_(self, args):
        """PALETTE USING: set palette from array buffer."""
        array_name, start_indices = next(args)
        array_name = self._memory.complete_name(array_name)
        list(args)
        num_palette_entries = self.mode.num_attr if self.mode.num_attr != 32 else 16
        try:
            dimensions = self._memory.arrays.dimensions(array_name)
        except KeyError:
            raise error.BASICError(error.IFC)
        error.throw_if(array_name[-1] != '%', error.TYPE_MISMATCH)
        lst = self._memory.arrays.view_full_buffer(array_name)
        start = self._memory.arrays.index(start_indices, dimensions)
        error.throw_if(self._memory.arrays.array_len(dimensions) - start < num_palette_entries)
        new_palette = []
        for i in range(num_palette_entries):
            offset = (start+i) * 2
            ## signed int, as -1 means don't set
            val, = struct.unpack('<h', lst[offset:offset+2])
            error.range_check(-1, len(self.mode.colours)-1, val)
            new_palette.append(val if val > -1 else self.get_entry(i))
        self.set_all(new_palette)


#######################################################################################
# cursor

class Cursor(object):
    """Manage the cursor."""

    def __init__(self, queues, mode, capabilities):
        """Initialise the cursor."""
        self._queues = queues
        self._mode = mode
        self._capabilities = capabilities
        # are we in parse mode? invisible unless visible_run is True
        self.default_visible = True
        # cursor visible in parse mode? user override
        self.visible_run = False
        # cursor shape
        self.from_line = 0
        self.to_line = 0
        self.width = self._mode.font_width
        self._height = self._mode.font_height

    def init_mode(self, mode):
        """Change the cursor for a new screen mode."""
        self._mode = mode
        self.width = mode.font_width
        self._height = mode.font_height
        # cursor width starts out as single char
        self.set_default_shape(True)
        #self.reset_attr()
        self.reset_visibility()

    def reset_attr(self, new_attr):
        """Set the text cursor attribute."""
        if self._mode.is_text_mode:
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, new_attr))

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, do_show))

    def set_visibility(self, visible_run):
        """Set cursor visibility when a program is being run."""
        self.visible_run = visible_run
        self.reset_visibility()

    def reset_visibility(self):
        """Set cursor visibility to its default state."""
        # visible if in interactive mode and invisible when a program is being run
        visible = self.default_visible
        # unless forced to be visible
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self._mode.is_text_mode:
            visible = visible or self.visible_run
        self._queues.video.put(signals.Event(signals.VIDEO_SHOW_CURSOR, visible))

    def set_shape(self, from_line, to_line):
        """Set the cursor shape."""
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        fx, fy = self.width, self._height
        # do all text modes with >8 pixels have an ega-cursor?
        if self._capabilities in (
                'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules'):
            # odd treatment of cursors on EGA machines,
            # presumably for backward compatibility
            # the following algorithm is based on DOSBox source int10_char.cpp
            #     INT10_SetCursorShape(Bit8u first,Bit8u last)
            max_line = fy - 1
            if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
                if (to_line < from_line):
                    # invisible only if to_line is zero and to_line < from_line
                    if to_line != 0:
                        # block shape from *to_line* to end
                        from_line = to_line
                        to_line = max_line
                elif ((from_line | to_line) >= max_line or
                            to_line != max_line-1 or from_line != max_line):
                    if to_line > 3:
                        if from_line+2 < to_line:
                            if from_line > 2:
                                from_line = (max_line+1) // 2
                            to_line = max_line
                        else:
                            from_line = from_line - to_line + max_line
                            to_line = max_line
                            if max_line > 0xc:
                                from_line -= 1
                                to_line -= 1
        self.from_line = max(0, min(from_line, fy-1))
        self.to_line = max(0, min(to_line, fy-1))
        self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                            (self.width, fy, self.from_line, self.to_line)))

    def set_default_shape(self, overwrite_shape):
        """Set the cursor to one of two default shapes."""
        if overwrite_shape:
            if not self._mode.is_text_mode:
                # always a block cursor in graphics mode
                self.set_shape(0, self._height-1)
            elif self._capabilities == 'ega':
                # EGA cursor is on second last line
                self.set_shape(self._height-2, self._height-2)
            elif self._height == 9:
                # Tandy 9-pixel fonts; cursor on 8th
                self.set_shape(self._height-2, self._height-2)
            else:
                # other cards have cursor on last line
                self.set_shape(self._height-1, self._height-1)
        else:
            # half-block cursor for insert
            self.set_shape(self._height//2, self._height-1)

    def set_width(self, num_chars):
        """Set the cursor with to num_chars characters."""
        new_width = num_chars * self._mode.font_width
        # update cursor shape to new width if necessary
        if new_width != self.width:
            self.width = new_width
            self._queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                    (self.width, self._height, self.from_line, self.to_line)))


#######################################################################################
# glyph cache

class GlyphCache(object):

    def __init__(self, mode, fonts, codepage, queues):
        """Initialise glyph set."""
        self._queues = queues
        self._mode = mode
        self._fonts = fonts
        self._codepage = codepage
        # preload SBCS glyphs
        self._glyphs = {
            c: self._fonts[mode.font_height].build_glyph(c, mode.font_width, mode.font_height)
            for c in map(chr, range(256))
        }
        self.submit()

    def submit(self):
        """Send glyph dict to interface."""
        if self._mode.is_text_mode:
            # send glyphs to signals; copy is necessary
            # as dict may change here while the other thread is working on it
            self._queues.video.put(signals.Event(signals.VIDEO_BUILD_GLYPHS,
                    {self._codepage.to_unicode(k, u'\0'): v for k, v in self._glyphs.iteritems()}))

    def rebuild_glyph(self, ordval):
        """Rebuild a text-mode character after POKE."""
        if self._mode.is_text_mode:
            # force rebuilding the character by deleting and requesting
            del self._glyphs[chr(ordval)]
            self.get_glyph(chr(ordval))

    def get_glyph(self, c):
        """Return a glyph mask for a given character """
        try:
            mask = self._glyphs[c]
        except KeyError:
            mask = self._fonts[self._mode.font_height].build_glyph(
                                        c, self._mode.font_width*2, self._mode.font_height)
            self._glyphs[c] = mask
            if self._mode.is_text_mode:
                self._queues.video.put(signals.Event(
                        signals.VIDEO_BUILD_GLYPHS, {self._codepage.to_unicode(c, u'\0'): mask}))
        return mask

    if numpy:
        def to_rect(self, row, col, mask, fore, back):
            """Return a sprite for a given character """
            # set background
            glyph = numpy.full(mask.shape, back)
            # stamp foreground mask
            glyph[mask] = fore
            x0, y0 = (col-1) * self._mode.font_width, (row-1) * self._mode.font_height
            x1, y1 = x0 + mask.shape[1] - 1, y0 + mask.shape[0] - 1
            return x0, y0, x1, y1, glyph
    else:
        def to_rect(self, row, col, mask, fore, back):
            """Return a sprite for a given character """
            glyph = [[(fore if bit else back) for bit in row] for row in mask]
            x0, y0 = (col-1) * self._mode.font_width, (row-1) * self._mode.font_height
            x1, y1 = x0 + len(mask[0]) - 1, y0 + len(mask) - 1
            return x0, y0, x1, y1, glyph
