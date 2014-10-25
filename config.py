#
# PC-BASIC 3.23 
#
# Configuration file and command-line options parser
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import os
import sys
import ConfigParser
import logging
import zipfile
import plat

if plat.system == 'Android':
    # crashes on Android
    argparse = None
else:
    import argparse

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

# GWBASIC invocation, for reference:
# GWBASIC [prog] [<inp] [[>]>outp] [/f:n] [/i] [/s:n] [/c:n] [/m:[n][,n]] [/d]
#   /d      Allow double-precision ATN, COS, EXP, LOG, SIN, SQR, and TAN. 
#   /f:n    Set maximum number of open files to n. Default is 3. 
#           Each additional file reduces free memory by 322 bytes.
#   /s:n    Set the maximum record length for RANDOM files. 
#           Default is 128, maximum is 32768.
#   /c:n    Set the COM receive buffer to n bytes. 
#           If n==0, disable the COM ports.   
# NOT IMPLEMENTED:
#   /i      Statically allocate file control blocks and data buffer.
#   /m:n,m  Set the highest memory location to n and maximum block size to m
gw_args = { 
    'double': 'd', 'max-files': 'f', 'max-reclen': 's', 'serial-buffer-size': 'c' 
    # 'max-memory': 'm', 'static-fcbs': 'i'
    }
    
# short-form arguments with single dash
short_args = { 
    'cli': 'b', 'ansi': 't', 'load': 'l', 
    'run': 'r', 'exec': 'e', 'quit': 'q', 'keys': 'k', 'version': 'v',
    }

# all long-form arguments
arguments = {
    'input': {'type': 'string', 'default': '', },
    'output': {'type': 'string', 'default': '', },
    'append': {'type': 'bool', 'default': 'False', },
    'cli': {'type': 'bool', 'default': 'False', },
    'ansi': {'type': 'bool', 'default': 'False', },
    'interface': { 
        'type': 'string', 'default': '',
        'choices': ('none', 'cli', 'ansi', 'graphical'), },
    'load': {'type': 'string', 'default': '', },
    'run': {'type': 'string', 'default': '',  },
    'convert': {'type': 'string', 'default': '', },
    'keys': {'type': 'string', 'default': '', },
    'exec': {'type': 'string', 'default': '',  },
    'quit': {'type': 'bool', 'default': 'False',},
    'double': {'type': 'bool', 'default': 'False',},
    'max-files': {'type': 'int', 'default': 3,}, 
    'max-reclen': {'type': 'int', 'default': 128,},
    'serial-buffer-size': {'type': 'int', 'default': 256,},
    'peek': {'type': 'list', 'default': [],},
    'lpt1': {'type': 'string', 'default': '',},
    'lpt2': {'type': 'string', 'default': '',},
    'lpt3': {'type': 'string', 'default': '',},
    'com1': {'type': 'string', 'default': '',},
    'com2': {'type': 'string', 'default': '',},
    'codepage': {'type': 'string', 'choices': encodings, 'default': '437',},
    'font': { 
        'type': 'list', 'choices': families, 
        'default': ['unifont', 'univga', 'freedos'],},
    'nosound': {'type': 'bool', 'default': 'False', },
    'dimensions': {'type': 'string', 'default': '',},
    'fullscreen': {'type': 'bool', 'default': 'False',},
    'noquit': {'type': 'bool', 'default': 'False',},
    'debug': {'type': 'bool', 'default': 'False',},
    'strict-hidden-lines': {'type': 'bool', 'default': 'False',},
    'strict-protect': {'type': 'bool', 'default': 'False',},
    'capture-caps': {'type': 'bool', 'default': 'False',},
    'mount': {'type': 'list', 'default': [],},
    'resume': {'type': 'bool', 'default': 'False',},
    'strict-newline': {'type': 'bool', 'default': 'False',},
    'syntax': { 
        'type': 'string', 'choices': ('advanced', 'pcjr', 'tandy'), 
        'default': 'advanced',},
    'pcjr-term': {'type': 'string', 'default': '',},
    'video': { 
        'type': 'string', 'default': 'vga',
        'choices': ('vga', 'ega', 'cga', 'cga_old', 'mda', 'pcjr', 'tandy',
                     'hercules', 'olivetti'), },
    'map-drives': {'type': 'bool', 'default': 'False',},
    'cga-low': {'type': 'bool', 'default': 'False',},
    'nobox': {'type': 'bool', 'default': 'False',},
    'utf8': {'type': 'bool', 'default': 'False',},
    'border': {'type': 'int', 'default': 5,},
    'mouse': {'type': 'string', 'default': 'copy,paste,pen',},
    'state': {'type': 'string', 'default': '',},
    'mono-tint': {'type': 'string', 'default': '255,255,255',},
    'monitor': { 
        'type': 'string', 'choices': ('rgb', 'composite', 'mono'),
        'default': 'rgb',},
    'aspect': {'type': 'string', 'default': '4,3',},
    'blocky': {'type': 'bool', 'default': 'False',},
    'version': {'type': 'bool', 'default': 'False',},
}


def prepare():
    """ Initialise config.py """
    global options
    # store options in options dictionary
    options = get_options()
    
def get_options():
    """ Retrieve command line and option file options. """
    arg_program = None    
    parser = None
    remaining = None
    # set default arguments
    args = {}
    for arg in arguments:
        try:
            args[arg] = arguments[arg]['default']
        except KeyError:
            pass
    # define argument parser
    if argparse:
        # we need to disable -h and re-enable it manually 
        # to avoid the wrong usage message from parse_known_args
        parser = argparse.ArgumentParser(add_help=False)
        remaining = sys.argv[1:]
        # unpack any packages and parse program arguments
        arg_program, remaining = parse_package(parser, remaining)
    # get arguments ad presets from specified config file
    conf_dict, remaining = parse_config(parser, remaining)
    # set defaults based on presets
    defaults, remaining = parse_presets(parser, remaining, conf_dict)
    args.update(defaults)
    # parse rest of command line
    if parser:
        args.update(parse_args(parser, remaining, args))
    # clean up arguments    
    for d in arguments:
        if d in args:
            if (arguments[d]['type'] == 'list'):
                args[d] = parse_list_arg(args[d])
            elif (arguments[d]['type'] == 'int'):
                args[d] = parse_int_arg(args[d])
            elif (arguments[d]['type'] == 'bool'):
                args[d] = parse_bool_arg(args[d])
    # any program given on the command line overrides that in config files    
    args['program'] = '' or arg_program
    return args        
            
def default_args(conf_dict):
    """ Return default arguments for this operating system. """
    args = {}
    for p in default_presets:
        try:
            args.update(conf_dict[p])
        except KeyError:
            pass
    return args

def parse_presets(parser, remaining, conf_dict):
    """ Parse presets. """
    presets = []
    if parser:
        parser.add_argument('--preset', nargs='*', action='append', 
                            choices=conf_dict.keys(), 
                            help='Load machine preset options')
        arg_presets, remaining = parser.parse_known_args(
                                    remaining if remaining else '')
        presets = parse_list_arg(arg_presets.preset)
    # get dictionary of default config
    defaults = default_args(conf_dict)
    # add any nested presets defined in [pcbasic] section
    try:
        presets += parse_list_config(conf_dict['pcbasic']['preset'])
    except KeyError:
        pass
    # set machine preset options; command-line args will override these
    if presets:
        for preset in presets:
            try:
                defaults.update(**conf_dict[preset])
            except KeyError:
                logging.warning('Preset %s not defined', preset)
    return defaults, remaining

def parse_package(parser, remaining):
    """ Load options from BAZ package, if specified. """
    global package
    # positional args: program or package name
    arg_package = None
    if (remaining and remaining[0] and 
        (len(remaining[0]) < 1 or remaining[0][0] != '-')):
        arg_package = remaining[0]
        remaining = remaining[1:]
    if arg_package and zipfile.is_zipfile(arg_package):
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
        return None, remaining
    else:
        # it's not a package, treat it as a BAS program.
        return arg_package, remaining

def parse_config(parser, remaining):
    """ Find the correct config file and read it. """
    # always read default config file
    conf_dict = read_config_file(os.path.join(plat.info_dir, plat.config_name))
    # find any overriding config file & read it
    config_file = None
    if os.path.exists(plat.config_name):
        config_file = plat.config_name
    if parser:    
        # parse any overrides    
        parser.add_argument('--config')
        arg_config, remaining = parser.parse_known_args(
                                    remaining if remaining else '')       
        if arg_config.config:
            if os.path.exists(arg_config.config):
                config_file = arg_config.config 
            else:
                logging.warning('Could not read configuration file %s. '
                    'Using %s instead', arg_config.config, config_file)    
    # update a whole preset at once, there's no joining of settings.                
    if config_file:
        conf_dict.update(read_config_file(config_file))
    return conf_dict, remaining
    
def parse_args(parser, remaining, default):
    """ Retrieve command line options. """
    # argparse converts hyphens into underscores
    # takes more code correcting for argparse than would reimplementing it?
    default_underscore = {}
    for key in default:
        key_corrected = key.replace('-', '_')
        default_underscore[key_corrected] = default[key]
    parser.set_defaults(**default_underscore)
    # manually re-enable -h
    parser.add_argument('--help', '-h', action='store_true')
    # set arguments
    for argname in sorted(arguments.keys()):
        kwparms = {} 
        for n in ['help', 'choices', 'metavar']:
            try:
                kwparms[n] = arguments[argname][n]            
            except KeyError:
                pass  
        if arguments[argname]['type'] in ('int', 'string'):
            kwparms['action'] = 'store'
        elif arguments[argname]['type'] == 'bool':
            kwparms['action'] = 'store'
            # need * because *!&^# argparse makes no distinction between
            # --foo empty and not specified for nargs='?'.
            kwparms['nargs'] = '*'
        elif arguments[argname]['type'] == 'list':
            kwparms['action'] = 'append'
            kwparms['nargs'] = '*'
        parms = ['--' + argname ]
        # add short options
        try:
            parms.append('-' + gw_args[argname])
        except KeyError:
            pass
        try:
            parms.append('-' + short_args[argname])
        except KeyError:
            pass
        parser.add_argument(*parms, **kwparms)
    # parse command line arguments to override defaults
    args = vars(parser.parse_args(remaining if remaining else ''))
    # turn bool args into something sensible
    for d in arguments:
        if d in args:
            if (arguments[d]['type'] == 'bool'):
                if args[d] == []:
                    args[d] = 'True'
                elif type(args[d]) is list:  
                    args[d] = args[d][-1]
    # and convert the underscores back into hyphens...    
    args_hyphen = {}
    for key in args:
        key_corrected = key.replace('_', '-')
        args_hyphen[key_corrected] = args[key]
    return args_hyphen

################################################

def read_config_file(config_file):
    """ Read config file. """
    path = plat.basepath
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(config_file)
    except (ConfigParser.Error, IOError):
        logging.warning('Error in configuration file %s. '
                        'Configuration not loaded.', config_file)
        return {}
    presets = { header: convert_config_file(dict(config.items(header))) 
                for header in config.sections() }    
    return presets

def convert_config_file(arglist):
    """ Convert list strings from option file to lists. """
    for d in arglist:
        # convert various boolean notations
        if d in arguments:
            if arguments[d]['type'] == 'list':
                arglist[d] = parse_list_config(arglist[d])
            elif arguments[d]['type'] in ('string', 'int', 'bool'):
                arglist[d] = '' if not arglist[d] else arglist[d]      
    return arglist        

def parse_list_config(s):
    lst = s.split(',')
    if lst == ['']:
        return []
    return lst

################################################
    
def parse_bool_arg(s):
    """ Parse bool option. Empty means True (like store_true). """
    if s == '':
        return True
    try:
        if s.upper() in ('YES', 'TRUE', 'ON'):
            return True
        elif s.upper() in ('NO', 'FALSE', 'OFF'):
            return False   
    except AttributeError:
        return None
    
def parse_list_arg(arglist):
    """ Convert lists of lists to one dimension. """
    newlist = []
    if arglist:
        for sublist in arglist:
            if type(sublist)==list:
                newlist += sublist
            else:
                newlist += [sublist]
    return newlist    

def parse_int_arg(inargs):
    """ Parse int option provided as a one-element list of string. """
    if inargs:
        try:
            return int(inargs)
        except ValueError:
            logging.warning('Illegal number value %s ignored', inargs)         
    return None

def parse_pair(option, default):
    """ Split a string option into int values. """
    if options[option]:
        try:
            sx, sy = options[option].split(',')
            x, y = int(sx), int(sy)
        except (ValueError, TypeError):
            logging.warning('Could not parse option: %s=%s. '
                            'Provide two values separated by a comma.', 
                            option, options[option]) 
        return x, y
    return default    

#########################################################

def make_ini():
    """ Write a default config file. """
    argnames = sorted(arguments.keys())
    f = open(plat.config_name, 'w')
    f.write('[pcbasic]\n')
    for a in argnames:
        f.write("# %s\n" % arguments[a]['help'])
        try:
            f.write('# %s=%s\n' % (a, arguments[a]['metavar']))
        except (KeyError, TypeError):
            pass
        try:
            f.write('# choices: %s\n' % repr(arguments[a]['choices']))
        except (KeyError, TypeError):
            pass
        if arguments[a]['type'] == 'list':
            formatted = ','.join(arguments[a]['default'])
        else:
            formatted = str(arguments[a]['default'])
        f.write("%s=%s\n" % (a, formatted))
    f.close()    
        
# initialise this module    
prepare()
    
