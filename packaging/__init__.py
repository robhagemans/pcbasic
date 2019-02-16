"""
PC-BASIC - packagig
Windows, MacOS, Linux packaging

(c) 2015--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

from .common import COMMANDS

if sys.platform == 'win32':
    from .windows import package
elif sys.platform == 'darwin':
    from .mac import package
else:
    from .linux import package
