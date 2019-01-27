"""
PC-BASIC - textscreen.py
Text operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from contextlib import contextmanager

from ...compat import iterchar

from ..base import signals
from ..base import error
from ..base import tokens as tk
from ..base.tokens import ALPHANUMERIC
from .. import values
from .textbase import BottomBar, Cursor, ScrollArea


class TextScreen(object):
    """Text screen."""

    def __init__(self, queues, values, mode, capabilities, codepage):
        """Initialise text-related members."""
        self._queues = queues
        self._values = values
        self._codepage = codepage
        self._conv = codepage.get_converter(preserve=b'')
        self._tandytext = capabilities in ('pcjr', 'tandy')
        # overwrite mode (instead of insert)
        self._overwrite_mode = True
        # cursor
        self.cursor = Cursor(queues, mode)
        # current row and column
        # overflow: true if we're on 80 but should be on 81
        self.current_row, self.current_col, self.overflow = 1, 1, False
        # text viewport parameters
        self.scroll_area = ScrollArea(mode)
        # writing on bottom row is allowed
        self._bottom_row_allowed = False
        # function key macros
        self._bottom_bar = BottomBar()
        # initialised by init_mode
        self.mode = None
        self._attr = 0
        # used by Editor only
        self.apagenum = 0
        self._vpagenum = 0
        self._glyphs = None
        self._colourmap = None
        # used by Editor only
        self.text_pages = None
        self._dbcs_enabled = False
        self._dbcs_text = None
        self._pixel_pages = None

    def init_mode(
            self, mode, pixel_pages, text_pages,
            attr, vpagenum, apagenum, font, colourmap, do_fullwidth
        ):
        """Reset the text screen for new video mode."""
        self.mode = mode
        self._attr = attr
        self.apagenum = apagenum
        self._vpagenum = vpagenum
        self._glyphs = font
        self._colourmap = colourmap
        # character buffers
        self.text_pages = text_pages
        self._dbcs_enabled = self._codepage.dbcs and do_fullwidth
        self._dbcs_text = [
            [tuple(iterchar(b' ')) * mode.width for _ in range(mode.height)]
            for _ in range(mode.num_pages)
        ]
        # pixel buffer
        self._pixel_pages = pixel_pages
        # redraw key line
        self.redraw_bar()
        # initialise text viewport & move cursor home
        self.scroll_area.init_mode(self.mode)
        # rebuild the cursor
        if not mode.is_text_mode and mode.cursor_attr:
            self.cursor.init_mode(self.mode, mode.cursor_attr, colourmap)
        else:
            self.cursor.init_mode(self.mode, self._attr, colourmap)
        self.set_pos(self.scroll_area.top, 1)

    def __repr__(self):
        """Return an ascii representation of the screen buffer (for debugging)."""
        return '\n'.join(repr(page) for page in self.text_pages)

    def set_page(self, vpagenum, apagenum):
        """Set visible and active page."""
        self._vpagenum = vpagenum
        self.apagenum = apagenum

    def set_attr(self, attr):
        """Set attribute."""
        self._attr = attr

    ###########################################################################
    # text buffer operations

    def write_char(self, char, do_scroll_down=False):
        """Put one character at the current position."""
        # check if scroll & repositioning needed
        if self.overflow:
            self.current_col += 1
            self.overflow = False
        # see if we need to wrap and scroll down
        self._check_wrap(do_scroll_down)
        # move cursor and see if we need to scroll up
        self.check_pos(scroll_ok=True)
        # put the character
        self.text_pages[self.apagenum].put_char_attr(
            self.current_row, self.current_col, char, self._attr, adjust_end=True
        )
        self.refresh_range(self.apagenum, self.current_row, self.current_col, self.current_col)
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
                if do_scroll_down:
                    # scroll down (make space by shifting the next rows down)
                    if self.current_row < self.scroll_area.bottom:
                        self.scroll_down(self.current_row+1)
                # wrap line
                self.set_wrap(self.current_row, True)
                # move cursor and reset cursor attribute
                self._move_cursor(self.current_row + 1, 1)
            else:
                self.current_col = self.mode.width

    def set_wrap(self, row, wrap):
        """Connect/disconnect rows on active page by line wrap."""
        self.text_pages[self.apagenum].set_wrap(row, wrap)

    def wraps(self, row):
        """The given row is connected by line wrap."""
        return self.text_pages[self.apagenum].wraps(row)

    def set_row_length(self, row, length):
        """Set logical length of row."""
        self.text_pages[self.apagenum].set_row_length(row, length)

    def row_length(self, row):
        """Return logical length of row."""
        return self.text_pages[self.apagenum].row_length(row)

    ###########################################################################
    # cursor position

    def incr_pos(self):
        """Increase the current position by a char width."""
        step = self._get_charwidth(self.current_row, self.current_col)
        # on a trail byte: go just one to the right
        step = step or 1
        self.set_pos(self.current_row, self.current_col + step, scroll_ok=False)

    def decr_pos(self):
        """Decrease the current position by a char width."""
        # check width of cell to the left
        width = self._get_charwidth(self.current_row, self.current_col-1)
        # previous is trail byte: go two to the left
        # lead byte: go three to the left
        if width == 0:
            step = 2
        elif width == 2:
            step = 3
        else:
            step = 1
        self.set_pos(self.current_row, self.current_col - step, scroll_ok=False)

    def move_to_end(self):
        """Jump to end of logical line; follow wraps (END)."""
        row = self.text_pages[self.apagenum].find_end_of_line(self.current_row)
        if self.row_length(row) == self.mode.width:
            self.set_pos(row, self.row_length(row))
            self.overflow = True
        else:
            self.set_pos(row, self.row_length(row) + 1)

    def set_pos(self, to_row, to_col, scroll_ok=True):
        """Set the current position."""
        self.overflow = False
        self.current_row, self.current_col = to_row, to_col
        # move cursor and reset cursor attribute
        # this may alter self.current_row, self.current_col
        self.check_pos(scroll_ok)

    def check_pos(self, scroll_ok=True):
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
        # in text mode, set the cursor width and attriute to that of the new location
        if self.mode.is_text_mode:
            # set halfwidth/fullwidth cursor
            width = self._get_charwidth(row, col)
            # set the cursor attribute
            attr = self.text_pages[self.apagenum].get_attr(row, col)
            self.cursor.move(row, col, attr, width)
        else:
            # move the cursor
            self.cursor.move(row, col)

    ###########################################################################
    # update pixel buffer and interface

    def rebuild(self):
        """Completely resubmit the text and graphics screen to the interface."""
        self.cursor.rebuild()
        # redraw the text screen and rebuild text buffers in video plugin
        for pagenum in range(self.mode.num_pages):
            # resubmit the text buffer without changing the pixel buffer
            # redraw graphics
            for row in range(self.mode.height):
                self.refresh_range(pagenum, row+1, 1, self.mode.width, text_only=True)

    def _get_charwidth(self, row, col):
        """Get DBCS width of cell on active page."""
        return len(self._dbcs_text[self.apagenum][row-1][col-1])

    def refresh_range(self, pagenum, row, start, stop, text_only=False):
        """Draw a section of a screen row to pixels and interface."""
        # mark out replaced char and changed following dbcs characters to be redrawn
        raw = self.text_pages[pagenum].get_row_text_raw(row)
        if self._dbcs_enabled:
            marks = self._conv.mark(raw, flush=True)
            tuples = ((_seq,) if len(_seq) == 1 else (_seq, b'') for _seq in marks)
            sequences = [_seq for _tup in tuples for _seq in _tup]
        else:
            sequences = tuple(iterchar(raw))
        updated = [old != new for old, new in zip(self._dbcs_text[pagenum][row-1], sequences)]
        self._dbcs_text[pagenum][row-1] = sequences
        try:
            start = min(start, updated.index(True) + 1)
            stop = max(stop, len(updated) - updated[::-1].index(True))
        except ValueError:
            # no change to buffer
            # however, in graphics mode we need to plot at least the updated range
            # as the dbcs buffer is not updated when overdrawn
            if self.mode.is_text_mode:
                return
        col, last_col = start, start
        last_attr = None
        chars = []
        chunks = []
        # collect chars in chunks with the same attribute
        while col <= stop:
            char = self._dbcs_text[pagenum][row-1][col-1]
            attr = self.text_pages[pagenum].get_attr(row, col)
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
        if row < 1 or col < 1 or row > self.mode.height or col > self.mode.width:
            logging.debug('Ignoring out-of-range text rendering request: row %d col %d', row, col)
            return
        _, back, _, underline = self._colourmap.split_attr(attr)
        # update pixel buffer
        left, top = self.mode.text_to_pixel_pos(row, col)
        sprite = self._glyphs.render_text(chars, attr, back, underline)
        if not text_only:
            self._pixel_pages[self.apagenum][top:top+sprite.height, left:left+sprite.width] = sprite
        else:
            sprite = self._pixel_pages[self.apagenum][top:top+sprite.height, left:left+sprite.width]
        # mark full-width chars by a trailing empty string to preserve column counts
        text = [[_c, u''] if len(_c) > 1 else [_c] for _c in chars]
        text = [self._codepage.to_unicode(_c, u'\0') for _list in text for _c in _list]
        self._queues.video.put(signals.Event(
            signals.VIDEO_PUT_TEXT, (pagenum, row, col, text, attr, sprite)
        ))

    def _clear_rows_refresh(self, start, stop):
        """Clear row range to pixels and interface."""
        x0, y0, x1, y1 = self.mode.text_to_pixel_area(start, 1, stop, self.mode.width)
        # background attribute must be 0 in graphics mode
        self._pixel_pages[self.apagenum][y0:y1+1, x0:x1+1] = 0
        _, back, _, _ = self._colourmap.split_attr(self._attr)
        self._queues.video.put(signals.Event(signals.VIDEO_CLEAR_ROWS, (back, start, stop)))

    ###########################################################################
    # clearing text screen

    def clear_view(self):
        """Clear the scroll area."""
        with self._modify_attr_on_clear():
            self._clear_rows(self.scroll_area.top, self.scroll_area.bottom)
            self.set_pos(self.scroll_area.top, 1)

    def clear(self):
        """Clear the screen."""
        with self._modify_attr_on_clear():
            self._clear_rows(1, self.mode.height)
            self.set_pos(1, 1)

    def _clear_rows(self, start, stop):
        """Clear text and graphics on given (inclusive) text row range."""
        self.text_pages[self.apagenum].clear_area(
            start, 1, stop, self.mode.width, self._attr, adjust_end=True, clear_wrap=True
        )
        self._dbcs_text[self.apagenum][start-1:stop] = [
            tuple(iterchar(b' ')) * self.mode.width for _ in range(stop-start+1)
        ]
        self._clear_rows_refresh(start, stop)

    @contextmanager
    def _modify_attr_on_clear(self):
        """On some adapters, modify character attributes when clearing the scroll area."""
        if not self._tandytext:
            # keep background, set foreground to 7
            attr_save = self._attr
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
        _, back, _, _ = self._colourmap.split_attr(self._attr)
        self._queues.video.put(signals.Event(
            signals.VIDEO_SCROLL, (-1, from_line, self.scroll_area.bottom, back)
        ))
        if self.current_row > from_line:
            self._move_cursor(self.current_row - 1, self.current_col)
        # update text buffer
        self.text_pages[self.apagenum].scroll_up(from_line, self.scroll_area.bottom, self._attr)
        # update dbcs buffer
        self._dbcs_text[self.apagenum][from_line-1:self.scroll_area.bottom-1] = (
            self._dbcs_text[self.apagenum][from_line:self.scroll_area.bottom]
        )
        self._dbcs_text[self.apagenum][self.scroll_area.bottom-1] = (
            tuple(iterchar(b' ')) * self.mode.width
        )
        # update pixel buffer
        sx0, sy0, sx1, sy1 = self.mode.text_to_pixel_area(
            from_line+1, 1, self.scroll_area.bottom, self.mode.width
        )
        tx0, ty0 = self.mode.text_to_pixel_pos(from_line, 1)
        self._pixel_pages[self.apagenum].move(sy0, sy1+1, sx0, sx1+1, ty0, tx0)

    def scroll_down(self, from_line):
        """Scroll the scroll region down by one line, starting at from_line."""
        _, back, _, _ = self._colourmap.split_attr(self._attr)
        self._queues.video.put(signals.Event(
            signals.VIDEO_SCROLL, (1, from_line, self.scroll_area.bottom, back)
        ))
        if self.current_row >= from_line:
            self._move_cursor(self.current_row + 1, self.current_col)
        # update text buffer
        self.text_pages[self.apagenum].scroll_down(from_line, self.scroll_area.bottom, self._attr)
        # update dbcs buffer
        self._dbcs_text[self.apagenum][from_line:self.scroll_area.bottom] = (
            self._dbcs_text[self.apagenum][from_line-1:self.scroll_area.bottom-1]
        )
        self._dbcs_text[self.apagenum][from_line-1] = tuple(iterchar(b' ')) * self.mode.width
        # update pixel buffer
        sx0, sy0, sx1, sy1 = self.mode.text_to_pixel_area(
            from_line, 1, self.scroll_area.bottom-1, self.mode.width
        )
        tx0, ty0 = self.mode.text_to_pixel_pos(from_line+1, 1)
        self._pixel_pages[self.apagenum].move(sy0, sy1+1, sx0, sx1+1, ty0, tx0)

    ###########################################################################
    # console operations

    def get_logical_line(self, from_start, prompt_row, left, right):
        """Get contents of the logical line (INPUT and console interaction)."""
        if from_start:
            return self.text_pages[self.apagenum].get_logical_line(self.current_row)
        else:
            return self.text_pages[self.apagenum].get_logical_line_from(
                self.current_row, prompt_row, left, right
            )

    # delete

    def delete_fullchar(self):
        """Delete the character (half/fullwidth) at the current position."""
        width = self._get_charwidth(self.current_row, self.current_col)
        # on a halfwidth char, delete once; lead byte, delete twice; trail byte, do nothing
        if width > 0:
            self._delete_at(self.current_row, self.current_col)
        if width == 2:
            self._delete_at(self.current_row, self.current_col)

    def _delete_at(self, row, col, remove_depleted=False):
        """Delete the halfwidth character at the given position."""
        # case 0) non-wrapping row:
        #           0a) left of or at logical end -> redraw until logical end
        #           0b) beyond logical end -> do nothing
        # case 1) full wrapping row -> redraw until physical end -> recurse for next row
        # case 2) LF row:
        #           2a) left of LF logical end ->  redraw until logical end
        #           2b) at or beyond LF logical end
        #                   -> attach next row's contents at current postion until physical end
        #                   -> if next row now empty, scroll it up & stop; otherwise recurse
        # note that the last line recurses into a multi-character delete!
        if not self.wraps(row):
            # case 0b
            if col > self.row_length(row):
                return
            # case 0a
            start_col, stop_col = self.text_pages[self.apagenum].delete_char_attr(
                row, col, self._attr
            )
            # if the row is depleted, drop it and scroll up from below
            if remove_depleted and self.row_length(row) == 0:
                self.scroll(row)
        elif self.row_length(row) == self.mode.width:
            # case 1
            wrap_char_attr = (
                self.text_pages[self.apagenum].get_char(row+1, 0),
                self.text_pages[self.apagenum].get_attr(row+1, 0)
            )
            if self.row_length(row + 1) == 0:
                wrap_char_attr = None
            start_col, stop_col = self.text_pages[self.apagenum].delete_char_attr(
                row, col, self._attr, wrap_char_attr
            )
            self._delete_at(row+1, 1, remove_depleted=True)
        elif col < self.row_length(row):
            # case 2a
            start_col, stop_col = self.text_pages[self.apagenum].delete_char_attr(
                row, col, self._attr
            )
        elif remove_depleted and col == self.row_length(row):
            # case 2b (ii) while on the first LF row deleting the last char immediately appends
            # the next row, any subsequent LF rows are only removed once they are fully empty and
            # DEL is pressed another time
            start_col, stop_col = self.text_pages[self.apagenum].delete_char_attr(
                self.apagenum, row, col, self._attr
            )
        elif remove_depleted and self.row_length(row) == 0:
            # case 2b (iii) this is where the empty row mentioned at 2b (ii) gets removed
            self.scroll(row)
            return
        else:
            # case 2b (i) perform multi_character delete by looping single chars
            for newcol in range(col, self.mode.width+1):
                if self.row_length(row + 1) == 0:
                    break
                wrap_char = self.text_pages[self.apagenum].get_char(row+1, 0)
                self.text_pages[self.apagenum].put_char_attr(
                    row, newcol, wrap_char, self._attr, adjust_end=True
                )
                self._delete_at(row+1, 1, remove_depleted=True)
            start_col, stop_col = col, newcol
        # refresh all that has been changed
        self.refresh_range(self.apagenum, row, start_col, stop_col)

    # insert

    def insert_fullchars(self, sequence):
        """Insert one or more half- or fullwidth characters and adjust cursor."""
        # insert one at a time at cursor location
        # to let cursor position logic deal with scrolling
        for c in iterchar(sequence):
            if self._insert_at(self.current_row, self.current_col, c, self._attr):
                # move cursor by one character
                # this will move to next row when necessary
                self.incr_pos()

    def _insert_at(self, row, col, c, attr):
        """Insert one halfwidth character at the given position."""
        if self.row_length(row) < self.mode.width:
            # insert the new char and ignore what drops off at the end
            # this changes the attribute of everything that has been redrawn
            _, _, start_col, stop_col = self.text_pages[self.apagenum].insert_char_attr(
                row, col, c, attr
            )
            # redraw everything that has changed
            self.refresh_range(self.apagenum, row, start_col, stop_col)
            # the insert has now filled the row and we used to be a row ending in LF:
            # scroll and continue into the new row
            if self.wraps(row) and self.row_length(row) == self.mode.width:
                # since we used to be an LF row, wrap == True already
                # then, the newly added row should wrap - TextBuffer.scroll_down takes care of this
                self.scroll_down(row+1)
            # if we filled out the row but aren't wrapping, we scroll & wrap at the *next* insert
            return True
        else:
            # we have therow.end == width, so we're pushing the end of the row past the screen edge
            # if we're not a wrapping line, make space by scrolling and wrap into the new line
            if not self.wraps(row) and row < self.scroll_area.bottom:
                self.scroll_down(row+1)
                self.set_wrap(row, True)
            if row >= self.scroll_area.bottom:
                # once the end of the line hits the bottom, start scrolling the start of the line up
                start = self.text_pages[self.apagenum].find_start_of_line(self.current_row)
                # if we hist the top of the screen, stop inserting & drop chars
                if start <= self.scroll_area.top:
                    return False
                # scroll up
                self.scroll()
                # adjust working row number
                row -= 1
            c, _, start_col, stop_col = self.text_pages[self.apagenum].insert_char_attr(
                row, col, c, attr
            )
            # redraw everything that has changed on this row
            self.refresh_range(self.apagenum, row, start_col, stop_col)
            # insert the character in the next row
            return self._insert_at(row+1, 1, c, attr)

    def clear_from(self, srow, scol):
        """Clear from given position to end of logical line (CTRL+END)."""
        end_row = self.text_pages[self.apagenum].find_end_of_line(srow)
        # clear the first row of the logical line
        self.text_pages[self.apagenum].clear_area(
            srow, scol, srow, self.mode.width, self._attr, adjust_end=True, clear_wrap=True
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
        if self.current_col < self.row_length(self.current_row):
            # insert characters, preserving cursor position
            cursor = self.current_row, self.current_col
            self.insert_fullchars(b' ' * (self.mode.width-self.current_col+1))
            self.set_pos(*cursor, scroll_ok=False)
            # adjust end of line and wrapping flag - LF connects lines like word wrap
            self.set_row_length(self.current_row, self.current_col - 1)
            self.set_wrap(self.current_row, True)
            # cursor stays in place after line feed!
        else:
            # find last row in logical line
            end = self.text_pages[self.apagenum].find_end_of_line(self.current_row)
            # if the logical line hits the bottom, start scrolling up to make space...
            if end >= self.scroll_area.bottom:
                # ... until the it also hits the top; then do nothing
                start = self.text_pages[self.apagenum].find_start_of_line(self.current_row)
                if start > self.scroll_area.top:
                    self.scroll()
                else:
                    return
            # self.current_row has changed, don't use row var
            if self.current_row < self.mode.height:
                self.scroll_down(self.current_row+1)
            # ensure the current row now wraps
            self.set_wrap(self.current_row, True)
            # cursor moves to start of next line
            self.set_pos(self.current_row+1, 1)

    # editor calls

    @property
    def overwrite_mode(self):
        """Overwrite (True) or Insert (False) mode."""
        return self._overwrite_mode

    def set_overwrite_mode(self, new_overwrite=True):
        """Set or unset the overwrite mode (INS)."""
        if new_overwrite != self._overwrite_mode:
            self._overwrite_mode = new_overwrite
            self.cursor.set_default_shape(new_overwrite)

    def clear_line(self, the_row, from_col=1):
        """Clear whole logical line (ESC), leaving prompt."""
        self.clear_from(
            self.text_pages[self.apagenum].find_start_of_line(the_row), from_col
        )

    def backspace(self, prompt_row, furthest_left):
        """Delete the char to the left (BACKSPACE)."""
        row, col = self.current_row, self.current_col
        start_row = self.text_pages[self.apagenum].find_start_of_line(row)
        # don't backspace through prompt or through start of logical line
        # on the prompt row, don't go any further back than we've been already
        if (
                ((col != furthest_left or row != prompt_row)
                and (col > 1 or row > start_row))
            ):
            self.decr_pos()
        self.delete_fullchar()

    def tab(self):
        """Jump to next 8-position tab stop (TAB)."""
        newcol = 9 + 8 * int((self.current_col-1) // 8)
        if self._overwrite_mode:
            self.set_pos(self.current_row, newcol, scroll_ok=False)
        else:
            self.insert_fullchars(b' ' * (newcol-self.current_col))

    def skip_word_right(self):
        """Skip one word to the right (CTRL+RIGHT)."""
        crow, ccol = self.current_row, self.current_col
        # find non-alphanumeric chars
        while True:
            c = self.text_pages[self.apagenum].get_char(crow, ccol)
            if (c not in ALPHANUMERIC):
                break
            ccol += 1
            if ccol > self.mode.width:
                if crow >= self.scroll_area.bottom:
                    # nothing found
                    return
                crow += 1
                ccol = 1
        # find alphanumeric chars
        while True:
            c = self.text_pages[self.apagenum].get_char(crow, ccol)
            if (c in ALPHANUMERIC):
                break
            ccol += 1
            if ccol > self.mode.width:
                if crow >= self.scroll_area.bottom:
                    # nothing found
                    return
                crow += 1
                ccol = 1
        self.set_pos(crow, ccol)

    def skip_word_left(self):
        """Skip one word to the left (CTRL+LEFT)."""
        crow, ccol = self.current_row, self.current_col
        # find alphanumeric chars
        while True:
            ccol -= 1
            if ccol < 1:
                if crow <= self.scroll_area.top:
                    # not found
                    return
                crow -= 1
                ccol = self.mode.width
            c = self.text_pages[self.apagenum].get_char(crow, ccol)
            if (c in ALPHANUMERIC):
                break
        # find non-alphanumeric chars
        while True:
            last_row, last_col = crow, ccol
            ccol -= 1
            if ccol < 1:
                if crow <= self.scroll_area.top:
                    break
                crow -= 1
                ccol = self.mode.width
            c = self.text_pages[self.apagenum].get_char(crow, ccol)
            if (c not in ALPHANUMERIC):
                break
        self.set_pos(last_row, last_col)

    ###########################################################################
    # bottom bar

    def update_bar(self, descriptions):
        """Update thekey descriptions in the bottom bar."""
        self._bottom_bar.clear()
        for i, text in enumerate(descriptions):
            kcol = 1 + 8*i
            self._bottom_bar.write((b'%d' % (i+1,))[-1:], kcol, False)
            self._bottom_bar.write(text, kcol+1, True)

    def show_bar(self, on):
        """Switch bottom bar visibility."""
        # tandy can have VIEW PRINT 1 to 25, should raise IFC in that case
        error.throw_if(on and self.scroll_area.bottom == self.mode.height)
        self._bottom_bar.visible, was_visible = on, self._bottom_bar.visible
        if self._bottom_bar.visible != was_visible:
            self.redraw_bar()

    def redraw_bar(self):
        """Redraw bottom bar if visible, clear if not."""
        key_row = self.mode.height
        # Keys will only be visible on the active page at which KEY ON was given,
        # and only deleted on page at which KEY OFF given.
        self._clear_rows(key_row, key_row)
        if not self.mode.is_text_mode:
            reverse_attr = self._attr
        elif (self._attr >> 4) & 0x7 == 0:
            reverse_attr = 0x70
        else:
            reverse_attr = 0x07
        if self._bottom_bar.visible:
            # always show only complete 8-character cells
            # this matters on pcjr/tandy width=20 mode
            for col in range((self.mode.width//8) * 8):
                char, reverse = self._bottom_bar.get_char_reverse(col)
                attr = reverse_attr if reverse else self._attr
                self.text_pages[self.apagenum].put_char_attr(key_row, col+1, char, attr)
            self.set_row_length(self.mode.height, self.mode.width)
            # update the screen
            self.refresh_range(self.apagenum, key_row, 1, self.mode.width)

    ###########################################################################
    # vpage text retrieval

    def print_screen(self, target_file):
        """Output the visible page to file in raw bytes."""
        if not target_file:
            return
        for line in self.text_pages[self._vpagenum].get_text_raw():
            target_file.write_line(line.replace(b'\0', b' '))

    def copy_clipboard(self, start_row, start_col, stop_row, stop_col):
        """Copy selected screen area to clipboard."""
        text = self.text_pages[self._vpagenum].get_text_logical(
            start_row, start_col, stop_row, stop_col
        )
        text = u''.join(self._codepage.str_to_unicode(_chunk) for _chunk in text.split(b'\n'))
        self._queues.video.put(signals.Event(
            signals.VIDEO_SET_CLIPBOARD_TEXT, (text,)
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
        error.throw_if(row == self.mode.height and self._bottom_bar.visible)
        if self.scroll_area.active:
            error.range_check(self.scroll_area.top, self.scroll_area.bottom, row)
        else:
            error.range_check(1, self.mode.height, row)
        error.range_check(1, self.mode.width, col)
        if row == self.mode.height:
            # temporarily allow writing on last row
            self._bottom_row_allowed = True
        self.set_pos(row, col, scroll_ok=False)
        if cursor is not None:
            error.range_check(0, (255 if self._tandytext else 1), cursor)
            # set cursor visibility - this should set the flag but have no effect in graphics modes
            self.cursor.set_visibility(cursor != 0)
        error.throw_if(start is None and stop is not None)
        if stop is None:
            stop = start
        if start is not None:
            error.range_check(0, 31, start, stop)
            # cursor shape only has an effect in text mode
            if self.mode.is_text_mode:
                self.cursor.set_shape(start, stop)

    def csrlin_(self, args):
        """CSRLIN: get the current screen row."""
        list(args)
        if (
                self.overflow and self.current_col == self.mode.width
                and self.current_row < self.scroll_area.bottom
            ):
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
                result = self.text_pages[self.apagenum].get_attr(row, col)
        else:
            result = self.text_pages[self.apagenum].get_byte(row, col)
        return self._values.new_integer().from_int(result)

    def view_print_(self, args):
        """VIEW PRINT: set scroll region."""
        start, stop = (None if arg is None else values.to_int(arg) for arg in args)
        if start is None and stop is None:
            self.scroll_area.unset()
        else:
            if self._tandytext and not self._bottom_bar.visible:
                max_line = 25
            else:
                max_line = 24
            error.range_check(1, max_line, start, stop)
            error.throw_if(stop < start)
            self.scroll_area.set(start, stop)
            #set_pos(start, 1)
            self.overflow = False
            self._move_cursor(start, 1)
