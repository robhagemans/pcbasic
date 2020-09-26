#!/usr/bin/env python3

import os
import string
import tarfile
from io import TextIOWrapper

import monobit

bdf_name = 'uni_vga/u_vga16.bdf'
unizip = 'uni-vga.tgz'

header = 'header.txt'
hex_name = 'univga_16.hex'

with tarfile.open(unizip, 'r:gz').extractfile(bdf_name) as infile:
    uni_vga = monobit.load(TextIOWrapper(infile), format='bdf')
    with open(hex_name, 'wb') as outfile:
        with open(header, 'rb') as h:
            for line in h:
                outfile.write(line)
        outfile.write(b'\n')
        uni_vga.save(outfile, format='hex')
