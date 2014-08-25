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

def font_filename(name):
    """ Return _name_ if filename exists in current path, else font_dir/name. """
    if not os.path.exists(name):
        # if not found in current dir, try in font directory
        path = plat.basepath
        name = os.path.join(font_dir, name)
    return name    

def load(name):
    """ Load and return a half-width single-byte rom font. Return None if not loaded. """
    return load_generic(name, 256, 8)

def load_generic(name, num_chars, width):
    """ Load and return a rom font of _num_chars_ characters of _width_ bytes. Return None if not loaded. """
    name = font_filename(name)
    try:
        size = os.path.getsize(name)
        height = size/num_chars/(width//8)        
        fontfile = open(name, 'rb')
        font = []
        for _ in range(num_chars):
            lines = fontfile.read(height*(width//8))
            font += [lines]
        return font
    except (IOError, OSError):
        logging.warning('Could not read font file %s', name)
        return None

def load_unicode(name, codepage):
    """ Load the specified unicodepage from a unifont .hex file """
    fontdict = load_hex(name)
    return [ fontdict[codepage[c]] for c in codepage ]
    
def load_hex(name):
    """ Load a unifont .hex font. """
    name = font_filename(name)
    try:
        fontfile = open(name, 'rb')
        unifont = fontfile.lines()
        fontdict = {}
        for line in unifont:
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
                codepoint = int('0x' + splitline[0].strip(), 16)
                string = splitline[1].strip().split(' ')
                # string must be 16-byte or 32-byte
                if len(string) not in (16, 32):
                    raise ValueError
                fontdict[codepoint] = string            
            except ValueError:
                logging.warning('Could not parse line in font file %s: %s', name, repr(line))    
        return fontdict        
    except (IOError, OSError):
        logging.warning('Could not read font file %s', name)
        return None




