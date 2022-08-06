"""
PC-BASIC - guard
Crash guard

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io
import sys
import logging
import platform
import tempfile
import traceback
import webbrowser
import json
from datetime import datetime
from contextlib import contextmanager
from subprocess import check_output, CalledProcessError

from .basic.base import error, signals
from .basic import VERSION, LONG_VERSION, Session
from .compat import BrokenPipeError, is_broken_pipe, text_type
from . import info


class ExceptionGuard(object):
    """Context manager to handle uncaught exceptions."""

    def __init__(self, interface, log_dir=u'', uargv=()):
        """Initialise crash guard."""
        self._interface = interface
        self._uargv = uargv
        self._log_dir = log_dir
        self._session = None

    def __call__(self, session):
        """Complete initialisation."""
        self._session = session
        return self

    def __enter__(self):
        """Enter context guard."""
        self.exception_handled = None
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Handle exceptions."""
        success = False
        if not exc_type or exc_type == error.Reset:
            return success
        if is_broken_pipe(exc_value):
            # BrokenPipeError may be raised by shell pipes, handled at entry point
            # see docs.python.org/3/library/signal.html#note-on-sigpipe
            return success
        try:
            success = _bluescreen(
                self._session, self._interface,
                self._uargv, self._log_dir,
                exc_type, exc_value, exc_traceback
            )
            if success:
                # we still want to show the exception on the log
                logging.error(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                self.exception_handled = exc_value
        except error.Exit:
            pass
        except BaseException as e:
            logging.error(e)
            raise
        return success


LOG_PATTERN = u'crash-%Y%m%d-'
CAPTION = u'System error. Please file a bug report. Press <Enter> to resume.'

REPORT_TEMPLATE="""
10 ' ** modal crash report **
20 SCREEN 0,0,0,0: WIDTH 80: COLOR 7,1,1: CLS: KEY OFF
100 ' print the report
110 WHILE -1
120   READ FG%, BG%, S$, NL%: COLOR FG%, BG%: PRINT S$;
130   IF NL% = 255 THEN 200
140   IF NL% THEN PRINT
150 WEND
200 ' bottom line
210 LOCATE 25,1: COLOR 1,7: PRINT "Press <Enter> to resume.";
220 COLOR 15,1: PRINT " It is recommended that you save any unsaved work.";
230 LOCATE 23,1
900 ' exit
910 COLOR 7,1: END
1000 ' template
1010 DATA 1,7,"PC-BASIC SYSTEM ERROR",0, 7,1,"",1
1020 DATA 7,1,"version   ",0, 15,1,"{version}",1
1030 DATA 7,1,"python    ",0, 15,1,"{python_version}",1
1040 DATA 7,1,"platform  ",0, 15,1,"{os_version}",1
1050 DATA 7,1,"interface ",0, 15,1,"{interface}",1
1060 DATA 7,1,"statement ",0, 15,1,"{statement}",1
1070 DATA 7,1,"",1
1080 DATA 15,1,"{traceback_0}",1
1090 DATA 15,1,"{traceback_1}",1
1100 DATA 15,1,"{traceback_2}",1
1110 DATA 15,1,"{traceback_3}",1
1120 DATA 15,1,"{exc_type}: ",0, 7,1,"{exc_value}",1
1130 DATA 7,1,"",1
1140 DATA 1,7,"This is a bug in PC-BASIC.",0, 7,1,"",1
1150 DATA 7,1,"Sorry about that. You can help improve PC-BASIC:",1
1160 DATA 7,1,"- Please file a bug report at",1
1170 DATA 15,1,"  {bug_url}",1
1180 DATA 7,1,"- Please include the full crash log stored at",1
1190 DATA 15,1,"  {crashlog}",1
1200 DATA 7,1,"",255
"""

def _bluescreen(session, iface, argv, log_dir, exc_type, exc_value, exc_traceback):
    """Process crash information and write reports."""
    # retrieve information from the defunct session
    session_info = _debrief_session(session)
    # interface information
    if iface:
        iface_name = u'%s, %s' % (type(iface._video).__name__, type(iface._audio).__name__)
    else:
        iface_name = u'--'
    # platform information
    python_version = u'%s [%s] %s' % (
        platform.python_version(), u' '.join(platform.architecture()),
        getattr(sys, 'frozen', u'') or u''
    )
    # format traceback
    # make sure the list is long enough if the traceback is not
    stack = traceback.extract_tb(exc_traceback)
    traceback_lines=[
        u'{0}:{1}, {2}'.format(os.path.basename(s[0]), s[1], s[2])
        for s in stack[-4:]
    ] + [u''] * 4
    # standard traceback format
    python_traceback=traceback.format_exception(exc_type, exc_value, exc_traceback)
    # write crash log and get its name
    log_file_name = _write_crashlog(
        log_dir, argv, python_traceback,
        **session_info
    )
    # display modal message on the interface
    do_resume = _show_report(
        iface, iface_name, python_version, session_info['code_line'],
        traceback_lines, exc_type, exc_value,
        log_file_name
    )
    return do_resume


def _debrief_session(session):
    # hide further output from defunct session
    session.attach(None)
    info = dict(
        # get session information
        repr_text_screen=session.info.repr_text_screen(),
        repr_scalars=session.info.repr_scalars(),
        repr_arrays=session.info.repr_arrays(),
        repr_strings=session.info.repr_strings(),
        repr_program=session.info.repr_program(),
        # obtain statement being executed
        code_line=session.info.get_current_code(as_type=text_type),
        # get code listing
        listing=session.execute('LIST', as_type=text_type),
    )
    return info


def _get_exception_info(exc_type, exc_value, exc_traceback):
    """Format the traceback."""
    stack = traceback.extract_tb(exc_traceback)
    exception_info = dict(
        # make sure the list is long enough if the traceback is not
        traceback_lines=[
            u'{0}:{1}, {2}'.format(os.path.basename(s[0]), s[1], s[2])
            for s in stack[-4:]
        ] + [u''] * 4,
        # standard traceback format
        python_traceback=traceback.format_exception(exc_type, exc_value, exc_traceback)
    )
    return exception_info


def _write_crashlog(
        log_dir, argv, python_traceback,
        repr_text_screen,
        repr_scalars,
        repr_arrays,
        repr_strings,
        repr_program,
        code_line,
        listing
    ):
    def separator(title):
        return u'==== {} ='.format(title).ljust(100, u'=')


    # create crash log
    crashlog = [
        u'PC-BASIC crash log',
        u'=' * 100,
        code_line, u'',
        separator('Traceback'), u''.join(python_traceback),
        separator('Version'), info.get_version_info(),
        separator('Platform'), info.get_platform_info(),
        separator('Options'), repr(argv), u'',
        separator('Screen Pages'), repr_text_screen,
        separator('Scalars'), repr_scalars,
        separator('Arrays'), repr_arrays,
        separator('Strings'), repr_strings,
        separator('Program Buffer'), repr_program, u'',
        separator('Program'), listing,
    ]
    # create crash log file
    logname = datetime.now().strftime(LOG_PATTERN)
    logfile = tempfile.NamedTemporaryFile(
        mode='wb', suffix='.log', prefix=logname, dir=log_dir, delete=False,
    )
    with logfile as f:
        for line in crashlog:
            f.write(line.encode('utf-8', 'replace'))
            f.write(b'\n')
    # open text file
    webbrowser.open(logfile.name)
    return logfile.name


def _show_report(iface, iface_name, python_version, code_line, traceback_lines, exc_type, exc_value, log_file_name):
    """Show a crash report on the interface."""
    resume = False
    with Session(output_streams='stdio' if not iface else ()) as session:
        # display report
        # construct the message
        message = REPORT_TEMPLATE.format(
            version=LONG_VERSION,
            python_version=python_version,
            os_version=platform.platform(),
            interface=iface_name,
            statement=code_line,
            traceback_0=traceback_lines[0],
            traceback_1=traceback_lines[1],
            traceback_2=traceback_lines[2],
            traceback_3=traceback_lines[3],
            exc_type=u'{0}'.format(exc_type.__name__),
            exc_value=u'{0}'.format(exc_value),
            bug_url=u'https://github.com/robhagemans/pcbasic/issues',
            crashlog=log_file_name,
        )
        session.execute(message)
        session.execute('RUN')
        session.attach(iface)
    if not iface:
        return False
    while True:
        signal = iface.pause(CAPTION)
        if signal.event_type == signals.KEYB_DOWN and signal.params[0] == '\r':
            return True
        elif signal.event_type == signals.QUIT:
            return False
