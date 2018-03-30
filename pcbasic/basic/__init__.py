"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .api import Session
from ..metadata import VERSION as __version__
from .debug import DebugSession
from .base.error import *
from .base import signals, scancode, eascii
