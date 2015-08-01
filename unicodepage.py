"""
PC-BASIC - unicodepage.py
Codepage conversions

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import config
import state
import logging
import os
import plat

########################################
# codepage loader

# is the current codepage a double-byte codepage?
dbcs = False

def prepare():
    """ Initialise unicodepage module. """
    global box_protext
    codepage = config.get('codepage')
    if not codepage:
        codepage = '437'
    box_protect = not config.get('nobox')
    state.console_state.codepage = codepage
    load_codepage(codepage)

def load_codepage(codepage_name):
    """ Load codepage to Unicode table. """
    global cp_to_utf8, utf8_to_cp, cp_to_unicodepoint
    global lead, trail, dbcs, dbcs_num_chars, box_left, box_right
    name = os.path.join(plat.encoding_dir, codepage_name + '.ucp')
    # lead and trail bytes
    lead = set()
    trail = set()
    box_left = [set(), set()]
    box_right = [set(), set()]
    cp_to_utf8 = {}
    cp_to_unicodepoint = {}
    dbcs_num_chars = 0
    try:
        with open(name, 'rb') as f:
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
                    cp_to_unicodepoint[cp_point] = ucs_point
                    cp_to_utf8[cp_point] = unichr(ucs_point).encode('utf-8')
                    # track lead and trail bytes
                    if len(cp_point) == 2:
                        lead.add(cp_point[0])
                        trail.add(cp_point[1])
                        dbcs_num_chars += 1
                    # track box drawing chars
                    else:
                        for i in (0, 1):
                            if ucs_point in box_left_unicode[i]:
                                box_left[i].add(cp_point[0])
                            if ucs_point in box_right_unicode[i]:
                                box_right[i].add(cp_point[0])
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
            cp_to_unicodepoint[chr(c)] = 0
    utf8_to_cp = dict((reversed(item) for item in cp_to_utf8.items()))
    if dbcs_num_chars > 0:
        dbcs = True
    return codepage_name

########################################
# control character protection

# on the terminal, these values are not shown as special graphic chars but as their normal effect
# BEL, TAB, LF, HOME, CLS, CR, RIGHT, LEFT, UP, DOWN  (and not BACKSPACE)
control = ('\x07', '\x09', '\x0a', '\x0b', '\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')


########################################
# box drawing protection

# protect box drawing sequences under dbcs?
box_protect = True

# left-connecting box drawing chars [ single line, double line ]
box_left_unicode = [ (0x2500,), (0x2550,) ]

# right-connecting box drawing chars [ single line, double line ]
box_right_unicode = [ (0x2500,), (0x2550,) ]

def connects(c, d, bset):
    """ Return True if c and d connect according to box-drawing set bset. """
    return c in box_right[bset] and d in box_left[bset]

# left-connecting
## single line:
# 0x2500, 0x252c, 0x2534, 0x253c, 0x2510, 0x2518, 0x2524,
# mixed single / double
# 0x2556, 0x255c, 0x2562, 0x2565, 0x2568, 0x256b, 0x256e,
# dotted lines
# 0x2504, 0x2508, 0x254c,
# mixed thick / thin line
# 0x251a, 0x2526, 0x2527, 0x2528, 0x252e, 0x2530, 0x2532, 0x2536, 0x2538, 0x253a, 0x253e,
# 0x2540, 0x2541, 0x2542, 0x2544, 0x2546, 0x254a, 0x257c
# rounded corners and half-lines
# 0x256f, 0x2574,
## double line:
# 0x2550, 0x2566, 0x2569, 0x256c,0x2557, 0x255d, 0x2563,
# mixed single / double line
# 0x2555, 0x255b, 0x2561, 0x2564, 0x2567, 0x256a,

# right-connecting
# single line
## 0x2500, 0x252c, 0x2534, 0x253c,
## 0x250c, 0x2514, 0x251c,
# dotted
# 0x2504, 0x2508,
# mixed
# 0x2516, 0x251e, 0x251f, 0x2520, 0x252d,
# 0x2530, 0x2531, 0x2535, 0x2538, 0x2539, 0x253d,
# 0x2540, 0x2541, 0x2542, 0x2543, 0x2545, 0x2549, 0x254c,
# 0x2553, 0x2559, 0x255f, 0x2565, 0x2568, 0x256b, 0x256d, 0x2570, 0x2576, 0x257e
# double line
## 0x2550, 0x2566, 0x2569, 0x256c,
## 0x2554, 0x255a, 0x2560,
# 0x2552, 0x2558, 0x255e, 0x2564, 0x2567, 0x256a,


##################################################
# conversion


def split_utf8(s):
    """ Split UTF8 string into single-char byte sequences. """
    # decode and encode each char back
    try:
        return [c.encode('utf-8') for c in s.decode('utf-8')]
    except UnicodeDecodeError:
        # not valid UTF8, pass through raw.
        return list(s)

def from_utf8(c):
    """ Convert utf8 char sequence to codepage char sequence. """
    return utf8_to_cp[c]

def str_from_utf8(s):
    """ Convert utf8 string to codepage string. """
    chars, s = split_utf8(s), ''
    for c in chars:
        try:
            # try to codepage-encode the one-char UTF8 byte sequence
            s += from_utf8(c)
        except KeyError:
            # pass unknown sequences untranslated. this includes \r.
            s += c
    return s

class UTF8Converter(object):
    """ Buffered converter to UTF8 - supports DBCS and box-drawing protection. """

    def __init__(self, preserve_control=False, do_dbcs=None, protect_box=None):
        """ Initialise with empty buffer. """
        self.buf = ''
        self.preserve_control = preserve_control
        self.protect_box = protect_box
        self.dbcs = do_dbcs
        # set dbcs and box protection defaults according to global settings
        if protect_box is None:
            self.protect_box = box_protect
        if do_dbcs is None:
            self.dbcs = dbcs
        self.bset = -1
        self.last = ''

    def to_utf8(self, s):
        """ Process codepage string, returning utf8 string when ready. """
        if not self.dbcs:
            # stateless if not dbcs
            return ''.join([ (c if (self.preserve_control and c in control) else cp_to_utf8[c]) for c in s ])
        else:
            out = ''
            # remove any naked lead-byte first
            if self.buf:
                out += '\b'*len(self.buf)
            # process the string
            for c in s:
                out += self.process(c)
            # any naked lead-byte or boxable dbcs left will be printed (but don't flush buffers!)
            if self.buf:
                out += cp_to_utf8[self.buf]
            return out

    def flush(self, num=None):
        """ Empty buffer and return contents. """
        out = ''
        if num is None:
            num = len(self.buf)
        if self.buf:
            # can be one or two-byte sequence in self.buf
            out = cp_to_utf8[self.buf[:num]]
        self.buf = self.buf[num:]
        return out

    def process(self, c):
        """ Process a single char, returning UTF8 char sequences when ready """
        if not self.protect_box:
            return self.process_nobox(c)
        out = ''
        if self.preserve_control and c in control:
            # control char; flush buffer as SBCS and add control char unchanged
            out += self.flush() + c
            self.bset = -1
            self.last = ''
        elif self.bset == -1:
            if not self.buf:
                out += self.process_case0(c)
            elif len(self.buf) == 1:
                out += self.process_case1(c)
            elif len(self.buf) == 2:
                out += self.process_case2(c)
            else:
                # not allowed
                logging.debug('DBCS buffer corrupted: %d %s', self.bset, repr(self.buf))
        elif len(self.buf) == 2:
            out += self.process_case3(c)
        elif not self.buf:
            out += self.process_case4(c)
        else:
            # not allowed
            logging.debug('DBCS buffer corrupted: %d %s', self.bset, repr(self.buf))
        return out

    def process_nobox(self, c):
        """ Process a single char, no box drawing protection """
        out = ''
        if self.preserve_control and c in control:
            # control char; flush buffer as SBCS and add control char unchanged
            out += self.flush() + c
            return out
        elif self.buf:
            if c in trail:
                # add a DBCS character
                self.buf += c
                out += self.flush()
                return out
            else:
                # flush buffer
                out += self.flush()
        if c in lead:
            self.buf = c
        else:
            out += cp_to_utf8[c]
        return out

    def process_case0(self, c):
        """ Process a single char with box drawing protection; case 0, starting point """
        out = ''
        if c not in lead:
            out += cp_to_utf8[c]
            # goes to case 0
        else:
            self.buf += c
            # goes to case 1
        return out

    def process_case1(self, c):
        """ Process a single char with box drawing protection; case 1 """
        out = ''
        if c not in trail:
            out += self.flush() + cp_to_utf8[c]
            # goes to case 0
        else:
            for bset in (0, 1):
                if connects(self.buf, c, bset):
                    self.bset = bset
                    self.buf += c
                    break
                    # goes to case 3
            else:
                # no connection
                self.buf += c
                # goes to case 2
        return out

    def process_case2(self, c):
        """ Process a single char with box drawing protection; case 2 """
        out = ''
        if c not in lead:
            out += self.flush() + cp_to_utf8[c]
            # goes to case 0
        else:
            for bset in (0, 1):
                if connects(self.buf[-1], c, bset):
                    self.bset = bset
                    # take out only first byte
                    out += self.flush(1)
                    self.buf += c
                    break
                    # goes to case 3
            else:
                # no connection found
                out += self.flush()
                self.buf += c
                # goes to case 1
        return out

    def process_case3(self, c):
        """ Process a single char with box drawing protection; case 3 """
        out = ''
        if c not in lead:
            out += self.flush() + cp_to_utf8[c]
        elif connects(self.buf[-1], c, self.bset):
            self.last = self.buf[-1]
            # output box drawing
            out += self.flush(1) + self.flush(1) + cp_to_utf8[c]
            # goes to case 4
        else:
            out += self.flush()
            self.buf = c
            self.bset = -1
            # goes to case 1
        return out

    def process_case4(self, c):
        """ Process a single char with box drawing protection; case 4, continuing box drawing """
        out = ''
        if c not in lead:
            out += cp_to_utf8[c]
            # goes to case 0
        elif connects(self.last, c, self.bset):
            self.last = c
            out += cp_to_utf8[c]
            # goes to case 4
        else:
            self.buf += c
            self.bset = -1
            # goes to case 1
        return out

prepare()
