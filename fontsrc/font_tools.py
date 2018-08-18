import os
import sys
import binascii

cp437 = (
    u'\u0000\u263A\u263B\u2665\u2666\u2663\u2660\u2022\u25D8\u25CB\u25D9\u2642\u2640\u266A\u266B\u263C' +
    u'\u25BA\u25C4\u2195\u203C\u00B6\u00A7\u25AC\u21A8\u2191\u2193\u2192\u2190\u221F\u2194\u25B2\u25BC' +
    u'\u0020\u0021\u0022\u0023\u0024\u0025\u0026\u0027\u0028\u0029\u002A\u002B\u002C\u002D\u002E\u002F' +
    u'\u0030\u0031\u0032\u0033\u0034\u0035\u0036\u0037\u0038\u0039\u003A\u003B\u003C\u003D\u003E\u003F' +
    u'\u0040\u0041\u0042\u0043\u0044\u0045\u0046\u0047\u0048\u0049\u004A\u004B\u004C\u004D\u004E\u004F' +
    u'\u0050\u0051\u0052\u0053\u0054\u0055\u0056\u0057\u0058\u0059\u005A\u005B\u005C\u005D\u005E\u005F' +
    u'\u0060\u0061\u0062\u0063\u0064\u0065\u0066\u0067\u0068\u0069\u006A\u006B\u006C\u006D\u006E\u006F' +
    u'\u0070\u0071\u0072\u0073\u0074\u0075\u0076\u0077\u0078\u0079\u007A\u007B\u007C\u007D\u007E\u2302' +
    u'\u00c7\u00fc\u00e9\u00e2\u00e4\u00e0\u00e5\u00e7\u00ea\u00eb\u00e8\u00ef\u00ee\u00ec\u00c4\u00c5' +
    u'\u00c9\u00e6\u00c6\u00f4\u00f6\u00f2\u00fb\u00f9\u00ff\u00d6\u00dc\u00a2\u00a3\u00a5\u20a7\u0192' +
    u'\u00e1\u00ed\u00f3\u00fa\u00f1\u00d1\u00aa\u00ba\u00bf\u2310\u00ac\u00bd\u00bc\u00a1\u00ab\u00bb' +
    u'\u2591\u2592\u2593\u2502\u2524\u2561\u2562\u2556\u2555\u2563\u2551\u2557\u255d\u255c\u255b\u2510' +
    u'\u2514\u2534\u252c\u251c\u2500\u253c\u255e\u255f\u255a\u2554\u2569\u2566\u2560\u2550\u256c\u2567' +
    u'\u2568\u2564\u2565\u2559\u2558\u2552\u2553\u256b\u256a\u2518\u250c\u2588\u2584\u258c\u2590\u2580' +
    u'\u03b1\u00df\u0393\u03c0\u03a3\u03c3\u00b5\u03c4\u03a6\u0398\u03a9\u03b4\u221e\u03c6\u03b5\u2229' +
    u'\u2261\u00b1\u2265\u2264\u2320\u2321\u00f7\u2248\u00b0\u2219\u00b7\u221a\u207f\u00b2\u25a0\u00a0'
    )


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
        us = u''
        print splitline
        # extract codepage point
        cp_point = binascii.unhexlify(splitline[0].strip())
        for cps in splitline[1].split(','):
            # extract unicode point
            ucs_point = int('0x' + cps.split()[0].strip(), 16)
            us += unichr(ucs_point)
        cp_to_unicode[cp_point] = us
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

# load a 256-character 8xN font dump with no headers
def load_rom_font(name, height, width):
    try:
        fontfile = open(name, 'rb')
        font = []
        while True:
            lines = fontfile.read(height*(width//8))
            if not lines:
                break
            font += [lines]
        return font
    except IOError:
        return None
    finally:
        fontfile.close()

def load_hex_font(name, height, codepage_dict):
    """ Load the specified codepage from a unifont .hex file. Codepage should be a CP-to-UCS dict. """
    fontdict = load_hex_font_bare(name, height)
    font = {}
    for c in codepage_dict:
        u = codepage_dict[c]
        try:
            font[c] = fontdict[u]
        except KeyError:
            pass
    return font

def load_hex_font_bare(name, height):
    """ Load a unifont .hex file """
    fontdict = {}
    fontfile = open(name, 'rb')
    for line in fontfile:
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == '#'):
            continue
        # split unicodepoint and hex string
        splitline = line.split(':')
        # ignore malformed lines
        if len(splitline) < 2:
            continue
        # extract codepoint and hex string; discard anything following whitespace; ignore malformed lines
        codepoint = unichr(int('0x' + splitline[0].strip(), 16))
        # skip chars we won't need
        if (codepoint in fontdict):
            sys.stderr.write('Ignored repeated definition of code point %x\n' % ord(codepoint))
            continue
        string = binascii.unhexlify(splitline[1].strip().split()[0])
        # string must be 32-byte or 16-byte; cut to required font size
        if len(string) == 32:
            # dbcs glyph
            fontdict[codepoint] = string[:2*height]
        elif len(string) == 16:
            # sbcs glyph
            fontdict[codepoint] = string[:height]
        else:
            raise ValueError
    # char 0 should always be empty
    fontdict['\0'] = '\0'*16
    return fontdict


def font_show(font, height, cp_to_unicode, show_width):
    num_chars = len(cp_to_unicode)
    for i in range(0, num_chars, show_width):
        print
        numstr = ''
        for j in range(show_width):
            # add zero width space before to avoid combining marks with brackets
            ucs = u'\u200b' + cp_to_unicode[chr(i+j)]
            numstr += '%02x:[%s]   ' % (i+j, ucs.encode('utf-8'))
            #numstr += ','.join('%04x' % ord(c) for c in ucs)
        print numstr
        for y in range(height):
            lstr = ''
            for j in range(show_width):
                lstr += "{0:08b} ".format(ord(font[i+j][y])).replace('0', '.').replace('1', '#')
            print lstr

def print_hex(font, unitbl):
    for i, f in enumerate(font):
        s = binascii.hexlify(f).upper()
        tohex = s + '0'*(32-len(s))
        print "%04X:%s" % (ord(unitbl[chr(i)]), tohex)
