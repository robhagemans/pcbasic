"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import sys
import logging
import struct

from .base import error
from ..compat import PY2, text_type
from ..info import get_platform_info
from . import values
from . import api



class DebugException(BaseException):
    """This exception was raised deliberately through the debug module."""
    # inherit from BaseException to circumvent extension manager catching Exception

    def __repr__(self):
        return self.__doc__

    __str__ = __repr__


class DebugSession(api.Session):
    """Debugging helper."""

    def __init__(self, *args, **kwargs):
        """Initialise debugger."""
        # register as an extension
        kwargs['extension'] = tuple(kwargs.get('extension', ())) + (self,)
        api.Session.__init__(self, *args, **kwargs)

    def start(self):
        """Start the session."""
        # initialise implementation
        if api.Session.start(self):
            # replace dummy debugging step
            self.set_hook(self._debug_step)
            self._do_trace = False
            self._watch_list = []

    def _debug_step(self, token):
        """Execute traces and watches on a program step."""
        outstr = u''
        if self._do_trace:
            linum = struct.unpack_from('<H', token, 2)
            outstr += u'[%i]' % linum
        for expr in self._watch_list:
            exprstr = self.convert(expr, to_type=text_type)
            outstr += u' %s = ' % (exprstr,)
            try:
                val = self.evaluate(expr)
                print(expr, val)
                if isinstance(val, bytes):
                    outstr += u'"%s"' % self.convert(val, to_type=text_type)
                else:
                    outstr += repr(val)
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
        logging.debug(self.convert(b' '.join(bytes(arg) for arg in args), to_type=text_type))

    def logwrite(self, *args):
        """Write arguments to log."""
        logging.debug(' '.join(repr(arg) for arg in args))

    def trace(self, on=True):
        """Switch line number tracing on or off."""
        self._do_trace = on

    def watch(self, expr):
        """Add an expression to the watch list."""
        self._watch_list.append(expr)

    def showvariables(self):
        """Dump all variables to the log."""
        repr_vars = '\n'.join((
            '==== Scalars ='.ljust(100, '='),
            self.info.repr_scalars(),
            '==== Arrays ='.ljust(100, '='),
            self.info.repr_arrays(),
            '==== Strings ='.ljust(100, '='),
            self.info.repr_strings(),
        ))
        for s in repr_vars.split('\n'):
            logging.debug(s)

    def showscreen(self):
        """Copy the screen buffer to the log."""
        for s in self.info.repr_text_screen().split('\n'):
            logging.debug(s)

    def showprogram(self):
        """Write a marked-up hex dump of the program to the log."""
        for s in self.info.repr_program().split('\n'):
            logging.debug(s)

    def showplatform(self):
        """Show platform info."""
        logging.debug(get_platform_info())
