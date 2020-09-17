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
import codecs
import io
import tempfile


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


# unicode stream wrappers

def wrap_output_stream(stream):
    """Wrap std bytes streams to make them behave more like in Python 3."""
    wrapped = codecs.getwriter(stream.encoding or 'utf-8')(stream)
    wrapped.buffer = stream
    return wrapped

def wrap_input_stream(stream):
    """Wrap std bytes streams to make them behave more like in Python 3."""
    wrapped = codecs.getreader(stream.encoding or 'utf-8')(stream)
    wrapped.buffer = stream
    return wrapped


# utility functions, this has to go somewhere...

def split_quoted(line, split_by=u'\s', quote=u'"', strip_quotes=False):
    """Split by separators, preserving quoted blocks."""
    chunks = re.findall(u'[^%s%s][^%s]*|%s.+?%s' % (quote, split_by, split_by, quote, quote), line)
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

@contextlib.contextmanager
def muffle(std_stream, preserve=False):
    """Suppress or delay stdout or stderr messages from Python, C or external programs."""
    save = None
    try:
        try:
            # save the file descriptor for the target stream
            save = os.dup(std_stream.fileno())
        except EnvironmentError:
            yield
            return
        # check for file-like objects that expect unicode, raw output otherwise
        if isinstance(std_stream, (
                io.TextIOWrapper, io.StringIO,
                codecs.StreamReaderWriter, codecs.StreamWriter,
            )):
            mode = ''
        else:
            mode = 'b'
        if preserve:
            temp_file = tempfile.TemporaryFile('w+' + mode)
        else:
            temp_file = io.open(os.devnull, 'w' + mode)
        # http://stackoverflow.com/questions/977840/
        # redirecting-fortran-called-via-f2py-output-in-python/978264#978264
        with temp_file as temp:
            # put /dev/null fds on 1 (stdout) or 2 (stderr)
            os.dup2(temp.fileno(), std_stream.fileno())
            # do stuff
            try:
                yield
            finally:
                std_stream.flush()
                # restore file descriptors
                os.dup2(save, std_stream.fileno())
                if preserve:
                    # write contents of temporary file back into stream
                    temp.flush()
                    temp.seek(0)
                    std_stream.write(temp.read())
    finally:
        if save is not None:
            os.close(save)
