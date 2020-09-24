"""
PC-BASIC - guard
Crash guard

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import logging
import platform
import tempfile
import traceback
import json
from datetime import datetime
from contextlib import contextmanager
from subprocess import check_output, CalledProcessError

from .metadata import VERSION
from .basic.base import error, signals
from .data import get_data, ResourceFailed


LOG_PATTERN = u'crash-%Y%m%d-'
PAUSE_MESSAGE = u'Fatal error. Press a key to close this window'


class NoGuard(object):
    """Null context manager."""

    @contextmanager
    def protect(self, *args, **kwargs):
        yield

NOGUARD = NoGuard()

try:
    RELEASE_ID = json.loads(get_data('release.json'))
    TAG = RELEASE_ID[u'tag']
    COMMIT = RELEASE_ID[u'commit']
    TIMESTAMP = RELEASE_ID[u'timestamp']
except ResourceFailed:
    TAG = u''
    TIMESTAMP = u''
    try:
        COMMIT = check_output(
            ['git', 'describe', '--always'], cwd=os.path.dirname(__file__)
        ).strip().decode('ascii', 'ignore')
    except (CalledProcessError, EnvironmentError):
        COMMIT = u'unknown'


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
            if not self._bluescreen(session._impl, interface, *sys.exc_info()):
                raise
            interface.pause(PAUSE_MESSAGE)

    def _bluescreen(self, impl, iface, exc_type, exc_value, exc_traceback):
        """Display modal message"""
        if not impl:
            return False
        if iface:
            iface_name = u'%s, %s' % (type(iface._video).__name__, type(iface._audio).__name__)
        else:
            iface_name = u'--'
        # log the standard python error
        stack = traceback.extract_tb(exc_traceback)
        logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        # obtain statement being executed
        if impl.interpreter.run_mode:
            codestream = impl.program.bytecode
            bytepos = codestream.tell() - 1
            from_line = impl.program.get_line_number(bytepos)
            try:
                codestream.seek(impl.program.line_numbers[from_line]+1)
                _, output, textpos = impl.lister.detokenise_line(codestream, bytepos)
                code_line = bytes(output)
            except KeyError:
                code_line = b'<could not retrieve line number %d>' % from_line
        else:
            impl.interpreter.direct_line.seek(0)
            code_line = bytes(
                impl.lister.detokenise_compound_statement(impl.interpreter.direct_line)[0]
            )
        # don't risk codepage logic here, use cp437
        code_line = code_line.decode('cp437', 'replace')
        # stop program execution
        impl.interpreter.set_pointer(False)
        # create crash log file
        logname = datetime.now().strftime(LOG_PATTERN)
        logfile = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.log', prefix=logname, dir=self._log_dir, delete=False
        )
        # construct the message
        frozen = getattr(sys, 'frozen', u'') or u''
        message = [
            (0x70, u'FATAL ERROR\n'),
            (0x17, u'version   '),
            (0x1f, u'%s [%s] %s %s' % (VERSION, COMMIT, TAG, TIMESTAMP)),
            (0x17, u'\npython    '),
            (0x1f, u'%s [%s] %s' % (
                platform.python_version(), u' '.join(platform.architecture()), frozen
            )),
            (0x17, u'\nplatform  '),
            (0x1f, platform.platform()),
            (0x17, u'\ninterface '),
            (0x1f, iface_name),
            (0x17, u'\nstatement '),
            (0x1f, code_line + u'\n\n'),
        ] + [
            (0x1f, u'{0}:{1}, {2}\n'.format(os.path.split(s[0])[-1], s[1], s[2]))
            for s in stack[-4:]
        ] + [
            (0x1f, u'{0}:'.format(exc_type.__name__)),
            (0x17, u' {0}\n\n'.format(exc_value)),
            (0x70, u'This is a bug in PC-BASIC.\n'),
            (0x17, u'Sorry about that. '),
            (0x17, u'To help improve PC-BASIC, '),
            (0x70, u'please file a bug report'),
            (0x17, u' at\n  '),
            (0x1f, u'https://github.com/robhagemans/pcbasic/issues'),
            (0x17, u'\nPlease include the messages above and '),
            (0x17, u'as much information as you can about what you were doing and '),
            (0x17, u'how this happened. Please attach the log file\n  '),
            (0x1f, logfile.name),
            (0x17, u'\nThank you!\n\n'),
            (0x17, u'Press a key to close this window.'),
        ]
        bottom = (0x70,
            u'This message has been copied onto the clipboard. You can paste it with Ctrl-V.'
        )
        # create crash log
        crashlog = [
            u'PC-BASIC crash log',
            u'=' * 100,
            u''.join(text for _, text in message),
            u''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            u'==== Screen Pages ='.ljust(100, u'='),
            repr(impl.display.text_screen),
            u'==== Scalars ='.ljust(100, u'='),
            repr(impl.scalars),
            u'==== Arrays ='.ljust(100, u'='),
            repr(impl.arrays),
            u'==== Strings ='.ljust(100, u'='),
            repr(impl.strings),
            u'==== Program Buffer ='.ljust(100, u'='),
            repr(impl.program),
        ]
        impl.program.bytecode.seek(1)
        crashlog.append(u'==== Program ='.ljust(100, u'='))
        while True:
            _, line, _ = impl.lister.detokenise_line(impl.program.bytecode)
            if not line:
                break
            crashlog.append(bytes(line).decode('cp437', 'replace'))
        crashlog.append(u'==== Options ='.ljust(100, u'='))
        crashlog.append(repr(self._uargv))
        # clear screen for modal message
        # choose attributes - this should be readable on VGA, MDA, PCjr etc.
        impl.display.screen(0, 0, 0, 0, new_width=80)
        impl.display.set_attr(0x17)
        impl.display.set_border(1)
        impl.display.text_screen.clear()
        impl.display.text_screen._bottom_row_allowed = True
        # show message on screen
        for attr, text in message:
            impl.display.set_attr(attr)
            impl.display.text_screen.write(text.replace('\n', '\r').encode('cp437', 'replace'))
        impl.display.text_screen.set_pos(25, 1)
        impl.display.set_attr(bottom[0])
        impl.display.text_screen.write(bottom[1].replace('\n', '\r').encode('cp437', 'replace'))
        # write crash log
        crashlog = u'\n'.join(
            line.decode('cp437', 'replace') if isinstance(line, bytes) else line
            for line in crashlog
        )
        with logfile as f:
            f.write(crashlog.encode('utf-8', 'replace'))
        # put on clipboard
        impl.queues.video.put(signals.Event(signals.VIDEO_SET_CLIPBOARD_TEXT, (crashlog, False)))
        return True
