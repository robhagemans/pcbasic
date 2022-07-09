"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2021 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import os
import sys
import locale
import logging
import pkg_resources
import traceback

from . import basic
from . import state
from . import config
from .guard import ExceptionGuard, NOGUARD
from .basic import NAME, VERSION, LONG_VERSION, COPYRIGHT
from .basic import debug
from .interface import Interface, InitFailed
from .compat import stdio


def main(*arguments):
    """Wrapper for run() to deal with argv encodings, Ctrl-C, stdio and pipes."""
    try:
        run(*arguments)
    except KeyboardInterrupt:
        pass
    except:
        # without this except clause we seem to be dropping exceptions
        # probably due to the sys.stdout.close() hack below
        logging.error('Unhandled exception\n%s', traceback.format_exc())
    finally:
        # avoid sys.excepthook errors when piping output
        # http://stackoverflow.com/questions/7955138/addressing-sys-excepthook-error-in-bash-script
        try:
            sys.stdout.close()
        except:
            pass
        try:
            sys.stderr.close()
        except:
            pass

def run(*arguments):
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

def _show_usage():
    """Show usage description."""
    usage = pkg_resources.resource_string(__name__, 'data/USAGE.txt').decode('utf-8', 'replace')
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
    guard = ExceptionGuard(**settings.guard_params)
    try:
        Interface(guard, **settings.iface_params).launch(_run_session, **settings.launch_params)
    except InitFailed as e:
        logging.error(e)

def _run_session(
        interface=None, guard=NOGUARD,
        resume=False, debug=False, state_file=None,
        prog=None, commands=(), keys=u'', greeting=True, **session_params
    ):
    """Run an interactive BASIC session."""
    Session = basic.DebugSession if debug else basic.Session
    with Session(interface, **session_params) as s:
        with state.manage_state(s, state_file, resume) as session:
            with guard.protect(interface, session):
                if greeting:
                    session.greet()
                if prog:
                    with session.bind_file(prog) as progfile:
                        session.execute(b'LOAD "%s"' % (progfile,))
                session.press_keys(keys)
                for cmd in commands:
                    session.execute(cmd)
                session.interact()
