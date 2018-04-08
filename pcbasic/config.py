"""
PC-BASIC - config.py
Configuration file and command-line options parser

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import ConfigParser
import logging
import zipfile
import codecs
import locale
import tempfile
import shutil
import platform
import pkg_resources
import string
from collections import deque

from .metadata import VERSION, NAME
from .data import CODEPAGES, FONTS, PROGRAMS, ICON
from .compat import WIN32, get_short_pathname, get_unicode_argv, HAS_CONSOLE
from .compat import USER_CONFIG_HOME, USER_DATA_HOME
from .compat import split_quoted
from . import data


MIN_PYTHON_VERSION = (2, 7, 12)

# base directory name
MAJOR_VERSION = u'.'.join(VERSION.split(u'.')[:2])
BASENAME = u'pcbasic-{0}'.format(MAJOR_VERSION)

# user configuration and state directories
USER_CONFIG_DIR = os.path.join(USER_CONFIG_HOME, BASENAME)
STATE_PATH = os.path.join(USER_DATA_HOME, BASENAME)

# @: target drive for bundled programs
PROGRAM_PATH = os.path.join(STATE_PATH, u'bundled_programs')


def get_logger(logfile=None):
    """Use the awkward logging interface as we can only use basicConfig once."""
    l = logging.getLogger(__name__)
    l.setLevel(logging.INFO)
    if logfile:
        h = logging.FileHandler(logfile, mode=b'w')
    else:
        h = logging.StreamHandler()
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter(u'%(levelname)s: %(message)s'))
    l.addHandler(h)
    return l

def append_arg(args, key, value):
    """Update a single list-type argument by appending a value."""
    if key in args and args[key]:
        if value:
            args[key] += u',' + value
    else:
        args[key] = value

def safe_split(s, sep):
    """Split an argument by separator, always return two elements."""
    slist = s.split(sep, 1)
    s0 = slist[0]
    if len(slist) > 1:
        s1 = slist[1]
    else:
        s1 = u''
    return s0, s1

def store_bundled_programs(PROGRAM_PATH):
    """Retrieve contents of BASIC programs."""
    for name in PROGRAMS:
        with open(os.path.join(PROGRAM_PATH, name), 'wb') as f:
            f.write(data.read_program_file(name))


class TemporaryDirectory():
    """Temporary directory context guard like in Python 3 tempfile."""

    def __init__(self, prefix=u''):
        """Initialise context guard."""
        self._prefix = prefix
        self._temp_dir = None

    def __enter__(self):
        """Create temp directory."""
        self._temp_dir = tempfile.mkdtemp(prefix=self._prefix)
        return self._temp_dir

    def __exit__(self, dummy_1, dummy_2, dummy_3):
        """Clean up temp directory."""
        if self._temp_dir:
            try:
                shutil.rmtree(self._temp_dir)
            except EnvironmentError as e:
                logging.error(str(e))


class Settings(object):
    """Read and retrieve command-line settings and options."""

    # Default preset definitions
    # For example, --preset=tandy will load all options in the [tandy] section. Preset options override default options.
    # Presets can also be added by adding a section in brackets in the user configuration file
    # e.g., a section headed [myconfig] will be loaded with --preset=myconfig

    default_config = {
        u'strict': {
            u'strict-hidden-lines': u'True',
            u'strict-newline': u'True',
            u'strict-protect': u'True',
            u'allow-code-poke': u'True',
            u'nokill': u'True',
            u'ctrl-c-break': u'False',
            },
        u'basica': {
            u'reserved-memory': u'789',
            },
        u'pcjr': {
            u'syntax': u'pcjr',
            u'pcjr-term': os.path.join(PROGRAM_PATH, 'PCTERM.BAS'),
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
            u'mono-tint': u'0,255,0',
            },
        u'hercules': {
            u'video': u'hercules',
            u'font': u'cga,mda',
            u'codepage': u'437',
            u'monitor': u'mono',
            u'mono-tint': u'0,255,0',
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

    # user and local config files
    config_name = u'PCBASIC.INI'
    user_config_path = os.path.join(USER_CONFIG_DIR, config_name)

    # save-state file name
    state_name = 'pcbasic.session'

    # by default, load what's in section [pcbasic] and override with anything
    # in os-specific section [windows] [android] [linux] [osx] [unknown_os]
    default_presets = [u'pcbasic']

    # number of positional arguments
    positional = 2

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
    short_args = {
        u'd': u'double',
        u'f': u'max-files',
        u's': u'max-reclen',
        u'c': u'serial-buffer-size',
        u'm': u'max-memory',
        u'i': u'',
        u'b': u'interface=cli',
        u't': u'interface=text',
        u'n': u'interface=none',
        u'l': u'load',
        u'h': u'help',
        u'r': u'run',
        u'e': u'exec',
        u'q': u'quit',
        u'k': u'keys',
        u'v': u'version',
        u'w': u'wait',
        }

    # all long-form arguments
    arguments = {
        u'input': {u'type': u'string', u'default': u'', },
        u'output': {u'type': u'string', u'default': u'', },
        u'append': {u'type': u'bool', u'default': False, },
        u'interface': {
            u'type': u'string', u'default': u'',
            u'choices': (u'', u'none', u'cli', u'text', u'graphical',
                        u'ansi', u'curses', u'pygame', u'sdl2'), },
        u'sound-engine': {
            u'type': u'string', u'default': u'',
            u'choices': (u'', u'none', u'beep', u'portaudio'), },
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
            u'default': [u'unifont', u'univga', u'freedos'],},
        u'dimensions': {u'type': u'int', u'list': 2, u'default': [],},
        u'fullscreen': {u'type': u'bool', u'default': False,},
        u'nokill': {u'type': u'bool', u'default': False,},
        u'debug': {u'type': u'bool', u'default': False,},
        u'strict-hidden-lines': {u'type': u'bool', u'default': False,},
        u'strict-protect': {u'type': u'bool', u'default': False,},
        u'mount': {u'type': u'string', u'list': u'*', u'default': [],},
        u'resume': {u'type': u'bool', u'default': False,},
        u'strict-newline': {u'type': u'bool', u'default': False,},
        u'syntax': {
            u'type': u'string', u'choices': (u'advanced', u'pcjr', u'tandy'),
            u'default': u'advanced',},
        u'pcjr-term': {u'type': u'string', u'default': u'',},
        u'video': {
            u'type': u'string', u'default': 'vga',
            u'choices': (
                u'vga', u'ega', u'cga', u'cga_old', u'mda',
                u'pcjr', u'tandy', u'hercules', u'olivetti'), },
        u'map-drives': {u'type': u'bool', u'default': False,},
        u'cga-low': {u'type': u'bool', u'default': False,},
        u'nobox': {u'type': u'bool', u'default': False,},
        u'utf8': {u'type': u'bool', u'default': False,},
        u'border': {u'type': u'int', u'default': 5,},
        u'mouse-clipboard': {u'type': u'bool', u'default': True,},
        u'state': {u'type': u'string', u'default': u'',},
        u'mono-tint': {u'type': u'int', u'list': 3, u'default': [255, 255, 255],},
        u'monitor': {
            u'type': u'string', u'choices': (u'rgb', u'composite', u'mono'),
            u'default': u'rgb',},
        u'aspect': {u'type': u'int', u'list': 2, u'default': [4, 3],},
        u'scaling': {
            u'type': u'string', u'choices':(u'smooth', u'native', u'crisp'),
            u'default': u'smooth',},
        u'version': {u'type': u'bool', u'default': False,},
        u'config': {u'type': u'string', u'default': u'',},
        u'logfile': {u'type': u'string', u'default': u'',},
        # negative list length means 'optionally up to'
        u'max-memory': {u'type': u'int', u'list': -2, u'default': [65534, 4096]},
        u'allow-code-poke': {u'type': u'bool', u'default': False,},
        u'reserved-memory': {u'type': u'int', u'default': 3429,},
        u'caption': {u'type': u'string', u'default': NAME,},
        u'text-width': {u'type': u'int', u'choices':(40, 80), u'default': 80,},
        u'video-memory': {u'type': u'int', u'default': 262144,},
        u'shell': {u'type': u'string', u'default': u'',},
        u'ctrl-c-break': {u'type': u'bool', u'default': True,},
        u'wait': {u'type': u'bool', u'default': False,},
        u'current-device': {u'type': u'string', u'default': 'Z'},
        u'extension': {u'type': u'string', u'list': u'*', u'default': []},
    }

    def __init__(self, temp_dir, arguments):
        """Initialise settings."""
        # arguments should be unicode
        if not arguments:
            self._uargv = get_unicode_argv()[1:]
        else:
            self._uargv = list(arguments)
        # first parse a logfile argument, if any
        for args in self._uargv:
            if args[:9] == u'--logfile':
                logfile = args[10:]
                break
        else:
            logfile = None
        self._logger = get_logger(logfile)
        self._temp_dir = temp_dir
        # create state path if needed
        if not os.path.exists(STATE_PATH):
            os.makedirs(STATE_PATH)
        # create user config file if needed
        if not os.path.exists(self.user_config_path):
            try:
                os.makedirs(USER_CONFIG_DIR)
            except OSError:
                pass
            self.build_default_config_file(self.user_config_path)
        # create @: drive if not present
        if not os.path.exists(PROGRAM_PATH):
            os.makedirs(PROGRAM_PATH)
            # unpack bundled programs
            store_bundled_programs(PROGRAM_PATH)
        # store options in options dictionary
        self._options = self._retrieve_options(self._uargv)
        # prepare global logger for use by main program
        self._prepare_logging()
        # initial validations
        python_version = tuple(int(v) for v in platform.python_version_tuple())
        if python_version >= (3, 0, 0) or python_version < MIN_PYTHON_VERSION:
            msg = 'PC-BASIC requires Python 2, version %d.%d.%d or higher. ' % MIN_PYTHON_VERSION + 'You have %d.%d.%d.' % python_version
            logging.fatal(msg)
            raise Exception(msg)

    def _prepare_logging(self):
        """Set up the global logger."""
        logfile = self.get('logfile')
        if self.get('version') or self.get('help'):
            formatstr = '%(message)s'
            loglevel = logging.INFO
        else:
            # logging setup before we import modules and may need to log errors
            formatstr = '[%(asctime)s.%(msecs)04d] %(levelname)s: %(message)s'
            if self.get('debug'):
                loglevel = logging.DEBUG
            else:
                loglevel = logging.INFO
        # o dear o dear what a horrible API
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        root_logger.setLevel(loglevel)
        if logfile:
            handler = logging.FileHandler(logfile, mode=b'w')
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt=formatstr, datefmt='%H:%M:%S'))
        root_logger.addHandler(handler)

    def _retrieve_options(self, uargv):
        """Retrieve command line and option file options."""
        # convert command line arguments to string dictionary form
        remaining = self._get_arguments(uargv)
        # unpack any packages
        package = self._parse_package(remaining)
        # get preset groups from specified config file
        preset_dict = self._parse_config(remaining)
        # set defaults based on presets
        args = self._parse_presets(remaining, preset_dict)
        # local config file settings override preset settings
        self._merge_arguments(args, preset_dict[u'pcbasic'])
        # parse rest of command line
        self._merge_arguments(args, self._parse_args(remaining))
        # clean up arguments
        self._clean_arguments(args)
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
                    value = self.arguments[name][u'default']
                except KeyError:
                    if name in range(self.positional):
                        return u''
            else:
                value = None
        return value

    def _get_redirects(self):
        """Determine which i/o streams to attach."""
        input_streams, output_streams = [], []
        # add stdio if redirected or no interface
        if HAS_CONSOLE and (not self.interface or not sys.stdin.isatty()):
            input_streams.append(sys.stdin)
        # redirect output as well if input is redirected, but not the other way around
        # this is because (1) GW-BASIC does this from the DOS prompt
        # (2) otherwise we don't see anything - we quit after input closes
        # isatty is also false if we run as a GUI exe, so check that here
        if HAS_CONSOLE and (
                not self.interface or not sys.stdout.isatty() or not sys.stdin.isatty()):
            output_streams.append(sys.stdout)
        # explicit redirects
        infile = self.get(b'input')
        if infile:
            try:
                input_streams.append(open(infile, 'rb'))
            except EnvironmentError as e:
                logging.warning(u'Could not open input file %s: %s', infile, e.strerror)
        outfile = self.get(b'output')
        if outfile:
            try:
                output_streams.append(open(outfile, 'ab' if self.get(b'append') else 'wb'))
            except EnvironmentError as e:
                logging.warning(u'Could not open output file %s: %s', outfile, e.strerror)
        return {
            'output_streams': output_streams,
            'input_streams': input_streams,
        }

    @property
    def session_params(self):
        """Return a dictionary of parameters for the Session object."""
        current_device, mount_dict = self._get_drives(False)
        if self.get('resume'):
            return {}
        pcjr_term = self.get('pcjr-term')
        peek_values = {}
        try:
            for a in self.get('peek'):
                seg, addr, val = a.split(':')
                peek_values[int(seg)*0x10 + int(addr)] = int(val)
        except (TypeError, ValueError):
            pass
        device_params = {
                key.upper()+':' : self.get(key)
                for key in ('lpt1', 'lpt2', 'lpt3', 'com1', 'com2', 'cas1')}
        max_list = self.get('max-memory')
        max_list[1] = max_list[1]*16 if max_list[1] else max_list[0]
        max_list[0] = max_list[0] or max_list[1]
        current_device, mount_dict = self._get_drives()
        codepage_dict = data.read_codepage(self.get('codepage'))
        params = self._get_redirects()
        params.update({
            'syntax': self.get('syntax'),
            'video': self.get('video'),
            'codepage': codepage_dict,
            'box_protect': not self.get('nobox'),
            'monitor': self.get('monitor'),
            # screen settings
            'aspect_ratio': (3072, 2000) if self.get('video') == 'tandy' else (4, 3),
            'text_width': self.get('text-width'),
            'video_memory': self.get('video-memory'),
            'low_intensity': self.get('cga-low'),
            'mono_tint': self.get('mono-tint'),
            'font': data.read_fonts(codepage_dict, self.get('font'), warn=self.get('debug')),
            # inserted keystrokes
            'keys': self.get('keys').encode('utf-8', 'replace')
                        .decode('string_escape').decode('utf-8', 'replace'),
            # find program for PCjr TERM command
            'term': pcjr_term,
            'shell': self.get('shell'),
            'double': self.get('double'),
            # device settings
            'devices': device_params,
            'current_device': current_device,
            'mount': mount_dict,
            'serial_buffer_size': self.get('serial-buffer-size'),
            # text file parameters
            'utf8': self.get('utf8'),
            'universal': not self.get('strict-newline'),
            # keyboard settings
            'ctrl_c_is_break': self.get('ctrl-c-break'),
            # program parameters
            'max_list_line': 65535 if not self.get('strict-hidden-lines') else 65530,
            'allow_protect': self.get('strict-protect'),
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
        return params

    def _get_video_parameters(self):
        """Return a dictionary of parameters for the video plugin."""
        return {
            'dimensions': self.get('dimensions'),
            'aspect_ratio': self.get('aspect'),
            'border_width': self.get('border'),
            'scaling': self.get('scaling'),
            'fullscreen': self.get('fullscreen'),
            'alt_f4_quits': not self.get('nokill'),
            'caption': self.get('caption'),
            'mouse_clipboard': self.get('mouse-clipboard'),
            'icon': ICON,
            'wait': self.get('wait'),
            }

    def _get_audio_parameters(self):
        """Return a dictionary of parameters for the audio plugin."""
        return {}

    def _get_state_file(self):
        """Name of state file"""
        state_name = self.get('state') or self.state_name
        if not os.path.exists(state_name):
            state_name = os.path.join(STATE_PATH, state_name)
        return state_name

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
            # (video, audio), in order of preference
            'text': ('curses', 'ansi'),
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
            'audio_override': self.get('sound-engine'),
        }
        iface_params.update(self._get_video_parameters())
        iface_params.update(self._get_audio_parameters())
        return iface_params

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

    @property
    def guard_params(self):
        """Dict of exception guard parameters."""
        return {
            'uargv': self._uargv,
            'log_dir': STATE_PATH,
            }

    def _get_drives(self, get_default=True):
        """Assign disk locations to disk devices."""
        mount_dict = {}
        # always get current device
        current_device = self.get('current-device')
        if self.get('map-drives', get_default):
            if WIN32:
                # get all drives in use by windows
                # if started from CMD.EXE, get the 'current working dir' for each drive
                # if not in CMD.EXE, there's only one cwd
                save_current = os.getcwdu()
                for letter in string.uppercase:
                    try:
                        os.chdir(letter + b':')
                        cwd = get_short_pathname(os.getcwdu()) or os.getcwdu()
                    except EnvironmentError:
                        # doesn't exist or can't access, do not mount this drive
                        pass
                    else:
                        # must not start with \\
                        path, cwd = cwd[:3], cwd[3:]
                        mount_dict[letter] = (path, cwd)
                os.chdir(save_current)
                try:
                    current_device = os.path.abspath(save_current).split(u':')[0].encode('ascii')
                except UnicodeEncodeError:
                    # fallback in case of some error
                    current_device = mount_dict.keys()[0]
            else:
                cwd = os.getcwdu()
                home = os.path.expanduser(u'~')
                # if cwd is in home tree, set it also on H:
                if cwd[:len(home)] == home:
                    home_cwd = cwd[len(home)+1:]
                else:
                    home_cwd = u''
                mount_dict = {
                    # map C to root
                    b'C': (u'/', cwd[1:]),
                    # map Z to cwd
                    b'Z': (cwd, u''),
                    # map H to home
                    b'H': (home, home_cwd),
                    }
                # default durrent drive
                current_device = b'Z'
        else:
            mount_dict[b'Z'] = (os.getcwdu(), u'')
        # directory for bundled BASIC programs accessible through @:
        mount_dict[b'@'] = (PROGRAM_PATH, u'')
        # build mount dictionary
        mount_list = self.get('mount', get_default)
        if mount_list:
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
                    logging.warning(u'Could not mount %s: %s', a, unicode(e))
        return current_device, mount_dict

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

    def _append_short_args(self, args, key, value):
        """Append short arguments and value to dict."""
        for i, short_arg in enumerate(key[1:]):
            try:
                skey, svalue = safe_split(self.short_args[short_arg], u'=')
                if not svalue and not skey:
                    continue
                if (not svalue) and i == len(key)-2:
                    # assign value to last argument specified
                    append_arg(args, skey, value)
                else:
                    append_arg(args, skey, svalue)
            except KeyError:
                self._logger.warning(u'Ignored unrecognised option `-%s`', short_arg)

    def _get_arguments(self, argv):
        """Convert arguments to dictionary."""
        args = {}
        arg_deque = deque(argv)
        # positional arguments must come before any options
        for pos in range(self.positional):
            if not arg_deque or arg_deque[0].startswith(u'-'):
                break
            args[pos] = arg_deque.popleft()
        while arg_deque:
            arg = arg_deque.popleft()
            key, value = safe_split(arg, u'=')
            if not value:
                if arg_deque and not arg_deque[0].startswith(u'-') and u'=' not in arg_deque[0]:
                    value = arg_deque.popleft()
            if key:
                if key[0:2] == u'--':
                    if key[2:]:
                        append_arg(args, key[2:], value)
                elif key[0] == u'-':
                    self._append_short_args(args, key, value)
                else:
                    self._logger.warning(u'Ignored surplus positional argument `%s`', arg)
            else:
                self._logger.warning(u'Ignored unrecognised option `=%s`', value)
        return args

    def _parse_presets(self, remaining, conf_dict):
        """Parse presets"""
        presets = self.default_presets
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
                    if p not in self.default_presets:
                        self._logger.warning(u'Ignored undefined preset "%s"', p)
            # look for more presets in expended arglist
            try:
                presets = self._parse_list(u'preset', argdict.pop(u'preset'))
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
                contents = os.listdir('.')
                if len(contents) == 1:
                    os.chdir(contents[0])
                # recursively rename all files to all-caps to avoid case issues on Unix
                # collisions: the last file renamed overwrites earlier ones
                for root, dirs, files in os.walk(u'.', topdown=False):
                    for name in dirs + files:
                        try:
                            os.rename(os.path.join(root, name),
                                      os.path.join(root, name.upper()))
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
        conf_dict = dict(self.default_config)
        conf_dict.update(self._read_config_file(self.user_config_path))
        # find any local overriding config file & read it
        config_file = None
        try:
            config_file = remaining.pop(u'config')
        except KeyError:
            if os.path.exists(self.config_name):
                config_file = self.config_name
        if config_file:
            conf_dict.update(self._read_config_file(config_file))
        return conf_dict

    def _read_config_file(self, config_file):
        """Read config file."""
        try:
            config = ConfigParser.RawConfigParser(allow_no_value=True)
            # use utf_8_sig to ignore a BOM if it's at the start of the file (e.g. created by Notepad)
            with codecs.open(config_file, b'r', b'utf_8_sig') as f:
                config.readfp(f)
        except (ConfigParser.Error, IOError):
            self._logger.warning(u'Error in configuration file %s. '
                           u'Configuration not loaded.', config_file)
            return {u'pcbasic': {}}
        presets = { header: dict(config.items(header))
                    for header in config.sections() }
        return presets

    def _parse_args(self, remaining):
        """Retrieve command line options."""
        # set arguments
        known = self.arguments.keys() + range(self.positional)
        args = {d:remaining[d] for d in remaining if d in known}
        not_recognised = {d:remaining[d] for d in remaining if d not in known}
        for d in not_recognised:
            self._logger.warning(u'Ignored unrecognised option "%s=%s"',
                            d, not_recognised[d])
        return args

    ################################################

    def _merge_arguments(self, args0, args1):
        """Update args0 with args1. Lists of indefinite length are appended."""
        for a in args1:
            try:
                if (a in args0 and self.arguments[a][u'list'] == u'*' and args0[a]):
                    args0[a] += u',' + args1[a]
                    continue
            except KeyError:
                pass
            # override
            args0[a] = args1[a]

    def _clean_arguments(self, args):
        """Convert arguments to required type and list length."""
        for d in args:
            try:
                args[d] = self._parse_list(d, args[d], self.arguments[d][u'list'])
            except KeyError:
                # not a list
                args[d] = self._parse_type(d, args[d])

    def _parse_type(self, d, arg):
        """Convert argument to required type."""
        if d not in self.arguments:
            return arg
        if u'choices' in self.arguments[d]:
            arg = arg.lower()
        if u'type' in self.arguments[d]:
            if (self.arguments[d][u'type'] == u'int'):
                arg = self._parse_int(d, arg)
            elif (self.arguments[d][u'type'] == u'bool'):
                arg = self._parse_bool(d, arg)
        if u'choices' in self.arguments[d]:
            if arg and arg not in self.arguments[d][u'choices']:
                self._logger.warning(u'Value "%s=%s" ignored; should be one of (%s)',
                                d, unicode(arg), u', '.join(self.arguments[d][u'choices']))
                arg = u''
        return arg

    def _parse_list(self, d, s, length='*'):
        """Convert list strings to typed lists."""
        lst = s.split(u',')
        if lst == [u'']:
            if length == '*':
                return []
            elif length < 0:
                return [None]*(-length)
            else:
                return None
        lst = [self._parse_type(d, arg) for arg in lst]
        # negative length: optional up-to
        if length < 0:
            lst += [None]*(-length-len(lst))
        if length != u'*' and (len(lst) > abs(length) or len(lst) < length):
            self._logger.warning(u'Option "%s=%s" ignored, should have %d elements',
                            d, s, abs(length))
        return lst

    def _parse_bool(self, d, s):
        """Parse bool option. Empty string (i.e. specified) means True."""
        if s == u'':
            return True
        try:
            if s.upper() in (u'YES', u'TRUE', u'ON', u'1'):
                return True
            elif s.upper() in (u'NO', u'FALSE', u'OFF', u'0'):
                return False
        except AttributeError:
            self._logger.warning(u'Option "%s=%s" ignored; should be a boolean', d, s)
            return None

    def _parse_int(self, d, s):
        """Parse int option provided as a one-element list of string."""
        if s:
            try:
                return int(s)
            except ValueError:
                self._logger.warning(u'Option "%s=%s" ignored; should be an integer', d, s)
        return None


    #########################################################

    def build_default_config_file(self, file_name):
        """Write a default config file."""
        header = (
        u"# PC-BASIC configuration file.\n"
        u"# Edit this file to change your default settings or add presets.\n"
        u"# Changes to this file will not affect any other users of your computer.\n"
        u"# All lines starting with # are comments and have no effect.\n"
        u"# Thus, to use one of the example options below, you need to remove the # at the start of the line.\n"
        u"\n"
        u"[pcbasic]\n"
        u"# Use the [pcbasic] section to specify options you want to be enabled by default.\n"
        u"# See the documentation or run pcbasic -h for a list of available options.\n"
        u"# for example (for version '%s'):\n" % VERSION)
        footer = (
        u"\n\n# To add presets, create a section header between brackets and put the \n"
        u"# options you need below it, like this:\n"
        u"# [your_preset]\n"
        u"# border=0\n"
        u"# \n"
        u"# You will then be able to load these options with --preset=your_preset.\n"
        u"# If you choose the same name as a system preset, PC-BASIC will use your\n"
        u"# options for that preset and not the system ones. This is not recommended.\n")
        argnames = sorted(self.arguments.keys())
        try:
            with open(file_name, b'w') as f:
                # write a BOM at start to ensure Notepad gets that it's utf-8
                # but don't use codecs.open as that doesn't do CRLF on Windows
                f.write(b'\xEF\xBB\xBF')
                f.write(header.encode(b'utf-8'))
                for a in argnames:
                    try:
                        f.write((u'## choices: %s\n' %
                                    u', '.join(map(unicode, self.arguments[a][u'choices']))).encode(b'utf-8'))
                    except(KeyError, TypeError):
                        pass
                    try:
                        # check if it's a list
                        self.arguments[a][u'list']
                        formatted = u','.join(map(unicode, self.arguments[a][u'default']))
                    except(KeyError, TypeError):
                        formatted = unicode(self.arguments[a][u'default'])
                    f.write((u'#%s=%s\n' % (a, formatted)).encode(b'utf-8'))
                f.write(footer)
        except (OSError, IOError):
            # can't create file, ignore. we'll get a message later.
            pass
