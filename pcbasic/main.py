"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import locale
import logging
import traceback

# set locale - this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
locale.setlocale(locale.LC_ALL, '')

from .version import __version__
from . import ansipipe
from . import basic
from . import config


def main():
    """Initialise and perform requested operations."""
    try:
        with config.TemporaryDirectory(prefix='pcbasic-') as temp_dir:
            # get settings and prepare logging
            settings = config.Settings(temp_dir)
            command = settings.get_command()
            if command == 'version':
                # in version mode, print version and exit
                config.show_version(settings)
            elif command == 'help':
                # in help mode, print usage and exit
                config.show_usage()
            elif command == 'convert':
                # in converter mode, convert and exit
                convert(settings)
            else:
                # otherwise, start an interpreter session
                start_basic(settings)
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

def convert(settings):
    """Perform file format conversion."""
    mode, name_in, name_out = settings.get_converter_parameters()
    session = basic.Session(**settings.get_session_parameters())
    try:
        session.load_program(name_in, rebuild_dict=False)
        session.save_program(name_out, filetype=mode)
    except basic.RunError as e:
        logging.error(e.message)

def start_basic(settings):
    """Start an interactive interpreter session."""
    from . import interface
    interface_name = settings.get_interface()
    audio_params = settings.get_audio_parameters()
    video_params = settings.get_video_parameters()
    launch_params = settings.get_launch_parameters()
    try:
        with basic.launch_session(**launch_params) as queues:
            interface.run(interface_name, video_params, audio_params, *queues)
    except interface.InitFailed:
        logging.error('Failed to initialise interface.')

if __name__ == "__main__":
    main()
