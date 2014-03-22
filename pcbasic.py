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
import argparse
                
import run
import error
import var
import deviceio
import fileio
import util
import expressions
import oslayer
import statements
import backend_dumb
import nosound
import graphics
import console
import tokenise
import program

greeting = 'PC-BASIC 3.23%s\r\n(C) Copyright 2013, 2014 PC-BASIC authors. Type RUN "INFO" for more.\r\n%d Bytes free\r\n'

def main():
    args = get_args()
    # DEBUG mode
    tokenise.init_DEBUG(args.debug)
    debugstr = ' [DEBUG mode]' if args.debug else ''
    # PEEK presets
    if args.peek != None:
        for a in args.peek:
            seg, addr, val = a.split(':')
            expressions.peek_values[(int(seg), int(addr))] = int(val)
    # implied RUN invocations
    if args.infile and not args.load and not args.conv:
        args.run = True    
    if args.double:
        expressions.option_double = True    
    # announce ourselves; go!
    try:
        # choose the screen backends and other devices 
        prepare_devices(args)
        # initialise program memory
        program.clear_program()
        if not args.run and not args.cmd and not args.conv:
            console.write(greeting % (debugstr, var.total_mem))
        try:
            if args.run or args.load or args.conv:
                program.load(fileio.open_file_or_device(0, args.infile, mode='L', defext='BAS') if args.infile else sys.stdin)
            if args.conv:
                # allow conversion of protected files
                program.protected = False
                program.save(fileio.open_file_or_device(0, args.outfile, mode='S', defext='') if args.outfile else sys.stdout, args.conv)
                run.exit()
        except error.Error as e:
            # give BASIC error message and exit
            if not run.handle_error(e):
                run.exit()
        if args.run and not args.cmd:
            # if a command is given, the program is only loaded.
            args.cmd = 'RUN'
        run.once(args.cmd, args.quit)
        run.loop()
    finally:
        # fix the terminal on exit or crashes (inportant for ANSI terminals)
        console.close()

def prepare_devices(args):
    console.sound = nosound
    if args.dumb or not sys.stdout.isatty() or not sys.stdin.isatty() or args.conv:
        console.backend = backend_dumb
        console.backend.set_dumberterm()
    elif args.uni:                
        console.backend = backend_dumb
        console.backend.set_dumbterm()
    elif args.text:
        import backend_ansi
        console.backend = backend_ansi
    else:   
        import backend_pygame
        console.backend = backend_pygame   
        graphics.backend = backend_pygame
        if not args.nosound:
            console.sound = backend_pygame
    # initialise backends
    console.keys_visible = (not args.run and args.cmd == None)
    console.init()
    if not console.sound.init_sound():
        # fallback warning here?
        console.sound = nosound
    # choose peripherals    
    deviceio.init_devices(args)
    
def get_args():
    parser = argparse.ArgumentParser(
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    parser.add_argument('infile', metavar='in_file', nargs='?', 
        help='Input program file to run (default), load or convert.')
    parser.add_argument('outfile', metavar='out_file', nargs='?', 
        help='Output program file. If no convert option is specified, this is ignored.')
    parser.add_argument('-b', '--dumb', action='store_true', 
        help='Use dumb text terminal. Echo input. This is the default if redirecting input or output')
    parser.add_argument('-u', '--uni', action='store_true', 
        help='Use unicode text terminal. Do not echo input (the terminal does). Translate graphic characters into unicode.')
    parser.add_argument('-t', '--text', action='store_true', 
        help='Use ANSI textmode terminal')
    parser.add_argument('--conv', metavar='MODE', help='Convert file to (A)SCII, (B)ytecode or (P)rotected mode')
    parser.add_argument('-l', '--load', action='store_true', help='Load in_file only, do not execute')
    parser.add_argument('-r', '--run', action='store_true', help='Execute input file (default if in_file given)')
    parser.add_argument('-c', '--cmd', metavar='CMD', help='Execute BASIC command line')
    parser.add_argument('-q', '--quit', action='store_true', help='Quit interpreter when execution stops')
    parser.add_argument('-d', '--double', action='store_true', help='Allow double-precision math functions')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG keyword')
    parser.add_argument('--nosound', action='store_true', help='Disable sound output')
    parser.add_argument('--peek', nargs='*', metavar=('SEG:ADDR:VAL'), help='Define PEEK preset values')
    parser.add_argument('-p1', '--lpt1', nargs='*', metavar=('TYPE:VAL'), help='Set LPT1: to FILE:file_name or CUPS:printer_name. Default is CUPS:default')
    parser.add_argument('-p2', '--lpt2', nargs='*', metavar=('TYPE:VAL'), help='Set LPT2: to FILE:file_name or CUPS:printer_name.')
    parser.add_argument('-p3', '--lpt3', nargs='*', metavar=('TYPE:VAL'), help='Set LPT3: to FILE:file_name or CUPS:printer_name.')
    parser.add_argument('-s1', '--com1', nargs='*', metavar=('TYPE:VAL'), help='Set COM1: to FILE:file_name or CUPS:printer_name or PORT:device_name.')
    parser.add_argument('-s2', '--com2', nargs='*', metavar=('TYPE:VAL'), help='Set COM2: to FILE:file_name or CUPS:printer_name PORT:device_name.')
    return parser.parse_args()


main()

