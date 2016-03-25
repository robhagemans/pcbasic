"""
PC-BASIC - config.py
Configuration file and command-line options parser

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import ConfigParser
import logging
import zipfile
import codecs

import plat
if plat.system == b'Windows':
    import ctypes
    import ctypes.wintypes

# system-wide config path
system_config_path = os.path.join(plat.system_config_dir, u'default.ini')

#user and local config files
config_name = u'PCBASIC.INI'
user_config_path = os.path.join(plat.user_config_dir, config_name)

# by default, load what's in section [pcbasic] and override with anything
# in os-specific section [windows] [android] [linux] [osx] [unknown_os]
default_presets = [u'pcbasic', plat.system.lower().decode('ascii')]

# get supported codepages
encodings = sorted([ x[0] for x in [ c.split(u'.ucp')
                     for c in os.listdir(plat.encoding_dir) ] if len(x)>1])
# get supported font families
families = sorted(list(set([ x[0] for x in [ c.split(u'_')
                  for c in os.listdir(plat.font_dir) ] if len(x)>1])))

# dictionary to hold all options chosen
options = {}
# flag True if we're running from a package
package = False
# sys.argv converted to unicode
uargv = []

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
    u'load': {u'type': u'string', u'default': u'', },
    u'run': {u'type': u'string', u'default': u'',  },
    u'convert': {u'type': u'string', u'default': u'', },
    u'help': {u'type': u'bool', u'default': False, },
    u'keys': {u'type': u'string', u'default': u'', },
    u'exec': {u'type': u'string', u'default': u'',  },
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
    u'codepage': {u'type': u'string', u'choices': encodings, u'default': u'437',},
    u'font': {
        u'type': u'string', u'list': u'*', u'choices': families,
        u'default': [u'unifont', u'univga', u'freedos'],},
    u'nosound': {u'type': u'bool', u'default': False, },
    u'dimensions': {u'type': u'int', u'list': 2, u'default': None,},
    u'fullscreen': {u'type': u'bool', u'default': False,},
    u'nokill': {u'type': u'bool', u'default': False,},
    u'debug': {u'type': u'bool', u'default': False,},
    u'strict-hidden-lines': {u'type': u'bool', u'default': False,},
    u'strict-protect': {u'type': u'bool', u'default': False,},
    u'capture-caps': {u'type': u'bool', u'default': False,},
    u'mount': {u'type': u'string', u'list': u'*', u'default': [],},
    u'resume': {u'type': u'bool', u'default': False,},
    u'strict-newline': {u'type': u'bool', u'default': False,},
    u'syntax': {
        u'type': u'string', u'choices': (u'advanced', u'pcjr', u'tandy'),
        u'default': u'advanced',},
    u'pcjr-term': {u'type': u'string', u'default': u'',},
    u'video': {
        u'type': u'string', u'default': 'vga',
        u'choices': (u'vga', u'ega', u'cga', u'cga_old', u'mda', u'pcjr', u'tandy',
                     u'hercules', u'olivetti'), },
    u'map-drives': {u'type': u'bool', u'default': False,},
    u'cga-low': {u'type': u'bool', u'default': False,},
    u'nobox': {u'type': u'bool', u'default': False,},
    u'utf8': {u'type': u'bool', u'default': False,},
    u'border': {u'type': u'int', u'default': 5,},
    u'pen': {
        u'type': u'string', u'default': u'left',
        u'choices': (u'left', u'middle', u'right', u'none',), },
    u'copy-paste': {u'type': u'string', u'list': 2, u'default': [u'left', u'middle'],
                   u'choices': (u'left', u'middle', u'right', u'none',),},
    u'state': {u'type': u'string', u'default': u'',},
    u'mono-tint': {u'type': u'int', u'list': 3, u'default': [255, 255, 255],},
    u'monitor': {
        u'type': u'string', u'choices': (u'rgb', u'composite', u'mono'),
        u'default': u'rgb',},
    u'aspect': {u'type': u'int', u'list': 2, u'default': [4, 3],},
    u'scaling': {u'type': u'string', u'choices':(u'smooth', u'native', u'crisp'), u'default': u'smooth',},
    u'version': {u'type': u'bool', u'default': False,},
    u'config': {u'type': u'string', u'default': u'',},
    u'logfile': {u'type': u'string', u'default': u'',},
    # negative list length means 'optionally up to'
    u'max-memory': {u'type': u'int', u'list': -2, u'default': [65534, 4096]},
    u'allow-code-poke': {u'type': u'bool', u'default': False,},
    u'reserved-memory': {u'type': u'int', u'default': 3429,},
    u'caption': {u'type': u'string', u'default': 'PC-BASIC',},
    u'text-width': {u'type': u'int', u'choices':(40, 80), u'default': 80,},
    u'video-memory': {u'type': u'int', u'default': 262144,},
    u'shell': {u'type': u'string', u'default': u'none',},
    u'print-trigger': {u'type': u'string', u'choices':(u'close', u'page', u'line'), u'default': u'close',},
    u'altgr': {u'type': u'bool', u'default': True,},
    u'ctrl-c-break': {u'type': u'bool', u'default': True,},
    u'wait': {u'type': u'bool', u'default': False,},
    u'current-device': {u'type': u'string', u'default': 'Z'},
}


def prepare():
    """ Initialise config.py """
    global options, logger, uargv
    # convert arguments to unicode using preferred encoding
    uargv = get_unicode_argv()
    # first parse a logfile argument, if any
    for args in uargv:
        if args[:9] == u'--logfile':
            logfile = args[10:]
            break
    else:
        logfile = None
    logger = get_logger(logfile)
    # create user config file if needed
    if not os.path.exists(user_config_path):
        try:
            os.makedirs(plat.user_config_dir)
        except OSError:
            pass
        build_default_config_file(user_config_path)
    # store options in options dictionary
    options = retrieve_options()

def get_unicode_argv():
    """ Convert command-line arguments to unicode. """
    if plat.system == b'Windows':
        # see http://code.activestate.com/recipes/572200-get-sysargv-with-unicode-characters-under-windows/
        GetCommandLineW = ctypes.cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = ctypes.wintypes.LPCWSTR
        cmd = GetCommandLineW()
        argc = ctypes.c_int(0)
        CommandLineToArgvW = ctypes.windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        CommandLineToArgvW.restype = ctypes.POINTER(ctypes.wintypes.LPWSTR)
        argv = CommandLineToArgvW(cmd, ctypes.byref(argc))
        argv = [argv[i] for i in xrange(argc.value)]
        # clip off the python interpreter call, if we use it
        if argv[0][:6].lower() == u'python':
            argv = argv[1:]
        return argv
    else:
        # the official parameter should be LC_CTYPE but that's None in my locale
        # on windows, this would only work if the mbcs CP_ACP includes the characters we need
        return [arg.decode(plat.preferred_encoding) for arg in sys.argv]

def retrieve_options():
    """ Retrieve command line and option file options. """
    # convert command line arguments to string dictionary form
    remaining = get_arguments(uargv[1:])
    # unpack any packages
    parse_package(remaining)
    # get preset groups from specified config file
    preset_dict = parse_config(remaining)
    # set defaults based on presets
    args = parse_presets(remaining, preset_dict)
    # local config file settings override preset settings
    merge_arguments(args, preset_dict[u'pcbasic'])
    # parse rest of command line
    merge_arguments(args, parse_args(remaining))
    # clean up arguments
    clean_arguments(args)
    return args

def get(name, get_default=True):
    """ Get value of option; choose whether to get default or None. """
    try:
        value = options[name]
        if value is None or value == u'':
            raise KeyError
    except KeyError:
        if get_default:
            try:
                value = arguments[name][u'default']
            except KeyError:
                if name in range(positional):
                    return u''
        else:
            value = None
    return value

def append_arg(args, key, value):
    """ Update a single argument by appending a value """
    if key in args and args[key]:
        if value:
            args[key] += u',' + value
    else:
        args[key] = value

def safe_split(s, sep):
    slist = s.split(sep, 1)
    s0 = slist[0]
    if len(slist) > 1:
        s1 = slist[1]
    else:
        s1 = u''
    return s0, s1

def get_arguments(argv):
    """ Convert arguments to { key: value } dictionary. """
    args = {}
    pos = 0
    for arg in argv:
        key, value = safe_split(arg, u'=')
        if key:
            if key[0:2] == u'--':
                if key[2:]:
                    append_arg(args, key[2:], value)
            elif key[0] == u'-':
                for i, short_arg in enumerate(key[1:]):
                    try:
                        skey, svalue = safe_split(short_args[short_arg], u'=')
                        if not svalue and not skey:
                            continue
                        if (not svalue) and i == len(key)-2:
                            # assign value to last argument specified
                            append_arg(args, skey, value)
                        else:
                            append_arg(args, skey, svalue)
                    except KeyError:
                        logger.warning(u'Ignored unrecognised option "-%s"', short_arg)
            elif pos < positional:
                # positional argument
                args[pos] = arg
                pos += 1
            else:
                logger.warning(u'Ignored extra positional argument "%s"', arg)
        else:
            logger.warning(u'Ignored unrecognised option "=%s"', value)
    return args

def parse_presets(remaining, conf_dict):
    """ Parse presets. """
    presets = default_presets
    try:
        argdict = {u'preset': remaining.pop(u'preset')}
    except KeyError:
        argdict = {}
    # apply default presets, including nested presets
    while True:
        # get dictionary of default config
        for p in presets:
            try:
                merge_arguments(argdict, conf_dict[p])
            except KeyError:
                if p not in default_presets:
                    logger.warning(u'Ignored undefined preset "%s"', p)
        # look for more presets in expended arglist
        try:
            presets = parse_list(u'preset', argdict.pop(u'preset'))
        except KeyError:
            break
    return argdict

def parse_package(remaining):
    """ Unpack BAZ package, if specified, and make its temp dir current. """
    global package
    # first positional arg: program or package name
    try:
        arg_package = remaining[0]
    except KeyError:
        return
    if os.path.isdir(arg_package):
        os.chdir(arg_package)
        remaining.pop(0)
        package = arg_package
    elif zipfile.is_zipfile(arg_package):
        remaining.pop(0)
        # extract the package to a temp directory
        # and make that the current dir for our run
        zipfile.ZipFile(arg_package).extractall(path=plat.temp_dir)
        os.chdir(plat.temp_dir)
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

def parse_config(remaining):
    """ Find the correct config file and read it. """
    # always read default config files; private config overrides system config
    # we update a whole preset at once, there's no joining of settings.
    conf_dict = read_config_file(system_config_path)
    conf_dict.update(read_config_file(user_config_path))
    # find any local overriding config file & read it
    config_file = None
    try:
        config_file = remaining.pop(u'config')
    except KeyError:
        if os.path.exists(config_name):
            config_file = config_name
    if config_file:
        conf_dict.update(read_config_file(config_file))
    return conf_dict

def read_config_file(config_file):
    """ Read config file. """
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        # use utf_8_sig to ignore a BOM if it's at the start of the file (e.g. created by Notepad)
        with codecs.open(config_file, b'r', b'utf_8_sig') as f:
            config.readfp(f)
    except (ConfigParser.Error, IOError):
        logger.warning(u'Error in configuration file %s. '
                       u'Configuration not loaded.', config_file)
        return {}
    presets = { header: dict(config.items(header))
                for header in config.sections() }
    return presets

def parse_args(remaining):
    """ Retrieve command line options. """
    # set arguments
    known = arguments.keys() + range(positional)
    args = {d:remaining[d] for d in remaining if d in known}
    not_recognised = {d:remaining[d] for d in remaining if d not in known}
    for d in not_recognised:
        logger.warning(u'Ignored unrecognised option "%s=%s"',
                        d, not_recognised[d])
    return args

################################################

def merge_arguments(args0, args1):
    """ Update args0 with args1. Lists of indefinite length are appended. """
    for a in args1:
        try:
            if (a in args0 and arguments[a][u'list'] == u'*' and args0[a]):
                args0[a] += u',' + args1[a]
                continue
        except KeyError:
            pass
        # override
        args0[a] = args1[a]

def clean_arguments(args):
    """ Convert arguments to required type and list length. """
    for d in args:
        try:
            args[d] = parse_list(d, args[d], arguments[d][u'list'])
        except KeyError:
            # not a list
            args[d] = parse_type(d, args[d])

def parse_type(d, arg):
    """ Convert argument to required type. """
    if d not in arguments:
        return arg
    if u'choices' in arguments[d]:
        arg = arg.lower()
    if u'type' in arguments[d]:
        if (arguments[d][u'type'] == u'int'):
            arg = parse_int(d, arg)
        elif (arguments[d][u'type'] == u'bool'):
            arg = parse_bool(d, arg)
    if u'choices' in arguments[d]:
        if arg and arg not in arguments[d][u'choices']:
            logger.warning(u'Value "%s=%s" ignored; should be one of (%s)',
                            d, unicode(arg), u', '.join(arguments[d][u'choices']))
            arg = u''
    return arg

def parse_list(d, s, length='*'):
    """ Convert list strings to typed lists. """
    lst = s.split(u',')
    if lst == [u'']:
        if length == '*':
            return []
        elif length < 0:
            return [None]*(-length)
        else:
            return None
    lst = [parse_type(d, arg) for arg in lst]
    # negative length: optional up-to
    if length < 0:
        lst += [None]*(-length-len(lst))
    if length != u'*' and (len(lst) > abs(length) or len(lst) < length):
        logger.warning(u'Option "%s=%s" ignored, should have %d elements',
                        d, s, abs(length))
    return lst

def parse_bool(d, s):
    """ Parse bool option. Empty string (i.e. specified) means True. """
    if s == u'':
        return True
    try:
        if s.upper() in (u'YES', u'TRUE', u'ON', u'1'):
            return True
        elif s.upper() in (u'NO', u'FALSE', u'OFF', u'0'):
            return False
    except AttributeError:
        logger.warning(u'Option "%s=%s" ignored; should be a boolean', d, s)
        return None

def parse_int(d, s):
    """ Parse int option provided as a one-element list of string. """
    if s:
        try:
            return int(s)
        except ValueError:
            logger.warning(u'Option "%s=%s" ignored; should be an integer', d, s)
    return None

#########################################################

def get_logger(logfile=None):
    # use the awkward logging interface as we can only use basicConfig once
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

#########################################################

def build_default_config_file(file_name):
    """ Write a default config file. """
    header = (
    u"# PC-BASIC private configuration file.\n"
    u"# Edit this file to change your default settings or add presets.\n"
    u"# Changes to this file will not affect any other users of your computer.\n"
    u"\n"
    u"[pcbasic]\n"
    u"# Use the [pcbasic] section to specify options you want to be enabled by default.\n"
    u"# See the documentation or run pcbasic -h for a list of available options.\n"
    u"# for example (for version '%s'):\n" % plat.version)
    footer = (
    u"\n\n# To add presets, create a section header between brackets and put the \n"
    u"# options you need below it, like this:\n"
    u"# [your_preset]\n"
    u"# border=0\n"
    u"# \n"
    u"# You will then be able to load these options with --preset=your_preset.\n"
    u"# If you choose the same name as a system preset, PC-BASIC will use your\n"
    u"# options for that preset and not the system ones. This is not recommended.\n")
    argnames = sorted(arguments.keys())
    try:
        with open(file_name, b'w') as f:
            # write a BOM at start to ensure Notepad gets that it's utf-8
            # but don't use codecs.open as that doesn't do CRLF on Windows
            f.write(b'\xEF\xBB\xBF')
            f.write(header.encode(b'utf-8'))
            for a in argnames:
                try:
                    # check if it's a list
                    arguments[a][u'list']
                    formatted = u','.join(map(unicode, arguments[a][u'default']))
                except(KeyError, TypeError):
                    formatted = unicode(arguments[a][u'default'])
                f.write((u'# %s=%s' % (a, formatted)).encode(b'utf-8'))
                try:
                    f.write((u' ; choices: %s\n' %
                                u', '.join(map(unicode, arguments[a][u'choices']))).encode(b'utf-8'))
                except(KeyError, TypeError):
                    f.write(b'\n')
            f.write(footer)
    except (OSError, IOError):
        # can't create file, ignore. we'll get a message later.
        pass

# initialise this module
prepare()
