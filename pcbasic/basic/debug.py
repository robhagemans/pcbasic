"""
PC-BASIC - debug.py
DEBUG statement and utilities

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import traceback
import logging
import os
import platform
import struct
import io

from . import values
from . import error


def get_debugger(session, option_debug):
    """Create debugger."""
    if option_debug:
        return Debugger(session)
    else:
        return BaseDebugger(session)


class DebugException(Exception):
    """Test exception for debugging purposes"""
    def __str__(self):
        return self.__doc__


class BaseDebugger(object):
    """Only debug uncaught exceptions."""

    debug_mode = False

    def __init__(self, session):
        """Initialise debugger."""
        self.debug_tron = False
        self.session = session

    def bluescreen(self, e):
        """Display a modal exception message."""
        screen = self.session.screen
        screen.screen(0, 0, 0, 0, new_width=80)
        screen.clear()
        screen.init_mode()
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # log the standard python error
        logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        # format the error more readably on the screen
        screen.set_border(4)
        screen.set_attr(0x70)
        screen.write_line('EXCEPTION')
        screen.set_attr(15)
        if self.session.interpreter.run_mode:
            self.session.program.bytecode.seek(-1, 1)
            self.session.program.edit(screen,
                    self.session.program.get_line_number(
                            self.session.program.bytecode.tell()),
                            self.session.program.bytecode.tell())
            screen.write_line('\n')
        else:
            self.session.interpreter.direct_line.seek(0)
            screen.write_line(str(
                    self.session.lister.detokenise_compound_statement(
                            self.session.interpreter.direct_line)[0])+'\n')
        stack = traceback.extract_tb(exc_traceback)
        for s in stack[-4:]:
            screen.set_attr(15)
            screen.write_line('{0}:{1}, {2}'.format(os.path.split(s[0])[-1], s[1], s[2]))
            if s[3] is not None:
                screen.set_attr(7)
                screen.write_line('    {0}'.format(s[3]))
        exc_message = traceback.format_exception_only(exc_type, exc_value)[0]
        screen.set_attr(15)
        screen.write('{0}:'.format(exc_type.__name__))
        screen.set_attr(7)
        screen.write_line(' {0}'.format(str(exc_value)))
        screen.set_attr(0x70)
        screen.write_line('\nThis is a bug in PC-BASIC.')
        screen.set_attr(7)
        screen.write('Sorry about that. Please send the above messages to the bugs forum\nby e-mail to ')
        screen.set_attr(15)
        screen.write('bugs@discussion.pcbasic.p.re.sf.net')
        screen.set_attr(7)
        screen.write(' or file a bug\nreport at ')
        screen.set_attr(15)
        screen.write('https://github.com/robhagemans/pcbasic/issues')
        screen.set_attr(7)
        screen.write_line('. Please include')
        screen.write_line('as much information as you can about what you were doing and how this happened.')
        screen.write_line('Thank you!')
        screen.set_attr(7)
        self.session.interpreter.set_pointer(False)

    def debug_step(self, token):
        """Dummy debug step."""

    def debug_(self, debug_cmd):
        """Dummy debug exec."""


class Debugger(BaseDebugger):
    """Debugging helper."""

    debug_mode = True

    def __init__(self, session):
        """Initialise debugger."""
        BaseDebugger.__init__(self, session)
        self.watch_list = []

    def debug_step(self, token):
        """Execute traces and watches on a program step."""
        outstr = ''
        if self.debug_tron:
            linum = struct.unpack_from('<H', token, 2)
            outstr += '[%i]' % linum
        for (expr, outs) in self.watch_list:
            outstr += ' %s =' % str(expr)
            outs.seek(2)
            try:
                val = self.session.expression_parser.parse(outs)
                if isinstance(val, values.String):
                    outstr += '"%s"' % val.to_str()
                else:
                    outstr += values.to_repr(val, leading_space=False, type_sign=True)
            except Exception as e:
                logging.debug(str(type(e))+' '+str(e))
                traceback.print_tb(sys.exc_info()[2])
        if outstr:
            logging.debug(outstr)

    def debug_(self, debug_cmd):
        """Execute a debug command."""
        global debugger, session
        # make session available to debugging commands
        debugger = self
        session = self.session
        buf = io.BytesIO()
        save_stdout = sys.stdout
        sys.stdout = buf
        try:
            exec(debug_cmd)
        except DebugException:
            raise
        except error.Exit:
            raise
        except Exception as e:
            logging.debug(str(type(e))+' '+str(e))
            traceback.print_tb(sys.exc_info()[2])
        finally:
            sys.stdout = save_stdout
            logging.debug(buf.getvalue()[:-1]) # exclude \n


##############################################################################
# debugging commands

# module-globals for use by debugging commands
# these should be set (by debug_exec) before using any of the below
debugger = None
# convenient access to current session
session = None

def crash():
    """Simulate a crash."""
    raise DebugException()

def reset():
    """Ctrl+Alt+Delete."""
    raise error.Reset()

def exit():
    """Quit the session."""
    raise error.Exit()

def trace(on=True):
    """Switch line number tracing on or off."""
    debugger.debug_tron = on

def watch(expr):
    """Add an expression to the watch list."""
    outs = session.tokeniser.tokenise_line('?'+expr)
    debugger.watch_list.append((expr, outs))

def show_variables():
    """Dump all variables to the log."""
    logging.debug('==== Scalars ='.ljust(100, '='))
    logging.debug(str(debugger.session.scalars))
    logging.debug('==== Arrays ='.ljust(100, '='))
    logging.debug(str(debugger.session.arrays))
    logging.debug('==== Strings ='.ljust(100, '='))
    logging.debug(str(debugger.session.strings))

def show_screen():
    """Copy the screen buffer to the log."""
    logging.debug('  +' + '-'*session.screen.mode.width+'+')
    i = 0
    lastwrap = False
    for row in session.screen.apage.row:
        s = [ c[0] for c in row.buf ]
        i += 1
        outstr = '{0:2}'.format(i)
        if lastwrap:
            outstr += ('\\')
        else:
            outstr += ('|')
        outstr += (''.join(s))
        if row.wrap:
            logging.debug(outstr + '\\ {0:2}'.format(row.end))
        else:
            logging.debug(outstr + '| {0:2}'.format(row.end))
        lastwrap = row.wrap
    logging.debug('  +' + '-'*session.screen.mode.width+'+')

def show_program():
    """Write a marked-up hex dump of the program to the log."""
    prog = debugger.session.program
    code = prog.bytecode.getvalue()
    offset_val, p = 0, 0
    for key in sorted(prog.line_numbers.keys())[1:]:
        offset, linum = code[p+1:p+3], code[p+3:p+5]
        last_offset = offset_val
        offset_val = (struct.unpack('<H', offset)[0]
                                - (debugger.session.memory.code_start + 1))
        linum_val, = struct.unpack('<H', linum)
        logging.debug((code[p:p+1].encode('hex') + ' ' +
                        offset.encode('hex') + ' (+%03d) ' +
                        code[p+3:p+5].encode('hex') + ' [%05d] ' +
                        code[p+5:prog.line_numbers[key]].encode('hex')),
                     offset_val - last_offset, linum_val )
        p = prog.line_numbers[key]
    logging.debug(code[p:p+1].encode('hex') + ' ' +
                code[p+1:p+3].encode('hex') + ' (ENDS) ' +
                code[p+3:p+5].encode('hex') + ' ' + code[p+5:].encode('hex'))
