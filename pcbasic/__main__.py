#!/usr/bin/env python2

"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import shutil
import logging
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import traceback
import subprocess

import plat
import ansipipe
import printer

# declare to avoid pylint errors
config = None

def main():
    """ Initialise and do requested operations. """
    # make imported modules available in main module
    global config
    try:
        import config
        import debug
        if plat.system == 'Android':
            # resume from existing directory (or clear it if we're not resuming)
            if not config.get('resume') and os.path.exists(plat.temp_dir):
                shutil.rmtree(plat.temp_dir)
            if not os.path.exists(plat.temp_dir):
                os.mkdir(plat.temp_dir)
        # set up the logging system
        prepare_logging()
        if config.get('version'):
            # in version mode, print version and exit
            sys.stdout.write(plat.version + '\n')
            if config.get('debug'):
                debug.details()
        elif config.get('help'):
            # in help mode, print usage and exit
            with open(os.path.join(plat.info_dir, 'usage.txt')) as f:
                for line in f:
                    sys.stdout.write(line)
        elif config.get('convert'):
            # in converter mode, convert and exit
            convert()
        else:
            # otherwise, go into BASIC
            start_basic()
    finally:
        try:
            printer.wait()
            # clean up our temp dir if we made one
            if plat.temp_dir and plat.system != 'Android':
                shutil.rmtree(plat.temp_dir)
        except NameError:
            pass
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

def prepare_logging():
    """ Set up the logging system. """
    logfile = config.get('logfile')
    if config.get('version') or config.get('help'):
        formatstr = '%(message)s'
        loglevel = logging.INFO
    else:
        # logging setup before we import modules and may need to log errors
        formatstr = '%(levelname)s: %(message)s'
        if config.get('debug'):
            loglevel = logging.DEBUG
        else:
            loglevel = logging.INFO
    logging.basicConfig(format=formatstr, level=loglevel, filename=logfile)

def convert():
    """ Perform file format conversion. """
    import program
    import disk
    import error
    # set conversion output
    # first arg, if given, is mode; second arg, if given, is outfile
    mode = config.get('convert')
    infile = (config.get(0) or
              config.get('run') or config.get('load'))
    outfile = config.get(1)
    # keep uppercase first letter
    mode = mode[0].upper() if mode else 'A'
    # load & save in different format
    try:
        prog_infile = None
        if infile:
            prog_infile = disk.open_native_or_dos_filename(infile)
        elif plat.has_stdin:
            # use StringIO buffer for seekability
            in_buffer = StringIO(sys.stdin.read())
            prog_infile = disk.create_file_object(in_buffer, filetype='ABP', mode='I')
        if prog_infile:
            with prog_infile:
                program.load(prog_infile)
        prog_outfile = None
        if outfile:
            # on save from command-line, use exact file name
            prog_outfile = disk.create_file_object(open(outfile, 'wb'), filetype=mode, mode='O')
        elif plat.has_stdout:
            prog_outfile = disk.create_file_object(sys.stdout, filetype=mode, mode='O')
        if prog_outfile:
            with prog_outfile:
                program.save(prog_outfile)
    except error.RunError as e:
        logging.error(e.message)
    except EnvironmentError as e:
        logging.error(str(e))

def start_basic():
    """ Load & run programs and commands and hand over to interactive mode. """
    import program
    import interpreter
    import error
    import state
    import devices
    import disk
    import cassette
    import reset
    import sound
    import audio
    import video
    do_reset = False
    backend, console = None, None
    exit_error = ''
    # resume from saved emulator state if requested and available
    resume = config.get('resume') and state.load()
    try:
        # choose the video and sound backends
        backend, console = prepare_console()
        if resume:
            # override selected settings from command line
            cassette.override()
            disk.override()
            # suppress double prompt
            if not state.basic_state.execute_mode:
                state.basic_state.prompt = False
            interpreter.loop()
        else:
            # greet, load and start the interpreter
            interpreter.start()
    except KeyboardInterrupt:
        if config.get('debug'):
            raise
    except error.Reset:
        do_reset = True
    except error.RunError as e:
        exit_error = e.message
    except Exception as e:
        exit_error = "Unhandled exception\n%s" % traceback.format_exc()
    finally:
        try:
            audio.close()
        except (NameError, AttributeError) as e:
            logging.debug('Error on closing audio: %s', e)
        try:
            # fix the terminal on exit (important for ANSI terminals)
            video.close()
        except (NameError, AttributeError) as e:
            logging.debug('Error on closing video: %s', e)
        # delete state if resetting
        if do_reset:
            state.delete()
            if plat.system == 'Android':
                shutil.rmtree(plat.temp_dir)
        if exit_error:
            logging.error(exit_error)

def prepare_console():
    """ Initialise backend and console. """
    import state
    import backend
    import display
    import sound
    import console
    # we need this prepared for input to work,
    # even if we don't use any function from it
    import inputs
    interface = config.get('interface') or 'graphical'
    display.init(interface)
    sound.init('none' if config.get('nosound') else interface)
    if not state.loaded:
        console.init_mode()
    return backend, console


if __name__ == "__main__":
    main()
