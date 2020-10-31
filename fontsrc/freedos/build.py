#!/usr/bin/env python3

# build HEX font file from FreeDOS CPIDOS font


import os
import sys
import zipfile
import subprocess
import logging
from unicodedata import normalize, name
from collections import defaultdict
from itertools import chain
from urllib import request

import monobit

logging.basicConfig(level=logging.INFO)

CPIDOS_URL = 'http://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/dos/cpi/cpidos30.zip'
FDZIP = 'cpidos30.zip'
CODEPAGE_DIR = 'codepage/'
CPI_DIR = 'BIN/'
CPI_NAMES = ['ega.cpx'] + [f'ega{_i}.cpx' for _i in range(2, 19)]
HEADER = 'header.txt'
CHOICES = 'choices'
UNIVGA = '../univga/univga_16.hex'
SIZES = (8, 14, 16)
COMPONENTS = {
    8: ('combining_08.yaff', 'additions_08.yaff', 'more_08.yaff',),
    14: ('combining_14.yaff', 'additions_14.yaff',),
    16: ('combining.yaff', 'additions.yaff', 'precomposed.yaff', 'composed_16.yaff'),
}

# don't use the glyphs from freedos, use uni-vga instead
FREEDOS_DROP = (
    '\u0256', # U+0256 LATIN SMALL LETTER D WITH TAIL
    '\u0257', # U+0257 LATIN SMALL LETTER D WITH HOOK
)

FREEDOS_COPY = {
    # U+2107 EULER CONSTANT <-- U+0190 LATIN CAPITAL LETTER OPEN E
    '\u2107': '\u0190',
    # U+01A9 LATIN CAPITAL LETTER ESH <-- U+03A3 GREEK CAPITAL LETTER SIGMA
    '\u01a9': '\u03a3',
    # U+03DC GREEK LETTER DIGAMMA
    '\u03dc': 'F',
    # U+03F2 GREEK LUNATE SIGMA SYMBOL
    '\u03f2': 'c',
    # U+03F3 GREEK LETTER YOT
    '\u03f3': 'j',
    # U+0400 CYRILLIC CAPITAL LETTER IE WITH GRAVE
    # U+00C8 LATIN CAPITAL LETTER E WITH GRAVE
    '\u0400': '\u00c8',
    # U+0450 CYRILLIC SMALL LETTER IE WITH GRAVE
    # U+00E8 LATIN SMALL LETTER E WITH GRAVE
    '\u0450': '\u00e8',
    # U+0589 ARMENIAN FULL STOP
    '\u0589': ':',
}

FREEDOS_MIRROR = {
    # U+01B8 LATIN CAPITAL LETTER EZH REVERSED <-- U+01B7 LATIN CAPITAL LETTER EZH
    '\u01b8' : '\u01b7',
    # U+01B9 LATIN SMALL LETTER EZH REVERSED <-- U+0292 LATIN SMALL LETTER EZH
    '\u01b9': '\u0292',
    # U+0295 LATIN LETTER PHARYNGEAL VOICED FRICATIVE <-- U+0294 LATIN LETTER GLOTTAL STOP
    '\u0295': '\u0294',
    # U+02A2 LATIN LETTER REVERSED GLOTTAL STOP WITH STROKE <-- U+02A1 LATIN LETTER GLOTTAL STOP WITH STROKE
    '\u02a2': '\u02a1',
    # U+01A7 LATIN CAPITAL LETTER TONE TWO <-- LATIN CAPITAL LETTER S
    '\u01a7': 'S',
    # U+01A8 LATIN SMALL LETTER TONE TWO <-- LATIN SMALL LETTER S
    '\u01a8': 's',
    # U+0258 LATIN SMALL LETTER REVERSED E <-- LATIN SMALL LETTER E
    '\u0258': 'e',
    # U+027F LATIN SMALL LETTER REVERSED R WITH FISHHOOK
    # U+027E LATIN SMALL LETTER R WITH FISHHOOK
    '\u027f': '\u027e',
    # U+025E LATIN SMALL LETTER CLOSED REVERSED OPEN E
    # U+029A LATIN SMALL LETTER CLOSED OPEN E
    '\u025e': '\u029a',
    # U+058E LEFT-FACING ARMENIAN ETERNITY SIGN
    # U+058D RIGHT-FACING ARMENIAN ETERNITY SIGN
    '\u058e': '\u058d',
}

FREEDOS_FLIP = {
    # U+01BE LATIN LETTER INVERTED GLOTTAL STOP WITH STROKE <-- U+02A1 LATIN LETTER GLOTTAL STOP WITH STROKE
    '\u01be': '\u02a1',
    # U+0296 LATIN LETTER INVERTED GLOTTAL STOP <-- U+0294 LATIN LETTER GLOTTAL STOP
    '\u0296': '\u0294',
    # U+2127 INVERTED OHM SIGN <-- U+03A9 GREEK CAPITAL LETTER OMEGA
    '\u2127': '\u03a9',
    # U+0280 LATIN LETTER SMALL CAPITAL R
    # U+0281 LATIN LETTER SMALL CAPITAL INVERTED R
    '\u0281': '\u0280',
}


FREEDOS_TURN = {
    # should have descender
    # U+018D LATIN SMALL LETTER TURNED DELTA <-- U+1E9F LATIN SMALL LETTER DELTA
    '\u018d': '\u1e9f',
    # U+0250 LATIN SMALL LETTER TURNED A <-- LATIN SMALL LETTER A
    '\u0250': 'a',
    # U+0252 LATIN SMALL LETTER TURNED ALPHA <-- U+0251 LATIN SMALL LETTER ALPHA
    '\u0252': '\u0251',
    # U+0265 LATIN SMALL LETTER TURNED H
    '\u0265': 'h',
    # U+026F LATIN SMALL LETTER TURNED M
    '\u026f': 'm',
    # U+0279 LATIN SMALL LETTER TURNED R
    '\u0279': 'r',
    # U+027A LATIN SMALL LETTER TURNED R WITH LONG LEG
    # should have descender
    # U+027C LATIN SMALL LETTER R WITH LONG LEG
    '\u027a': '\u027c',
    # U+0287 LATIN SMALL LETTER TURNED T
    '\u0287': 't',
    # U+028D LATIN SMALL LETTER TURNED W
    '\u028d': 'w',
    # U+028E LATIN SMALL LETTER TURNED Y
    '\u028e': 'y',
    # should have descender
    # U+029E LATIN SMALL LETTER TURNED K
    '\u029e': 'k',
}

UNIVGA_COPY = {
    '\u2011': '\u2010', # U+2011 NON-BREAKING HYPHEN <-- U+2010 HYPHEN
}

# don't rebaseline box-drawing and vertically continuous characters
UNIVGA_UNSHIFTED = chain(
    range(0x2308, 0x230c), range(0x2320, 0x23b4), range(0x23b7, 0x23ba),
    range(0x2500, 0x2600),
    # not a box drawing glyph but fits with 058d if unshifted
    range(0x058e, 0x058f),
)
# exclude glyphs for nonprinting characters
UNIVGA_NONPRINTING = chain(
    range(0x0000, 0x0020), range(0x007f, 0x00a0),
    range(0x2000, 0x2010), range(0x2011, 0x2012), range(0xfeff, 0xff00),
)

# wrong code points in uni-vga
UNIVGA_REPLACE = {
    '\u208f': '\u2099', # U+2099 LATIN SUBSCRIPT SMALL LETTER N
    '\u0530': '\u058e', # U+058E LEFT-FACING ARMENIAN ETERNITY SIGN
    # or just mirror 058d...
}

def fullname(char):
    """Unicode codepoint and name."""
    return ', '.join(f'U+{ord(_c):04X} {name(_c)}' for _c in char)


def precompose(font, max_glyphs):
    """Create composed glyphs from combining up to `max_glyphs` glyphs."""
    composed_glyphs = {}
    codepoints = set(_glyph.char for _glyph in font.glyphs if _glyph.char)
    # run through all of plane 0
    for cp in range(0x10000):
        char = chr(cp)
        if char not in codepoints:
            # first see if an equivalent precomposed char is already there
            equiv = normalize('NFC', char)
            if equiv in codepoints:
                logging.info(f'Assigning {fullname(char)} == {fullname(equiv)}.')
                font = font.with_glyph(font.get_glyph(equiv).set_annotations(char=char))
            else:
                decomp = normalize('NFD', char)
                if len(decomp) <= max_glyphs and all(c in codepoints for c in decomp):
                    logging.info(f'Composing {fullname(char)} as {fullname(decomp)}.')
                    glyphs = (font.get_glyph(c) for c in decomp)
                    composed = monobit.Glyph.superimpose(glyphs).set_annotations(char=char)
                    font = font.with_glyph(composed)
    return font


def main():

    # register custom FreeDOS codepages
    for filename in os.listdir(CODEPAGE_DIR):
        cp_name, ext = os.path.splitext(os.path.basename(filename))
        if ext == '.ucp':
            monobit.Codepage.override(f'cp{cp_name}', f'{os.getcwd()}/{CODEPAGE_DIR}/{filename}')

    try:
        os.mkdir('work')
    except OSError:
        pass
    try:
        os.mkdir('work/yaff')
    except OSError:
        pass

    # read header
    logging.info('Processing header')
    with open(HEADER, 'r') as header:
        comments = tuple(_line[2:].rstrip() for _line in header)

    # create empty fonts with header
    final_font = {
        size: monobit.font.Font(comments=comments).set_encoding('unicode')
        for size in SIZES
    }

    # obtain original zip file
    logging.info('Downloading CPIDOS.')
    request.urlretrieve(CPIDOS_URL, FDZIP)

    # unpack zipfile
    os.chdir('work')
    pack = zipfile.ZipFile('../' + FDZIP, 'r')
    # extract cpi files from compressed cpx files
    for name in CPI_NAMES:
        pack.extract(CPI_DIR + name)
        subprocess.call(['upx', '-d', CPI_DIR + name])
    os.chdir('..')

    # load CPIs and add to dictionary
    freedos_fonts = {_size: {} for _size in SIZES}
    for cpi_name in CPI_NAMES:
        logging.info(f'Reading {cpi_name}')
        cpi = monobit.load(f'work/{CPI_DIR}{cpi_name}', format='cpi')
        for font in cpi:
            codepage = font.encoding # always starts with `cp`
            height = font.bounding_box[1]
            # save intermediate file
            monobit.save(
                font.add_glyph_names(),
                f'work/yaff/{cpi_name}_{codepage}_{font.pixel_size:02d}.yaff'
            )
            freedos_fonts[font.pixel_size][(cpi_name, codepage)] = font.set_encoding('unicode')

    # retrieve preferred picks from choices file
    logging.info('Processing choices')
    choices = defaultdict(list)
    with open(CHOICES, 'r') as f:
        for line in f:
            if line and line[0] in ('#', '\n'):
                continue
            codepoint, codepagestr = line.strip('\n').split(':', 1)
            codepage_info = codepagestr.split(':') # e.g. 852:ega.cpx
            if len(codepage_info) > 1:
                codepage, cpi_name = codepage_info[:2]
            else:
                codepage, cpi_name = codepage_info[0], None
            choices[(cpi_name, f'cp{codepage}')].append(chr(int(codepoint, 16)))

    # merge locally drawn glyphs
    for size in SIZES:
        for yaff in COMPONENTS[size]:
            logging.info(f'Merging {yaff}.')
            final_font[size] = final_font[size].merged_with(monobit.load(yaff))

    # merge preferred picks from FreeDOS fonts
    logging.info('Add freedos preferred glyphs')
    for size, fontdict in freedos_fonts.items():
        for (cpi_name_0, codepage_0), labels in choices.items():
            for (cpi_name_1, codepage_1), font in fontdict.items():
                if (
                        (codepage_0 == codepage_1)
                        and (cpi_name_0 is None or cpi_name_0 == cpi_name_1)
                    ):
                    final_font[size] = final_font[size].merged_with(font.subset(labels))

    # merge other fonts
    logging.info('Add remaining freedos glyphs')
    for size, fontdict in freedos_fonts.items():
        for font in fontdict.values():
            final_font[size] = final_font[size].merged_with(font)

    # assign length-1 equivalents
    logging.info('Assign canonical equivalents.')
    for size in final_font.keys():
        final_font[size] = precompose(final_font[size], max_glyphs=1)

    # drop glyphs with better alternatives in uni-vga
    final_font[16] = final_font[16].without(FREEDOS_DROP)

    # copy glyphs (canonical equivalents have been covered before)
    for size in final_font.keys():
        for copy, orig in FREEDOS_COPY.items():
            try:
                final_font[size] = final_font[size].with_glyph(
                    final_font[size].get_glyph(orig).set_annotations(char=copy)
                )
            except KeyError as e:
                logging.warning(e)
        for copy, orig in FREEDOS_MIRROR.items():
            try:
                orig = final_font[size].get_glyph(orig)
            except KeyError as e:
                logging.warning(e)
            else:
                offsets = orig.ink_offsets
                mirrored = orig.crop(*offsets).mirror().expand(*offsets)
                final_font[size] = final_font[size].with_glyph(mirrored.set_annotations(char=copy))
        for copy, orig in FREEDOS_FLIP.items():
            try:
                orig = final_font[size].get_glyph(orig)
            except KeyError as e:
                logging.warning(e)
            else:
                offsets = orig.ink_offsets
                flipped = orig.crop(*offsets).flip().expand(*offsets)
                final_font[size] = final_font[size].with_glyph(flipped.set_annotations(char=copy))
        for copy, orig in FREEDOS_TURN.items():
            try:
                orig = final_font[size].get_glyph(orig)
            except KeyError as e:
                logging.warning(e)
            else:
                offsets = orig.ink_offsets
                flipped = orig.crop(*offsets).flip().mirror().expand(*offsets)
                final_font[size] = final_font[size].with_glyph(flipped.set_annotations(char=copy))

    # read univga
    univga_orig = monobit.load(UNIVGA)
    # replace code points where necessary
    univga = univga_orig.without(UNIVGA_REPLACE.keys())
    for orig, repl in UNIVGA_REPLACE.items():
        univga = univga.with_glyph(univga_orig.get_glyph(orig).set_annotations(char=repl))

    logging.info('Add uni-vga box-drawing glyphs.')
    box_glyphs = univga.subset(chr(_code) for _code in UNIVGA_UNSHIFTED)
    final_font[16] = final_font[16].merged_with(box_glyphs)

    # shift uni-vga baseline down by one
    logging.info('Add remaining uni-vga glyphs after rebaselining.')
    univga_rebaselined = univga.without(chr(_code) for _code in UNIVGA_NONPRINTING)
    univga_rebaselined = univga_rebaselined.expand(top=1).crop(bottom=1)
    final_font[16] = final_font[16].merged_with(univga_rebaselined)

    # copy glyphs from uni-vga
    for copy, orig in UNIVGA_COPY.items():
        final_font[16] = final_font[16].with_glyph(
            final_font[size].get_glyph(orig).set_annotations(char=copy)
        )

    # exclude personal use area code points
    logging.info('Removing private use area')
    pua_keys = set(chr(_code) for _code in range(0xe000, 0xf900))
    pua_font = {_size: _font.subset(pua_keys) for _size, _font in final_font.items()}
    for size, font in pua_font.items():
        monobit.save(font, f'work/pua_{size:02d}.hex', format='hext')
    final_font = {_size: _font.without(pua_keys) for _size, _font in final_font.items()}

    logging.info('Sorting glyphs')
    for size in final_font.keys():
        # first take the 437 subset
        # note this'll be the Freedos 437 as we overrode it
        keys437 = list(monobit.Codepage('cp437')._mapping.values())
        font437 = final_font[size].subset(keys437)
        sortedfont = monobit.font.Font(sorted(
            (_glyph for _glyph in final_font[size].glyphs),
            key=lambda _g: (_g.char or '')
        ))
        final_font[size] = font437.merged_with(sortedfont)

    # output
    logging.info('Writing output')
    for size, font in final_font.items():
        monobit.save(font.drop_comments(), f'freedos_{size:02d}.hex', format='hext')

    composed = {
        size: precompose(font, max_glyphs=4)
                .without(font.get_chars()).drop_comments().add_glyph_names()
        for size, font in final_font.items()
    }

    for size, font in composed.items():
        monobit.save(font, f'autocomposed_{size:02d}.yaff')


main()
