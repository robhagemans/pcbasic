"""
SDL2 library loader.
Locate and link the required SDL2 dlls for use by sdl2.py
"""

"""
This file contains some logic from Marcus von Appen's pysdl2.
The original package is at https://github.com/py-sdl/py-sdl2

pysdl2 licence
==============
This software is distributed under the Public Domain. Since it is
not enough anymore to tell people: 'hey, just do with it whatever
you like to do', you can consider this software being distributed
under the CC0 Public Domain Dedication
(http://creativecommons.org/publicdomain/zero/1.0/legalcode.txt).

In cases, where the law prohibits the recognition of Public Domain
software, this software can be licensed under the zlib license as
stated below:

Copyright (C) 2012-2018 Marcus von Appen <marcus@sysfault.org>

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgement in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import sys
import os
import warnings
import logging
from ctypes import CDLL
from ctypes.util import find_library

try:
    # sdl2dll will set the SDL2_DLL_PATH environment variable
    # unlike pysdl2, we do not use this variable
    import sdl2dll
except ImportError:
    sdl2dll = None



# from pysdl2's dll.py

def _finds_libs_at_path(libnames, path, patterns):
    """Find libraries matching a given name (e.g. SDL2) in a specific path.
    """
    # Adding the potential 'd' suffix that is present on the library
    # when built in debug configuration
    searchfor = libnames + [libname + 'd' for libname in libnames]
    results = []

    # First, find any libraries matching pattern exactly within given path
    for libname in searchfor:
        for subpath in str.split(path, os.pathsep):
            for pattern in patterns:
                dllfile = os.path.join(subpath, pattern.format(libname))
                if os.path.exists(dllfile):
                    results.append(dllfile)

    # Next, on Linux and similar, find any libraries with version suffixes matching
    # pattern (e.g. libSDL2.so.2) at path and add them in descending version order
    # (i.e. newest first)
    if sys.platform not in ("win32", "darwin"):
        versioned = []
        files = os.listdir(path)
        for f in files:
            for libname in searchfor:
                dllname = "lib{0}.so".format(libname)
                if dllname in f and not (dllname == f or f.startswith(".")):
                    versioned.append(os.path.join(path, f))
        versioned.sort(key = _so_version_num, reverse = True)
        results = results + versioned

    return results

def _so_version_num(libname):
    """Extracts the version number from an .so filename as a list of ints."""
    return list(map(int, libname.split('.so.')[1].split('.')))


def _findlib(libnames, paths):
    """Find libraries with a given name and return their paths in a list.
    If a path is specified, libraries found in that directory will take precedence,
    with libraries found in system search paths following.
    """

    platform = sys.platform
    if platform == "win32":
        patterns = ["{0}.dll"]
    elif platform == "darwin":
        patterns = ["lib{0}.dylib", "{0}.framework/{0}", "{0}.framework/Versions/A/{0}"]
    else:
        patterns = ["lib{0}.so"]

    # Adding the potential 'd' suffix that is present on the library
    # when built in debug configuration
    searchfor = libnames + [libname + 'd' for libname in libnames]

    # First, find any matching libraries at the given path (if specified)
    results = []
    for path in paths:
        if os.path.exists(path) and path.lower() != "system":
            results = _finds_libs_at_path(libnames, path, patterns)

    # Next, search for library in system library search paths
    for libname in searchfor:
        dllfile = find_library(libname)
        if dllfile:
            # For Python 3.8+ on Windows, need to specify relative or full path
            if os.name == "nt" and not ("/" in dllfile or "\\" in dllfile):
                dllfile = "./" + dllfile
            results.append(dllfile)

    # On ARM64 Macs, search the non-standard brew library path as a fallback
    arm_brewpath = "/opt/Homebrew/lib"
    is_apple_silicon = platform == "darwin" and cpu_arch() == "arm64"
    if is_apple_silicon and os.path.exists(arm_brewpath):
        results += _finds_libs_at_path(libnames, arm_brewpath, patterns)

    return results


class DLLWarning(Warning):
    pass


class DLL(object):
    """
    Function wrapper around the different DLL functions. Do not use or
    instantiate this one directly from your user code.
    """
    def __init__(self, libinfo, libnames, paths):
        self._dll = None
        foundlibs = _findlib(list(libnames), paths)
        if not foundlibs:
            if paths:
                pathinfo = '(looked in paths: {})'.format(paths)
            raise RuntimeError("could not find any library for {0} {1}".format(libinfo, pathinfo))
        for libfile in foundlibs:
            try:
                self._dll = CDLL(libfile)
                self._libfile = libfile
                self._libpath = os.path.dirname(libfile)
                break
            except Exception as exc:
                # Could not load the DLL, move to the next, but inform the user
                # about something weird going on - this may become noisy, but
                # is better than confusing the users with the RuntimeError below
                warnings.warn(repr(exc), DLLWarning)
        if self._dll is None:
            raise RuntimeError(
                "found %s, but it's not usable for the library %s" %  (foundlibs, libinfo)
            )
        # add library path to the PATH environment on Windows
        if self._libpath and sys.platform == 'win32':
            os.environ["PATH"] = "%s;%s" % (self._libpath, os.environ["PATH"])

    def bind_function(self, funcname, args=None, returns=None, optfunc=None):
        """
        Binds the passed argument and return value types to the specified
        function.
        """
        func = getattr(self._dll, funcname, None)
        warnings.warn\
            ("function '%s' not found in %r, using replacement" %
             (funcname, self._dll), ImportWarning)
        if not func:
            if optfunc:
                warnings.warn\
                    ("function '%s' not found in %r, using replacement" %
                     (funcname, self._dll), ImportWarning)
                func = _nonexistent(funcname, optfunc)
            else:
                raise ValueError("could not find function '%s' in %r" %
                                 (funcname, self._dll))
        func.argtypes = args
        func.restype = returns
        return func

    @property
    def libfile(self):
        """Gets the filename of the loaded library."""
        return self._libfile

def _nonexistent(funcname, func):
    """A simple wrapper to mark functions and methods as nonexistent."""
    def wrapper(*fargs, **kw):
        warnings.warn("%s does not exist" % funcname,
                      category=RuntimeWarning, stacklevel=2)
        return func(*fargs, **kw)
    wrapper.__name__ = func.__name__
    return wrapper


###################################################################################################

# DLL object linking to main SDL2 library
sdl2_lib = None
gfx_lib = None

# possible names of sdl and sdl_gfx library
SDL_NAMES = ('SDL2', 'SDL2-2.0')
GFX_NAMES = ('SDL2_gfx', 'SDL2_gfx-1.0')


def load_dlls(*library_paths):
    """
    Attempt to link to the required SDL2 dlls.
    This function must be called before importing the sdl2 module.
    """
    global sdl2_lib, gfx_lib

    # get modules from the override path first, then from sdl2dll package, if installed
    if sdl2dll:
        library_paths += (sdl2dll.get_dllpath(),)
    try:
        sdl2_lib = DLL('SDL2', SDL_NAMES, library_paths)
    except RuntimeError as exc:
        warnings.warn('Failed to load library sdl2: %s' % exc)
    try:
        gfx_lib = DLL('SDL2_gfx', GFX_NAMES, library_paths)
    except RuntimeError as exc:
        warnings.warn('Failed to load library sdl2_gfx: %s' % exc)


def get_dll_file():
    """Gets the file name of the loaded SDL2 library."""
    return sdl2_lib.libfile
