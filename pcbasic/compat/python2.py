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

import shutil
import sys
import os


PY2 = sys.version_info.major == 2
PY3 = not PY2


if PY2:
    import ConfigParser as configparser
    import Queue as queue
    import copy_reg as copyreg

    import itertools as _itertools

    _FS_ENCODING = sys.getfilesystemencoding()

    getcwdu = os.getcwdu
    xrange = xrange
    unichr = unichr
    int2byte = chr
    text_type = unicode
    zip = _itertools.izip

    # unicode system interfaces

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

    # bytes streams

    def bstdout():
        return sys.stdout

    def bstdin():
        return sys.stdin

    def bstderr():
        return sys.stderr

    # iterators

    def iterchar(s):
        """Iterate over bytes, returning char."""
        return s

    def iteritems(d, **kw):
        return d.iteritems(**kw)

    def itervalues(d, **kw):
        return d.itervalues(**kw)

    def iterkeys(d, **kw):
        return d.iterkeys(**kw)

else:
    import configparser
    import queue
    import copyreg

    import struct as _struct

    getcwdu = os.getcwd
    xrange = range
    unichr = chr
    int2byte = _struct.Struct(">B").pack
    text_type = str
    zip = zip

    # unicode system interfaces

    # following python 3.5 this uses sys.getfilesystemencoding()
    getenvu = os.getenv

    def setenvu(key, value):
        os.environ[key] = value

    def iterenvu():
        return os.environ.keys()

    # bytes streams

    def bstdout():
        sys.stdout.buffer.encoding = sys.stdout.encoding
        return sys.stdout.buffer

    def bstdin():
        sys.stdin.buffer.encoding = sys.stdin.encoding
        return sys.stdin.buffer

    def bstderr():
        sys.stderr.buffer.encoding = sys.stderr.encoding
        return sys.stderr.buffer

    # iterators

    def iterchar(s):
        """Iterate over bytes, returning char."""
        return (s[_i:_i+1] for _i in range(len(s)))

    def iteritems(d, **kw):
        return iter(d.items(**kw))

    def itervalues(d, **kw):
        return iter(d.values(**kw))

    def iterkeys(d, **kw):
        return iter(d.keys(**kw))


try:
    from shutil import which
except ImportError:
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
