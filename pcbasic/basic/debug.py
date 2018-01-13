"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
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
from datetime import datetime

from ..version import __version__
from .. import config
from .base import error
from . import values


def get_debugger(session, option_debug, debug_uargv):
    """Create debugger."""
    if option_debug:
        return Debugger(session, debug_uargv)
    else:
        return BaseDebugger(session, debug_uargv)


class DebugException(Exception):
    """Test exception for debugging purposes"""
    def __str__(self):
        return self.__doc__


class BaseDebugger(object):
    """Only debug uncaught exceptions."""

    debug_mode = False

    def __init__(self, session, uargv):
        """Initialise debugger."""
        self.debug_tron = False
        self.uargv = uargv
        self.session = session

    def repr_variables(self):
        """Return a string representation of all variables."""
        return '\n'.join((
            '==== Scalars ='.ljust(100, '='),
            str(self.session.scalars),
            '==== Arrays ='.ljust(100, '='),
            str(self.session.arrays),
            '==== Strings ='.ljust(100, '='),
            str(self.session.strings),
        ))

    def repr_screen(self):
        """Return a string representation of the screen buffer."""
        horiz_bar = ('  +' + '-'*self.session.screen.mode.width + '+')
        i = 0
        lastwrap = False
        row_strs = [
            '==== Screen ='.ljust(100, '='),
            horiz_bar]
        for row in self.session.screen.apage.row:
            s = [ c[0] for c in row.buf ]
            i += 1
            outstr = '{0:2}'.format(i)
            if lastwrap:
                outstr += ('\\')
            else:
                outstr += ('|')
            outstr += (''.join(s))
            if row.wrap:
                row_strs.append(outstr + '\\ {0:2}'.format(row.end))
            else:
                row_strs.append(outstr + '| {0:2}'.format(row.end))
            lastwrap = row.wrap
        row_strs.append(horiz_bar)
        return '\n'.join(row_strs)

    def repr_program(self):
        """Return a marked-up hex dump of the program."""
        prog = self.session.program
        code = prog.bytecode.getvalue()
        offset_val, p = 0, 0
        output = ['==== Program Buffer ='.ljust(100, '=')]
        for key in sorted(prog.line_numbers.keys())[1:]:
            offset, linum = code[p+1:p+3], code[p+3:p+5]
            last_offset = offset_val
            offset_val = (struct.unpack('<H', offset)[0]
                                    - (self.session.memory.code_start + 1))
            linum_val, = struct.unpack('<H', linum)
            output.append(
                (code[p:p+1].encode('hex') + ' ' +
                offset.encode('hex') + ' (+%03d) ' +
                code[p+3:p+5].encode('hex') + ' [%05d] ' +
                code[p+5:prog.line_numbers[key]].encode('hex')) %
                                        (offset_val - last_offset, linum_val))
            p = prog.line_numbers[key]
        output.append(code[p:p+1].encode('hex') + ' ' +
                    code[p+1:p+3].encode('hex') + ' (ENDS) ' +
                    code[p+3:p+5].encode('hex') + ' ' + code[p+5:].encode('hex'))
        return '\n'.join(output)

    def bluescreen(self, e):
        """Display a modal exception message."""
        # log the standard python error
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack = traceback.extract_tb(exc_traceback)
        logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        # obtain statement being executed
        if self.session.interpreter.run_mode:
            codestream = self.session.program.bytecode
            bytepos = codestream.tell() - 1
            from_line = self.session.program.get_line_number(bytepos)
            codestream.seek(self.session.program.line_numbers[from_line]+1)
            _, output, textpos = self.session.lister.detokenise_line(codestream, bytepos)
            code_line = str(output)
        else:
            self.session.interpreter.direct_line.seek(0)
            code_line = str(self.session.lister.detokenise_compound_statement(
                    self.session.interpreter.direct_line)[0])
        # stop program execution
        self.session.interpreter.set_pointer(False)
        # create crash log file
        logname = datetime.now().strftime('pcbasic-crash-%Y%m%d-')
        logfile = tempfile.NamedTemporaryFile(suffix='.log', prefix=logname, dir=config.state_path, delete=False)
        # construct the message
        message = [
            (0x70, 'EXCEPTION\n'),
            (0x17, 'version   '),
            (0x1f, __version__),
            (0x17, '\npython    '),
            (0x1f, platform.python_version()),
            (0x17, '\nplatform  '),
            (0x1f, platform.platform()),
            (0x17, '\nstatement '),
            (0x1f, code_line + '\n\n'),
        ] + [
            (0x1f, '{0}:{1}, {2}\n'.format(os.path.split(s[0])[-1], s[1], s[2]))
            for s in stack[-4:]
        ] + [
            (0x1f,  '{0}:'.format(exc_type.__name__)),
            (0x17,  ' {0}\n\n'.format(str(exc_value))),
            (0x70,  'This is a bug in PC-BASIC.\n'),
            (0x17,  'Sorry about that. Please file a bug report at\n  '),
            (0x1f,  'https://github.com/robhagemans/pcbasic/issues'),
            (0x17,  '\nPlease include the messages above and '),
            (0x17,  'as much information as you can about what you were doing and how this happened. '),
            (0x17,  'If possible, please attach the log file\n  '),
            (0x1f,  logfile.name.encode('ascii', errors='replace')),
            (0x17,  '\nThis file contains detailed information about your program and this crash.\n'),
            (0x17,  'Thank you!\n'),
            (0x07,  ''),
        ]
        # create crash log
        crashlog = [
            b'PC-BASIC crash log',
            b'=' * 100,
            b''.join(text for _, text in message),
            b''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            self.repr_screen(),
            self.repr_variables(),
            self.repr_program(),
        ]
        self.session.program.bytecode.seek(1)
        crashlog.append('==== Program ='.ljust(100, '='))
        while True:
            _, line, _ = self.session.lister.detokenise_line(self.session.program.bytecode)
            if not line:
                break
            crashlog.append(str(line))
        crashlog.append('==== Options ='.ljust(100, '='))
        crashlog.append(repr(self.uargv))
        # clear screen for modal message
        screen = self.session.screen
        # choose attributes - this should be readable on VGA, MDA, PCjr etc.
        screen.screen(0, 0, 0, 0, new_width=80)
        screen.set_attr(0x17)
        screen.set_border(1)
        screen.clear()
        # show message on screen
        for attr, text in message:
            screen.set_attr(attr)
            screen.write(text.replace('\n', '\r'))
        # write crash log
        with logfile as f:
            f.write('\n'.join(crashlog))

    def step(self, token):
        """Dummy debug step."""


class Debugger(BaseDebugger):
    """Debugging helper."""

    debug_mode = True

    def __init__(self, session, uargv):
        """Initialise debugger."""
        BaseDebugger.__init__(self, session, uargv)
        self.watch_list = []
        session.extensions.add(DebugCommands(self))

    def step(self, token):
        """Execute traces and watches on a program step."""
        outstr = ''
        if self.debug_tron:
            linum = struct.unpack_from('<H', token, 2)
            outstr += '[%i]' % linum
        for (expr, outs) in self.watch_list:
            outstr += ' %s = ' % str(expr)
            outs.seek(2)
            try:
                val = self.session.parser.expression_parser.parse(outs)
                if isinstance(val, values.String):
                    outstr += '"%s"' % val.to_str()
                else:
                    outstr += values.to_repr(val, leading_space=False, type_sign=True)
            except Exception as e:
                logging.debug(str(type(e))+' '+str(e))
                traceback.print_tb(sys.exc_info()[2])
        if outstr:
            logging.debug(outstr)

    def bluescreen(self, e):
        """Pass through exceptions in debug mode."""
        # don't catch exceptions - so that testing script records them.
        raise e


class DebugCommands(object):
    # debugging commands

    def __init__(self, debugger):
        """Initialise."""
        self._debugger = debugger

    def dir(self):
        """Show debugging commands."""
        logging.debug('Available commands:\n' + '\n'.join(
            '    _%s: %s' % (n.upper(), getattr(self, n).__doc__) for n in dir(self) if not n.startswith('_')))

    def crash(self):
        """Simulate a crash."""
        try:
            raise DebugException()
        except DebugException as e:
            BaseDebugger.bluescreen(self._debugger, e)

    def restart(self):
        """Ctrl+Alt+Delete."""
        raise error.Reset()

    def exit(self):
        """Quit the session."""
        raise error.Exit()

    def trace(self, on=True):
        """Switch line number tracing on or off."""
        self._debugger.debug_tron = on

    def watch(self, expr):
        """Add an expression to the watch list."""
        outs = self._debugger.session.tokeniser.tokenise_line('?'+expr)
        self._debugger.watch_list.append((expr, outs))

    def showvariables(self):
        """Dump all variables to the log."""
        for s in self._debugger.repr_variables().split('\n'):
            logging.debug(s)

    def showscreen(self):
        """Copy the screen buffer to the log."""
        for s in self._debugger.repr_screen().split('\n'):
            logging.debug(s)

    def showprogram(self):
        """Write a marked-up hex dump of the program to the log."""
        for s in self._debugger.debugger.repr_program().split('\n'):
            logging.debug(s)
