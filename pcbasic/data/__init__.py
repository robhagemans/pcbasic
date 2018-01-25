"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkg_resources
import logging

from ..basic.codepage import PRINTABLE_ASCII


CODEPAGE_DIR = u'codepages'
PROGRAM_DIR = u'programs'
FONT_DIR = u'fonts'

CODEPAGES = [name.split(u'.', 1)[0] for name in pkg_resources.resource_listdir(__name__, CODEPAGE_DIR) if name.lower().endswith(u'.ucp')]
PROGRAMS = (name for name in pkg_resources.resource_listdir(__name__, PROGRAM_DIR) if name.lower().endswith(u'.bas'))
FONTS = [name.split(u'_', 1)[0] for name in pkg_resources.resource_listdir(__name__, FONT_DIR) if name.lower().endswith(u'.hex')]


###############################################################################
# exceptions

class ResourceFailed(Exception):
    """Failed to load resource"""

    def __init__(self, spec=u'resource', name=u''):
        self._message = u'Failed to load {0} {1}'.format(spec, name)

    def __str__(self):
        return self._message


###############################################################################
# resource readers

def get_data(name):
    """Wrapper for resource_string."""
    try:
        # this should return None if not available, I thought, but it doesn't
        return pkg_resources.resource_string(__name__, name)
    except EnvironmentError:
        return None

def read_font_files(families, height):
    """Retrieve contents of font files."""
    return [
        get_data(u'%s/%s_%02d.hex' % (FONT_DIR, name, height))
        for name in families]

def read_codepage_file(codepage_name):
    """Retrieve contents of codepage file."""
    resource = get_data('%s/%s.ucp' % (CODEPAGE_DIR, codepage_name))
    if resource is None:
        raise ResourceFailed(u'codepage', codepage_name)
    return resource

def read_program_file(name):
    """Read a bundled BASIC program file."""
    program = ('%s/%s' % (PROGRAM_DIR, name))
    if program is None:
        raise ResourceFailed(u'bundled program', name)
    return program


###############################################################################
# file parsers

def read_codepage(codepage_name):
    """Read a codepage file and convert to codepage dict."""
    codepage = {}
    for line in read_codepage_file(codepage_name).splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == '#'):
            continue
        # strip off comments; split unicodepoint and hex string
        splitline = line.split('#')[0].split(':')
        # ignore malformed lines
        if len(splitline) < 2:
            continue
        try:
            # extract codepage point
            cp_point = splitline[0].strip().decode('hex')
            # allow sequence of code points separated by commas
            grapheme_cluster = u''.join(unichr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(','))
            codepage[cp_point] = grapheme_cluster
        except ValueError:
            logging.warning('Could not parse line in codepage file: %s', repr(line))
    return codepage

###############################################################################

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
        fonts[height] = FontLoader(height).load_hex(
                read_font_files(font_families, height),
                unicode_needed, substitutes, warn=warn)
        # fix missing code points font based on 16-line font
        if fonts[16]:
            fonts[height].fix_missing(unicode_needed, fonts[16])
    if 8 in fonts:
        fonts[9] = fonts[8]
    return {height: font.fontdict for height, font in fonts.iteritems()}


class FontLoader(object):
    """Single-height bitfont."""

    def __init__(self, height):
        """Initialise the font."""
        self.height = height
        self.fontdict = {}

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
