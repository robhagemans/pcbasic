"""
PC-BASIC - font.py
Font handling

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging

try:
    import numpy
except ImportError:
    numpy = None

from ..base import signals


# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
CARRY_COL_9_CHARS = tuple(chr(_c) for _c in range(0xb0, 0xdf+1))
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
CARRY_ROW_9_CHARS = tuple(chr(_c) for _c in range(0xb0, 0xdf+1))


# The glyphs below are extracted from Henrique Peron's CPIDOS v3.0,
# CPIDOS is distributed with FreeDOS at
#   http://www.freedos.org/software/?prog=cpidos
#   http://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/dos/cpi/
# CPIDOS is Copyright (C) 2002-2011 by Henrique Peron (hperon@terra.com.br)
# and licensed under the GNU GPL version 2 or later.
DEFAULT_FONT = {chr(_i): _v.decode('hex') for _i, _v in enumerate((
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
        self._height = height
        if height == 8 and not fontdict:
            fontdict = DEFAULT_FONT
        self._fontdict = fontdict

    def get_byte(self, charvalue, offset):
        """Get byte sequency for character."""
        return ord(self._fontdict[chr(charvalue)][offset])

    def set_byte(self, charvalue, offset, byte):
        """Set byte sequency for character."""
        old = self._fontdict[chr(charvalue)]
        self._fontdict[chr(charvalue)] = old[:offset%8] + byte + old[offset%8+1:]
        #self.screen.rebuild_glyph(charvalue)

    def build_glyph(self, c, req_width, req_height):
        """Build a glyph for the given codepage character."""
        try:
            face = bytearray(self._fontdict[c])
        except KeyError:
            logging.debug(
                    b'code point [%s] not represented in font, replacing with blank glyph.',
                    repr(c))
            face = bytearray(int(self._height))
        # shape of encoded mask (8 or 16 wide; usually 8, 14 or 16 tall)
        code_height = 8 if req_height == 9 else req_height
        code_width = (8 * len(face)) // code_height
        force_double = req_width >= code_width * 2
        force_single = code_width >= (req_width-1) * 2
        if force_double or force_single:
            # i.e. we need a double-width char but got single or v.v.
            logging.debug(
                    b'Incorrect glyph width for code point [%s]: %d-pixel requested, %d-pixel found.',
                    repr(c), req_width, code_width)
        return _unpack_glyph(
                face, code_height, code_width, req_height, req_width,
                force_double, force_single,
                c in CARRY_COL_9_CHARS, c in CARRY_ROW_9_CHARS)

if numpy:

    def _unpack_glyph(
            face, code_height, code_width, req_height, req_width,
            force_double, force_single, carry_col_9, carry_row_9):
        """Convert byte list to glyph pixels, numpy implementation."""
        glyph = numpy.unpackbits(face, axis=0).reshape((code_height, code_width)).astype(bool)
        # repeat last rows (e.g. for 9-bit high chars)
        if req_height > glyph.shape[0]:
            if carry_row_9:
                repeat_row = glyph[-1]
            else:
                repeat_row = numpy.zeros((1, code_width), dtype=numpy.uint8)
            while req_height > glyph.shape[0]:
                glyph = numpy.vstack((glyph, repeat_row))
        if force_double:
            glyph = glyph.repeat(2, axis=1)
        elif force_single:
            glyph = glyph[:, ::2]
        # repeat last cols (e.g. for 9-bit wide chars)
        if req_width > glyph.shape[1]:
            if carry_col_9:
                repeat_col = numpy.atleast_2d(glyph[:,-1]).T
            else:
                repeat_col = numpy.zeros((code_height, 1), dtype=numpy.uint8)
            while req_width > glyph.shape[1]:
                glyph = numpy.hstack((glyph, repeat_col))
        return glyph

else:

    def _unpack_glyph(
            face, code_height, code_width, req_height, req_width,
            force_double, force_single, carry_col_9, carry_row_9):
        """Convert byte list to glyph pixels, non-numpy implementation."""
        # req_width can be 8, 9 (SBCS), 16, 18 (DBCS) only
        req_width_base = req_width if req_width <= 9 else req_width // 2
        # if our code glyph is too wide for request, we need to make space
        start_width = req_width*2 if force_single else req_width
        glyph = [ [False]*start_width for _ in range(req_height) ]
        for yy in range(code_height):
            for half in range(code_width//8):
                line = face[yy*(code_width//8)+half]
                for xx in range(8):
                    if (line >> (7-xx)) & 1 == 1:
                        glyph[yy][half*8 + xx] = True
            # halve the width if code width incorrect
            if force_single:
                glyph[yy] = glyph[yy][::2]
            # MDA/VGA 9-bit characters
            # carry_col_9 will be ignored for double-width glyphs
            if carry_col_9 and req_width == 9:
                glyph[yy][8] = glyph[yy][7]
        # tandy 9-bit high characters
        if carry_row_9 and req_height == 9:
            for xx in range(8):
                glyph[8][xx] = glyph[7][xx]
        # double the width if code width incorrect
        if force_double:
            for yy in range(code_height):
                for xx in range(req_width_base, -1, -1):
                    glyph[yy][2*xx+1] = glyph[yy][xx]
                    glyph[yy][2*xx] = glyph[yy][xx]
        return glyph


#######################################################################################
# glyph cache

class GlyphCache(object):

    def __init__(self, mode, fonts, codepage, queues):
        """Initialise glyph set."""
        self._queues = queues
        self._mode = mode
        self._fonts = fonts
        self._codepage = codepage
        # preload SBCS glyphs
        self._glyphs = {
            c: self._fonts[mode.font_height].build_glyph(c, mode.font_width, mode.font_height)
            for c in map(chr, range(256))
        }
        self.submit()

    def submit(self):
        """Send glyph dict to interface."""
        if self._mode.is_text_mode:
            # send glyphs to signals; copy is necessary
            # as dict may change here while the other thread is working on it
            self._queues.video.put(signals.Event(signals.VIDEO_BUILD_GLYPHS,
                ({self._codepage.to_unicode(k, u'\0'): v for k, v in self._glyphs.iteritems()},)))

    def rebuild_glyph(self, ordval):
        """Rebuild a text-mode character after POKE."""
        if self._mode.is_text_mode:
            # force rebuilding the character by deleting and requesting
            del self._glyphs[chr(ordval)]
            self._submit_char(chr(ordval))

    def _submit_char(self, char):
        """Rebuild glyph and send to interface."""
        mask = self._fonts[self._mode.font_height].build_glyph(
                char, self._mode.font_width*2, self._mode.font_height)
        self._glyphs[char] = mask
        if self._mode.is_text_mode:
            self._queues.video.put(signals.Event(
                    signals.VIDEO_BUILD_GLYPHS, ({self._codepage.to_unicode(char, u'\0'): mask},)))

    def check_char(self, char):
        """Submit glyph if needed."""
        if self._mode.is_text_mode and char not in self._glyphs:
            self._submit_char(char)

    if numpy:
        def get_sprite(self, row, col, char, fore, back):
            """Return a sprite for a given character."""
            if char not in self._glyphs:
                self._submit_char(char)
            mask = self._glyphs[char]
            # set background
            glyph = numpy.full(mask.shape, back, dtype=int)
            # stamp foreground mask
            glyph[mask] = fore
            x0, y0 = (col-1) * self._mode.font_width, (row-1) * self._mode.font_height
            x1, y1 = x0 + mask.shape[1] - 1, y0 + mask.shape[0] - 1
            return x0, y0, x1, y1, glyph
    else:
        def get_sprite(self, row, col, char, fore, back):
            """Return a sprite for a given character."""
            if char not in self._glyphs:
                self._submit_char(char)
            mask = self._glyphs[char]
            glyph = [[(fore if bit else back) for bit in row] for row in mask]
            x0, y0 = (col-1) * self._mode.font_width, (row-1) * self._mode.font_height
            x1, y1 = x0 + len(mask[0]) - 1, y0 + len(mask) - 1
            return x0, y0, x1, y1, glyph
