"""
PC-BASIC - display.py
Text and graphics buffer, cursor and video signals

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging

try:
    import numpy
except ImportError:
    numpy = None

import config
import backend
import state
import error
import typeface
import modes
import graphics
import clipboard
import unicodepage
import basictoken as tk

import video

# create the window icon
backend.icon = typeface.build_glyph('icon', {'icon':
    '\x00\x00\x7C\xE0\xC6\x60\xC6\x66\xC6\x6C\xC6\x78\xC6\x6C\x7C\xE6' +
    '\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00\xFF\x00'}, 16, 16)

def prepare():
    """ Prepare the video subsystem. """
    global egacursor
    global video_capabilities, composite_monitor, mono_monitor
    global fonts
    video_capabilities = config.get('video')
    # do all text modes with >8 pixels have an ega-cursor?
    egacursor = video_capabilities in (
        'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules')
    composite_monitor = config.get('monitor') == 'composite'
    mono_monitor = config.get('monitor') == 'mono'
    if video_capabilities == 'ega' and mono_monitor:
        video_capabilities = 'ega_mono'
    # set initial video mode
    state.console_state.screen = Screen(config.get('text-width'),
                                        config.get('video-memory'))
    backend.initial_mode = state.console_state.screen.mode
    heights_needed = set([8])
    for mode in state.console_state.screen.text_data.values():
        heights_needed.add(mode.font_height)
    for mode in state.console_state.screen.mode_data.values():
        heights_needed.add(mode.font_height)
    # load the graphics fonts, including the 8-pixel RAM font
    fonts = typeface.load_fonts(config.get('font'), heights_needed)
    fonts[9] = fonts[8]

def init(video_plugin):
    """ Initialise the video backend. """
    video.init(video_plugin)
    if not video.plugin.ok:
        video.close()
        return False

    #MOVE to backend or video_pygame
    # clipboard handler may need an initialised pygame screen
    # incidentally, we only need a clipboard handler when we use pygame
    # avoid error messages by not calling
    if video_plugin == 'pygame':
        backend.clipboard_handler = clipboard.get_handler()
    else:
        backend.clipboard_handler = clipboard.Clipboard()

    if state.loaded:
        # reload the screen in resumed state
        if not state.console_state.screen.resume():
            video.close()
            return False
    else:
        # initialise a fresh textmode screen
        info = state.console_state.screen.mode
        state.console_state.screen.set_mode(info, 0, 1, 0, 0)
    return True


###############################################################################
# screen buffer

class TextRow(object):
    """ Buffer for a single row of the screen. """

    def __init__(self, battr, bwidth):
        """ Set up screen row empty and unwrapped. """
        # screen buffer, initialised to spaces, dim white on black
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False

    def clear(self, battr):
        """ Clear the screen row buffer. Leave wrap untouched. """
        bwidth = len(self.buf)
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0


class TextPage(object):
    """ Buffer for a screen page. """

    def __init__(self, battr, bwidth, bheight, pagenum, do_dbcs):
        """ Initialise the screen buffer to given dimensions. """
        self.row = [TextRow(battr, bwidth) for _ in xrange(bheight)]
        self.width = bwidth
        self.height = bheight
        self.pagenum = pagenum
        self.do_dbcs = do_dbcs

    def get_char_attr(self, crow, ccol, want_attr):
        """ Retrieve a byte from the screen (SBCS or DBCS half-char). """
        ca = self.row[crow-1].buf[ccol-1][want_attr]
        return ca if want_attr else ord(ca)

    def put_char_attr(self, crow, ccol, c, cattr, one_only=False, force=False):
        """ Put a byte to the screen, reinterpreting SBCS and DBCS as necessary. """
        if self.row[crow-1].buf[ccol-1] == (c, cattr) and not force:
            # nothing to do
            return ccol, ccol
        # update the screen buffer
        self.row[crow-1].buf[ccol-1] = (c, cattr)
        # mark the replaced char for refreshing
        start, stop = ccol, ccol+1
        self.row[crow-1].double[ccol-1] = 0
        # mark out sbcs and dbcs characters
        if unicodepage.dbcs and self.do_dbcs:
            orig_col = ccol
            # replace chars from here until necessary to update double-width chars
            therow = self.row[crow-1]
            # replacing a trail byte? take one step back
            # previous char could be a lead byte? take a step back
            if (ccol > 1 and therow.double[ccol-2] != 2 and
                    (therow.buf[ccol-1][0] in unicodepage.trail or
                     therow.buf[ccol-2][0] in unicodepage.lead)):
                ccol -= 1
                start -= 1
            # check all dbcs characters between here until it doesn't matter anymore
            while ccol < self.width:
                c = therow.buf[ccol-1][0]
                d = therow.buf[ccol][0]
                if (c in unicodepage.lead and d in unicodepage.trail):
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
            if unicodepage.box_protect:
                ccol = start-2
                connecting = 0
                bset = -1
                while ccol < stop+2 and ccol < self.width:
                    c = therow.buf[ccol-1][0]
                    d = therow.buf[ccol][0]
                    if bset > -1 and unicodepage.connects(c, d, bset):
                        connecting += 1
                    else:
                        connecting = 0
                        bset = -1
                    if bset == -1:
                        for b in (0, 1):
                            if unicodepage.connects(c, d, b):
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
    """ Buffer for text on all screen pages. """

    def __init__(self, battr, bwidth, bheight, bpages, do_dbcs):
        """ Initialise the screen buffer to given pages and dimensions. """
        self.pages = [TextPage(battr, bwidth, bheight, num, do_dbcs)
                      for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap


class PixelBuffer(object):
    """ Buffer for graphics on all screen pages. """

    def __init__(self, bwidth, bheight, bpages, bitsperpixel):
        """ Initialise the graphics buffer to given pages and dimensions. """
        self.pages = [ PixelPage(bwidth, bheight, num, bitsperpixel) for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]

class PixelPage(object):
    """ Buffer for a screen page. """

    def __init__(self, bwidth, bheight, pagenum, bitsperpixel):
        """ Initialise the screen buffer to given dimensions. """
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
        """ Pickle the page. """
        pagedict = self.__dict__.copy()
        # lambdas can't be pickled
        pagedict['operations'] = None
        return pagedict

    def __setstate__(self, pagedict):
        """ Initialise from pickled page. """
        self.__dict__.update(pagedict)
        self.init_operations()

    def put_pixel(self, x, y, attr):
        """ Put a pixel in the buffer. """
        try:
            self.buffer[y][x] = attr
        except IndexError:
            pass

    def get_pixel(self, x, y):
        """ Get attribute of a pixel in the buffer. """
        try:
            return self.buffer[y][x]
        except IndexError:
            return 0

    def fill_interval(self, x0, x1, y, attr):
        """ Write a list of attributes to a scanline interval. """
        try:
            self.buffer[y][x0:x1+1] = [attr]*(x1-x0+1)
        except IndexError:
            pass

    if numpy:
        def init_operations(self):
            """ Initialise operations closures. """
            self.operations = {
                tk.PSET: lambda x, y: x.__setitem__(slice(len(x)), y),
                tk.PRESET: lambda x, y: x.__setitem__(slice(len(x)), y.__xor__((1<<self.bitsperpixel) - 1)),
                tk.AND: lambda x, y: x.__iand__(y),
                tk.OR: lambda x, y: x.__ior__(y),
                tk.XOR: lambda x, y: x.__ixor__(y),
            }

        def put_interval(self, x, y, colours, mask=0xff):
            """ Write a list of attributes to a scanline interval. """
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
            """ Return *view of* attributes of a scanline interval. """
            try:
                return self.buffer[y, x:x+length]
            except IndexError:
                return numpy.zeros(length, dtype=numpy.int8)

        def fill_rect(self, x0, y0, x1, y1, attr):
            """ Apply solid attribute to an area. """
            if (x1 < x0) or (y1 < y0):
                return
            try:
                self.buffer[y0:y1+1, x0:x1+1].fill(attr)
            except IndexError:
                pass

        def put_rect(self, x0, y0, x1, y1, array, operation_token):
            """ Apply numpy array [y][x] of attributes to an area. """
            if (x1 < x0) or (y1 < y0):
                return
            try:
                self.operations[operation_token](self.buffer[y0:y1+1, x0:x1+1], numpy.asarray(array))
                return self.buffer[y0:y1+1, x0:x1+1]
            except IndexError:
                return numpy.zeros((y1-y0+1, x1-x0+1), dtype=numpy.int8)

        def get_rect(self, x0, y0, x1, y1):
            """ Get *copy of* numpy array [y][x] of target area. """
            try:
                # our only user in module graphics needs a copy, so copy.
                return numpy.array(self.buffer[y0:y1+1, x0:x1+1])
            except IndexError:
                return numpy.zeros((y1-y0+1, x1-x0+1), dtype=numpy.int8)

        def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
            """ Move pixels from an area to another, replacing with attribute 0. """
            w, h = sx1-sx0+1, sy1-sy0+1
            area = numpy.array(self.buffer[sy0:sy1+1, sx0:sx1+1])
            self.buffer[sy0:sy1+1, sx0:sx1+1] = numpy.zeros((h, w), dtype=numpy.int8)
            self.buffer[ty0:ty0+h, tx0:tx0+w] = area

        def get_until(self, x0, x1, y, c):
            """ Get the attribute values of a scanline interval [x0, x1-1]. """
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
            """ Initialise operations closures. """
            self.operations = {
                tk.PSET: lambda x, y: y,
                tk.PRESET: lambda x, y: y ^ ((1<<self.bitsperpixel)-1),
                tk.AND: lambda x, y: x & y,
                tk.OR: lambda x, y: x | y,
                tk.XOR: lambda x, y: x ^ y,
            }

        def put_interval(self, x, y, colours, mask=0xff):
            """ Write a list of attributes to a scanline interval. """
            if mask != 0xff:
                inv_mask = 0xff ^ mask
                self.buffer[y][x:x+len(colours)] = [(c & mask) |
                                                (self.buffer[y][x+i] & inv_mask)
                                                for i,c in enumerate(colours)]
            return self.buffer[y][x:x+len(colours)]

        def get_interval(self, x, y, length):
            """ Return *view of* attributes of a scanline interval. """
            try:
                return self.buffer[y][x:x+length]
            except IndexError:
                return [0] * length

        def fill_rect(self, x0, y0, x1, y1, attr):
            """ Apply solid attribute to an area. """
            if (x1 < x0) or (y1 < y0):
                return
            try:
                for y in range(y0, y1+1):
                    self.buffer[y][x0:x1+1] = [attr] * (x1-x0+1)
            except IndexError:
                pass

        def put_rect(self, x0, y0, x1, y1, array, operation_token):
            """ Apply 2d list [y][x] of attributes to an area. """
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
            """ Get *copy of* 2d list [y][x] of target area. """
            try:
                return [self.buffer[y][x0:x1+1] for y in range(y0, y1+1)]
            except IndexError:
                return [[0]*(x1-x0+1) for _ in range(y1-y0+1)]

        def move_rect(self, sx0, sy0, sx1, sy1, tx0, ty0):
            """ Move pixels from an area to another, replacing with attribute 0. """
            for y in range(0, sy1-sy0+1):
                row = self.buffer[sy0+y][sx0:sx1+1]
                self.buffer[sy0+y][sx0:sx1+1] = [0] * (sx1-sx0+1)
                self.buffer[ty0+y][tx0:tx0+(sx1-sx0+1)] = row

        def get_until(self, x0, x1, y, c):
            """ Get the attribute values of a scanline interval [x0, x1-1]. """
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
    """ Screen manipulation operations. """

    def __init__(self, initial_width, video_mem_size):
        """ Minimal initialisiation of the screen. """
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
        self.cga4_palette = list(modes.cga4_palettes[1])
        self.prepare_modes()
        self.mode = self.text_data[initial_width]
        # cursor
        self.cursor = Cursor(self)

    def prepare_modes(self):
        """ Build lists of allowed graphics modes. """
        self.text_data, self.mode_data = modes.get_modes(self,
                                    self.cga4_palette, self.video_mem_size)

    def close(self):
        """ Close the display. """
        video.close()

    def resume(self):
        """ Load a video mode from storage and initialise. """
        # recalculate modes in case we've changed hardware emulations
        self.prepare_modes()
        cmode = self.mode
        nmode = self.screen_mode
        if (not cmode.is_text_mode and
                (nmode not in self.mode_data or
                 cmode.name != self.mode_data[nmode].name)):
            logging.warning(
                "Resumed screen mode %d (%s) not supported by this setup",
                nmode, cmode.name)
            return False
        if not cmode.is_text_mode:
            mode_info = self.mode_data[nmode]
        else:
            mode_info = self.text_data[cmode.width]
        if (cmode.is_text_mode and cmode.name != mode_info.name):
            # we switched adapters on resume; fix font height, palette, cursor
            self.cursor.from_line = (self.cursor.from_line *
                                       mode_info.font_height) // cmode.font_height
            self.cursor.to_line = (self.cursor.to_line *
                                     mode_info.font_height) // cmode.font_height
            self.palette = Palette(self.mode)
        # set the screen mode
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_MODE, mode_info))
        if mode_info.is_text_mode:
            # send glyphs to backend; copy is necessary
            # as dict may change here while the other thread is working on it
            backend.video_queue.put(backend.Event(backend.VIDEO_BUILD_GLYPHS,
                    dict((k,v) for k,v in self.glyphs.iteritems())))
        # set the visible and active pages
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)))
        # rebuild palette
        self.palette.set_all(self.palette.palette, check_mode=False)
        # fix the cursor
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_SHAPE,
                (self.cursor.width, mode_info.font_height,
                 self.cursor.from_line, self.cursor.to_line)))
        backend.video_queue.put(backend.Event(backend.VIDEO_MOVE_CURSOR,
                (state.console_state.row, state.console_state.col)))
        if self.mode.is_text_mode:
            fore, _, _, _ = self.split_attr(
                self.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
        else:
            fore, _, _, _ = self.split_attr(self.mode.cursor_index or self.attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_ATTR, fore))
        self.cursor.reset_visibility()
        fore, _, _, _ = self.split_attr(self.border_attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_BORDER_ATTR, fore))
        # redraw the text screen and rebuild text buffers in video plugin
        self.mode = mode_info
        for pagenum in range(self.mode.num_pages):
            for crow in range(self.mode.height):
                # for_keys=True means 'suppress echo on cli'
                self.refresh_range(pagenum, crow+1, 1, self.mode.width,
                                   for_keys=True, text_only=True)
            # redraw graphics
            if not self.mode.is_text_mode:
                backend.video_queue.put(backend.Event(backend.VIDEO_PUT_RECT, (pagenum, 0, 0,
                                self.mode.pixel_width-1, self.mode.pixel_height-1,
                                self.pixels.pages[pagenum].buffer)))
        return True

    def screen(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum,
               erase=1, new_width=None):
        """ SCREEN: change the video mode, colourburst, visible or active page. """
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
            if video_capabilities == 'pcjr':
                new_colorswitch = 0
            elif video_capabilities == 'tandy':
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
            if (video_capabilities == 'pcjr' and info and
                    new_vpagenum >= info.num_pages):
                new_vpagenum = 0
        if new_apagenum is None:
            new_apagenum = self.apagenum
            if (video_capabilities == 'pcjr' and info and
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
        """ Change the video mode, colourburst, visible or active page. """
        # reset palette happens even if the SCREEN call fails
        self.set_cga4_palette(1)
        # if the new mode has fewer pages than current vpage/apage,
        # illegal fn call before anything happens.
        # signal the backend to change the screen resolution
        if (not mode_info or
                new_apagenum >= mode_info.num_pages or
                new_vpagenum >= mode_info.num_pages):
            # reset palette happens even if the SCREEN call fails
            self.palette = Palette(self.mode)
            raise error.RunError(error.IFC)
        # preload SBCS glyphs
        try:
            self.glyphs = { chr(c): typeface.build_glyph(chr(c),
                                        fonts[mode_info.font_height],
                                        mode_info.font_width, mode_info.font_height)
                            for c in range(256) }
        except (KeyError, AttributeError):
            logging.warning(
                'No %d-pixel font available. Could not enter video mode %s.',
                mode_info.font_height, mode_info.name)
            raise error.RunError(error.IFC)
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_MODE, mode_info))
        if mode_info.is_text_mode:
            # send glyphs to backend; copy is necessary
            # as dict may change here while the other thread is working on it
            backend.video_queue.put(backend.Event(backend.VIDEO_BUILD_GLYPHS,
                    dict((k,v) for k,v in self.glyphs.iteritems())))
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
                               do_dbcs=(self.mode.font_height >= 14))
        if not self.mode.is_text_mode:
            self.pixels = PixelBuffer(self.mode.pixel_width, self.mode.pixel_height,
                                    self.mode.num_pages, self.mode.bitsperpixel)
        # ensure current position is not outside new boundaries
        state.console_state.row, state.console_state.col = 1, 1
        # set active page & visible page, counting from 0.
        self.set_page(new_vpagenum, new_apagenum)
        # set graphics characteristics
        self.drawing = graphics.Drawing(self)
        # cursor width starts out as single char
        self.cursor.init_mode(self.mode)
        self.palette = Palette(self.mode)
        # set the attribute
        if not self.mode.is_text_mode:
            fore, _, _, _ = self.split_attr(self.mode.cursor_index or self.attr)
            backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_ATTR, fore))
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if self.mode.is_text_mode:
            self.set_colorburst(new_colorswitch)
        elif self.mode.name == '320x200x4':
            self.set_colorburst(not new_colorswitch)
        elif self.mode.name == '640x200x2':
            self.set_colorburst(False)

    def set_width(self, to_width):
        """ Set the character width of the screen, reset pages and change modes. """
        if to_width == 20:
            if video_capabilities in ('pcjr', 'tandy'):
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

    def set_colorburst(self, on=True):
        """ Set the composite colorburst bit. """
        # On a composite monitor:
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        colorburst_capable = video_capabilities in (
                                    'cga', 'cga_old', 'tandy', 'pcjr')
        if self.mode.name == '320x200x4' and not composite_monitor:
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self.cga_mode_5 = not on
            self.set_cga4_palette(1)
        elif (on or not composite_monitor and not mono_monitor):
            modes.colours16[:] = modes.colours16_colour
        else:
            modes.colours16[:] = modes.colours16_mono
        # reset the palette to reflect the new mono or mode-5 situation
        self.palette = Palette(self.mode)
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_COLORBURST, (on and colorburst_capable,
                            self.palette.rgb_palette, self.palette.rgb_palette1)))

    def set_cga4_palette(self, num):
        """ set the default 4-colour CGA palette. """
        self.cga4_palette_num = num
        # we need to copy into cga4_palette as it's referenced by mode.palette
        if self.cga_mode_5 and video_capabilities in ('cga', 'cga_old'):
            self.cga4_palette[:] = modes.cga4_palettes[5]
        else:
            self.cga4_palette[:] = modes.cga4_palettes[num]

    def set_video_memory_size(self, new_size):
        """ Change the amount of memory available to the video card. """
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
        """ Set active page & visible page, counting from 0. """
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
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_PAGE, (new_vpagenum, new_apagenum)))

    def set_attr(self, attr):
        """ Set the default attribute. """
        self.attr = attr
        if not self.mode.is_text_mode and self.mode.cursor_index is None:
            fore, _, _, _ = self.split_attr(attr)
            backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_ATTR, fore))

    def set_border(self, attr):
        """ Set the border attribute. """
        self.border_attr = attr
        fore, _, _, _ = self.split_attr(attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_BORDER_ATTR, fore))

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        self.text.copy_page(src, dst)
        backend.video_queue.put(backend.Event(backend.VIDEO_COPY_PAGE, (src, dst)))

    def get_char_attr(self, pagenum, crow, ccol, want_attr):
        """ Retrieve a byte from the screen. """
        return self.text.pages[pagenum].get_char_attr(crow, ccol, want_attr)

    def put_char_attr(self, pagenum, crow, ccol, c, cattr,
                            one_only=False, for_keys=False, force=False):
        """ Put a byte to the screen, redrawing as necessary. """
        if not self.mode.is_text_mode:
            cattr = cattr & 0xf
            # always force drawing of spaces, it may have been overdrawn
            if c == ' ':
                force = True
        start, stop = self.text.pages[pagenum].put_char_attr(crow, ccol, c, cattr, one_only, force)
        # update the screen
        self.refresh_range(pagenum, crow, start, stop, for_keys)

    def get_text(self, start_row, start_col, stop_row, stop_col):
        """ Retrieve a clip of the text between start and stop. """
        r, c = start_row, start_col
        full = ''
        clip = ''
        if self.vpage.row[r-1].double[c-1] == 2:
            # include lead byte
            c -= 1
        if self.vpage.row[stop_row-1].double[stop_col-1] == 1:
            # include trail byte
            stop_col += 1
        while r < stop_row or (r == stop_row and c <= stop_col):
            clip += self.vpage.row[r-1].buf[c-1][0]
            c += 1
            if c > self.mode.width:
                if not self.vpage.row[r-1].wrap:
                    full += unicodepage.UTF8Converter().to_utf8(clip) + '\r\n'
                    clip = ''
                r += 1
                c = 1
        full += unicodepage.UTF8Converter().to_utf8(clip)
        return full

    def refresh_range(self, pagenum, crow, start, stop, for_keys=False, text_only=False):
        """ Redraw a section of a screen row, assuming DBCS buffer has been set. """
        therow = self.text.pages[pagenum].row[crow-1]
        ccol = start
        while ccol < stop:
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
            backend.video_queue.put(backend.Event(backend.VIDEO_PUT_GLYPH, (pagenum, r, c, char,
                                 fore, back, blink, underline, for_keys)))
            if not self.mode.is_text_mode and not text_only:
                # update pixel buffer
                x0, y0, x1, y1, sprite = self.glyph_to_rect(
                                                r, c, mask, fore, back)
                self.pixels.pages[self.apagenum].put_rect(
                                                x0, y0, x1, y1, sprite, tk.PSET)
                backend.video_queue.put(backend.Event(backend.VIDEO_PUT_RECT,
                                        (self.apagenum, x0, y0, x1, y1, sprite)))

    # should be in console? uses wrap
    def redraw_row(self, start, crow, wrap=True):
        """ Draw the screen row, wrapping around and reconstructing DBCS buffer. """
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

    #D -> state.io_state.lpt1_file.write(get_text(...))
    def print_screen(self):
        """ Output the visible page to LPT1. """
        for crow in range(1, self.mode.height+1):
            line = ''
            for c, _ in self.vpage.row[crow-1].buf:
                line += c
            state.io_state.lpt1_file.write_line(line)

    def clear_text_at(self, x, y):
        """ Remove the character covering a single pixel. """
        fx, fy = self.mode.font_width, self.mode.font_height
        cymax, cxmax = self.mode.height-1, self.mode.width-1
        cx, cy = x // fx, y // fy
        if cx >= 0 and cy >= 0 and cx <= cxmax and cy <= cymax:
            self.apage.row[cy].buf[cx] = (' ', self.attr)
        fore, back, blink, underline = self.split_attr(self.attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_PUT_GLYPH, (self.apagenum, cy+1, cx+1, ' ',
                             fore, back, blink, underline, True)))

    #MOVE to TextBuffer? replace with graphics_to_text_loc v.v.?
    def clear_text_area(self, x0, y0, x1, y1):
        """ Remove all characters from the textbuffer on a rectangle of the graphics screen. """
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
        """ Convert area from text buffer to area for pixel buffer. """
        # area bounds are all inclusive
        return ((col0-1)*self.mode.font_width, (row0-1)*self.mode.font_height,
                (col1-col0+1)*self.mode.font_width-1, (row1-row0+1)*self.mode.font_height-1)

    def clear_rows(self, start, stop):
        """ Clear text and graphics on given (inclusive) text row range. """
        for r in self.apage.row[start-1:stop]:
            r.clear(self.attr)
        if not self.mode.is_text_mode:
            x0, y0, x1, y1 = self.text_to_pixel_area(
                            start, 1, stop, self.mode.width)
            # background attribute must be 0 in graphics mode
            self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, 0)
        _, back, _, _ = self.split_attr(self.attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_CLEAR_ROWS, (back, start, stop)))

    #MOVE to Cursor.move ?
    def move_cursor(self, row, col):
        """ Move the cursor to a new position. """
        state.console_state.row, state.console_state.col = row, col
        backend.video_queue.put(backend.Event(backend.VIDEO_MOVE_CURSOR, (row, col)))
        self.cursor.reset_attr()

    def rebuild_glyph(self, ordval):
        """ Rebuild a text-mode character after POKE. """
        if self.mode.is_text_mode:
            # force rebuilding the character by deleting and requesting
            del self.glyphs[chr(ordval)]
            self.get_glyph(chr(ordval))

    ## text viewport / scroll area

    def set_view(self, start, stop):
        """ Set the scroll area. """
        state.console_state.view_set = True
        state.console_state.view_start = start
        state.console_state.scroll_height = stop
        #set_pos(start, 1)
        state.console_state.overflow = False
        self.move_cursor(start, 1)

    def unset_view(self):
        """ Unset scroll area. """
        self.set_view(1, 24)
        state.console_state.view_set = False

    def clear_view(self):
        """ Clear the scroll area. """
        if video_capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # keep background, set foreground to 7
            attr_save = self.attr
            self.set_attr(attr_save & 0x70 | 0x7)
        state.console_state.row = state.console_state.view_start
        state.console_state.col = 1
        if state.console_state.bottom_row_allowed:
            last_row = self.mode.height
        else:
            last_row = state.console_state.scroll_height
        for r in self.apage.row[state.console_state.view_start-1:
                        state.console_state.scroll_height]:
            # we're clearing the rows below, but don't set the wrap there
            r.wrap = False
        self.clear_rows(state.console_state.view_start, last_row)
        # ensure the cursor is show in the right position
        self.move_cursor(state.console_state.row, state.console_state.col)
        if video_capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # restore attr
            self.set_attr(attr_save)

    def scroll(self, from_line=None):
        """ Scroll the scroll region up by one line, starting at from_line. """
        if from_line is None:
            from_line = state.console_state.view_start
        _, back, _, _ = self.split_attr(self.attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_SCROLL_UP,
                    (from_line, state.console_state.scroll_height, back)))
        # sync buffers with the new screen reality:
        if state.console_state.row > from_line:
            state.console_state.row -= 1
        self.apage.row.insert(state.console_state.scroll_height,
                              TextRow(self.attr, self.mode.width))
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.text_to_pixel_area(from_line+1, 1,
                state.console_state.scroll_height, self.mode.width)
            tx0, ty0, _, _ = self.text_to_pixel_area(from_line, 1,
                state.console_state.scroll_height-1, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)
        del self.apage.row[from_line-1]

    def scroll_down(self,from_line):
        """ Scroll the scroll region down by one line, starting at from_line. """
        _, back, _, _ = self.split_attr(self.attr)
        backend.video_queue.put(backend.Event(backend.VIDEO_SCROLL_DOWN,
                    (from_line, state.console_state.scroll_height, back)))
        if state.console_state.row >= from_line:
            state.console_state.row += 1
        # sync buffers with the new screen reality:
        self.apage.row.insert(from_line - 1, TextRow(self.attr, self.mode.width))
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.text_to_pixel_area(from_line, 1,
                state.console_state.scroll_height-1, self.mode.width)
            tx0, ty0, _, _ = self.text_to_pixel_area(from_line+1, 1,
                state.console_state.scroll_height, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)
        del self.apage.row[state.console_state.scroll_height-1]

    ## graphics primitives

    def put_pixel(self, x, y, index, pagenum=None):
        """ Put a pixel on the screen; empty character buffer. """
        if pagenum is None:
            pagenum = self.apagenum
        if self.drawing.view_contains(x, y):
            self.pixels.pages[pagenum].put_pixel(x, y, index)
            backend.video_queue.put(backend.Event(backend.VIDEO_PUT_PIXEL, (pagenum, x, y, index)))
            self.clear_text_at(x, y)

    def get_pixel(self, x, y, pagenum=None):
        """ Return the attribute a pixel on the screen. """
        if pagenum is None:
            pagenum = self.apagenum
        return self.pixels.pages[pagenum].get_pixel(x, y)

    def get_interval(self, pagenum, x, y, length):
        """ Read a scanline interval into a list of attributes. """
        return self.pixels.pages[pagenum].get_interval(x, y, length)

    def put_interval(self, pagenum, x, y, colours, mask=0xff):
        """ Write a list of attributes to a scanline interval. """
        x, y, colours = self.drawing.view_clip_list(x, y, colours)
        newcolours = self.pixels.pages[pagenum].put_interval(x, y, colours, mask)
        backend.video_queue.put(backend.Event(backend.VIDEO_PUT_INTERVAL, (pagenum, x, y, newcolours)))
        self.clear_text_area(x, y, x+len(colours), y)

    def fill_interval(self, x0, x1, y, index):
        """ Fill a scanline interval in a solid attribute. """
        x0, x1, y = self.drawing.view_clip_interval(x0, x1, y)
        self.pixels.pages[self.apagenum].fill_interval(x0, x1, y, index)
        backend.video_queue.put(backend.Event(backend.VIDEO_FILL_INTERVAL,
                        (self.apagenum, x0, x1, y, index)))
        self.clear_text_area(x0, y, x1, y)

    def get_until(self, x0, x1, y, c):
        """ Get the attribute values of a scanline interval. """
        return self.pixels.pages[self.apagenum].get_until(x0, x1, y, c)

    def get_rect(self, x0, y0, x1, y1):
        """ Read a screen rect into an [y][x] array of attributes. """
        return self.pixels.pages[self.apagenum].get_rect(x0, y0, x1, y1)

    def put_rect(self, x0, y0, x1, y1, sprite, operation_token):
        """ Apply an [y][x] array of attributes onto a screen rect. """
        x0, y0, x1, y1, sprite = self.drawing.view_clip_area(x0, y0, x1, y1, sprite)
        rect = self.pixels.pages[self.apagenum].put_rect(x0, y0, x1, y1,
                                                        sprite, operation_token)
        backend.video_queue.put(backend.Event(backend.VIDEO_PUT_RECT,
                              (self.apagenum, x0, y0, x1, y1, rect)))
        self.clear_text_area(x0, y0, x1, y1)

    def fill_rect(self, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """
        x0, y0, x1, y1 = self.drawing.view_clip_rect(x0, y0, x1, y1)
        self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, index)
        backend.video_queue.put(backend.Event(backend.VIDEO_FILL_RECT,
                                (self.apagenum, x0, y0, x1, y1, index)))
        self.clear_text_area(x0, y0, x1, y1)

    # text

    def get_glyph(self, c):
        """ Return a glyph mask for a given character """
        try:
            mask = self.glyphs[c]
        except KeyError:
            mask = typeface.build_glyph(c, fonts[self.mode.font_height],
                                self.mode.font_width*2, self.mode.font_height)
            self.glyphs[c] = mask
            if self.mode.is_text_mode:
                backend.video_queue.put(backend.Event(backend.VIDEO_BUILD_GLYPHS, {c: mask}))
        return mask

    if numpy:
        def glyph_to_rect(self, row, col, mask, fore, back):
            """ Return a sprite for a given character """
            # set background
            glyph = numpy.full(mask.shape, back)
            # stamp foreground mask
            glyph[mask] = fore
            x0, y0 = (col-1) * self.mode.font_width, (row-1) * self.mode.font_height
            x1, y1 = x0 + mask.shape[1] - 1, y0 + mask.shape[0] - 1
            return x0, y0, x1, y1, glyph
    else:
        def glyph_to_rect(self, row, col, mask, fore, back):
            """ Return a sprite for a given character """
            glyph = [[(fore if bit else back) for bit in row] for row in mask]
            x0, y0 = (col-1) * self.mode.font_width, (row-1) * self.mode.font_height
            x1, y1 = x0 + len(mask[0]) - 1, y0 + len(mask) - 1
            return x0, y0, x1, y1, glyph


    #MOVE to modes classes in modes.py
    def split_attr(self, attr):
        """ Split attribute byte into constituent parts. """
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
    """ Colour palette. """

    def __init__(self, mode):
        """ Initialise palette. """
        self.set_all(mode.palette, check_mode=False)

    def set_entry(self, index, colour, check_mode=True):
        """ Set a new colour for a given attribute. """
        mode = state.console_state.screen.mode
        if check_mode and not self.mode_allows_palette(mode):
            return
        self.palette[index] = colour
        self.rgb_palette[index] = mode.colours[colour]
        if mode.colours1:
            self.rgb_palette1[index] = mode.colours1[colour]
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def get_entry(self, index):
        """ Retrieve the colour for a given attribute. """
        return self.palette[index]

    def set_all(self, new_palette, check_mode=True):
        """ Set the colours for all attributes. """
        mode = state.console_state.screen.mode
        if check_mode and new_palette and not self.mode_allows_palette(mode):
            return
        self.palette = list(new_palette)
        self.rgb_palette = [mode.colours[i] for i in self.palette]
        if mode.colours1:
            self.rgb_palette1 = [mode.colours1[i] for i in self.palette]
        else:
            self.rgb_palette1 = None
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_PALETTE, (self.rgb_palette, self.rgb_palette1)))

    def mode_allows_palette(self, mode):
        """ Check if the video mode allows palette change. """
        # effective palette change is an error in CGA
        if video_capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.RunError(error.IFC)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif video_capabilities in ('tandy', 'pcjr') and mode.is_text_mode:
            return False
        else:
            return True


###############################################################################
# cursor

class Cursor(object):
    """ Manage the cursor. """

    def __init__(self, screen):
        """ Initialise the cursor. """
        self.screen = screen
        # cursor visible in execute mode?
        self.visible_run = False
        # cursor shape
        self.from_line = 0
        self.to_line = 0
        self.width = screen.mode.font_width
        self.height = screen.mode.font_height

    def init_mode(self, mode):
        """ Change the cursor for a new screen mode. """
        self.width = mode.font_width
        self.height = mode.font_height
        self.set_default_shape(True)
        self.reset_attr()

    def reset_attr(self):
        """ Set the text cursor attribute to that of the current location. """
        if self.screen.mode.is_text_mode:
            fore, _, _, _ = self.screen.split_attr(self.screen.apage.row[
                    state.console_state.row-1].buf[
                    state.console_state.col-1][1] & 0xf)
            backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_ATTR, fore))

    def show(self, do_show):
        """ Force cursor to be visible/invisible. """
        backend.video_queue.put(backend.Event(backend.VIDEO_SHOW_CURSOR, do_show))

    def set_visibility(self, visible_run):
        """ Set default cursor visibility. """
        self.visible_run = visible_run
        self.reset_visibility()

    def reset_visibility(self):
        """ Set cursor visibility to its default state. """
        # visible if in interactive mode, unless forced visible in text mode.
        visible = (not state.basic_state.execute_mode)
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self.screen.mode.is_text_mode:
            visible = visible or self.visible_run
        backend.video_queue.put(backend.Event(backend.VIDEO_SHOW_CURSOR, visible))

    def set_shape(self, from_line, to_line):
        """ Set the cursor shape. """
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        mode = self.screen.mode
        fx, fy = self.width, self.height
        if egacursor:
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
        backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_SHAPE,
                            (self.width, fy, self.from_line, self.to_line)))
        self.reset_attr()

    def set_default_shape(self, overwrite_shape):
        """ Set the cursor to one of two default shapes. """
        if overwrite_shape:
            if not self.screen.mode.is_text_mode:
                # always a block cursor in graphics mode
                self.set_shape(0, self.height-1)
            elif video_capabilities == 'ega':
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
        """ Set the cursor with to num_chars characters. """
        new_width = num_chars * self.screen.mode.font_width
        # update cursor shape to new width if necessary
        if new_width != self.width:
            self.width = new_width
            backend.video_queue.put(backend.Event(backend.VIDEO_SET_CURSOR_SHAPE,
                    (self.width, self.height, self.from_line, self.to_line)))
            self.reset_attr()


###############################################################################

prepare()
