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

from ..data import read_font_files


def load_fonts(font_families, heights_needed, unicode_needed, substitutes, warn=False):
    """Load font typefaces."""
    fonts = {}
    if 9 in heights_needed:
        # 9-pixel font is same as 8-pixel font
        heights_needed -= set([9])
        heights_needed |= set([8])
    # load fonts, height-16 first
    for height in reversed(sorted(heights_needed)):
        # load a Unifont .hex font and take the codepage subset
        fonts[height] = Font(height).load_hex(
                read_font_files(font_families, height),
                unicode_needed, substitutes, warn=warn)
        # fix missing code points font based on 16-line font
        try:
            font_16 = fonts[16]
        except KeyError:
            font_16 = Font(16).load_hex(
                read_font_files(font_families, 16),
                unicode_needed, substitutes, warn=False)
        if font_16:
            fonts[height].fix_missing(unicode_needed, font_16)
    if 8 in fonts:
        fonts[9] = fonts[8]
    return fonts


class Font(object):
    """Single-height bitfont."""

    def __init__(self, height, fontdict={}):
        """Initialise the font."""
        self.height = height
        self.fontdict = fontdict

    def load_hex(self, hex_resources, unicode_needed, substitutes, warn=True):
        """Load a set of overlaying unifont .hex files."""
        self.fontdict = {}
        all_needed = unicode_needed | set(substitutes)
        for hexres in reversed(hex_resources):
            if hexres is None:
                continue
            for line in hexres.splitlines():
                # ignore empty lines and comment lines (first char is #)
                if (not line) or (line[0] == '#'):
                    continue
                # strip off comments
                # split unicodepoint and hex string (max 32 chars)
                ucs_str, fonthex = line.split('#')[0].split(':')
                ucs_sequence = ucs_str.split(',')
                fonthex = fonthex.strip()
                # extract codepoint and hex string;
                # discard anything following whitespace; ignore malformed lines
                try:
                    # construct grapheme cluster
                    c = u''.join(unichr(int(ucshex.strip(), 16)) for ucshex in ucs_sequence)
                    # skip grapheme clusters we won't need
                    if c not in all_needed:
                        continue
                    # skip chars we already have
                    if (c in self.fontdict):
                        continue
                    # string must be 32-byte or 16-byte; cut to required font size
                    if len(fonthex) < 32:
                        raise ValueError
                    if len(fonthex) < 64:
                        fonthex = fonthex[:2*self.height]
                    else:
                        fonthex = fonthex[:4*self.height]
                    self.fontdict[c] = fonthex.decode('hex')
                except Exception as e:
                    logging.warning('Could not parse line in font file: %s', repr(line))
        # substitute code points
        self.fontdict.update({old: self.fontdict[new]
                for (new, old) in substitutes.iteritems()
                if new in self.fontdict})
        # char 0 should always be defined and empty
        self.fontdict[u'\0'] = '\0'*self.height
        self._combine_glyphs(unicode_needed)
        # in debug mode, check if we have all needed glyphs
        if warn:
            self._warn_missing(unicode_needed)
        return self

    def _combine_glyphs(self, unicode_needed):
        """Fix missing grapheme clusters by combining components."""
        for cluster in unicode_needed:
            if cluster not in self.fontdict:
                # try to combine grapheme clusters first
                if len(cluster) > 1:
                    # combine strings
                    clusterglyph = bytearray(self.height)
                    try:
                        for c in cluster:
                            for y, row in enumerate(self.fontdict[c]):
                                clusterglyph[y] |= ord(row)
                    except KeyError as e:
                        logging.debug('Could not combine grapheme cluster %s, missing %s [%s]',
                            cluster, repr(c), c)
                    self.fontdict[cluster] = str(clusterglyph)

    def _warn_missing(self, unicode_needed, max_warnings=3):
        """Check if we have all needed glyphs."""
        # fontdict: unicode char -> glyph
        missing = unicode_needed - set(self.fontdict)
        warnings = 0
        for u in missing:
            warnings += 1
            logging.debug(u'Codepoint %s [%s] not represented in font', repr(u), u)
            if warnings == max_warnings:
                logging.debug('Further codepoint warnings suppressed.')
                break

    def fix_missing(self, unicode_needed, font16):
        """Fill in missing codepoints in font using 16-line font or blanks."""
        if self.height == 16:
            return
        for c in unicode_needed:
            if c not in self.fontdict:
                # try to construct from 16-bit font
                try:
                    s16 = list(font16.fontdict[c])
                    start = (16 - self.height) // 2
                    if len(s16) == 16:
                        self.fontdict[c] = ''.join([s16[i] for i in range(start, 16-start)])
                    else:
                        self.fontdict[c] = ''.join([s16[i] for i in range(start*2, 32-start*2)])
                except (KeyError, AttributeError) as e:
                    self.fontdict[c] = '\0'*self.height

    def build_glyph(self, c, req_width, req_height, carry_col_9, carry_row_9):
        """Build a glyph for the given unicode character."""
        # req_width can be 8, 9 (SBCS), 16, 18 (DBCS) only
        req_width_base = req_width if req_width <= 9 else req_width // 2
        try:
            face = bytearray(self.fontdict[c])
        except KeyError:
            logging.debug(u'%s [%s] not represented in font, replacing with blank glyph.', c, repr(c))
            face = bytearray(self.height)
        # shape of encoded mask (8 or 16 wide; usually 8, 14 or 16 tall)
        code_height = 8 if req_height == 9 else req_height
        code_width = (8*len(face))//code_height
        force_double = req_width >= code_width*2
        force_single = code_width >= (req_width-1)*2
        if force_double or force_single:
            # i.e. we need a double-width char but got single or v.v.
            logging.debug(u'Incorrect glyph width for %s [%s]: %d-pixel requested, %d-pixel found.', c, repr(c), req_width, code_width)
        if numpy:
            glyph = numpy.unpackbits(face, axis=0).reshape((code_height, code_width)).astype(bool)
            # repeat last rows (e.g. for 9-bit high chars)
            if req_height > glyph.shape[0]:
                if carry_row_9:
                    repeat_row = glyph[-1]
                else:
                    repeat_row = numpy.zeros((1, code_width), dtype = numpy.uint8)
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
                    repeat_col = numpy.zeros((code_height, 1), dtype = numpy.uint8)
                while req_width > glyph.shape[1]:
                    glyph = numpy.hstack((glyph, repeat_col))
        else:
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
