"""
PC-BASIC - compat.base
Cross-platform compatibility utilities

(c) 2018--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import re
import contextlib
import sys
import platform


# Python major version
PY2 = sys.version_info.major == 2

# platform constants
WIN32 = sys.platform == 'win32'
MACOS = sys.platform == 'darwin'

# 64-bit (needed for Windows binary modules)
X64 = platform.architecture()[0] == '64bit'

# platform tag for libraries
if WIN32:
    PLATFORM = sys.platform + ('_x64' if X64 else '_x86')
else:
    PLATFORM = sys.platform

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

# package/executable directory
if hasattr(sys, 'frozen'):
    # we're a package: get the directory of the packaged executable
    # (__file__ is undefined in frozen packages)
    # this is for cx_Freeze's package layout
    BASE_DIR = os.path.join(os.path.dirname(sys.executable), 'lib', 'pcbasic')
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))



# utility functions, this has to go somewhere...

def split_quoted(line, split_by=u'\s', quote=u'"', strip_quotes=False):
    """Split by separators, preserving quoted blocks."""
    # https://stackoverflow.com/questions/16710076/python-split-a-string-respect-and-preserve-quotes
    regexp = r'(?:[^{split_by}{quote}]|{quote}(?:\\.|[^{quote}])*{quote})+'.format(
        split_by=split_by, quote=quote
    )
    chunks = re.findall(regexp, line)
    if strip_quotes:
        chunks = [c.strip(quote) for c in chunks]
    return chunks

def split_pair(s, sep):
    """Split an argument by separator, always return two elements."""
    slist = s.split(sep, 1)
    s0 = slist[0]
    if len(slist) > 1:
        s1 = slist[1]
    else:
        s1 = u''
    return s0, s1

def iter_chunks(char_list, attrs):
    """Iterate over list yielding chunks of elements with the same attribute."""
    last_attr = None
    chars = []
    # collect chars in chunks with the same attribute
    for char, attr in zip(char_list, attrs):
        if attr != last_attr:
            if last_attr is not None:
                yield chars, last_attr
            last_attr = attr
            chars = []
        chars.append(char)
    if chars:
        yield chars, attr
