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
import var
import expressions
import oslayer
import nosound
import sound_beep
import graphics
import console
import tokenise
import program
import unicodepage
import debug
import state
import backend_pygame
import io


greeting = 'PC-BASIC 3.23%s\r(C) Copyright 2013, 2014 PC-BASIC authors. Type RUN "@:INFO" for more.\r%d Bytes free'
debugstr = ''

def main():
    reset = False
    args = get_args()
    # DEBUG, PCjr and Tandy modes
    prepare_keywords(args)
    # other command-line settings
    prepare_constants(args)
    try:
        # initialise program memory
        program.new()
        if args.resume or plat.system == 'Android':
            # resume from saved emulator state
            args.resume = state.load()
            # can't currently jump into a running program
            program.set_runmode(False)
            # or into auto mode
            state.basic_state.auto_mode = False
        # choose the video and sound backends
        prepare_console(args)
        # choose peripherals    
        io.prepare_devices(args)
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
                args.cmd += ':RUN'
            # get out, if we ran with -q
            if args.quit:
                state.basic_state.prompt = False
                run.execute(args.cmd)
                raise error.Exit()
            # execute & handle exceptions; show Ok prompt
            run.execute(args.cmd)
        # go into interactive mode 
        run.loop()
    except error.RunError as e:
        # errors during startup/conversion are handled here, then exit
        e.handle_break()  
    except error.Exit:
        pass
    except error.Reset:
        reset = True
    except KeyboardInterrupt:
        if args.debug:
            raise
    except Exception as e:
        raise
    finally:
        if reset:
            state.delete()
        else:   
            # STOP execution as we can't handle jumping into a running program (yet)
            if state.basic_state.run_mode:
                state.basic_state.stop = state.basic_state.bytecode.tell()
                program.set_runmode(False) 
                error.write_error_message("Break", program.get_line_number(state.basic_state.stop))
                run.show_prompt()
            state.save()
        # fix the terminal on exit or crashes (inportant for ANSI terminals)
        console.exit()
        io.close_all()
        io.close_devices()
            
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
    if args.pcjr or args.tandy:
        tokenise.insert_noise_keyword()
    if args.pcjr:
        tokenise.insert_term_keyword()        

def prepare_constants(args):
    # PEEK presets
    if args.peek != None:
        try:
            for a in args.peek:
                seg, addr, val = a.split(':')
                var.peek_values[int(seg)*0x10 + int(addr)] = int(val)
        except Exception:
            pass     
    # drive mounts           
    if args.mount != None:
        try:
            for a in args.mount:
                # last one specified sticks
                letter, path = a.split(':',1)
                oslayer.drives[letter.upper()] = os.path.realpath(path)
                oslayer.drive_cwd[letter.upper()] = ''
        except Exception:
            pass                
    # implied RUN invocations
    if args.program and not args.load and not args.conv:
        args.run = True   
    if args.double:
        expressions.option_double = True    
    if args.list_all or args.conv:
        program.max_list_line = 65535    
    if args.unprotect or args.conv:
        program.dont_protect = True    
    if args.codepage:
        state.console_state.codepage = int(args.codepage)
    if args.caps:
        console.state.caps = True    
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

def prepare_console(args):
    unicodepage.load_codepage(state.console_state.codepage)
    if args.dumb or args.conv or (not args.graphical and not args.ansi and (not stdin_is_tty or not stdout_is_tty)):
        # redirected input or output leads to dumbterm use
        console.backend = backend_dumb
        console.sound = sound_beep
    elif args.ansi and stdout_is_tty:
        console.backend = backend_ansi
        console.sound = sound_beep
    else:   
        console.backend = backend_pygame   
        graphics.backend = backend_pygame
        graphics.backend.prepare(args)
        console.penstick = backend_pygame
        console.sound = backend_pygame
    # initialise backends 
    # on --resume, changes to state here get overwritten
    console.state.keys_visible = not args.run
    if not console.init() and backend_dumb:
        logging.warning('Falling back to dumb-terminal.')
        console.backend = backend_dumb
        console.sound = sound_beep        
        if not console.backend or not console.init():
            logging.critical('Failed to initialise console. Quitting.')
            sys.exit(0)
    # sound fallback        
    if args.nosound:
        console.sound = nosound
    if not console.sound.init_sound():
        logging.warning('Failed to initialise sound. Sound will be disabled.')
        console.sound = nosound
    # gwbasic-style redirected output is split between graphical screen and redirected file    
    if args.output:
        echo = partial(echo_ascii, f=oslayer.safe_open(args.output[0], "S", "W"))
        console.state.output_echos.append(echo) 
        console.state.input_echos.append(echo)
    if args.input:
        load_redirected_input(oslayer.safe_open(args.input[0], "L", "R"))       

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

   
def get_args():
    # GWBASIC invocation, for reference:
    # GWBASIC [filename] [<stdin] [[>]>stdout] [/f:n] [/i] [/s:n] [/c:n] [/m:[n][,n]] [/d]
    #   /d      Allow double-precision ATN, COS, EXP, LOG, SIN, SQR, and TAN. Implemented as -d or --double. 
    # NOT IMPLEMENTED:
    #   /f:n    set maximum number of open files to n. Default is 3. Each additional file reduces free memory by 322 bytes.
    #   /s:n    sets the maximum record length for RANDOM files. Default is 128, maximum is 32768.
    #   /c:n    sets the COM receive buffer to n bytes. If n==0, disable the COM ports.   
    #   /i      statically allocate file control blocks and data buffer.
    #   /m:n,m  sets the highest memory location to n and maximum block size to m
    if not argparse:
        config = read_config()
        class Namespace(object):
            pass
        args = Namespace()            
        for name in config:
            setattr(args, name, config[name])
        return args    
    parser = argparse.ArgumentParser(
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    # read config file, if any
    parser.set_defaults(**read_config())
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
    parser.add_argument('--peek', nargs='*', metavar=('SEG:ADDR:VAL'), help='Define PEEK preset values')
    parser.add_argument('--lpt1', action='store', metavar=('TYPE:VAL'), help='Set LPT1: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt2', action='store', metavar=('TYPE:VAL'), help='Set LPT2: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt3', action='store', metavar=('TYPE:VAL'), help='Set LPT3: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--com1', action='store', metavar=('TYPE:VAL'), help='Set COM1: to PORT:device_name or SOCK:host:socket.')
    parser.add_argument('--com2', action='store', metavar=('TYPE:VAL'), help='Set COM2: to PORT:device_name or SOCK:host:socket.')
    parser.add_argument('--conv', action='store', nargs='?', metavar='mode:outfile', help='Convert basic_program to (A)SCII, (B)ytecode or (P)rotected mode. Implies --unprotect and --list-all.')
    parser.add_argument('--codepage', action='store', metavar=('NUMBER'), help='Load specified font codepage. Default is 437 (US).')
    parser.add_argument('--nosound', action='store_true', help='Disable sound output')
    parser.add_argument('--dimensions', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for graphics mode. Default is 640,480. Use 640,400 or multiples for cleaner pixels - but incorrect aspect ratio - on square-pixel LCDs. Graphical terminal only.')
    parser.add_argument('--dimensions-text', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for text mode. Default is 640,400. Graphical terminal only.')
    parser.add_argument('--fullscreen', action='store_true', help='Fullscreen mode. This is unlikely to have either the correct aspect ratio or clean square pixels, but it does take up the whole screen. Graphical terminal only.')
    parser.add_argument('--smooth', action='store_true', help='Use smooth display scaling. Graphical terminal only.')
    parser.add_argument('--noquit', action='store_true', help='Allow BASIC to capture <ALT+F4>. Graphical terminal only.')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG keyword')
    parser.add_argument('--pcjr', action='store_true', help='Enable NOISE and TERM keywords')
    parser.add_argument('--tandy', action='store_true', help='Enable NOISE keyword')
    parser.add_argument('--list-all', action='store_true', help='Allow listing and ASCII saving of lines beyond 65530')
    parser.add_argument('--unprotect', action='store_true', help='Allow listing and ASCII saving of protected files')
    parser.add_argument('--caps', action='store_true', help='Start in CAPS LOCK mode.')
    parser.add_argument('--mount', action='append', nargs='*', metavar=('D:PATH'), help='Set a drive letter to PATH.')
    parser.add_argument('--resume', action='store_true', help='Resume from saved state. Most other arguments are ignored.')
    args = parser.parse_args()
    # flatten list arguments
    args.mount = flatten_arg_list(args.mount)
    args.peek = flatten_arg_list(args.peek)
    return args

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

def read_config():
    try:
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        path = os.path.dirname(os.path.realpath(__file__))
        config.read(os.path.join(path, 'info', 'PCBASIC.INI'))
        defaults = dict(config.items('pcbasic'))
        # convert booleans
        for d in defaults:
            if defaults[d].upper() in ('YES', 'TRUE', 'ON'):
                defaults[d] = True
            elif defaults[d].upper() in ('NO', 'FALSE', 'OFF'):
                defaults[d] = False
            elif defaults[d] == '':
                defaults[d] = None  
            else:
                defaults[d] = defaults[d].split(',')    
        return defaults          
    except Exception:
        return {}    

if __name__ == "__main__":
    main()
        
