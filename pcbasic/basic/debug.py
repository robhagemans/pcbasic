"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013--2018 Rob Hagemans
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
from ..compat import WIN32, X64, BASE_DIR, which
from . import values
from . import api


def show_platform_info():
    """Show information about operating system and installed modules."""
    logging.info('\nPLATFORM')
    logging.info('os: %s %s %s', platform.system(), platform.processor(), platform.version())
    logging.info('python: %s %s', sys.version.replace('\n',''), ' '.join(platform.architecture()))
    logging.info('\nMODULES')
    # try numpy before pygame to avoid strange ImportError on FreeBSD
    modules = ('numpy', 'pygame', 'curses', 'serial', 'parallel')
    for module in modules:
        try:
            m = importlib.import_module(module)
        except Exception:
            logging.info('%s: --', module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    name = module.split('.')[-1]
                    version = getattr(m, version_attr)
                    logging.info('%s: %s', name, version)
                    break
                except AttributeError:
                    pass
            else:
                logging.info('%s: available', module)
    if WIN32:
        logging.info('\nLIBRARIES')
        dlls = ('sdl2.dll', 'sdl2_gfx.dll')
        if X64:
            LIB_DIR = os.path.join(BASE_DIR, 'lib', 'win32_x64')
        else:
            LIB_DIR = os.path.join(BASE_DIR, 'lib', 'win32_x86')
        for dll in dlls:
            path = os.path.join(LIB_DIR, dll)
            if os.path.isfile(path):
                logging.info('%s: %s', dll, path)
            else:
                logging.info('%s: --', dll)
    logging.info('\nEXTERNAL TOOLS')
    tools = ('notepad', 'lpr', 'paps', 'beep', 'pbcopy', 'pbpaste')
    for tool in tools:
        location = which(tool) or '--'
        logging.info('%s: %s', tool, location)


class DebugException(BaseException):
    """Test exception for debugging purposes"""
    # inherit from BaseException to circumvent extension manager catching Exception

    def __str__(self):
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
        outstr = ''
        if self._do_trace:
            linum = struct.unpack_from('<H', token, 2)
            outstr += '[%i]' % linum
        for (expr, outs) in self._watch_list:
            outstr += ' %s = ' % str(expr)
            outs.seek(2)
            try:
                val = self._impl.parser.expression_parser.parse(outs)
                if isinstance(val, values.String):
                    outstr += '"%s"' % val.to_str()
                else:
                    outstr += values.to_repr(val, leading_space=False, type_sign=True)
            except Exception as e:
                logging.debug(str(type(e))+' '+str(e))
                traceback.print_tb(sys.exc_info()[2])
        if outstr:
            logging.debug(outstr)

    def _handle_exception(self, e):
        """Handle exception during debugging."""
        logging.debug(b'%s %s', type(e), bytes(e))
        traceback.print_tb(sys.exc_info()[2])

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
        buf = io.BytesIO()
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
        logging.debug(' '.join(bytes(arg) for arg in args))

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
            str(self._impl.scalars),
            '==== Arrays ='.ljust(100, '='),
            str(self._impl.arrays),
            '==== Strings ='.ljust(100, '='),
            str(self._impl.strings),
        ))
        for s in repr_vars.split('\n'):
            logging.debug(s)

    def showscreen(self):
        """Copy the screen buffer to the log."""
        for s in str(self._impl.display.text_screen).split('\n'):
            logging.debug(s)

    def showprogram(self):
        """Write a marked-up hex dump of the program to the log."""
        for s in str(self._impl.program).split('\n'):
            logging.debug(s)

    def showplatform(self):
        """Show platform info."""
        show_platform_info()
