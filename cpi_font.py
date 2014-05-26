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

# CPI files retrieved from the FreeDOS project CPIDOS at http://www.fdos.org/kernel/cpi/
# which carries the following copyright notice:
#   CPIDOS is distributed under the GNU-GPL 2.0 license or later.
#   CPIDOS and KPDOS are developed and copyright by Henrique Peron.
#   This file copyright (c) 2011
#   Henrique Peron

import os

def load_codepage(number=437):
    found = False
    for cpifile in cpi_files:
        if number in cpi_files[cpifile]:
            found = True
            break
    if not found:
        import logging
        logging.warning('Could not find EGA font for codepage %d. Falling back to codepage 437 (US).\n', number)
        cpifile = 'ega.cpi'
        number = 437        
    path = os.path.dirname(os.path.realpath(__file__))
    cpi = open(os.path.join(path, 'cpi', cpifile), 'rb')
    # 23-byte header
    cpi.read(23)
    # get number codepages in this file
    num = chars_to_uint(cpi.read(2))
    for _ in range(num):
        codepage = read_codepage_header(cpi)
        num_fonts = read_font_header(cpi)
        fonts = {}
        for _ in range(num_fonts):
            height, font = load_font(cpi)
            fonts[height] = font
        if codepage == number:    
            return fonts
    return None
    
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

# load a 256-character 8x8 font dump with no headers
def load_rom_font(name, height):
    try:
        fontfile = open(name, 'rb')
        font = []
        num_chars, width = 256, 8
        for _ in range(num_chars):
            lines = ''.join(fontfile.read(height*(width//8)))
            font += [lines]
        return font
    except IOError:
        return None
        
cpi_files = {
        'ega.cpi': (    
            437, # United States
            850, # Latin-1 (Western European)
            852, # Latin-2 (Central European) (2)
            853, # Latin-3 (Southern European)
            857, # Latin-5 (2)(3)
            858, # Latin-1 with Euro (1)
            ),
        'ega2.cpi': (
             775, #Latin-7 (Baltic Rim)
             859, #Latin-9
            1116, #Estonian
            1117, #Latvian
            1118, #Lithuanian (*)
            1119, #Cyrillic Russian and Lithuanian (*)
            ),
        'ega3.cpi': (
            771, #Cyrillic Russian and Lithuanian (KBL)
            772, #Cyrillic Russian and Lithuanian (**)
            808, #Cyrillic Russian with Euro (*)
            855, #Cyrillic South Slavic
            866, #Cyrillic Russian
            872, #Cyrillic South Slavic with Euro (*)
            ),
        'ega4.cpi': (
              848, #Cyrillic Ukrainian with Euro (*)
              849, #Cyrillic Belarusian with Euro (*)
             1125, #Cyrillic Ukrainian
             1131, #Cyrillic Belarusian
             3012, #Cyrillic Russian and Latvian ("RusLat")
            30010, #Cyrillic Gagauz and Moldovan
            ),
        'ega5.cpi': (
            113, #Yugoslavian Latin
            737, #Greek-2
            851, #Greek (old codepage)
            852, #Latin-2
            858, #Multilingual Latin-1 with Euro
            869, #Greek (*)
            ),
        'ega6.cpi': (
              899, #Armenian
            30008, #Cyrillic Abkhaz and Ossetian
            58210, #Cyrillic Russian and Azeri
            59829, #Georgian
            60258, #Cyrillic Russian and Latin Azeri
            60853, #Georgian with capital letters
            ),
        'ega7.cpi': (
            30011, #Cyrillic Russian Southern District
            30013, #Cyrillic Volga District, #Turkic languages
            30014, #Cyrillic Volga District, #Finno-ugric languages
            30017, #Cyrillic Northwestern District
            30018, #Cyrillic Russian and Latin Tatar
            30019, #Cyrillic Russian and Latin Chechen
            ),
        'ega8.cpi': (
            770, #Baltic
            773, #Latin-7 (old standard)
            774, #Lithuanian
            775, #Latin-7
            777, #Accented Lithuanian (old)
            778, #Accented Lithuanian
            ),
        'ega9.cpi': (
            858, #Latin-1 with Euro
            860, #Portuguese
            861, #Icelandic
            863, #Canadian French
            865, #Nordic
            867, #Czech Kamenicky
            ),
        'ega10.cpi': (
              667, #Polish
              668, #Polish (polish letters on cp852 codepoints)
              790, #Polish Mazovia
              852, #Latin-2
              991, #Polish Mazovia with Zloty sign
             3845, #Hungarian
            ),
        'ega11.cpi': (
              858, #Latin-1 with Euro
            30000, #Saami
            30001, #Celtic
            30004, #Greenlandic
            30007, #Latin
            30009, #Romani
            ),
        'ega12.cpi': (
              852, #Latin-2
              858, #Latin-1 with Euro
            30003, #Latin American
            30029, #Mexican
            30030, #Mexican II
            58335, #Kashubian
            ),
        'ega13.cpi': (
              852, #Latin-2
              895, #Czech Kamenicky (*)
            30002, #Cyrillic Tajik
            58152, #Cyrillic Kazakh with Euro
            59234, #Cyrillic Tatar
            62306, #Cyrillic Uzbek
            ),
        'ega14.cpi': (
            30006, #Vietnamese
            30012, #Cyrillic Russian Siberian and Far Eastern Districts
            30015, #Cyrillic Khanty
            30016, #Cyrillic Mansi
            30020, #Low saxon and frisian
            30021, #Oceania
            ),
        'ega15.cpi': (
            30023, #Southern Africa
            30024, #Northern and Eastern Africa
            30025, #Western Africa
            30026, #Central Africa
            30027, #Beninese
            30028, #Nigerien
            ),
        'ega16.cpi': (
              858, #Latin-1 with Euro
             3021, #Cyrillic MIK Bulgarian
            30005, #Nigerian
            30022, #Canadian First Nations
            30031, #Latin-4 (Northern European)
            30032, #Latin-6
            ),
        'ega17.cpi': (
              862, #Hebrew
              864, #Arabic
            30034, #Cherokee
            30033, #Crimean Tatar with Hryvnia
            30039, #Cyrillic Ukrainian with Hryvnia
            30040, #Cyrillic Russian with Hryvnia
            ),
        'ega18.cpi': (
              856, #Hebrew II
             3846, #Turkish
             3848, #Brazilian ABICOMP
            ),
    }

