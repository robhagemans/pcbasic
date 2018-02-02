"""
PC-BASIC - text.py
Text-buffer operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

#######################################################################################
# text buffer

class TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, attr, width):
        """Set up screen row empty and unwrapped."""
        self.width = width
        self.clear(attr)
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False

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


class TextPage(object):
    """Buffer for a screen page."""

    def __init__(self, attr, width, height, codepage, do_fullwidth):
        """Initialise the screen buffer to given dimensions."""
        self.row = [TextRow(attr, width) for _ in xrange(height)]
        self.width = width
        self.height = height
        self._dbcs_enabled = codepage.dbcs and do_fullwidth
        self._codepage = codepage

    def put_char_attr(self, row, col, c, attr, one_only=False, force=False):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        # update the screen buffer
        self.row[row-1].buf[col-1] = (c, attr)
        self.row[row-1].double[col-1] = 0
        if self._dbcs_enabled:
            # mark out replaced char and changed following dbcs characters to be redrawn
            return self._recalculate_dbcs_from(row, col, one_only, force)
        else:
            # mark the replaced char to be redrawn
            return col, col+1

    def _recalculate_dbcs_from(self, row, col, one_only, force):
        """Recalculate DBCS buffer starting from given byte."""
        start, stop = col, col+1
        orig_col = col
        # replace chars from here until necessary to update double-width chars
        therow = self.row[row-1]
        # replacing a trail byte? take one step back
        # previous char could be a lead byte? take a step back
        if (col > 1 and therow.double[col-2] != 2 and
                (therow.buf[col-1][0] in self._codepage.trail or
                 therow.buf[col-2][0] in self._codepage.lead)):
            col -= 1
            start -= 1
        # check all dbcs characters between here until it doesn't matter anymore
        while col < self.width:
            c = therow.buf[col-1][0]
            d = therow.buf[col][0]
            if (c in self._codepage.lead and
                    d in self._codepage.trail):
                if (therow.double[col-1] == 1 and
                        therow.double[col] == 2 and col > orig_col):
                    break
                therow.double[col-1] = 1
                therow.double[col] = 2
                start, stop = min(start, col), max(stop, col+2)
                col += 2
            else:
                if therow.double[col-1] == 0 and col > orig_col:
                    break
                therow.double[col-1] = 0
                start, stop = min(start, col), max(stop, col+1)
                col += 1
            if (col >= self.width or
                    (one_only and col > orig_col)):
                break
        # check for box drawing
        if self._codepage.box_protect:
            col = start-2
            connecting = 0
            bset = -1
            while col < stop+2 and col < self.width:
                c = therow.buf[col-1][0]
                d = therow.buf[col][0]
                if bset > -1 and self._codepage.connects(c, d, bset):
                    connecting += 1
                else:
                    connecting = 0
                    bset = -1
                if bset == -1:
                    for b in (0, 1):
                        if self._codepage.connects(c, d, b):
                            bset = b
                            connecting = 1
                if connecting >= 2:
                    therow.double[col] = 0
                    therow.double[col-1] = 0
                    therow.double[col-2] = 0
                    start = min(start, col-1)
                    if col > 2 and therow.double[col-3] == 1:
                        therow.double[col-3] = 0
                        start = min(start, col-2)
                    if (col < self.width-1 and
                            therow.double[col+1] == 2):
                        therow.double[col+1] = 0
                        stop = max(stop, col+2)
                col += 1
        return start, stop


class TextBuffer(object):
    """Buffer for text on all screen pages."""

    def __init__(self, attr, width, height, num_pages, codepage, do_fullwidth):
        """Initialise the screen buffer to given pages and dimensions."""
        self.pages = [TextPage(attr, width, height, codepage, do_fullwidth)
                      for _ in range(num_pages)]
        self.width = width
        self.height = height

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap

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
            # do we need to set this here?
            therow.double[col-1] = 1
            therow.double[col] = 2
        elif therow.double[col-1] == 0:
            ca = therow.buf[col-1]
            char, attr = ca[0], ca[1]
        else:
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

    def get_logical_line(self, pagenum, srow):
        """Get bytearray of the contents of the logical line."""
        # find start of logical line
        srow = self.find_start_of_line(pagenum, srow)
        line = bytearray()
        # add all rows of the logical line
        for therow in self.pages[pagenum].row[srow-1:self.height]:
            line += bytearray(pair[0] for pair in therow.buf[:therow.end])
            # continue so long as the line wraps
            if not therow.wrap:
                break
            # wrap before end of line means LF
            if therow.end < self.width:
                line += b'\n'
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
