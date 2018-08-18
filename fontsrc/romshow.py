#!/usr/bin/python
import sys
import os
from font_tools import *

name = sys.argv[1]
size = os.path.getsize(name)
height = size // 256
num_chars, width = 256, 8
show_width = 16

def main():
    if len(sys.argv) > 2:
        cp_to_unicode = load_codepage(sys.argv[2])
    else:
        cp_to_unicode = dict(enumerate(cp437))
    font = load_rom_font(name, height, width)
    font_show(font, height, cp_to_unicode, show_width)

main()
