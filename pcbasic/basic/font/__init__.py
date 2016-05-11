"""
PC-BASIC - font package
Font definitions

(c) 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkgutil

fonts = pkgutil.get_data(__name__, 'list.txt').splitlines()


def get_data(package, name):
    """Wrapper for get_data to make it do what is advertised."""
    try:
        return pkgutil.get_data(package, name)
    except EnvironmentError:
        return None

def read_files(families, height):
    """Retrieve contents of font files."""
    return [get_data(__name__, '%s_%02d.hex' % (name, height)) for name in families]
