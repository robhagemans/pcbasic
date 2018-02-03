"""
PC-BASIC - screen.py
Screen operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

from ..base import signals
from ..base import error
from ..base import tokens as tk
from .. import values
from . import graphics
from . import font
from . import modes

from .display import BottomBar, Palette, Cursor, ScrollArea
from .text import TextBuffer, TextRow
from .pixels import PixelBuffer
from .modes import Video


class Screen(object):
    """Screen manipulation operations."""

    def __init__(self, queues, values, input_methods, memory,
                initial_width, video_mem_size, capabilities, monitor, sound, redirect,
                cga_low, mono_tint, screen_aspect, codepage, fonts):
        """Minimal initialisiation of the screen."""
        self.queues = queues
        self._values = values
        self._memory = memory
        self.codepage = codepage
        # needed for printing \a
        self.sound = sound
        # output redirection
        self.redirect = redirect
        # low level settings
        self.video = Video(
                capabilities, monitor, mono_tint, cga_low,
                screen_aspect, video_mem_size)
        self.capabilities = self.video.capabilities
        # video mode settings
        self._mode_nr, self.colorswitch, self.apagenum, self.vpagenum = 0, 1, 0, 0
        # prepare video modes
        self.mode = self.video.get_mode(0, initial_width)
        # current attribute
        self.attr = 7
        # border attribute
        self.border_attr = 0
        # cursor
        self.cursor = Cursor(self.queues, self.mode, self.capabilities)
        # current row and column
        # overflow: true if we're on 80 but should be on 81
        self.current_row, self.current_col, self.overflow = 1, 1, False
        # text viewport parameters
        self.scroll_area = ScrollArea(self.mode)
        # writing on bottom row is allowed
        self._bottom_row_allowed = False
        # prepare fonts
        self.fonts = {height: font.Font(height, font_dict) for height, font_dict in fonts.iteritems()}
        # function key macros
        self.bottom_bar = BottomBar()
        self.drawing = graphics.Drawing(self, input_methods, values, memory)
        self.palette = Palette(self.queues, self.mode, self.capabilities, self._memory)
        # initialise a fresh textmode screen
        self.set_mode_(self.mode, 0, 1, 0, 0)

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
            self.set_mode_(
                    info, new_mode, new_colorswitch, new_apagenum, new_vpagenum, erase)
        else:
            # only switch pages
            if (new_apagenum >= info.num_pages or new_vpagenum >= info.num_pages):
                raise error.BASICError(error.IFC)
            self.set_page(new_vpagenum, new_apagenum)

    def set_mode_(self, spec, new_mode, new_colorswitch,
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
        if spec.font_height not in self.fonts:
            logging.warning('No %d-pixel font available. Could not enter video mode %s.',
                            spec.font_height, spec.name)
            raise error.BASICError(error.IFC)
        # if we made it here we're ready to commit to the new mode
        self.queues.video.put(signals.Event(signals.VIDEO_SET_MODE, spec))
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
        # set up glyph cache and preload halfwidth glyphs (i.e. single-byte code points)
        self._glyphs = font.GlyphCache(self.mode, self.fonts, self.codepage, self.queues)
        # build the screen buffer
        self.text = TextBuffer(self.attr, self.mode.width, self.mode.height, self.mode.num_pages,
                               self.codepage, do_fullwidth=(self.mode.font_height >= 14))
        if not self.mode.is_text_mode:
            self.pixels = PixelBuffer(self.mode.pixel_width, self.mode.pixel_height,
                                    self.mode.num_pages, self.mode.bitsperpixel)
        # set active page & visible page, counting from 0.
        self.set_page(new_vpagenum, new_apagenum)
        # set graphics viewport
        self.graph_view = graphics.GraphicsViewPort(
                self.mode.pixel_width, self.mode.pixel_height)
        # initialise the palette
        self.palette.init_mode(self.mode)
        # set the cursor attribute
        if not self.mode.is_text_mode:
            fore, _, _, _ = self.mode.split_attr(self.mode.cursor_index or self.attr)
            self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))
        # set the colorswitch
        self._init_mode_colorburst(new_colorswitch)
        # restore emulated video memory in new mode
        if save_mem:
            self.mode.set_all_memory(self, save_mem)
        # center graphics cursor, reset window, etc.
        self.drawing.init_mode()
        # redraw key line
        self.bottom_bar.redraw(self)
        # initialise text viewport & move cursor home
        self.scroll_area.init_mode(self.mode)
        self.set_pos(self.scroll_area.top, 1)
        # rebuild the cursor
        self.cursor.init_mode(self.mode)

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
        self.palette.init_mode(self.mode)
        # this is only needed because composite artifacts are implemented in the interface
        self.queues.video.put(signals.Event(signals.VIDEO_SET_COLORBURST, (colorburst,
                            self.palette.rgb_palette, self.palette.rgb_palette1)))

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
        """Rebuild the screen from scratch."""
        # set the screen mode
        self.queues.video.put(signals.Event(signals.VIDEO_SET_MODE, self.mode))
        # send the glyph dict to interface if necessary
        self._glyphs.submit()
        # set the visible and active pages
        self.queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (self.vpagenum, self.apagenum)))
        # rebuild palette
        self.palette.set_all(self.palette.palette, check_mode=False)
        # fix the cursor
        self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_SHAPE,
                (self.cursor.width, self.mode.font_height,
                 self.cursor.from_line, self.cursor.to_line)))
        self.queues.video.put(signals.Event(signals.VIDEO_MOVE_CURSOR,
                (self.current_row, self.current_col)))
        if self.mode.is_text_mode:
            attr = self.text.get_attr(self.apagenum, self.current_row, self.current_col)
            fore, _, _, _ = self.mode.split_attr(attr & 0xf)
        else:
            fore, _, _, _ = self.mode.split_attr(self.mode.cursor_index or self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))
        self.cursor.reset_visibility()
        # set the border
        fore, _, _, _ = self.mode.split_attr(self.border_attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, fore))
        # redraw the text screen and rebuild text buffers in video plugin
        for pagenum in range(self.mode.num_pages):
            for crow in range(self.mode.height):
                # suppress_cli=True means 'suppress echo on cli'
                self.refresh_range(pagenum, crow+1, 1, self.mode.width,
                                   suppress_cli=True, text_only=True)
            # redraw graphics
            if not self.mode.is_text_mode:
                self.queues.video.put(signals.Event(signals.VIDEO_PUT_RECT, (pagenum, 0, 0,
                                self.mode.pixel_width-1, self.mode.pixel_height-1,
                                self.pixels.pages[pagenum].buffer)))

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
        self.vpage = self.text.pages[new_vpagenum]
        self.apage = self.text.pages[new_apagenum]
        self.queues.video.put(signals.Event(signals.VIDEO_SET_PAGE, (new_vpagenum, new_apagenum)))

    def set_attr(self, attr):
        """Set the default attribute."""
        self.attr = attr
        if not self.mode.is_text_mode and self.mode.cursor_index is None:
            fore, _, _, _ = self.mode.split_attr(attr)
            self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, fore))

    def set_border(self, attr):
        """Set the border attribute."""
        self.border_attr = attr
        fore, _, _, _ = self.mode.split_attr(attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_BORDER_ATTR, fore))

    ###########################################################################
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

    def write_line(self, s=b'', scroll_ok=True, do_echo=True):
        """Write a string to the screen and end with a newline."""
        self.write(b'%s\r' % (s,), scroll_ok, do_echo)

    def list_line(self, line, newline=True):
        """Print a line from a program listing or EDIT prompt."""
        # no wrap if 80-column line, clear row before printing.
        # replace LF CR with LF
        line = line.replace(b'\n\r', b'\n')
        cuts = line.split(b'\n')
        for i, l in enumerate(cuts):
            # clear_line looks back along wraps, use screen.clear_from instead
            self.clear_from(self.current_row, 1)
            self.write(str(l))
            if i != len(cuts) - 1:
                self.write(b'\n')
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
        self._check_pos(scroll_ok=True)
        # put the character
        self.put_char_attr(self.apagenum, self.current_row, self.current_col, c, self.attr)
        # adjust end of line marker
        if (self.current_col > self.apage.row[self.current_row-1].end):
            self.apage.row[self.current_row-1].end = self.current_col
        # move cursor. if on col 80, only move cursor to the next row
        # when the char is printed
        if self.current_col < self.mode.width:
            self.current_col += 1
        else:
            self.overflow = True
        # move cursor and see if we need to scroll up
        self._check_pos(scroll_ok=True)

    def _check_wrap(self, do_scroll_down):
        """Wrap if we need to."""
        if self.current_col > self.mode.width:
            if self.current_row < self.mode.height:
                # wrap line
                self.apage.row[self.current_row-1].wrap = True
                if do_scroll_down:
                    # scroll down (make space by shifting the next rows down)
                    if self.current_row < self.scroll_area.bottom:
                        self.scroll_down(self.current_row+1)
                # move cursor and reset cursor attribute
                self._move_cursor(self.current_row + 1, 1)
            else:
                self.current_col = self.mode.width

    def start_line(self):
        """Move the cursor to the start of the next line, this line if empty."""
        if self.current_col != 1:
            self.redirect.write('\r\n')
            self._check_pos(scroll_ok=True)
            self.set_pos(self.current_row + 1, 1)
        # ensure line above doesn't wrap
        self.apage.row[self.current_row-2].wrap = False

    ###########################################################################
    # cursor position

    def set_pos(self, to_row, to_col, scroll_ok=True):
        """Set the current position."""
        self.overflow = False
        self.current_row, self.current_col = to_row, to_col
        # move cursor and reset cursor attribute
        # this may alter self.current_row, self.current_col
        self._check_pos(scroll_ok)

    def incr_pos(self):
        """Increase the current position by one."""
        # skip dbcs trail byte
        row, col = self.current_row, self.current_col
        width = self.text.get_charwidth(self.apagenum, row, col) or 1
        self.set_pos(row, col + width, scroll_ok=False)

    def _check_pos(self, scroll_ok=True):
        """Check if we have crossed the screen boundaries and move as needed."""
        oldrow, oldcol = self.current_row, self.current_col
        if self._bottom_row_allowed:
            if self.current_row == self.mode.height:
                self.current_col = min(self.mode.width, self.current_col)
                if self.current_col < 1:
                    self.current_col += 1
                self._move_cursor(self.current_row, self.current_col)
                return self.current_col == oldcol
            else:
                # if row > height, we also end up here
                # (eg if we do INPUT on the bottom row)
                # adjust viewport if necessary
                self._bottom_row_allowed = False
        # see if we need to move to the next row
        if self.current_col > self.mode.width:
            if self.current_row < self.scroll_area.bottom or scroll_ok:
                # either we don't nee to scroll, or we're allowed to
                self.current_col -= self.mode.width
                self.current_row += 1
            else:
                # we can't scroll, so we just stop at the right border
                self.current_col = self.mode.width
        # see if we need to move a row up
        elif self.current_col < 1:
            if self.current_row > self.scroll_area.top:
                self.current_col += self.mode.width
                self.current_row -= 1
            else:
                self.current_col = 1
        # see if we need to scroll
        if self.current_row > self.scroll_area.bottom:
            if scroll_ok:
                self.scroll()
            self.current_row = self.scroll_area.bottom
        elif self.current_row < self.scroll_area.top:
            self.current_row = self.scroll_area.top
        self._move_cursor(self.current_row, self.current_col)
        # signal position change
        return (self.current_row == oldrow and
                 self.current_col == oldcol)

    def _move_cursor(self, row, col):
        """Move the cursor to a new position."""
        self.current_row, self.current_col = row, col
        # set halfwidth/fullwidth cursor
        width = self.text.get_charwidth(self.apagenum, self.current_row, self.current_col)
        self.cursor.set_width(width)
        # set the cursor's attribute to that of the current location
        fore, _, _, _ = self.mode.split_attr(0xf &
                self.text.get_attr(self.apagenum, self.current_row, self.current_col))
        self.cursor.reset_attr(fore)
        self.queues.video.put(signals.Event(signals.VIDEO_MOVE_CURSOR,
                (self.current_row, self.current_col)))

    ###########################################################################

    def put_char_attr(self, pagenum, row, col, c, attr, one_only=False, suppress_cli=False):
        """Put a byte to the screen, redrawing as necessary."""
        if not self.mode.is_text_mode:
            attr = attr & 0xf
        start, stop = self.text.put_char_attr(pagenum, row, col, c, attr)
        if one_only:
            stop = start
        # update the screen
        self.refresh_range(pagenum, row, start, stop, suppress_cli)

    ###########################################################################

    def refresh_range(self, pagenum, crow, start, stop, suppress_cli=False, text_only=False):
        """Redraw a section of a screen row, assuming DBCS buffer has been set."""
        therow = self.text.pages[pagenum].row[crow-1]
        ccol = start
        while ccol <= stop:
            r, c = crow, ccol
            char, attr = self.text.get_fullchar_attr(pagenum, crow, ccol)
            ccol += len(char)
            # ensure glyph is stored
            self._glyphs.check_char(char)
            fore, back, blink, underline = self.mode.split_attr(attr)
            self.queues.video.put(signals.Event(signals.VIDEO_PUT_GLYPH, (
                    pagenum, r, c, self.codepage.to_unicode(char, u'\0'),
                    len(char) > 1, fore, back, blink, underline, suppress_cli
            )))
            if not self.mode.is_text_mode and not text_only:
                # update pixel buffer
                x0, y0, x1, y1, sprite = self._glyphs.get_sprite(r, c, char, fore, back)
                self.pixels.pages[self.apagenum].put_rect(x0, y0, x1, y1, sprite, tk.PSET)
                self.queues.video.put(signals.Event(
                        signals.VIDEO_PUT_RECT, (self.apagenum, x0, y0, x1, y1, sprite)))

    def redraw_row(self, start, row, wrap=True):
        """Draw the screen row, wrapping around and reconstructing DBCS buffer."""
        while True:
            for i in range(start, self.apage.row[row-1].end):
                # redrawing changes colour attributes to current foreground (cf. GW)
                # don't update all dbcs chars behind at each put
                char = chr(self.text.get_char(self.apagenum, row, i+1))
                self.put_char_attr(self.apagenum, row, i+1, char, self.attr, one_only=True)
            if (wrap and self.apage.row[row-1].wrap and row >= 0 and row < self.text.height-1):
                row += 1
                start = 0
            else:
                break

    def clear_from(self, srow, scol):
        """Clear from given position to end of logical line (CTRL+END)."""
        self.apage.row[srow-1].clear_from(scol, self.attr)
        crow = srow
        # can use self.text.find_end_of_line
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
        therow.end = self.mode.width
        if scol > 1:
            self.redraw_row(scol-1, srow)
        else:
            # inelegant: we're clearing the text buffer for a second time now
            self.clear_rows(srow, srow)
        therow.end = save_end

    ###########################################################################
    # clearing text screen

    def clear_rows(self, start, stop):
        """Clear text and graphics on given (inclusive) text row range."""
        for r in self.apage.row[start-1:stop]:
            r.clear(self.attr)
            # can't we just do this in row.clear?
            r.wrap = False
        if not self.mode.is_text_mode:
            x0, y0, x1, y1 = self.mode.text_to_pixel_area(start, 1, stop, self.mode.width)
            # background attribute must be 0 in graphics mode
            self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, 0)
        _, back, _, _ = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_CLEAR_ROWS, (back, start, stop)))

    def _clear_area(self, start_row, stop_row):
        """Clear the screen or the scroll area."""
        if self.capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # keep background, set foreground to 7
            attr_save = self.attr
            self.set_attr(attr_save & 0x70 | 0x7)
        self.clear_rows(start_row, stop_row)
        # ensure the cursor is shown in the right position
        self.set_pos(start_row, 1)
        if self.capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # restore attr
            self.set_attr(attr_save)

    def clear_view(self):
        """Clear the scroll area."""
        self._clear_area(self.scroll_area.top, self.scroll_area.bottom)

    def clear(self):
        """Clear the screen."""
        self._clear_area(1, self.mode.height)

    ###########################################################################
    # text viewport / scroll area

    def _set_scroll_area(self, start, stop):
        """Set the scroll area."""
        self.scroll_area.set(start, stop)
        #set_pos(start, 1)
        self.overflow = False
        self._move_cursor(start, 1)

    ###########################################################################
    # scrolling

    def scroll(self, from_line=None):
        """Scroll the scroll region up by one line, starting at from_line."""
        if from_line is None:
            from_line = self.scroll_area.top
        _, back, _, _ = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SCROLL_UP,
                    (from_line, self.scroll_area.bottom, back)))
        if self.current_row > from_line:
            self.current_row -= 1
        # sync buffers with the new screen reality:
        self.text.scroll_up(self.apagenum, from_line, self.scroll_area.bottom, self.attr)
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.mode.text_to_pixel_area(from_line+1, 1,
                self.scroll_area.bottom, self.mode.width)
            tx0, ty0, _, _ = self.mode.text_to_pixel_area(from_line, 1,
                self.scroll_area.bottom-1, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)

    def scroll_down(self, from_line):
        """Scroll the scroll region down by one line, starting at from_line."""
        _, back, _, _ = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SCROLL_DOWN,
                    (from_line, self.scroll_area.bottom, back)))
        if self.current_row >= from_line:
            self.current_row += 1
        # sync buffers with the new screen reality:
        self.text.scroll_down(self.apagenum, from_line, self.scroll_area.bottom, self.attr)
        if not self.mode.is_text_mode:
            sx0, sy0, sx1, sy1 = self.mode.text_to_pixel_area(from_line, 1,
                self.scroll_area.bottom-1, self.mode.width)
            tx0, ty0, _, _ = self.mode.text_to_pixel_area(from_line+1, 1,
                self.scroll_area.bottom, self.mode.width)
            self.pixels.pages[self.apagenum].move_rect(sx0, sy0, sx1, sy1, tx0, ty0)

    ###########################################################################
    # vpage text retrieval

    def print_screen(self, target_file):
        """Output the visible page to file in raw bytes."""
        if not target_file:
            return
        for line in self.text.get_text_raw(self.vpagenum):
            target_file.write_line(line.replace(b'\0', b' '))

    def copy_clipboard(self, start_row, start_col, stop_row, stop_col, is_mouse_selection):
        """Copy selected screen area to clipboard."""
        clips = self.text.get_text_logical(
                self.vpagenum, start_row, start_col, stop_row, stop_col)
        text = u'\n'.join(self.codepage.str_to_unicode(clip) for clip in clips)
        self.queues.video.put(signals.Event(
                signals.VIDEO_SET_CLIPBOARD_TEXT, (text, is_mouse_selection)))

    ###########################################################################
    # memory operations

    def get_memory(self, addr, num_bytes):
        """Retrieve bytes from video memory."""
        return self.mode.get_memory(self, addr, num_bytes)

    def set_memory(self, addr, bytestr):
        """Set bytes in video memory."""
        self.mode.set_memory(self, addr, bytestr)

    ###########################################################################
    # text/graphics interaction

    def clear_text_at(self, x, y):
        """Remove the character covering a single pixel."""
        row, col = self.mode.pixel_to_text_pos(x, y)
        if col >= 1 and row >= 1 and col <= self.mode.width and row <= self.mode.height:
            self.text.put_char_attr(self.apagenum, row, col, b' ', self.attr)
        fore, back, blink, underline = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_PUT_GLYPH,
                (self.apagenum, row, col, u' ', False, fore, back, blink, underline, True)))

    def clear_text_area(self, x0, y0, x1, y1):
        """Remove all characters from the text buffer on a rectangle of the graphics screen."""
        row0, col0, row1, col1 = self.mode.pixel_to_text_area(x0, y0, x1, y1)
        self.text.clear_area(self.apagenum, row0, col0, row1, col1, self.attr)

    ###########################################################################
    # graphics primitives

    def put_pixel(self, x, y, index, pagenum=None):
        """Put a pixel on the screen; empty character buffer."""
        if pagenum is None:
            pagenum = self.apagenum
        if self.graph_view.contains(x, y):
            self.pixels.pages[pagenum].put_pixel(x, y, index)
            self.queues.video.put(signals.Event(signals.VIDEO_PUT_PIXEL, (pagenum, x, y, index)))
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
        self.queues.video.put(signals.Event(signals.VIDEO_PUT_INTERVAL, (pagenum, x, y, newcolours)))
        self.clear_text_area(x, y, x+len(colours), y)

    def fill_interval(self, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""
        x0, x1, y = self.graph_view.clip_interval(x0, x1, y)
        self.pixels.pages[self.apagenum].fill_interval(x0, x1, y, index)
        self.queues.video.put(signals.Event(signals.VIDEO_FILL_INTERVAL,
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
        self.queues.video.put(signals.Event(signals.VIDEO_PUT_RECT,
                              (self.apagenum, x0, y0, x1, y1, rect)))
        self.clear_text_area(x0, y0, x1, y1)

    def fill_rect(self, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""
        x0, y0, x1, y1 = self.graph_view.clip_rect(x0, y0, x1, y1)
        self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, index)
        self.queues.video.put(signals.Event(signals.VIDEO_FILL_RECT,
                                (self.apagenum, x0, y0, x1, y1, index)))
        self.clear_text_area(x0, y0, x1, y1)

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
        self.text.copy_page(src, dst)
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
            if self.graph_view.is_set():
                val = 1
            elif self.scroll_area.active:
                val = 2
            else:
                val = 0
        list(args)
        # cls is only executed if no errors have occurred
        if val == 0:
            self.clear()
            self.bottom_bar.redraw(self)
            self.drawing.reset()
        elif val == 1:
            # clear the graphics viewport
            if not self.mode.is_text_mode:
                self.fill_rect(*self.graph_view.get(), index=(self.attr >> 4) & 0x7)
            self.drawing.reset()
        elif val == 2:
            self.clear_view()

    def locate_(self, args):
        """LOCATE: Set cursor position, shape and visibility."""
        args = list(None if arg is None else values.to_int(arg) for arg in args)
        args = args + [None] * (5-len(args))
        row, col, cursor, start, stop = args
        row = self.current_row if row is None else row
        col = self.current_col if col is None else col
        cmode = self.mode
        error.throw_if(row == cmode.height and self.bottom_bar.visible)
        if self.scroll_area.active:
            error.range_check(self.scroll_area.top, self.scroll_area.bottom, row)
        else:
            error.range_check(1, cmode.height, row)
        error.range_check(1, cmode.width, col)
        if row == cmode.height:
            # temporarily allow writing on last row
            self._bottom_row_allowed = True
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

    def csrlin_(self, args):
        """CSRLIN: get the current screen row."""
        list(args)
        if (self.overflow and self.current_col == self.mode.width and
                                    self.current_row < self.scroll_area.bottom):
            # in overflow position, return row+1 except on the last row
            csrlin = self.current_row + 1
        else:
            csrlin = self.current_row
        return self._values.new_integer().from_int(csrlin)

    def pos_(self, args):
        """POS: get the current screen column."""
        list(args)
        if self.current_col == self.mode.width and self.overflow:
            # in overflow position, return column 1.
            pos = 1
        else:
            pos = self.current_col
        return self._values.new_integer().from_int(pos)

    def screen_fn_(self, args):
        """SCREEN: get char or attribute at a location."""
        row = values.to_integer(next(args))
        col = values.to_integer(next(args))
        want_attr = next(args)
        if want_attr is not None:
            want_attr = values.to_integer(want_attr)
            want_attr = want_attr.to_int()
            error.range_check(0, 255, want_attr)
        row, col = row.to_int(), col.to_int()
        error.range_check(0, self.mode.height, row)
        error.range_check(0, self.mode.width, col)
        error.throw_if(row == 0 and col == 0)
        list(args)
        row = row or 1
        col = col or 1
        if self.scroll_area.active:
            error.range_check(self.scroll_area.top, self.scroll_area.bottom, row)
        if want_attr:
            if not self.mode.is_text_mode:
                result = 0
            else:
                result = self.text.get_attr(self.apagenum, row, col)
        else:
            result = self.text.get_char(self.apagenum, row, col)
        return self._values.new_integer().from_int(result)

    def view_print_(self, args):
        """VIEW PRINT: set scroll region."""
        start, stop = (None if arg is None else values.to_int(arg) for arg in args)
        if start is None and stop is None:
            self.scroll_area.unset()
        else:
            max_line = 25 if (self.capabilities in ('pcjr', 'tandy') and not self.bottom_bar.visible) else 24
            error.range_check(1, max_line, start, stop)
            error.throw_if(stop < start)
            self._set_scroll_area(start, stop)

    def point_(self, args):
        """POINT (1 argument): Return current coordinate (2 arguments): Return the attribute of a pixel."""
        arg0 = next(args)
        arg1 = next(args)
        if arg1 is None:
            arg0 = values.to_integer(arg0)
            fn = values.to_int(arg0)
            error.range_check(0, 3, fn)
            list(args)
            if self.mode.is_text_mode:
                return self._values.new_single()
            if fn in (0, 1):
                point = self.drawing.last_point[fn]
            elif fn in (2, 3):
                point = self.drawing.get_window_logical(*self.drawing.last_point)[fn - 2]
            return self._values.new_single().from_value(point)
        else:
            if self.mode.is_text_mode:
                raise error.BASICError(error.IFC)
            arg1 = values.pass_number(arg1)
            list(args)
            x, y = values.to_single(arg0).to_value(), values.to_single(arg1).to_value()
            x, y = self.graph_view.coords(*self.drawing.get_window_physical(x, y))
            if x < 0 or x >= self.mode.pixel_width or y < 0 or y >= self.mode.pixel_height:
                point = -1
            else:
                point = self.get_pixel(x, y)
            return self._values.new_integer().from_int(point)

    def pmap_(self, args):
        """PMAP: convert between logical and physical coordinates."""
        # create a new Single for the return value
        coord = values.to_single(next(args))
        mode = values.to_integer(next(args))
        list(args)
        mode = mode.to_int()
        error.range_check(0, 3, mode)
        if self.mode.is_text_mode:
            if mode in (2, 3):
                values.to_integer(coord)
            value = 0
        elif mode == 0:
            value, _ = self.drawing.get_window_physical(values.to_single(coord).to_value(), 0.)
        elif mode == 1:
            _, value = self.drawing.get_window_physical(0., values.to_single(coord).to_value())
        elif mode == 2:
            value, _ = self.drawing.get_window_logical(values.to_integer(coord).to_int(), 0)
        elif mode == 3:
            _, value = self.drawing.get_window_logical(0, values.to_integer(coord).to_int())
        return self._values.new_single().from_value(value)
