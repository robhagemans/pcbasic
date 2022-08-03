"""
PC-BASIC - application data package
Fonts, codepages, bundled programs and application branding

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import json as _json

from ..compat import resources as _resources

from .programs import PROGRAMS, read_program_file
from .fonts import FONTS, read_fonts
from .codepages import CODEPAGES, read_codepage

ICON = tuple(_json.loads(_resources.read_binary(__package__, 'icon.json')))
