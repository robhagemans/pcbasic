"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io
import sys
import traceback
import logging
import platform
import struct
import tempfile
import subprocess
import importlib

from .base import error
from ..compat import PY2, WIN32, X64, BASE_DIR, which
from . import values
from . import api


def get_platform_info():
    """Show information about operating system and installed modules."""
    info = []
    info.append(u'\nPLATFORM')
    info.append(u'os: %s' % platform.platform())
    frozen = getattr(sys, 'frozen', '') or ''
    info.append(
        u'python: %s %s %s' % (
        sys.version.replace('\n', ''), ' '.join(platform.architecture()), frozen))
    info.append(u'\nMODULES')
    modules = ('pyaudio', 'serial', 'parallel')
    for module in modules:
        try:
            m = importlib.import_module(module)
        except Exception:
            info.append(u'%s: --' % module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    name = module.split('.')[-1]
                    version = getattr(m, version_attr)
                    if isinstance(version, bytes):
                        version = version.decode('ascii', 'ignore')
                    info.append(u'%s: %s' % (name, version))
                    break
                except AttributeError:
                    pass
            else:
                info.append(u'%s: available' % module)
    info.append(u'\nLIBRARIES')
    try:
        from ..interface import video_sdl2
        video_sdl2._import_sdl2()

        info.append(u'sdl2: %s' % (video_sdl2.sdl2.sdl2_lib.libfile,))
        if video_sdl2:
            info.append(u'sdl2_gfx: %s' % (video_sdl2.sdl2.gfx_lib.libfile, ))
        else:
            info.append(u'sdl2_gfx: --')
    except ImportError as e:
        raise
        info.append(u'sdl2: --')
        sdl2 = None
    info.append(u'\nEXTERNAL TOOLS')
    tools = (u'notepad', u'lpr', u'paps', u'beep', u'pbcopy', u'pbpaste')
    for tool in tools:
        location = which(tool) or u'--'
        info.append(u'%s: %s' % (tool, location))
    info.append(u'')
    return u'\n'.join(info)


class DebugException(BaseException):
    """Test exception for debugging purposes"""
    # inherit from BaseException to circumvent extension manager catching Exception

    def __repr__(self):
        return self.__doc__


class DebugSession(api.Session):
    """Debugging helper."""

    def __init__(self, *args, **kwargs):
        """Initialise debugger."""
        api.Session.__init__(self, *args, **kwargs)

    def start(self):
        """Start the session."""
        if not self._impl:
            api.Session.start(self)
            # register as an extension
            self._impl.extensions.add(self)
            # replace dummy debugging step
            self._impl.interpreter.step = self._debug_step
            self._do_trace = False
            self._watch_list = []

    def _debug_step(self, token):
        """Execute traces and watches on a program step."""
        outstr = u''
        if self._do_trace:
            linum = struct.unpack_from('<H', token, 2)
            outstr += u'[%i]' % linum
        for (expr, outs) in self._watch_list:
            outstr += u' %r = ' % (expr,)
            outs.seek(2)
            try:
                val = self._impl.parser.expression_parser.parse(outs)
                if isinstance(val, values.String):
                    outstr += u'"%s"' % self._impl.codepage.bytes_to_unicode(val.to_str())
                else:
                    outstr += (
                        values.to_repr(val, leading_space=False, type_sign=True)
                        .decode('ascii', 'ignore')
                    )
            except Exception as e:
                self._handle_exception(e)
        if outstr:
            logging.debug(outstr)

    def _handle_exception(self, e):
        """Handle exception during debugging."""
        logging.debug('%s %s', type(e), str(e))
        raise

    ###########################################################################
    # debugging commands

    def dir(self):
        """Show debugging commands."""
        logging.debug('Available commands:\n' + '\n'.join(
            '    _%s: %s' % (
                n.upper(), getattr(self, n).__doc__)
                for n in dir(self)
                    if '_' not in n and callable(getattr(self, n)) and n not in dir(api.Session)
            ))

    def crash(self):
        """Simulate a crash."""
        raise DebugException()

    def python(self, cmd):
        """Execute any Python code."""
        buf = io.BytesIO() if PY2 else io.StringIO()
        save_stdout = sys.stdout
        sys.stdout = buf
        try:
            exec(cmd)
        except Exception as e:
            self._handle_exception(e)
        sys.stdout = save_stdout
        logging.debug(buf.getvalue()[:-1]) # exclude \n

    def restart(self):
        """Ctrl+Alt+Delete."""
        raise error.Reset()

    def exit(self):
        """Quit the session."""
        raise error.Exit()

    def logprint(self, *args):
        """Write arguments to log."""
        logging.debug(self._impl.codepage.bytes_to_unicode(b' '.join(bytes(arg) for arg in args)))

    def logwrite(self, *args):
        """Write arguments to log."""
        logging.debug(' '.join(repr(arg) for arg in args))

    def trace(self, on=True):
        """Switch line number tracing on or off."""
        self._do_trace = on

    def watch(self, expr):
        """Add an expression to the watch list."""
        outs = self._impl.tokeniser.tokenise_line(b'?' + expr)
        self._watch_list.append((expr, outs))

    def showvariables(self):
        """Dump all variables to the log."""
        repr_vars = '\n'.join((
            '==== Scalars ='.ljust(100, '='),
            repr(self._impl.scalars),
            '==== Arrays ='.ljust(100, '='),
            repr(self._impl.arrays),
            '==== Strings ='.ljust(100, '='),
            repr(self._impl.strings),
        ))
        for s in repr_vars.split('\n'):
            logging.debug(s)

    def showscreen(self):
        """Copy the screen buffer to the log."""
        for s in repr(self._impl.display.text_screen).split('\n'):
            logging.debug(self._impl.codepage.bytes_to_unicode(s.encode('latin-1', 'ignore')))

    def showprogram(self):
        """Write a marked-up hex dump of the program to the log."""
        for s in repr(self._impl.program).split('\n'):
            logging.debug(s)

    def showplatform(self):
        """Show platform info."""
        logging.debug(get_platform_info())
