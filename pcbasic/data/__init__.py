"""
PC-BASIC - application data package
Fonts, codepages, bundled programs and application branding

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .resources import PROGRAMS, read_program_file, get_data, ResourceFailed
from .loadhex import FONTS, read_fonts
from .loaducp import CODEPAGES, read_codepage
