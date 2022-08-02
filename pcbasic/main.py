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

from . import basic
from . import state
from . import config
from .guard import ExceptionGuard
from .basic import NAME, VERSION, LONG_VERSION, COPYRIGHT
from .basic import debug
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
            _launch_session(settings)
        else:
            # start an interpreter session with standard i/o
            _run_session(**settings.launch_params)

# api backward compatibility
run = main


def _show_usage():
    """Show usage description."""
    usage = resources.read_text(__package__ + '.' + 'data', 'USAGE.txt', errors='replace')
    stdio.stdout.write(usage)

def _show_version(settings):
    """Show version with optional debugging details."""
    if settings.debug:
        stdio.stdout.write(u'%s %s\n%s\n' % (NAME, LONG_VERSION, COPYRIGHT))
        stdio.stdout.write(debug.get_platform_info())
    else:
        stdio.stdout.write(u'%s %s\n%s\n' % (NAME, VERSION, COPYRIGHT))

def _convert(settings):
    """Perform file format conversion."""
    mode, in_name, out_name = settings.conv_params
    with basic.Session(**settings.session_params) as session:
        # binary stdin if no name supplied - use BytesIO buffer for seekability
        with session.bind_file(in_name or io.BytesIO(stdio.stdin.buffer.read())) as infile:
            session.execute(b'LOAD "%s"' % (infile,))
        with session.bind_file(out_name or stdio.stdout.buffer, create=True) as outfile:
            mode_suffix = b',%s' % (mode.encode('ascii'),) if mode.upper() in ('A', 'P') else b''
            session.execute(b'SAVE "%s"%s' % (outfile, mode_suffix))

def _launch_session(settings):
    """Start an interactive interpreter session."""
    try:
        interface = Interface(**settings.iface_params)
    except InitFailed as e: # pragma: no cover
        logging.error(e)
    else:
        exception_guard = ExceptionGuard(**settings.guard_params)
        interface.launch(
            _run_session,
            interface=interface,
            exception_guard=exception_guard,
            **settings.launch_params
        )

def _run_session(
        interface=None, exception_guard=None,
        resume=False, debug=False, state_file=None,
        prog=None, commands=(), keys=u'', greeting=True, **session_params
    ):
    """Run an interactive BASIC session."""
    if resume:
        session_class = state.load_session(state_file)
    elif debug:
        session_class = basic.DebugSession
    else:
        session_class = basic.Session
    session = session_class(**session_params)
    if not exception_guard:
        protect = nullcontext()
    else:
        protect = exception_guard.protect(interface, session)
    with protect:
        try:
            with session:
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
        finally:
            state.save_session(session, state_file)
