"""
PC-BASIC - text.py
Text-buffer operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""


#######################################################################################
# text buffer

class TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, battr, bwidth):
        """Set up screen row empty and unwrapped."""
        # screen buffer, initialised to spaces, dim white on black
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False

    def clear(self, battr):
        """Clear the screen row buffer. Leave wrap untouched."""
        bwidth = len(self.buf)
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0


class TextPage(object):
    """Buffer for a screen page."""

    def __init__(self, battr, bwidth, bheight, pagenum, do_dbcs, codepage):
        """Initialise the screen buffer to given dimensions."""
        self.row = [TextRow(battr, bwidth) for _ in xrange(bheight)]
        self.width = bwidth
        self.height = bheight
        self.pagenum = pagenum
        self.do_dbcs = do_dbcs
        self.codepage = codepage

    def put_char_attr(self, crow, ccol, c, cattr, one_only=False, force=False):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        # update the screen buffer
        self.row[crow-1].buf[ccol-1] = (c, cattr)
        # mark the replaced char for refreshing
        start, stop = ccol, ccol+1
        self.row[crow-1].double[ccol-1] = 0
        # mark out sbcs and dbcs characters
        if self.codepage.dbcs and self.do_dbcs:
            orig_col = ccol
            # replace chars from here until necessary to update double-width chars
            therow = self.row[crow-1]
            # replacing a trail byte? take one step back
            # previous char could be a lead byte? take a step back
            if (ccol > 1 and therow.double[ccol-2] != 2 and
                    (therow.buf[ccol-1][0] in self.codepage.trail or
                     therow.buf[ccol-2][0] in self.codepage.lead)):
                ccol -= 1
                start -= 1
            # check all dbcs characters between here until it doesn't matter anymore
            while ccol < self.width:
                c = therow.buf[ccol-1][0]
                d = therow.buf[ccol][0]
                if (c in self.codepage.lead and
                        d in self.codepage.trail):
                    if (therow.double[ccol-1] == 1 and
                            therow.double[ccol] == 2 and ccol > orig_col):
                        break
                    therow.double[ccol-1] = 1
                    therow.double[ccol] = 2
                    start, stop = min(start, ccol), max(stop, ccol+2)
                    ccol += 2
                else:
                    if therow.double[ccol-1] == 0 and ccol > orig_col:
                        break
                    therow.double[ccol-1] = 0
                    start, stop = min(start, ccol), max(stop, ccol+1)
                    ccol += 1
                if (ccol >= self.width or
                        (one_only and ccol > orig_col)):
                    break
            # check for box drawing
            if self.codepage.box_protect:
                ccol = start-2
                connecting = 0
                bset = -1
                while ccol < stop+2 and ccol < self.width:
                    c = therow.buf[ccol-1][0]
                    d = therow.buf[ccol][0]
                    if bset > -1 and self.codepage.connects(c, d, bset):
                        connecting += 1
                    else:
                        connecting = 0
                        bset = -1
                    if bset == -1:
                        for b in (0, 1):
                            if self.codepage.connects(c, d, b):
                                bset = b
                                connecting = 1
                    if connecting >= 2:
                        therow.double[ccol] = 0
                        therow.double[ccol-1] = 0
                        therow.double[ccol-2] = 0
                        start = min(start, ccol-1)
                        if ccol > 2 and therow.double[ccol-3] == 1:
                            therow.double[ccol-3] = 0
                            start = min(start, ccol-2)
                        if (ccol < self.width-1 and
                                therow.double[ccol+1] == 2):
                            therow.double[ccol+1] = 0
                            stop = max(stop, ccol+2)
                    ccol += 1
        return start, stop


class TextBuffer(object):
    """Buffer for text on all screen pages."""

    def __init__(self, battr, bwidth, bheight, bpages, do_dbcs, codepage):
        """Initialise the screen buffer to given pages and dimensions."""
        self.pages = [TextPage(battr, bwidth, bheight, num, do_dbcs, codepage)
                      for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap

    def get_char(self, pagenum, crow, ccol):
        """Retrieve a byte from the screen (SBCS or DBCS half-char)."""
        return ord(self.pages[pagenum].row[crow-1].buf[ccol-1][0])

    def get_attr(self, pagenum, crow, ccol):
        """Retrieve a byte from the screen (SBCS or DBCS half-char)."""
        return self.pages[pagenum].row[crow-1].buf[ccol-1][1]

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
            for crow in range(srow, self.height+1):
                therow = self.pages[pagenum].row[crow-1]
                # exclude prompt, if any; only go from furthest_left to furthest_right
                if crow == prompt_row:
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
