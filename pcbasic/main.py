"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import os
import sys
import locale
import logging
import traceback

from . import config
from . import info
from .basic import Session
from .debug import DebugSession
from .guard import ExceptionGuard
from .basic import NAME, VERSION, LONG_VERSION, COPYRIGHT
from .interface import Interface, InitFailed
from .compat import stdio, resources, nullcontext
from .compat import script_entry_point_guard


def main(*arguments):
    """Initialise, parse arguments and perform requested operations."""
    with config.TemporaryDirectory(prefix='pcbasic-') as temp_dir:
        # get settings and prepare logging
        settings = config.Settings(temp_dir, arguments)
        if settings.version:
            # print version and exit
            _show_version(settings)
        elif settings.help:
            # print usage and exit
            _show_usage()
        elif settings.convert:
            # convert and exit
            _convert(settings)
        elif settings.interface:
            # start an interpreter session with interface
            _run_session_with_interface(settings)
        else:
            # start an interpreter session with standard i/o
            _run_session(**settings.launch_params)


def _show_usage():
    """Show usage description."""
    usage = resources.read_text(__package__ + '.' + 'data', 'USAGE.txt', errors='replace')
    stdio.stdout.write(usage)

def _show_version(settings):
    """Show version with optional debugging details."""
    if settings.debug:
        stdio.stdout.write(u'%s %s\n%s\n' % (NAME, LONG_VERSION, COPYRIGHT))
        stdio.stdout.write(info.get_platform_info())
    else:
        stdio.stdout.write(u'%s %s\n%s\n' % (NAME, VERSION, COPYRIGHT))

def _convert(settings):
    """Perform file format conversion."""
    mode, in_name, out_name = settings.conv_params
    with Session(**settings.session_params) as session:
        # binary stdin if no name supplied - use BytesIO buffer for seekability
        with session.bind_file(in_name or io.BytesIO(stdio.stdin.buffer.read())) as infile:
            session.execute(b'LOAD "%s"' % (infile,))
        with session.bind_file(out_name or stdio.stdout.buffer, create=True) as outfile:
            mode_suffix = b',%s' % (mode.encode('ascii'),) if mode.upper() in ('A', 'P') else b''
            session.execute(b'SAVE "%s"%s' % (outfile, mode_suffix))


def _run_session_with_interface(settings):
    """Start an interactive interpreter session."""
    try:
        interface = Interface(**settings.iface_params)
    except InitFailed as e: # pragma: no cover
        logging.error(e)
    else:
        exception_guard = ExceptionGuard(interface, **settings.guard_params)
        interface.launch(
            _run_session,
            interface=interface,
            exception_handler=exception_guard,
            **settings.launch_params
        )

def _run_session(
        interface=None, exception_handler=nullcontext,
        resume=False, debug=False, state_file=None,
        prog=None, commands=(), keys=u'', greeting=True, **session_params
    ):
    """Start or resume session, handle exceptions, suspend on exit."""
    if resume:
        try:
            session = Session.resume(state_file)
        except Exception as e:
            # if we were told to resume but can't, give up
            logging.critical('Failed to resume session from %s: %s' % (state_file, e))
            sys.exit(1)
    elif debug:
        session = DebugSession(**session_params)
    else:
        session = Session(**session_params)
    with exception_handler(session) as handler:
        with session:
            try:
                _operate_session(session, interface, prog, commands, keys, greeting)
            finally:
                try:
                    session.suspend(state_file)
                except Exception as e:
                    logging.error('Failed to save session to %s: %s', state_file, e)
    if exception_handler is not nullcontext and handler.exception_handled:
        _run_session(
            interface, exception_handler, resume=True, state_file=state_file, greeting=False
        )


def _operate_session(session, interface, prog, commands, keys, greeting):
    """Run an interactive BASIC session."""
    session.attach(interface)
    if greeting:
        session.greet()
    if prog:
        with session.bind_file(prog) as progfile:
            session.execute(b'LOAD "%s"' % (progfile,))
    session.press_keys(keys)
    for cmd in commands:
        session.execute(cmd)
    session.interact()
