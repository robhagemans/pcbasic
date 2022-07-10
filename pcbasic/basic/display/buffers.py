"""
PC-BASIC - display.buffers
Text and pixel buffer operations

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from contextlib import contextmanager

from ...compat import zip, int2byte, iterchar, text_type
from ...compat import iter_chunks
from ..base import signals
from ..base.bytematrix import ByteMatrix


class _TextRow(object):
    """Buffer for a single row of the screen."""

    def __init__(self, attr, width):
        """Set up screen row empty and unwrapped."""
        # halfwidth character buffer, initialised to spaces
        self.chars = [b' '] * width
        # attribute buffer
        self.attrs = [attr] * width
        # last non-whitespace column [0--width], zero means all whitespace
        self.length = 0
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False


class _PixelAccess(object):
    """
    Wrapper class to enable pixel indexing.
    Usage example: VideoBuffer.pixels[y0:y1, x0:x1] = sprite
    """

    def __init__(self, video_buffer):
        """Wrap the VideoBuffer."""
        self._video_buffer = video_buffer
        self._pixels = video_buffer._pixels

    @property
    def width(self):
        """Width in pixels."""
        return self._pixels.width

    @property
    def height(self):
        """Height in pixels."""
        return self._pixels.height

    def __getitem__(self, index):
        """Retrieve a copy of a pixel range."""
        return self._pixels[index]

    def __setitem__(self, index, data):
        """Set a pixel range, clear affected text buffers and submit to interface."""
        self._pixels[index] = data
        # make sure the indices are slices so that __getattr__ returns a matrix
        yslice, xslice = index
        if not isinstance(yslice, slice):
            yslice = slice(yslice, yslice+1)
        if not isinstance(xslice, slice):
            xslice = slice(xslice, xslice+1)
        self._video_buffer._update_pixels(yslice.start, xslice.start, yslice.stop-1, xslice.stop-1)


class VideoBuffer(object):
    """Buffer for a screen page."""

    def __init__(
            self, queues, pixel_height, pixel_width, height, width,
            colourmap, attr, font, codepage, do_fullwidth
        ):
        """Initialise the screen buffer to given dimensions."""
        self._rows = [_TextRow(attr, width) for _ in range(height)]
        self._width = width
        self._height = height
        self._font = font
        self._colourmap = colourmap
        # DBCS support
        self._codepage = codepage
        self._dbcs_enabled = codepage.dbcs and do_fullwidth
        self._dbcs_text = [[u' '] * width for _ in range(height)]
        # initialise pixel buffers
        self._pixels = ByteMatrix(pixel_height, pixel_width)
        # with set_attr that calls submit_pixels
        self._pixel_access = _PixelAccess(self)
        # needed for signals only
        self._queues = queues
        # dirty rectangle collection
        self._dirty_left = {}
        self._dirty_right = {}
        self._locked = False
        self._visible = False

    def set_visible(self, visible):
        """Set the vpage flag."""
        if self._visible != visible:
            self._visible = visible
            if visible:
                self.resubmit()

    @property
    def pixels(self):
        """Pixel-buffer access."""
        return self._pixel_access

    def __repr__(self):
        """Return an ascii representation of the screen buffer (for debugging)."""
        horiz_bar = ('   +' + '-' * self._width + '+')
        row_strs = []
        lastwrap = False
        row_strs.append(horiz_bar)
        for i, row in enumerate(self._rows):
            # replace non-ascii with ? - this is not ideal but
            # for python2 we need to stick to ascii-128 so implicit conversion to bytes works
            # and for python3 we must use unicode
            # and backslashreplace messes up the output width...
            rowstr = ''.join(
                _char.decode('ascii', 'replace').replace(u'\ufffd', u'?')
                for _char in row.chars
            )
            left = '\\' if lastwrap else '|'
            right = '\\' if row.wrap else '|'
            row_strs.append('{0:2} {1}{2}{3} {4:2}'.format(
                i, left, rowstr, right, row.length,
            ))
            lastwrap = row.wrap
        row_strs.append(horiz_bar)
        return '\n'.join(row_strs)

    ##########################################################################
    # query buffers

    def get_char(self, row, col):
        """Retrieve a (halfwidth) character from the screen (as bytes)."""
        return self._rows[row-1].chars[col-1]

    def get_byte(self, row, col):
        """Retrieve a byte from the character buffer (as int)."""
        return ord(self._rows[row-1].chars[col-1])

    def get_attr(self, row, col):
        """Retrieve attribute from the screen."""
        return self._rows[row-1].attrs[col-1]

    def get_charwidth(self, row, col):
        """Get DBCS width of cell on active page."""
        if col == self._width:
            return 1
        if not self._dbcs_text[row-1][col-1]:
            return 0
        return 1 if self._dbcs_text[row-1][col] else 2

    def get_chars(self, as_type=bytes):
        """Retrieve all characters on this page, as tuple of tuples of bytes (raw) or unicode (dbcs)."""
        if as_type == bytes:
            return tuple(tuple(_row.chars) for _row in self._rows)
        elif as_type == text_type:
            return tuple(tuple(_row) for _row in self._dbcs_text)
        else:
            raise ValueError('`as_type` must be bytes or unicode, not %s.' % type(as_type))

    ##########################################################################
    # logical line parameters: wrap and row length

    def set_wrap(self, row, wrap):
        """Connect/disconnect rows on active page by line wrap."""
        self._rows[row-1].wrap = wrap

    def wraps(self, row):
        """The given row is connected by line wrap."""
        return self._rows[row-1].wrap

    def set_row_length(self, row, length):
        """Return logical length of row."""
        self._rows[row-1].length = length

    def row_length(self, row):
        """Return logical length of row."""
        return self._rows[row-1].length

    def has_linefeed(self, row):
        """Row terminates in a linefeed character."""
        return self.wraps(row) and self.row_length(row) < self._width

    ##########################################################################
    # convert between text and pixel positions

    def pixel_to_text_pos(self, x, y):
        """Convert pixel position to text position."""
        return 1 + y // self._font.height, 1 + x // self._font.width

    def pixel_to_text_area(self, x0, y0, x1, y1):
        """Convert from pixel area to text area."""
        col0 = min(self._width, max(1, 1 + x0 // self._font.width))
        row0 = min(self._height, max(1, 1 + y0 // self._font.height))
        col1 = min(self._width, max(1, 1 + x1 // self._font.width))
        row1 = min(self._height, max(1, 1 + y1 // self._font.height))
        return row0, col0, row1, col1

    def text_to_pixel_pos(self, row, col):
        """Convert text position to pixel position."""
        # area bounds are all inclusive
        return (
            (col-1) * self._font.width, (row-1) * self._font.height,
        )

    def text_to_pixel_area(self, row0, col0, row1, col1):
        """Convert text area to pixel area."""
        # area bounds are all inclusive
        return (
            (col0-1) * self._font.width, (row0-1) * self._font.height,
            col1 * self._font.width - 1, row1 * self._font.height - 1
        )

    ##########################################################################
    # page copy

    def copy_from(self, src):
        """Copy source into this page."""
        for dst_row, src_row in zip(self._rows, src._rows):
            assert len(dst_row.chars) == len(src_row.chars)
            assert len(dst_row.attrs) == len(src_row.attrs)
            dst_row.chars[:] = src_row.chars
            dst_row.attrs[:] = src_row.attrs
            dst_row.length = src_row.length
            dst_row.wrap = src_row.wrap
        self._dbcs_text[:] = src._dbcs_text
        self._pixels[:, :] = src._pixels
        self._pixel_access = _PixelAccess(self)
        # resubmit to interface
        self.resubmit()

    ##########################################################################
    # modify pixels

    def _update_pixels(self, top, left, bottom, right):
        """Clear the text under the rect and submit to interface."""
        row0, col0, row1, col1 = self.pixel_to_text_area(left, top, right, bottom)
        # clear text area
        # we can't see or query the attribute in graphics mode - might as well set to zero
        self._clear_text_area(
            row0, col0, row1, col1, 0, adjust_end=False, clear_wrap=False
        )
        rect = self._pixels[top:bottom+1, left:right+1]
        self._submit(row0, col0, row1, col1)

    ##########################################################################
    # modify text

    def put_char_attr(self, row, col, char, attr, adjust_end=False):
        """Put a byte to the screen, reinterpreting SBCS and DBCS as necessary."""
        assert isinstance(char, bytes), type(char)
        # update the screen buffer
        self._rows[row-1].chars[col-1] = char
        self._rows[row-1].attrs[col-1] = attr
        if adjust_end:
            self._rows[row-1].length = max(self._rows[row-1].length, col)
        self._update(row, col, col)

    def insert_char_attr(self, row, col, char, attr):
        """
        Insert a halfwidth character,
        NOTE: This sets the attribute of *everything that has moved* to attr.
        Return the character dropping off at the end.
        """
        therow = self._rows[row-1]
        therow.chars.insert(col-1, char)
        therow.attrs.insert(col-1, attr)
        pop_char = therow.chars.pop()
        pop_attr = therow.attrs.pop()
        if therow.length >= col:
            therow.length = min(therow.length + 1, self._width)
        else:
            therow.length = col
        # reset the attribute of all moved chars
        stop_col = max(therow.length, col)
        therow.attrs[col-1:stop_col] = [attr] * (stop_col - col + 1)
        # attrs change only up to logical end of row but dbcs can change up to row width
        self._update(row, col, stop_col)
        return pop_char

    def delete_char_attr(self, row, col, attr, fill_char_attr=None):
        """
        Delete a halfwidth character, filling with space(s) at the logical end.
        NOTE: This sets the attribute of *everything that has moved* to attr.
        """
        therow = self._rows[row-1]
        # do nothing beyond logical end of row
        if therow.length < col:
            return 0, 0
        adjust_end = fill_char_attr is None
        if fill_char_attr is None:
            fill_char, fill_attr = b' ', attr
        else:
            fill_char, fill_attr = fill_char_attr
        therow.chars[:therow.length] = (
            therow.chars[:col-1] + therow.chars[col:therow.length] + [fill_char]
        )
        therow.attrs[:therow.length] = (
            therow.attrs[:col-1] + therow.attrs[col:therow.length] + [fill_attr]
        )
        # reset the attribute of all moved chars
        stop_col = max(therow.length, col)
        therow.attrs[col-1:stop_col] = [attr] * (stop_col - col + 1)
        # change the logical end
        if adjust_end:
            therow.length = max(therow.length - 1, 0)
        self._update(row, col, stop_col)
        return col, stop_col

    ###########################################################################
    # update DBCS/unicode buffer

    def _refresh_dbcs(self, row, orig_start, orig_stop):
        """Update the DBCS buffer."""
        raw = b''.join(self._rows[row-1].chars)
        # get a new converter each time so we don't share state between calls
        conv = self._codepage.get_converter(preserve=b'', use_substitutes=True)
        sequences = conv.to_unicode_list(raw, flush=True)
        updated = [old != new for old, new in zip(self._dbcs_text[row-1], sequences)]
        self._dbcs_text[row-1] = sequences
        try:
            start = updated.index(True) + 1
            stop = len(updated) - updated[::-1].index(True)
        except ValueError:
            # no change to text in dbcs buffer
            start, stop = len(updated), 0
        start, stop = min(start, orig_start), max(stop, orig_stop)
        return start, stop

    ###########################################################################
    # submit to interface

    def resubmit(self):
        """Completely resubmit the text and graphics screen to the interface."""
        self._submit(1, 1, self._height, self._width)

    def _submit(self, top, left, bottom, right):
        """Submit a rectangular screen section to interface (text coordinates)."""
        if self._visible:
            text = [_row[left-1:right] for _row in self._dbcs_text[top-1:bottom]]
            attrs = [_row.attrs[left-1:right] for _row in self._rows[top-1:bottom]]
            x0, y0 = self.text_to_pixel_pos(top, left)
            x1, y1 = self.text_to_pixel_pos(bottom+1, right+1)
            self._queues.video.put(signals.Event(
                signals.VIDEO_UPDATE, (top, left, text, attrs, y0, x0, self._pixels[y0:y1, x0:x1])
            ))

    ###########################################################################
    # text rendering - dirty rectangles

    @contextmanager
    def collect_updates(self):
        """Lock buffer to collect updates and submit them in one go."""
        if self._locked:
            # nested call - only lock/unlock outermost
            yield
        else:
            self._locked = True
            try:
                yield
            finally:
                self._locked = False
                self.force_submit()

    def _update(self, row, start, stop):
        """Mark section of screen row as dirty for update."""
        # merge with existing dirty rects for row
        if row in self._dirty_left:
            self._dirty_left[row] = min(start, self._dirty_left[row])
            self._dirty_right[row] = max(stop, self._dirty_right[row])
        else:
            self._dirty_left[row] = start
            self._dirty_right[row] = stop
        if not self._locked:
            self.force_submit()

    def force_submit(self):
        """Update dbcs, write all dirty text rectangles to pixels and submit."""
        for row in sorted(self._dirty_left):
            start, stop = self._refresh_dbcs(row, self._dirty_left[row], self._dirty_right[row])
            self._draw_text(row, start, row, stop)
            self._submit(row, start, row, stop)
        self._dirty_left = {}
        self._dirty_right = {}

    ###########################################################################
    # text rendering

    def _draw_text(self, top, left, bottom, right):
        """Draw text in a rectangular screen section to pixel buffer."""
        for row in range(top, bottom+1):
            gen_chunks = iter_chunks(
                self._dbcs_text[row-1][left-1:right], self._rows[row-1].attrs[left-1:right]
            )
            col = left
            for text, attr in gen_chunks:
                sprite = self._draw_text_chunk(row, col, text, attr)
                # marking by trailing u'' ensures list length is column number
                col += len(text)

    def _draw_text_chunk(self, row, col, chars, attr):
        """Draw a chunk of text in a single attribute to pixels and interface."""
        if row < 1 or col < 1 or row > self._height or col > self._width:
            logging.debug('Ignoring out-of-range text rendering request: row %d col %d', row, col)
            return
        _, back, _, underline = self._colourmap.split_attr(attr)
        # update pixel buffer
        left, top = self.text_to_pixel_pos(row, col)
        sprite = self._font.render_text(chars, attr, back, underline)
        self._pixels[top:top+sprite.height, left:left+sprite.width] = sprite
        return sprite

    ###########################################################################
    # clearing buffers

    def clear_rows(self, start, stop, attr):
        """Clear text and graphics on given (inclusive) text row range."""
        self._clear_text_area(
            start, 1, stop, self._width, attr, adjust_end=True, clear_wrap=True
        )
        # clear pixels
        x0, y0, x1, y1 = self.text_to_pixel_area(start, 1, stop, self._width)
        _, back, _, _ = self._colourmap.split_attr(attr)
        self._pixels[y0:y1+1, x0:x1+1] = back
        # submit dirty rects before clear
        self.force_submit()
        # this should only be called on the active page
        if self._visible:
            self._queues.video.put(signals.Event(signals.VIDEO_CLEAR_ROWS, (back, start, stop)))

    def clear_row_from(self, row, col, attr):
        """Clear from given position to end of row."""
        if col == 1:
            self.clear_rows(row, row, attr)
        else:
            # clear the first row of the logical line
            self._clear_text_area(
                row, col, row, self._width, attr, adjust_end=True, clear_wrap=True
            )
            # submit changes
            self._update(row, 1, self._width)

    def _clear_text_area(self, from_row, from_col, to_row, to_col, attr, clear_wrap, adjust_end):
        """
        Clear a rectangular area of the screen (inclusive bounds; 1-based indexing).
        Does not clear pixels or submit to interface (which allows its use in put_rect).
        """
        for row in self._rows[from_row-1:to_row]:
            row.chars[from_col-1:to_col] = [b' '] * (to_col - from_col + 1)
            row.attrs[from_col-1:to_col] = [attr] * (to_col - from_col + 1)
            if adjust_end and row.length <= to_col:
                row.length = min(row.length, from_col-1)
            if clear_wrap:
                row.wrap = False
        # we have to rebuild the DBCS buffer unless clearing the whole row or not enabled
        # as lead or trail bytes might have been replaced by spaces
        if self._dbcs_enabled and (to_col-from_col+1) < self._width:
            for row in range(from_row, to_row+1):
                # refresh whole row
                # characters earlier on the row may be affected, e.g. box-protected chars
                self._refresh_dbcs(row, 1, self._width)
        else:
            for row in range(from_row, to_row+1):
                self._dbcs_text[row-1][from_col-1:to_col] = [u' '] * (to_col-from_col+1)

    ###########################################################################
    # scrolling buffers

    def scroll_up(self, from_row, to_row, attr):
        """Scroll up by one line, between from_row and to_row, filling empty row with attr."""
        # submit dirty rects before scroll
        self.force_submit()
        _, back, _, _ = self._colourmap.split_attr(attr)
        if self._visible:
            self._queues.video.put(signals.Event(
                signals.VIDEO_SCROLL, (-1, from_row, to_row, back)
            ))
        # update text buffer
        new_row = _TextRow(attr, self._width)
        self._rows.insert(to_row, new_row)
        # remove any wrap above/into deleted row, unless the deleted row wrapped into the next
        if self._rows[from_row-2].wrap:
            self._rows[from_row-2].wrap = self._rows[from_row-1].wrap
        # delete row # from_row
        del self._rows[from_row-1]
        # update dbcs buffer
        self._dbcs_text[from_row-1:to_row-1] = self._dbcs_text[from_row:to_row]
        self._dbcs_text[to_row-1] = [u' '] * self._width
        # update pixel buffer
        sx0, sy0, sx1, sy1 = self.text_to_pixel_area(
            from_row+1, 1, to_row, self._width
        )
        tx0, ty0 = self.text_to_pixel_pos(from_row, 1)
        self._pixels.move(sy0, sy1+1, sx0, sx1+1, ty0, tx0)

    def scroll_down(self, from_row, to_row, attr):
        """Scroll down by one line, between from_row and to_row, filling empty row with attr."""
        # submit dirty rects before scroll
        self.force_submit()
        _, back, _, _ = self._colourmap.split_attr(attr)
        if self._visible:
            self._queues.video.put(signals.Event(
                signals.VIDEO_SCROLL, (1, from_row, to_row, back)
            ))
        # update text buffer
        new_row = _TextRow(attr, self._width)
        # insert at row # from_row
        self._rows.insert(from_row - 1, new_row)
        # delete row # to_row
        del self._rows[to_row-1]
        # if we inserted below a wrapping row, make sure the new empty row wraps
        # so as not to break line continuation
        if self._rows[from_row-2].wrap:
            self._rows[from_row-1].wrap = True
        # update dbcs buffer
        self._dbcs_text[from_row:to_row] = self._dbcs_text[from_row-1:to_row-1]
        self._dbcs_text[from_row-1] = [u' '] * self._width
        # update pixel buffer
        sx0, sy0, sx1, sy1 = self.text_to_pixel_area(
            from_row, 1, to_row-1, self._width
        )
        tx0, ty0 = self.text_to_pixel_pos(from_row+1, 1)
        self._pixels.move(sy0, sy1+1, sx0, sx1+1, ty0, tx0)
