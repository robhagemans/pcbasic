"""
PC-BASIC - compat.base
Cross-platform compatibility utilities

(c) 2018--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import re
import contextlib
import sys
import platform


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
    USER_CONFIG_HOME = os.getenv(u'APPDATA', default=u'')
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

def _build_split_regexp(split_by, quote, as_type):
    """
    Build regexp for use with split_quoted and split_pair.
    `split_by` and `quote` must be of type `as_type`.
    """
    if not quote:
        quote = as_type()
    quote = re.escape(quote)
    if split_by is None:
        # by default, split on whitespace
        split_by = u'\s'
    else:
        split_by = re.escape(split_by)
    # https://stackoverflow.com/questions/16710076/python-split-a-string-respect-and-preserve-quotes
    # note ur'' is not accepted by python 3, and r'' means bytes in python2.
    # bytes has no .format so using % which is awkward here
    pattern = (
        br'(?:[^{%s}{%s}]|[{%s}](?:\\.|[^{%s}])*[{%s}])+'
    )
    if as_type == type(u''):
        # we know the template pattern string and ascii is ok
        pattern = pattern.decode('ascii', 'ignore')
    regexp = pattern % (split_by, quote, quote, quote, quote)
    return regexp

def split_quoted(line, split_by=None, quote=None, strip_quotes=False):
    """
    Split by separators, preserving quoted blocks; \\ escapes quotes.
    """
    regexp = _build_split_regexp(split_by, quote, as_type=type(line))
    chunks = re.findall(regexp, line)
    if strip_quotes:
        chunks = [c.strip(quote) for c in chunks]
    return chunks

def split_pair(line, split_by=None, quote=None):
    """
    Split by separators, preserving quoted blocks; \\ escapes quotes.
    First match only, always return two values.
    """
    regexp = _build_split_regexp(split_by, quote, as_type=type(line))
    for match in re.finditer(regexp, line):
        s0 = match.group()
        s1 = line[match.end()+1:]
        # only loop once
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
