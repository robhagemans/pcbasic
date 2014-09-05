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

import plat

if plat.system == 'Android':
    # crashes on Android
    argparse = None
else:
    import argparse

# config file
config_file = 'PCBASIC.INI'

# get supported codepages
encodings = sorted([ x[0] for x in [ c.split('.ucp') for c in os.listdir(plat.encoding_dir) ] if len(x)>1])
# get supported font families
families = sorted(list(set([ x[0] for x in [ c.split('_') for c in os.listdir(plat.font_dir) ] if len(x)>1])))

# dictionary to hold all options chosen
options = {}


# GWBASIC invocation, for reference:
# GWBASIC [filename] [<stdin] [[>]>stdout] [/f:n] [/i] [/s:n] [/c:n] [/m:[n][,n]] [/d]
#   /d      Allow double-precision ATN, COS, EXP, LOG, SIN, SQR, and TAN. Implemented as -d or --double. 
#   /f:n    set maximum number of open files to n. Default is 3. Each additional file reduces free memory by 322 bytes.
#   /s:n    sets the maximum record length for RANDOM files. Default is 128, maximum is 32768.
#   /c:n    sets the COM receive buffer to n bytes. If n==0, disable the COM ports.   
# NOT IMPLEMENTED:
#   /i      statically allocate file control blocks and data buffer.
#   /m:n,m  sets the highest memory location to n and maximum block size to m
gw_args = { 'double':'d', 'max_files':'f', 'max_reclen':'s', 'serial_in_size':'c' } # 'max_memory':'m', 'static_fcbs':'i'

# short-form arguments with single dash
short_args = { 'cli':'b', 'ansi':'t', 'graphical':'g', 'load':'l', 'run':'r', 'exec':'e', 'quit':'q', 'keys':'k' }

# all long-form arguments
arguments = {
#    'program':  { 'metavar':'basic_program', 'nargs':'?', 'help':'Input program file to run (default), load or convert.' },
    'input':            { 'action':'store', 'metavar':'input_file', 'nargs':1, 'help':'Retrieve keyboard input from input_file, except if KYBD: is read explicitly.' },
    'output':           { 'action':'store', 'metavar':'output_file', 'nargs':1, 'help':'Send screen output to output_file, except if SCRN: is written to explicitly.' },
    'filter':           { 'action':'store_true', 'help':'Use text filter interface. This is the default if redirecting input.' },
    'cli':              { 'action':'store_true', 'help':'Use command-line text interface' },
    'ansi':             { 'action':'store_true', 'help':'Use ANSI text interface' },
    'graphical':        { 'action':'store_true', 'help':'Use graphical interface. This is the normal default; use to override when redirecting i/o.' },
    'load':             { 'action':'store_true', 'help':'Load in_file only, do not execute' },
    'run':              { 'action':'store_true', 'help':'Execute input file (default if in_file given)' },
    'keys':             { 'metavar':'keystring', 'help':'Insert keys into the key buffer' },
    'exec':             { 'metavar':'command_line', 'help':'Execute BASIC command line' },
    'quit':             { 'action':'store_true', 'help':'Quit interpreter when execution stops' },
    'double':           { 'action':'store_true', 'help':'Allow double-precision math functions' },
    'max_files':        { 'type':'int', 'action':'store', 'metavar':'NUMBER', 'help':'Set maximum number of open files (default is 3).' },
    'max_reclen':       { 'type':'int', 'action':'store', 'metavar':'NUMBER', 'help':'Set maximum record length for RANDOM files (default is 128, max is 32767).' },
    'serial_in_size':   { 'type':'int', 'action':'store', 'metavar':'NUMBER', 'help':'Set serial input buffer size (default is 256). If 0, serial communications are disabled.' },
    'peek':             { 'type':'list', 'action':'store', 'nargs':'*', 'metavar':'SEG:ADDR:VAL', 'help':'Define PEEK preset values' },
    'lpt1':             { 'action':'store', 'metavar':'TYPE:VAL', 'help':'Set LPT1: to FILE:file_name or PRINTER:printer_name.' },
    'lpt2':             { 'action':'store', 'metavar':'TYPE:VAL', 'help':'Set LPT2: to FILE:file_name or PRINTER:printer_name.' },
    'lpt3':             { 'action':'store', 'metavar':'TYPE:VAL', 'help':'Set LPT3: to FILE:file_name or PRINTER:printer_name.' },
    'com1':             { 'action':'store', 'metavar':'TYPE:VAL', 'help':'Set COM1: to PORT:device_name or SOCKET:host:socket.' },
    'com2':             { 'action':'store', 'metavar':'TYPE:VAL', 'help':'Set COM2: to PORT:device_name or SOCKET:host:socket.' },
    'conv':             { 'action':'store', 'nargs':'?', 'metavar':'mode:outfile', 'help':'Convert basic_program to (A)SCII, (B)ytecode or (P)rotected mode.' },
    'codepage':         { 'type':'string', 'action':'store', 'choices':encodings, 'help':'Load specified font codepage; default is 437' },
    'font':             { 'action':'append', 'nargs':'*', 'choices':families, 'help':'Load current codepage from specified .hex fonts. Last fonts specified take precedent, previous ones are fallback. Default is unifont,univga,freedos.' },
    'nosound':          { 'action':'store_true', 'help':'Disable sound output' },
    'dimensions':       { 'nargs':2, 'metavar':('X', 'Y'), 'help':'Set pixel dimensions for graphics mode. Default is 640,480. Use 640,400 or multiples for cleaner pixels - but incorrect aspect ratio - on square-pixel LCDs. Graphical interface only.' },
    'dimensions_text':  { 'nargs':2, 'metavar':('X', 'Y'), 'help':'Set pixel dimensions for text mode. Default is 640,400. Graphical interface only.' },
    'fullscreen':       { 'action':'store_true', 'help':'Fullscreen mode. This is unlikely to have either the correct aspect ratio or clean square pixels, but it does take up the whole screen. Graphical interface only.' },
    'smooth':           { 'action':'store_true', 'help':'Use smooth display scaling. Graphical interface only.' },
    'noquit':           { 'action':'store_true', 'help':'Allow BASIC to capture <ALT+F4>. Graphical interface only.' },
    'debug':            { 'action':'store_true', 'help':'Enable DEBUG keyword' },
    'strict_hidden_lines':{ 'type':'bool', 'action':'store_true', 'help':'Disable listing and ASCII saving of lines beyond 65530 (as in GW-BASIC). Use with care as this allows execution of unseen statements.' },
    'strict_protect':   { 'type':'bool', 'action':'store_true', 'help':'Disable listing and ASCII saving of protected files (as in GW-BASIC). Use with care as this allows execution of unseen statements.' },
    'capture_caps':     { 'action':'store_true', 'help':"Handle CAPS LOCK; may collide with the operating system's own handling." },
    'mount':            { 'type':'list', 'action':'append', 'nargs':'*', 'metavar':'D:PATH', 'help':'Set a drive letter to PATH.' },
    'resume':           { 'action':'store_true', 'help':'Resume from saved state. Most other arguments are ignored.' },
    'strict_newline':   { 'type':'bool', 'action':'store_true', 'help':'Parse CR and LF strictly like GW-BASIC. May create problems with UNIX line endings.' },
    'pcjr_syntax':      { 'type':'string', 'action':'store', 'choices':('pcjr', 'tandy'), 'help':'Enable PCjr/Tandy 1000 syntax extensions' },
    'pcjr_term':        { 'type':'string', 'action':'store', 'metavar':'TERM.BAS', 'help':'Set the program run by the PCjr TERM command' },
    'video':            { 'action':'store', 'nargs':1, 'choices':('ega', 'cga', 'cga_old', 'pcjr', 'tandy'), 'help':'Set video capabilities' },
    'windows_map_drives':{ 'type':'bool', 'action':'store_true', 'help':'Map all Windows drive letters to PC-BASIC drive letters (Windows only)' },
    'cga_low':          { 'action':'store_true', 'help':'Use low-intensity palettes in CGA (for --video={cga,ega} only).' },
    'composite':        { 'action':'store_true', 'help':'Emulates the output on an NTSC composite monitor. Disables smooth scaling. Enables colour artifacts on SCREEN 2 only (and crudely). For --video={cga,cga_old,pcjr,tandy} only.' },
    'nobox':            { 'action':'store_true', 'help':'Disable box-drawing recognition for DBCS code pages' },
    'utf8':             { 'type':'bool', 'action':'store_true', 'help':'Load and save "ascii" files as UTF-8.' },
}

def prepare():
    """ Initialise config.py """
    global options
    # store options in options dictionary
    options = vars(get_args())
    
def get_args():
    """ Retrieve command line and option file options. """
    # read config file, if any
    conf_dict = read_config()
    # if argparse module not available, use the preset defaults (this happens on Android)
    if not argparse:
        presets = ['pcbasic']
        if plat.system == 'Android':
            presets += ['android']
        class Namespace(object):
            pass
        args = Namespace()
        for p in presets:
            config = conf_dict[p]
            for name in config:
                setattr(args, name, config[name])
        return args
    # define argument parser
    # we need to disable -h and re-enable it manually to avoid the wrong usage message from parse_known_args
    parser = argparse.ArgumentParser(add_help=False,
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    # parse presets
    parser.add_argument('--preset', nargs='*', choices=conf_dict.keys(), help='Load machine preset options')
    arg_presets, remaining = parser.parse_known_args()
    presets = flatten_arg_list(arg_presets.preset)
    # get dictionary of default config
    defaults = conf_dict['pcbasic']
    # set machine preset options; command-line args will override these
    if presets:
        for preset in presets:
            try:
                defaults.update(**conf_dict[preset])
            except KeyError:
                logging.warning('Preset %s not found in configuration file %s', preset, config_file)
    # set defaults
    parser.set_defaults(**defaults)
    # positional args
    parser.add_argument('program', metavar='basic_program', nargs='?', help='Input program file to run (default), load or convert.')
    # set arguments
    for argname in arguments:
        kwparms = {} 
        for n in ['acrion', 'help', 'choices', 'metavar', 'nargs']:
            try:
                kwparms[n] = arguments[n]            
            except KeyError:
                pass    
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
    parser.add_argument('-h', '--help', action='store_true', help='Show this message and exit')
    # parse command line arguments to override defaults
    args = parser.parse_args(remaining)
    # display help message if requested, and exit
    # this needs to be done here as we need the parser object to exist
    if args.help:
        parser.print_help()
        sys.exit(0)
    # flatten list arguments
    args.font = flatten_arg_list(args.font)
    for d in arguments:
        if hasattr(args, d) and arguments[d].has_key('type') and arguments[d]['type'] == 'list':
            setattr(args, d, flatten_arg_list(getattr(args, d)))
        if hasattr(args, d) and arguments[d].has_key('type') and arguments[d]['type'] == 'int':
            setattr(args, d, parse_int_option_silent(getattr(args, d)))
    return args

def convert_arglist(arglist):
    """ Convert list strings from option file to lists. """
    try:
        for d in arglist:
            # convert various boolean notations
            if arglist[d].upper() in ('YES', 'TRUE', 'ON'):
                arglist[d] = True
            elif arglist[d].upper() in ('NO', 'FALSE', 'OFF'):
                arglist[d] = False
            elif arglist[d] == '':
                arglist[d] = None  
            else:
                # convert lists
                arglist[d] = arglist[d].split(',')    
    except (TypeError, ValueError):
        logging.warning('Error in configuration file %s. Configuration not loaded.', config_file)
        return {}    
    for d in arguments:
        if d in arglist and arguments[d].has_key('type') and arguments[d]['type'] == 'string':
            arglist[d] = '' if not arglist[d] else arglist[d][0]
    return arglist        

def read_config():
    """ Read config file. """
    path = plat.basepath
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(os.path.join(path, 'info', 'PCBASIC.INI'))
    except (ConfigParser.Error, IOError):
        logging.warning('Error in configuration file %s. Configuration not loaded.', config_file)
        return {}
    presets = { header: convert_arglist(dict(config.items(header))) for header in config.sections() }    
    return presets
    
def flatten_arg_list(arglist):
    """ Convert lists of lists to one dimension. """
    if arglist:
        newlist = []
        for sublist in arglist:
            if type(sublist)==list:
                newlist += sublist
            else:
                newlist += [sublist]    
        return newlist    
    return None    

def parse_int_option_silent(inargs):
    """ Parse int option provided as a one-element list of string. """
    if inargs:
        try:
            return int(inargs[0])
        except ValueError:
            pass        
    return None

# initialise this module    
prepare()
    
