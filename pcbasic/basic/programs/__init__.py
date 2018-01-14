"""
PC-BASIC - programs package
Bundled BASIC programs

(c) 2016--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import pkgutil


def store_bundled_programs(program_path):
    """Retrieve contents of BASIC programs."""
    for name in pkgutil.get_data(__name__, 'list.txt').splitlines():
        with open(os.path.join(program_path, name), 'wb') as f:
            f.write(pkgutil.get_data(__name__, name))
