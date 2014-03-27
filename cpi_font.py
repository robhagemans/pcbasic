#
# PC-BASIC 3.23 - cpi_font.py
#
# Read .CPI font files
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# CPI file documentation:
# http://www.win.tue.nl/~aeb/linux/kbd/font-formats-3.html

# CPI files retrieved from the FreeDOS project CPI pack at http://www.fdos.org/kernel/cpi/


import os

def chars_to_uint(c):
    return ord(c[0]) + ord(c[1])*0x100
def chars_to_ulong(c):
    return ord(c[0]) + ord(c[1])*0x100 + ord(c[2])*0x10000 + ord(c[3])*0x1000000

def load_codepage():
    cpifile = 'ega.cpi'
    path = os.path.dirname(os.path.realpath(__file__))
    cpi = open(os.path.join(path, cpifile), 'rb')
    # 23-byte header
    cpi.read(23)
    # get number codepages in this file
    num = chars_to_uint(cpi.read(2))
    codepage = read_codepage_header(cpi)
    num_fonts = read_font_header(cpi)
    fonts = {}
    for _ in range(num_fonts):
        height, font = load_font(cpi)
        fonts[height] = font
    return fonts
    
def read_codepage_header(cpi):
    size = chars_to_uint(cpi.read(2))
    next = chars_to_ulong(cpi.read(4)) # offset to next header, ignore this and assume header - page - header - page etc.
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
    
def load_font(cpi):   
    height = ord(cpi.read(1))
    width = ord(cpi.read(1))
    cpi.read(2)
    num_chars = chars_to_uint(cpi.read(2))
    font = []
    for _ in range(num_chars):
        lines = ''.join(cpi.read(height*(width//8)))    # we assume width==8
        font += [lines]
    return height, font


    


