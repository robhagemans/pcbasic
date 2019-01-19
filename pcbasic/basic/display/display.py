"""
PC-BASIC - display.py
Display and video mode operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging

from ...compat import iteritems
from ..base import signals
from ..base import error
from .. import values
from . import graphics
from . import modes
from . import font

from .textscreen import TextScreen
from .pixels import PixelBuffer
from .colours import MONO_TINT
from .modes import TO_WIDTH


class Display(object):
    """Display and video mode operations."""

    def __init__(
            self, queues, values, input_methods, memory,
            initial_width, video_mem_size, adapter, monitor, sound, io_streams,
            codepage, fonts
        ):
        """Initialise the display."""
        self._queues = queues
        self._values = values
        self._memory = memory
        # low level settings
        if adapter == 'ega':
            if monitor in MONO_TINT:
                adapter = 'ega_mono'
            elif video_mem_size < 131072:
                # less than 128k means 64k, as EGA has memory in 64k blocks
                adapter = 'ega_64k'
        self._adapter = adapter
        self._monitor = monitor
        self._video_mem_size = video_mem_size
        # prepare video modes
        self.mode = modes.get_mode(
            0, initial_width, self._adapter, self._monitor, self._video_mem_size
        )
        # video mode settings
        self.colorswitch, self.apagenum, self.vpagenum = 1, 0, 0
        # current attribute
        self.attr = self.mode.attr
        # border attribute
        self._border_attr = 0
        # prepare fonts
        self._fonts = {}
        if fonts:
            self._fonts = {
                height: font.Font(height, font_dict)
                for height, font_dict in iteritems(fonts) if font_dict
            }
        # we must have an 8-pixel font; use the default CP437 font if none provided
        if 8 not in self._fonts:
            self._fonts[8] = font.Font(8, None)
        # copy as 8-pixel hardware BIOS font (for CGA textmodes)
        # as opposed to the loadable 8-pixel memory font used in graphics modes
        self._bios_font_8 = self._fonts[8].copy()
        # text screen
        self.text_screen = TextScreen(
            self._queues, self._values, self.mode, self._adapter, codepage, io_streams, sound
        )
        # pixel buffer, set by _set_mode
        self.pixels = None
        # screen aspect ratio: used to determine pixel aspect ratio, which is used by CIRCLE
        # all adapters including PCjr target 4x3, except Tandy
        if self._adapter == 'tandy':
            aspect = (3072, 2000)
        else:
            aspect = (4, 3)
        # Tandy pixel aspect ratio is different from normal
        # suggesting screen aspect ratio is not 4/3.
        # Tandy pixel aspect ratios, experimentally found with CIRCLE (on DOSBox?):
        # screen 2, 6:     48/100   normal if aspect = 3072, 2000
        # screen 1, 4, 5:  96/100   normal if aspect = 3072, 2000
        # pcjr: screen 1: .833, s2: .833/2, s3: .833*2 s4:.833 s5:.833 s6: .833/2
        # (checked with CIRCLE on MAME)
        # .833 == 5:6 corresponding to screen aspect ratio of 4:3
        # --> old value SCREEN 3 pixel aspect 1968/1000 not quite (but almost) consistent with this
        #     and I don't think it was really checked on Tandy -- dosbox won't run SCREEN 3
        # graphics operations
        self.drawing = graphics.Drawing(
            self._queues, input_methods, self._values, self._memory, aspect
        )
        # colour palette
        self.colourmap = self.mode.colourmap(
            self._queues, self._adapter, self._monitor, self.colorswitch
        )
        # initialise a fresh textmode screen
        self._set_mode(self.mode, 1, 0, 0, erase=True)


    ###########################################################################
    # video modes

    def screen(
            self, new_mode_nr, new_colorswitch, new_apagenum, new_vpagenum,
            erase=1, new_width=None, force_reset=False
        ):
        """Change the video mode, colourburst, visible or active page."""
        # reset palette happens even if the SCREEN call fails
        self.colourmap.reset()
        # find the new mode we're trying to get into
        if new_mode_nr is None:
            # keep current mode if graphics but maybe change width if text
            if self.mode.is_text_mode and new_width is not None:
                new_mode = modes.get_mode(
                    0, new_width, self._adapter, self._monitor, self._video_mem_size
                )
            else:
                new_mode = self.mode
        else:
            if new_mode_nr == 0 and new_width is None:
                # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
                # otherwise, width persists on change to screen 0
                new_width = 40 if (self.mode.width == 20) else self.mode.width
            # retrieve the specs for the new video mode
            new_mode = modes.get_mode(
                new_mode_nr, new_width, self._adapter, self._monitor, self._video_mem_size
            )
        # set colorswitch
        new_colorswitch = bool(new_colorswitch)
        if new_colorswitch is None:
            new_colorswitch = True
            if self._adapter == 'pcjr':
                new_colorswitch = False
            elif self._adapter == 'tandy':
                new_colorswitch = new_mode.is_text_mode
        # vpage and apage nums are persistent on mode switch with SCREEN
        # on pcjr only, reset page to zero if current page number would be too high.
        # in other adapters, that's going to raise an IFC later on.
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
            if (self._adapter == 'pcjr' and new_vpagenum >= new_mode.num_pages):
                new_vpagenum = 0
        if new_apagenum is None:
            new_apagenum = self.apagenum
            if (self._adapter == 'pcjr' and new_apagenum >= new_mode.num_pages):
                new_apagenum = 0
        # if the new mode has fewer pages than current vpage/apage
        # illegal fn call before anything happens.
        # signal the signals to change the screen resolution
        if (new_apagenum >= new_mode.num_pages or new_vpagenum >= new_mode.num_pages):
            raise error.BASICError(error.IFC)
        # if mode or colorswitch changed, do a full reset
        # otherwise only change pages
        if force_reset or new_mode != self.mode or new_colorswitch != self.colorswitch:
            self._set_mode(new_mode, new_colorswitch, new_apagenum, new_vpagenum, erase)
        else:
            self.set_page(new_vpagenum, new_apagenum)

    def _set_mode(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum, erase):
        """Change the video mode, colourburst, visible or active page."""
        # preserve memory if erase==0; don't distingush erase==1 and erase==2
        if not erase:
            saved_addr, saved_buffer = self.mode.memorymap.get_all_memory(self)
        # get a font for the new mode
        try:
            # in CGA (8- or 9-pixel) text modes, use the 8-pixel BIOS font, not the POKE-able one
            # 9th pixel is added by rendering code if needed
            if new_mode.is_text_mode and new_mode.font_height in (8, 9):
                font = self._bios_font_8
            else:
                font = self._fonts[new_mode.font_height]
            # initialise for this mode's font width (8 or 9 pixels)
            font.init_mode(new_mode.font_width)
        except KeyError:
            logging.warning(
                'No %d-pixel font available. Using 8-pixel font instead.',
                new_mode.font_height
            )
            font = self._bios_font_8.init_mode(new_mode.font_width)
        # submit the mode change to the interface
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_MODE, (
                new_mode.num_pages, new_mode.pixel_height, new_mode.pixel_width,
                new_mode.height, new_mode.width, new_mode.is_text_mode
            )
        ))
        # switching to another text mode (width-only change)
        width_only = self.mode.is_text_mode and new_mode.is_text_mode
        # attribute and border persist on width-only change
        # otherwise start with black border and default attr
        if (
                not width_only
                or self.apagenum != new_apagenum or self.vpagenum != new_vpagenum
                or self.colorswitch != new_colorswitch
            ):
            self.attr = new_mode.attr
        if not width_only and new_mode != self.mode:
            self.set_border(0)
        # set the screen mode parameters
        self.mode = new_mode
        # set the colorswitch
        self.colorswitch = new_colorswitch
        # initialise the palette
        self.colourmap = new_mode.colourmap(
            self._queues, self._adapter, self._monitor, self.colorswitch
        )
        # initialise pixel buffers
        if not self.mode.is_text_mode:
            self.pixels = PixelBuffer(
                self.mode.pixel_width, self.mode.pixel_height,
                self.mode.num_pages, self.mode.bitsperpixel
            )
        else:
            self.pixels = None
        # set active page & visible page, counting from 0.
        self.set_page(new_vpagenum, new_apagenum)
        # initialise text screen
        self.text_screen.init_mode(
            self.mode, self.pixels, self.attr, new_vpagenum, new_apagenum, font, self.colourmap
        )
        # restore emulated video memory in new mode
        if not erase:
            self.mode.memorymap.set_memory(self, saved_addr, saved_buffer)
        # center graphics cursor, reset window, etc.
        self.drawing.init_mode(
            self.mode, self.text_screen.text, self.pixels, self.colourmap.num_attr
        )
        self.drawing.set_attr(self.attr)

    def set_width(self, to_width):
        """Set the number of columns of the screen, reset pages and change modes."""
        # if we're currently at that width, do nothing
        if to_width == self.mode.width:
            return
        if self.mode.is_text_mode and to_width in (40, 80):
            new_mode = 0
        else:
            try:
                new_mode = TO_WIDTH[self._adapter][self.mode.name][to_width]
            except KeyError:
                # raise an error if the width value doesn't make sense
                raise error.BASICError(error.IFC)
        self.screen(new_mode, None, 0, 0, new_width=to_width)

    def set_video_memory_size(self, new_size):
        """Change the amount of memory available to the video card."""
        self._video_mem_size = int(new_size)
        # check if we need to drop out of our current mode
        page = max(self.vpagenum, self.apagenum)
        # reload max number of pages; do we fit? if not, drop to text
        self.mode.memorymap.set_video_mem_size(self._video_mem_size)
        if page >= self.mode.num_pages:
            self.screen(0, 0, 0, 0, force_reset=True)

    def rebuild(self):
        """Completely resubmit the screen to the interface."""
        # set the screen mode
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_MODE, (
                self.mode.num_pages, self.mode.pixel_height, self.mode.pixel_width,
                self.mode.height, self.mode.width, self.mode.is_text_mode
            )
        ))
        # set the visible and active pages
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)
        ))
        # rebuild palette
        self.colourmap.submit()
        # set the border
        self._queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (self._border_attr,)))
        self.text_screen.rebuild()

    ###########################################################################
    # memory accessible properties

    def get_mode_info_byte(self):
        """Screen mode info byte in low memory address 1125."""
        # blink vs bright
        # this can in theory be set with OUT 984 (&h3d8), but not implemented
        blink_enabled = True
        # bit 0: only in text mode?
        # bit 2: should this be colorswitch or colorburst_is_enabled?
        return (
            (self.mode.is_text_mode and self.mode.width == 80) * 1 +
            (not self.mode.is_text_mode) * 2 +
            self.colorswitch * 4 + 8 +
            (self.mode.name == '640x200x2') * 16 +
            blink_enabled * 32
        )

    def get_colour_info_byte(self):
        """Colour info byte in low memory address 1126."""
        if self.mode.name == '320x200x4':
            return (
                self.colourmap.get_entry(0)
                + 32 * self.colourmap.get_cga4_palette()
            )
        elif self.mode.is_text_mode:
            return self.get_border_attr()
            # not implemented: + 16 "if current color specified through
            # COLOR f,b with f in [0,15] and b > 7

    @property
    def memory_font(self):
        """8-bit memory font (half in ROM, half in RAM and loadable)."""
        return self._fonts[8]


    ###########################################################################

    def set_page(self, new_vpagenum, new_apagenum):
        """Set active page & visible page, counting from 0."""
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
        if new_apagenum is None:
            new_apagenum = self.apagenum
        if (new_vpagenum >= self.mode.num_pages or new_apagenum >= self.mode.num_pages):
            raise error.BASICError(error.IFC)
        self.vpagenum = new_vpagenum
        self.apagenum = new_apagenum
        self.drawing.set_page(new_apagenum)
        self.text_screen.set_page(new_vpagenum, new_apagenum)
        self._queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (new_vpagenum, new_apagenum)))

    def set_attr(self, attr):
        """Set the default attribute."""
        self.attr = attr
        self.drawing.set_attr(attr)
        self.text_screen.set_attr(attr)
        if not self.mode.is_text_mode and self.mode.cursor_attr is None:
            self.text_screen.cursor.set_attr(attr)

    def set_border(self, attr):
        """Set the border attribute."""
        fore, _, _, _ = self.colourmap.split_attr(attr)
        self._border_attr = fore
        self._queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (fore,)))

    def get_border_attr(self):
        """Get the border attribute, in range 0 <= attr < 16."""
        return self._border_attr


    ###########################################################################
    # callbacks

    # SCREEN statement
    # Colorswitch parameter
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
    #
    # Erase parameter:
    #   tells basic how much video memory to erase
    #   0: do not erase video memory
    #   1: (default) erase old and new page if screen or width changes
    #   2: erase all video memory if screen or width changes
    #   -> we're not distinguishing between 1 and 2 here

    def screen_(self, args):
        """SCREEN: change the video mode, colourburst, visible or active page."""
        # in GW, screen 0,0,0,0,0,0 raises error after changing the palette
        # this raises error before
        mode, colorswitch, apagenum, vpagenum = (
            None if arg is None else values.to_int(arg)
            for _, arg in zip(range(4), args)
        )
        # if any parameter not in [0,255], error 5 without doing anything
        # if the parameters are outside narrow ranges
        # (e.g. not implemented screen mode, pagenum beyond max)
        # then the error is only raised after changing the palette.
        error.range_check(0, 255, mode, colorswitch, apagenum, vpagenum)
        if self._adapter == 'tandy':
            error.range_check(0, 1, colorswitch)
        erase = next(args)
        if erase is not None:
            erase = values.to_int(erase)
            error.range_check(0, 2, erase)
        list(args)
        if erase is not None:
            # erase can only be set on pcjr/tandy 5-argument syntax
            if self._adapter not in ('pcjr', 'tandy'):
                raise error.BASICError(error.IFC)
        else:
            erase = 1
        self.screen(mode, colorswitch, apagenum, vpagenum, erase)

    def pcopy_(self, args):
        """Copy source to destination page."""
        src = values.to_int(next(args))
        error.range_check(0, self.mode.num_pages-1, src)
        dst = values.to_int(next(args))
        list(args)
        error.range_check(0, self.mode.num_pages-1, dst)
        self.text_screen.text.copy_page(src, dst)
        if not self.mode.is_text_mode:
            self.pixels.pages[dst].copy_from(self.pixels.pages[src])
        self._queues.video.put(signals.Event(signals.VIDEO_COPY_PAGE, (src, dst)))

    def color_(self, args):
        """COLOR: set colour attributes."""
        args = list(args)
        error.throw_if(len(args) > 3)
        args += [None] * (3 - len(args))
        arg0, arg1, arg2 = args
        arg0 = arg0 and values.to_int(arg0)
        arg1 = arg1 and values.to_int(arg1)
        arg2 = arg2 and values.to_int(arg2)
        attr, border = self.colourmap.color(self.attr, arg0, arg1, arg2)
        if attr is not None:
            self.set_attr(attr)
        if border is not None:
            self.set_border(border)

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
            self.colourmap.set_all(self.colourmap.default_palette)
        else:
            # can't set blinking colours separately
            error.range_check(0, self.colourmap.num_palette-1, attrib)
            # numbers 255 and up are in fact allowed, 255 -> -1, 256 -> 0, etc
            colour = -1 + (colour + 1) % 256
            error.range_check(-1, self.colourmap.num_colours-1, colour)
            if colour != -1:
                self.colourmap.set_entry(attrib, colour)

    def palette_using_(self, args):
        """PALETTE USING: set palette from array buffer."""
        array_name, start_indices = next(args)
        array_name = self._memory.complete_name(array_name)
        list(args)
        try:
            dimensions = self._memory.arrays.dimensions(array_name)
        except KeyError:
            raise error.BASICError(error.IFC)
        error.throw_if(array_name[-1:] != values.INT, error.TYPE_MISMATCH)
        lst = self._memory.arrays.view_full_buffer(array_name)
        start = self._memory.arrays.index(start_indices, dimensions)
        num_palette_entries = self.colourmap.num_palette
        error.throw_if(self._memory.arrays.array_len(dimensions) - start < num_palette_entries)
        new_palette = []
        for i in range(num_palette_entries):
            offset = (start+i) * 2
            ## signed int, as -1 means don't set
            val, = struct.unpack('<h', lst[offset:offset+2])
            error.range_check(-1, self.colourmap.num_colours-1, val)
            new_palette.append(val if val > -1 else self.colourmap.get_entry(i))
        self.colourmap.set_all(new_palette)

    def cls_(self, args):
        """CLS: clear the screen."""
        val = next(args)
        if val is not None:
            val = values.to_int(val)
            # tandy gives illegal function call on CLS number
            error.throw_if(self._adapter == 'tandy')
            error.range_check(0, 2, val)
        else:
            if self.drawing.graph_view.is_set():
                val = 1
            elif self.text_screen.scroll_area.active:
                val = 2
            else:
                val = 0
        list(args)
        # cls is only executed if no errors have occurred
        if val == 0:
            self.text_screen.clear()
            self.text_screen.redraw_bar()
            self.drawing.reset()
        elif val == 1:
            # clear the graphics viewport
            if not self.mode.is_text_mode:
                self.drawing.fill_rect(*self.drawing.graph_view.get(), index=(self.attr >> 4) & 0x7)
            self.drawing.reset()
        elif val == 2:
            self.text_screen.clear_view()
