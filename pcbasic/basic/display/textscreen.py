"""
PC-BASIC - textscreen.py
Text operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from contextlib import contextmanager

from ...compat import iterchar, iteritems, int2byte

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
            for height, font_dict in iteritems(fonts)
        }
        # function key macros
        self.bottom_bar = BottomBar()

    def init_mode(self, mode, pixels, attr, vpagenum, apagenum):
        """Reset the text screen for new video mode."""
        self.mode = mode
        self.attr = attr
        self.apagenum = apagenum
        self.vpagenum = vpagenum
        # get glyph cache and initialise for this mode's font width (8 or 9 pixels)
        self._glyphs = self.fonts[self.mode.font_height].init_mode(self.mode.font_width)
        # build the screen buffer
        self.text = TextBuffer(
            self.attr, self.mode.width, self.mode.height, self.mode.num_pages,
            self.codepage, do_fullwidth=(self.mode.font_height >= 14)
        )
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
            logging.warning(
                'No %d-pixel font available. Could not enter video mode %s.',
                mode.font_height, mode.name
            )
            raise error.BASICError(error.IFC)

    def __repr__(self):
        """Return an ascii representation of the screen buffer (for debugging)."""
        return repr(self.text)

    ##########################################################################

    def write(self, s, scroll_ok=True, do_echo=True):
        """Write a string to the screen at the current position."""
        if do_echo:
            # CR -> CRLF, CRLF -> CRLF LF
            self._io_streams.write(b''.join([(b'\r\n' if c == b'\r' else c) for c in iterchar(s)]))
        last = b''
        # if our line wrapped at the end before, it doesn't anymore
        self.text.pages[self.apagenum].row[self.current_row-1].wrap = False
        for c in iterchar(s):
            row, col = self.current_row, self.current_col
            if c == b'\t':
                # TAB
                num = (8 - (col - 1 - 8 * int((col-1) // 8)))
                for _ in range(num):
                    self.write_char(b' ')
            elif c == b'\n':
                # LF
                # exclude CR/LF
                if last != b'\r':
                    # LF connects lines like word wrap
                    self.text.pages[self.apagenum].row[row-1].wrap = True
                    self.set_pos(row + 1, 1, scroll_ok)
            elif c == b'\r':
                # CR
                self.text.pages[self.apagenum].row[row-1].wrap = False
                self.set_pos(row + 1, 1, scroll_ok)
            elif c == b'\a':
                # BEL
                self.sound.beep()
            elif c == b'\x0B':
                # HOME
                self.set_pos(1, 1, scroll_ok)
            elif c == b'\x0C':
                # CLS
                self.clear_view()
            elif c == b'\x1C':
                # RIGHT
                self.set_pos(row, col + 1, scroll_ok)
            elif c == b'\x1D':
                # LEFT
                self.set_pos(row, col - 1, scroll_ok)
            elif c == b'\x1E':
                # UP
                self.set_pos(row - 1, col, scroll_ok)
            elif c == b'\x1F':
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
            self.write(l)
            if i != len(cuts) - 1:
                self.write(b'\n')
        if newline:
            self.write_line()
        # remove wrap after 80-column program line
        if len(line) == self.mode.width and self.current_row > 2:
            self.text.pages[self.apagenum].row[self.current_row-3].wrap = False


    ###########################################################################

    def write_char(self, c, do_scroll_down=False):
        """Put one character at the current position."""
        # check if scroll & repositioning needed
        if self.overflow:
            self.current_col += 1
            self.overflow = False
        # see if we need to wrap and scroll down
        self._check_wrap(do_scroll_down)
        # move cursor and see if we need to scroll up
        self._check_pos(scroll_ok=True)
        # put the character
        start, stop = self.text.put_char_attr(
            self.apagenum, self.current_row, self.current_col, c, self.attr, adjust_end=True
        )
        self.refresh_range(self.apagenum, self.current_row, start, stop)
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
                if do_scroll_down:
                    # scroll down (make space by shifting the next rows down)
                    if self.current_row < self.scroll_area.bottom:
                        self.scroll_down(self.current_row+1)
                # wrap line
                self.text.pages[self.apagenum].row[self.current_row-1].wrap = True
                # move cursor and reset cursor attribute
                self._move_cursor(self.current_row + 1, 1)
            else:
                self.current_col = self.mode.width

    def start_line(self):
        """Move the cursor to the start of the next line, this line if empty."""
        if self.current_col != 1:
            self._io_streams.write(b'\r\n')
            self._check_pos(scroll_ok=True)
            self.set_pos(self.current_row + 1, 1)
        # ensure line above doesn't wrap
        self.text.pages[self.apagenum].row[self.current_row-2].wrap = False

    ###########################################################################
    # cursor position

    def incr_pos(self):
        """Increase the current position by a char width."""
        # on a trail byte: just go one to the right
        step = self.text.step_right(self.apagenum, self.current_row, self.current_col)
        self.set_pos(self.current_row, self.current_col + step, scroll_ok=False)

    def decr_pos(self):
        """Decrease the current position by a char width."""
        step = self.text.step_left(self.apagenum, self.current_row, self.current_col)
        self.set_pos(self.current_row, self.current_col - step, scroll_ok=False)

    def move_to_end(self):
        """Jump to end of logical line; follow wraps (END)."""
        row = self.text.find_end_of_line(self.apagenum, self.current_row)
        if self.text.pages[self.apagenum].row[row-1].end == self.mode.width:
            self.set_pos(row, self.text.pages[self.apagenum].row[row-1].end)
            self.overflow = True
        else:
            self.set_pos(row, self.text.pages[self.apagenum].row[row-1].end+1)

    def set_pos(self, to_row, to_col, scroll_ok=True):
        """Set the current position."""
        self.overflow = False
        self.current_row, self.current_col = to_row, to_col
        # move cursor and reset cursor attribute
        # this may alter self.current_row, self.current_col
        self._check_pos(scroll_ok)

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
                # either we don't need to scroll, or we're allowed to
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
        return (self.current_row == oldrow and self.current_col == oldcol)

    def _move_cursor(self, row, col):
        """Move the cursor to a new position."""
        self.current_row, self.current_col = row, col
        # set halfwidth/fullwidth cursor
        width = self.text.get_charwidth(self.apagenum, self.current_row, self.current_col)
        self.cursor.set_width(width)
        # set the cursor's attribute to that of the current location
        fore, _, _, _ = self.mode.split_attr(
            0xf & self.text.get_attr(self.apagenum, self.current_row, self.current_col)
        )
        self.cursor.reset_attr(fore)
        self.queues.video.put(signals.Event(
            signals.VIDEO_MOVE_CURSOR, (self.current_row, self.current_col))
        )

    ###########################################################################
    # update pixel buffer and interface

    def rebuild(self):
        """Completely resubmit the text and graphics screen to the interface."""
        # fix the cursor
        self.queues.video.put(signals.Event(
            signals.VIDEO_SET_CURSOR_SHAPE,
            (self.cursor.width, self.cursor.from_line, self.cursor.to_line)
        ))
        self.queues.video.put(signals.Event(
            signals.VIDEO_MOVE_CURSOR, (self.current_row, self.current_col)
        ))
        if self.mode.is_text_mode:
            attr = self.text.get_attr(self.apagenum, self.current_row, self.current_col)
            fore, _, _, _ = self.mode.split_attr(attr & 0xf)
        else:
            fore, _, _, _ = self.mode.split_attr(self.mode.cursor_index or self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_SET_CURSOR_ATTR, (fore,)))
        self.cursor.reset_visibility()
        # redraw the text screen and rebuild text buffers in video plugin
        for pagenum in range(self.mode.num_pages):
            # resubmit the text buffer without changing the pixel buffer
            for row in range(self.mode.height):
                self.refresh_range(pagenum, row+1, 1, self.mode.width, text_only=True)
            # redraw graphics
            if not self.mode.is_text_mode:
                self.queues.video.put(signals.Event(
                    signals.VIDEO_PUT_RECT, (
                        pagenum, 0, 0, self.mode.pixel_width-1, self.mode.pixel_height-1,
                        self.pixels.pages[pagenum].buffer
                    )
                ))

    def refresh_range(self, pagenum, row, start, stop, text_only=False):
        """Draw a section of a screen row to pixels and interface."""
        col, last_col = start, start
        last_attr = None
        chars = []
        chunks = []
        # collect chars in chunks with the same attribute
        while col <= stop:
            char, attr = self.text.get_fullchar_attr(pagenum, row, col)
            if attr != last_attr:
                if last_attr is not None:
                    chunks.append((last_col, chars, last_attr))
                last_col, last_attr = col, attr
                chars = []
            chars.append(char)
            col += len(char)
        if chars:
            chunks.append((last_col, chars, attr))
        for col, chars, attr in chunks:
            self._draw_text(pagenum, row, col, chars, attr, text_only)

    def _draw_text(self, pagenum, row, col, chars, attr, text_only):
        """Draw a chunk of text in a single attribute to pixels and interface."""
        fore, back, blink, underline = self.mode.split_attr(attr)
        glyphs = self._glyphs.get_glyphs(chars)
        # mark full-width chars by a trailing empty string to preserve column counts
        text = [[_c, u''] if len(_c) > 1 else [_c] for _c in chars]
        text = [self.codepage.to_unicode(_c, u'\0') for _list in text for _c in _list]
        self.queues.video.put(signals.Event(
            signals.VIDEO_PUT_TEXT, (
                pagenum, row, col, text,
                fore, back, blink, underline,
                glyphs
            )
        ))
        if not self.mode.is_text_mode and not text_only:
            left, top = self.mode.text_to_pixel_pos(row, col)
            sprite, width, height = self._glyphs.render_text(chars, fore, back)
            right, bottom = left+width-1, top+height-1
            self.pixels.pages[self.apagenum].put_rect(left, top, right, bottom, sprite, tk.PSET)
            self.queues.video.put(signals.Event(
                signals.VIDEO_PUT_RECT, (self.apagenum, left, top, right, bottom, sprite)
            ))

    def _clear_rows_refresh(self, start, stop):
        """Clear row range to pixels and interface."""
        if not self.mode.is_text_mode:
            x0, y0, x1, y1 = self.mode.text_to_pixel_area(start, 1, stop, self.mode.width)
            # background attribute must be 0 in graphics mode
            self.pixels.pages[self.apagenum].fill_rect(x0, y0, x1, y1, 0)
        _, back, _, _ = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(signals.VIDEO_CLEAR_ROWS, (back, start, stop)))

    ###########################################################################
    # clearing text screen

    def clear_view(self):
        """Clear the scroll area."""
        with self._modify_attr_on_clear():
            self.clear_rows(self.scroll_area.top, self.scroll_area.bottom)
            self.set_pos(self.scroll_area.top, 1)

    def clear(self):
        """Clear the screen."""
        with self._modify_attr_on_clear():
            self.clear_rows(1, self.mode.height)
            self.set_pos(1, 1)

    # called externally only by BottomBar.redraw()
    def clear_rows(self, start, stop):
        """Clear text and graphics on given (inclusive) text row range."""
        self.text.clear_rows(self.apagenum, start, stop, self.attr)
        self._clear_rows_refresh(start, stop)

    @contextmanager
    def _modify_attr_on_clear(self):
        """On some adapters, modify current attributes when clearing the scroll area."""
        if self.capabilities in ('vga', 'ega', 'cga', 'cga_old'):
            # keep background, set foreground to 7
            attr_save = self.attr
            self.set_attr(attr_save & 0x70 | 0x7)
            yield
            self.set_attr(attr_save)
        else:
            yield

    ###########################################################################
    # scrolling

    def scroll(self, from_line=None):
        """Scroll the scroll region up by one line, starting at from_line."""
        if from_line is None:
            from_line = self.scroll_area.top
        _, back, _, _ = self.mode.split_attr(self.attr)
        self.queues.video.put(signals.Event(
            signals.VIDEO_SCROLL_UP, (from_line, self.scroll_area.bottom, back)
        ))
        if self.current_row > from_line:
            self._move_cursor(self.current_row - 1, self.current_col)
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
        self.queues.video.put(signals.Event(
            signals.VIDEO_SCROLL_DOWN, (from_line, self.scroll_area.bottom, back)
        ))
        if self.current_row >= from_line:
            self._move_cursor(self.current_row + 1, self.current_col)
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

    # delete

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
            self.text.pages[self.apagenum].row[self.current_row-1].wrap = (
                self.text.pages[self.apagenum].row[self.current_row].wrap
            )
            self.scroll(self.current_row + 1)
            # redraw from the LF
            self._rewrite_for_delete(text[1:] + b' ' * cwidth)
        else:
            # rewrite the contents (with the current attribute!)
            self._rewrite_for_delete(text[cwidth:] + b' ' * cwidth)
            # if last row was empty, scroll up.
            if (
                    self.text.pages[self.apagenum].row[lastrow-1].end == 0 and
                    self.text.pages[self.apagenum].row[lastrow-2].wrap
                ):
                self.text.pages[self.apagenum].row[lastrow-2].wrap = False
                self.scroll(lastrow)
        # restore original position
        self.set_pos(row, col)

    def _rewrite_for_delete(self, text):
        """Rewrite text contents (with the current attribute)."""
        for c in iterchar(text):
            if c == b'\n':
                start, stop = self.text.put_char_attr(
                    self.apagenum, self.current_row, self.current_col, b' ', self.attr
                )
                self.refresh_range(self.apagenum, self.current_row, start, stop)
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col-1
                break
            else:
                start, stop = self.text.put_char_attr(
                    self.apagenum, self.current_row, self.current_col, c, self.attr
                )
                self.refresh_range(self.apagenum, self.current_row, start, stop)
                self.set_pos(self.current_row, self.current_col+1)
        else:
            # we're on the position after the additional space
            if self.current_col == 1:
                self.current_row -= 1
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.mode.width - 1
            else:
                # adjust row end
                self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col - 2

    # insert

    def insert_fullchars(self, sequence):
        """Insert one or more single- or double-width characters and adjust cursor."""
        # insert one at a time at cursor location
        # to let cursor position logic deal with scrolling
        for c in iterchar(sequence):
            if self._insert_fullchar_at(self.current_row, self.current_col, c, self.attr):
                # move cursor by one character
                # this will move to next row when necessary
                self.incr_pos()

    def _insert_fullchar_at(self, row, col, c, attr):
        """Insert one single- or double-width character at the given position."""
        therow = self.text.pages[self.apagenum].row[row-1]
        if therow.end < self.mode.width:
            # insert the new char and ignore what drops off at the end
            # this changes the attribute of everything that has been redrawn
            _, _, start_col, stop_col = therow.insert_char_attr(col, c, attr)
            # redraw everything that has changed
            self.refresh_range(self.apagenum, row, start_col, stop_col)
            # the insert has now filled the row and we used to be a row ending in LF:
            # scroll and continue into the new row
            if therow.wrap and therow.end == self.mode.width:
                # since we used to be an LF row, wrap == True already
                # then, the newly added row should wrap - TextBuffer.scroll_down takes care of this
                self.scroll_down(row+1)
            # if we filled out the row but aren't wrapping, we scroll & wrap at the *next* insert
            return True
        else:
            # we have therow.end == width, so we're pushing the end of the row past the screen edge
            # if we're not a wrapping line, make space by scrolling and wrap into the new line
            if not therow.wrap and row < self.scroll_area.bottom:
                self.scroll_down(row+1)
                therow.wrap = True
            if row >= self.scroll_area.bottom:
                # once the end of the line hits the bottom, start scrolling the start of the line up
                start = self.text.find_start_of_line(self.apagenum, self.current_row)
                # if we hist the top of the screen, stop inserting & drop chars
                if start <= self.scroll_area.top:
                    return False
                # scroll up
                self.scroll()
                # adjust working row number
                row -= 1
                assert therow is self.text.pages[self.apagenum].row[row-1]
            c, _, start_col, stop_col = therow.insert_char_attr(col, c, attr)
            # redraw everything that has changed on this row
            self.refresh_range(self.apagenum, row, start_col, stop_col)
            # insert the character in the next row
            return self._insert_fullchar_at(row+1, 1, c, attr)

    def clear_from(self, srow, scol):
        """Clear from given position to end of logical line (CTRL+END)."""
        end_row = self.text.find_end_of_line(self.apagenum, srow)
        # clear the first row of te logical line
        self.text.pages[self.apagenum].row[srow-1].clear(
            self.attr, from_col=scol, clear_wrap=True,
        )
        if scol > 1:
            # redraw the last char before the clear too, as it may have been changed by dbcs logic
            self.refresh_range(self.apagenum, srow, scol-1, self.mode.width)
        else:
            # just clear out the whole row
            self._clear_rows_refresh(srow, srow)
        # remove the additional rows in the logical line by scrolling up
        for row in range(end_row, srow, -1):
            self.scroll(row)
        self.set_pos(srow, scol)

    # line feed

    def line_feed(self):
        """Move the remainder of the line to the next row and wrap (LF)."""
        if self.current_col < self.text.pages[self.apagenum].row[self.current_row-1].end:
            # insert characters, preserving cursor position
            cursor = self.current_row, self.current_col
            self.insert_fullchars(b' ' * (self.mode.width-self.current_col+1))
            self.set_pos(*cursor, scroll_ok=False)
            # adjust end of line and wrapping flag - LF connects lines like word wrap
            self.text.pages[self.apagenum].row[self.current_row-1].end = self.current_col - 1
            self.text.pages[self.apagenum].row[self.current_row-1].wrap = True
            # cursor stays in place after line feed!
        else:
            # find last row in logical line
            end = self.text.find_end_of_line(self.apagenum, self.current_row)
            # if the logical line hits the bottom, start scrolling up to make space...
            if end >= self.scroll_area.bottom:
                # ... until the it also hits the top; then do nothing
                start = self.text.find_start_of_line(self.apagenum, self.current_row)
                if start > self.scroll_area.top:
                    self.scroll()
                else:
                    return
            # self.current_row has changed, don't use row var
            if self.current_row < self.mode.height:
                self.scroll_down(self.current_row+1)
                # if we were already a wrapping row, make sure the new empty row wraps
                #if self.text.pages[self.apagenum].row[self.current_row-1].wrap:
                #    self.text.pages[self.apagenum].row[self.current_row].wrap = True
            # ensure the current row now wraps
            self.text.pages[self.apagenum].row[self.current_row-1].wrap = True
            # cursor moves to start of next line
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
            self.vpagenum, start_row, start_col, stop_row, stop_col
        )
        text = u'\n'.join(self.codepage.str_to_unicode(clip) for clip in clips)
        self.queues.video.put(signals.Event(
                signals.VIDEO_SET_CLIPBOARD_TEXT, (text, is_mouse_selection)
        ))

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
            if self.capabilities in ('pcjr', 'tandy') and not self.bottom_bar.visible:
                max_line = 25
            else:
                max_line = 24
            error.range_check(1, max_line, start, stop)
            error.throw_if(stop < start)
            self.scroll_area.set(start, stop)
            #set_pos(start, 1)
            self.overflow = False
            self._move_cursor(start, 1)
