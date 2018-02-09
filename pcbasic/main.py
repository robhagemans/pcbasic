"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import locale
import logging
import pkg_resources
import traceback

# set locale - this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
locale.setlocale(locale.LC_ALL, '')

from .version import __version__
from . import ansipipe
from . import basic
from . import state
from . import config


def main(*arguments):
    """Wrapper for run() to deal with Ctrl-C, stdio and pipes."""
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
        command = settings.get_command()
        if command == 'version':
            # print version and exit
            show_version(settings)
        elif command == 'help':
            # print usage and exit
            show_usage()
        elif command == 'convert':
            # convert and exit
            convert(settings)
        elif settings.has_interface():
            # start an interpreter session with interface
            launch_session(settings)
        else:
            # start an interpreter session with standard i/o
            run_session(**settings.get_launch_parameters())

def show_usage():
    """Show usage description."""
    sys.stdout.write(pkg_resources.resource_string(__name__, 'USAGE.txt'))

def show_version(settings):
    """Show version with optional debugging details."""
    sys.stdout.write(__version__ + '\n')
    if settings.get('debug'):
        from pcbasic.basic import debug
        debug.show_platform_info()

def convert(settings):
    """Perform file format conversion."""
    mode, name_in, name_out = settings.get_converter_parameters()
    session = basic.Session(**settings.get_session_parameters())
    try:
        session.load_program(name_in)
        session.save_program(name_out, filetype=mode)
    except basic.BASICError as e:
        logging.error(e.message)

def launch_session(settings):
    """Start an interactive interpreter session."""
    from .interface import Interface, InitFailed
    try:
        Interface(**settings.get_interface_parameters()).launch(
                run_session, **settings.get_launch_parameters())
    except InitFailed:
        logging.error('Failed to initialise interface.')

def run_session(interface=None, resume=False, state_file=None,
                prog=None, commands=(), **session_params):
    """Run an interactive BASIC session."""
    with basic.Session(interface, **session_params) as s:
        with state.manage_state(s, state_file, resume) as session:
            try:
                if prog:
                    session.load_program(prog)
                for cmd in commands:
                    session.execute(cmd)
                session.interact()
            except basic.Exit:
                # SYSTEM called during launch
                pass


if __name__ == "__main__":
    main()
