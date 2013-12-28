#
# PC-BASIC 3.23 - cpi_font.py
#
# Read .CPI font files
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# CPI file documentation:
# http://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html

# CPI files retrieved from the FreeDOS project CPI pack at http://www.fdos.org/kernel/cpi/
# EGA.CPI copyright notice:
#   Copyright (C) 1993-1996 by kostis@acm.org (Kosta Kostis)
#   This program may be used free of charge at your own risk.


import os

def chars_to_uint(c):
    return ord(c[0]) + ord(c[1])*0x100


def load_codepage():
    path = os.path.dirname(os.path.realpath(__file__))
    cpi = open (os.path.join(path,'ega.cpi'),'rb')
    
    # skip general header
    cpi.read(53)
    # skip version number
    cpi.read(2)
    num_fonts = chars_to_uint(cpi.read(2))
    
    chars_to_uint(cpi.read(2))  # size
    
    fonts= []
    # for each font:
    for font in range(num_fonts):
        height = ord(cpi.read(1))
        width = ord(cpi.read(1))
        cpi.read(2)
        num_chars = chars_to_uint(cpi.read(2))
        fonts += [[]]
            
        for _ in range(num_chars):
            lines = ''.join(cpi.read(height*(width//8)))    # we assume width==8
            fonts[font] += [lines]

    return fonts        


