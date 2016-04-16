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
import platform
import subprocess
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import traceback

import plat
import ansipipe
import config
import error

# video plugins
# these are unused but need to be initialised and packaged
import video_none
import video_ansi
import video_cli
import video_curses
import video_pygame
import video_sdl2

# audio plugins
import audio_none
import audio_beep
import audio_pygame
import audio_sdl2


def main():
    """ Initialise and do requested operations. """
    try:
        # set up the logging system
        prepare_logging()
        if config.get('version'):
            # in version mode, print version and exit
            show_version()
        elif config.get('help'):
            # in help mode, print usage and exit
            show_usage()
        elif config.get('convert'):
            # in converter mode, convert and exit
            convert()
        else:
            # otherwise, start an interpreter session
            start_basic()
    finally:
        # clean up our temp dir if we made one
        if plat.temp_dir:
            shutil.rmtree(plat.temp_dir)
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
    import files
    import disk
    import interpreter
    # set conversion output
    # first arg, if given, is mode; second arg, if given, is outfile
    mode = config.get('convert')
    infile = (config.get(0) or
              config.get('run') or config.get('load'))
    outfile = config.get(1)
    # keep uppercase first letter
    mode = mode[0].upper() if mode else 'A'
    # FIXME - need to remove Session dependence from Devices, replace with class to hold main event loop only
    session = interpreter.Session()
    files = files.Files(session.devices, max_files=3)
    # load & save in different format
    try:
        prog_infile = None
        if infile:
            prog_infile = files.open_native_or_basic(infile)
        elif plat.has_stdin:
            # use StringIO buffer for seekability
            in_buffer = StringIO(sys.stdin.read())
            prog_infile = disk.create_file_object(in_buffer, filetype='ABP', mode='I')
        prog = program.Program(address=4717)
        if prog_infile:
            with prog_infile:
                prog.load(prog_infile, rebuild_dict=False)
        prog_outfile = None
        if outfile:
            # on save from command-line, use exact file name
            prog_outfile = disk.create_file_object(open(outfile, 'wb'), filetype=mode, mode='O')
        elif plat.has_stdout:
            prog_outfile = disk.create_file_object(sys.stdout, filetype=mode, mode='O')
        if prog_outfile:
            with prog_outfile:
                prog.save(prog_outfile)
    except error.RunError as e:
        logging.error(e.message)
    except EnvironmentError as e:
        logging.error(str(e))

def start_basic():
    """ Start an interactive interpreter session. """
    import interface
    import interpreter
    try:
        with interpreter.SessionLauncher():
            try:
                interface.run()
            except interface.InitFailed:
                logging.error('Failed to initialise interface.')
    except error.RunError as e:
        # only runtime errors that occur on interpreter launch are caught here
        # e.g. "File not Found" for --load parameter
        logging.error(e.message)
    except Exception:
        logging.error('Unhandled exception\n%s' % traceback.format_exc())

def show_usage():
    """ Show usage description. """
    with open(os.path.join(plat.info_dir, 'usage.txt')) as f:
        for line in f:
            sys.stdout.write(line)

def show_version():
    """ Show version with optional debugging details. """
    sys.stdout.write(plat.version + '\n')
    if not config.get('debug'):
        return
    logging.info('\nPLATFORM')
    logging.info('os: %s %s %s', plat.system, platform.processor(), platform.version())
    logging.info('python: %s %s', sys.version.replace('\n',''), ' '.join(platform.architecture()))
    logging.info('\nMODULES')
    # try numpy before pygame to avoid strange ImportError on FreeBSD
    modules = ('numpy', 'win32api', 'sdl2', 'pygame', 'curses', 'pexpect', 'serial', 'parallel')
    for module in modules:
        try:
            m = __import__(module)
        except ImportError:
            logging.info('%s: --', module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    version = getattr(m, version_attr)
                    logging.info('%s: %s', module, version)
                    break
                except AttributeError:
                    pass
            else:
                logging.info('available\n')
    if plat.system != 'Windows':
        logging.info('\nEXTERNAL TOOLS')
        tools = ('lpr', 'paps', 'beep', 'xclip', 'xsel', 'pbcopy', 'pbpaste')
        for tool in tools:
            try:
                location = subprocess.check_output('command -v %s' % tool, shell=True).replace('\n','')
                logging.info('%s: %s', tool, location)
            except Exception as e:
                logging.info('%s: --', tool)


if __name__ == "__main__":
    main()
