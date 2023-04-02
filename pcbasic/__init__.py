"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# compatibility pre-init: ensures package __path__ is absolute
from . import compat

from .basic import __version__
from .basic import NAME, VERSION, AUTHOR, COPYRIGHT
from .basic import Session, codepage, font
from .main import main, script_entry_point_guard
