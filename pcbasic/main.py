"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
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
from .metadata import NAME, VERSION, COPYRIGHT
from .basic import debug
from .interface import Interface, InitFailed

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
            show_version(settings)
        elif settings.help:
            # print usage and exit
            show_usage()
        elif settings.convert:
            # convert and exit
            convert(settings)
        elif settings.interface:
            # start an interpreter session with interface
            launch_session(settings)
        else:
            # start an interpreter session with standard i/o
            run_session(**settings.launch_params)

def show_usage():
    """Show usage description."""
    sys.stdout.write(pkg_resources.resource_string(__name__, 'data/USAGE.txt'))

def show_version(settings):
    """Show version with optional debugging details."""
    sys.stdout.write((u'%s %s\n%s\n' % (NAME, VERSION, COPYRIGHT)).encode(sys.stdout.encoding))
    if settings.debug:
        debug.show_platform_info()

def convert(settings):
    """Perform file format conversion."""
    mode, in_name, out_name = settings.conv_params
    with basic.Session(**settings.session_params) as session:
        # stdin if no name supplied - use io.BytesIO buffer for seekability
        with session.bind_file(in_name or io.BytesIO(sys.stdin.read())) as infile:
            session.execute(b'LOAD "%s"' % (infile,))
        with session.bind_file(out_name or sys.stdout, create=True) as outfile:
            mode_suffix = b',%s' % (mode,) if mode.upper() in (b'A', b'P') else b''
            session.execute(b'SAVE "%s"%s' % (outfile, mode_suffix))

def launch_session(settings):
    """Start an interactive interpreter session."""
    guard = ExceptionGuard(**settings.guard_params)
    try:
        Interface(guard, **settings.iface_params).launch(run_session, **settings.launch_params)
    except InitFailed as e:
        logging.error(e)

def run_session(
        interface=None, guard=NOGUARD,
        resume=False, debug=False, state_file=None,
        prog=None, commands=(), **session_params):
    """Run an interactive BASIC session."""
    Session = basic.DebugSession if debug else basic.Session
    with Session(interface, **session_params) as s:
        with state.manage_state(s, state_file, resume) as session:
            with guard.protect(interface, session):
                if prog:
                    with session.bind_file(prog) as progfile:
                        session.execute(b'LOAD "%s"' % (progfile,))
                for cmd in commands:
                    session.execute(cmd)
                session.interact()
