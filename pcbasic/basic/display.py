"""
PC-BASIC - display.py
Text and graphics buffer, cursor and screen operations

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import struct

try:
    import numpy
except ImportError:
    numpy = None

from . import signals
from . import error
from . import modes
from . import font
from . import graphics
from . import values
from . import tokens as tk

# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
carry_col_9_chars = [chr(c) for c in range(0xb0, 0xdf+1)]
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
carry_row_9_chars = [chr(c) for c in range(0xb0, 0xdf+1)]


###############################################################################
# screen buffer

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

###############################################################################
# screen operations

class Screen(object):
    """Screen manipulation operations."""

    # CGA mono intensities
    intensity16_mono = range(0x00, 0x100, 0x11)
    # CGA colours
    colours16_colour = (
        (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
        (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0x55,0x00), (0xaa,0xaa,0xaa),
        (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
        (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) )
    # EGA colours
    colours64 = (
        (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
        (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0xaa,0x00), (0xaa,0xaa,0xaa),
        (0x00,0x00,0x55), (0x00,0x00,0xff), (0x00,0xaa,0x55), (0x00,0xaa,0xff),
        (0xaa,0x00,0x55), (0xaa,0x00,0xff), (0xaa,0xaa,0x55), (0xaa,0xaa,0xff),
        (0x00,0x55,0x00), (0x00,0x55,0xaa), (0x00,0xff,0x00), (0x00,0xff,0xaa),
        (0xaa,0x55,0x00), (0xaa,0x55,0xaa), (0xaa,0xff,0x00), (0xaa,0xff,0xaa),
        (0x00,0x55,0x55), (0x00,0x55,0xff), (0x00,0xff,0x55), (0x00,0xff,0xff),
        (0xaa,0x55,0x55), (0xaa,0x55,0xff), (0xaa,0xff,0x55), (0xaa,0xff,0xff),
        (0x55,0x00,0x00), (0x55,0x00,0xaa), (0x55,0xaa,0x00), (0x55,0xaa,0xaa),
        (0xff,0x00,0x00), (0xff,0x00,0xaa), (0xff,0xaa,0x00), (0xff,0xaa,0xaa),
        (0x55,0x00,0x55), (0x55,0x00,0xff), (0x55,0xaa,0x55), (0x55,0xaa,0xff),
        (0xff,0x00,0x55), (0xff,0x00,0xff), (0xff,0xaa,0x55), (0xff,0xaa,0xff),
        (0x55,0x55,0x00), (0x55,0x55,0xaa), (0x55,0xff,0x00), (0x55,0xff,0xaa),
        (0xff,0x55,0x00), (0xff,0x55,0xaa), (0xff,0xff,0x00), (0xff,0xff,0xaa),
        (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
        (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) )

    def __init__(self, session, initial_width, video_mem_size, capabilities, monitor, sound, redirect, fkey_macros,
                cga_low, mono_tint, screen_aspect, codepage, font_family, warn_fonts):
        """Minimal initialisiation of the screen."""
        # emulated video card - cga, ega, etc
        if capabilities == 'ega' and monitor == 'mono':
            capabilities = 'ega_mono'
        # initialise the 4-colour CGA palette
        # palette 1: Black, Ugh, Yuck, Bleah, choice of low & high intensity
        # palette 0: Black, Green, Red, Brown/Yellow, low & high intensity
        # tandy/pcjr have high-intensity white, but low-intensity colours
        # mode 5 (SCREEN 1 + colorburst on RGB) has red instead of magenta
        if capabilities in ('pcjr', 'tandy'):
            # pcjr does not have mode 5
            self.cga4_palettes = {0: (0, 2, 4, 6), 1: (0, 3, 5, 15), 5: None}
        elif cga_low:
            self.cga4_palettes = {0: (0, 2, 4, 6), 1: (0, 3, 5, 7), 5: (0, 3, 4, 7)}
        else:
            self.cga4_palettes = {0: (0, 10, 12, 14), 1: (0, 11, 13, 15), 5: (0, 11, 12, 15)}
        # build 16-greyscale and 16-colour sets
        self.colours16_mono = tuple(tuple(tint*i//255 for tint in mono_tint)
                               for i in self.intensity16_mono)
        if monitor == 'mono':
            self.colours16 = list(self.colours16_mono)
        else:
            self.colours16 = list(self.colours16_colour)
        self.capabilities = capabilities
        # emulated monitor type - rgb, composite, mono
        self.monitor = monitor
        # screen aspect ratio, for CIRCLE
        self.screen_aspect = screen_aspect
        self.screen_mode = 0
        self.colorswitch = 1
        self.apagenum = 0
        self.vpagenum = 0
        # current attribute
        self.attr = 7
        # border attribute
        self.border_attr = 0
        self.video_mem_size = video_mem_size
        # prepare video modes
        self.cga_mode_5 = False
        self.cga4_palette = list(self.cga4_palettes[1])
        self.mono_tint = mono_tint
        self.prepare_modes()
        self.mode = self.text_data[initial_width]
        # cursor
        self.cursor = Cursor(self)
        # current row and column
        self.current_row = 1
        self.current_col = 1
        # set codepage for video plugin
        self.codepage = codepage
        # session dependence only for queues
        self.session = session
        self.session.video_queue.put(signals.Event(
                signals.VIDEO_SET_CODEPAGE, self.codepage))
        # prepare fonts
        heights_needed = set([8])
        for mode in self.text_data.values():
            heights_needed.add(mode.font_height)
        for mode in self.mode_data.values():
            heights_needed.add(mode.font_height)
        # load the graphics fonts, including the 8-pixel RAM font
        # use set() for speed - lookup is O(1) rather than O(n) for list
        chars_needed = set(self.codepage.cp_to_unicode.values())
        # break up any grapheme clusters and add components to set of needed glyphs
        chars_needed |= set(c for cluster in chars_needed if len(cluster) > 1 for c in cluster)
        self.fonts = font.load_fonts(font_family, heights_needed,
                    chars_needed, self.codepage.substitutes, warn_fonts)
        # text viewport parameters
        self.view_start = 1
        self.scroll_height = 24
        # viewport has been set
        self.view_set = False
        # writing on bottom row is allowed
        self.bottom_row_allowed = False
        # true if we're on 80 but should be on 81
        self.overflow = False
        # needed for printing \a
        self.sound = sound
        # output redirection
        self.redirect = redirect
        # function key macros
        self.fkey_macros = fkey_macros
        # print screen target, to be set later due to init order issues
        self.lpt1_file = None
        self.drawing = graphics.Drawing(self)
        # initialise a fresh textmode screen
        self.set_mode(self.mode, 0, 1, 0, 0)

    def prepare_modes(self):
        """Build lists of allowed graphics modes."""
        self.text_data, self.mode_data = modes.get_modes(self,
                    self.cga4_palette, self.video_mem_size,
                    self.capabilities, self.mono_tint, self.screen_aspect)

    def rebuild(self):
        """Rebuild the screen from scratch."""
        # set the codepage
        self.session.video_queue.put(signals.Event(
                signals.VIDEO_SET_CODEPAGE, self.codepage))
        # set the screen mode
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_MODE, self.mode))
        if self.mode.is_text_mode:
            # send glyphs to signals; copy is necessary
            # as dict may change here while the other thread is working on it
            self.session.video_queue.put(signals.Event(signals.VIDEO_BUILD_GLYPHS,
                    dict((k,v) for k,v in self.glyphs.iteritems())))
        # set the visible and active pages
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)))
        # rebuild palette
        self.palette.set_all(self.palette.palette, check_mode=False)
        # fix the cursor
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                (self.cursor.width, self.mode.font_height,
                 self.cursor.from_line, self.cursor.to_line)))
        self.session.video_queue.put(signals.Event(signals.VIDEO_MOVE_CURSOR,
                (self.current_row, self.current_col)))
        if self.mode.is_text_mode:
            fore, _, _, _ = self.split_attr(
                self.apage.row[self.current_row-1].buf[self.current_col-1][1] & 0xf)
        else:
            fore, _, _, _ = self.split_attr(self.mode.cursor_index or self.attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))
        self.cursor.reset_visibility()
        # set the border
        fore, _, _, _ = self.split_attr(self.border_attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, fore))
        # redraw the text screen and rebuild text buffers in video plugin
        for pagenum in range(self.mode.num_pages):
            for crow in range(self.mode.height):
                # for_keys=True means 'suppress echo on cli'
                self.refresh_range(pagenum, crow+1, 1, self.mode.width,
                                   for_keys=True, text_only=True)
            # redraw graphics
            if not self.mode.is_text_mode:
                self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_RECT, (pagenum, 0, 0,
                                self.mode.pixel_width-1, self.mode.pixel_height-1,
                                self.pixels.pages[pagenum].buffer)))

    def screen_(self,args):
        """SCREEN: change the video mode, colourburst, visible or active page."""
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        mode = next(args)
        colorswitch = next(args)
        apagenum = next(args)
        vpagenum = next(args)
        # if any parameter not in [0,255], error 5 without doing anything
        # if the parameters are outside narrow ranges
        # (e.g. not implemented screen mode, pagenum beyond max)
        # then the error is only raised after changing the palette.
        error.range_check(0, 255, mode, colorswitch, apagenum, vpagenum)
        if self.capabilities == 'tandy':
            error.range_check(0, 1, colorswitch)
        erase = next(args)
        error.range_check(0, 2, erase)
        list(args)
        if erase is not None:
            # erase can only be set on pcjr/tandy 5-argument syntax
            if self.capabilities not in ('pcjr', 'tandy'):
                raise error.RunError(error.IFC)
        else:
            erase = 1
        # decide whether to redraw the screen
        oldmode, oldcolor = self.mode, self.colorswitch
        self.screen(mode, colorswitch, apagenum, vpagenum, erase)
        if ((not self.mode.is_text_mode and self.mode.name != oldmode.name) or
                (self.mode.is_text_mode and not oldmode.is_text_mode) or
                (self.mode.width != oldmode.width) or
                (self.colorswitch != oldcolor)):
            # rebuild the console if we've switched modes or colorswitch
            self.init_mode()

    def screen(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum,
               erase=1, new_width=None):
        """Change the video mode, colourburst, visible or active page."""
        # reset palette happens even if the SCREEN call fails
        self.palette = Palette(self.mode, self.capabilities)
        # set default arguments
        if new_mode is None:
            new_mode = self.screen_mode
        # THIS IS HOW COLORSWITCH SHOULD WORK:
        #   SCREEN 0,0 - mono on composite, color on RGB
        #   SCREEN 0,1 - color (colorburst=True)
        #   SCREEN 1,0 - color (colorburst=True)
        #   SCREEN 1,1 - mono on composite, mode 5 on RGB
        # default colorswitch:
        #   SCREEN 0 = SCREEN 0,0 (pcjr)
        #   SCREEN 0 = SCREEN 0,1 (tandy, cga, ega, vga, ..)
        #   SCREEN 1 = SCREEN 1,0 (pcjr, tandy)
        #   SCREEN 1 = SCREEN 1,1 (cga, ega, vga, ...)
        # colorswitch is NOT preserved between screens when unspecified
        # colorswitch is NOT the same as colorburst (opposite on screen 1)
        if new_colorswitch is None:
            if self.capabilities == 'pcjr':
                new_colorswitch = 0
            elif self.capabilities == 'tandy':
                new_colorswitch = not new_mode
            else:
                new_colorswitch = 1
        new_colorswitch = (new_colorswitch != 0)
        if new_mode == 0 and new_width is None:
            # width persists on change to screen 0
            new_width = self.mode.width
            # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
            if new_width == 20:
                new_width = 40
        # retrieve the specs for the new video mode
        try:
            if new_mode != 0:
                info = self.mode_data[new_mode]
            else:
                info = self.text_data[new_width]
        except KeyError:
            # no such mode
            raise error.RunError(error.IFC)
        # vpage and apage nums are persistent on mode switch with SCREEN
        # on pcjr only, reset page to zero if current page number would be too high.
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
            if (self.capabilities == 'pcjr' and info and
                    new_vpagenum >= info.num_pages):
                new_vpagenum = 0
        if new_apagenum is None:
            new_apagenum = self.apagenum
            if (self.capabilities == 'pcjr' and info and
                    new_apagenum >= info.num_pages):
                new_apagenum = 0
        if ((not info.is_text_mode and info.name != self.mode.name) or
                (info.is_text_mode and not self.mode.is_text_mode) or
                (info.width != self.mode.width) or
                (new_colorswitch != self.colorswitch)):
            # Erase tells basic how much video memory to erase
            # 0: do not erase video memory
            # 1: (default) erase old and new page if screen or width changes
            # 2: erase all video memory if screen or width changes
            # -> we're not distinguishing between 1 and 2 here
            if (erase == 0 and self.mode.video_segment == info.video_segment):
                save_mem = self.mode.get_memory(
                                self.mode.video_segment*0x10, self.video_mem_size)
            else:
                save_mem = None
            self.set_mode(info, new_mode, new_colorswitch,
                          new_apagenum, new_vpagenum)
            if save_mem:
                self.mode.set_memory(self.mode.video_segment*0x10, save_mem)
        else:
            # only switch pages
            if (new_apagenum >= info.num_pages or
                    new_vpagenum >= info.num_pages):
                raise error.RunError(error.IFC)
            self.set_page(new_vpagenum, new_apagenum)

    def set_mode(self, mode_info, new_mode, new_colorswitch,
                 new_apagenum, new_vpagenum):
        """Change the video mode, colourburst, visible or active page."""
        # reset palette happens even if the SCREEN call fails
        self.set_cga4_palette(1)
        # if the new mode has fewer pages than current vpage/apage,
        # illegal fn call before anything happens.
        # signal the signals to change the screen resolution
        if (not mode_info or
                new_apagenum >= mode_info.num_pages or
                new_vpagenum >= mode_info.num_pages):
            raise error.RunError(error.IFC)
        # preload SBCS glyphs
        try:
            self.glyphs = {
                chr(c): self.fonts[mode_info.font_height].build_glyph(self.codepage.to_unicode(chr(c), u'\0'),
                                mode_info.font_width, mode_info.font_height,
                                chr(c) in carry_col_9_chars, chr(c) in carry_row_9_chars)
                for c in range(256) }
        except (KeyError, AttributeError):
            logging.warning(
                'No %d-pixel font available. Could not enter video mode %s.',
                mode_info.font_height, mode_info.name)
            raise error.RunError(error.IFC)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_MODE, mode_info))
        if mode_info.is_text_mode:
            # send glyphs to signals; copy is necessary
            # as dict may change here while the other thread is working on it
            self.session.video_queue.put(signals.Event(signals.VIDEO_BUILD_GLYPHS,
                                                                self.glyphs))
        # attribute and border persist on width-only change
        if (not (self.mode.is_text_mode and mode_info.is_text_mode) or
                self.apagenum != new_apagenum or self.vpagenum != new_vpagenum
                or self.colorswitch != new_colorswitch):
            self.attr = mode_info.attr
        if (not (self.mode.is_text_mode and mode_info.is_text_mode) and
                mode_info.name != self.mode.name):
            # start with black border
            self.set_border(0)
        # set the screen parameters
        self.screen_mode = new_mode
        self.colorswitch = new_colorswitch
        # set all state vars
        self.mode = mode_info
        # build the screen buffer
        self.text = TextBuffer(self.attr, self.mode.width,
                               self.mode.height, self.mode.num_pages,
                               (self.mode.font_height >= 14),
                               self.codepage)
        if not self.mode.is_text_mode:
            self.pixels = PixelBuffer(self.mode.pixel_width, self.mode.pixel_height,
                                    self.mode.num_pages, self.mode.bitsperpixel)
        # ensure current position is not outside new boundaries
        self.current_row, self.current_col = 1, 1
        # set active page & visible page, counting from 0.
        self.set_page(new_vpagenum, new_apagenum)
        # set graphics characteristics
        self.graph_view = graphics.GraphicsViewPort(self)
        self.drawing.init_mode()
        # cursor width starts out as single char
        self.cursor.init_mode(self.mode)
        self.palette = Palette(self.mode, self.capabilities)
        # set the attribute
        if not self.mode.is_text_mode:
            fore, _, _, _ = self.split_attr(self.mode.cursor_index or self.attr)
            self.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if self.mode.is_text_mode:
            self.set_colorburst(new_colorswitch)
        elif self.mode.name == '320x200x4':
            self.set_colorburst(not new_colorswitch)
        elif self.mode.name == '640x200x2':
            self.set_colorburst(False)

    def set_width(self, to_width):
        """Set the character width of the screen, reset pages and change modes."""
        # raise an error if the width value doesn't make sense
        if to_width not in (20, 40, 80):
            raise error.RunError(error.IFC)
        # if we're currently at that width, do nothing
        if to_width == self.mode.width:
            return
        if to_width == 20:
            if self.capabilities in ('pcjr', 'tandy'):
                self.screen(3, None, 0, 0)
            else:
                raise error.RunError(error.IFC)
        elif self.mode.is_text_mode:
            self.screen(0, None, 0, 0, new_width=to_width)
        elif to_width == 40:
            if self.mode.name == '640x200x2':
                self.screen(1, None, 0, 0)
            elif self.mode.name == '160x200x16':
                self.screen(1, None, 0, 0)
            elif self.mode.name == '640x200x4':
                self.screen(5, None, 0, 0)
            elif self.mode.name == '640x200x16':
                self.screen(7, None, 0, 0)
            elif self.mode.name == '640x350x16':
                # screen 9 switches to screen 1 (not 7) on WIDTH 40
                self.screen(1, None, 0, 0)
        elif to_width == 80:
            if self.mode.name == '320x200x4':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '160x200x16':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '320x200x4pcjr':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '320x200x16pcjr':
                self.screen(6, None, 0, 0)
            elif self.mode.name == '320x200x16':
                self.screen(8, None, 0, 0)
        else:
            raise error.RunError(error.IFC)
        self.init_mode()

    def init_mode(self):
        """Initialisation when we switched to new screen mode."""
        # redraw key line
        self.fkey_macros.redraw_keys(self)
        # rebuild build the cursor;
        # first move to home in case the screen has shrunk
        self.set_pos(1, 1)
        # there is only one VIEW PRINT setting across all pages.
        if self.scroll_height == 25:
            # tandy/pcjr special case: VIEW PRINT to 25 is preserved
            self.set_view(1, 25)
        else:
            self.unset_view()
        self.cursor.set_default_shape(True)
        self.cursor.reset_visibility()

    def set_colorburst(self, on=True):
        """Set the composite colorburst bit."""
        # On a composite monitor:
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        colorburst_capable = self.capabilities in (
                                    'cga', 'cga_old', 'tandy', 'pcjr')
        if self.mode.name == '320x200x4' and self.monitor != 'composite':
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self.cga_mode_5 = not on
            self.set_cga4_palette(1)
        elif self.monitor != 'mono' and (on or self.monitor != 'composite'):
            self.colours16[:] = self.colours16_colour
        else:
            self.colours16[:] = self.colours16_mono
        # reset the palette to reflect the new mono or mode-5 situation
        self.palette = Palette(self.mode, self.capabilities)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_COLORBURST, (on and colorburst_capable,
                            self.palette.rgb_palette, self.palette.rgb_palette1)))

    def set_cga4_palette(self, num):
        """set the default 4-colour CGA palette."""
        self.cga4_palette_num = num
        # we need to copy into cga4_palette as it's referenced by mode.palette
        if self.cga_mode_5 and self.capabilities in ('cga', 'cga_old'):
            self.cga4_palette[:] = self.cga4_palettes[5]
        else:
            self.cga4_palette[:] = self.cga4_palettes[num]

    def set_video_memory_size(self, new_size):
        """Change the amount of memory available to the video card."""
        self.video_mem_size = new_size
        # redefine number of available video pages
        self.prepare_modes()
        # text screen modes don't depend on video memory size
        if self.screen_mode == 0:
            return True
        # check if we need to drop out of our current mode
        page = max(self.vpagenum, self.apagenum)
        # reload max number of pages; do we fit? if not, drop to text
        new_mode = self.mode_data[self.screen_mode]
        if (page >= new_mode.num_pages):
            return False
        self.mode = new_mode
        return True

    def set_page(self, new_vpagenum, new_apagenum):
        """Set active page & visible page, counting from 0."""
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
        if new_apagenum is None:
            new_apagenum = self.apagenum
        if (new_vpagenum >= self.mode.num_pages or new_apagenum >= self.mode.num_pages):
            raise error.RunError(error.IFC)
        self.vpagenum = new_vpagenum
        self.apagenum = new_apagenum
        self.vpage = self.text.pages[new_vpagenum]
        self.apage = self.text.pages[new_apagenum]
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_PAGE, (new_vpagenum, new_apagenum)))

    def set_attr(self, attr):
        """Set the default attribute."""
        self.attr = attr
        if not self.mode.is_text_mode and self.mode.cursor_index is None:
            fore, _, _, _ = self.split_attr(attr)
            self.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))

    def set_border(self, attr):
        """Set the border attribute."""
        self.border_attr = attr
        fore, _, _, _ = self.split_attr(attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, fore))

    def pcopy_(self, args):
        """Copy source to destination page."""
        src = values.to_int(next(args))
        error.range_check(0, self.mode.num_pages-1, src)
        dst = values.to_int(next(args))
        list(args)
        error.range_check(0, self.mode.num_pages-1, dst)
        self.text.copy_page(src, dst)
        if not self.mode.is_text_mode:
            self.pixels.copy_page(src, dst)
        self.session.video_queue.put(signals.Event(signals.VIDEO_COPY_PAGE, (src, dst)))

    def color_(self, args):
        """COLOR: set colour attributes."""
        args = list(args)
        error.throw_if(len(args) > 3)
        args += [None] * (3-len(args))
        fore, back, bord = args
        mode = self.mode
        if fore is None:
            fore = (self.attr>>7) * 0x10 + (self.attr & 0xf)
        if back is None:
            # graphics mode bg is always 0; sets palette instead
            if mode.is_text_mode:
                back = (self.attr>>4) & 0x7
            else:
                back = self.palette.get_entry(0)
        if mode.name == '320x200x4':
            self._color_mode_1(fore, back, bord)
        elif mode.name in ('640x200x2', '720x348x2'):
            # screen 2; hercules: illegal fn call
            raise error.RunError(error.IFC)
        else:
            # for screens other than 1, no distinction between 3rd parm zero and not supplied
            bord = bord or 0
            error.range_check(0, 255, bord)
            if mode.is_text_mode:
                error.range_check(0, mode.num_attr-1, fore)
                error.range_check(0, 15, back, bord)
                self.set_attr(((0x8 if (fore > 0xf) else 0x0) + (back & 0x7))*0x10
                                + (fore & 0xf))
                self.set_border(bord)
            elif mode.name in ('160x200x16', '320x200x4pcjr', '320x200x16pcjr'
                                '640x200x4', '320x200x16', '640x200x16'):
                error.range_check(1, mode.num_attr-1, fore)
                error.range_check(0, mode.num_attr-1, back)
                self.set_attr(fore)
                # in screen 7 and 8, only low intensity palette is used.
                self.palette.set_entry(0, back % 8, check_mode=False)
            elif mode.name in ('640x350x16', '640x350x4'):
                error.range_check(1, mode.num_attr-1, fore)
                error.range_check(0, len(mode.colours)-1, back)
                self.set_attr(fore)
                self.palette.set_entry(0, back, check_mode=False)
            elif mode.name == '640x400x2':
                error.range_check(0, len(mode.colours)-1, fore)
                if back != 0:
                    raise error.RunError(error.IFC)
                self.palette.set_entry(1, fore, check_mode=False)

    def _color_mode_1(self, back, pal, override):
        """Helper function for COLOR in SCREEN 1."""
        back = self.palette.get_entry(0) if back is None else back
        if override is not None:
            # uses last entry as palette if given
            pal = override
        error.range_check(0, 255, back)
        if pal is not None:
            error.range_check(0, 255, pal)
            self.set_cga4_palette(pal%2)
            palette = list(self.mode.palette)
            palette[0] = back & 0xf
            # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
            # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15
            self.palette.set_all(palette, check_mode=False)
        else:
            self.palette.set_entry(0, back & 0xf, check_mode=False)

    def cls_(self, args):
        """CLS: clear the screen."""
        val = next(args)
        if val is not None:
            # tandy gives illegal function call on CLS number
            error.throw_if(self.capabilities == 'tandy')
            error.range_check(0, 2, val)
        else:
            if self.graph_view.is_set():
                val = 1
            elif self.view_set:
                val = 2
            else:
                val = 0
        list(args)
        # cls is only executed if no errors have occurred
        if val == 0:
            self.clear()
            self.fkey_macros.redraw_keys(self)
            self.drawing.reset()
        elif val == 1:
            self.graph_view.clear()
            self.drawing.reset()
        elif val == 2:
            self.clear_view()

    #####################
    # screen read/write

    def write(self, s, scroll_ok=True, do_echo=True):
        """Write a string to the screen at the current position."""
        if do_echo:
            # CR -> CRLF, CRLF -> CRLF LF
            self.redirect.write(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
        last = ''
        # if our line wrapped at the end before, it doesn't anymore
        self.apage.row[self.current_row-1].wrap = False
        for c in s:
            row, col = self.current_row, self.current_col
            if c == '\t':
                # TAB
                num = (8 - (col - 1 - 8 * int((col-1) / 8)))
                for _ in range(num):
                    self.write_char(' ')
            elif c == '\n':
                # LF
                # exclude CR/LF
                if last != '\r':
                    # LF connects lines like word wrap
                    self.apage.row[row-1].wrap = True
                    self.set_pos(row + 1, 1, scroll_ok)
            elif c == '\r':
                # CR
                self.apage.row[row-1].wrap = False
                self.set_pos(row + 1, 1, scroll_ok)
            elif c == '\a':
                # BEL
                self.sound.play_alert()
            elif c == '\x0B':
                # HOME
                self.set_pos(1, 1, scroll_ok)
            elif c == '\x0C':
                # CLS
                self.clear_view()
            elif c == '\x1C':
                # RIGHT
                self.set_pos(row, col + 1, scroll_ok)
            elif c == '\x1D':
                # LEFT
                self.set_pos(row, col - 1, scroll_ok)
            elif c == '\x1E':
                # UP
                self.set_pos(row - 1, col, scroll_ok)
            elif c == '\x1F':
                # DOWN
                self.set_pos(row + 1, col, scroll_ok)
            else:
                # includes \b, \0, and non-control chars
                self.write_char(c)
            last = c

    def write_line(self, s='', scroll_ok=True, do_echo=True):
        """Write a string to the screen and end with a newline."""
        self.write(s, scroll_ok, do_echo)
        if do_echo:
            self.redirect.write('\r\n')
        self.check_pos(scroll_ok=True)
        self.apage.row[self.current_row-1].wrap = False
        self.set_pos(self.current_row + 1, 1)

    def list_line(self, line, newline=True):
        """Print a line from a program listing or EDIT prompt."""
        # no wrap if 80-column line, clear row before printing.
        # replace LF CR with LF
        line = line.replace('\n\r', '\n')
        cuts = line.split('\n')
        for i, l in enumerate(cuts):
            # clear_line looks back along wraps, use screen.clear_from instead
            self.clear_from(self.current_row, 1)
            self.write(str(l))
            if i != len(cuts)-1:
                self.write('\n')
        if newline:
            self.write_line()
        # remove wrap after 80-column program line
        if len(line) == self.mode.width and self.current_row > 2:
            self.apage.row[self.current_row-3].wrap = False

    def write_char(self, c, do_scroll_down=False):
        """Put one character at the current position."""
        # check if scroll& repositioning needed
        if self.overflow:
            self.current_col += 1
            self.overflow = False
        # see if we need to wrap and scroll down
        self._check_wrap(do_scroll_down)
        # move cursor and see if we need to scroll up
        self.check_pos(scroll_ok=True)
        # put the character
        self.put_char_attr(self.apagenum,
                self.current_row, self.current_col, c, self.attr)
        # adjust end of line marker
        if (self.current_col >
                self.apage.row[self.current_row-1].end):
             self.apage.row[self.current_row-1].end = self.current_col
        # move cursor. if on col 80, only move cursor to the next row
        # when the char is printed
        if self.current_col < self.mode.width:
            self.current_col += 1
        else:
            self.overflow = True
        # move cursor and see if we need to scroll up
        self.check_pos(scroll_ok=True)

    def _check_wrap(self, do_scroll_down):
        """Wrap if we need to."""
        if self.current_col > self.mode.width:
            if self.current_row < self.mode.height:
                # wrap line
                self.apage.row[self.current_row-1].wrap = True
                if do_scroll_down:
                    # scroll down (make space by shifting the next rows down)
                    if self.current_row < self.scroll_height:
                        self.scroll_down(self.current_row+1)
                # move cursor and reset cursor attribute
                self.move_cursor(self.current_row + 1, 1)
            else:
                self.current_col = self.mode.width

    def start_line(self):
        """Move the cursor to the start of the next line, this line if empty."""
        if self.current_col != 1:
            self.redirect.write('\r\n')
            self.check_pos(scroll_ok=True)
            self.set_pos(self.current_row + 1, 1)
        # ensure line above doesn't wrap
        self.apage.row[self.current_row-2].wrap = False

    def locate_(self, args):
        """LOCATE: Set cursor position, shape and visibility."""
        args = list(args)
        args = args + [None] * (5-len(args))
        row, col, cursor, start, stop = args
        row = self.current_row if row is None else row
        col = self.current_col if col is None else col
        cmode = self.mode
        error.throw_if(row == cmode.height and self.fkey_macros.keys_visible)
        if self.view_set:
            error.range_check(self.view_start, self.scroll_height, row)
        else:
            error.range_check(1, cmode.height, row)
        error.range_check(1, cmode.width, col)
        if row == cmode.height:
            # temporarily allow writing on last row
            self.bottom_row_allowed = True
        self.set_pos(row, col, scroll_ok=False)
        if cursor is not None:
            error.range_check(0, (255 if self.capabilities in ('pcjr', 'tandy') else 1), cursor)
            # set cursor visibility - this should set the flag but have no effect in graphics modes
            self.cursor.set_visibility(cursor != 0)
        error.throw_if(start is None and stop is not None)
        if stop is None:
            stop = start
        if start is not None:
            error.range_check(0, 31, start, stop)
            # cursor shape only has an effect in text mode
            if cmode.is_text_mode:
                self.cursor.set_shape(start, stop)

    def set_pos(self, to_row, to_col, scroll_ok=True):
        """Set the current position."""
        self.overflow = False
        self.current_row, self.current_col = to_row, to_col
        # this may alter self.current_row, self.current_col
        self.check_pos(scroll_ok)
        # move cursor and reset cursor attribute
        self.move_cursor(self.current_row, self.current_col)

    def check_pos(self, scroll_ok=True):
        """Check if we have crossed the screen boundaries and move as needed."""
        oldrow, oldcol = self.current_row, self.current_col
        if self.bottom_row_allowed:
            if self.current_row == self.mode.height:
                self.current_col = min(self.mode.width, self.current_col)
                if self.current_col < 1:
                    self.current_col += 1
                self.move_cursor(self.current_row, self.current_col)
                return self.current_col == oldcol
            else:
                # if row > height, we also end up here
                # (eg if we do INPUT on the bottom row)
                # adjust viewport if necessary
                self.bottom_row_allowed = False
        # see if we need to move to the next row
        if self.current_col > self.mode.width:
            if self.current_row < self.scroll_height or scroll_ok:
                # either we don't nee to scroll, or we're allowed to
                self.current_col -= self.mode.width
                self.current_row += 1
            else:
                # we can't scroll, so we just stop at the right border
                self.current_col = self.mode.width
        # see if we eed to move a row up
        elif self.current_col < 1:
            if self.current_row > self.view_start:
                self.current_col += self.mode.width
                self.current_row -= 1
            else:
                self.current_col = 1
        # see if we need to scroll
        if self.current_row > self.scroll_height:
            if scroll_ok:
                self.scroll()
            self.current_row = self.scroll_height
        elif self.current_row < self.view_start:
            self.current_row = self.view_start
        self.move_cursor(self.current_row, self.current_col)
        # signal position change
        return (self.current_row == oldrow and
                 self.current_col == oldcol)

    def screen_fn_(self, row, col, want_attr=None):
        """SCREEN: get char or attribute at a location."""
        new_int = row.new()
        row, col = row.to_int(), col.to_int()
        error.range_check(1, self.mode.height, row)
        error.range_check(1, self.mode.width, col)
        if want_attr:
            want_attr = want_attr.to_int()
            error.range_check(0, 255, want_attr)
        if self.view_set:
            error.range_check(self.view_start, self.scroll_height, row)
        if want_attr and not self.mode.is_text_mode:
            return new_int.from_int(0)
        else:
            return new_int.from_int(self.apage.get_char_attr(row, col, bool(want_attr)))

    def get_char_attr(self, pagenum, crow, ccol, want_attr):
        """Retrieve a byte from the screen."""
        return self.text.pages[pagenum].get_char_attr(crow, ccol, want_attr)

    def put_char_attr(self, pagenum, crow, ccol, c, cattr,
                            one_only=False, for_keys=False, force=False):
        """Put a byte to the screen, redrawing as necessary."""
        if not self.mode.is_text_mode:
            cattr = cattr & 0xf
            # always force drawing of spaces, it may have been overdrawn
            if c == ' ':
                force = True
        start, stop = self.text.pages[pagenum].put_char_attr(crow, ccol, c, cattr, one_only, force)
        # update the screen
        self.refresh_range(pagenum, crow, start, stop-1, for_keys)

    def refresh_range(self, pagenum, crow, start, stop, for_keys=False, text_only=False):
        """Redraw a section of a screen row, assuming DBCS buffer has been set."""
        therow = self.text.pages[pagenum].row[crow-1]
        ccol = start
        while ccol <= stop:
            double = therow.double[ccol-1]
            if double == 1:
                ca = therow.buf[ccol-1]
                da = therow.buf[ccol]
                r, c, char, attr = crow, ccol, ca[0]+da[0], da[1]
                therow.double[ccol-1] = 1
                therow.double[ccol] = 2
                ccol += 2
            else:
                if double != 0:
                    logging.debug('DBCS buffer corrupted at %d, %d (%d)',
                                  crow, ccol, double)
                ca = therow.buf[ccol-1]
                r, c, char, attr = crow, ccol, ca[0], ca[1]
                ccol += 1
            fore, back, blink, underline = self.split_attr(attr)
            # ensure glyph is stored
            mask = self.get_glyph(char)
            self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_GLYPH,
                    (pagenum, r, c, char, len(char) > 1,
                                 fore, back, blink, underline, for_keys)))
            if not self.mode.is_text_mode and not text_only:
                # update pixel buffer
                x0, y0, x1, y1, sprite = self.glyph_to_rect(
                                                r, c, mask, fore, back)
                self.pixels.pages[self.apagenum].put_rect(
                                                x0, y0, x1, y1, sprite, tk.PSET)
                self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_RECT,
                                        (self.apagenum, x0, y0, x1, y1, sprite)))

    def redraw_row(self, start, crow, wrap=True):
        """Draw the screen row, wrapping around and reconstructing DBCS buffer."""
        while True:
            therow = self.apage.row[crow-1]
            for i in range(start, therow.end):
                # redrawing changes colour attributes to current foreground (cf. GW)
                # don't update all dbcs chars behind at each put
                self.put_char_attr(self.apagenum, crow, i+1,
                        therow.buf[i][0], self.attr, one_only=True, force=True)
            if (wrap and therow.wrap and
                    crow >= 0 and crow < self.text.height-1):
                crow += 1
                start = 0
            else:
                break

    def clear_from(self, srow, scol):
        """Clear from given position to end of logical line (CTRL+END)."""
        mode = self.mode
        therow = self.apage.row[srow-1]
        therow.buf = (therow.buf[:scol-1] +
            [(' ', self.attr)] * (mode.width-scol+1))
        therow.double = (therow.double[:scol-1] + [0] * (mode.width-scol+1))
        therow.end = min(therow.end, scol-1)
        crow = srow
        while self.apage.row[crow-1].wrap:
            crow += 1
            self.apage.row[crow-1].clear(self.attr)
        for r in range(crow, srow, -1):
            self.apage.row[r-1].wrap = False
            self.scroll(r)
        therow = self.apage.row[srow-1]
        therow.wrap = False
        self.set_pos(srow, scol)
        save_end = therow.end
        therow.end = mode.width
        if scol > 1:
            self.redraw_row(scol-1, srow)
        else:
            # inelegant: we're clearing the text buffer for a second time now
            self.clear_rows(srow, srow)
        therow.end = save_end

    def set_print_screen_target(self, lpt1_file):
        """Set stream for print_screen() """
        self.lpt1_file = lpt1_file

    def print_screen(self):
        """Output the visible page to LPT1."""
        if not self.lpt1_file:
            logging.debug('Print screen target not set.')
            return
        for crow in range(1, self.mode.height+1):
            line = ''
            for c, _ in self.vpage.row[crow-1].buf:
                line += c
            self.lpt1_file.write_line(line)

    def clear_text_at(self, x, y):
        """Remove the character covering a single pixel."""
        fx, fy = self.mode.font_width, self.mode.font_height
        cymax, cxmax = self.mode.height-1, self.mode.width-1
        cx, cy = x // fx, y // fy
        if cx >= 0 and cy >= 0 and cx <= cxmax and cy <= cymax:
            self.apage.row[cy].buf[cx] = (' ', self.attr)
        fore, back, blink, underline = self.split_attr(self.attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_GLYPH,
                (self.apagenum, cy+1, cx+1, ' ', False,
                             fore, back, blink, underline, True)))

    #MOVE to TextBuffer? replace with graphics_to_text_loc v.v.?
    def clear_text_area(self, x0, y0, x1, y1):
        """Remove all characters from the textbuffer on a rectangle of the graphics screen."""
        fx, fy = self.mode.font_width, self.mode.font_height
        cymax, cxmax = self.mode.height-1, self.mode.width-1
        cx0 = min(cxmax, max(0, x0 // fx))
        cy0 = min(cymax, max(0, y0 // fy))
        cx1 = min(cxmax, max(0, x1 // fx))
        cy1 = min(cymax, max(0, y1 // fy))
        for r in range(cy0, cy1+1):
            self.apage.row[r].buf[cx0:cx1+1] = [
                (' ', self.attr)] * (cx1 - cx0 + 1)

    def text_to_pixel_area(self, row0, col0, row1, col1):
        """Convert area from text buffer to area for pixel buffer."""
        # area bounds are all inclusive
        return ((col0-1)*self.mode.font_width, (row0-1)*self.mode.font_height,
                (col1-col0+1)*self.mode.font_width-1, (row1-row0+1)*self.mode.font_height-1)

    def clear_rows(self, start, stop):
        """Clear text and graphics on given (inclusive) text row range."""
        for r in self.apage.row[start-1:stop]:
            r.clear(self.attr)
        if not self.mode.is_text_mode:
            x0, y0, x1, y1 = self.text_to_pixel_area(
                            start, 1, stop, self.mode.width)
            # background attribute must be 0 in graphics mode
            self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, 0)
        _, back, _, _ = self.split_attr(self.attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_CLEAR_ROWS, (back, start, stop)))

    #MOVE to Cursor.move ?
    def move_cursor(self, row, col):
        """Move the cursor to a new position."""
        self.current_row, self.current_col = row, col
        self.session.video_queue.put(signals.Event(signals.VIDEO_MOVE_CURSOR, (row, col)))
        self.cursor.reset_attr()

    def rebuild_glyph(self, ordval):
        """Rebuild a text-mode character after POKE."""
        if self.mode.is_text_mode:
            # force rebuilding the character by deleting and requesting
            del self.glyphs[chr(ordval)]
            self.get_glyph(chr(ordval))

    ## text viewport / scroll area

    def view_print_(self, args):
        """VIEW PRINT: set scroll region."""
        start, stop = args
        if start is None and stop is None:
            self.unset_view()
        else:
            max_line = 25 if (self.capabilities in ('pcjr', 'tandy') and not self.fkey_macros.keys_visible) else 24
            error.range_check(1, max_line, start, stop)
            error.throw_if(stop < start)
            self.set_view(start, stop)

    def set_view(self, start, stop):
        """Set the scroll area."""
        self.view_set = True
        self.view_start = start
        self.scroll_height = stop
        #set_pos(start, 1)
        self.overflow = False
        self.move_cursor(start, 1)

    def unset_view(self):
        """Unset scroll area."""
        self.set_view(1, 24)
        self.view_set = False

    def clear_view(self):
        """Clear the scroll area."""
        if self.capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # keep background, set foreground to 7
            attr_save = self.attr
            self.set_attr(attr_save & 0x70 | 0x7)
        self.current_row = self.view_start
        self.current_col = 1
        if self.bottom_row_allowed:
            last_row = self.mode.height
        else:
            last_row = self.scroll_height
        for r in self.apage.row[self.view_start-1:
                        self.scroll_height]:
            # we're clearing the rows below, but don't set the wrap there
            r.wrap = False
        self.clear_rows(self.view_start, last_row)
        # ensure the cursor is show in the right position
        self.move_cursor(self.current_row, self.current_col)
        if self.capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # restore attr
            self.set_attr(attr_save)

    def clear(self):
        """Clear the screen."""
        save_view_set = self.view_set
        save_view_start = self.view_start
        save_scroll_height = self.scroll_height
        self.set_view(1, self.mode.height)
        self.clear_view()
        if save_view_set:
            self.set_view(save_view_start, save_scroll_height)
        else:
            self.unset_view()

    def scroll(self, from_line=None):
        """Scroll the scroll region up by one line, starting at from_line."""
        if from_line is None:
            from_line = self.view_start
        _, back, _, _ = self.split_attr(self.attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SCROLL_UP,
                    (from_line, self.scroll_height, back)))
        # sync buffers with the new screen reality:
        if self.current_row > from_line:
            self.current_row -= 1
        self.apage.row.insert(self.scroll_height,
                              TextRow(self.attr, self.mode.width))
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.text_to_pixel_area(from_line+1, 1,
                self.scroll_height, self.mode.width)
            tx0, ty0, _, _ = self.text_to_pixel_area(from_line, 1,
                self.scroll_height-1, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)
        del self.apage.row[from_line-1]

    def scroll_down(self,from_line):
        """Scroll the scroll region down by one line, starting at from_line."""
        _, back, _, _ = self.split_attr(self.attr)
        self.session.video_queue.put(signals.Event(signals.VIDEO_SCROLL_DOWN,
                    (from_line, self.scroll_height, back)))
        if self.current_row >= from_line:
            self.current_row += 1
        # sync buffers with the new screen reality:
        self.apage.row.insert(from_line - 1, TextRow(self.attr, self.mode.width))
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.text_to_pixel_area(from_line, 1,
                self.scroll_height-1, self.mode.width)
            tx0, ty0, _, _ = self.text_to_pixel_area(from_line+1, 1,
                self.scroll_height, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)
        del self.apage.row[self.scroll_height-1]

    def get_text(self, start_row, start_col, stop_row, stop_col):
        """Retrieve unicode text for copying."""
        r, c = start_row, start_col
        full = []
        clip = []
        if self.vpage.row[r-1].double[c-1] == 2:
            # include lead byte
            c -= 1
        if self.vpage.row[stop_row-1].double[stop_col-2] == 1:
            # include trail byte
            stop_col += 1
        while r < stop_row or (r == stop_row and c < stop_col):
            clip.append(self.vpage.row[r-1].buf[c-1][0])
            c += 1
            if c > self.vpage.row[r-1].end:
                if not self.vpage.row[r-1].wrap:
                    full.append(self.codepage.str_to_unicode(b''.join(clip)))
                    full.append('\n')
                    clip = []
                r += 1
                c = 1
        full.append(self.codepage.str_to_unicode(clip))
        return u''.join(full).replace(u'\0', u' ')

    def csrlin_(self):
        """CSRLIN: get the current screen row."""
        if (self.overflow and self.current_col == self.mode.width and
                                    self.current_row < self.scroll_height):
            # in overflow position, return row+1 except on the last row
            return self.current_row + 1
        return self.current_row

    def pos_(self, dummy=None):
        """POS: get the current screen column."""
        if self.current_col == self.mode.width and self.overflow:
            # in overflow position, return column 1.
            return 1
        return self.current_col

    ## graphics primitives

    def put_pixel(self, x, y, index, pagenum=None):
        """Put a pixel on the screen; empty character buffer."""
        if pagenum is None:
            pagenum = self.apagenum
        if self.graph_view.contains(x, y):
            self.pixels.pages[pagenum].put_pixel(x, y, index)
            self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_PIXEL, (pagenum, x, y, index)))
            self.clear_text_at(x, y)

    def get_pixel(self, x, y, pagenum=None):
        """Return the attribute a pixel on the screen."""
        if pagenum is None:
            pagenum = self.apagenum
        return self.pixels.pages[pagenum].get_pixel(x, y)

    def get_interval(self, pagenum, x, y, length):
        """Read a scanline interval into a list of attributes."""
        return self.pixels.pages[pagenum].get_interval(x, y, length)

    def put_interval(self, pagenum, x, y, colours, mask=0xff):
        """Write a list of attributes to a scanline interval."""
        x, y, colours = self.graph_view.clip_list(x, y, colours)
        newcolours = self.pixels.pages[pagenum].put_interval(x, y, colours, mask)
        self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_INTERVAL, (pagenum, x, y, newcolours)))
        self.clear_text_area(x, y, x+len(colours), y)

    def fill_interval(self, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""
        x0, x1, y = self.graph_view.clip_interval(x0, x1, y)
        self.pixels.pages[self.apagenum].fill_interval(x0, x1, y, index)
        self.session.video_queue.put(signals.Event(signals.VIDEO_FILL_INTERVAL,
                        (self.apagenum, x0, x1, y, index)))
        self.clear_text_area(x0, y, x1, y)

    def get_until(self, x0, x1, y, c):
        """Get the attribute values of a scanline interval."""
        return self.pixels.pages[self.apagenum].get_until(x0, x1, y, c)

    def get_rect(self, x0, y0, x1, y1):
        """Read a screen rect into an [y][x] array of attributes."""
        return self.pixels.pages[self.apagenum].get_rect(x0, y0, x1, y1)

    def put_rect(self, x0, y0, x1, y1, sprite, operation_token):
        """Apply an [y][x] array of attributes onto a screen rect."""
        x0, y0, x1, y1, sprite = self.graph_view.clip_area(x0, y0, x1, y1, sprite)
        rect = self.pixels.pages[self.apagenum].put_rect(x0, y0, x1, y1,
                                                        sprite, operation_token)
        self.session.video_queue.put(signals.Event(signals.VIDEO_PUT_RECT,
                              (self.apagenum, x0, y0, x1, y1, rect)))
        self.clear_text_area(x0, y0, x1, y1)

    def fill_rect(self, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""
        x0, y0, x1, y1 = self.graph_view.clip_rect(x0, y0, x1, y1)
        self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, index)
        self.session.video_queue.put(signals.Event(signals.VIDEO_FILL_RECT,
                                (self.apagenum, x0, y0, x1, y1, index)))
        self.clear_text_area(x0, y0, x1, y1)


    def point_(self, arg0, arg1=None):
        """POINT (1 argument): Return current coordinate (2 arguments): Return the attribute of a pixel."""
        if arg1 is None:
            new_sng = arg0.to_single().clone()
            if self.mode.is_text_mode:
                return new_sng.from_int(0)
            fn = values.to_int(arg0)
            if fn in (0, 1):
                return new_sng.from_value(self.drawing.last_point[fn])
            elif fn in (2, 3):
                return new_sng.from_value(self.drawing.get_window_logical(*self.drawing.last_point)[fn - 2])
            return new_sng.from_int(0)
        else:
            if self.mode.is_text_mode:
                raise error.RunError(error.IFC)
            new_int = arg0.to_integer().clone()
            x, y = values.csng_(arg0).to_value(), values.csng_(arg1).to_value()
            x, y = self.graph_view.coords(*self.drawing.get_window_physical(x, y))
            if x < 0 or x >= self.mode.pixel_width:
                return new_int.from_int(-1)
            if y < 0 or y >= self.mode.pixel_height:
                return new_int.from_int(-1)
            return new_int.from_int(self.get_pixel(x, y))

    def pmap_(self, coord, mode):
        """PMAP: convert between logical and physical coordinates."""
        # create a new Single for the return value
        fvalue = mode.to_single()
        mode = mode.to_int()
        error.range_check(0, 3, mode)
        if self.mode.is_text_mode:
            return fvalue.from_value(0)
        if mode == 0:
            value, _ = self.drawing.get_window_physical(values.csng_(coord).to_value(), 0.)
            return fvalue.from_value(value)
        elif mode == 1:
            _, value = self.drawing.get_window_physical(0., values.csng_(coord).to_value())
            return fvalue.from_value(value)
        elif mode == 2:
            value, _ = self.drawing.get_window_logical(values.to_int(coord), 0)
            return fvalue.from_value(value)
        elif mode == 3:
            _, value = self.drawing.get_window_logical(0, values.to_int(coord))
            return fvalue.from_value(value)

    # text

    def get_glyph(self, c):
        """Return a glyph mask for a given character """
        try:
            mask = self.glyphs[c]
        except KeyError:
            uc = self.codepage.to_unicode(c, u'\0')
            carry_col_9 = c in carry_col_9_chars
            carry_row_9 = c in carry_row_9_chars
            mask = self.fonts[self.mode.font_height].build_glyph(uc,
                                self.mode.font_width*2, self.mode.font_height,
                                carry_col_9, carry_row_9)
            self.glyphs[c] = mask
            if self.mode.is_text_mode:
                self.session.video_queue.put(signals.Event(signals.VIDEO_BUILD_GLYPHS,
                    {c: mask}))
        return mask

    if numpy:
        def glyph_to_rect(self, row, col, mask, fore, back):
            """Return a sprite for a given character """
            # set background
            glyph = numpy.full(mask.shape, back)
            # stamp foreground mask
            glyph[mask] = fore
            x0, y0 = (col-1) * self.mode.font_width, (row-1) * self.mode.font_height
            x1, y1 = x0 + mask.shape[1] - 1, y0 + mask.shape[0] - 1
            return x0, y0, x1, y1, glyph
    else:
        def glyph_to_rect(self, row, col, mask, fore, back):
            """Return a sprite for a given character """
            glyph = [[(fore if bit else back) for bit in row] for row in mask]
            x0, y0 = (col-1) * self.mode.font_width, (row-1) * self.mode.font_height
            x1, y1 = x0 + len(mask[0]) - 1, y0 + len(mask) - 1
            return x0, y0, x1, y1, glyph


    #MOVE to modes classes in modes.py
    def split_attr(self, attr):
        """Split attribute byte into constituent parts."""
        if self.mode.has_underline:
            # MDA text attributes: http://www.seasip.info/VintagePC/mda.html
            # see also http://support.microsoft.com/KB/35148
            # don't try to change this with PALETTE, it won't work correctly
            underline = (attr % 8) == 1
            blink = (attr & 0x80) != 0
            # background is almost always black
            back = 0
            # intensity set by bit 3
            fore = 1 if not (attr & 0x8) else 2
            # exceptions
            if attr in (0x00, 0x08, 0x80, 0x88):
                fore, back = 0, 0
            elif attr in (0x70, 0xf0):
                fore, back = 0, 1
            elif attr in (0x78, 0xf8):
                fore, back = 3, 1
        else:
            # 7  6 5 4  3 2 1 0
            # Bl b b b  f f f f
            back = (attr >> 4) & 7
            blink = (attr >> 7) == 1
            fore = attr & 0xf
            underline = False
        return fore, back, blink, underline


###############################################################################
# palette

class Palette(object):
    """Colour palette."""

    def __init__(self, mode, capabilities):
        """Initialise palette."""
        self.capabilities = capabilities
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
        self.mode.screen.session.video_queue.put(
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
        self.mode.screen.session.video_queue.put(
            signals.Event(signals.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def mode_allows_palette(self, mode):
        """Check if the video mode allows palette change."""
        # effective palette change is an error in CGA
        if self.capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.RunError(error.IFC)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif self.capabilities in ('tandy', 'pcjr') and mode.is_text_mode:
            return False
        else:
            return True

    def palette_(self, attrib, colour):
        """PALETTE: assign colour to attribute."""
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

    def palette_using_(self, array_name, start_indices, arrays):
        """PALETTE USING: set palette from array buffer."""
        num_palette_entries = self.mode.num_attr if self.mode.num_attr != 32 else 16
        try:
            dimensions = arrays.dimensions(array_name)
        except KeyError:
            raise error.RunError(error.IFC)
        error.throw_if(array_name[-1] != '%', error.TYPE_MISMATCH)
        lst = arrays.view_full_buffer(array_name)
        start = arrays.index(start_indices, dimensions)
        error.throw_if(arrays.array_len(dimensions) - start < num_palette_entries)
        new_palette = []
        for i in range(num_palette_entries):
            offset = (start+i) * 2
            ## signed int, as -1 means don't set
            val, = struct.unpack('<h', lst[offset:offset+2])
            error.range_check(-1, len(self.mode.colours)-1, val)
            new_palette.append(val if val > -1 else self.get_entry(i))
        self.set_all(new_palette)


###############################################################################
# cursor

class Cursor(object):
    """Manage the cursor."""

    def __init__(self, screen):
        """Initialise the cursor."""
        self.screen = screen
        # are we in parse mode? invisible unless visible_run is True
        self.default_visible = True
        # cursor visible in parse mode? user override
        self.visible_run = False
        # cursor shape
        self.from_line = 0
        self.to_line = 0
        self.width = screen.mode.font_width
        self.height = screen.mode.font_height

    def init_mode(self, mode):
        """Change the cursor for a new screen mode."""
        self.width = mode.font_width
        self.height = mode.font_height
        self.set_default_shape(True)
        self.reset_attr()

    def reset_attr(self):
        """Set the text cursor attribute to that of the current location."""
        if self.screen.mode.is_text_mode:
            fore, _, _, _ = self.screen.split_attr(self.screen.apage.row[
                    self.screen.current_row-1].buf[
                    self.screen.current_col-1][1] & 0xf)
            self.screen.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))

    def show(self, do_show):
        """Force cursor to be visible/invisible."""
        self.screen.session.video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, do_show))

    def set_visibility(self, visible_run):
        """Set default cursor visibility."""
        self.visible_run = visible_run
        self.reset_visibility()

    def reset_visibility(self):
        """Set cursor visibility to its default state."""
        # visible if in interactive mode, unless forced visible in text mode.
        visible = self.default_visible
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self.screen.mode.is_text_mode:
            visible = visible or self.visible_run
        self.screen.session.video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, visible))

    def set_shape(self, from_line, to_line):
        """Set the cursor shape."""
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        mode = self.screen.mode
        fx, fy = self.width, self.height
        # do all text modes with >8 pixels have an ega-cursor?
        if self.screen.capabilities in (
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
        self.screen.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                            (self.width, fy, self.from_line, self.to_line)))
        self.reset_attr()

    def set_default_shape(self, overwrite_shape):
        """Set the cursor to one of two default shapes."""
        if overwrite_shape:
            if not self.screen.mode.is_text_mode:
                # always a block cursor in graphics mode
                self.set_shape(0, self.height-1)
            elif self.screen.capabilities == 'ega':
                # EGA cursor is on second last line
                self.set_shape(self.height-2, self.height-2)
            elif self.height == 9:
                # Tandy 9-pixel fonts; cursor on 8th
                self.set_shape(self.height-2, self.height-2)
            else:
                # other cards have cursor on last line
                self.set_shape(self.height-1, self.height-1)
        else:
            # half-block cursor for insert
            self.set_shape(self.height//2, self.height-1)

    def set_width(self, num_chars):
        """Set the cursor with to num_chars characters."""
        new_width = num_chars * self.screen.mode.font_width
        # update cursor shape to new width if necessary
        if new_width != self.width:
            self.width = new_width
            self.screen.session.video_queue.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                    (self.width, self.height, self.from_line, self.to_line)))
            self.reset_attr()
