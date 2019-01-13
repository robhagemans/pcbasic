"""
PC-BASIC - display.py
Display mode and colour palette operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from ..base import signals
from ..base import error
from .. import values
from . import graphics
from . import modes

from .colours import Palette
from .textscreen import TextScreen
from .pixels import PixelBuffer
from .modes import Video


class Display(object):
    """Display and video mode manipulation operations."""

    def __init__(
            self, queues, values, input_methods, memory,
            initial_width, video_mem_size, capabilities, monitor, sound, io_streams,
            screen_aspect, codepage, fonts
        ):
        """Initialise the display."""
        self.queues = queues
        self._values = values
        self._memory = memory
        # low level settings
        self.video = Video(
            capabilities, monitor, screen_aspect, video_mem_size
        )
        self.capabilities = self.video.capabilities
        # video mode settings
        self._mode_nr, self.colorswitch, self.apagenum, self.vpagenum = 0, 1, 0, 0
        # prepare video modes
        self.mode = self.video.get_mode(0, initial_width)
        # current attribute
        self.attr = 7
        # border attribute
        self._border_attr = 0
        # text screen
        self.text_screen = TextScreen(
            self.queues, self._values, self.mode, self.capabilities,
            fonts, codepage, io_streams, sound
        )
        # graphics operations
        self.drawing = graphics.Drawing(self.queues, input_methods, self._values, self._memory)
        # colour palette
        self.palette = Palette(self.queues, self.mode)
        # initialise a fresh textmode screen
        self._set_mode(self.mode, 0, 1, 0, 0)

    ###########################################################################
    # video modes

    def screen(
            self, new_mode_nr, new_colorswitch, new_apagenum, new_vpagenum,
            erase=1, new_width=None, force_reset=False
        ):
        """Change the video mode, colourburst, visible or active page."""
        # reset palette happens even if the SCREEN call fails
        self.palette.reset()
        # set default arguments
        new_mode_nr = self._mode_nr if (new_mode_nr is None) else new_mode_nr
        # set colorswitch
        if new_colorswitch is None:
            new_colorswitch = True
            if self.capabilities == 'pcjr':
                new_colorswitch = False
            elif self.capabilities == 'tandy':
                new_colorswitch = not new_mode_nr
        new_colorswitch = bool(new_colorswitch)
        if new_mode_nr == 0 and new_width is None:
            # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
            # otherwise, width persists on change to screen 0
            new_width = 40 if (self.mode.width == 20) else self.mode.width
        # retrieve the specs for the new video mode
        new_mode = self.video.get_mode(new_mode_nr, new_width)
        # vpage and apage nums are persistent on mode switch with SCREEN
        # on pcjr only, reset page to zero if current page number would be too high.
        # in other adapters, that's going to raise an IFC later on.
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
            if (self.capabilities == 'pcjr' and new_vpagenum >= new_mode.num_pages):
                new_vpagenum = 0
        if new_apagenum is None:
            new_apagenum = self.apagenum
            if (self.capabilities == 'pcjr' and new_apagenum >= new_mode.num_pages):
                new_apagenum = 0
        # if the new mode has fewer pages than current vpage/apage
        # illegal fn call before anything happens.
        # signal the signals to change the screen resolution
        if (new_apagenum >= new_mode.num_pages or new_vpagenum >= new_mode.num_pages):
            raise error.BASICError(error.IFC)
        if (
                (not new_mode.is_text_mode and new_mode.name != self.mode.name) or
                (new_mode.is_text_mode and not self.mode.is_text_mode) or
                (new_mode.width != self.mode.width) or
                (new_colorswitch != self.colorswitch) or force_reset
            ):
            self._set_mode(new_mode, new_mode_nr, new_colorswitch, new_apagenum, new_vpagenum, erase)
        else:
            # only switch pages
            self.set_page(new_vpagenum, new_apagenum)

    def _set_mode(
            self, new_mode, new_mode_nr, new_colorswitch, new_apagenum, new_vpagenum, erase=True
        ):
        """Change the video mode, colourburst, visible or active page."""
        # preserve memory if erase==0; don't distingush erase==1 and erase==2
        if not erase:
            saved_addr, saved_buffer = self.mode.memorymap.get_all_memory(self)
        # illegal fn call if we don't have a font for this mode
        self.text_screen.check_font_available(new_mode)
        # if we made it here we're ready to commit to the new mode
        self.queues.video.put(signals.Event(
            signals.VIDEO_SET_MODE, (
                new_mode.num_pages, new_mode.pixel_height, new_mode.pixel_width,
                new_mode.height, new_mode.width, new_mode.colourmap.num_attr, new_mode.is_text_mode
            )
        ))
        # switching to another text mode (width-only change)
        width_only = (self.mode.is_text_mode and new_mode.is_text_mode)
        # attribute and border persist on width-only change
        # otherwise start with black border and default attr
        if (
                not width_only or self.apagenum != new_apagenum or self.vpagenum != new_vpagenum
                or self.colorswitch != new_colorswitch
            ):
            self.attr = new_mode.attr
        if (not width_only and new_mode.name != self.mode.name):
            self.set_border(0)
        # set the screen mode parameters
        self.mode, self._mode_nr = new_mode, new_mode_nr
        # set the colorswitch
        self.colorswitch = new_colorswitch
        # initialise the palette
        self.palette.init_mode(self.mode, self.colorswitch)
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
        # NOTE this requires active page to have beet set!
        self.text_screen.init_mode(self.mode, self.pixels, self.attr, new_vpagenum, new_apagenum)
        # restore emulated video memory in new mode
        if not erase:
            self.mode.memorymap.set_memory(self, saved_addr, saved_buffer)
        # center graphics cursor, reset window, etc.
        self.drawing.init_mode(self.mode, self.text_screen.text, self.pixels)
        self.drawing.set_attr(self.attr)

    def set_width(self, to_width):
        """Set the character width of the screen, reset pages and change modes."""
        # raise an error if the width value doesn't make sense
        if to_width not in self.video.get_allowed_widths():
            raise error.BASICError(error.IFC)
        # if we're currently at that width, do nothing
        if to_width == self.mode.width:
            return
        elif to_width == 20:
            self.screen(3, None, 0, 0)
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
            raise error.BASICError(error.IFC)

    def set_video_memory_size(self, new_size):
        """Change the amount of memory available to the video card."""
        self.video.set_video_memory_size(new_size)
        # text screen modes don't depend on video memory size
        if self._mode_nr == 0:
            return
        # check if we need to drop out of our current mode
        page = max(self.vpagenum, self.apagenum)
        # reload max number of pages; do we fit? if not, drop to text
        new_mode = self.video.get_mode(self._mode_nr)
        if (page >= new_mode.num_pages):
            self.screen(0, 0, 0, 0, force_reset=True)
        else:
            self.mode = new_mode

    def rebuild(self):
        """Completely resubmit the screen to the interface."""
        # set the screen mode
        self.queues.video.put(signals.Event(
            signals.VIDEO_SET_MODE, (
                self.mode.num_pages, self.mode.pixel_height, self.mode.pixel_width,
                self.mode.height, self.mode.width,
                self.mode.colourmap.num_attr, self.mode.is_text_mode
            )
        ))
        # set the visible and active pages
        self.queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)))
        # rebuild palette
        self.palette.submit()
        # set the border
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (self._border_attr,)))
        self.text_screen.rebuild()


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
        self.queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (new_vpagenum, new_apagenum)))

    def set_attr(self, attr):
        """Set the default attribute."""
        self.attr = attr
        self.drawing.set_attr(attr)
        self.text_screen.set_attr(attr)
        if not self.mode.is_text_mode and self.mode.cursor_index is None:
            self.text_screen.cursor.set_attr(attr)

    def set_border(self, attr):
        """Set the border attribute."""
        fore, _, _, _ = self.mode.colourmap.split_attr(attr)
        self._border_attr = fore
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (fore,)))

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
        if self.capabilities == 'tandy':
            error.range_check(0, 1, colorswitch)
        erase = next(args)
        if erase is not None:
            erase = values.to_int(erase)
            error.range_check(0, 2, erase)
        list(args)
        if erase is not None:
            # erase can only be set on pcjr/tandy 5-argument syntax
            if self.capabilities not in ('pcjr', 'tandy'):
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
        self.queues.video.put(signals.Event(signals.VIDEO_COPY_PAGE, (src, dst)))

    def color_(self, args):
        """COLOR: set colour attributes."""
        args = list(args)
        error.throw_if(len(args) > 3)
        args += [None] * (3 - len(args))
        fore, back, bord = args
        if fore is None:
            fore = (self.attr >> 7) * 0x10 + (self.attr & 0xf)
        else:
            fore = values.to_int(fore)
        if back is not None:
            back = back and values.to_int(back)
        if bord is not None:
            bord = bord and values.to_int(bord)
        if self.mode.name in ('640x200x2', '720x348x2'):
            # screen 2; hercules: illegal fn call
            raise error.BASICError(error.IFC)
        elif self.mode.is_text_mode:
            self._color_mode_0(fore, back, bord)
        elif self.mode.name == '320x200x4':
            self._color_mode_1(fore, back, bord)
        else:
            self._color_other_modes(fore, back, bord)

    def _color_mode_0(self, fore, back, bord):
        """Helper function for COLOR in text mode (SCREEN 0)."""
        if back is None:
            _, back, _, _ = self.mode.colourmap.split_attr(self.attr)
        # for screens other than 1, no distinction between 3rd parm zero and not supplied
        bord = bord or 0
        error.range_check(0, 255, bord)
        # allow twice the number of foreground attributes (16) - because of blink
        num_fore_attr = self.mode.colourmap.num_palette
        error.range_check(0, num_fore_attr*2-1, fore)
        # allow background attributes up to 15 though highest bit is ignored
        error.range_check(0, num_fore_attr-1, back, bord)
        # COLOR > 17 means blink, but the blink bit is the top bit of the true attribute
        blink, fore = divmod(fore, num_fore_attr)
        self.set_attr(self.mode.colourmap.join_attr(fore, back, blink, False))
        self.set_border(bord)

    def _color_mode_1(self, back, pal, override):
        """Helper function for COLOR in SCREEN 1."""
        back = self.palette.get_entry(0) if back is None else back
        if override is not None:
            # uses last entry as palette if given
            pal = override
        error.range_check(0, 255, back)
        if pal is not None:
            error.range_check(0, 255, pal)
            self.mode.colourmap.set_cga4_palette(pal % 2)
            palette = list(self.mode.colourmap.default_palette)
            palette[0] = back & 0xf
            self.palette.set_all(palette, force=True)
        else:
            self.palette.set_entry(0, back & 0xf, force=True)

    def _color_other_modes(self, fore, back, bord):
        """Helper function for COLOR in modes other than SCREEN 1."""
        if back is None:
            # graphics mode bg is always 0; sets palette instead
            back = self.palette.get_entry(0)
        # for screens other than 1, no distinction between 3rd parm zero and not supplied
        bord = bord or 0
        error.range_check(0, 255, bord)
        max_attr = self.mode.colourmap.num_attr - 1
        max_colour = self.mode.colourmap.num_colours - 1
        if self.mode.name in (
                '160x200x16', '320x200x4pcjr', '320x200x16pcjr'
                '640x200x4', '320x200x16', '640x200x16'
            ):
            error.range_check(1, max_attr, fore)
            error.range_check(0, max_attr, back)
            self.set_attr(fore)
            # in screen 7 and 8, only low intensity palette is used.
            self.palette.set_entry(0, back % 8, force=True)
        elif self.mode.name in ('640x350x16', '640x350x4'):
            error.range_check(1, max_attr, fore)
            error.range_check(0, max_colour, back)
            self.set_attr(fore)
            self.palette.set_entry(0, back, force=True)
        elif self.mode.name == '640x400x2':
            error.range_check(0, max_colour, fore)
            if back != 0:
                raise error.BASICError(error.IFC)
            self.palette.set_entry(1, fore, force=True)

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
            self.palette.set_all(self.mode.colourmap.default_palette)
        else:
            # can't set blinking colours separately
            error.range_check(0, self.mode.colourmap.num_palette-1, attrib)
            # numbers 255 and up are in fact allowed, 255 -> -1, 256 -> 0, etc
            colour = -1 + (colour + 1) % 256
            error.range_check(-1, self.mode.colourmap.num_colours-1, colour)
            if colour != -1:
                self.palette.set_entry(attrib, colour)

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
        num_palette_entries = self.mode.colourmap.num_palette
        error.throw_if(self._memory.arrays.array_len(dimensions) - start < num_palette_entries)
        new_palette = []
        for i in range(num_palette_entries):
            offset = (start+i) * 2
            ## signed int, as -1 means don't set
            val, = struct.unpack('<h', lst[offset:offset+2])
            error.range_check(-1, self.mode.colourmap.num_colours-1, val)
            new_palette.append(val if val > -1 else self.palette.get_entry(i))
        self.palette.set_all(new_palette)

    def cls_(self, args):
        """CLS: clear the screen."""
        val = next(args)
        if val is not None:
            val = values.to_int(val)
            # tandy gives illegal function call on CLS number
            error.throw_if(self.capabilities == 'tandy')
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
