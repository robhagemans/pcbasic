"""
PC-BASIC - data package
HEX font loader

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import pkg_resources
import logging
import binascii

from ..compat import iteritems, itervalues, unichr

from ..basic.codepage import PRINTABLE_ASCII
from .resources import get_data, ResourceFailed


FONT_DIR = u'fonts'
FONT_PATTERN = u'{path}/{name}_{height:02d}.hex'
FONTS = sorted(
    set(name.split(u'_', 1)[0]
    for name in pkg_resources.resource_listdir(__name__, FONT_DIR)
    if name.lower().endswith(u'.hex'))
)

_HEIGHTS = (8, 14, 16)


def _get_font(name, height):
    """Load font from file."""
    try:
        return get_data(FONT_PATTERN, path=FONT_DIR, name=name, height=height)
    except ResourceFailed as e:
        logging.debug('Failed to load font `%s` with height %d: %s', name, height, e)


def read_fonts(codepage_dict, font_families):
    """Load font typefaces."""
    # load the graphics fonts, including the 8-pixel RAM font
    # use set() for speed - lookup is O(1) rather than O(n) for list
    unicode_needed = set(itervalues(codepage_dict))
    # break up any grapheme clusters and add components to set of needed glyphs
    unicode_needed |= set(c for cluster in unicode_needed if len(cluster) > 1 for c in cluster)
    # substitutes is in reverse order: { yen: backslash }
    substitutes = {
        _grapheme_cluster: unichr(ord(_cp_point))
        for _cp_point, _grapheme_cluster in iteritems(codepage_dict)
        if (
            _cp_point in PRINTABLE_ASCII
            and (
                len(_grapheme_cluster) > 1
                or ord(_grapheme_cluster) != ord(_cp_point)
            )
        )
    }
    # load font resources
    font_files = {
        _height: [
            _font for _font in
            (_get_font(_name, _height) for _name in font_families)
            if _font is not None
        ]
        for _height in _HEIGHTS
    }
    # convert
    uc_fonts = {
        _height: load_hex(_font_file, _height, unicode_needed, substitutes)
        for _height, _font_file in iteritems(font_files)
        if _font_file
    }
    # convert keys from unicode to codepage
    fonts = {
        _height: {
            _c: _font[_uc]
            for _c, _uc in iteritems(codepage_dict) if _uc in _font
        }
        for _height, _font in iteritems(uc_fonts)
    }
    return fonts


def load_hex(hex_resources, height, unicode_needed, substitutes):
    """Load a set of overlaying unifont .hex files."""
    fontdict = {}
    all_needed = unicode_needed | set(substitutes)
    for hexres in reversed(hex_resources):
        if hexres is None:
            continue
        for line in hexres.splitlines():
            # ignore empty lines and comment lines (first char is #)
            if (not line) or (line[:1] == b'#'):
                continue
            # strip off comments
            # split unicodepoint and hex string (max 32 chars)
            ucs_str, fonthex = line.split(b'#')[0].split(b':')
            ucs_sequence = ucs_str.split(b',')
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
                if (c in fontdict):
                    continue
                # string must be 32-byte or 16-byte; cut to required font size
                if len(fonthex) < 32:
                    raise ValueError
                if len(fonthex) < 64:
                    fonthex = fonthex[:2*height]
                else:
                    fonthex = fonthex[:4*height]
                fontdict[c] = binascii.unhexlify(fonthex)
            except Exception as e:
                logging.warning('Could not parse line in font file: %s', repr(line))
    # substitute code points
    fontdict.update({
        old: fontdict[new]
        for (new, old) in iteritems(substitutes)
        if new in fontdict
    })
    # fill missing with nulls
    missing = unicode_needed - set(fontdict)
    fontdict.update({_u: b'\0' * height for _u in missing})
    # char 0 should always be defined and empty
    fontdict[u'\0'] = b'\0' * height
    _combine_glyphs(height, fontdict, unicode_needed)
    # warn if we miss needed glyphs
    _warn_missing(missing)
    return fontdict

def _combine_glyphs(height, fontdict, unicode_needed):
    """Fix missing grapheme clusters by combining components."""
    for cluster in unicode_needed:
        if cluster not in fontdict:
            # try to combine grapheme clusters first
            if len(cluster) > 1:
                # combine strings
                clusterglyph = bytearray(height)
                try:
                    for c in cluster:
                        for y, row in enumerate(fontdict[c]):
                            clusterglyph[y] |= ord(row)
                except KeyError as e:
                    logging.debug(
                        'Could not combine grapheme cluster %s, missing %r [%s]', cluster, c, c
                    )
                fontdict[cluster] = bytes(clusterglyph)

def _warn_missing(missing, max_warnings=3):
    """Warn if we miss needed glyphs."""
    warnings = 0
    for u in missing:
        warnings += 1
        logging.debug('Code point u+%x not represented in font', ord(u))
        if warnings == max_warnings:
            logging.debug('Further code point warnings suppressed.')
            break
