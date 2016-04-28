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
    import interpreter
    # set conversion output
    # first arg, if given, is mode; second arg, if given, is outfile
    mode = config.get('convert')
    infile = (config.get(0) or
              config.get('run') or config.get('load'))
    outfile = config.get(1)
    # keep uppercase first letter
    mode = mode[0].upper() if mode else 'A'
    session = interpreter.Session()
    files = session.files
    internal_disk = session.devices.internal_disk
    prog = session.program
    # load & save in different format
    try:
        prog_infile = None
        if infile:
            prog_infile = files.open_native_or_basic(infile)
        elif plat.has_stdin:
            # use StringIO buffer for seekability
            in_buffer = StringIO(sys.stdin.read())
            prog_infile = internal_disk.create_file_object(in_buffer, filetype='ABP', mode='I')
        if prog_infile:
            with prog_infile:
                prog.load(prog_infile, rebuild_dict=False)
        prog_outfile = None
        if outfile:
            # on save from command-line, use exact file name
            prog_outfile = internal_disk.create_file_object(open(outfile, 'wb'), filetype=mode, mode='O')
        elif plat.has_stdout:
            prog_outfile = internal_disk.create_file_object(sys.stdout, filetype=mode, mode='O')
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
    interface_name = config.get('interface') or 'graphical'
    nosound = config.get('nosound')
    video_params = {
        'force_display_size': config.get('dimensions'),
        'aspect': config.get('aspect'),
        'border_width': config.get('border'),
        'force_native_pixel': (config.get('scaling') == 'native'),
        'fullscreen': config.get('fullscreen'),
        'smooth': (config.get('scaling') == 'smooth'),
        'nokill': config.get('nokill'),
        'altgr': config.get('altgr'),
        'caption': config.get('caption'),
        'composite_monitor': (config.get('monitor') == 'composite'),
        'composite_card': config.get('video'),
        'copy_paste': config.get('copy-paste'),
        'pen': config.get('pen'),
        }
    pcjr_term = config.get('pcjr-term')
    if pcjr_term and not os.path.exists(pcjr_term):
        pcjr_term = os.path.join(plat.info_dir, pcjr_term)
    if not os.path.exists(pcjr_term):
        pcjr_term = ''
    peek_values = {}
    try:
        for a in config.get('peek'):
            seg, addr, val = a.split(':')
            peek_values[int(seg)*0x10 + int(addr)] = int(val)
    except (TypeError, ValueError):
        pass
    device_params = {
            key.upper()+':' : config.get(key)
            for key in ('lpt1', 'lpt2', 'lpt3', 'com1', 'com2', 'cas1')}
    max_list = config.get('max-memory')
    max_list[1] = max_list[1]*16 if max_list[1] else max_list[0]
    max_list[0] = max_list[0] or max_list[1]
    session_params = {
        'syntax': config.get('syntax'),
        'option_debug': config.get('debug'),
        'output_file': config.get(b'output'),
        'append': config.get(b'append'),
        'input_file': config.get(b'input'),
        'video_capabilities': config.get('video'),
        'codepage': config.get('codepage') or '437',
        'box_protect': not config.get('nobox'),
        'monitor': config.get('monitor'),
        # screen settings
        'screen_aspect': (3072, 2000) if config.get('video') == 'tandy' else (4, 3),
        'text_width': config.get('text-width'),
        'video_memory': config.get('video-memory'),
        'cga_low': config.get('cga-low'),
        'mono_tint': config.get('mono-tint'),
        'font': config.get('font'),
        # inserted keystrokes
        'keystring': config.get('keys').decode('string_escape').decode('utf-8'),
        # find program for PCjr TERM command
        'pcjr_term': pcjr_term,
        'option_shell': config.get('shell'),
        'double': config.get('double'),
        # device settings
        'device_params': device_params,
        'current_device': config.get(u'current-device'),
        'mount': config.get(u'mount'),
        'map_drives': config.get(u'map-drives'),
        'print_trigger': config.get('print-trigger'),
        'serial_buffer_size': config.get('serial-buffer-size'),
        # text file parameters
        'utf8': config.get('utf8'),
        'universal': not config.get('strict-newline'),
        # stdout echo (for filter interface)
        'echo_to_stdout': (config.get(b'interface') == u'none'),
        # keyboard settings
        'ignore_caps': not config.get('capture-caps'),
        'ctrl_c_is_break': config.get('ctrl-c-break'),
        # program parameters
        'max_list_line': 65535 if not config.get('strict-hidden-lines') else 65530,
        'allow_protect': config.get('strict-protect'),
        'allow_code_poke': config.get('allow-code-poke'),
        # max available memory to BASIC (set by /m)
        'max_memory': min(max_list) or 65534,
        # maximum record length (-s)
        'max_reclen': max(1, min(32767, config.get('max-reclen'))),
        # number of file records
        'max_files': config.get('max-files'),
        # first field buffer address (workspace size; 3429 for gw-basic)
        'reserved_memory': config.get('reserved-memory'),
    }
    try:
        with interpreter.SessionLauncher(**session_params) as launcher:
            try:
                interface.run(
                        launcher.input_queue, launcher.video_queue,
                        launcher.tone_queue, launcher.message_queue,
                        interface_name, nosound, **video_params)
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
