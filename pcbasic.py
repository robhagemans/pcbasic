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
import logging
import argparse
import platform
# for autosave
import os
import tempfile
             
import run
import error
import var
import deviceio
import fileio
import util
import expressions
import oslayer
import statements
import nosound
import sound_beep
import graphics
import console
import tokenise
import program
import unicodepage

if platform.system() == 'Linux':
    import backend_dumb
    stdin_is_tty = sys.stdin.isatty()
    stdout_is_tty = sys.stdout.isatty()
    stdin, stdout = sys.stdin, sys.stdout
else:
    backend_dumb = None
    # no stdin/stdout access allowed on Win & OSX packaged apps
    stdin_is_tty, stdout_is_tty = True, True
    stdin, stdout = None, None
    

greeting = 'PC-BASIC 3.23%s\r(C) Copyright 2013, 2014 PC-BASIC authors. Type RUN "INFO" for more.\r%d Bytes free'
debugstr = ''

def main():
    args = get_args()
    # DEBUG mode
    prepare_debug(args)
    # other command-line settings
    prepare_constants(args)
    try:
        # choose the video and sound backends
        prepare_console(args)
        # choose peripherals    
        deviceio.init_devices(args)
        # initialise program memory
        program.new()
        # print greeting
        if not args.run and not args.cmd and not args.conv:
            if stdin_is_tty:
                console.write_line(greeting % (debugstr, var.total_mem))
        # execute arguments
        if args.run or args.load or args.conv and (args.infile or stdin):
            program.load(oslayer.safe_open(args.infile, "L", "R") if args.infile else stdin)
        if args.conv and (args.outfile or stdout):
            program.save(oslayer.safe_open(args.outfile, "S", "W") if args.outfile else stdout, args.conv)
            run.exit()
        if not args.cmd:
            # if a command is given, the program is only loaded; run.loop() doesn't take None.
            args.cmd = 'RUN' if args.run else ''
        # get out, if we ran with -q
        if args.quit:
            run.prompt = False
            run.execute(args.cmd)
            run.exit()
        # execute & handle exceptions; show Ok prompt
        run.execute(args.cmd)
        # go into interactive mode 
        run.loop()
    except error.RunError as e:
        # errors during startup/conversion are handled here, then exit
        e.handle_break()    
    except KeyboardInterrupt:
        if args.debug:
            raise
        else:    
            run.exit()    
    finally:
        # fix the terminal on exit or crashes (inportant for ANSI terminals)
        console.exit()
        # autosave any file in memory
        if program.bytecode:
            program.protected = False
            autosave = os.path.join(tempfile.gettempdir(), "AUTOSAVE.BAS")
            program.save(oslayer.safe_open(autosave, "S", "W"), 'B')
            
def prepare_debug(args):
    global debugstr
    tokenise.init_DEBUG(args.debug)
    if args.debug:
        # set logging format
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
        debugstr = ' [DEBUG mode]'
    else:
        # set logging format
        logging.basicConfig(format='%(levelname)s: %(message)s')

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
                letter, path = a.split(':',1)
                oslayer.drives[letter] = path
        except Exception:
            pass                
    # implied RUN invocations
    if args.infile and not args.load and not args.conv:
        args.run = True    
    if args.double:
        expressions.option_double = True    
    if args.list_all or args.conv:
        program.max_list_line = 65535    
    if args.unprotect or args.conv:
        program.dont_protect = True    
    if args.codepage:
        console.codepage = int(args.codepage[0])
    if args.caps:
        console.caps = True    

def prepare_console(args):
    unicodepage.load_codepage(console.codepage)
    if args.dumb or args.conv or (not args.graphical and not args.text and not stdin_is_tty):
        # redirected input leads to dumbterm use
        console.backend = backend_dumb
        console.sound = sound_beep
    elif args.text and stdout_is_tty:
        import backend_ansi
        console.backend = backend_ansi
        console.sound = sound_beep
    else:   
        import backend_pygame
        console.backend = backend_pygame   
        graphics.backend = backend_pygame
        graphics.backend.prepare(args)
        console.penstick = backend_pygame
        console.sound = backend_pygame
        # redirected output is split between graphical screen and redirected file    
        if not stdout_is_tty:
            console.output_echos.append(backend_dumb.echo_stdout) 
            console.input_echos.append(backend_dumb.echo_stdout)   
    # initialise backends
    console.keys_visible = (not args.run and args.cmd == None)
    if not console.init() and backend_dumb:
        logging.warning('Falling back to dumb-terminal.\n')
        console.backend = backend_dumb
        console.sound = sound_beep        
    if not console.init():
        logging.critial('Failed to initialise console.\n')
        sys.exit(0)
    if args.nosound:
        console.sound = nosound
    if not console.sound.init_sound():
        logging.warning('Failed to initialise sound. Sound will be disabled.\n')
        console.sound = nosound
   
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
    parser = argparse.ArgumentParser(
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    parser.add_argument('infile', metavar='in_file', nargs='?', 
        help='Input program file to run (default), load or convert.')
    parser.add_argument('outfile', metavar='out_file', nargs='?', 
        help='Output program file. If no --conv option is specified, this is ignored.')
    parser.add_argument('-b', '--dumb', action='store_true', 
        help='Use dumb text terminal. This is the default if redirecting input.')
    parser.add_argument('-t', '--text', action='store_true', 
        help='Use ANSI textmode terminal')
    parser.add_argument('-g', '--graphical', action='store_true', 
        help='Use graphical terminal. This is the normal default; use to override when redirecting i/o.')
    parser.add_argument('-l', '--load', action='store_true', help='Load in_file only, do not execute')
    parser.add_argument('-r', '--run', action='store_true', help='Execute input file (default if in_file given)')
    parser.add_argument('-e', '--cmd', metavar='CMD', help='Execute BASIC command line')
    parser.add_argument('-q', '--quit', action='store_true', help='Quit interpreter when execution stops')
    parser.add_argument('-d', '--double', action='store_true', help='Allow double-precision math functions')
    parser.add_argument('--peek', nargs='*', metavar=('SEG:ADDR:VAL'), help='Define PEEK preset values')
    parser.add_argument('--lpt1', nargs=1, metavar=('TYPE:VAL'), help='Set LPT1: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt2', nargs=1, metavar=('TYPE:VAL'), help='Set LPT2: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--lpt3', nargs=1, metavar=('TYPE:VAL'), help='Set LPT3: to FILE:file_name or PRINTER:printer_name.')
    parser.add_argument('--com1', nargs=1, metavar=('TYPE:VAL'), help='Set COM1: to PORT:device_name or SOCK:host:socket.')
    parser.add_argument('--com2', nargs=1, metavar=('TYPE:VAL'), help='Set COM2: to PORT:device_name or SOCK:host:socket.')
    parser.add_argument('--conv', metavar='MODE', help='Convert file to (A)SCII, (B)ytecode or (P)rotected mode. Implies --unprotect and --list-all.')
    parser.add_argument('--codepage', nargs=1, metavar=('NUMBER'), help='Load specified font codepage. Default is 437 (US).')
    parser.add_argument('--nosound', action='store_true', help='Disable sound output')
    parser.add_argument('--dimensions', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for graphics mode. Default is 640,480. Use 640,400 or multiples for cleaner pixels - but incorrect aspect ratio - on square-pixel LCDs. Graphical terminal only.')
    parser.add_argument('--dimensions-text', nargs=1, metavar=('X, Y'), help='Set pixel dimensions for text mode. Default is 640,400. Graphical terminal only.')
    parser.add_argument('--fullscreen', action='store_true', help='Fullscreen mode. This is unlikely to have either the correct aspect ratio or clean square pixels, but it does take up the whole screen. Graphical terminal only.')
    parser.add_argument('--smooth', action='store_true', help='Use smooth display scaling. Graphical terminal only.')
    parser.add_argument('--noquit', action='store_true', help='Allow BASIC to capture <ALT+F4>. Graphical terminal only.')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG keyword')
    parser.add_argument('--list-all', action='store_true', help='Allow listing and ASCII saving of lines beyond 65530')
    parser.add_argument('--unprotect', action='store_true', help='Allow listing and ASCII saving of protected files')
    parser.add_argument('--caps', action='store_true', help='Start in CAPS LOCK mode.')
    parser.add_argument('--mount', nargs='*', metavar=('D:PATH'), help='Set a drive letter to PATH.')
    return parser.parse_args()


main()

