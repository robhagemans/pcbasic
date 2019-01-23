"""
PC-BASIC - config.py
Configuration file and command-line options parser

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io
import sys
import logging
import zipfile
import locale
import shutil
import codecs
import pkg_resources
from collections import deque

from .compat import iteritems, text_type, iterchar
from .compat import configparser
from .compat import WIN32, get_short_pathname, argv, getcwdu
from .compat import USER_CONFIG_HOME, USER_DATA_HOME
from .compat import split_quoted, split_pair
from .compat import console, stdout, stdin, stderr, IS_CONSOLE_APP
from .compat import TemporaryDirectory

from .data import CODEPAGES, FONTS, PROGRAMS, ICON
from .metadata import VERSION, NAME
from . import data


# base directory name
MAJOR_VERSION = u'.'.join(VERSION.split(u'.')[:2])
BASENAME = u'pcbasic-{0}'.format(MAJOR_VERSION)

# user configuration and state directories
USER_CONFIG_DIR = os.path.join(USER_CONFIG_HOME, BASENAME)
STATE_PATH = os.path.join(USER_DATA_HOME, BASENAME)

# default config file name
CONFIG_NAME = u'PCBASIC.INI'

# user and local config files
USER_CONFIG_PATH = os.path.join(USER_CONFIG_DIR, CONFIG_NAME)

# save-state file name
STATE_NAME = 'pcbasic.session'

# @: target drive for bundled programs
PROGRAM_PATH = os.path.join(STATE_PATH, u'bundled_programs')

# format for log files
LOGGING_FORMAT = u'[%(asctime)s.%(msecs)04d] %(levelname)s: %(message)s'
LOGGING_FORMATTER = logging.Formatter(fmt=LOGGING_FORMAT, datefmt=u'%H:%M:%S')

# drive letters except @, bytes constant
UPPERCASE = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

# bool strings
TRUES = (u'YES', u'TRUE', u'ON', u'1')
FALSES = (u'NO', u'FALSE', u'OFF', u'0')


##############################################################################
# version checks

# minimum required python versions
MIN_PYTHON2_VERSION = (2, 7, 12)
MIN_PYTHON3_VERSION = (3, 5, 0)

def _validate_version():
    """Initial validations."""
    # sys.version_info tuple's first three elements are guaranteed to be ints
    python_version = sys.version_info[:3]
    if (
            (python_version[0] == 2 and python_version < MIN_PYTHON2_VERSION) or
            (python_version[0] == 3 and python_version < MIN_PYTHON3_VERSION)
        ):
        msg = (
            'PC-BASIC requires Python version %d.%d.%d, ' % MIN_PYTHON2_VERSION +
            'version %d.%d.%d, or higher. ' % MIN_PYTHON3_VERSION +
            'You have %d.%d.%d.' % python_version
        )
        logging.fatal(msg)
        raise ImportError(msg)

# raise ImportError if incorrect Python version
_validate_version()


##############################################################################
# Default preset definitions
# For example, --preset=tandy will load all options in the [tandy] section.
# Preset options override default options.
# Presets can also be added by adding a section in brackets in the user configuration file
# e.g., a section headed [myconfig] will be loaded with --preset=myconfig

PRESETS = {
    u'strict': {
        u'hide-listing': u'65530',
        u'text-encoding': u'',
        u'soft-linefeed': u'False',
        u'hide-protected': u'True',
        u'allow-code-poke': u'True',
        u'prevent-close': u'True',
        u'ctrl-c-break': u'False',
    },
    u'basica': {
        u'reserved-memory': u'789',
    },
    u'pcjr': {
        u'syntax': u'pcjr',
        u'term': os.path.join(PROGRAM_PATH, 'PCTERM.BAS'),
        u'video': u'pcjr',
        u'font': u'vga',
        u'codepage': u'437',
        u'reserved-memory': u'4035',
        u'text-width': u'40',
        u'video-memory': u'16384',
    },
    u'tandy': {
        u'syntax': u'tandy',
        u'video': u'tandy',
        u'font': u'tandy2',
        u'codepage': u'437',
        u'aspect': u'3072,2000',
        u'max-reclen': u'255',
        u'reserved-memory': u'3240',
        u'video-memory': u'16384',
    },
    u'cga': {
        u'video': u'cga',
        u'font': u'cga',
        u'codepage': u'437',
        u'text-width': u'40',
    },
    u'ega': {
        u'video': u'ega',
        u'font': u'vga',
    },
    u'mda': {
        u'video': u'mda',
        u'font': u'cga,mda',
        u'codepage': u'437',
        u'monitor': u'mono',
    },
    u'hercules': {
        u'video': u'hercules',
        u'font': u'cga,mda',
        u'codepage': u'437',
        u'monitor': u'mono',
    },
    u'olivetti': {
        u'video': u'olivetti',
        u'font': u'cga,olivetti',
        u'codepage': u'437',
    },
    u'vga': {
        u'video': u'vga',
        u'font': u'vga',
        u'codepage': u'437',
    },
}

# by default, load what's in section [pcbasic] and override with anything
DEFAULT_SECTION = [u'pcbasic']


##############################################################################
# short-form arguments

SHORT_ARGS = {
    u'd': u'double',
    u'f': u'max-files',
    u's': u'max-reclen',
    u'b': u'interface=cli',
    u't': u'interface=text',
    u'n': u'interface=none',
    u'l': u'load',
    u'h': u'help',
    u'r': u'run',
    u'q': u'quit',
    u'e': u'exec',
    u'k': u'keys',
    u'v': u'version',
    u'w': u'wait',
    }


##############################################################################
# all long-form arguments

def _check_text_encoding(arg):
    """Check if text-encoding argument is acceptable."""
    try:
        codecs.lookup(arg)
    except LookupError:
        return False
    return True


# number of positional arguments
NUM_POSITIONAL = 2

ARGUMENTS = {
    u'input': {u'type': u'string', u'default': u'', },
    u'output': {u'type': u'string', u'default': u'', },
    u'interface': {
        u'type': u'string', u'default': u'',
        u'choices': (
            u'', u'none', u'cli', u'text', u'graphical',
            u'ansi', u'curses', u'pygame', u'sdl2'
        ),
    },
    u'sound': {
        u'type': u'string', u'default': u'',
        u'choices': (u'', u'none', u'beep', u'portaudio', u'interface'),
    },
    u'load': {u'type': u'string', u'default': u'', },
    u'run': {u'type': u'string', u'default': u'',  },
    u'convert': {u'type': u'string', u'default': u'', },
    u'help': {u'type': u'bool', u'default': False, },
    u'keys': {u'type': u'string', u'default': u'', },
    u'exec': {u'type': u'string', u'default': u'', },
    u'quit': {u'type': u'bool', u'default': False,},
    u'double': {u'type': u'bool', u'default': False,},
    u'max-files': {u'type': u'int', u'default': 3,},
    u'max-reclen': {u'type': u'int', u'default': 128,},
    u'serial-buffer-size': {u'type': u'int', u'default': 256,},
    u'peek': {u'type': u'string', u'list': u'*', u'default': [],},
    u'lpt1': {u'type': u'string', u'default': u'PRINTER:',},
    u'lpt2': {u'type': u'string', u'default': u'',},
    u'lpt3': {u'type': u'string', u'default': u'',},
    u'cas1': {u'type': u'string', u'default': u'',},
    u'com1': {u'type': u'string', u'default': u'',},
    u'com2': {u'type': u'string', u'default': u'',},
    u'codepage': {u'type': u'string', u'choices': CODEPAGES, u'default': u'437',},
    u'font': {
        u'type': u'string', u'list': u'*', u'choices': FONTS,
        u'default': [u'unifont', u'univga', u'freedos'],
    },
    u'dimensions': {u'type': u'int', u'list': 2, u'default': [],},
    u'fullscreen': {u'type': u'bool', u'default': False,},
    u'prevent-close': {u'type': u'bool', u'default': False,},
    u'debug': {u'type': u'bool', u'default': False,},
    u'hide-listing': {u'type': u'int', u'default': 65535,},
    u'hide-protected': {u'type': u'bool', u'default': False,},
    u'mount': {u'type': u'string', u'list': u'*', u'default': [],},
    u'resume': {u'type': u'bool', u'default': False,},
    u'syntax': {
        u'type': u'string', u'choices': (u'advanced', u'pcjr', u'tandy'),
        u'default': u'advanced',
    },
    u'term': {u'type': u'string', u'default': u'',},
    u'video': {
        u'type': u'string', u'default': 'vga',
        u'choices': (
            u'vga', u'ega', u'cga', u'mda',
            u'pcjr', u'tandy', u'hercules', u'olivetti'
        ),
    },
    u'text-encoding': {u'type': u'string', u'default': u'', u'check': _check_text_encoding},
    u'soft-linefeed': {u'type': u'bool', u'default': False,},
    u'border': {u'type': u'int', u'default': 5,},
    u'mouse-clipboard': {u'type': u'bool', u'default': True,},
    u'state': {u'type': u'string', u'default': u'',},
    u'monitor': {
        u'type': u'string',
        u'choices': (u'rgb', u'composite', u'green', u'amber', u'grey', u'mono'),
        u'default': u'rgb',
    },
    u'aspect': {u'type': u'int', u'list': 2, u'default': [4, 3],},
    u'scaling': {
        u'type': u'string', u'choices':(u'smooth', u'native', u'crisp'),
        u'default': u'smooth',
    },
    u'version': {u'type': u'bool', u'default': False,},
    u'config': {u'type': u'string', u'default': u'',},
    u'logfile': {u'type': u'string', u'default': u'',},
    # negative list length means 'optionally up to'
    u'max-memory': {u'type': u'int', u'list': -2, u'default': [65534, 4096]},
    u'allow-code-poke': {u'type': u'bool', u'default': False,},
    u'reserved-memory': {u'type': u'int', u'default': 3429,},
    u'caption': {u'type': u'string', u'default': NAME,},
    u'text-width': {u'type': u'int', u'choices':(u'40', u'80'), u'default': 80,},
    u'video-memory': {u'type': u'int', u'default': 262144,},
    u'shell': {u'type': u'string', u'default': u'',},
    u'ctrl-c-break': {u'type': u'bool', u'default': True,},
    u'wait': {u'type': u'bool', u'default': False,},
    u'current-device': {u'type': u'string', u'default': ''},
    u'extension': {u'type': u'string', u'list': u'*', u'default': []},
    u'options': {u'type': u'string', u'default': ''},
    # depecated argument, use text-encoding instead
    u'utf8': {u'type': u'bool', u'default': False,},
}


##########################################################################
# logging

class Lumberjack(object):
    """Logging manager."""

    def __init__(self):
        """Set up the global logger temporarily until we know the log stream."""
        # we use the awkward logging interface as we can only use basicConfig once
        # get the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # send to a buffer until we know where to log to
        self._logstream = io.StringIO()
        handler = logging.StreamHandler(self._logstream)
        handler.setFormatter(LOGGING_FORMATTER)
        root_logger.addHandler(handler)

    def reset(self):
        """Reset root logger."""
        # o dear o dear what a horrible API
        root_logger = logging.getLogger()
        # remove all old handlers: temporary ones we set as well as any default ones
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        return root_logger

    def prepare(self, logfile, debug):
        """Set up the global logger."""
        # get log stream and level from options
        loglevel = logging.DEBUG if debug else logging.INFO
        root_logger = self.reset()
        root_logger.setLevel(loglevel)
        if logfile:
            logstream = io.open(logfile, 'w', encoding='utf_8', errors='replace')
        else:
            logstream = stderr
        # write out cached logs
        logstream.write(self._logstream.getvalue())
        handler = logging.StreamHandler(logstream)
        handler.setFormatter(LOGGING_FORMATTER)
        root_logger.addHandler(handler)


##############################################################################
# settings parser

def _store_bundled_programs(PROGRAM_PATH):
    """Retrieve contents of BASIC programs."""
    for name in PROGRAMS:
        with io.open(os.path.join(PROGRAM_PATH, name), 'wb') as f:
            f.write(data.read_program_file(name))



class Settings(object):
    """Read and retrieve command-line settings and options."""

    def __init__(self, temp_dir, arguments):
        """Initialise settings."""
        # arguments should be unicode
        if not arguments:
            self._uargv = argv[1:]
        else:
            self._uargv = list(arguments)
        lumberjack = Lumberjack()
        try:
            self._temp_dir = temp_dir
            # create state path if needed
            if not os.path.exists(STATE_PATH):
                os.makedirs(STATE_PATH)
            # create user config file if needed
            if not os.path.exists(USER_CONFIG_PATH):
                try:
                    os.makedirs(USER_CONFIG_DIR)
                except OSError:
                    pass
                self.build_default_config_file(USER_CONFIG_PATH)
            # create @: drive if not present
            if not os.path.exists(PROGRAM_PATH):
                os.makedirs(PROGRAM_PATH)
                # unpack bundled programs
                _store_bundled_programs(PROGRAM_PATH)
            # store options in options dictionary
            self._options = self._retrieve_options(self._uargv)
        except:
            # avoid losing exception messages occuring while logging was disabled
            lumberjack.reset()
            raise
        # prepare global logger for use by main program
        lumberjack.prepare(self.get('logfile'), self.get('debug'))

    def _retrieve_options(self, uargv):
        """Retrieve command line and option file options."""
        # convert command line arguments to string dictionary form
        remaining = self._get_arguments(uargv)
        # unpack any packages
        package = self._parse_package(remaining)
        # get preset groups from specified config file
        preset_dict = self._parse_config(remaining)
        # parse default presets nested in config presets
        preset_dict = {
            _key: self._merge_arguments(
                self._parse_presets(_dict, self.default_config),
                _dict
            )
            for _key, _dict in iteritems(preset_dict)
        }
        # set defaults based on presets
        args = self._parse_presets(remaining, preset_dict)
        # local config file settings override preset settings
        self._merge_arguments(args, preset_dict[u'pcbasic'])
        # find unrecognised arguments
        unrecognised = ((_k, _v) for _k, _v in iteritems(args) if _k not in ARGUMENTS)
        for key, value in unrecognised:
            logging.warning(
                'Ignored unrecognised option `%s=%s` in configuration file', key, value
            )
        args = {_k: _v for _k, _v in iteritems(args) if _k in ARGUMENTS}
        # parse rest of command line
        self._merge_arguments(args, self._parse_args(remaining))
        # parse GW-BASIC style options
        self._parse_gw_options(args)
        # clean up arguments
        self._convert_types(args)
        if package:
            # do not resume from a package
            args['resume'] = False
        return args

    def get(self, name, get_default=True):
        """Get value of option; choose whether to get default or None if unspecified."""
        try:
            value = self._options[name]
            if value is None or value == u'':
                raise KeyError
        except KeyError:
            if get_default:
                try:
                    value = ARGUMENTS[name][u'default']
                except KeyError:
                    if name in range(NUM_POSITIONAL):
                        return u''
            else:
                value = None
        return value

    ##########################################################################
    # session parameters

    @property
    def session_params(self):
        """Return a dictionary of parameters for the Session object."""
        # don't parse any options on --resume
        if self.get('resume'):
            return {}
        # preset PEEK values
        peek_values = {}
        try:
            for a in self.get('peek'):
                seg, addr, val = a.split(u':')
                peek_values[int(seg)*0x10 + int(addr)] = int(val)
        except (TypeError, ValueError):
            pass
        # devices and mounts
        device_params = {
            key.upper()+':' : self.get(key)
            for key in ('lpt1', 'lpt2', 'lpt3', 'com1', 'com2', 'cas1')
        }
        current_device, mount_dict = self._get_drives()
        # memory setting
        max_list = self.get('max-memory')
        max_list[1] = max_list[1]*16 if max_list[1] else max_list[0]
        max_list[0] = max_list[0] or max_list[1]
        # codepage parameters
        codepage_params = self.get('codepage').split(u':')
        codepage_dict = data.read_codepage(codepage_params[0])
        nobox = len(codepage_params) > 1 and codepage_params[1] == u'nobox'
        # video parameters
        video_params = self.get('video').split(u':')
        # redirects
        params = self._get_redirects()
        params.update({
            'syntax': self.get('syntax'),
            'video': video_params[0],
            'codepage': codepage_dict,
            'box_protect': not nobox,
            'monitor': self.get('monitor'),
            # screen settings
            'text_width': self.get('text-width'),
            'video_memory': self.get('video-memory'),
            'font': data.read_fonts(codepage_dict, self.get('font')),
            # inserted keystrokes
            # we first need to encode the unicode to bytes before we can decode it
            # this preserves unicode as \x (if latin-1) and \u escapes
            'keys': self.get('keys').encode('ascii', 'backslashreplace').decode('unicode-escape'),
            # find program for PCjr TERM command
            'term': self.get('term'),
            'shell': self.get('shell'),
            'double': self.get('double'),
            # device settings
            'devices': device_params,
            'current_device': current_device,
            'mount': mount_dict,
            'serial_buffer_size': self.get('serial-buffer-size'),
            # text file parameters
            'textfile_encoding': self.get('text-encoding'),
            'soft_linefeed': self.get('soft-linefeed'),
            # keyboard settings
            'ctrl_c_is_break': self.get('ctrl-c-break'),
            # program parameters
            'hide_listing': self.get('hide-listing'),
            'hide_protected': self.get('hide-protected'),
            'allow_code_poke': self.get('allow-code-poke'),
            'rebuild_offsets': not self.get('convert'),
            # max available memory to BASIC (set by /m)
            'max_memory': min(max_list) or 65534,
            # maximum record length (-s)
            'max_reclen': max(1, min(32767, self.get('max-reclen'))),
            # number of file records
            'max_files': self.get('max-files'),
            # first field buffer address (workspace size; 3429 for gw-basic)
            'reserved_memory': self.get('reserved-memory'),
            'peek_values': peek_values,
            'extension': self.get('extension'),
            # ignore key buffer in console-based interfaces, to allow pasting text in console
            'check_keybuffer_full': self.get('interface') not in ('cli', 'text', 'ansi', 'curses'),
            # following GW, don't write greeting for redirected input or command-line filter run
            'greeting': (not params['input_streams']),
        })
        # deprecated arguments
        if self.get('utf8', get_default=False) is not None:
            if self.get('text-encoding', get_default=False) is not None:
                logging.warning(
                    'Deprecated option `utf8` ignored: `text-encoding` takes precedence.'
                )
            else:
                logging.warning('Option `utf8` is deprecated; use `text-encoding=utf-8` instead.')
                params['textfile_encoding'] = u'utf-8' if self.get('utf8') else u''
        return params

    def _get_redirects(self):
        """Determine which i/o streams to attach."""
        input_streams, output_streams = [], []
        # explicit redirects
        # input redirects
        infile_params = self.get('input').split(u':')
        if infile_params[0].upper() in (u'STDIO', u'STDIN'):
            if u'RAW' in (_x.upper() for _x in infile_params):
                input_streams.append(stdin.buffer)
            else:
                input_streams.append(stdin)
        else:
            if len(infile_params) > 1 and infile_params[0].upper() == u'FILE':
                infile = infile_params[1]
            else:
                infile = infile_params[0]
            if infile:
                try:
                    input_streams.append(io.open(infile, 'rb'))
                except EnvironmentError as e:
                    logging.warning(u'Could not open input file %s: %s', infile, e.strerror)
        # output redirects
        outfile_params = self.get('output').split(u':')
        if outfile_params[0].upper() in (u'STDIO', u'STDOUT'):
            if u'RAW' in (_x.upper() for _x in outfile_params):
                output_streams.append(stdout.buffer)
            else:
                output_streams.append(stdout)
        else:
            if len(outfile_params) > 1 and outfile_params[0].upper() == u'FILE':
                outfile_params = outfile_params[1:]
            outfile = outfile_params[0]
            append = len(outfile_params) > 1 and outfile_params[1].lower() == u'append'
            if outfile:
                try:
                    output_streams.append(io.open(outfile, 'ab' if append else 'wb'))
                except EnvironmentError as e:
                    logging.warning(u'Could not open output file %s: %s', outfile, e.strerror)
        # implicit stdio redirects
        # add stdio if redirected or no interface
        if stdin not in input_streams and stdin.buffer not in input_streams:
            if IS_CONSOLE_APP and not stdin.isatty():
                # redirected on console; use bytes stream
                input_streams.append(stdin.buffer)
            elif IS_CONSOLE_APP and not self.interface:
                # no interface & on console; use unicode stream
                input_streams.append(stdin)
        # redirect output as well if input is redirected, but not the other way around
        # this is because (1) GW-BASIC does this from the DOS prompt
        # (2) otherwise we don't see anything - we quit after input closes
        # isatty is also false if we run as a GUI exe, so check that here
        if stdout not in output_streams and stdout.buffer not in output_streams:
            if IS_CONSOLE_APP and (not stdout.isatty() or not stdin.isatty()):
                output_streams.append(stdout.buffer)
            elif IS_CONSOLE_APP and not self.interface:
                output_streams.append(stdout)
        return {
            'output_streams': output_streams,
            'input_streams': input_streams,
        }

    def _get_drives(self):
        """Assign disk locations to disk devices."""
        # always get current device
        current_device = self.get('current-device').upper()
        # build mount dictionary
        mount_list = self.get('mount', False)
        mount_dict = {}
        if mount_list is not None:
            for a in mount_list:
                # the last one that's specified will stick
                try:
                    letter, path = a.split(u':', 1)
                    letter = letter.encode('ascii', errors='replace').upper()
                    # take abspath first to ensure unicode, realpath gives bytes for u'.'
                    path = os.path.realpath(os.path.abspath(path))
                    if not os.path.isdir(path):
                        logging.warning(u'Could not mount %s', a)
                    else:
                        mount_dict[letter] = (path, u'')
                except (TypeError, ValueError) as e:
                    logging.warning(u'Could not mount %s: %s', a, e)
        else:
            if WIN32:
                # get all drives in use by windows
                # if started from CMD.EXE, get the 'current working dir' for each drive
                # if not in CMD.EXE, there's only one cwd
                save_current = getcwdu()
                for letter in iterchar(UPPERCASE):
                    try:
                        os.chdir(letter + b':')
                        cwd = get_short_pathname(getcwdu()) or getcwdu()
                    except EnvironmentError:
                        # doesn't exist or can't access, do not mount this drive
                        pass
                    else:
                        # must not start with \\
                        path, cwd = cwd[:3], cwd[3:]
                        mount_dict[letter] = (path, cwd)
                os.chdir(save_current)
                if not current_device:
                    try:
                        current_device = (
                            os.path.abspath(save_current).split(u':')[0].encode('ascii')
                        )
                    except UnicodeEncodeError:
                        pass
            else:
                # non-Windows systems simply have 'Z:' set to their their cwd by default
                mount_dict[b'Z'] = (getcwdu(), u'')
                current_device = b'Z'
        # fallbacks for current device
        if (
                current_device != 'CAS1' and
                (not current_device or current_device not in mount_dict.keys())
            ):
            if mount_dict:
                # if not set or not sensible, set current device to lowest available
                current_device = sorted(mount_dict.keys())[0]
            else:
                # if nothing mounted at all and not set to CAS1, current device will be @:
                current_device = b'@'
        # directory for bundled BASIC programs accessible through @:
        mount_dict[b'@'] = (PROGRAM_PATH, u'')
        return current_device, mount_dict


    ##########################################################################
    # interface parameters

    @property
    def interface(self):
        """Run with interface."""
        return self.get('interface') != 'none'

    @property
    def iface_params(self):
        """Dict of interface parameters."""
        interface = self.get('interface')
        # categorical interfaces
        categories = {
            'text': ('ansi', 'curses'),
            'graphical': ('sdl2', 'pygame'),
        }
        if not interface:
            # default: try graphical first, then text, then cli
            iface_list = categories['graphical'] + categories['text'] + ('cli',)
        else:
            try:
                iface_list = categories[interface]
            except KeyError:
                iface_list = (interface,)
        iface_params = {
            'try_interfaces': iface_list,
            'audio_override': self.get('sound') != 'interface' and self.get('sound'),
        }
        iface_params.update(self._get_video_parameters())
        iface_params.update(self._get_audio_parameters())
        return iface_params

    def _get_video_parameters(self):
        """Return a dictionary of parameters for the video plugin."""
        return {
            'dimensions': self.get('dimensions'),
            'aspect_ratio': self.get('aspect'),
            'border_width': self.get('border'),
            'scaling': self.get('scaling'),
            'fullscreen': self.get('fullscreen'),
            'prevent_close': self.get('prevent-close'),
            'caption': self.get('caption'),
            'mouse_clipboard': self.get('mouse-clipboard'),
            'icon': ICON,
            'wait': self.get('wait'),
            }

    def _get_audio_parameters(self):
        """Return a dictionary of parameters for the audio plugin."""
        return {}


    ##########################################################################
    # launch parameters

    @property
    def launch_params(self):
        """Dict of launch parameters."""
        # build list of commands to execute on session startup
        commands = []
        if not self.get('resume'):
            run = (self.get(0) != '' and self.get('load') == '') or (self.get('run') != '')
            # treat colons as CRs
            commands = split_quoted(self.get('exec'), split_by=u':', quote=u"'", strip_quotes=True)
            # note that executing commands (or RUN) will suppress greeting
            if run:
                commands.append('RUN')
            if self.get('quit'):
                commands.append('SYSTEM')
        launch_params = {
            'prog': self.get('run') or self.get('load') or self.get(0),
            'resume': self.get('resume'),
            'state_file': self._get_state_file(),
            'commands': commands,
            'debug': self.get('debug'),
            }
        launch_params.update(self.session_params)
        return launch_params

    def _get_state_file(self):
        """Name of state file"""
        state_name = self.get('state') or STATE_NAME
        if not os.path.exists(state_name):
            state_name = os.path.join(STATE_PATH, state_name)
        return state_name


    ##########################################################################
    # other calls

    @property
    def guard_params(self):
        """Dict of exception guard parameters."""
        return {
            'uargv': self._uargv,
            'log_dir': STATE_PATH,
            }

    @property
    def conv_params(self):
        """Get parameters for file conversion."""
        # conversion output
        # first arg, if given, is mode; second arg, if given, is outfile
        mode = self.get('convert')
        # keep uppercase first letter
        mode = mode[0].upper() if mode else 'A'
        name_in = (self.get(0) or self.get('run') or self.get('load'))
        name_out = self.get(1)
        return mode, name_in, name_out

    @property
    def version(self):
        """Version operating mode."""
        return self.get('version')

    @property
    def help(self):
        """Help operating mode."""
        return self.get('help')

    @property
    def convert(self):
        """Converter operating mode."""
        return self.get('convert')

    @property
    def debug(self):
        """Debugging mode."""
        return self.get('debug')


    ##########################################################################
    # general argument parsing

    def _append_short_args(self, args, key, value):
        """Append short arguments and value to dict."""
        for i, short_arg in enumerate(key[1:]):
            try:
                skey, svalue = split_pair(SHORT_ARGS[short_arg], u'=')
                if not svalue and not skey:
                    continue
                if (not svalue) and i == len(key)-2:
                    # assign value to last argument specified
                    _append_arg(args, skey, value)
                else:
                    _append_arg(args, skey, svalue)
            except KeyError:
                logging.warning(u'Ignored unrecognised option `-%s`', short_arg)

    def _get_arguments(self, argv):
        """Convert arguments to dictionary."""
        args = {}
        arg_deque = deque(argv)
        # positional arguments must come before any options
        for pos in range(NUM_POSITIONAL):
            if not arg_deque or arg_deque[0].startswith(u'-'):
                break
            args[pos] = arg_deque.popleft()
        while arg_deque:
            arg = arg_deque.popleft()
            key, value = split_pair(arg, u'=')
            if not value:
                if arg_deque and not arg_deque[0].startswith(u'-') and u'=' not in arg_deque[0]:
                    value = arg_deque.popleft()
            if key:
                if key[0:2] == u'--':
                    if key[2:]:
                        _append_arg(args, key[2:], value)
                elif key[0] == u'-':
                    self._append_short_args(args, key, value)
                else:
                    logging.warning(u'Ignored surplus positional argument `%s`', arg)
            else:
                logging.warning(u'Ignored unrecognised option `=%s`', value)
        return args

    def _parse_presets(self, remaining, conf_dict):
        """Parse presets"""
        presets = DEFAULT_SECTION
        try:
            argdict = {u'preset': remaining.pop(u'preset')}
        except KeyError:
            argdict = {}
        # apply default presets, including nested presets
        while True:
            # get dictionary of default config
            for p in presets:
                try:
                    self._merge_arguments(argdict, conf_dict[p])
                except KeyError:
                    if p not in DEFAULT_SECTION:
                        logging.warning(u'Ignored undefined preset "%s"', p)
            # look for more presets in expended arglist
            try:
                presets = self._to_list(u'preset', argdict.pop(u'preset'))
            except KeyError:
                break
        return argdict

    def _parse_package(self, remaining):
        """Unpack BAZ package, if specified, and make its temp dir current."""
        # first positional arg: program or package name
        package = None
        try:
            arg_package = remaining[0]
        except KeyError:
            pass
        else:
            if os.path.isdir(arg_package):
                os.chdir(arg_package)
                remaining.pop(0)
                package = arg_package
            elif zipfile.is_zipfile(arg_package):
                remaining.pop(0)
                # extract the package to a temp directory
                # and make that the current dir for our run
                zipfile.ZipFile(arg_package).extractall(path=self._temp_dir)
                os.chdir(self._temp_dir)
                # if the zip-file contains only a directory at the top level,
                # then move into that directory. E.g. all files in package.zip
                # could be under the directory package/
                contents = os.listdir(u'.')
                if len(contents) == 1:
                    os.chdir(contents[0])
                # recursively rename all files to all-caps to avoid case issues on Unix
                # collisions: the last file renamed overwrites earlier ones
                for root, dirs, files in os.walk(u'.', topdown=False):
                    for name in dirs + files:
                        try:
                            os.rename(os.path.join(root, name), os.path.join(root, name.upper()))
                        except OSError:
                            # if we can't rename, ignore
                            pass
                package = arg_package
        # make package setting available
        return package

    def _parse_config(self, remaining):
        """Find the correct config file and read it."""
        # always read default config files; private config overrides system config
        # we update a whole preset at once, there's no joining of settings.
        conf_dict = PRESETS.copy()
        conf_dict.update(self._read_config_file(USER_CONFIG_PATH))
        # find any local overriding config file & read it
        config_file = None
        try:
            config_file = remaining.pop(u'config')
        except KeyError:
            if os.path.exists(CONFIG_NAME):
                config_file = CONFIG_NAME
        if config_file:
            conf_dict.update(self._read_config_file(config_file))
        return conf_dict

    def _read_config_file(self, config_file):
        """Read config file."""
        try:
            config = configparser.RawConfigParser(allow_no_value=True)
            # use utf_8_sig to ignore a BOM if it's at the start of the file
            # (e.g. created by Notepad)
            with io.open(config_file, 'r', encoding='utf_8_sig', errors='replace') as f:
                config.readfp(WhitespaceStripper(f))
        except (configparser.Error, IOError):
            logging.warning(
                u'Error in configuration file %s. Configuration not loaded.', config_file
            )
            return {u'pcbasic': {}}
        presets = {header: dict(config.items(header)) for header in config.sections()}
        return presets

    def _parse_args(self, remaining):
        """Retrieve command line options."""
        # set arguments
        known = list(ARGUMENTS.keys()) + list(range(NUM_POSITIONAL))
        args = {d: remaining[d] for d in remaining if d in known}
        not_recognised = {d: remaining[d] for d in remaining if d not in known}
        for d in not_recognised:
            if not_recognised[d]:
                logging.warning(
                    u'Ignored unrecognised command-line argument `%s=%s`', d, not_recognised[d]
                )
            else:
                logging.warning(u'Ignored unrecognised command-line argument `%s`', d)
        return args

    def _parse_gw_options(self, args):
        """Parse GW-BASIC-style options."""
        # GWBASIC invocation, for reference:
        # GWBASIC [prog] [<inp] [[>]>outp] [/f:n] [/i] [/s:n] [/c:n] [/m:[n][,m]] [/d]
        #   /d      Allow double-precision ATN, COS, EXP, LOG, SIN, SQR, and TAN.
        #   /f:n    Set maximum number of open files to n. Default is 3.
        #           Each additional file reduces free memory by 322 bytes.
        #   /s:n    Set the maximum record length for RANDOM files.
        #           Default is 128, maximum is 32768.
        #   /c:n    Set the COM receive buffer to n bytes.
        #           If n==0, disable the COM ports.
        #   /i      Statically allocate file control blocks and data buffer.
        #           NOTE: this appears to be always the case in GW-BASIC, as here.
        #   /m:n,m  Set the highest memory location to n (default 65534) and maximum
        #           BASIC memory to m*16 bytes (default is all available).
        options = args.pop('options', '')
        for option in options.split(u' '):
            if not option:
                continue
            if option.startswith(u'<'):
                args['input'] = option[1:]
            elif option.startswith(u'>'):
                if option[1] == u'>':
                    args['output'] = option[2:] + u':append'
                else:
                    args['output'] = option[1:]
            elif option.startswith(u'/'):
                option = option.lower()
                split = option[1:].split(u':')
                if len(split) == 1:
                    if option[1] == u'd':
                        args['double'] = True
                    elif option[1] == u'i':
                        pass
                elif len(split) == 2:
                    if option[1] == u'f':
                        args['max-files'] = split[1]
                    elif option[1] == u's':
                        args['max-reclen'] = split[1]
                    elif option[1] == u'c':
                        args['serial-buffer-size'] = split[1]
                    elif option[1] == u'm':
                        args['max-memory'] = split[1]
            else:
                # positional argument
                args[0] = option
        return args


    ################################################

    def _merge_arguments(self, target_dict, new_dict):
        """Update target_dict with new_dict. Lists of indefinite length are appended."""
        for a in new_dict:
            try:
                if (a in target_dict and ARGUMENTS[a][u'list'] == u'*' and target_dict[a]):
                    target_dict[a] += u',' + new_dict[a]
                    continue
            except KeyError:
                pass
            # override
            target_dict[a] = new_dict[a]
        return target_dict

    def _convert_types(self, args):
        """Convert arguments to required type and list length."""
        for name in args:
            try:
                args[name] = self._to_list(name, args[name], ARGUMENTS[name][u'list'])
            except KeyError:
                # not a list
                args[name] = self._parse_type(name, args[name])

    ##########################################################################
    # type conversions

    def _parse_type(self, d, arg):
        """Convert argument to required type."""
        if d not in ARGUMENTS:
            return arg
        if u'choices' in ARGUMENTS[d]:
            arg = arg.lower()
        first_arg = arg.split(u':')[0]
        if u'type' in ARGUMENTS[d]:
            if (ARGUMENTS[d][u'type'] == u'int'):
                arg = self._to_int(d, arg)
            elif (ARGUMENTS[d][u'type'] == u'bool'):
                arg = self._to_bool(d, arg)
        if u'choices' in ARGUMENTS[d]:
            if first_arg and first_arg not in ARGUMENTS[d][u'choices']:
                logging.warning(
                    u'Value "%s=%s" ignored; should be one of (%s)',
                    d, arg, u', '.join(text_type(x) for x in ARGUMENTS[d][u'choices'])
                )
                arg = u''
        if u'check' in ARGUMENTS[d]:
            if arg and not ARGUMENTS[d][u'check'](first_arg):
                logging.warning(u'Value "%s=%s" ignored; not recognised', d, arg)
                arg = u''
        return arg

    def _to_list(self, argname, strval, length='*'):
        """Convert list strings to typed lists."""
        lst = strval.split(u',')
        if lst == [u'']:
            if length == '*':
                return []
            elif length < 0:
                return [None] * (-length)  # pylint: disable=invalid-unary-operand-type
            else:
                return None
        parsed = (self._parse_type(argname, _arg) for _arg in lst)
        lst = [_arg for _arg in parsed if _arg]
        # negative length: optional up-to
        if length != u'*' and length < 0:
            lst += [None] * (-length-len(lst))  # pylint: disable=invalid-unary-operand-type
        if length != u'*' and (len(lst) > abs(length) or len(lst) < length):
            logging.warning(
                u'Option "%s=%s" ignored, should have %d elements',
                argname, strval, abs(length)
            )
            lst = []
        return lst

    def _to_bool(self, argname, strval):
        """Convert bool string to bool. Empty string (i.e. specified) means True."""
        if strval == u'':
            return True
        try:
            if strval.upper() in TRUES:
                return True
            elif strval.upper() in FALSES:
                return False
        except AttributeError:
            logging.warning(u'Option "%s=%s" ignored; should be a boolean', argname, strval)
        return None

    def _to_int(self, argname, strval):
        """Convert int string to int."""
        if strval:
            try:
                return int(strval)
            except ValueError:
                logging.warning(u'Option "%s=%s" ignored; should be an integer', argname, strval)
        return None


    ##########################################################################
    # write config file

    def build_default_config_file(self, file_name):
        """Write a default config file."""
        header = (
            u"# PC-BASIC configuration file.\n"
            u"# Edit this file to change your default settings or add presets.\n"
            u"# Changes to this file will not affect any other users of your computer.\n"
            u"# All lines starting with # are comments and have no effect.\n"
            u"# Thus, to use one of the example options below, "
            u"you need to remove the # at the start of the line.\n"
            u"\n"
            u"[pcbasic]\n"
            u"# Use the [pcbasic] section to specify options you want to be enabled by default.\n"
            u"# See the documentation or run pcbasic -h for a list of available options.\n"
            u"# for example (for version '%s'):\n" % VERSION
        )
        footer = (
            u"\n\n# To add presets, create a section header between brackets and put the \n"
            u"# options you need below it, like this:\n"
            u"# [your_preset]\n"
            u"# border=0\n"
            u"# \n"
            u"# You will then be able to load these options with --preset=your_preset.\n"
            u"# If you choose the same name as a system preset, PC-BASIC will use your\n"
            u"# options for that preset and not the system ones. This is not recommended.\n"
        )
        argnames = sorted(ARGUMENTS.keys())
        try:
            with io.open(file_name, 'w', encoding='utf_8_sig', errors='replace') as f:
                f.write(header)
                for a in argnames:
                    try:
                        f.write(
                            u'## choices: %s\n' %
                            u', '.join(u'%s' % (_s,) for _s in ARGUMENTS[a][u'choices'])
                        )
                    except(KeyError, TypeError):
                        pass
                    try:
                        # check if it's a list
                        ARGUMENTS[a][u'list']
                        formatted = u','.join(u'%s' % (_s,) for _s in ARGUMENTS[a][u'default'])
                    except(KeyError, TypeError):
                        formatted = u'%s' % (ARGUMENTS[a][u'default'],)
                    f.write(u'#%s=%s\n' % (a, formatted))
                f.write(footer)
        except (OSError, IOError):
            # can't create file, ignore. we'll get a message later.
            pass



##############################################################################
# utilities

def _append_arg(args, key, value):
    """Update a single list-type argument by appending a value."""
    if key in args and args[key]:
        if value:
            args[key] += u',' + value
    else:
        args[key] = value


class WhitespaceStripper(object):
    """File wrapper for ConfigParser that strips leading whitespace."""

    def __init__(self, file):
        """Initialise to file object."""
        self._file = file

    def readline(self):
        """Read a line and strip whitespace (but not EOL)."""
        return self._file.readline().lstrip(u' \t')

    def __next__(self):
        """Make iterable for Python 3."""
        line = self.readline()
        if not line:
            raise StopIteration()
        return line

    # iterability not actually needed in Python 2, but this keeps pylint happy
    next = __next__

    def __iter__(self):
        """We are iterable."""
        return self
