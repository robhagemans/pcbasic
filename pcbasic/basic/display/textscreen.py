"""
PC-BASIC - display.textscreen
Text operations

(c) 2013--2021 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from contextlib import contextmanager

from ...compat import iterchar, text_type

from ..base import error
from ..base import tokens as tk
from ..base.tokens import ALPHANUMERIC
from .. import values


class ScrollArea(object):
    """Text viewport / scroll area."""

    def __init__(self, mode):
        """Initialise the scroll area."""
        self._height = mode.height
        self.unset()

    def init_mode(self, mode):
        """Initialise the scroll area for new screen mode."""
        self._height = mode.height
        if self._bottom == self._height:
            # tandy/pcjr special case: VIEW PRINT to 25 is preserved
            self.set(1, self._height)
        else:
            self.unset()

    @property
    def active(self):
        """A viewport has been set."""
        return self._active

    @property
    def bounds(self):
        """Return viewport bounds."""
        return self._top, self._bottom

    @property
    def top(self):
        """Return viewport top bound."""
        return self._top

    @property
    def bottom(self):
        """Return viewport bottom bound."""
        return self._bottom

    def set(self, start, stop):
        """Set the scroll area."""
        self._active = True
        # _top and _bottom are inclusive and count rows from 1
        self._top = start
        self._bottom = stop

    def unset(self):
        """Unset scroll area."""
        # there is only one VIEW PRINT setting across all pages.
        # scroll area normally excludes the bottom bar
        self.set(1, self._height - 1)
        self._active = False


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
        self._contents = [(b' ', 0)] * 80

    def write(self, s, col, reverse):
        """Write chars on virtual bottom bar."""
        for i, c in enumerate(iterchar(s)):
            self._contents[col + i] = (c, reverse)

    def get_char_reverse(self, col):
        """Retrieve char and reverse attribute."""
        return self._contents[col]


class TextScreen(object):
    """Text screen."""

    def __init__(self, values, mode, cursor, capabilities):
        """Initialise text-related members."""
        self._values = values
        self._tandytext = capabilities in ('pcjr', 'tandy')
        # cursor
        self._cursor = cursor
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
        self._apagenum = 0
        self._vpagenum = 0
        self._pages = None
        self._apage = None
        self._locked = False

    def init_mode(
            self, mode, pages, attr, vpagenum, apagenum,
        ):
        """Reset the text screen for new video mode."""
        self.mode = mode
        self._attr = attr
        self._apagenum = apagenum
        self._vpagenum = vpagenum
        # character buffers
        self._pages = pages
        # pixel buffer
        self._apage = self._pages[self._apagenum]
        # redraw key line
        self.redraw_bar()
        # initialise text viewport & move cursor home
        self.scroll_area.init_mode(self.mode)
        self.set_pos(self.scroll_area.top, 1)

    def __repr__(self):
        """Return an ascii representation of the screen buffer (for debugging)."""
        return '\n'.join(repr(page) for page in self._pages)

    def set_page(self, vpagenum, apagenum):
        """Set visible and active page."""
        self._vpagenum = vpagenum
        self._apagenum = apagenum
        self._apage = self._pages[self._apagenum]
        # cursor lives on active page
        # this is technically only the case in graphics mode -
        # in DOSBox it's visible in text mode if the active page is not visible
        # but then the cursor location is static and does not equal the text insert location
        # so this seems acceptable
        self._cursor.set_active(self._vpagenum == self._apagenum)

    def set_attr(self, attr):
        """Set attribute."""
        self._attr = attr


    ###########################################################################
    # basic text buffer operations

    def write_chars(self, chars, do_scroll_down):
        """Put one character at the current position."""
        with self.collect_updates():
            for char in iterchar(chars):
                self.write_char(char, do_scroll_down)

    def write_char(self, char, do_scroll_down):
        """Put one character at the current position."""
        # see if we need to wrap and scroll down
        self._consume_overflow_before_write(do_scroll_down)
        # move cursor and see if we need to scroll up
        self._wrap_around_and_scroll_as_needed(scroll_ok=True)
        self._refresh_cursor()
        # put the character
        self._apage.put_char_attr(
            self.current_row, self.current_col, char, self._attr, adjust_end=True
        )
        # move cursor. if on col 80, only move cursor to the next row
        # when the char is printed, except if the row already wraps into the next one
        if self.current_col < self.mode.width:
            self.current_col += 1
        elif self.wraps(self.current_row):
            self.current_row += 1
            self.current_col = 1
        else:
            self.overflow = True
        # move cursor and see if we need to scroll up
        self._wrap_around_and_scroll_as_needed(scroll_ok=True)
        self._refresh_cursor()

    def _consume_overflow_before_write(self, do_scroll_down):
        """Move from overflow position to next line and set wrap flag, scroll down if needed."""
        if self.overflow:
            self.current_col += 1
            self.overflow = False
        if self.current_col > self.mode.width:
            if self.current_row < self.mode.height:
                if not self.wraps(self.current_row):
                    if do_scroll_down:
                        # scroll down (make space by shifting the next rows down)
                        if self.current_row < self.scroll_area.bottom:
                            self.scroll_down(self.current_row+1)
                    # wrap line
                    self.set_wrap(self.current_row, True)
                # move cursor and reset cursor attribute
                self.current_row, self.current_col = self.current_row + 1, 1
                self._refresh_cursor()
            else:
                self.current_col = self.mode.width

    def set_wrap(self, row, wrap):
        """Connect/disconnect rows on active page by line wrap."""
        self._apage.set_wrap(row, wrap)

    def wraps(self, row):
        """The given row is connected by line wrap."""
        return self._apage.wraps(row)

    def set_row_length(self, row, length):
        """Set logical length of row."""
        self._apage.set_row_length(row, length)

    def row_length(self, row):
        """Return logical length of row."""
        return self._apage.row_length(row)


    ###########################################################################
    # cursor position

    def up(self):
        """Move the current position 1 row up."""
        self.set_pos(self.current_row - 1, self.current_col, scroll_ok=False)

    def down(self):
        """Move the current position 1 row down."""
        self.set_pos(self.current_row + 1, self.current_col, scroll_ok=False)

    def incr_pos(self):
        """Increase the current position by a char width."""
        if self.overflow:
            # if we're in overflow, there's no character yet. So it's halfwidth by default.
            step = 1
        else:
            step = self._apage.get_charwidth(self.current_row, self.current_col)
            # on a trail byte: go just one to the right
            step = step or 1
        self.set_pos(self.current_row, self.current_col + step, scroll_ok=False)

    def decr_pos(self):
        """Decrease the current position by a char width."""
        # apply overflow to column number
        if self.overflow:
            self.current_col += 1
            self.overflow = False
        # check width of cell to the left
        width = self._apage.get_charwidth(self.current_row, self.current_col-1)
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
        row = self.find_end_of_line(self.current_row)
        if self.row_length(row) == self.mode.width:
            self.set_pos(row, self.row_length(row))
            self.overflow = True
        else:
            self.set_pos(row, self.row_length(row) + 1)

    def set_pos(self, to_row, to_col, scroll_ok=True):
        """Set the current position."""
        # overflow status is maintained under up or down movements
        # e.g. if we print a char while on col 80, we end up in overflow position.
        # down-error from there gets us to overflow position on the next row.
        if to_col < self.mode.width:
            self.overflow = False
        self.current_row, self.current_col = to_row, to_col
        # move cursor and reset cursor attribute
        # this may alter self.current_row, self.current_col
        self._wrap_around_and_scroll_as_needed(scroll_ok)
        self._refresh_cursor()

    def _wrap_around_and_scroll_as_needed(self, scroll_ok):
        """Check if we have crossed the screen boundaries and move as needed."""
        if self._bottom_row_allowed:
            if self.current_row == self.mode.height:
                self.current_col = min(self.mode.width, self.current_col)
                if self.current_col < 1:
                    self.current_col += 1
                return
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

    @contextmanager
    def collect_updates(self):
        """Lock cursor to collect updates and submit them in one go."""
        save, self._locked = self._locked, True
        try:
            with self._apage.collect_updates():
                yield
        finally:
            self._locked = save
            self._refresh_cursor()

    def _refresh_cursor(self):
        """Move the cursor to the current position and update its attributes."""
        if self._locked:
            return
        row, col = self.current_row, self.current_col
        # in text mode, set the cursor width and attriute to that of the new location
        if self.mode.is_text_mode:
            # set halfwidth/fullwidth cursor
            width = self._apage.get_charwidth(row, col)
            # set the cursor attribute
            attr = self._apage.get_attr(row, col)
            self._cursor.move(row, col, attr, width)
        else:
            # move the cursor
            self._cursor.move(row, col)

    ###########################################################################
    # clearing the screen

    def clear_view(self):
        """Clear the scroll area."""
        with self._modify_attr_on_clear():
            self._apage.clear_rows(self.scroll_area.top, self.scroll_area.bottom, self._attr)
            self.set_pos(self.scroll_area.top, 1)

    def clear(self):
        """Clear the screen."""
        with self._modify_attr_on_clear():
            self._apage.clear_rows(1, self.mode.height, self._attr)
            self.set_pos(1, 1)

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

    def scroll(self, from_row=None):
        """Scroll the scroll region up by one row, starting at from_row."""
        if from_row is None:
            from_row = self.scroll_area.top
        self._apage.scroll_up(from_row, self.scroll_area.bottom, self._attr)
        if self.current_row > from_row:
            self.current_row -= 1
            self._refresh_cursor()


    def scroll_down(self, from_row):
        """Scroll the scroll region down by one row, starting at from_row."""
        self._apage.scroll_down(from_row, self.scroll_area.bottom, self._attr)
        if self.current_row >= from_row:
            self.current_row += 1
            self._refresh_cursor()


    ###########################################################################
    # console operations

    def find_start_of_line(self, srow):
        """Find the start of the logical line that includes our current position."""
        # move up as long as previous line wraps
        while srow > 1 and self._apage.wraps(srow-1):
            srow -= 1
        return srow

    def find_end_of_line(self, srow):
        """Find the end of the logical line that includes our current position."""
        # move down as long as this line wraps
        while srow <= self.mode.height and self._apage.wraps(srow):
            srow += 1
        return srow

    # delete

    def delete_fullchar(self):
        """Delete the character (half/fullwidth) at the current position."""
        width = self._apage.get_charwidth(self.current_row, self.current_col)
        # on a halfwidth char, delete once; lead byte, delete twice; trail byte, do nothing
        with self.collect_updates():
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
            self._apage.delete_char_attr(row, col, self._attr)
            # if the row is depleted, drop it and scroll up from below
            if remove_depleted and self.row_length(row) == 0:
                self.scroll(row)
        elif self.row_length(row) == self.mode.width:
            # case 1
            wrap_char_attr = (
                self._apage.get_char(row+1, 1),
                self._apage.get_attr(row+1, 1)
            )
            if self.row_length(row + 1) == 0:
                wrap_char_attr = None
            self._apage.delete_char_attr(
                row, col, self._attr, wrap_char_attr
            )
            self._delete_at(row+1, 1, remove_depleted=True)
        elif col < self.row_length(row):
            # case 2a
            self._apage.delete_char_attr(row, col, self._attr)
        elif remove_depleted and col == self.row_length(row):
            # case 2b (ii) while on the first LF row deleting the last char immediately appends
            # the next row, any subsequent LF rows are only removed once they are fully empty and
            # DEL is pressed another time
            self._apage.delete_char_attr(row, col, self._attr)
        elif remove_depleted and self.row_length(row) == 0:
            # case 2b (iii) this is where the empty row mentioned at 2b (ii) gets removed
            self.scroll(row)
            return
        else:
            # case 2b (i) perform multi_character delete by looping single chars
            for newcol in range(col, self.mode.width+1):
                if self.row_length(row + 1) == 0:
                    break
                wrap_char = self._apage.get_char(row+1, 0)
                self._apage.put_char_attr(row, newcol, wrap_char, self._attr, adjust_end=True)
                self._delete_at(row+1, 1, remove_depleted=True)

    # insert

    def insert_fullchars(self, sequence):
        """Insert one or more half- or fullwidth characters and adjust cursor."""
        # insert one at a time at cursor location
        # to let cursor position logic deal with scrolling
        with self.collect_updates():
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
            self._apage.insert_char_attr(row, col, c, attr)
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
                start = self.find_start_of_line(self.current_row)
                # if we hist the top of the screen, stop inserting & drop chars
                if start <= self.scroll_area.top:
                    return False
                # scroll up
                self.scroll()
                # adjust working row number
                row -= 1
            popped_char = self._apage.insert_char_attr(row, col, c, attr)
            # insert the character in the next row
            return self._insert_at(row+1, 1, popped_char, attr)

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
            end = self.find_end_of_line(self.current_row)
            # if the logical line hits the bottom, start scrolling up to make space...
            if end >= self.scroll_area.bottom:
                # ... until the it also hits the top; then do nothing
                start = self.find_start_of_line(self.current_row)
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

    # console calls

    def clear_line(self, start_row, start_col, quirky_scrolling=False):
        """Clear from given position to end of logical line (CTRL+END, ESC)."""
        end_row = self.find_end_of_line(start_row)
        # clear the first row of the logical line
        self._apage.clear_row_from(start_row, start_col, self._attr)
        # input anomaly: when interacting with INPUT and ESC is pressed,
        # the first line gets cleared but not scrolled
        if quirky_scrolling and end_row > start_row:
            self._apage.clear_row_from(start_row+1, 1, self._attr)
            scroll_row = start_row + 1
        else:
            scroll_row = start_row
        # remove the additional rows in the logical line by scrolling up
        for row in range(end_row, scroll_row, -1):
            self.scroll(row)
        self.set_pos(start_row, start_col)

    def newline(self, wrap):
        """Write a newline with or without wrap."""
        self.set_wrap(self.current_row, wrap)
        self.set_pos(self.current_row + 1, 1, scroll_ok=True)

    def backspace(self, prompt_row, furthest_left):
        """Delete the char to the left (BACKSPACE)."""
        row, col = self.current_row, self.current_col
        start_row = self.find_start_of_line(row)
        # don't backspace through prompt or through start of logical line
        # on the prompt row, don't go any further back than we've been already
        if (
                ((col != furthest_left or row != prompt_row)
                and (col > 1 or row > start_row))
            ):
            self.decr_pos()
        self.delete_fullchar()

    def tab(self, overwrite):
        """Jump to next 8-position tab stop (TAB)."""
        newcol = 9 + 8 * int((self.current_col-1) // 8)
        if overwrite:
            self.set_pos(self.current_row, newcol, scroll_ok=False)
        else:
            self.insert_fullchars(b' ' * (newcol-self.current_col))

    def skip_word_right(self):
        """Skip one word to the right (CTRL+RIGHT)."""
        crow, ccol = self.current_row, self.current_col
        # find non-alphanumeric chars
        while True:
            c = self._apage.get_char(crow, ccol)
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
            c = self._apage.get_char(crow, ccol)
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
            c = self._apage.get_char(crow, ccol)
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
            c = self._apage.get_char(crow, ccol)
            if (c not in ALPHANUMERIC):
                break
        self.set_pos(last_row, last_col)

    ###########################################################################
    # bottom bar

    def update_bar(self, descriptions):
        """Update the key descriptions in the bottom bar."""
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
        self._apage.clear_rows(key_row, key_row, self._attr)
        if not self.mode.is_text_mode:
            reverse_attr = self._attr
        elif (self._attr >> 4) & 0x7 == 0:
            reverse_attr = 0x70
        else:
            reverse_attr = 0x07
        if self._bottom_bar.visible:
            with self.collect_updates():
                # always show only complete 8-character cells
                # this matters on pcjr/tandy width=20 mode
                for col in range((self.mode.width//8) * 8):
                    char, reverse = self._bottom_bar.get_char_reverse(col)
                    attr = reverse_attr if reverse else self._attr
                    self._apage.put_char_attr(key_row, col+1, char, attr)
            self.set_row_length(self.mode.height, self.mode.width)

    ###########################################################################
    # text retrieval on vpage (clipboard and print screen)
    # or apage (input, interactive commands)

    def get_chars(self, as_type=bytes):
        """Get all characters on the visible page, as tuple of tuples of bytes (raw) or unicode (dbcs)."""
        return self._pages[self._vpagenum].get_chars(as_type=as_type)

    def get_text(self, start_row=None, stop_row=None, pagenum=None, wrap=True, as_type=text_type):
        """
        Retrieve consecutive rows of text on page `pagenum`,
        as tuple of bytes (raw) / tuple of unicode (dbcs).
        Each row is one (bytes or unicode) string and ends at the row length.
        So poked characters may not be included.
        Wrapped lines are output as a single row if `wrap=True`.
        """
        if pagenum is None:
            pagenum = self._vpagenum
        page = self._pages[pagenum]
        chars = page.get_chars(as_type)
        if start_row is None:
            start_row = 1
        if stop_row is None:
            stop_row = len(chars)
        output = tuple(
            as_type().join(_charrow[:page.row_length(_row0 + 1)])
            for _row0, _charrow in enumerate(chars)
            if start_row <= _row0 + 1 <= stop_row
        )
        if wrap:
            prev_wraps = [False] + list(
                page.wraps(_row)
                # don't include the stop_row as we need previous-row wraps anyway
                for _row in range(start_row, stop_row)
            )
            wrapped_output = []
            for row, prev_row_wrap in zip(output, prev_wraps):
                if prev_row_wrap:
                    wrapped_output[-1] += row
                else:
                    wrapped_output.append(row)
            output = tuple(wrapped_output)
        return output

    def get_logical_line(self, from_row, as_type=bytes):
        """Get the contents of the logical line on the active page, as one bytes string."""
        # find start and end of logical line
        start_row = self.find_start_of_line(from_row)
        stop_row = self.find_end_of_line(from_row)
        line = as_type().join(
            self.get_text(start_row, stop_row, pagenum=self._apagenum, as_type=bytes)
        )
        return line

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
            self._cursor.set_textmode_override(cursor != 0)
        error.throw_if(start is None and stop is not None)
        if stop is None:
            stop = start
        if start is not None:
            error.range_check(0, 31, start, stop)
            # cursor shape only has an effect in text mode
            if self.mode.is_text_mode:
                self._cursor.set_shape(start, stop)

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
                result = self._apage.get_attr(row, col)
        else:
            result = self._apage.get_byte(row, col)
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
            self.current_row, self.current_col = start, 1
            self._refresh_cursor()
