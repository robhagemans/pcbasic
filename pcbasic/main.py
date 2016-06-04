"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import locale
import logging
import traceback
import threading
from Queue import Queue

# set locale - this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
locale.setlocale(locale.LC_ALL, '')

from .version import __version__
from . import ansipipe
from . import basic
from .basic import signals
from . import state
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
                launch_session(settings)
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

def launch_session(settings):
    """Start an interactive interpreter session."""
    from . import interface
    # initialise queues
    input_queue = Queue()
    video_queue = Queue()
    tone_queues = [Queue(), Queue(), Queue(), Queue()]
    message_queue = Queue()
    queues = (input_queue, video_queue, tone_queues, message_queue)
    # launch the BASIC thread
    thread = threading.Thread(
                target=run_session,
                args=(queues,), kwargs=settings.get_launch_parameters())
    thread.start()
    try:
        interface.run(
                settings.get_interface(),
                settings.get_video_parameters(), settings.get_audio_parameters(), *queues)
    except interface.InitFailed:
        logging.error('Failed to initialise interface.')
    finally:
        input_queue.put(signals.Event(signals.KEYB_QUIT))
        thread.join()

def run_session(queues, resume, state_file, wait, prog, commands, **session_params):
    """Run an interactive BASIC session."""
    if resume:
        session = state.zunpickle(state_file).attach(*queues)
    else:
        session = basic.Session(*queues, **session_params)
    with session:
        try:
            if prog:
                session.load_program(prog)
            for cmd in commands:
                session.execute(cmd)
            session.interact()
        except basic.Exit:
            # SYSTEM called during launch
            pass
        except basic.RunError as e:
            # only runtime errors that occur on interpreter launch are caught here
            # e.g. "File not Found" for --load parameter
            logging.error(e.message)
        finally:
            state.zpickle(session, state_file)
            if wait:
                session.pause('Press a key to close window')


if __name__ == "__main__":
    main()
