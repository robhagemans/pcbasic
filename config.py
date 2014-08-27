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

import plat
import ConfigParser

import os

if plat.system == 'Android':
    # crashes on Android
    argparse = None
else:
    import argparse

    
def get_args():
    # GWBASIC invocation, for reference:
    # GWBASIC [filename] [<stdin] [[>]>stdout] [/f:n] [/i] [/s:n] [/c:n] [/m:[n][,n]] [/d]
    #   /d      Allow double-precision ATN, COS, EXP, LOG, SIN, SQR, and TAN. Implemented as -d or --double. 
    #   /f:n    set maximum number of open files to n. Default is 3. Each additional file reduces free memory by 322 bytes.
    #   /s:n    sets the maximum record length for RANDOM files. Default is 128, maximum is 32768.
    #   /c:n    sets the COM receive buffer to n bytes. If n==0, disable the COM ports.   
    # NOT IMPLEMENTED:
    #   /i      statically allocate file control blocks and data buffer.
    #   /m:n,m  sets the highest memory location to n and maximum block size to m
    #
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
    #
    # define argument parser   
    # we need to disable -h and re-enable it manually to avoid the wrong usage message from parse_known_args
    parser = argparse.ArgumentParser(add_help=False,
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    #
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
                logging.warning('Preset %s not found in PCBASIC.INI', preset)
    # set defaults
    parser.set_defaults(**defaults)
    # get supported codepages
    cpdir = os.listdir(os.path.join(plat.basepath, 'encoding'))
    encodings = sorted([ x[0] for x in [ c.split('.ucp') for c in cpdir ] if len(x)>1])
    # get supported font families
    fontdir = os.listdir(os.path.join(plat.basepath, 'font'))
    families = sorted(list(set([ x[0] for x in [ c.split('_') for c in fontdir ] if len(x)>1])))
    #
    # set arguments    
    parser.add_argument('program', metavar='basic_program', nargs='?', 
        help='Input program file to run (default), load or convert.')
    parser.add_argument('--input', metavar='input_file', nargs=1, 
        help='Retrieve keyboard input from input_file, except if KYBD: is read explicitly.')
    parser.add_argument('--output', metavar='output_file', nargs=1, 
        help='Send screen output to output_file, except if SCRN: is written to explicitly.')
    parser.add_argument('-b', '--dumb', action='store_true', 
        help='Use command-line interface. This is the default if redirecting input.')
    parser.add_argument('-t', '--ansi', action='store_true', 
        help='Use ANSI text interface')
    parser.add_argument('-g', '--graphical', action='store_true', 
        help='Use graphical interface. This is the normal default; use to override when redirecting i/o.')
    parser.add_argument('-l', '--load', action='store_true', help='Load in_file only, do not execute')
    parser.add_argument('-r', '--run', action='store_true', help='Execute input file (default if in_file given)')
    parser.add_argument('-e', '--exec', metavar='command_line', help='Execute BASIC command line')
    parser.add_argument('-q', '--quit', action='store_true', help='Quit interpreter when execution stops')
    parser.add_argument('-d', '--double', action='store_true', help='Allow double-precision math functions')
    parser.add_argument('-f', '--max-files', nargs=1, metavar=('NUMBER'), help='Set maximum number of open files (default is 3).')
    parser.add_argument('-s', '--max-reclen', nargs=1, metavar=('NUMBER'), help='Set maximum record length for RANDOM files (default is 128, max is 32767).')
    parser.add_argument('-c', '--serial-in-size', nargs=1, metavar=('NUMBER'), help='Set serial input buffer size (default is 256). If 0, serial communications are disabled.')
    parser.add_argument('--peek', nargs='*', metavar=('SEG:ADDR:VAL'), help='Define PEEK preset values')
    parser.add_argument('--lpt1', action='store', metavar=('TYPE:VAL'), help='Set LPT1: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt2', action='store', metavar=('TYPE:VAL'), help='Set LPT2: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt3', action='store', metavar=('TYPE:VAL'), help='Set LPT3: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--com1', action='store', metavar=('TYPE:VAL'), help='Set COM1: to PORT:device_name or SOCKET:host:socket.')
    parser.add_argument('--com2', action='store', metavar=('TYPE:VAL'), help='Set COM2: to PORT:device_name or SOCKET:host:socket.')
    parser.add_argument('--conv', action='store', nargs='?', metavar='mode:outfile', help='Convert basic_program to (A)SCII, (B)ytecode or (P)rotected mode.')
    parser.add_argument('--codepage', action='store', nargs=1, choices=encodings, help='Load specified font codepage; default is 437')
    parser.add_argument('--font', action='append', nargs='*', choices=families, help='Load current codepage from specified .hex fonts. Last fonts specified take precedent, previous ones are fallback. Default is unifont,univga,freedos.')
    parser.add_argument('--nosound', action='store_true', help='Disable sound output')
    parser.add_argument('--dimensions', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for graphics mode. Default is 640,480. Use 640,400 or multiples for cleaner pixels - but incorrect aspect ratio - on square-pixel LCDs. Graphical interface only.')
    parser.add_argument('--dimensions-text', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for text mode. Default is 640,400. Graphical interface only.')
    parser.add_argument('--fullscreen', action='store_true', help='Fullscreen mode. This is unlikely to have either the correct aspect ratio or clean square pixels, but it does take up the whole screen. Graphical interface only.')
    parser.add_argument('--smooth', action='store_true', help='Use smooth display scaling. Graphical interface only.')
    parser.add_argument('--noquit', action='store_true', help='Allow BASIC to capture <ALT+F4>. Graphical interface only.')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG keyword')
    parser.add_argument('--strict-hidden-lines', action='store_true', help='Disable listing and ASCII saving of lines beyond 65530 (as in GW-BASIC). Use with care as this allows execution of unseen statements.')
    parser.add_argument('--strict-protect', action='store_true', help='Disable listing and ASCII saving of protected files (as in GW-BASIC). Use with care as this allows execution of unseen statements.')
    parser.add_argument('--caps', action='store_true', help='Start in CAPS LOCK mode.')
    parser.add_argument('--mount', action='append', nargs='*', metavar=('D:PATH'), help='Set a drive letter to PATH.')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state. Most other arguments are ignored.')
#    parser.add_argument('--save-options', action='store', metavar=('FILENAME'), help='Save current options to specified .INI file')
    parser.add_argument('--strict-newline', action='store_true', help='Parse CR and LF strictly like GW-BASIC. May create problems with UNIX line endings.')
    # PCjr and Tandy options
    parser.add_argument('--pcjr-syntax', action='store', nargs=1, choices=('pcjr', 'tandy'), help='Enable PCjr/Tandy 1000 syntax extensions')
    parser.add_argument('--pcjr-term', action='store', metavar=('TERM.BAS'), help='Set the program run by the PCjr TERM command')
    parser.add_argument('--video', action='store', nargs=1, choices=('ega', 'cga', 'cga_old', 'pcjr', 'tandy'), help='Set video capabilities')
    parser.add_argument('--windows-map-drives', action='store_true', help='Map all Windows drive letters to PC-BASIC drive letters (Windows only)')
    parser.add_argument('--cga-low', action='store_true', help='Use low-intensity palettes in CGA (for --video={cga,ega} only).')
    parser.add_argument('--composite', action='store_true', help='Emulates the output on an NTSC composite monitor. Disables smooth scaling. Enables colour artifacts on SCREEN 2 only (and crudely). For --video={cga,cga_old,pcjr,tandy} only.')
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
    args.mount = flatten_arg_list(args.mount)
    args.peek = flatten_arg_list(args.peek)    
    args.font = flatten_arg_list(args.font)
    return args

def convert_arglist(arglist):
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
        return arglist        
    except (TypeError, ValueError):
        logging.warning('Error in config file PCBASIC.INI. Configuration not loaded.')
        return {}    

def read_config():
    path = plat.basepath
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(os.path.join(path, 'info', 'PCBASIC.INI'))
    except (ConfigParser.Error, IOError):
        logging.warning('Error in config file PCBASIC.INI. Configuration not loaded.')
        return {}
    presets = { header: convert_arglist(dict(config.items(header))) for header in config.sections() }    
    return presets
    
def flatten_arg_list(arglist):
    if arglist:
        newlist = []
        for sublist in arglist:
            if type(sublist)==list:
                newlist += sublist
            else:
                newlist += [sublist]    
        return newlist    
    return None    

# parse int option provided as a one-element list of string 
def parse_int_option_silent(inargs):
    if inargs:
        try:
            return int(inargs[0])
        except ValueError:
            pass        
    return None

