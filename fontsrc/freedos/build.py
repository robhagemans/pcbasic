#!/usr/bin/env python2

# build HEX font file from FreeDOS CPIDOS font


import os
import sys
import zipfile
import subprocess

# tools

def load_codepage(name):
    """ Load codepage to Unicode table. """
    cp_to_unicode = {}
    f = open(name, 'rb')
    for line in f:
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == '#'):
            continue
        # split unicodepoint and hex string
        splitline = line.split(':')
        # ignore malformed lines
        if len(splitline) < 2:
            continue
        # extract codepage point
        cp_point = splitline[0].strip().decode('hex')
        # extract unicode point
        ucs_point = int('0x' + splitline[1].split()[0].strip(), 16)
        cp_to_unicode[cp_point] = unichr(ucs_point)
    # fill up any undefined 1-byte codepoints
    for c in range(256):
        if chr(c) not in cp_to_unicode:
            cp_to_unicode[chr(c)] = u'\0'
    return cp_to_unicode


def chars_to_uint(c):
    return ord(c[0]) + ord(c[1])*0x100

def chars_to_ulong(c):
    return ord(c[0]) + ord(c[1])*0x100 + ord(c[2])*0x10000 + ord(c[3])*0x1000000

def read_codepage_header(cpi):
    size = chars_to_uint(cpi.read(2))
    chars_to_ulong(cpi.read(4)) # offset to next header, ignore this and assume header - page - header - page etc.
    cpi.read(2) # device_type
    cpi.read(8) # device name
    codepage = chars_to_uint(cpi.read(2))
    cpi.read(6) # reserved
    cpi.read(size-24) # pointer to CPIInfoHeader or 0
    return codepage

def read_font_header(cpi):
    # skip version number
    cpi.read(2)
    num_fonts = chars_to_uint(cpi.read(2))
    chars_to_uint(cpi.read(2))  # size
    return num_fonts

def load_cpi_font(cpi):
    height = ord(cpi.read(1))
    width = ord(cpi.read(1))
    cpi.read(2)
    num_chars = chars_to_uint(cpi.read(2))
    font = []
    for _ in range(num_chars):
        lines = cpi.read(height*(width//8))    # we assume width==8
        font += [lines]
    return height, font

def save_rom_font(font, out_name):
    out = open(out_name, 'wb')
    for glyph in font:
        out.write(glyph)

def write_hex(outfile, font, unitbl):
    with open(outfile, 'w') as of:
        for i, f in enumerate(font):
            of.write(hexline(ord(unitbl[chr(i)]), f))

def hexline(cp, glyph):
    s = glyph.encode('hex').upper()
    tohex = s + '0'*(32-len(s))
    return "%04X:%s\n" % (cp, tohex)

def add_to_multidict(mdict, key, value):
    try:
        mdict[key].add(value)
    except KeyError:
        mdict[key] = set([value])


fdzip = 'cpidos30.zip'
ucp_loc = 'codepage/'
cpi_prefix = 'BIN/'
cpi_names = ['ega.cpx'] + ['ega%d.cpx'% i for i in range(2, 19)]


def main():
    try:
        os.mkdir('work')
    except OSError:
        pass
    os.chdir('work')
    try:
        os.mkdir('hex')
    except OSError:
        pass
    try:
        os.mkdir('rom')
    except OSError:
        pass

    # unpack zipfile
    pack = zipfile.ZipFile('../' + fdzip, 'r')
    for name in cpi_names:
        pack.extract(cpi_prefix + name)
        subprocess.call(['upx', '-d', cpi_prefix + name])

    # retrieve forced choices
    forced = {}
    multidict = {8: {}, 14: {}, 16: {}}
    dropped = {8: {}, 14: {}, 16: {}}
    with open('../choices', 'r') as f:
        for line in f:
            if line and line[0] in ('#', '\n'):
                continue
            codepoint, codepagestr = line.strip('\n').split(':', 1)
            ucs = unichr(int(codepoint, 16))
            codepage = codepagestr.split(':')
            forced[ucs] = (int(codepage[0]), codepage[1] if codepage[1:] else None)
    # load CPIs and add to dictionary
    for cpi_name in cpi_names:
        print
        print cpi_name
        cpi = open(cpi_prefix + cpi_name, 'rb')
        # 23-byte header
        cpi.read(23)
        # get number codepages in this file
        num = chars_to_uint(cpi.read(2))
        for _ in range(num):
            codepage = read_codepage_header(cpi)
            num_fonts = read_font_header(cpi)
            fonts = {}
            print '[', codepage, ']',
            for _ in range(num_fonts):
                height, font = load_cpi_font(cpi)
                print height,
                # save intermediate ROM font
                save_rom_font(font, 'rom/%s_%d_%02d.fnt' % (cpi_name, codepage, height))
                try:
                    unitbl = load_codepage(os.path.join('..', ucp_loc, str(codepage)+'.ucp'))
                except Exception as e:
                    print codepage, height, e
                else:
                    for key, value in unitbl.iteritems():
                        unikey = unitbl[key]
                        glyph = font[ord(key)]
                        if (unikey in forced and
                                    (codepage, cpi_name) != forced[unikey] and
                                    (codepage, None) != forced[unikey]):
                            # do not add forced chars
                            #print "dropping", hex(ord(unikey)), codepage, cpi_name, repr(forced[unikey])
                            add_to_multidict(dropped[height], unikey, glyph)
                        else:
                            add_to_multidict(multidict[height], unikey, glyph)
                    # save intermediate HEX
                    write_hex('hex/%s_%d_%02d.hex' % (cpi_name, codepage, height), font, unitbl)
            print
    for height in (8, 14, 16):
        # write out all except pua
        with open('base_%02d.hex' % height, 'w') as f:
            # header
            with open ('../header.txt', 'r') as h:
                for line in h:
                    f.write(line)
            for unicp in range(0xe000) + range(0xf900, 0x10000):
                try:
                    for glyph in multidict[height][unichr(unicp)]:
                        f.write(hexline(unicp, glyph))
                except KeyError:
                    pass
        # write out pua
        with open('pua_%02d.hex' % height, 'w') as f:
            for unicp in range(0xe000, 0xf900):
                try:
                    for glyph in multidict[height][unichr(unicp)]:
                        f.write(hexline(unicp, glyph))
                except KeyError:
                    pass
        # write out dropped glyphs
        with open('dropped_%02d.hex' % height, 'w') as f:
            for unicp, glyphset in dropped[height].iteritems():
                for glyph in glyphset:
                    # only output what differs from base
                    if unicp not in multidict[height] or glyph not in multidict[height][unicp]:
                        f.write(hexline(ord(unicp), glyph))

main()
