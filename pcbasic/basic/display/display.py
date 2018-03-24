"""
PC-BASIC - display.py
Display mode and colour palette operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from ..base import signals
from ..base import error
from .. import values
from . import graphics
from . import modes

from .textscreen import TextScreen
from .pixels import PixelBuffer
from .modes import Video


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
# display

class Display(object):
    """Display and video mode manipulation operations."""

    def __init__(self, queues, values, input_methods, memory,
                initial_width, video_mem_size, capabilities, monitor, sound, io_streams,
                low_intensity, mono_tint, screen_aspect, codepage, fonts):
        """Initialise the display."""
        self.queues = queues
        self._values = values
        self._memory = memory
        # low level settings
        self.video = Video(
                capabilities, monitor, mono_tint, low_intensity, screen_aspect, video_mem_size)
        self.capabilities = self.video.capabilities
        # video mode settings
        self._mode_nr, self.colorswitch, self.apagenum, self.vpagenum = 0, 1, 0, 0
        # prepare video modes
        self.mode = self.video.get_mode(0, initial_width)
        # current attribute
        self.attr = 7
        # border attribute
        self.border_attr = 0
        # text screen
        self.text_screen = TextScreen(
                self.queues, self._values, self.mode, self.capabilities,
                fonts, codepage, io_streams, sound)
        # graphics operations
        self.drawing = graphics.Drawing(self.queues, input_methods, self._values, self._memory)
        # colour palette
        self.palette = Palette(self.queues, self.mode, self.capabilities, self._memory)
        # initialise a fresh textmode screen
        self._set_mode(self.mode, 0, 1, 0, 0)

    ###########################################################################
    # video modes

    def screen(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum,
               erase=1, new_width=None, force_reset=False):
        """Change the video mode, colourburst, visible or active page."""
        # reset palette happens even if the SCREEN call fails
        self.palette.init_mode(self.mode)
        # set default arguments
        new_mode = self._mode_nr if (new_mode is None) else new_mode
        # set colorswitch
        if new_colorswitch is None:
            new_colorswitch = True
            if self.capabilities == 'pcjr':
                new_colorswitch = False
            elif self.capabilities == 'tandy':
                new_colorswitch = not new_mode
        new_colorswitch = bool(new_colorswitch)
        if new_mode == 0 and new_width is None:
            # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
            # otherwise, width persists on change to screen 0
            new_width = 40 if (self.mode.width == 20) else self.mode.width
        # retrieve the specs for the new video mode
        info = self.video.get_mode(new_mode, new_width)
        # vpage and apage nums are persistent on mode switch with SCREEN
        # on pcjr only, reset page to zero if current page number would be too high.
        # in other adapters, that's going to raise an IFC later on.
        if new_vpagenum is None:
            new_vpagenum = self.vpagenum
            if (self.capabilities == 'pcjr' and new_vpagenum >= info.num_pages):
                new_vpagenum = 0
        if new_apagenum is None:
            new_apagenum = self.apagenum
            if (self.capabilities == 'pcjr' and new_apagenum >= info.num_pages):
                new_apagenum = 0
        if ((not info.is_text_mode and info.name != self.mode.name) or
                (info.is_text_mode and not self.mode.is_text_mode) or
                (info.width != self.mode.width) or
                (new_colorswitch != self.colorswitch) or force_reset):
            self._set_mode(
                    info, new_mode, new_colorswitch, new_apagenum, new_vpagenum, erase)
        else:
            # only switch pages
            if (new_apagenum >= info.num_pages or new_vpagenum >= info.num_pages):
                raise error.BASICError(error.IFC)
            self.set_page(new_vpagenum, new_apagenum)

    def _set_mode(self, spec, new_mode, new_colorswitch,
                 new_apagenum, new_vpagenum, erase=True):
        """Change the video mode, colourburst, visible or active page."""
        # preserve memory if erase==0; don't distingush erase==1 and erase==2
        save_mem = None
        if (not erase and self.mode.video_segment == spec.video_segment):
            save_mem = self.mode.get_all_memory(self)
        # reset palette happens even if the SCREEN call fails
        self.video.set_cga4_palette(1)
        # if the new mode has fewer pages than current vpage/apage,
        # illegal fn call before anything happens.
        # signal the signals to change the screen resolution
        if (not spec or new_apagenum >= spec.num_pages or new_vpagenum >= spec.num_pages):
            raise error.BASICError(error.IFC)
        # illegal fn call if we don't have a font for this mode
        self.text_screen.check_font_available(spec)
        # if we made it here we're ready to commit to the new mode
        self.queues.video.put(signals.Event(signals.VIDEO_SET_MODE, (spec,)))
        # switching to another text mode (width-only change)
        width_only = (self.mode.is_text_mode and spec.is_text_mode)
        # attribute and border persist on width-only change
        # otherwise start with black border and default attr
        if (not width_only or self.apagenum != new_apagenum or self.vpagenum != new_vpagenum
                or self.colorswitch != new_colorswitch):
            self.attr = spec.attr
        if (not width_only and spec.name != self.mode.name):
            self.set_border(0)
        # set the screen mode parameters
        self.mode, self._mode_nr = spec, new_mode
        # initialise the palette
        self.palette.init_mode(self.mode)
        # set the colorswitch
        self._init_mode_colorburst(new_colorswitch)
        # initialise pixel buffers
        if not self.mode.is_text_mode:
            self.pixels = PixelBuffer(self.mode.pixel_width, self.mode.pixel_height,
                                    self.mode.num_pages, self.mode.bitsperpixel)
        else:
            self.pixels = None
        # initialise text screen
        self.text_screen.init_mode(self.mode, self.pixels, self.attr, new_vpagenum, new_apagenum)
        # restore emulated video memory in new mode
        if save_mem:
            self.mode.set_all_memory(self, save_mem)
        # set active page & visible page, counting from 0.
        self.set_page(new_vpagenum, new_apagenum)
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

    def _init_mode_colorburst(self, new_colorswitch):
        """Initialise colorburst settings for new screen mode and colorswitch."""
        self.colorswitch = new_colorswitch
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if self.mode.is_text_mode:
            self.set_colorburst(new_colorswitch)
        elif self.mode.name == '320x200x4':
            self.set_colorburst(not new_colorswitch)
        elif self.mode.name == '640x200x2':
            self.set_colorburst(False)

    def set_colorburst(self, on=True):
        """Set the composite colorburst bit."""
        colorburst = self.video.set_colorburst(on, is_cga=(self.mode.name == '320x200x4'))
        # reset the palette to reflect the new mono or mode-5 situation
        # this sends the signal to the interface as well
        self.palette.init_mode(self.mode)
        # don't try composite unless our video card supports it
        if self.capabilities in modes.COMPOSITE:
            composite_artifacts = (colorburst and self.video.monitor == 'composite' and
                        (not self.mode.is_text_mode) and self.mode.supports_artifacts)
            # this is only needed because composite artifacts are implemented in the interface
            self.queues.video.put(signals.Event(
                    signals.VIDEO_SET_COMPOSITE,
                    (composite_artifacts, modes.COMPOSITE[self.capabilities])))

    def set_video_memory_size(self, new_size):
        """Change the amount of memory available to the video card."""
        # redefine number of available video pages
        self.video.prepare_modes(new_size)
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
        self.queues.video.put(signals.Event(signals.VIDEO_SET_MODE, (self.mode,)))
        # set the visible and active pages
        self.queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)))
        # rebuild palette
        self.palette.set_all(self.palette.palette, check_mode=False)
        # set the border
        fore, _, _, _ = self.mode.split_attr(self.border_attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (fore,)))
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
            fore, _, _, _ = self.mode.split_attr(attr)
            self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, (fore,)))

    def set_border(self, attr):
        """Set the border attribute."""
        self.border_attr = attr
        fore, _, _, _ = self.mode.split_attr(attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, (fore,)))

    ###########################################################################
    # memory operations

    def get_memory(self, addr, num_bytes):
        """Retrieve bytes from video memory."""
        return self.mode.get_memory(self, addr, num_bytes)

    def set_memory(self, addr, bytestr):
        """Set bytes in video memory."""
        self.mode.set_memory(self, addr, bytestr)

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
                for _, arg in zip(range(4), args))
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
            self.pixels.copy_page(src, dst)
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
        elif self.mode.name == '320x200x4':
            self._color_mode_1(fore, back, bord)
        else:
            self._color_other_modes(fore, back, bord)

    def _color_mode_1(self, back, pal, override):
        """Helper function for COLOR in SCREEN 1."""
        back = self.palette.get_entry(0) if back is None else back
        if override is not None:
            # uses last entry as palette if given
            pal = override
        error.range_check(0, 255, back)
        if pal is not None:
            error.range_check(0, 255, pal)
            self.video.set_cga4_palette(pal % 2)
            palette = list(self.mode.palette)
            palette[0] = back & 0xf
            # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
            # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15
            self.palette.set_all(palette, check_mode=False)
        else:
            self.palette.set_entry(0, back & 0xf, check_mode=False)

    def _color_other_modes(self, fore, back, bord):
        """Helper function for COLOR in modes other than SCREEN 1."""
        mode = self.mode
        if back is None:
            # graphics mode bg is always 0; sets palette instead
            if mode.is_text_mode:
                back = (self.attr >> 4) & 0x7
            else:
                back = self.palette.get_entry(0)
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
                raise error.BASICError(error.IFC)
            self.palette.set_entry(1, fore, check_mode=False)

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
            self.text_screen.bottom_bar.redraw(self.text_screen)
            self.drawing.reset()
        elif val == 1:
            # clear the graphics viewport
            if not self.mode.is_text_mode:
                self.drawing.fill_rect(*self.drawing.graph_view.get(), index=(self.attr >> 4) & 0x7)
            self.drawing.reset()
        elif val == 2:
            self.text_screen.clear_view()
