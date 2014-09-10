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

import plat

if plat.system == 'Android':
    # crashes on Android
    argparse = None
else:
    import argparse

# config file
config_file = 'PCBASIC.INI'

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

# top line of usage statement
description = (
    'PC-BASIC 3.23 interpreter. '
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
    'cli': 'b', 'ansi': 't', 'graphical': 'g', 'load': 'l', 
    'run': 'r', 'exec': 'e', 'quit': 'q', 'keys': 'k' 
    }

# all long-form arguments
arguments = {
    'input':   {
        'type': 'string', 'metavar': 'input_file', 
        'help': 'Retrieve keyboard input from input_file, '
                'except if KYBD: is read explicitly.' },
    'output':  {
        'type': 'string', 'metavar': 'output_file', 
        'help': 'Send screen output to output_file, '
                'except if SCRN: is written to explicitly.' },
    'filter':  {
        'type': 'bool',  
        'help': 'Use text filter interface. '
                'This is the default if redirecting input.' },
    'cli': {
        'type': 'bool', 
        'help': 'Use command-line text interface' },
    'ansi': {
        'type': 'bool',
        'help': 'Use ANSI text interface' },
    'graphical': { 
        'type': 'bool',
        'help': 'Use graphical interface. This is the normal default; '
                'use to override when redirecting i/o.' },
    'load': {
        'type': 'bool',
        'help': 'Load in_file only, do not execute' },
    'run': {
        'type': 'bool',
        'help': 'Execute input file (default if in_file given)' },
    'keys': {
        'type': 'string', 'metavar':'keystring', 
        'help': 'Insert keys into the key buffer' },
    'exec': {
        'type': 'string', 'metavar': 'command_line', 
        'help': 'Execute BASIC command line' },
    'quit': {
        'type': 'bool', 
        'help': 'Quit interpreter when execution stops' },
    'double': {
        'type': 'bool',
        'help': 'Allow double-precision transcendental math functions' },
    'max_files': {
        'type': 'int', 'metavar':'NUMBER', 
        'help': 'Set maximum number of open files (default is 3).' },
    'max_reclen': { 
        'type': 'int', 'metavar':'NUMBER', 
        'help': 'Set maximum record length for RANDOM files ' 
                '(default is 128, max is 32767).' },
    'serial_in_size': { 
        'type': 'int', 'metavar':'NUMBER', 
        'help': 'Set serial input buffer size (default is 256). '
                'If 0, serial communications are disabled.' },
    'peek': { 
        'type': 'list', 'metavar':'SEG:ADDR:VAL', 
        'help': 'Define PEEK preset values' },
    'lpt1': { 
        'type': 'string', 'metavar':'TYPE:VAL', 
        'help': 'Set LPT1: to FILE:file_name or PRINTER:printer_name.' },
    'lpt2': { 
        'type': 'string', 'metavar':'TYPE:VAL', 
        'help': 'Set LPT2: to FILE:file_name or PRINTER:printer_name.' },
    'lpt3': { 
        'type': 'string', 'metavar':'TYPE:VAL', 
        'help': 'Set LPT3: to FILE:file_name or PRINTER:printer_name.' },
    'com1': { 
        'type': 'string', 'metavar':'TYPE:VAL', 
        'help': 'Set COM1: to PORT:device_name or SOCKET:host:socket.' },
    'com2': { 
        'type': 'string', 'metavar':'TYPE:VAL', 
        'help': 'Set COM2: to PORT:device_name or SOCKET:host:socket.' },
    'conv': { 
        'type': 'string', 'metavar':'mode:outfile', 
        'help': 'Convert basic_program to (A)SCII, (B)ytecode or '
                '(P)rotected mode.' },
    'codepage': { 
        'type': 'string', 'choices': encodings, 
        'help': 'Load specified font codepage; default is 437' },
    'font': { 
        'type': 'list', 'choices': families, 
        'help': 'Load current codepage from specified .hex fonts. '
                'Last fonts specified take precedence, previous ones are '
                'fallback. Default is unifont,univga,freedos.' },
    'nosound': { 
        'type': 'bool', 
        'help': 'Disable sound output' },
    'dimensions': { 
        'type': 'string', 'metavar':'X,Y', 
        'help': 'Set pixel dimensions for graphics mode. Default is 640,480. '
                'Use 640,400 or multiples for cleaner pixels - but incorrect '
                'aspect ratio - on square-pixel LCDs. '
                'Graphical interface only.' },
    'dimensions_text':  { 
        'type': 'string', 'metavar':'X,Y', 
        'help': 'Set pixel dimensions for text mode. Default is 640,400. '
                'Graphical interface only.' },
    'fullscreen': { 
        'type': 'bool',
        'help': 'Fullscreen mode. This is unlikely to have either the correct '
                'aspect ratio or clean square pixels, but it does take up the '
                'whole screen. Graphical interface only.' },
    'smooth': { 
        'type': 'bool',
        'help': 'Use smooth display scaling. Graphical interface only.' },
    'noquit': { 
        'type': 'bool',
        'help': 'Allow BASIC to capture <ALT+F4>. Graphical interface only.' },
    'debug': { 
        'type': 'bool',
        'help': 'Debugging mode.' },
    'strict_hidden_lines': { 
        'type': 'bool', 
        'help': 'Disable listing and ASCII saving of lines beyond 65530 '
                '(as in GW-BASIC). Use with care as this allows execution '
                'of invisible statements.' },
    'strict_protect': { 
        'type': 'bool', 
        'help': 'Disable listing and ASCII saving of protected files '
                '(as in GW-BASIC). Use with care as this allows execution '
                'of invisible statements.' },
    'capture_caps': {
        'type': 'bool',
        'help': "Handle CAPS LOCK; may collide with the operating system's "
                "own handling." },
    'mount': { 
        'type': 'list', 'metavar':'D:PATH', 
        'help': 'Assign a drive letter to a path.' },
    'resume': { 
        'type': 'bool', 
        'help': 'Resume from saved state. Most other arguments are ignored.' },
    'strict_newline': { 
        'type': 'bool', 
        'help': 'Parse CR and LF in files strictly like GW-BASIC. '
                'On Unix, you will need to convert your files to DOS text '
                'if using this.' },
    'pcjr_syntax': { 
        'type': 'string', 'choices': ('pcjr', 'tandy'), 
        'help': 'Enable PCjr/Tandy 1000 syntax extensions' },
    'pcjr_term': { 
        'type': 'string', 'metavar': 'TERM.BAS', 
        'help': 'Set the terminal program run by the PCjr TERM command' },
    'video': { 
        'type': 'string', 'choices': ('ega', 'cga', 'cga_old', 'pcjr', 'tandy'), 
        'help': 'Set video capabilities' },
    'windows_map_drives': { 
        'type': 'bool', 
        'help': 'Map all Windows drive letters to PC-BASIC drive letters '
                '(Windows only)' },
    'cga_low': { 
        'type': 'bool', 
        'help': 'Use low-intensity palettes in CGA '
                '(for --video={cga,ega} only).' },
    'composite': { 
        'type': 'bool', 
        'help': 'Emulates the output on an NTSC composite monitor. Disables '
                'smooth scaling. Enables colour artifacts on SCREEN 2 only '
                '(and crudely). Ignored for --video=ega' },
    'nobox': { 
        'type': 'bool', 
        'help': 'Disable box-drawing recognition for DBCS code pages' },
    'utf8': { 
        'type': 'bool', 
        'help': 'Use UTF-8 for ascii-mode programs and redirected i/o' },
}

def prepare():
    """ Initialise config.py """
    global options
    # store options in options dictionary
    options = get_options()
    
def get_options():
    """ Retrieve command line and option file options. """
    # read config file, if any
    conf_dict = read_config_file()
    if not argparse:
        # not available, use the preset defaults (this happens on Android)
        return default_args(conf_dict)
    else:    
        # read command line arguments
        return read_args(conf_dict)

def default_args(conf_dict):
    """ Return default arguments for this operating system. """
    args = {}
    for p in default_presets:
        try:
            args.update(conf_dict[p])
        except KeyError:
            pass
    return args
    
def read_args(conf_dict):
    """ Retrieve command line options. """
    # define argument parser
    # we need to disable -h and re-enable it manually 
    # to avoid the wrong usage message from parse_known_args
    parser = argparse.ArgumentParser(add_help=False, description=description)
    # parse presets
    parser.add_argument('--preset', nargs='*', choices=conf_dict.keys(), 
                        help='Load machine preset options')
    arg_presets, remaining = parser.parse_known_args()
    presets = parse_list_arg(arg_presets.preset)
    # get dictionary of default config
    defaults = default_args(conf_dict)
    # set machine preset options; command-line args will override these
    if presets:
        for preset in presets:
            try:
                defaults.update(**conf_dict[preset])
            except KeyError:
                logging.warning('Preset %s not found in configuration file %s', 
                                preset, config_file)
    # set defaults
    parser.set_defaults(**defaults)
    # positional args: program name
    parser.add_argument('program', metavar='basic_program', nargs='?', 
                help='Input program file to run (default), load or convert.')
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
    args = vars(parser.parse_args(remaining))
    # display help message if requested, and exit
    # this needs to be done here as we need the parser object to exist
    if args['help']:
        parser.print_help()
        sys.exit(0)
    for d in arguments:
        # flatten list arguments
        if (arguments[d]['type'] == 'list' and d in args):
            args[d] = parse_list_arg(args[d])
        # parse int parameters
        if (arguments[d]['type'] == 'int' and d in args):
            args[d] = parse_int_arg(args[d])
    return args

################################################

def read_config_file():
    """ Read config file. """
    path = plat.basepath
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(os.path.join(path, 'info', 'PCBASIC.INI'))
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
    return s.split(',')

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
        
# initialise this module    
prepare()
    
