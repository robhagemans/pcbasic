#
# PC-BASIC 3.23 - backend_pygame.py
#
# Font handling 
# 
# (c) 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import logging
import plat

font_dir = os.path.join(plat.basepath, 'font') 

def font_filename(name, height):
    """ Return name_height.hex if filename exists in current path, else font_dir/name_height.hex. """
    name = '%s_%02d.hex' % (name, height)
    if not os.path.exists(name):
        # if not found in current dir, try in font directory
        name = os.path.join(font_dir, name)
    return name    

def load(families, height, codepage_dict):
    """ Load the specified codepage from a unifont .hex file. Codepage should be a CP-to-UTF8 dict. """
    names = reversed([ font_filename(name, height) for name in families ])
    cp_reverse = dict((reversed(item) for item in codepage_dict.items()))
    fontfiles = [ open(name, 'rb') for name in names if os.path.exists(name) ]
    if len(fontfiles) == 0:
        logging.warning('Could not read font file for height %d', height)
        return None
    fontdict = {}
    for fontfile in fontfiles:
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
            try:
                codepoint = unichr(int('0x' + splitline[0].strip(), 16)).encode('utf-8')
                # skip chars we won't need 
                if (codepoint in fontdict) or (codepoint not in cp_reverse):
                    continue
                string = splitline[1].strip().split()[0].decode('hex')
                # string must be 32-byte or 16-byte
                if len(string) not in (16, 32):
                    raise ValueError
                fontdict[codepoint] = string            
            except ValueError:
                logging.warning('Could not parse line in font file: %s', repr(line))    
    # char 0 should always be empty
    return dict([ ('\0', '\0'*16) if c == '\0' else (c, fontdict[codepage_dict[c]]) for c in codepage_dict ])



