"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .loadhex import FONTS, read_fonts
from .loaducp import CODEPAGES, read_codepage
from .resources import PROGRAMS, read_program_file
