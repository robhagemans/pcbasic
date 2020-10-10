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
COMPONENTS = ('combining.yaff', 'additions.yaff', 'precomposed.yaff')
UNIVGA = '../univga/univga_16.hex'

# don't rebaseline box-drawing and vertically continuous characters
UNIVGA_UNSHIFTED = chain(
    range(0x2308, 0x230c), range(0x2320, 0x23b4), range(0x23b7, 0x23ba),
    range(0x2500, 0x2600),
)
# exclude glyphs for nonprinting characters
UNIVGA_NONPRINTING = chain(
    range(0x0000, 0x0020), range(0x007f, 0x00a0),
    range(0x2000, 0x2010), range(0x2011, 0x2012), range(0xfeff, 0xff00),
)


def fullname(char):
    """Unicode codepoint and name."""
    return ','.join(f'U+{ord(_c):04X} {name(_c)}' for _c in char)


def precompose(font, max_glyphs):
    """Create composed glyphs from combining up to `max_glyphs` glyphs."""
    composed_glyphs = {}
    codepoints = [cp.unicode for cp, _ in font.iter_unicode()]
    # run through all of plane 0
    for cp in range(0x10000):
        char = chr(cp)
        if char not in codepoints:
            # first see if an equivalent precomposed char is already there
            equiv = normalize('NFC', char)
            if equiv in codepoints:
                logging.info(f'Assigning {fullname(char)} == {fullname(equiv)}.')
                font = font.with_glyph(
                    font.get_char(equiv), f'u+{cp:04x}'
                )
            else:
                decomp = normalize('NFD', char)
                if len(decomp) <= max_glyphs and all(c in codepoints for c in decomp):
                    logging.info(f'Composing {fullname(char)} as {fullname(decomp)}.')
                    glyphs = (font.get_char(c) for c in decomp)
                    composed = monobit.glyph.Glyph.superimpose(glyphs)
                    font = font.with_glyph(composed, f'u+{cp:04x}')
    return font


def main():

    # register custom FreeDOS codepages
    for filename in os.listdir(CODEPAGE_DIR):
        cp_name, ext = os.path.splitext(os.path.basename(filename))
        if ext == '.ucp':
            monobit.font.Codepage.override(f'cp{cp_name}', f'{os.getcwd()}/{CODEPAGE_DIR}/{filename}')

    try:
        os.mkdir('work')
    except OSError:
        pass
    try:
        os.mkdir('work/yaff')
    except OSError:
        pass

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
    fonts = {8: {}, 14: {}, 16: {}}
    for cpi_name in CPI_NAMES:
        logging.info(f'Reading {cpi_name}')
        cpi = monobit.load(f'work/{CPI_DIR}{cpi_name}', format='cpi')
        for font in cpi:
            codepage = font.encoding # always starts with `cp`
            height = font.bounding_box[1]
            # save intermediate file
            monobit.Typeface([font.add_glyph_names()]).save(
                f'work/yaff/{cpi_name}_{codepage}_{font.pixel_size:02d}.yaff'
            )
            fonts[font.pixel_size][(cpi_name, codepage)] = font

    # retrieve preferred picks from choices file
    logging.info('Processing choices')
    choices = defaultdict(list)
    with open(CHOICES, 'r') as f:
        for line in f:
            if line and line[0] in ('#', '\n'):
                continue
            codepoint, codepagestr = line.strip('\n').split(':', 1)
            label = f'u+{codepoint}'.lower()
            codepage_info = codepagestr.split(':') # e.g. 852:ega.cpx
            if len(codepage_info) > 1:
                codepage, cpi_name = codepage_info[:2]
            else:
                codepage, cpi_name = codepage_info[0], None
            choices[(cpi_name, f'cp{codepage}')].append(label)

    # read header
    logging.info('Processing header')
    with open(HEADER, 'r') as header:
        comments = tuple(_line[2:].rstrip() for _line in header)

    final_font = {}
    for size in fonts.keys():
        final_font[size] = monobit.font.Font([], comments=comments)
        if size == 16:
            for yaff in COMPONENTS:
                # merging additions
                logging.info(f'Merging {yaff}.')
                final_font[size] = final_font[size].merged_with(monobit.load(yaff)[0])

    # merge preferred picks
    logging.info('Merging choices')
    for size, fontdict in fonts.items():
        for (cpi_name_0, codepage_0), labels in choices.items():
            for (cpi_name_1, codepage_1), font in fontdict.items():
                if (
                        (codepage_0 == codepage_1)
                        and (cpi_name_0 is None or cpi_name_0 == cpi_name_1)
                    ):
                    final_font[size] = final_font[size].merged_with(font.subset(labels))

    # merge other fonts
    logging.info('Merging remaining fonts')
    for size, fontdict in fonts.items():
        for font in fontdict.values():
            final_font[size] = final_font[size].merged_with(font)

    # assign length-1 equivalents
    logging.info('Assign canonical equivalents.')
    for size in final_font.keys():
        final_font[size] = precompose(final_font[size], max_glyphs=1)

    # read univga
    logging.info('Add uni-vga box-drawing glyphs.')
    univga = monobit.load(UNIVGA)[0]
    box_glyphs = univga.subset(f'u+{_code:04x}' for _code in UNIVGA_UNSHIFTED)
    final_font[16] = final_font[16].merged_with(box_glyphs)

    # shift uni-vga baseline down by one
    logging.info('Add remaining uni-vga glyphs after rebaselining.')
    univga_rebaselined = univga.without(f'u+{_code:04x}' for _code in UNIVGA_NONPRINTING)
    univga_rebaselined = univga_rebaselined.expand(top=1).crop(bottom=1)
    final_font[16] = final_font[16].merged_with(univga_rebaselined)

    # exclude personal use area code points
    logging.info('Removing private use area')
    pua_keys = set(f'u+{_code:04x}' for _code in range(0xe000, 0xf900))
    pua_font = {_size: _font.subset(pua_keys) for _size, _font in final_font.items()}
    for size, font in pua_font.items():
        monobit.Typeface([font]).save(f'work/pua_{size:02d}.hex', format='hext')
    final_font = {_size: _font.without(pua_keys) for _size, _font in final_font.items()}

    logging.info('Sorting glyphs')
    for size in final_font.keys():
        # first take the 437 subset
        # note this'll be the Freedos 437 as we overrode it
        keys437 = list(monobit.font.Codepage('cp437')._mapping.values())
        glyphs437 = [
            final_font[size].get_char(key)
            for key in keys437
        ]
        labels437 = {
            monobit.font.Label.from_unicode(_c): _i
            for _i, _c in enumerate(keys437)
        }
        font437 = monobit.font.Font(
            glyphs437, labels437, final_font[size]._comments
        )
        sorteddict = dict(sorted(
            (str(unilabel), glyph)
            for unilabel, glyph in final_font[size].iter_unicode()
        ))
        labeldict = {
            label: index
            for index, label in enumerate(sorteddict.keys())
        }
        sortedfont = monobit.font.Font(sorteddict.values(), labeldict)
        final_font[size] = font437.merged_with(sortedfont)

    # output
    logging.info('Writing output')
    for size, font in final_font.items():
        monobit.Typeface([font.drop_comments()]).save(f'freedos_{size:02d}.hex', format='hext')


main()
