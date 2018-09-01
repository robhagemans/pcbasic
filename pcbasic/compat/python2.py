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
import codecs
import contextlib
import itertools
import sys
import os


PY2 = sys.version_info.major == 2
PY3 = not PY2


if PY2:
    import ConfigParser as configparser
    import Queue as queue
    import copy_reg as copyreg

    _FS_ENCODING = sys.getfilesystemencoding()

    getcwdu = os.getcwdu
    xrange = xrange
    unichr = unichr
    int2byte = chr
    text_type = unicode
    zip = itertools.izip

    # unicode streams

    def _wrap_input_stream(stream):
        """Wrap std streams to make them behave more like in Python 3."""
        wrapped = codecs.getreader(stream.encoding or 'utf-8')(stream)
        wrapped.buffer = stream
        return wrapped

    def _wrap_output_stream(stream):
        """Wrap std streams to make them behave more like in Python 3."""
        wrapped = codecs.getwriter(stream.encoding or 'utf-8')(stream)
        wrapped.buffer = stream
        return wrapped

    stdin = _wrap_input_stream(sys.stdin)
    stdout = _wrap_output_stream(sys.stdout)
    stderr = _wrap_output_stream(sys.stderr)

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

    # unicode streams

    stdin = sys.stdin
    stdout = sys.stdout
    stderr = sys.stderr

    # unicode system interfaces

    # following python 3.5 this uses sys.getfilesystemencoding()
    getenvu = os.getenv

    def setenvu(key, value):
        os.environ[key] = value

    def iterenvu():
        return os.environ.keys()

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


@contextlib.contextmanager
def suppress_output():
    """Suppress stdout and stderr messages."""
    try:
        # save the file descriptors for /dev/stdout and /dev/stderr
        save_0, save_1 = os.dup(sys.stdout.fileno()), os.dup(sys.stderr.fileno())
        # http://stackoverflow.com/questions/977840/
        # redirecting-fortran-called-via-f2py-output-in-python/978264#978264
        with open(os.devnull, 'w') as null_0:
            with open(os.devnull, 'w') as null_1:
                # put /dev/null fds on 1 (stdout) and 2 (stderr)
                os.dup2(null_0.fileno(), sys.stdout.fileno())
                os.dup2(null_1.fileno(), sys.stderr.fileno())
                # do stuff
                yield
                sys.stdout.flush()
                sys.stderr.flush()
                # restore file descriptors
                os.dup2(save_0, sys.stdout.fileno())
                os.dup2(save_1, sys.stderr.fileno())
    finally:
        os.close(save_0)
        os.close(save_1)


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
