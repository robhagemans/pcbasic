"""
PC-BASIC - data package
HEX font loader

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import pkg_resources
import logging

from ..basic.codepage import PRINTABLE_ASCII
from .resources import get_data, ResourceFailed

FONT_DIR = u'fonts'
FONT_PATTERN = u'{path}/{name}_{height:02d}.hex'
FONTS = sorted(set(name.split(u'_', 1)[0] for name in pkg_resources.resource_listdir(__name__, FONT_DIR) if name.lower().endswith(u'.hex')))


def read_fonts(codepage_dict, font_families, warn):
    """Load font typefaces."""
    # load the graphics fonts, including the 8-pixel RAM font
    # use set() for speed - lookup is O(1) rather than O(n) for list
    unicode_needed = set(codepage_dict.itervalues())
    # break up any grapheme clusters and add components to set of needed glyphs
    unicode_needed |= set(c for cluster in unicode_needed if len(cluster) > 1 for c in cluster)
    # substitutes is in reverse order: { yen: backslash }
    substitutes = {
        grapheme_cluster: unichr(ord(cp_point))
        for cp_point, grapheme_cluster in codepage_dict.iteritems()
        if cp_point in PRINTABLE_ASCII and (len(grapheme_cluster) > 1 or ord(grapheme_cluster) != ord(cp_point))
    }
    fonts = {}
    # load fonts, height-16 first
    for height in (16, 14, 8):
        # load a Unifont .hex font and take the codepage subset
        font_files = []
        for name in font_families:
            try:
                font_files.append(
                        get_data(FONT_PATTERN, path=FONT_DIR, name=name, height=height))
            except ResourceFailed as e:
                if warn:
                    logging.debug(e)
        fonts[height] = FontLoader(height).load_hex(
                font_files, unicode_needed, substitutes, warn=warn)
        # fix missing code points font based on 16-line font
        if fonts[16]:
            fonts[height].fix_missing(unicode_needed, fonts[16])
    if 8 in fonts:
        fonts[9] = fonts[8]
    # convert keys from unicode to codepage
    fonts = {
        height: {c: font._fontdict[uc] for c, uc in codepage_dict.iteritems() if uc in font._fontdict}
        for height, font in fonts.iteritems()
    }
    return {height: font for height, font in fonts.iteritems()}


class FontLoader(object):
    """Single-height bitfont."""

    def __init__(self, height):
        """Initialise the font."""
        self._height = height
        self._fontdict = {}

    def load_hex(self, hex_resources, unicode_needed, substitutes, warn=True):
        """Load a set of overlaying unifont .hex files."""
        self._fontdict = {}
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
                    if (c in self._fontdict):
                        continue
                    # string must be 32-byte or 16-byte; cut to required font size
                    if len(fonthex) < 32:
                        raise ValueError
                    if len(fonthex) < 64:
                        fonthex = fonthex[:2*self._height]
                    else:
                        fonthex = fonthex[:4*self._height]
                    self._fontdict[c] = fonthex.decode('hex')
                except Exception as e:
                    logging.warning('Could not parse line in font file: %s', repr(line))
        # substitute code points
        self._fontdict.update({old: self._fontdict[new]
                for (new, old) in substitutes.iteritems()
                if new in self._fontdict})
        # char 0 should always be defined and empty
        self._fontdict[u'\0'] = b'\0' * self._height
        self._combine_glyphs(unicode_needed)
        # in debug mode, check if we have all needed glyphs
        if warn:
            self._warn_missing(unicode_needed)
        return self

    def _combine_glyphs(self, unicode_needed):
        """Fix missing grapheme clusters by combining components."""
        for cluster in unicode_needed:
            if cluster not in self._fontdict:
                # try to combine grapheme clusters first
                if len(cluster) > 1:
                    # combine strings
                    clusterglyph = bytearray(self._height)
                    try:
                        for c in cluster:
                            for y, row in enumerate(self._fontdict[c]):
                                clusterglyph[y] |= ord(row)
                    except KeyError as e:
                        logging.debug('Could not combine grapheme cluster %s, missing %s [%s]',
                            cluster, repr(c), c)
                    self._fontdict[cluster] = str(clusterglyph)

    def _warn_missing(self, unicode_needed, max_warnings=3):
        """Check if we have all needed glyphs."""
        # fontdict: unicode char -> glyph
        missing = unicode_needed - set(self._fontdict)
        warnings = 0
        for u in missing:
            warnings += 1
            logging.debug('Code point u+%x not represented in font', ord(u))
            if warnings == max_warnings:
                logging.debug('Further code point warnings suppressed.')
                break

    def fix_missing(self, unicode_needed, font16):
        """Fill in missing codepoints in font using 16-line font or blanks."""
        if self._height == 16:
            return
        for c in unicode_needed:
            if c not in self._fontdict:
                # try to construct from 16-bit font
                try:
                    s16 = list(font16.fontdict[c])
                    start = (16 - self._height) // 2
                    if len(s16) == 16:
                        self._fontdict[c] = ''.join([s16[i] for i in range(start, 16-start)])
                    else:
                        self._fontdict[c] = ''.join([s16[i] for i in range(start*2, 32-start*2)])
                except (KeyError, AttributeError) as e:
                    self._fontdict[c] = b'\0' * self._height
