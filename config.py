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

# top line of usage statement
description = (
    'PC-BASIC 3.23 interpreter. '
    'A BAS program or BAZ package to run can be specified as the first argument. '
    'If no options are present, the interpreter will run in interactive mode.')

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
    'double': 'd', 'max_files': 'f', 'max_reclen': 's', 'serial_in_size': 'c' 
    # 'max_memory': 'm', 'static_fcbs': 'i'
    }
    
# short-form arguments with single dash
short_args = { 
    'cli': 'b', 'ansi': 't', 'load': 'l', 
    'run': 'r', 'exec': 'e', 'quit': 'q', 'keys': 'k', 'version': 'v',
    }

# all long-form arguments
arguments = {
    'input':   {
        'type': 'string', 'metavar': 'input_file', 'default': '',
        'help': 'Retrieve keyboard input from input_file, '
                'except if KYBD: is read explicitly.' },
    'output':  {
        'type': 'string', 'metavar': 'output_file', 'default': '',
        'help': 'Send screen output to output_file, '
                'except if SCRN: is written to explicitly.' },
    'append':  {
        'type': 'bool', 'default': 'False',
        'help': 'Append to output_file, do not overwrite. Use with --output.' },
    'cli': {
        'type': 'bool', 'default': 'False',
        'help': 'Use command-line text interface. Same as --interface=cli' },
    'ansi': {
        'type': 'bool', 'default': 'False',
        'help': 'Use ANSI text interface. Same as --interface=ansi' },
    'interface': { 
        'type': 'string', 'default': '',
        'choices': ('none', 'cli', 'ansi', 'graphical'),
        'help': 'Choose type of interface. When redirecting i/o, the default '
                'is none; otherwise, default is graphical.' },
    'load': {
        'type': 'bool', 'default': 'False',
        'help': 'Load in_file only, do not execute' },
    'run': {
        'type': 'bool', 'default': 'False',
        'help': 'Execute input file (default if in_file given)' },
    'keys': {
        'type': 'string', 'metavar':'keystring', 'default': '',
        'help': 'Insert keys into the key buffer' },
    'exec': {
        'type': 'string', 'metavar': 'command_line', 'default': '',
        'help': 'Execute BASIC command line' },
    'quit': {
        'type': 'bool', 'default': 'False',
        'help': 'Quit interpreter when execution stops' },
    'double': {
        'type': 'bool', 'default': 'False',
        'help': 'Allow double-precision transcendental math functions' },
    'max_files': {
        'type': 'int', 'metavar':'NUMBER', 'default': '3', 
        'help': 'Set maximum number of open files (default is 3).' },
    'max_reclen': { 
        'type': 'int', 'metavar':'NUMBER', 'default': '128',
        'help': 'Set maximum record length for RANDOM files ' 
                '(default is 128, max is 32767).' },
    'serial_in_size': { 
        'type': 'int', 'metavar':'NUMBER', 'default': '256',
        'help': 'Set serial input buffer size (default is 256). '
                'If 0, serial communications are disabled.' },
    'peek': { 
        'type': 'list', 'metavar':'SEG:ADDR:VAL', 'default': '',
        'help': 'Define PEEK preset values' },
    'lpt1': { 
        'type': 'string', 'metavar':'TYPE:VAL', 'default': '',
        'help': 'Set LPT1: to FILE:file_name or PRINTER:printer_name.' },
    'lpt2': { 
        'type': 'string', 'metavar':'TYPE:VAL', 'default': '',
        'help': 'Set LPT2: to FILE:file_name or PRINTER:printer_name.' },
    'lpt3': { 
        'type': 'string', 'metavar':'TYPE:VAL', 'default': '',
        'help': 'Set LPT3: to FILE:file_name or PRINTER:printer_name.' },
    'com1': { 
        'type': 'string', 'metavar':'TYPE:VAL', 'default': '',
        'help': 'Set COM1: to PORT:device_name or SOCKET:host:socket.' },
    'com2': { 
        'type': 'string', 'metavar':'TYPE:VAL', 'default': '',
        'help': 'Set COM2: to PORT:device_name or SOCKET:host:socket.' },
    'conv': { 
        'type': 'string', 'metavar':'mode:outfile', 'default': '',
        'help': 'Convert basic_program to (A)SCII, (B)ytecode or '
                '(P)rotected mode.' },
    'codepage': { 
        'type': 'string', 'choices': encodings, 'default': '437',
        'help': 'Load specified font codepage; default is 437' },
    'font': { 
        'type': 'list', 'choices': families, 
        'default': 'unifont,univga,freedos',
        'help': 'Load current codepage from specified .hex fonts. '
                'Last fonts specified take precedence, previous ones are '
                'fallback. Default is unifont,univga,freedos.' },
    'nosound': { 
        'type': 'bool', 'default': 'False', 
        'help': 'Disable sound output' },
    'dimensions': { 
        'type': 'string', 'metavar':'X,Y', 'default': '',
        'help': 'Set pixel dimensions for graphics mode. Overrides '
                '--blocky and --aspect.'
                'Graphical interface only.' },
    'fullscreen': { 
        'type': 'bool', 'default': 'False',
        'help': 'Fullscreen mode. Graphical interface only.' },
    'noquit': { 
        'type': 'bool', 'default': 'False',
        'help': 'Allow BASIC to capture <ALT+F4>. Graphical interface only.' },
    'debug': { 
        'type': 'bool', 'default': 'False',
        'help': 'Debugging mode.' },
    'strict_hidden_lines': { 
        'type': 'bool', 'default': 'False',
        'help': 'Disable listing and ASCII saving of lines beyond 65530 '
                '(as in GW-BASIC). Use with care as this allows execution '
                'of invisible statements.' },
    'strict_protect': { 
        'type': 'bool', 'default': 'False',
        'help': 'Disable listing and ASCII saving of protected files '
                '(as in GW-BASIC). Use with care as this allows execution '
                'of invisible statements.' },
    'capture_caps': {
        'type': 'bool', 'default': 'False',
        'help': "Handle CAPS LOCK; may collide with the operating system's "
                "own handling." },
    'mount': { 
        'type': 'list', 'metavar':'D:PATH', 'default': '',
        'help': 'Assign a drive letter to a path.' },
    'resume': { 
        'type': 'bool', 'default': 'False',
        'help': 'Resume from saved state. Most other arguments are ignored.' },
    'strict_newline': { 
        'type': 'bool', 'default': 'False',
        'help': 'Parse CR and LF in files strictly like GW-BASIC. '
                'On Unix, you will need to convert your files to DOS text '
                'if using this.' },
    'pcjr_syntax': { 
        'type': 'string', 'choices': ('pcjr', 'tandy'), 'default': '',
        'help': 'Enable PCjr/Tandy 1000 syntax extensions' },
    'pcjr_term': { 
        'type': 'string', 'metavar': 'TERM.BAS', 'default': '',
        'help': 'Set the terminal program run by the PCjr TERM command' },
    'video': { 
        'type': 'string', 'default': 'vga',
        'choices': ('vga', 'ega', 'cga', 'cga_old', 'mda', 'pcjr', 'tandy',
                     'hercules', 'olivetti'), 
        'help': 'Set the video card to emulate.' },
    'map_drives': { 
        'type': 'bool', 'default': 'False',
        'help': 'Map all Windows drive letters to PC-BASIC drive letters '
                '(Windows only)' },
    'cga_low': { 
        'type': 'bool', 'default': 'False',
        'help': 'Use low-intensity palettes in CGA '
                '(for --video={cga, ega, vga} only).' },
    'nobox': { 
        'type': 'bool', 'default': 'False',
        'help': 'Disable box-drawing recognition for DBCS code pages' },
    'utf8': { 
        'type': 'bool', 'default': 'False',
        'help': 'Use UTF-8 for ascii-mode programs and redirected i/o' },
    'border': { 
        'type': 'int', 'default': '5',
        'help': 'Width of the screen border as a percentage 0-100 '
                '(graphical interface only).' },
    'mouse': {
        'type': 'string', 'metavar': 'left,middle,right', 
        'default': 'copy,paste,pen',
        'help': 'Set the functions of the three mouse buttons '
                '(copy,paste,pen).' },
    'state': {
        'type': 'string', 'metavar': plat.state_name, 'default': '',
        'help': 'Set the save-state file. Default is info/%s' % 
                plat.state_name },                
    'mono_tint': {
        'type': 'string', 'metavar': 'r,g,b', 'default': '255,255,255',
        'help': 'Specify the monochrome tint as RGB, each in the range 0-255' },
    'monitor': { 
        'type': 'string', 'choices': ('rgb', 'composite', 'mono'),
        'default': 'rgb',
        'help': 'Sets the monitor type to emulate.' 
                'Composite enables colour artifacts, crudely, on SCREEN 2 only '
                'and is not allowed for --video=ega' },
    'aspect': {
        'type': 'string', 'metavar': 'x,y', 'default': '4,3',
        'help': 'Set the display aspect ratio to x/y. '
                'Graphical interface only.' },
    'blocky': {
        'type': 'bool', 'default': 'False',
        'help': 'Choose whole multiples of pixel size for display and do not '
                'smoothen. Overrides --aspect. Graphical interface only.' },                
    'program': {
        'type': 'string', 'default': '',
        'metavar': 'PROGRAM.BAS',  
        'help': 'Run the specified .BAS program. '
                'If --load is given, only load; if --conv is given, convert.'},
    'version': {
        'type': 'bool', 'default': 'False',
        'help': 'Print version and exit'},
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
    if argparse:
        # define argument parser
        # we need to disable -h and re-enable it manually 
        # to avoid the wrong usage message from parse_known_args
        parser = argparse.ArgumentParser(
                        add_help=False, description=description, 
                        usage='%(prog)s [program_or_package] [options]')
        remaining = sys.argv[1:]
        # unpack any packages and parse program arguments
        arg_program, remaining = parse_package(parser, remaining)
    # parse config file
    conf_dict, remaining = parse_config(parser, remaining)
    if parser:
        # set defaults based on presets
        defaults, remaining = parse_presets(parser, remaining, conf_dict)
        parser.set_defaults(**defaults)
        # parse rest of command line
        args = read_args(parser, remaining, conf_dict) 
    else:
        # not available, use the preset defaults (this happens on Android)
        args = default_args(conf_dict)
    for d in arguments:
        # flatten list arguments
        if (arguments[d]['type'] == 'list' and d in args):
            args[d] = parse_list_arg(args[d])
        # parse int parameters
        if (arguments[d]['type'] == 'int' and d in args):
            args[d] = parse_int_arg(args[d])
    # any program given on the command line overrides that in config files    
    if arg_program:
        args['program'] = arg_program        
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
    # find default config file
    if os.path.exists(plat.config_name):
        config_file = plat.config_name
    else:
        config_file = os.path.join(plat.info_dir, plat.config_name)
    if parser:    
        # parse any overrides    
        parser.add_argument('--config', metavar=plat.config_name, 
            help='Read configuration file. Default is info/%s' % 
                 plat.config_name)
        arg_config, remaining = parser.parse_known_args(
                                    remaining if remaining else '')       
        if arg_config.config:
            if os.path.exists(arg_config.config):
                config_file = arg_config.config 
            else:
                logging.warning('Could not read configuration file %s. '
                    'Using %s instead', arg_config.config, config_file)    
    return read_config_file(config_file), remaining
    
def read_args(parser, remaining, conf_dict):
    """ Retrieve command line options. """
    # set arguments
    for argname in arguments:
        kwparms = {} 
        for n in ['help', 'choices', 'metavar']:
            try:
                kwparms[n] = arguments[argname][n]            
            except KeyError:
                pass  
        if arguments[argname]['type'] in ('int', 'string'):
            kwparms['action'] = 'store'
        elif arguments[argname]['type'] == 'bool':
            kwparms['action'] = 'store_true'
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
    # manually re-enable -h
    parser.add_argument('-h', '--help', action='store_true', 
                        help='Show this message and exit')
    # parse command line arguments to override defaults
    args = vars(parser.parse_args(remaining if remaining else ''))
    # display help message if requested, and exit
    # this needs to be done here as we need the parser object to exist
    if args['help']:
        parser.print_help()
        sys.exit(0)
    return args

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
            if arguments[d]['type'] == 'bool':
                arglist[d] = parse_bool_config(arglist[d])
            elif arguments[d]['type'] == 'list':
                arglist[d] = parse_list_config(arglist[d])
            elif arguments[d]['type'] in ('string', 'int'):
                arglist[d] = '' if not arglist[d] else arglist[d]      
    return arglist        

def parse_list_config(s):
    lst = s.split(',')
    if lst == ['']:
        return []
    return lst

def parse_bool_config(s):
    """ Parse bool option from config file. """
    try:
        if s.upper() in ('YES', 'TRUE', 'ON'):
            return True
        elif s.upper() in ('NO', 'FALSE', 'OFF'):
            return False   
    except AttributeError:
        pass
    return None
    
################################################
    
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
            f.write('# choices: %s\n' % repr(arguments[a]['choices']))
        except (KeyError, TypeError):
            pass
        f.write("%s=%s\n" % (a, arguments[a]['default']))
    f.close()    
        
# initialise this module    
prepare()
    
