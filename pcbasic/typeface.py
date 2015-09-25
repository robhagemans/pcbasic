"""
PC-BASIC - typeface.py
Font handling

(c) 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
import logging

import numpy

import plat
import unicodepage


def font_filename(name, height, ext='hex'):
    """ Return name_height.hex if filename exists in current path, else font_dir/name_height.hex. """
    name = '%s_%02d.%s' % (name, height, ext)
    if not os.path.exists(name):
        # if not found in current dir, try in font directory
        name = os.path.join(plat.font_dir, name)
    return name

def load(families, height, codepage_dict, nowarn=False):
    """ Load the specified fonts for a given CP-to-UTF8 codepage. """
    names = [ font_filename(name, height) for name in families ]
    fontfiles = [ open(name, 'rb') for name in reversed(names) if os.path.exists(name) ]
    if len(fontfiles) == 0:
        if not nowarn:
            logging.warning('Could not read font file for height %d', height)
        return None
    fontdict = load_hex(fontfiles, height, codepage_dict)
    for f in fontfiles:
        f.close()
    return build_codepage_font(fontdict, codepage_dict)

def load_hex(fontfiles, height, codepage_dict):
    """ Load a set of overlaying unifont .hex files. """
    fontdict = {}
    # use set() for speed - lookup is O(1) rather than O(n) for list
    codepoints_needed = set(codepage_dict.values())
    for fontfile in fontfiles:
        for line in fontfile:
            # ignore empty lines and comment lines (first char is #)
            if (not line) or (line[0] == '#'):
                continue
            # split unicodepoint and hex string (max 32 chars)
            ucshex = line[0:4]
            fonthex = line[5:69]
            # extract codepoint and hex string;
            # discard anything following whitespace; ignore malformed lines
            try:
                codepoint = int(ucshex, 16)
                # skip chars we won't need
                if codepoint not in codepoints_needed:
                    continue
                # skip chars we already have
                if (codepoint in fontdict):
                    continue
                # string must be 32-byte or 16-byte; cut to required font size
                if len(fonthex) < 64:
                    fonthex = fonthex[:32]
                if len(fonthex) < 32:
                    raise ValueError
                fontdict[codepoint] = fonthex.decode('hex')
            except Exception as e:
                logging.warning('Could not parse line in font file: %s', repr(line))
    return fontdict

def build_codepage_font(fontdict, codepage_dict):
    """ Extract the glyphs for a given codepage from a unicode font. """
    font = {}
    warnings = 0
    for ucs in codepage_dict:
        u = codepage_dict[ucs]
        try:
            font[ucs] = fontdict[u]
        except KeyError:
            warnings += 1
            if warnings <= 3:
                logging.debug('Codepoint %x [%s] not represented in font',
                              u, unicode(u).encode('utf-8'))
            if warnings == 3:
                logging.debug('Further codepoint warnings suppressed.')
    # char 0 should always be empty
    font['\0'] = '\0'*16
    return font

def fixfont(height, font, codepage_dict, font16):
    """ Fill in missing codepoints in font using 16-line font or blanks. """
    if not font:
        font = {}
    if height == 16:
        for c in codepage_dict:
            if c not in font:
                font[c] = ('\0'*16 if len(c) == 1 else '\0'*32)
    else:
        for c in codepage_dict:
            if c not in font:
                if font16 and c in font16:
                    font[c] = glyph_16_to(height, font16[c])
                else:
                    font[c] = ('\0'*height if len(c) == 1 else '\0'*2*height)
    return font

def glyph_16_to(height, glyph16):
    """ Crudely convert 16-line character to n-line character by taking out top and bottom. """
    s16 = list(glyph16)
    start = (16 - height) // 2
    if len(s16) == 16:
        return ''.join([ s16[i] for i in range(start, 16-start) ])
    else:
        return ''.join([ s16[i] for i in range(start*2, 32-start*2) ])


def load_fonts(font_families, heights_needed):
    """ Load font typefaces. """
    fonts = {}
    for height in reversed(sorted(heights_needed)):
        if height in fonts:
            # already force loaded
            continue
        # load a Unifont .hex font and take the codepage subset
        fonts[height] = load(font_families, height,
                                      unicodepage.cp_to_unicodepoint)
        # fix missing code points font based on 16-line font
        if 16 not in fonts:
            # if available, load the 16-pixel font unrequested
            font_16 = load(font_families, 16,
                                    unicodepage.cp_to_unicodepoint, nowarn=True)
            if font_16:
                fonts[16] = font_16
        if 16 in fonts and fonts[16]:
            fixfont(height, fonts[height],
                             unicodepage.cp_to_unicodepoint, fonts[16])
    return fonts


# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
carry_col_9 = [chr(c) for c in range(0xb0, 0xdf+1)]
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
carry_row_9 = [chr(c) for c in range(0xb0, 0xdf+1)]

#if numpy:
def build_glyph(c, font_face, req_width, req_height):
    """ Build a sprite for the given character glyph. """
    # req_width can be 8, 9 (SBCS), 16, 18 (DBCS) only
    try:
        face = font_face[c]
    except KeyError:
        logging.debug('Byte sequence %s not represented in codepage, replace with blank glyph.', repr(c))
        # codepoint 0 must be blank by our definitions
        face = font_face['\0']
        c = '\0'
    code_height = 8 if req_height == 9 else req_height
    glyph_width, glyph_height = 8*len(face)//code_height, req_height
    if req_width <= glyph_width + 2:
        # allow for 9-pixel widths (18-pixel dwidths) without scaling
        glyph_width = req_width
    elif glyph_width < req_width:
        u = unicodepage.cp_to_utf8[c]
        logging.debug('Incorrect glyph width for %s [%s, code point %x].', repr(c), u, ord(u.decode('utf-8')))
    glyph = numpy.zeros((glyph_height, glyph_width), dtype=bool)
    for yy in range(code_height):
        for half in range(glyph_width//8):
            line = ord(face[yy*(glyph_width//8)+half])
            for xx in range(8):
                if (line >> (7-xx)) & 1 == 1:
                    glyph[yy][half*8 + xx] = 1
        # MDA/VGA 9-bit characters
        if c in carry_col_9 and glyph_width == 9:
            if line & 1 == 1:
                glyph[yy][8] = 1
    # tandy 9-bit high characters
    if c in carry_row_9 and glyph_height == 9:
        line = ord(face[7*(glyph_width//8)])
        for xx in range(8):
            if (line >> (7-xx)) & 1 == 1:
                glyph[8][xx] = 1
    if req_width > glyph_width:
        # i.e. we need a double-width char
        # in this case, req_width == 2*glyph_width
        glyph = glyph.repeat(2, axis=1)
    return glyph
