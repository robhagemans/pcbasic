"""
PC-BASIC - font.py
Font handling

(c) 2014--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging
import binascii

from ...compat import iteritems, int2byte, zip

from ..base import bytematrix
from ..data import DEFAULT_FONT as _DEFAULT_FONT


# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
_CARRY_COL_9_BYTES = tuple(range(0xb0, 0xdf+1))
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
_CARRY_ROW_9_BYTES = tuple(range(0xb0, 0xdf+1))


class Font(object):
    """Single-height bitfont."""

    def __init__(self, height, fontdict, codepage):
        """Initialise the font."""
        self._width = 8
        self._height = int(height)
        self._codepage = codepage
        if not fontdict:
            if height == 8:
                fontdict = {
                    self._byte_to_char(_i): binascii.unhexlify(_glyph)
                    for _i, _glyph in enumerate(_DEFAULT_FONT)
                }
            else:
                raise ValueError(
                    'No font dictionary specified and no %d-pixel default available.' % (height,)
                )
        self._fontdict = fontdict
        self._glyphs = {}
        self._carry_row_9_chars = [self._byte_to_char(_b) for _b in _CARRY_ROW_9_BYTES]
        self._carry_col_9_chars = [self._byte_to_char(_b) for _b in _CARRY_COL_9_BYTES]

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def copy(self):
        """Make a deep copy."""
        copy = self.__class__(self._height, self._fontdict.copy(), self._codepage)
        copy._width = self._width
        return copy

    def init_mode(self, width, height):
        """Preload SBCS glyphs at mode switch."""
        if self._width != width or self._height != height:
            self._width = width
            self._height = height
            # build the basic 256 codepage characters
            for _c in range(256):
                self._build_glyph(self._byte_to_char(_c), fullwidth=False)
        return self

    def get_byte(self, byte, offset):
        """Get byte value from character sequence."""
        char = self._byte_to_char(byte)
        return ord(self._fontdict[char][offset:offset+1])

    def set_byte(self, byte, offset, byte_value):
        """Set byte value for character sequence."""
        char = self._byte_to_char(byte)
        old = self._fontdict[char]
        self._fontdict[char] = old[:offset%8] + int2byte(byte_value) + old[offset%8+1:]
        if char in self._glyphs:
            self._build_glyph(char, fullwidth=False)

    def _byte_to_char(self, byte):
        """Map single byte value to unicode character."""
        return self._codepage.codepoint_to_unicode(int2byte(byte), use_substitutes=True)

    def _get_glyph(self, char, fullwidth):
        """Retrieve a glyph, building if needed."""
        try:
            return self._glyphs[char]
        except KeyError:
            self._build_glyph(char, fullwidth)
            return self._glyphs[char]

    def _build_glyph(self, char, fullwidth):
        """Build a glyph for the given unicode character."""
        try:
            byteseq = bytearray(self._fontdict[char])
        except KeyError:
            logging.debug('No glyph for code point %r; replacing with blank.', char)
            byteseq = bytearray(self._height)
        # shape of encoded mask (8 or 16 wide; usually 8, 14 or 16 tall)
        code_height = 8 if self._height == 9 else self._height
        if len(byteseq) < code_height:
            byteseq = byteseq.ljust(code_height, b'\0')
        glyph = bytematrix.ByteMatrix.frompacked(byteseq, code_height, items_per_byte=8)
        # stretch or sqeeze if necessary
        req_width = self._width * (2 if fullwidth else 1)
        if req_width >= glyph.width * 2:
            logging.debug('Code point %r stretched to full-width.', char)
            glyph = glyph.hrepeat(2)
        elif glyph.width >= (req_width-1) * 2:
            logging.debug('Code point %r squeezed to half-width.', char)
            glyph = glyph[:, ::2]
        # repeat last rows (e.g. for 9-bit high chars)
        if self._height > glyph.height:
            glyph = _extend_height(glyph, char in self._carry_row_9_chars)
        # repeat last cols (e.g. for 9-bit wide chars)
        if req_width > glyph.width:
            glyph = _extend_width(glyph, char in self._carry_col_9_chars)
        self._glyphs[char] = glyph

    def render_text(self, unicode_list, attr, back, underline):
        """Return a sprite, width and height for given row of text."""
        sprite = self.get_glyphs(unicode_list).render(back, attr)
        if underline:
            sprite[-1:, :] = attr
        return sprite

    def get_glyphs(self, unicode_list):
        """
        Retrieve a row of text as a single matrix [y][x].
        Text is given as list of unicode, with fullwidth characters marked by trailing u''.
        """
        # find width of each character
        # last character can't be fullwidth as it's not trailed by u''
        # note that we assign a fw value to u'' markers, but this is ignored below
        fw_list = (not _next for _next in unicode_list[1:] + [True])
        # skip u'' markers
        return bytematrix.hstack(
            self._get_glyph(_c, _fw)
            for _c, _fw in zip(unicode_list, fw_list) if _c
        )


def _extend_height(glyph, carry_last):
    """Extend the character height by a row."""
    if carry_last:
        return bytematrix.vstack((glyph, glyph[-1, :]))
    else:
        return glyph.vextend(1)

def _extend_width(glyph, carry_last):
    """Extend the character width by a column."""
    # use two empty columns if doublewidth
    if glyph.width >= 16:
        return glyph.hextend(2)
    if carry_last:
        return bytematrix.hstack((glyph, glyph[:, -1]))
    return glyph.hextend(1)
