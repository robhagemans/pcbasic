"""
PC-BASIC 3.23 
Configuration file and command-line options parser
 
(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import os
import sys
import ConfigParser
import logging
import zipfile
import plat

# system-wide config path
system_config_path = os.path.join(plat.system_config_dir, plat.config_name)
user_config_path = os.path.join(plat.user_config_dir, plat.config_name)

# by default, load what's in section [pcbasic] and override with anything 
# in os-specific section [windows] [android] [linux] [osx] [unknown_os]
default_presets = ['pcbasic', plat.system.lower()]

# get supported codepages
encodings = sorted([ x[0] for x in [ c.split('.ucp') 
                     for c in os.listdir(plat.encoding_dir) ] if len(x)>1])
# get supported font families
families = sorted(list(set([ x[0] for x in [ c.split('_') 
                  for c in os.listdir(plat.font_dir) ] if len(x)>1])))

# dictionary to hold all options chosen
options = {}
# flag True if we're running from a package
package = False

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
    'd': 'double', 'f': 'max-files', 
    's': 'max-reclen', 'c': 'serial-buffer-size',
    'm': 'max-memory', 'i': '',
    'b': 'interface=cli', 't': 'interface=text', 'n': 'interface=none',
    'l': 'load', 'h': 'help',  
    'r': 'run', 'e': 'exec', 'q': 'quit', 'k': 'keys', 'v': 'version',
    'w': 'wait',
    }

# all long-form arguments
arguments = {
    'input': {'type': 'string', 'default': '', },
    'output': {'type': 'string', 'default': '', },
    'append': {'type': 'bool', 'default': False, },
    'interface': { 
        'type': 'string', 'default': '',
        'choices': ('', 'none', 'cli', 'ansi', 'text', 'graphical'), },
    'load': {'type': 'string', 'default': '', },
    'run': {'type': 'string', 'default': '',  },
    'convert': {'type': 'string', 'default': '', },
    'help': {'type': 'bool', 'default': False, },
    'keys': {'type': 'string', 'default': '', },
    'exec': {'type': 'string', 'default': '',  },
    'quit': {'type': 'bool', 'default': False,},
    'double': {'type': 'bool', 'default': False,},
    'max-files': {'type': 'int', 'default': 3,}, 
    'max-reclen': {'type': 'int', 'default': 128,},
    'serial-buffer-size': {'type': 'int', 'default': 256,},
    'peek': {'type': 'string', 'list': '*', 'default': [],},
    'lpt1': {'type': 'string', 'default': 'PRINTER:',},
    'lpt2': {'type': 'string', 'default': '',},
    'lpt3': {'type': 'string', 'default': '',},
    'cas1': {'type': 'string', 'default': '',},
    'com1': {'type': 'string', 'default': '',},
    'com2': {'type': 'string', 'default': '',},
    'codepage': {'type': 'string', 'choices': encodings, 'default': '437',},
    'font': { 
        'type': 'string', 'list': '*', 'choices': families, 
        'default': ['unifont', 'univga', 'freedos'],},
    'nosound': {'type': 'bool', 'default': False, },
    'dimensions': {'type': 'int', 'list': 2, 'default': None,},
    'fullscreen': {'type': 'bool', 'default': False,},
    'nokill': {'type': 'bool', 'default': False,},
    'debug': {'type': 'bool', 'default': False,},
    'strict-hidden-lines': {'type': 'bool', 'default': False,},
    'strict-protect': {'type': 'bool', 'default': False,},
    'capture-caps': {'type': 'bool', 'default': False,},
    'mount': {'type': 'string', 'list': '*', 'default': [],},
    'resume': {'type': 'bool', 'default': False,},
    'strict-newline': {'type': 'bool', 'default': False,},
    'syntax': { 
        'type': 'string', 'choices': ('advanced', 'pcjr', 'tandy'), 
        'default': 'advanced',},
    'pcjr-term': {'type': 'string', 'default': '',},
    'video': { 
        'type': 'string', 'default': 'vga',
        'choices': ('vga', 'ega', 'cga', 'cga_old', 'mda', 'pcjr', 'tandy',
                     'hercules', 'olivetti'), },
    'map-drives': {'type': 'bool', 'default': False,},
    'cga-low': {'type': 'bool', 'default': False,},
    'nobox': {'type': 'bool', 'default': False,},
    'utf8': {'type': 'bool', 'default': False,},
    'border': {'type': 'int', 'default': 5,},
    'pen': {
        'type': 'string', 'default': 'left', 
        'choices': ('left', 'middle', 'right', 'none',), },
    'copy-paste': {'type': 'string', 'list': 2, 'default': ['left', 'middle'],
                   'choices': ('left', 'middle', 'right', 'none',),},
    'state': {'type': 'string', 'default': '',},
    'mono-tint': {'type': 'int', 'list': 3, 'default': [255, 255, 255],},
    'monitor': { 
        'type': 'string', 'choices': ('rgb', 'composite', 'mono'),
        'default': 'rgb',},
    'aspect': {'type': 'int', 'list': 2, 'default': [4, 3],},
    'scaling': {'type': 'string', 'choices':('smooth', 'native', 'crisp'), 'default': 'smooth',},
    'version': {'type': 'bool', 'default': False,},
    'config': {'type': 'string', 'default': '',},
    'logfile': {'type': 'string', 'default': '',},
    # negatove length means optional up to (ok, ugly convention)
    'max-memory': {'type': 'int', 'list': -2, 'default': [65534, 4096]},
    'allow-code-poke': {'type': 'bool', 'default': False,},
    'reserved-memory': {'type': 'int', 'default': 3429,},
    'caption': {'type': 'string', 'default': 'PC-BASIC 3.23',},
    'text-width': {'type': 'int', 'choices':(40, 80), 'default': 80,},
    'video-memory': {'type': 'int', 'default': 262144,},
    'shell': {'type': 'string', 'default': 'none',},
    'print-trigger': {'type': 'string', 'choices':('close', 'page', 'line'), 'default':'close',},
    'altgr': {'type': 'bool', 'default': True,},
    'ctrl-c-break': {'type': 'bool', 'default': False,},
    'wait': {'type': 'bool', 'default': False,},
}


def prepare():
    """ Initialise config.py """
    global options, logger
    # first parse a logfile argument, if any
    for args in sys.argv:
        if args[:9] == '--logfile':
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
    options = get_options()
    
def get_options():
    """ Retrieve command line and option file options. """
    # convert command line arguments to string dictionary form
    remaining = get_arguments(sys.argv[1:])
    # unpack any packages and parse program arguments
    args_program = parse_package(remaining)
    # get arguments and presets from specified config file
    conf_dict = parse_config(remaining)
    # set defaults based on presets. 
    args = parse_presets(remaining, conf_dict)
    # parse rest of command line
    merge_arguments(args, parse_args(remaining))
    # apply program argument
    merge_arguments(args, args_program)
    # clean up arguments    
    clean_arguments(args)
    # apply builtin defaults for unspecified options
    apply_defaults(args)
    return args

def append_arg(args, key, value):
    """ Update a single argument by appending a value """
    if key in args and args[key]: 
        if value:
            args[key] += ',' + value
    else:
        args[key] = value    

def safe_split(s, sep):
    slist = s.split(sep, 1)
    s0 = slist[0]
    if len(slist) > 1:
        s1 = slist[1]
    else:
        s1 = ''
    return s0, s1
    
def get_arguments(argv):
    """ Convert arguments to { key: value } dictionary. """
    args = {}
    pos = 0
    for arg in argv:
        key, value = safe_split(arg, '=')
        if key:
            if key[0:2] == '--':
                if key[2:]:
                    append_arg(args, key[2:], value)
            elif key[0] == '-':
                for i, short_arg in enumerate(key[1:]):
                    try:
                        skey, svalue = safe_split(short_args[short_arg], '=')
                        if not svalue and not skey:
                            continue
                        if (not svalue) and i == len(key)-2:
                            # assign value to last argument specified    
                            append_arg(args, skey, value)
                        else:
                            append_arg(args, skey, svalue)
                    except KeyError:
                        logger.warning('Ignored unrecognised option "-%s"', short_arg)
            elif pos < positional:
                # positional argument
                args[pos] = arg  
                pos += 1
            else:
                logger.warning('Ignored extra positional argument "%s"', arg)    
        else:
            logger.warning('Ignored unrecognised option "=%s"', value)
    return args    

def apply_defaults(args):
    """ Apply default argument where no option specified. """
    for arg in arguments:
        if arg not in args or args[arg] in ('', None):
            try:
                args[arg] = arguments[arg]['default']
            except KeyError:
                pass
    for pos in range(positional):
        if pos not in args:
            args[pos] = ''
    return args    

def parse_presets(remaining, conf_dict):
    """ Parse presets. """
    presets = default_presets
    try:
        argdict = {'preset': remaining.pop('preset')}
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
                    logger.warning('Ignored undefined preset "%s"', p)
        # look for more presets in expended arglist
        try:
            presets = parse_list('preset', argdict.pop('preset'))
        except KeyError:
            break    
    return argdict

def parse_package(remaining):
    """ Unpack BAZ package, if specified, and make its temp dir current. """
    global package
    # first positional arg: program or package name
    args = {}
    try:
        arg_package = remaining[0]
    except KeyError:
        return args
    if zipfile.is_zipfile(arg_package):
        remaining.pop(0)
        # extract the package to a temp directory
        # and make that the current dir for our run
        zipfile.ZipFile(arg_package).extractall(path=plat.temp_dir)
        os.chdir(plat.temp_dir)    
        # recursively rename all files to all-caps to avoid case issues on Unix
        # collisions: the last file renamed overwrites earlier ones
        for root, dirs, files in os.walk('.', topdown=False):
            for name in dirs + files:
                try:
                    os.rename(os.path.join(root, name), 
                              os.path.join(root, name.upper()))
                except OSError:
                    # if we can't rename, ignore
                    pass    
        package = arg_package
    return args

def parse_config(remaining):
    """ Find the correct config file and read it. """
    # always read default config files; private config overrides system config
    # we update a whole preset at once, there's no joining of settings.                
    conf_dict = read_config_file(system_config_path)
    conf_dict.update(read_config_file(user_config_path))
    # find any local overriding config file & read it
    config_file = None
    try:
        config_file = remaining.pop('config')
    except KeyError:
        if os.path.exists(plat.config_name):
            config_file = plat.config_name
    if config_file:
        conf_dict.update(read_config_file(config_file))
    return conf_dict
    
def read_config_file(config_file):
    """ Read config file. """
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(config_file)
    except (ConfigParser.Error, IOError):
        logger.warning('Error in configuration file %s. '
                        'Configuration not loaded.', config_file)
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
        logger.warning('Ignored unrecognised option "%s=%s"', 
                        d, not_recognised[d])
    return args

################################################
    
def merge_arguments(args0, args1):
    """ Update args0 with args1. Lists of indefinite length are appended. """
    for a in args1:
        try:
            if (a in args0 and arguments[a]['list'] == '*' and args0[a]):
                args0[a] += ',' + args1[a]
                continue
        except KeyError:
            pass
        # override
        args0[a] = args1[a]        

def clean_arguments(args):
    """ Convert arguments to required type and list length. """
    for d in args:
        try:
            args[d] = parse_list(d, args[d], arguments[d]['list'])
        except KeyError:
            # not a list    
            args[d] = parse_type(d, args[d]) 
            
def parse_type(d, arg):
    """ Convert argument to required type. """
    if d not in arguments:
        return arg
    if 'type' in arguments[d]:
        if (arguments[d]['type'] == 'int'):
            arg = parse_int(d, arg)
        elif (arguments[d]['type'] == 'bool'):
            arg = parse_bool(d, arg)
    if 'choices' in arguments[d]:
        if arg and arg not in arguments[d]['choices']:
            logger.warning('Value "%s=%s" ignored; should be one of (%s)',
                            d, str(arg), ', '.join(arguments[d]['choices']))
            arg = ''
    return arg
    
def parse_list(d, s, length='*'):
    """ Convert list strings to typed lists. """
    lst = s.split(',')
    if lst == ['']:
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
    if length != '*' and (len(lst) > abs(length) or len(lst) < length):
        logger.warning('Option "%s=%s" ignored, should have %d elements', 
                        d, s, abs(length))
    return lst

def parse_bool(d, s):
    """ Parse bool option. Empty string (i.e. specified) means True. """
    if s == '':
        return True
    try:
        if s.upper() in ('YES', 'TRUE', 'ON', '1'):
            return True
        elif s.upper() in ('NO', 'FALSE', 'OFF', '0'):
            return False   
    except AttributeError:
        logger.warning('Option "%s=%s" ignored; should be a boolean', d, s)
        return None

def parse_int(d, s):
    """ Parse int option provided as a one-element list of string. """
    if s:
        try:
            return int(s)
        except ValueError:
            logger.warning('Option "%s=%s" ignored; should be an integer', d, s)
    return None

#########################################################

def get_logger(logfile=None):
    # use the awkward logging interface as we can only use basicConfig once
    l = logging.getLogger('config')
    l.setLevel(logging.INFO)
    if logfile:
        h = logging.FileHandler(logfile, mode='w')
    else:
        h = logging.StreamHandler()
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    l.addHandler(h)
    return l

#########################################################

def build_default_config_file(file_name):
    """ Write a default config file. """
    header = (
    "# PC-BASIC private configuration file.\n"
    "# Edit this file to change your default settings or add presets.\n"
    "# Changes to this file will not affect any other users of your computer.\n"
    "\n"
    "[pcbasic]\n"
    "# Use the [pcbasic] section to specify options you want to be enabled by default.\n"
    "# See the documentation or run pcbasic -h for a list of available options.\n"
    "# for example (for version '%s'):\n" % plat.version)
    footer = (
    "\n\n# To add presets, create a section header between brackets and put the \n"
    "# options you need below it, like this:\n"
    "# [your_preset]\n"
    "# border=0\n"
    "# \n"
    "# You will then be able to load these options with --preset=your_preset.\n"
    "# If you choose the same name as a system preset, PC-BASIC will use your\n"
    "# options for that preset and not the system ones. This is not recommended.\n")
    argnames = sorted(arguments.keys())
    try:
        with open(file_name, 'w') as f:
            f.write(header)
            for a in argnames:
                try:
                    # check if it's a list
                    arguments[a]['list']
                    formatted = ', '.join(map(str, arguments[a]['default']))
                except(KeyError, TypeError):
                    formatted = str(arguments[a]['default'])
                f.write("# %s=%s" % (a, formatted))
                try:
                    f.write(' # choices: %s\n' %
                                ', '.join(map(str, arguments[a]['choices'])))
                except(KeyError, TypeError):
                    f.write('\n')
            f.write(footer)
    except (OSError, IOError):
        # can't create file, ignore. we'll get a message later.
        pass
            
# initialise this module    
prepare()
    
