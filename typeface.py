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

def font_filename(name, height):
    """ Return name_height.hex if filename exists in current path, else font_dir/name_height.hex. """
    name = '%s_%02d.hex' % (name, height)
    if not os.path.exists(name):
        # if not found in current dir, try in font directory
        name = os.path.join(plat.font_dir, name)
    return name    

def load(families, height, codepage_dict):
    """ Load the specified codepage from a unifont .hex file. Codepage should be a CP-to-UTF8 dict. """
    names = [ font_filename(name, height) for name in families ]
    cp_reverse = dict((reversed(item) for item in codepage_dict.items()))
    fontfiles = [ open(name, 'rb') for name in reversed(names) if os.path.exists(name) ]
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
                # string must be 32-byte or 16-byte; cut to required font size
                if len(string) == 32:
                    # dbcs glyph
                    fontdict[codepoint] = string[:2*height]
                elif len(string) == 16:
                    # sbcs glyph
                    fontdict[codepoint] = string[:height]
                else:        
                    raise ValueError
            except ValueError:
                logging.warning('Could not parse line in font file: %s', repr(line))    
    # char 0 should always be empty
    fontdict['\0'] = '\0'*16
    font = {}    
    warnings = 0
    for c in codepage_dict:
        u = codepage_dict[c]
        try:
            font[c] = fontdict[u]
        except KeyError:
            warnings += 1
            if warnings <= 3:
                logging.debug('Codepoint %x [%s] not represented in font for height %d.', ord(u.decode('utf-8')), u, height)
            if warnings == 3:
                logging.debug('Further codepoint warnings suppressed.')
    return font

def fixfont(height, font, codepage_dict, font16):
    """ Fill in missing codepoints in font using 16-line font or blanks. """
    if height not in font or font[height] == None:
        font[height] = []
    if height == 16:            
        for c in codepage_dict:
            if c not in font:
                font[c] = ('\0'*16 if len(c) == 1 else '\0'*32)
    else:
        for c in codepage_dict:
            if c not in font:
                font[c] = glyph_16_to(height, font16[c])
    return font
            
def glyph_16_to(height, glyph16):
    """ Crudely convert 16-line character to n-line character by taking out top and bottom. """
    s16 = list(glyph16)
    start = (16 - height) // 2
    if len(s16) == 16:
        return ''.join([ s16[i] for i in range(start, 16-start) ])
    else:
        return ''.join([ s16[i] for i in range(start*2, 32-start*2) ])

