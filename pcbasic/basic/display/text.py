"""
PC-BASIC - text.py
Text-buffer operations

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

from ...compat import zip, int2byte


class TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, attr, width):
        """Set up screen row empty and unwrapped."""
        self._width = width
        # screen buffer, initialised to spaces
        self.buf = [(b' ', attr)] * width
        # last non-whitespace column [0--width], zero means all whitespace
        self.end = 0
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False

    def copy_from(self, src_row):
        """Copy contents from another row."""
        assert self._width == src_row._width
        self.buf[:] = src_row.buf[:]
        self.end = src_row.end
        self.wrap = src_row.wrap

    def clear(self, attr, from_col, to_col, adjust_end, clear_wrap):
        """Clear the screen row between given columns (inclusive; base-1 index)."""
        self.buf[from_col-1:to_col] = [(b' ', attr)] * (to_col - from_col + 1)
        if adjust_end and self.end <= to_col:
            self.end = min(self.end, from_col-1)
        if clear_wrap:
            self.wrap = False

    def put_char_attr(self, col, char, attr, adjust_end):
        """Put a byte to the screen."""
        assert isinstance(char, bytes), type(char)
        # update the screen buffer
        self.buf[col-1] = (char, attr)
        if adjust_end:
            self.end = max(self.end, col)

    def insert_char_attr(self, col, c, attr):
        """
        Insert a halfwidth character,
        NOTE: This sets the attribute of *everything that has moved* to attr.
        Return the character dropping off at the end.
        """
        self.buf.insert(col-1, (c, attr))
        pop_char, pop_attr = self.buf.pop()
        if self.end >= col:
            self.end = min(self.end + 1, self._width)
        else:
            self.end = col
        # reset the attribute of all moved chars
        self.buf[col-1:max(self.end, col)] = [
            (_c, attr) for _c, _ in self.buf[col-1:max(self.end, col)]
        ]
        # attrs change only up to logical end of row but dbcs can change up to row width
        stop_col = max(self.end, col)
        return pop_char, pop_attr, col, stop_col


class TextPage(object):
    """Buffer for a screen page."""

    def __init__(self, attr, width, height):
        """Initialise the screen buffer to given dimensions."""
        self._rows = [TextRow(attr, width) for _ in range(height)]
        self._width = width
        self._height = height

    def __repr__(self):
        """Return an ascii representation of the screen buffer (for debugging)."""
        horiz_bar = ('   +' + '-' * self._width + '+')
        row_strs = []
        lastwrap = False
        row_strs.append(horiz_bar)
        for i, row in enumerate(self._rows):
            # convert non-ascii bytes to \x81 etc
            # dbcs is encoded as double char in left column, '' in right
            rowbytes = (_pair[0] for _pair in row.buf)
            # replace non-ascii with ? - this is not ideal but
            # for python2 we need to stick to ascii-128 so implicit conversion to bytes works
            # and for python3 we must use unicode
            # and backslashreplace messes up the output width...
            rowstr = ''.join(
                _char.decode('ascii', 'replace').replace(u'\ufffd', u'?')
                for _char in rowbytes
            )
            left = '\\' if lastwrap else '|'
            right = '\\' if row.wrap else '|'
            row_strs.append('{0:2} {1}{2}{3} {4:2}'.format(
                i, left, rowstr, right, row.end,
            ))
            lastwrap = row.wrap
        row_strs.append(horiz_bar)
        return '\n'.join(row_strs)

    def set_wrap(self, row, wrap):
        """Connect/disconnect rows on active page by line wrap."""
        self._rows[row-1].wrap = wrap

    def wraps(self, row):
        """The given row is connected by line wrap."""
        return self._rows[row-1].wrap

    def set_row_length(self, row, length):
        """Return logical length of row."""
        self._rows[row-1].end = length

    def row_length(self, row):
        """Return logical length of row."""
        return self._rows[row-1].end

    def copy_from(self, src):
        """Copy source into this page."""
        for dst_row, src_row in zip(self._rows, src._rows):
            dst_row.copy_from(src_row)

    def clear_area(self, from_row, from_col, to_row, to_col, attr, clear_wrap, adjust_end):
        """Clear a rectangular area of the screen (inclusive bounds; 1-based indexing)."""
        for row in self._rows[from_row-1:to_row]:
            row.clear(attr, from_col, to_col, adjust_end, clear_wrap)

    def put_char_attr(self, row, col, c, attr, adjust_end=False):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        self._rows[row-1].put_char_attr(col, c, attr, adjust_end=adjust_end)

    def insert_char_attr(self, row, col, c, attr):
        """
        Insert a halfwidth character,
        NOTE: This sets the attribute of *everything that has moved* to attr.
        Return the character dropping off at the end.
        """
        return self._rows[row-1].insert_char_attr(col, c, attr)

    def delete_char_attr(self, row, col, attr, fill_char_attr=None):
        """
        Delete a halfwidth character, filling with space(s) at the logical end.
        NOTE: This sets the attribute of *everything that has moved* to attr.
        """
        therow = self._rows[row-1]
        # do nothing beyond logical end of row
        if therow.end < col:
            return 0, 0
        adjust_end = fill_char_attr is None
        if adjust_end:
            fill_char_attr = (b' ', attr)
        therow.buf[:therow.end] = (
            therow.buf[:col-1] + therow.buf[col:therow.end] + [fill_char_attr]
        )
        # reset the attribute of all moved chars
        therow.buf[col-1:max(therow.end, col)] = [
            (_c, attr) for _c, _ in therow.buf[col-1:max(therow.end, col)]
        ]
        # attrs change only up to old logical end of row but dbcs can change up to row width
        stop_col = max(therow.end, col)
        # change the logical end
        if adjust_end:
            therow.end = max(therow.end - 1, 0)
        return col, stop_col

    def scroll_up(self, from_line, bottom, attr):
        """Scroll up."""
        new_row = TextRow(attr, self._width)
        self._rows.insert(bottom, new_row)
        # remove any wrap above/into deleted row, unless the deleted row wrapped into the next
        if self.wraps(from_line-1):
            self.set_wrap(from_line-1, self.wraps(from_line))
        # delete row # from_line
        del self._rows[from_line-1]

    def scroll_down(self, from_line, bottom, attr):
        """Scroll down."""
        new_row = TextRow(attr, self._width)
        # insert at row # from_line
        self._rows.insert(from_line - 1, new_row)
        # delete row # bottom
        del self._rows[bottom-1]
        # if we inserted below a wrapping row, make sure the new empty row wraps
        # so as not to break line continuation
        if self.wraps(from_line-1):
            self.set_wrap(from_line, True)

    def get_char(self, row, col):
        """Retrieve a byte from the screen (SBCS or DBCS half-char)."""
        return ord(self._rows[row-1].buf[col-1][0])

    def get_attr(self, row, col):
        """Retrieve attribute from the screen."""
        return self._rows[row-1].buf[col-1][1]

    def get_text_raw(self):
        """Retrieve all raw text on this page."""
        return tuple(self.get_row_text_raw() for row in range(self._rows))

    def get_row_text_raw(self, row):
        """Retrieve raw text on a row."""
        return b''.join(_c for _c, _ in self._rows[row-1].buf)

    ###########################################################################
    # logical lines

    def get_text_logical(self, start_row, start_col, stop_row, stop_col):
        """Retrieve section of logical text for copying."""
        if start_row == stop_row:
            return self._get_row_logical(start_row, start_col, stop_col)
        text = [
            self._get_row_logical(start_row, from_col=start_col)
        ]
        text.extend(
            self._get_row_logical(_row)
            for _row in range(start_row, stop_row-1)
        )
        text.append(self._get_row_logical(stop_row, to_col=stop_col))
        return b''.join(text)

    def _get_row_logical(self, row, from_col=1, to_col=None):
        """Get the text between given columns (inclusive), don't go beyond end."""
        if to_col is None:
            to_col = self.row_length(row)
        else:
            to_col = min(to_col, self.row_length(row))
        text = b''.join(_c for _c, _ in self._rows[row-1].buf[from_col-1:to_col])
        # wrap on line that is not full means LF
        if self.row_length(row) < self._width or not self.wraps(row):
            text += b'\n'
        return text

    def find_start_of_line(self, srow):
        """Find the start of the logical line that includes our current position."""
        # move up as long as previous line wraps
        while srow > 1 and self.wraps(srow-1):
            srow -= 1
        return srow

    def find_end_of_line(self, srow):
        """Find the end of the logical line that includes our current position."""
        # move down as long as this line wraps
        while srow <= self._height and self.wraps(srow):
            srow += 1
        return srow

    def get_logical_line(self, from_row, from_column=None):
        """Get the contents of the logical line."""
        # find start and end of logical line
        if from_column is None:
            start_row, start_col = self.find_start_of_line(from_row), 1
        else:
            start_row, start_col = from_row, from_column
        stop_row = self.find_end_of_line(from_row)
        return self.get_text_logical(start_row, start_col, stop_row, stop_col=None)

    def get_logical_line_from(self, srow, prompt_row, left, right):
        """Get bytearray of the contents of the logical line, adapted for INPUT."""
        # INPUT: the prompt starts at the beginning of a logical line
        # but the row may have moved up: this happens on line 24
        # in this case we need to move up to the start of the logical line
        prompt_row = self.find_start_of_line(prompt_row)
        # find start of logical line
        srow = self.find_start_of_line(srow)
        # INPUT returns empty string if enter pressed below prompt row
        if srow > prompt_row:
            return b''
        text = []
        # add all rows of the logical line
        for row in range(srow, self._height+1):
            # exclude prompt, if any; only go from furthest_left to furthest_right
            if row == prompt_row:
                text.append(self._get_row_logical(row, from_col=left, to_col=right))
            else:
                text.append(self._get_row_logical(row))
            if not self.wraps(row):
                break
        return b''.join(text)
