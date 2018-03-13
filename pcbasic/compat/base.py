"""
PC-BASIC - compat.base
Cross-platform compatibility utilities

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys

# platform constants
WIN32 = sys.platform == 'win32'
MACOS = sys.platform == 'darwin'

# encodings

def encoding(stream):
    """Get encoding of a standard stream, fallback to UTF-8."""
    enc = stream.encoding
    return 'utf-8' if (not enc or enc == 'cp65001') else enc

# conventions
if WIN32:
    # ctrl+Z
    EOF = b'\x1A'
    UEOF = u'\x1A'
else:
    # ctrl+D
    EOF = b'\x04'
    UEOF = u'\x04'


# user configuration and state directories
HOME_DIR = os.path.expanduser(u'~')

if WIN32:
    USER_CONFIG_HOME = os.getenv(u'APPDATA')
    USER_DATA_HOME = USER_CONFIG_HOME

elif MACOS:
    USER_CONFIG_HOME = os.path.join(HOME_DIR, u'Library', u'Application Support')
    USER_DATA_HOME = USER_CONFIG_HOME

else:
    USER_CONFIG_HOME = os.environ.get(u'XDG_CONFIG_HOME') or os.path.join(HOME_DIR, u'.config')
    USER_DATA_HOME = os.environ.get(u'XDG_DATA_HOME') or os.path.join(HOME_DIR, u'.local', u'share')
