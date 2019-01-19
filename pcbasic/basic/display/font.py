"""
PC-BASIC - font.py
Font handling

(c) 2014--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging
import binascii

from ...compat import iteritems, int2byte, zip

from ..base import bytematrix


# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
CARRY_COL_9_CHARS = tuple(int2byte(_c) for _c in range(0xb0, 0xdf+1))
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
CARRY_ROW_9_CHARS = tuple(int2byte(_c) for _c in range(0xb0, 0xdf+1))


# The glyphs below are extracted from Henrique Peron's CPIDOS v3.0,
# CPIDOS is distributed with FreeDOS at
#   http://www.freedos.org/software/?prog=cpidos
#   http://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/dos/cpi/
# CPIDOS is Copyright (C) 2002-2011 by Henrique Peron (hperon@terra.com.br)
# and licensed under the GNU GPL version 2 or later.
DEFAULT_FONT = {
    int2byte(_i): binascii.unhexlify(_v) for _i, _v in enumerate((
    '0000000000000000', '7e81a581bd99817e', '7effdbffc3e7ff7e', '6cfefefe7c381000',
    '10387cfe7c381000', '387c38fefed61038', '10387cfefe7c1038', '0000183c3c180000',
    'ffffe7c3c3e7ffff', '003c664242663c00', 'ffc399bdbd99c3ff', '0f070f7dcccccc78',
    '3c6666663c187e18', '3f333f303070f0e0', '7f637f636367e6c0', '18db3ce7e73cdb18',
    '80e0f8fef8e08000', '020e3efe3e0e0200', '183c7e18187e3c18', '6666666666006600',
    '7fdbdb7b1b1b1b00', '3e613c66663c867c', '000000007e7e7e00', '183c7e187e3c18ff',
    '183c7e1818181800', '181818187e3c1800', '00180cfe0c180000', '003060fe60300000',
    '0000c0c0c0fe0000', '002466ff66240000', '00183c7effff0000', '00ffff7e3c180000',
    '0000000000000000', '00183c3c18180018', '0066662400000000', '006c6cfe6cfe6c6c',
    '00183e603c067c18', '0000c6cc183066c6', '00386c3876dccc76', '0018183000000000',
    '000c18303030180c', '0030180c0c0c1830', '0000663cff3c6600', '000018187e181800',
    '0000000000181830', '000000007e000000', '0000000000001818', '00060c183060c080',
    '00386cc6d6c66c38', '001838181818187e', '007cc6061c3066fe', '007cc6063c06c67c',
    '001c3c6cccfe0c1e', '00fec0c0fc06c67c', '003860c0fcc6c67c', '00fec60c18303030',
    '007cc6c67cc6c67c', '007cc6c67e060c78', '0000181800001818', '0018180000181830',
    '00060c1830180c06', '0000007e00007e00', '006030180c183060', '007cc60c18180018',
    '007cc6dededec078', '00386cc6fec6c6c6', '00fc66667c6666fc', '003c66c0c0c0663c',
    '00f86c6666666cf8', '00fe6268786862fe', '00fe6268786860f0', '003c66c0c0ce663a',
    '00c6c6c6fec6c6c6', '003c18181818183c', '001e0c0c0ccccc78', '00e6666c786c66e6',
    '00f06060606266fe', '00c6eefefed6c6c6', '00c6e6f6decec6c6', '007cc6c6c6c6c67c',
    '00fc66667c6060f0', '007cc6c6c6ce7c0e', '00fc66667c6c66e6', '003c6630180c663c',
    '007e7e5a1818183c', '00c6c6c6c6c6c67c', '00c6c6c6c6c66c38', '00c6c6c6d6d6fe6c',
    '00c6c66c386cc6c6', '006666663c18183c', '00fec68c183266fe', '003c30303030303c',
    '00c06030180c0602', '003c0c0c0c0c0c3c', '10386c0000000000', '00000000000000ff',
    '30180c0000000000', '000000780c7ccc76', '00e0607c666666dc', '0000007cc6c0c67c',
    '001c0c7ccccccc76', '0000007cc6fec07c', '003c6660f86060f0', '00000076cc7c0cf8',
    '00e0606c766666e6', '001800381818183c', '000600060606663c', '00e060666c786ce6',
    '003818181818183c', '000000ecfed6d6d6', '000000dc66666666', '0000007cc6c6c67c',
    '000000dc667c60f0', '00000076cc7c0c1e', '000000dc766060f0', '0000007ec07c06fc',
    '003030fc3030361c', '000000cccccccc76', '000000c6c6c66c38', '000000c6d6d6fe6c',
    '000000c66c386cc6', '000000c6c67e06fc', '0000007e0c18307e', '000e18187018180e',
    '0018181818181818', '007018180e181870', '76dc000000000000', '000010386cc6c6fe',
    '3c66c0c0663c1870', '00cc00cccccccc76', '0c18007cc6fec07c', '386c00780c7ccc76',
    '00cc00780c7ccc76', '603000780c7ccc76', '386c38780c7ccc76', '007cc6c0c67c1870',
    '386c007cc6fec07c', '00c6007cc6fec07c', '3018007cc6fec07c', '006600381818183c',
    '386c00381818183c', '301800381818183c', 'c610386cc6fec6c6', '386c387cc6fec6c6',
    '0c18fec0f8c0c0fe', '000000ec367ed86e', '003e6cccfeccccce', '386c007cc6c6c67c',
    '00c6007cc6c6c67c', '3018007cc6c6c67c', '78cc00cccccccc76', '603000cccccccc76',
    '00c600c6c67e06fc', 'c600386cc6c66c38', 'c600c6c6c6c6c67c', '18187ec0c07e1818',
    '386c64f0606066fc', '66663c7e187e1818', 'f8ccccfac6cfc6c7', '0e1b183c1818d870',
    '183000780c7ccc76', '0c1800381818183c', '0c18007cc6c6c67c', '183000cccccccc76',
    '76dc00dc66666666', '76dc00e6f6decec6', '003c6c6c36007e00', '00386c6c38007c00',
    '003000303060c67c', '000000fec0c00000', '000000fe06060000', '63e66c7e3366cc0f',
    '63e66c7a366adf06', '00180018183c3c18', '0000003366cc6633', '000000cc663366cc',
    '2288228822882288', '55aa55aa55aa55aa', '77dd77dd77dd77dd', '1818181818181818',
    '18181818f8181818', '1818f818f8181818', '36363636f6363636', '00000000fe363636',
    '0000f818f8181818', '3636f606f6363636', '3636363636363636', '0000fe06f6363636',
    '3636f606fe000000', '36363636fe000000', '1818f818f8000000', '00000000f8181818',
    '181818181f000000', '18181818ff000000', '00000000ff181818', '181818181f181818',
    '00000000ff000000', '18181818ff181818', '18181f181f181818', '3636363637363636',
    '363637303f000000', '00003f3037363636', '3636f700ff000000', '0000ff00f7363636',
    '3636373037363636', '0000ff00ff000000', '3636f700f7363636', '1818ff00ff000000',
    '36363636ff000000', '0000ff00ff181818', '00000000ff363636', '363636363f000000',
    '18181f181f000000', '00001f181f181818', '000000003f363636', '36363636ff363636',
    '1818ff18ff181818', '18181818f8000000', '000000001f181818', 'ffffffffffffffff',
    '00000000ffffffff', 'f0f0f0f0f0f0f0f0', '0f0f0f0f0f0f0f0f', 'ffffffff00000000',
    '00000076dcc8dc76', '78ccd8ccc6c6cc00', '00fe6260606060f0', '000000fe6c6c6c6c',
    '00fec6603060c6fe', '0000007ed8d8d870', '0000006666667cc0', '000000fe3030361c',
    '00107cd6d6d67c10', '007cc6c6fec6c67c', '00386cc6c66c28ee', '003c60387cc6c67c',
    '00007edbdb7e0000', '0000005cd6d67c10', '0000007cc670c67c', '007cc6c6c6c6c600',
    '0000fe00fe00fe00', '0018187e1818007e', '0030180c1830007e', '000c1830180c007e',
    '0e1b1b1818181818', '1818181818d8d870', '000018007e001800', '000076dc0076dc00',
    '00386c6c38000000', '0000000018180000', '0000000018000000', '0f0c0c0cec6c3c1c',
    '006c363636360000', '00780c18307c0000', '00003c3c3c3c0000', '0000000000000000',
))}


class Font(object):
    """Single-height bitfont."""

    def __init__(self, height=8, fontdict=None):
        """Initialise the font."""
        self._width = 8
        self._height = int(height)
        if not fontdict:
            if height == 8:
                fontdict = DEFAULT_FONT
            else:
                raise ValueError(
                    'No font dictionary specified and no %d-pixel default available.' % (height,)
                )
        self._fontdict = fontdict
        self._glyphs = {}

    def copy(self):
        """Make a deep copy."""
        copy = self.__class__(self._height, dict(**self._fontdict))
        copy._width = self._width
        return copy

    def init_mode(self, width):
        """Preload SBCS glyphs at mode switch."""
        if self._width != width:
            self._width = width
            for _c in map(int2byte, range(256)):
                self._build_glyph(_c)
        return self

    def get_byte(self, char, offset):
        """Get byte value from character sequence."""
        return ord(self._fontdict[char][offset])

    def set_byte(self, char, offset, byte_value):
        """Set byte value for character sequence."""
        old = self._fontdict[char]
        self._fontdict[char] = old[:offset%8] + int2byte(byte_value) + old[offset%8+1:]
        if char in self._glyphs:
            self._build_glyph(char)

    def _get_glyph(self, char):
        """Retrieve a glyph, building if needed."""
        try:
            return self._glyphs[char]
        except KeyError:
            self._build_glyph(char)
            return self._glyphs[char]

    def _build_glyph(self, char):
        """Build a glyph for the given codepage character."""
        try:
            byteseq = bytearray(self._fontdict[char])
        except KeyError:
            logging.debug('No glyph for code point %r; replacing with blank.', char)
            byteseq = bytearray(self._height)
        # shape of encoded mask (8 or 16 wide; usually 8, 14 or 16 tall)
        code_height = 8 if self._height == 9 else self._height
        glyph = bytematrix.ByteMatrix.frompacked(byteseq, code_height, items_per_byte=8)
        # stretch or sqeeze if necessary
        req_width = self._width * len(char)
        if req_width >= glyph.width * 2:
            logging.debug('Code point %r stretched to full-width.', char)
            glyph = glyph.hrepeat(2)
        elif glyph.width >= (req_width-1) * 2:
            logging.debug('Code point %r squeezed to half-width.', char)
            glyph = glyph[:, ::2]
        # repeat last rows (e.g. for 9-bit high chars)
        if self._height > glyph.height:
            glyph = _extend_height(glyph, char in CARRY_ROW_9_CHARS)
        # repeat last cols (e.g. for 9-bit wide chars)
        if req_width > glyph.width:
            glyph = _extend_width(glyph, char in CARRY_COL_9_CHARS)
        self._glyphs[char] = glyph

    def render_text(self, char_list, attr, back, underline):
        """Return a sprite, width and height for given row of text."""
        sprite = self.get_glyphs(char_list).render(back, attr)
        if underline:
            sprite[-1:, :] = attr
        return sprite

    def get_glyphs(self, char_list):
        """Retrieve a row of text as a single matrix [y][x]."""
        return bytematrix.hstack(self._get_glyph(_c) for _c in char_list)


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
