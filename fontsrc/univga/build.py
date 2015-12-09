#!/usr/bin/env python2

import os
import string
import tarfile

bdf_name = 'uni_vga/u_vga16.bdf'
unizip = 'uni-vga.tgz'

infile = tarfile.open(unizip, 'r:gz').extractfile(bdf_name)

header = 'header.txt'
hex_name = 'univga_16.hex'
with open(hex_name, 'w') as outfile:
    with open(header, 'r') as h:
        for line in h:
            outfile.write(line)

    for line in infile:
        if not line:
            continue
        if line[:8] == 'ENCODING':
            outfile.write('\n%04X:' % int(line[8:]))
        if len(line) == 3 and line[0] in string.hexdigits and line[1] in string.hexdigits and line[2] == '\n':
            outfile.write(line[:2])
    outfile.write('\n')
infile.close()
