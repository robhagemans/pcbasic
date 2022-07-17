"""
PC-BASIC - data package
HEX font loader

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import pkg_resources
import logging
import binascii
import unicodedata

from ..compat import iteritems, itervalues, unichr, iterchar

from .resources import get_data, ResourceFailed, listdir


FONT_DIR = u'fonts'
FONT_PATTERN = u'{path}/{name}_{height:02d}.hex'
FONTS = sorted(
    set(name.split(u'_', 1)[0]
    for name in listdir(FONT_DIR)
    if name.lower().endswith(u'.hex'))
)
_HEIGHTS = (8, 14, 16)
_DEFAULT_NAME = 'default'


def _get_font(name, height):
    """Load font from file."""
    try:
        return get_data(FONT_PATTERN, path=FONT_DIR, name=name, height=height)
    except ResourceFailed as e:
        logging.debug('Failed to load %d-pixel font `%s`: %s', height, name, e)


def read_fonts(codepage_dict, font_families):
    """Load font typefaces."""
    # default font is fallback
    font_families = list(font_families) + [_DEFAULT_NAME]
    # load the graphics fonts, including the 8-pixel RAM font
    # use set() for speed - lookup is O(1) rather than O(n) for list
    unicode_needed = set(itervalues(codepage_dict))
    # break up any grapheme clusters and add components to set of needed glyphs
    unicode_needed |= set(c for cluster in unicode_needed if len(cluster) > 1 for c in cluster)
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
        _height: load_hex(_font_file, _height, unicode_needed)
        for _height, _font_file in iteritems(font_files)
        if _font_file
    }
    return uc_fonts


def load_hex(hex_resources, height, all_needed):
    """Load a set of overlaying unifont .hex files."""
    fontdict = {}
    # get elements of codepoint sequences in case we need to combine glyphs
    elements = set.union(*(set(unicodedata.normalize('NFD', _c)) for _c in all_needed))
    all_needed = set(all_needed).union(elements)
    # transform the (smaller) set of needed chars into sequences for comparison
    # rather than the (larger) set of available sequences into chars
    needed_sequences = set(b','.join(b'%04X' % ord(_c) for _c in _s) for _s in all_needed)
    missing = set(all_needed)
    for hexres in reversed(hex_resources):
        if hexres is None:
            continue
        missing = _get_glyphs_from_hex(height, hexres, fontdict, missing, needed_sequences)
    missing = _combine_glyphs(height, fontdict, missing)
    # fill missing with nulls
    fontdict.update({_u: b'\0' * height for _u in missing})
    # char 0 should always be defined and empty
    fontdict[u'\0'] = b'\0' * height
    missing -= {u'\0'}
    # warn if we miss needed glyphs
    _warn_missing(height, missing)
    return fontdict


def _get_glyphs_from_hex(height, hexres, fontdict, missing, needed_sequences):
    for line in hexres.splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[:1] == b'#'):
            continue
        # strip off comments
        # split unicodepoint and hex string (max 32 chars)
        ucs_str, fonthex = line.split(b':')
        # get rid of spaces
        ucs_str = b''.join(ucs_str.split()).upper()
        # skip grapheme clusters we won't need
        if ucs_str not in needed_sequences:
            continue
        # remove from needed list
        needed_sequences -= {ucs_str}
        ucs_sequence = ucs_str.split(b',')
        fonthex = fonthex.split(b'#')[0].strip()
        # extract codepoint and hex string;
        # discard anything following whitespace; ignore malformed lines
        try:
            # construct grapheme cluster
            c = u''.join(unichr(int(_ucshex.strip(), 16)) for _ucshex in ucs_sequence)
            # skip chars we already have
            if (c in fontdict):
                continue
            # cut to required font size
            if len(fonthex) < 64:
                # 8xN glyph
                fonthex = fonthex[:2*height]
            else:
                # 16x16 glyph
                fonthex = fonthex[:4*height]
            fontdict[c] = binascii.unhexlify(fonthex)
        except Exception as e:
            logging.warning('Could not parse line in font file: %s: %s', repr(line), e)
        # remove newly found char
        # stop if we have all we need
        missing -= {c}
        if not missing:
            break
    return missing


def _combine_glyphs(height, fontdict, missing):
    """Fix missing grapheme clusters by combining components."""
    success = set()
    for cluster in missing:
        if cluster not in fontdict:
            # fully decompose the grapheme cluster
            decomposed = unicodedata.normalize('NFD', cluster)
            # try to combine grapheme clusters first
            if len(decomposed) > 1:
                # combine strings
                clusterglyph = bytearray(height)
                try:
                    for c in decomposed:
                        for y, row in enumerate(iterchar(fontdict[c])):
                            clusterglyph[y] |= ord(row)
                except KeyError as e:
                    logging.debug(
                        '%d-pixel font: Could not combine grapheme cluster %s, missing u+%04x [%s]',
                        height, cluster, ord(c), c
                    )
                fontdict[cluster] = bytes(clusterglyph)
                success.add(cluster)
    return missing - success


def _warn_missing(height, missing, max_warnings=5):
    """Warn if we miss needed glyphs."""
    warnings = 0
    for u in missing:
        warnings += 1
        sequence = ','.join('u+%04x' % ord(_c) for _c in u)
        logging.debug('Code point sequence %s not represented in %d-pixel font', sequence, height)
        if warnings == max_warnings:
            logging.debug('Further code point warnings suppressed.')
            break
