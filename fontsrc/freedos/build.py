#!/usr/bin/env python3

# build HEX font file from FreeDOS CPIDOS font


import os
import sys
import zipfile
import subprocess
import logging
from collections import defaultdict

import monobit

logging.basicConfig(level=logging.INFO)

FDZIP = 'cpidos30.zip'
CODEPAGE_DIR = 'codepage/'
CPI_DIR = 'BIN/'
CPI_NAMES = ['ega.cpx'] + [f'ega{_i}.cpx' for _i in range(2, 19)]
HEADER = 'header.txt'
CHOICES = 'choices'

def main():

    # register custom FreeDOS codepages
    for filename in os.listdir(CODEPAGE_DIR):
        cp_name, _ = os.path.splitext(os.path.basename(filename))
        monobit.font.Codepage.override(f'cp{cp_name}', f'{os.getcwd()}/{CODEPAGE_DIR}/{filename}')

    try:
        os.mkdir('work')
    except OSError:
        pass
    try:
        os.mkdir('work/hex')
    except OSError:
        pass

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
            monobit.Typeface([font]).save(
                f'work/hex/{cpi_name}_{codepage}_{font.pixel_size:02d}.hext'
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

    # merge preferred picks
    logging.info('Merging choices')
    final_font = {}
    for size, fontdict in fonts.items():
        final_font[size] = monobit.font.Font(
            [], comments=comments, properties=dict(encoding='unicode')
        )
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

    # exclude personal use area code points
    logging.info('Removing private use area')
    pua_keys = set(f'u+{_code:04x}' for _code in range(0xe000, 0xf900))
    pua_font = {_size: _font.subset(pua_keys) for _size, _font in final_font.items()}
    for size, font in pua_font.items():
        monobit.Typeface([font]).save(f'work/pua_{size:02d}.hex', format='hext')
    final_font = {_size: _font.without(pua_keys) for _size, _font in final_font.items()}

    # output
    logging.info('Writing output')
    for size, font in final_font.items():
        monobit.Typeface([font]).save(f'freedos_{size:02d}.hex', format='hext')


main()
