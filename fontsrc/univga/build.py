#!/usr/bin/env python3

import os
import string
import tarfile
from io import TextIOWrapper
import logging
from urllib import request

import monobit


UNIVGA_URL = 'http://www.inp.nsk.su/~bolkhov/files/fonts/univga/uni-vga.tgz'
UNIVGA_ZIP = 'uni-vga.tgz'
UNIVGA_BDF = 'uni_vga/u_vga16.bdf'

HEADER = 'header.txt'
UNIVGA_HEX = 'univga_16.hex'


logging.basicConfig(level=logging.INFO)


# obtain original zip file
logging.info('Downloading Uni-VGA.')
request.urlretrieve(UNIVGA_URL, UNIVGA_ZIP)

with tarfile.open(UNIVGA_ZIP, 'r:gz').extractfile(UNIVGA_BDF) as infile:
    uni_vga = monobit.load(TextIOWrapper(infile), format='bdf')
    with open(UNIVGA_HEX, 'wb') as outfile:

        logging.info('Processing header')
        with open(HEADER, 'rb') as h:
            for line in h:
                outfile.write(line)
        outfile.write(b'\n')

        logging.info('Converting Uni-VGA to .hex format')
        uni_vga.save(outfile, format='hex')
