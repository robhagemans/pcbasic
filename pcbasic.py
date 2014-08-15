#!/usr/bin/env python

#
# PC-BASIC 3.23 
#
# GW-BASIC (R) compatible interpreter 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
# GW-BASIC is a trademark of Microsoft Corporation.
 
 
import sys
import os
from functools import partial             
             
import plat

# OS-specific stdin/stdout selection
# no stdin/stdout access allowed on packaged apps
if plat.system in ('OSX', 'Windows'):
    backend_dumb = None
    stdin_is_tty, stdout_is_tty = True, True
    stdin, stdout = None, None
else:
    # Unix, Linux including Android
    import backend_dumb
    import backend_ansi
    try:
        stdin_is_tty = sys.stdin.isatty()
        stdout_is_tty = sys.stdout.isatty()
    except AttributeError:
        stdin_is_tty, stdout_is_tty = True, True
        stdin, stdout = None, None
    stdin, stdout = sys.stdin, sys.stdout

if plat.system == 'Android':
    # crashes on Android
    argparse = None
else:
    import argparse

import ConfigParser
import logging

import run
import error
import expressions
import oslayer
import sound
import nosound
import nopenstick
import sound_beep
import console
import tokenise
import machine
import program
import unicodepage
import debug
import state
import backend
import backend_pygame
import iolayer
import var
import statements

greeting = 'PC-BASIC 3.23%s\r(C) Copyright 2013, 2014 PC-BASIC authors. Type RUN "@:INFO" for more.\r%d Bytes free\rOk\xff'
debugstr = ''

def main():
    reset = False
    args = get_args()
    # DEBUG, PCjr and Tandy modes
    prepare_keywords(args)
    # other command-line settings
    prepare_constants(args)
    try:
        if args.resume or plat.system == 'Android':
            # resume from saved emulator state
            args.resume = state.load()
        # choose the video and sound backends
        prepare_console(args)
        # choose peripherals    
        iolayer.prepare_devices(args)
        if not args.resume:    
            # print greeting
            if not args.run and not args.cmd and not args.conv:
                if stdin_is_tty:
                    console.write_line(greeting % (debugstr, var.total_mem))
            # execute arguments
            if args.run or args.load or args.conv and (args.program or stdin):
                program.load(oslayer.safe_open(args.program, "L", "R") if args.program else stdin)
            if args.conv and (args.outfile or stdout):
                program.save(oslayer.safe_open(args.outfile, "S", "W") if args.outfile else stdout, args.conv_mode)
                raise error.Exit()
            if args.run:
                args.cmd = 'RUN'
            # get out, if we ran with -q
            if args.cmd:    
                # start loop in execute mode
                run.execute(args.cmd)
        # start the interpreter loop
        run.loop(args.quit)
    except error.RunError as e:
        # errors during startup/conversion are handled here, then exit
        run.handle_error(e)  
    except error.Exit:
        pass
    except error.Reset:
        reset = True
    except KeyboardInterrupt:
        if args.debug:
            raise
    finally:
        if reset:
            state.delete()
        else:   
            state.save()
        # fix the terminal on exit or crashes (inportant for ANSI terminals)
        console.close()
        iolayer.close_all()
        iolayer.close_devices()
            
def prepare_keywords(args):
    global debugstr
    if args.debug:
        debug.debug_mode = True
        tokenise.insert_debug_keyword()
        # set logging format
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
        debugstr = ' [DEBUG mode]'
    else:
        # set logging format
        logging.basicConfig(format='%(levelname)s: %(message)s')
    if args.pcjr_syntax:
        statements.pcjr_syntax = args.pcjr_syntax
        expressions.pcjr_syntax = args.pcjr_syntax
        sound.pcjr_sound = args.pcjr_syntax
        tokenise.insert_noise_keyword()
        tokenise.insert_term_keyword() 
    # set pcjr TERM program    
    if args.pcjr_term:
        statements.pcjr_term = args.pcjr_term[0]
    if args.video:
        console.video_capabilities = args.video[0]
        
def prepare_constants(args):
    # PEEK presets
    if args.peek != None:
        try:
            for a in args.peek:
                seg, addr, val = a.split(':')
                machine.peek_values[int(seg)*0x10 + int(addr)] = int(val)
        except (TypeError, ValueError):
            pass     
    # drive mounts           
    if args.mount != None:
        try:
            for a in args.mount:
                # last one specified sticks
                letter, path = a.split(':',1)
                oslayer.drives[letter.upper()] = os.path.realpath(path)
                oslayer.drive_cwd[letter.upper()] = ''
        except (TypeError, ValueError):
            pass                
    # implied RUN invocations
    if args.program and not args.load and not args.conv:
        args.run = True   
    if args.double:
        expressions.option_double = True    
    if (not args.strict_hidden_lines) or args.conv:
        program.max_list_line = 65535    
    if (not args.strict_protect) or args.conv:
        program.dont_protect = True    
    if args.codepage:
        state.console_state.codepage = args.codepage
    if args.caps:
        state.console_state.caps = True    
    # rename exec argument for convenience
    try:
        args.cmd = getattr(args, 'exec') 
    except AttributeError:
        args.cmd = ''    
    if not args.cmd:
        args.cmd = ''   
    # set conversion output; first arg, if given, is mode; second arg, if given, is outfile
    args.conv_mode = 'A'
    args.outfile = None
    if args.conv:
        args.conv = args.conv.split(':')
        try:
            args.conv_mode = args.conv.pop(0)
            args.outfile = args.conv.pop(0)
        except IndexError:
            pass    
        args.conv = True    
    if args.conv_mode:
        args.conv_mode = args.conv_mode[0].upper()        
    if args.strict_newline:
        program.universal_newline = False
    else:
        program.universal_newline = True
    if args.windows_map_drives:
        oslayer.windows_map_drives()


def prepare_console(args):
    state.console_state.codepage = unicodepage.load_codepage(state.console_state.codepage)
    backend.penstick = nopenstick
    backend.sound = nosound
    if args.dumb or args.conv or (not args.graphical and not args.ansi and (not stdin_is_tty or not stdout_is_tty)):
        # redirected input or output leads to dumbterm use
        backend.video = backend_dumb
        backend.sound = sound_beep
    elif args.ansi and stdout_is_tty:
        backend.video = backend_ansi
        backend.sound = sound_beep
    else:   
        backend.video = backend_pygame   
        backend.penstick = backend_pygame
        backend.sound = backend_pygame
        backend_pygame.prepare(args)
    # initialise backends 
    if args.run:
        state.console_state.keys_visible = False
    if not console.init() and backend_dumb:
        logging.warning('Falling back to dumb-terminal.')
        backend.video = backend_dumb
        backend.sound = sound_beep        
        if not backend.video or not console.init():
            logging.critical('Failed to initialise console. Quitting.')
            sys.exit(0)
    # sound fallback        
    if args.nosound:
        backend.sound = nosound
    if not sound.init_sound():
        logging.warning('Failed to initialise sound. Sound will be disabled.')
        backend.sound = nosound
    # gwbasic-style redirected output is split between graphical screen and redirected file    
    if args.output:
        echo = partial(echo_ascii, f=oslayer.safe_open(args.output[0], "S", "W"))
        state.console_state.output_echos.append(echo) 
        state.console_state.input_echos.append(echo)
    if args.input:
        load_redirected_input(oslayer.safe_open(args.input[0], "L", "R"))       
    if args.max_files:
        iolayer.max_files = parse_int_option_silent(args.max_files)
    if args.max_reclen:
        iolayer.max_reclen = parse_int_option_silent(args.max_reclen)
        if iolayer.max_reclen < 1:
            iolayer.max_reclen = 1
        if iolayer.max_reclen > 32767:
            iolayer.max_reclen = 32767
    if args.serial_in_size:
        iolayer.serial_in_size = parse_int_option_silent(args.serial_in_size)

#############################################
# io redirection

# basic-style redirected input
def load_redirected_input(f):
    # read everything
    all_input = f.read()
    last = ''
    for c in all_input:
        # replace CRLF with CR
        if not (c == '\n' and last == '\r'):
            console.insert_key(c)
        last = c
    console.input_closed = True
   
# basic_style redirected output   
def echo_ascii(s, f):
    for c in s:
        f.write(c)
    f.flush()  

#############################################
# parse args and opts

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
    path = os.path.dirname(os.path.realpath(__file__))
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
        config = conf_dict['pcbasic']
        class Namespace(object):
            pass
        args = Namespace()            
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
    #
    # set arguments    
    parser.add_argument('program', metavar='basic_program', nargs='?', 
        help='Input program file to run (default), load or convert.')
    parser.add_argument('--input', metavar='input_file', nargs=1, 
        help='Retrieve keyboard input from input_file, except if KYBD: is read explicitly.')
    parser.add_argument('--output', metavar='output_file', nargs=1, 
        help='Send screen output to output_file, except if SCRN: is written to explicitly.')
    parser.add_argument('-b', '--dumb', action='store_true', 
        help='Use dumb text terminal. This is the default if redirecting input.')
    parser.add_argument('-t', '--ansi', action='store_true', 
        help='Use ANSI textmode terminal')
    parser.add_argument('-g', '--graphical', action='store_true', 
        help='Use graphical terminal. This is the normal default; use to override when redirecting i/o.')
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
    parser.add_argument('--conv', action='store', nargs='?', metavar='mode:outfile', help='Convert basic_program to (A)SCII, (B)ytecode or (P)rotected mode. Implies --unprotect and --list-all.')
    parser.add_argument('--codepage', action='store', metavar=('NUMBER'), help='Load specified font codepage; default is 437')
    parser.add_argument('--font-family', action='store', metavar=('TYPEFACE'), help='Load current codepage from specified font family.')
    parser.add_argument('--font', action='append', nargs='*', metavar=('TYPEFACE'), help='Load specified fonts. These are used for the appropriate resolutions, regardless of font-family and codepage seetings.')
    parser.add_argument('--nosound', action='store_true', help='Disable sound output')
    parser.add_argument('--dimensions', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for graphics mode. Default is 640,480. Use 640,400 or multiples for cleaner pixels - but incorrect aspect ratio - on square-pixel LCDs. Graphical terminal only.')
    parser.add_argument('--dimensions-text', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for text mode. Default is 640,400. Graphical terminal only.')
    parser.add_argument('--fullscreen', action='store_true', help='Fullscreen mode. This is unlikely to have either the correct aspect ratio or clean square pixels, but it does take up the whole screen. Graphical terminal only.')
    parser.add_argument('--smooth', action='store_true', help='Use smooth display scaling. Graphical terminal only.')
    parser.add_argument('--noquit', action='store_true', help='Allow BASIC to capture <ALT+F4>. Graphical terminal only.')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG keyword')
    parser.add_argument('--strict-hidden-lines', action='store_true', help='Disable listing and ASCII saving of lines beyond 65530 (as in GW-BASIC). Use with care as this allows execution of unseen statements.')
    parser.add_argument('--strict-protect', action='store_true', help='Disable listing and ASCII saving of protected files (as in GW-BASIC). Use with care as this allows execution of unseen statements.')
    parser.add_argument('--caps', action='store_true', help='Start in CAPS LOCK mode.')
    parser.add_argument('--mount', action='append', nargs='*', metavar=('D:PATH'), help='Set a drive letter to PATH.')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state. Most other arguments are ignored.')
#    parser.add_argument('--save-options', action='store', metavar=('FILENAME'), help='Save current options to specified .INI file')
    parser.add_argument('--strict-newline', action='store_true', help='Parse CR and LF strictly like GW-BASIC. May create problems with UNIX line endings.')
    # PCjr and Tandy options
    parser.add_argument('--pcjr-syntax', action='store', choices=('pcjr', 'tandy'), help='Enable PCjr/Tandy 1000 syntax extensions')
    parser.add_argument('--pcjr-term', action='store', help='Set the program run by the PCjr TERM command')
    parser.add_argument('--video', action='store', choices=('ega', 'pcjr', 'tandy'), help='Set video capabilities')
    parser.add_argument('--windows-map-drives', action='store_true', help='Map all Windows drive letters to PC-BASIC drive letters (Windows only)')
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


if __name__ == "__main__":
    main()
        
