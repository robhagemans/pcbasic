
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
control = (
    '\x07', # BEL
    #'\x08',# BACKSPACE
    '\x09', # TAB 
    '\x0a', # LF
    '\x0b', # HOME
    '\x0c', # clear screen
    '\x0d', # CR
    '\x1c', # RIGHT
    '\x1d', # LEFT
    '\x1e', # UP
    '\x1f', # DOWN
    ) 

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
    utf8_to_cp = dict((reversed(item) for item in cp_to_utf8.items()))
    if dbcs_num_chars > 0:
        dbcs = True    
    return codepage_name  
    return lead.index(l)*len(trail)+trail.index(t)

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
        
