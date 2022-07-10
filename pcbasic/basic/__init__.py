"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .data import NAME, VERSION, LONG_VERSION, AUTHOR, COPYRIGHT, ICON
from .api import Session, codepage, font
from .debug import DebugSession
from .base.error import *
from .base import signals, scancode, eascii

__version__ = VERSION
