"""
PC-BASIC - textscreen.py
Text operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

from ..base import signals
from ..base import error
from ..base import tokens as tk
from .. import values
from . import font
from .text import TextBuffer, TextRow
from .textbase import BottomBar, Cursor, ScrollArea


class TextScreen(object):
    """Text screen."""

    def __init__(self, queues, values, mode, capabilities, fonts, codepage, io_streams, sound):
        """Initialise text-related members."""
        self.queues = queues
        self._values = values
        self.codepage = codepage
        self.capabilities = capabilities
        # output redirection
        self._io_streams = io_streams
        # sound output needed for printing \a
        self.sound = sound
        # cursor
        self.cursor = Cursor(queues, mode, capabilities)
        # current row and column
        # overflow: true if we're on 80 but should be on 81
        self.current_row, self.current_col, self.overflow = 1, 1, False
        # text viewport parameters
        self.scroll_area = ScrollArea(mode)
        # writing on bottom row is allowed
        self._bottom_row_allowed = False
        # prepare fonts
        if not fonts:
            fonts = {8: {}}
        self.fonts = {
                height: font.Font(height, font_dict)
                for height, font_dict in fonts.iteritems()}
        # function key macros
        self.bottom_bar = BottomBar()

    def init_mode(self, mode, pixels, attr, vpagenum, apagenum):
        """Reset the text screen for new video mode."""
        self.mode = mode
        self.attr = attr
        self.apagenum = apagenum
        self.vpagenum = vpagenum
        # set up glyph cache and preload halfwidth glyphs (i.e. single-byte code points)
        self._glyphs = font.GlyphCache(self.mode, self.fonts, self.codepage, self.queues)
        # build the screen buffer
        self.text = TextBuffer(self.attr, self.mode.width, self.mode.height, self.mode.num_pages,
                               self.codepage, do_fullwidth=(self.mode.font_height >= 14))
        # pixel buffer
        self.pixels = pixels
        # redraw key line
        self.bottom_bar.redraw(self)
        # initialise text viewport & move cursor home
        self.scroll_area.init_mode(self.mode)
        self.set_pos(self.scroll_area.top, 1)
        # rebuild the cursor
        self.cursor.init_mode(self.mode, self.attr)

    def set_page(self, vpagenum, apagenum):
        """Set visible and active page."""
        self.vpagenum = vpagenum
        self.apagenum = apagenum

    def set_attr(self, attr):
        """Set attribute."""
        self.attr = attr

    def check_font_available(self, mode):
        """Raise IFC if no suitable font available for this mode."""
        if mode.font_height not in self.fonts:
            logging.warning('No %d-pixel font available. Could not enter video mode %s.',
                            mode.font_height, mode.name)
            raise error.BASICError(error.IFC)

    def rebuild(self):
        """Completely resubmit the text screen to the interface."""
        # send the glyph dict to interface if necessary
        self._glyphs.submit()
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
        self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, (fore,)))
        self.cursor.reset_visibility()
        # redraw the text screen and rebuild text buffers in video plugin
        for pagenum in range(self.mode.num_pages):
            for row in range(self.mode.height):
                self.refresh_range(pagenum, row+1, 1, self.mode.width, text_only=True)
            # redraw graphics
            if not self.mode.is_text_mode:
                self.queues.video.put(signals.Event(signals.VIDEO_PUT_RECT, (pagenum, 0, 0,
                                self.mode.pixel_width-1, self.mode.pixel_height-1,
                                self.pixels.pages[pagenum].buffer)))

    def __str__(self):
        """Return a string representation of the screen buffer (for debugging)."""
        return str(self.text)

    ##########################################################################

    def write(self, s, scroll_ok=True, do_echo=True):
        """Write a string to the screen at the current position."""
        if do_echo:
            # CR -> CRLF, CRLF -> CRLF LF
            self._io_streams.write(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
        last = ''
        # if our line wrapped at the end before, it doesn't anymore
        self.text.pages[self.apagenum].row[self.current_row-1].wrap = False
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
                    self.text.pages[self.apagenum].row[row-1].wrap = True
                    self.set_pos(row + 1, 1, scroll_ok)
            elif c == '\r':
                # CR
                self.text.pages[self.apagenum].row[row-1].wrap = False
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
            self.text.pages[self.apagenum].row[self.current_row-3].wrap = False

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
        if (self.current_col > self.text.pages[self.apagenum].row[self.current_row-1].end):
            self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col
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
                self.text.pages[self.apagenum].row[self.current_row-1].wrap = True
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
            self._io_streams.write('\r\n')
            self._check_pos(scroll_ok=True)
            self.set_pos(self.current_row + 1, 1)
        # ensure line above doesn't wrap
        self.text.pages[self.apagenum].row[self.current_row-2].wrap = False

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
        """Increase the current position by a char width."""
        # on a trail byte: just go one to the right
        width = self.text.get_charwidth(self.apagenum, self.current_row, self.current_col) or 1
        self.set_pos(self.current_row, self.current_col + width, scroll_ok=False)

    def decr_pos(self):
        """Decrease the current position by a char width."""
        # previous is trail byte: go two to the left
        # lead byte: go three to the left
        width = self.text.get_charwidth(self.apagenum, self.current_row, self.current_col-1)
        if width == 0:
            skip = 2
        elif width == 2:
            skip = 3
        else:
            skip = 1
        self.set_pos(self.current_row, self.current_col - skip, scroll_ok=False)

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

    def move_to_end(self):
        """Jump to end of logical line; follow wraps (END)."""
        row = self.text.find_end_of_line(self.apagenum, self.current_row)
        if self.text.pages[self.apagenum].row[row-1].end == self.mode.width:
            self.set_pos(row, self.text.pages[self.apagenum].row[row-1].end)
            self.overflow = True
        else:
            self.set_pos(row, self.text.pages[self.apagenum].row[row-1].end+1)

    ###########################################################################

    def put_char_attr(self, pagenum, row, col, c, attr, one_only=False):
        """Put a byte to the screen, redrawing as necessary."""
        if not self.mode.is_text_mode:
            attr = attr & 0xf
        start, stop = self.text.put_char_attr(pagenum, row, col, c, attr)
        if one_only:
            stop = start
        # update the screen
        self.refresh_range(pagenum, row, start, stop)

    ###########################################################################

    def refresh_range(self, pagenum, row, start, stop, text_only=False):
        """Redraw a section of a screen row, assuming DBCS buffer has been set."""
        therow = self.text.pages[pagenum].row[row-1]
        col = start
        while col <= stop:
            r, c = row, col
            char, attr = self.text.get_fullchar_attr(pagenum, row, col)
            col += len(char)
            # ensure glyph is stored
            self._glyphs.check_char(char)
            fore, back, blink, underline = self.mode.split_attr(attr)
            self.queues.video.put(signals.Event(signals.VIDEO_PUT_GLYPH, (
                    pagenum, r, c, self.codepage.to_unicode(char, u'\0'),
                    len(char) > 1, fore, back, blink, underline,
            )))
            if not self.mode.is_text_mode and not text_only:
                # update pixel buffer
                x0, y0, x1, y1, sprite = self._glyphs.get_sprite(r, c, char, fore, back)
                self.pixels.pages[self.apagenum].put_rect(x0, y0, x1, y1, sprite, tk.PSET)
                self.queues.video.put(signals.Event(
                        signals.VIDEO_PUT_RECT, (self.apagenum, x0, y0, x1, y1, sprite)))

    def _redraw_row(self, start, row, wrap=True):
        """Draw the screen row, wrapping around and reconstructing DBCS buffer."""
        while True:
            for i in range(start, self.text.pages[self.apagenum].row[row-1].end):
                # redrawing changes colour attributes to current foreground (cf. GW)
                # don't update all dbcs chars behind at each put
                char = chr(self.text.get_char(self.apagenum, row, i+1))
                self.put_char_attr(self.apagenum, row, i+1, char, self.attr, one_only=True)
            if (wrap and self.text.pages[self.apagenum].row[row-1].wrap and row >= 0 and row < self.text.height-1):
                row += 1
                start = 0
            else:
                break

    def clear_from(self, srow, scol):
        """Clear from given position to end of logical line (CTRL+END)."""
        self.text.pages[self.apagenum].row[srow-1].clear_from(scol, self.attr)
        row = srow
        # can use self.text.find_end_of_line
        while self.text.pages[self.apagenum].row[row-1].wrap:
            row += 1
            self.text.pages[self.apagenum].row[row-1].clear(self.attr)
        for r in range(row, srow, -1):
            self.text.pages[self.apagenum].row[r-1].wrap = False
            self.scroll(r)
        therow = self.text.pages[self.apagenum].row[srow-1]
        therow.wrap = False
        self.set_pos(srow, scol)
        save_end = therow.end
        therow.end = self.mode.width
        if scol > 1:
            self._redraw_row(scol-1, srow)
        else:
            # inelegant: we're clearing the text buffer for a second time now
            self.clear_rows(srow, srow)
        therow.end = save_end

    ###########################################################################
    # clearing text screen

    def clear_rows(self, start, stop):
        """Clear text and graphics on given (inclusive) text row range."""
        for r in self.text.pages[self.apagenum].row[start-1:stop]:
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
    # console operations

    def delete_fullchar(self):
        """Delete the character (single/double width) at the current position."""
        row, col = self.current_row, self.current_col
        cwidth = self.text.get_charwidth(self.apagenum, self.current_row, self.current_col)
        if cwidth == 0:
            logging.debug('DBCS trail byte delete at %d, %d.', self.current_row, self.current_col)
            self.set_pos(self.current_row, self.current_col-1)
            cwidth = 2
        text = self.text.get_logical_line(self.apagenum, self.current_row, self.current_col)
        lastrow = self.text.find_end_of_line(self.apagenum, self.current_row)
        if self.current_col > self.text.pages[self.apagenum].row[self.current_row-1].end:
            # past the end. if this row ended with LF, attach next row and scroll further rows up
            # if not, do nothing
            if not self.text.pages[self.apagenum].row[self.current_row-1].wrap:
                return
            # else: LF case; scroll up without changing attributes
            self.text.pages[self.apagenum].row[self.current_row-1].wrap = self.text.pages[self.apagenum].row[self.current_row].wrap
            self.scroll(self.current_row + 1)
            # redraw from the LF
            self._rewrite_for_delete(text[1:] + b' ' * cwidth)
        else:
            # rewrite the contents (with the current attribute!)
            self._rewrite_for_delete(text[cwidth:] + b' ' * cwidth)
            # if last row was empty, scroll up.
            if self.text.pages[self.apagenum].row[lastrow-1].end == 0 and self.text.pages[self.apagenum].row[lastrow-2].wrap:
                self.text.pages[self.apagenum].row[lastrow-2].wrap = False
                self.scroll(lastrow)
        # restore original position
        self.set_pos(row, col)

    def _rewrite_for_delete(self, text):
        """Rewrite text contents (with the current attribute)."""
        for c in text:
            if c == b'\n':
                self.put_char_attr(self.apagenum, self.current_row, self.current_col, b' ', self.attr)
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col-1
                break
            else:
                self.put_char_attr(self.apagenum, self.current_row, self.current_col, c, self.attr)
                self.set_pos(self.current_row, self.current_col+1)
        else:
            # we're on the position after the additional space
            if self.current_col == 1:
                self.current_row -= 1
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.mode.width - 1
            else:
                # adjust row end
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col - 2

    def insert_fullchars(self, row, col, sequence, attr):
        """Insert one or more single- or double-width characters at the current position."""
        start_row, start_col = row, col
        for c in sequence:
            while True:
                therow = self.text.pages[self.apagenum].row[row-1]
                therow.buf.insert(col-1, (c, attr))
                if therow.end < self.mode.width:
                    therow.buf.pop()
                    if therow.end > col-1:
                        therow.end += 1
                    else:
                        therow.end = col
                    break
                else:
                    if row == self.scroll_area.bottom:
                        self.scroll()
                        row -= 1
                    if not therow.wrap and row < self.mode.height:
                        self.scroll_down(row+1)
                        therow.wrap = True
                    c, attr = therow.buf.pop()
                    row += 1
                    col = 1
            col += 1
        self._redraw_row(start_col-1, start_row)

    def line_feed(self):
        """Move the remainder of the line to the next row and wrap (LF)."""
        row, col = self.current_row, self.current_col
        if col < self.text.pages[self.apagenum].row[row-1].end:
            self.insert_fullchars(row, col, b' ' * (self.mode.width-col+1), self.attr)
            self.text.pages[self.apagenum].row[row-1].end = col - 1
        else:
            while (self.text.pages[self.apagenum].row[row-1].wrap and row < self.scroll_area.bottom):
                row += 1
            if row >= self.scroll_area.bottom:
                self.scroll()
            # self.current_row has changed, don't use row var
            if self.current_row < self.mode.height:
                self.scroll_down(self.current_row+1)
        # LF connects lines like word wrap
        self.text.pages[self.apagenum].row[self.current_row-1].wrap = True
        self.set_pos(self.current_row+1, 1)

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
    # text screen callbacks

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
