"""
PC-BASIC - compat.python2
Python 2 backports for Python 3 functionality

Contains functions from Python 3.3 source code, which is
copyright (c) 2001-2016 Python Software Foundation
and released under a GPL-compatible licence https://docs.python.org/3.3/license.html

Contains lines of code from package six, which is
Copyright (c) 2010-2018 Benjamin Peterson
and released under an MIT licence https://opensource.org/licenses/MIT
"""

# pylint: disable=import-error, no-member, undefined-variable

import shutil
import codecs
import contextlib
import itertools
import tempfile
import sys
import os

import ConfigParser as configparser
import Queue as queue
import copy_reg as copyreg

_FS_ENCODING = sys.getfilesystemencoding()


# __path__ hack for __init__ to ensure os.chdir does not break intra-package imports
# which they do because the package __path__ is given relative to cwd
# at least if run with python2 -m package
from .. import __path__
__path__[:] = [os.path.abspath(_e) for _e in __path__]


# strings

int2byte = chr

def iterchar(s):
    """Iterate over bytes, returning char."""
    return s

def iterbytes(s):
    """Iterate over bytes/bytearray/memoryview, returning int."""
    if isinstance(s, (bytes, memoryview)):
        return (ord(_c) for _c in s)
    return s

def add_str(cls):
    """Decorator to implement the correct str() function."""
    try:
        cls.__str__ = cls.__bytes__
    except AttributeError:
        pass
    return cls


# unicode system interfaces

getcwdu = os.getcwdu

# following python 3.5 this uses sys.getfilesystemencoding()
def getenvu(key, default=None):
    assert isinstance(key, unicode), type(key)
    try:
        return os.environ[key.encode(_FS_ENCODING)].decode(_FS_ENCODING)
    except KeyError:
        return default

def setenvu(key, value):
    assert isinstance(key, unicode), type(key)
    assert isinstance(value, unicode), type(value)
    os.environ[key.encode(_FS_ENCODING)] = value.encode(_FS_ENCODING)

def iterenvu():
    return (_key.decode(_FS_ENCODING) for _key in os.environ)


# iterators

xrange = xrange
zip = itertools.izip

def iteritems(d, **kw):
    return d.iteritems(**kw)

def itervalues(d, **kw):
    return d.itervalues(**kw)

def iterkeys(d, **kw):
    return d.iterkeys(**kw)

# utilities

# from Python3.3 shutil module source
def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode)
                and not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to the
    # current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd
        return None

    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if not os.curdir in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        # If it does match, only test that one, otherwise we have to try
        # others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir in path:
        normdir = os.path.normcase(dir)
        if not normdir in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    return name
    return None


class SimpleNamespace(object):
    """Namespace with attribute access, like in Python 3
    https://docs.python.org/dev/library/types.html#types.SimpleNamespace
    """

    def __init__(self, **kwargs):
        """Initialise the namespace with keyword arguments."""
        self.__dict__.update(kwargs)

    def __repr__(self):
        """Bytes representation (for Python 2)."""
        keys = sorted(self.__dict__)
        items = (b'{}={!r}'.format(k, self.__dict__[k]) for k in keys)
        return b'{}({})'.format(type(self).__name__, b', '.join(items))

    def __eq__(self, other):
        """Namespaces are equal if their entries are equal."""
        return self.__dict__ == other.__dict__


class TemporaryDirectory():
    """Temporary directory context guard like in Python 3 tempfile."""

    def __init__(self, prefix=u''):
        """Initialise context guard."""
        self._prefix = prefix
        self._temp_dir = None

    def __enter__(self):
        """Create temp directory."""
        self._temp_dir = tempfile.mkdtemp(prefix=self._prefix)
        return self._temp_dir

    def __exit__(self, dummy_1, dummy_2, dummy_3):
        """Clean up temp directory."""
        if self._temp_dir:
            try:
                shutil.rmtree(self._temp_dir)
            except EnvironmentError as e:
                pass
