#!/usr/bin/env python3

import tarfile
from io import TextIOWrapper
from itertools import chain

UNIFONT = 'unifont-13.0.03.tar.gz'
LOC = 'unifont-13.0.03/font/plane00/'
HEXFILES = ('spaces.hex', 'unifont-base.hex', 'hangul-syllables.hex', 'wqy.hex', 'thaana.hex')
HEADER = 'header.txt'
OUTPUT = 'unifont_16.hex'

# remove nonprinting characters in unifont-base.hex
NONPRINTING = tuple(f'{_c:04X}' for _c in chain(range(0x20), range(0x7f, 0xa0)))

# concatenate header and extracted hex files
with open(OUTPUT, 'w') as outfile:

    with open(HEADER) as header:
        outfile.write(header.read())

    unizip = tarfile.open(UNIFONT, 'r:gz')
    for name in HEXFILES:
        with TextIOWrapper(unizip.extractfile(LOC + name)) as hexfile:
            for line in hexfile:
                if not line[:4] in NONPRINTING:
                    outfile.write(line)
