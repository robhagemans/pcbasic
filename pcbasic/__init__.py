"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# fix the package __path__
from .compat import make__path__absolute as _make_absolute
__path__ = _make_absolute(__path__)


from .basic import __version__
from .basic import NAME, VERSION, AUTHOR, COPYRIGHT
from .basic import Session, codepage, font
from .main import run, main
