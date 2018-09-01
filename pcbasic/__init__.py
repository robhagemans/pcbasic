"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os as _os

# __path__ hack to ensure os.chdir does not break intra-package imports
# which they do because the package __path__ is given relative to cwd
# at least if run with python -m package
__path__ = [_os.path.abspath(_e) for _e in __path__]

from .metadata import VERSION as __version__
from .basic.api import Session, codepage, font
from .main import run, main
