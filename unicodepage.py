
# Codepage 437 to Unicode table 
# with Special Graphic Characters
# http://en.wikipedia.org/wiki/Code_page_437
# http://msdn.microsoft.com/en-us/library/cc195060.aspx
# http://msdn.microsoft.com/en-us/goglobal/cc305160

import logging
import os
import plat

# where to find unicode tables
encoding_dir = os.path.join(plat.basepath, 'encoding')

# on the terminal, these values are not shown as special graphic chars but as their normal effect
# BEL, TAB, LF, HOME, CLS, CR, RIGHT, LEFT, UP, DOWN  (and not BACKSPACE)
control = ('\x07', '\x09', '\x0a', '\x0b', '\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')

# left-connecting single-line box drawing chars
box0_left = (  
    u'\u2500', u'\u2504', u'\u2508',
    u'\u2510', u'\u2518', 
    u'\u2524', u'\u2526', u'\u2527', u'\u2528', u'\u252c', u'\u252e', 
    u'\u2530', u'\u2532', u'\u2534', u'\u2536', u'\u2538', u'\u253a', u'\u253c', u'\u253e',
    u'\u2540', u'\u2541', u'\u2542', u'\u2544', u'\u2546', u'\u254a', u'\u254c')

# right-connecting single-line box drawing chars
box0_right = ( 
    u'\u2500', u'\u2504', u'\u2508',
    u'\u2514', u'\u2516', u'\u251c', u'\u251e', u'\u251f',
    u'\u2520', u'\u252c', u'\u252d',
    u'\u2530', u'\u2531', u'\u2534', u'\u2535', u'\u2538', u'\u2539', u'\u253c', u'\u253d',
    u'\u2540', u'\u2541', u'\u2542', u'\u2543', u'\u2545', u'\u2549', u'\u254c')

# protect box drawing sequences under dbcs?
box_protect = True

# is the current codepage a double-byte codepage?
dbcs = False

def load_codepage(codepage_name):
    global cp_to_utf8, utf8_to_cp, lead, trail, dbcs, dbcs_num_chars
    # load double-byte unicode table
    name = os.path.join(encoding_dir, codepage_name + '.ucp')
    # lead and trail bytes
    lead = set()
    trail = set()
    cp_to_utf8 = {}
    dbcs_num_chars = 0
    try:
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
            try:
                # extract codepage point
                cp_point = splitline[0].strip().decode('hex')
                # extract unicode point
                ucs_point = int('0x' + splitline[1].split()[0].strip(), 16)
                cp_to_utf8[cp_point] = unichr(ucs_point).encode('utf-8')
                # track lead and trail bytes
                if len(cp_point) == 2:
                    lead.add(cp_point[0])
                    trail.add(cp_point[1])
                    dbcs_num_chars += 1
            except ValueError:
                logging.warning('Could not parse line in unicode mapping table: %s', repr(line))
    except IOError:
        if codepage_name == '437':
            logging.error('Could not load unicode mapping table for codepage 437.')
            return None
        else:
            logging.warning('Could not load unicode mapping table for codepage %s. Falling back to codepage 437.', codepage_name)
            return load_codepage('437')
    # fill up any undefined 1-byte codepoints
    for c in range(256):
        if chr(c) not in cp_to_utf8:
            cp_to_utf8[chr(c)] = '\0'
    utf8_to_cp = dict((reversed(item) for item in cp_to_utf8.items()))
    if dbcs_num_chars > 0:
        dbcs = True
    return codepage_name

# convert utf8 wchar to codepage char
def from_utf8(c):
    return utf8_to_cp[c]

# line buffer for conversion to UTF8 - supports DBCS
class UTF8Converter (object):
    def __init__(self):
        self.buf = ''

    # add chars to buffer
    def to_utf8(self, s, preserve_control=False):
        if not dbcs:
            # stateless if not dbcs
            return ''.join([ (c if (preserve_control and c in control) else cp_to_utf8[c]) for c in s ])
        else:
            out = ''
            if self.buf:
                # remove the naked lead-byte first
                out += '\b'
            for c in s:
                if preserve_control and c in control:
                    # control char; flush buffer as SBCS and add control char unchanged
                    if self.buf:
                        out += cp_to_utf8[self.buf]
                        self.buf = ''
                    out += c
                    continue
                elif self.buf:
                    if c in trail:
                        # add a DBCS character
                        out += cp_to_utf8[self.buf + c]
                        self.buf = ''
                        continue
                    else:
                        # flush buffer
                        out += cp_to_utf8[self.buf]
                        self.buf = ''
                if c in lead:
                    self.buf = c
                else:
                    out += cp_to_utf8[c]
            # any naked lead-byte left will be printed
            if self.buf:
                out += cp_to_utf8[self.buf]
            return out

