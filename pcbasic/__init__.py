"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# __path__ hack to ensure os.chdir does not break intra-package imports
# which they do because the package __path__ is given relative to cwd
# at least if run with python -m package
import os
__path__ = [os.path.abspath(e) for e in __path__]

from .basic import Session, metadata, __version__
from .main import main, run
