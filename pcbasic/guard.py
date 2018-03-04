"""
PC-BASIC - guard
Crash guard

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import platform
import traceback
import logging
import tempfile
from datetime import datetime
from contextlib import contextmanager

from basic.metadata import VERSION
from basic.base import error, signals


LOG_PATTERN = u'pcbasic-crash-%Y%m%d-'
PAUSE_MESSAGE = u'Fatal error. Press a key to close this window'


class NoGuard(object):
    """Null context manager."""

    @contextmanager
    def protect(self, *args, **kwargs):
        yield

NOGUARD = NoGuard()


class ExceptionGuard(object):
    """Context manager to handle uncaught exceptions."""

    def __init__(self, log_dir=u'', uargv=()):
        """Initialise crash guard."""
        self._uargv = uargv
        self._log_dir = log_dir

    @contextmanager
    def protect(self, interface, session):
        """Crash context guard."""
        try:
            yield
        except (error.Exit, error.Reset):
            raise
        except BaseException:
            self._impl = session._impl
            if not self._bluescreen(*sys.exc_info()):
                raise
            interface.pause(PAUSE_MESSAGE)

    def _bluescreen(self, exc_type, exc_value, exc_traceback):
        """Display modal message"""
        if not self._impl:
            return False
        # log the standard python error
        stack = traceback.extract_tb(exc_traceback)
        logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        # obtain statement being executed
        if self._impl.interpreter.run_mode:
            codestream = self._impl.program.bytecode
            bytepos = codestream.tell() - 1
            from_line = self._impl.program.get_line_number(bytepos)
            codestream.seek(self._impl.program.line_numbers[from_line]+1)
            _, output, textpos = self._impl.lister.detokenise_line(codestream, bytepos)
            code_line = str(output)
        else:
            self._impl.interpreter.direct_line.seek(0)
            code_line = str(self._impl.lister.detokenise_compound_statement(
                    self._impl.interpreter.direct_line)[0])
        # stop program execution
        self._impl.interpreter.set_pointer(False)
        # create crash log file
        logname = datetime.now().strftime(LOG_PATTERN)
        logfile = tempfile.NamedTemporaryFile(
                suffix='.log', prefix=logname, dir=self._log_dir, delete=False)
        # construct the message
        message = [
            (0x70, 'FATAL ERROR\n'),
            (0x17, 'version   '),
            (0x1f, VERSION.encode('ascii')),
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
            (0x17,  'Sorry about that. '),
            (0x17,  'To help improve PC-BASIC, '),
            (0x70,  'please file a bug report'),
            (0x17,  ' at\n  '),
            (0x1f,  'https://github.com/robhagemans/pcbasic/issues'),
            (0x17,  '\nPlease include the messages above and '),
            (0x17,  'as much information as you can about what you were doing and how this happened. '),
            (0x17,  'If possible, please attach the log file\n  '),
            (0x1f,  logfile.name.encode('ascii', errors='replace')),
            (0x17,  '\nThank you!\n\n'),
            (0x70,  'This message has been copied onto the clipboard. You can paste it with Ctrl-V.'),
            (0x17, '\n\nPress a key to close this window.\n'),
        ]
        # create crash log
        crashlog = [
            'PC-BASIC crash log',
            '=' * 100,
            ''.join(text for _, text in message),
            ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            '==== Screen Pages ='.ljust(100, '='),
            str(self._impl.display.text_screen),
            '==== Scalars ='.ljust(100, '='),
            str(self._impl.scalars),
            '==== Arrays ='.ljust(100, '='),
            str(self._impl.arrays),
            '==== Strings ='.ljust(100, '='),
            str(self._impl.strings),
            '==== Program Buffer ='.ljust(100, '='),
            str(self._impl.program),
        ]
        self._impl.program.bytecode.seek(1)
        crashlog.append('==== Program ='.ljust(100, '='))
        while True:
            _, line, _ = self._impl.lister.detokenise_line(self._impl.program.bytecode)
            if not line:
                break
            crashlog.append(str(line))
        crashlog.append('==== Options ='.ljust(100, '='))
        crashlog.append(repr(self._uargv))
        # clear screen for modal message
        # choose attributes - this should be readable on VGA, MDA, PCjr etc.
        self._impl.display.screen(0, 0, 0, 0, new_width=80)
        self._impl.display.set_attr(0x17)
        self._impl.display.set_border(1)
        self._impl.display.text_screen.clear()
        # show message on screen
        for attr, text in message:
            self._impl.display.set_attr(attr)
            self._impl.display.text_screen.write(text.replace('\n', '\r'))
        # write crash log
        crashlog = b'\n'.join(crashlog)
        with logfile as f:
            f.write(crashlog)
        # put on clipboard
        # note that log contains raw non-ascii bytes. don't risk codepage logic here, use cp437
        self._impl.queues.video.put(signals.Event(
                signals.VIDEO_SET_CLIPBOARD_TEXT, (crashlog.decode('cp437', 'replace'), False)))
        return True
