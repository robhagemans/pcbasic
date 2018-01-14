"""
PC-BASIC - programs package
Bundled BASIC programs

(c) 2016--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import pkg_resources


def store_bundled_programs(program_path):
    """Retrieve contents of BASIC programs."""
    programs = (name for name in pkg_resources.resource_listdir(__name__, '.') if name.lower().endswith('.bas'))
    for name in programs:
        with open(os.path.join(program_path, name), 'wb') as f:
            f.write(pkg_resources.resource_string(__name__, name))
