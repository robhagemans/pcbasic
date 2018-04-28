"""
PC-BASIC - text.py
Text-buffer operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging


class TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, attr, width, conv, dbcs_enabled):
        """Set up screen row empty and unwrapped."""
        self.width = width
        self.clear(attr)
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
        self._dbcs_enabled = dbcs_enabled
        self._conv = conv

    def clear(self, attr):
        """Clear the screen row buffer. Leave wrap untouched."""
        # screen buffer, initialised to spaces
        self.buf = [(b' ', attr)] * self.width
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [0] * self.width
        # last non-whitespace character
        self.end = 0

    def clear_from(self, scol, attr):
        """Clear characters from given position till end of row."""
        self.buf = self.buf[:scol-1] + [(b' ', attr)] * (self.width - scol + 1)
        self.double = self.double[:scol-1] + [0] * (self.width - scol + 1)
        self.end = min(self.end, scol-1)

    def put_char_attr(self, col, c, attr):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        # update the screen buffer
        self.buf[col-1] = (c, attr)
        self.double[col-1] = 0
        # for sbcs codepages we're done now
        if not self._dbcs_enabled:
            return col, col
        # mark out replaced char and changed following dbcs characters to be redrawn
        sequences = self._conv.mark(b''.join(entry[0] for entry in self.buf), flush=True)
        flags = ((0,) if len(seq) == 1 else (1, 2) for seq in sequences)
        old_double = self.double
        self.double = [entry for flag in flags for entry in flag]
        # find the first and last changed columns, to be able to redraw
        diff = [old != new for old, new in zip(old_double, self.double)]
        if True in diff:
            start, stop = diff.index(True) + 1, len(diff) - diff[::-1].index(True)
        else:
            start, stop = col, col
        # if the tail byte has changed, the lead byte needs to be redrawn as well
        if self.double[start-1] == 2:
            start -= 1
        return min(col, start), max(col, stop)


class TextPage(object):
    """Buffer for a screen page."""

    def __init__(self, attr, width, height, conv, dbcs_enabled):
        """Initialise the screen buffer to given dimensions."""
        self.row = [TextRow(attr, width, conv, dbcs_enabled) for _ in xrange(height)]
        self.width = width
        self.height = height


class TextBuffer(object):
    """Buffer for text on all screen pages."""

    def __init__(self, attr, width, height, num_pages, codepage, do_fullwidth):
        """Initialise the screen buffer to given pages and dimensions."""
        self._dbcs_enabled = codepage.dbcs and do_fullwidth
        self._conv = codepage.get_converter(preserve=b'')
        self.pages = [TextPage(attr, width, height, self._conv, self._dbcs_enabled)
                      for _ in range(num_pages)]
        self.width = width
        self.height = height

    def __str__(self):
        """Return a string representation of the screen buffer (for debugging)."""
        horiz_bar = ('  +' + '-' * self.width + '+')
        lastwrap = False
        row_strs = []
        for num, page in enumerate(self.pages):
            row_strs += [horiz_bar]
            for i, row in enumerate(page.row):
                s = [ c[0] for c in row.buf ]
                outstr = '{0:2}'.format(i)
                if lastwrap:
                    outstr += ('\\')
                else:
                    outstr += ('|')
                outstr += (''.join(s))
                if row.wrap:
                    row_strs.append(outstr + '\\ {0:2}'.format(row.end))
                else:
                    row_strs.append(outstr + '| {0:2}'.format(row.end))
                lastwrap = row.wrap
            row_strs.append(horiz_bar)
        return '\n'.join(row_strs)

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap

    def clear_area(self, pagenum, row0, col0, row1, col1, attr):
        """Clear a rectangular area of the screen."""
        for r in range(row0-1, row1):
            self.pages[pagenum].row[r].buf[col0-1:col1] = [(b' ', attr)] * (col1 - col0 + 1)

    def put_char_attr(self, pagenum, row, col, c, attr):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        return self.pages[pagenum].row[row-1].put_char_attr(col, c, attr)

    def scroll_up(self, pagenum, from_line, bottom, attr):
        """Scroll up."""
        self.pages[pagenum].row.insert(bottom,
                TextRow(attr, self.width, self._conv, self._dbcs_enabled))
        del self.pages[pagenum].row[from_line-1]

    def scroll_down(self, pagenum, from_line, bottom, attr):
        """Scroll down."""
        self.pages[pagenum].row.insert(from_line - 1,
                TextRow(attr, self.width, self._conv, self._dbcs_enabled))
        del self.pages[pagenum].row[bottom-1]

    def get_char(self, pagenum, row, col):
        """Retrieve a byte from the screen (SBCS or DBCS half-char)."""
        return ord(self.pages[pagenum].row[row-1].buf[col-1][0])

    def get_attr(self, pagenum, row, col):
        """Retrieve attribute from the screen."""
        return self.pages[pagenum].row[row-1].buf[col-1][1]

    def get_charwidth(self, pagenum, row, col):
        """Retrieve DBCS character width in bytes."""
        dbcs = self.pages[pagenum].row[row-1].double[col-1]
        if dbcs == 0:
            return 1
        elif dbcs == 1:
            return 2
        return 0

    def get_fullchar_attr(self, pagenum, row, col):
        """Retrieve SBCS or DBCS character."""
        therow = self.pages[pagenum].row[row-1]
        if therow.double[col-1] == 1:
            ca = therow.buf[col-1]
            da = therow.buf[col]
            char, attr = ca[0] + da[0], da[1]
        elif therow.double[col-1] == 0:
            ca = therow.buf[col-1]
            char, attr = ca[0], ca[1]
        else:
            char, attr = '\0', 0
            logging.debug('DBCS buffer corrupted at %d, %d (%d)', row, col, therow.double[col-1])
        return char, attr

    def get_text_raw(self, pagenum):
        """Retrieve all raw text on a page."""
        return tuple(
            b''.join(c for c, _ in self.pages[pagenum].row[row_index].buf)
            for row_index in range(self.pages[pagenum].height)
        )

    ###########################################################################
    # logical lines

    def get_text_logical(self, pagenum, start_row, start_col, stop_row, stop_col):
        """Retrieve section of logical text for copying."""
        # include lead byte if start on trail
        if self.pages[pagenum].row[start_row-1].double[start_col-1] == 2:
            start_col -= 1
        # include trail byte if end on lead
        if self.pages[pagenum].row[stop_row-1].double[stop_col-2] == 1:
            stop_col += 1
        r, c = start_row, start_col
        full = []
        clip = []
        while r < stop_row or (r == stop_row and c < stop_col):
            clip.append(self.pages[pagenum].row[r-1].buf[c-1][0])
            c += 1
            if c > self.pages[pagenum].row[r-1].end:
                if not self.pages[pagenum].row[r-1].wrap:
                    full.append(b''.join(clip))
                    clip = []
                r += 1
                c = 1
        full.append(b''.join(clip))
        return full

    def find_start_of_line(self, pagenum, srow):
        """Find the start of the logical line that includes our current position."""
        # move up as long as previous line wraps
        while srow > 1 and self.pages[pagenum].row[srow-2].wrap:
            srow -= 1
        return srow

    def find_end_of_line(self, pagenum, srow):
        """Find the end of the logical line that includes our current position."""
        # move down as long as this line wraps
        while srow <= self.height and self.pages[pagenum].row[srow-1].wrap:
            srow += 1
        return srow

    def get_logical_line(self, pagenum, start_row, from_column=None):
        """Get bytearray of the contents of the logical line."""
        # find start of logical line
        if from_column is None:
            srow, scol = self.find_start_of_line(pagenum, start_row), 1
        else:
            srow, scol = start_row, from_column
        line = bytearray()
        # add all rows of the logical line
        for row in range(srow, self.height+1):
            therow = self.pages[pagenum].row[row-1]
            line += bytearray(pair[0] for pair in therow.buf[scol-1:therow.end])
            # continue so long as the line wraps
            if not therow.wrap:
                break
            # wrap before end of line means LF
            if therow.end < self.width:
                line += b'\n'
            # all further lines taken from start
            scol = 1
        return bytes(line)

    def get_logical_line_from(self, pagenum, srow, prompt_row, left, right):
        """Get bytearray of the contents of the logical line, adapted for INPUT."""
        # INPUT: the prompt starts at the beginning of a logical line
        # but the row may have moved up: this happens on line 24
        # in this case we need to move up to the start of the logical line
        prompt_row = self.find_start_of_line(pagenum, prompt_row)
        # find start of logical line
        srow = self.find_start_of_line(pagenum, srow)
        line = bytearray()
        # INPUT returns empty string if enter pressed below prompt row
        if srow <= prompt_row:
            # add all rows of the logical line
            for row in range(srow, self.height+1):
                therow = self.pages[pagenum].row[row-1]
                # exclude prompt, if any; only go from furthest_left to furthest_right
                if row == prompt_row:
                    rowpairs = therow.buf[:therow.end][left-1:right-1]
                else:
                    rowpairs = therow.buf[:therow.end]
                # get characters from char/attr pairs and convert to bytearray
                line += bytearray(pair[0] for pair in rowpairs)
                if not therow.wrap:
                    break
                # wrap before end of line means LF
                if therow.end < self.width:
                    line += b'\n'
        return bytes(line)
