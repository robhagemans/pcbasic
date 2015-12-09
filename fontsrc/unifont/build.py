#!/usr/bin/env python2
import tarfile

unifont = 'unifont-8.0.01.tar.gz'
loc = 'unifont-8.0.01/font/plane00/'
hexfiles = (loc+'spaces.hex', loc+'unifont-base.hex', loc+'hangul-syllables.hex', loc+'wqy.hex')
unizip = tarfile.open(unifont, 'r:gz')

output = 'unifont_16.hex'

# concatenate extracted hex files
with open(output, 'w') as f:
    with open('header.txt') as g:
        f.write(g.read())
    for name in hexfiles:
        z = unizip.extractfile(name)
        f.write(z.read())
        z.close()


