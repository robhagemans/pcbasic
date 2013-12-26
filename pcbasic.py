#!/usr/bin/env python

#
# PC-BASIC 3.23 
#
# GW-BASIC (R) compatible interpreter 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
# (GW-BASIC is a trademark of Microsoft Corporation)



#################################################################

import sys
import argparse

import glob
import fileio
                
import run
import error
import var
import deviceio
import util
import printer
import oslayer
import statements
import nosound
import sound
import graphics
import tokenise
import program
    
#################################################################



def main():

    parser = argparse.ArgumentParser(
        description='PC-BASIC 3.23 interpreter. If no options are present, the interpreter will run in interactive mode.')
    parser.add_argument('infile', metavar='in_file', nargs='?', 
        help='Input program file to run (default), load or convert.')
    parser.add_argument('save', metavar='out_file', nargs='?', 
        help='Output program file. If no convert option is specified, this is ignored.')
    
    parser.add_argument('-d', '--dumb', action='store_true', 
        help='use dumb unicode terminal (no escape codes). This is the standard if redirecting input or output')
    parser.add_argument('-t', '--text', action='store_true', 
        help='use textmode terminal')
    
    parser.add_argument('-ca', '--conv-asc', action='store_true', help='convert to DOS text file (code page 347, CR/LF, EOF \\1A)')
    parser.add_argument('-cb', '--conv-byte', action='store_true', help='convert to bytecode file')
    parser.add_argument('-cp', '--conv-prot', action='store_true', help='convert to protected (encrypted) file')
    parser.add_argument('-l', '--load', action='store_true', help='load in_file only, do not execute')
    parser.add_argument('-r', '--run', action='store_true', help='execute input file (default if in_file given)')
    parser.add_argument('-c', '--cmd', metavar='CMD', help='execute BASIC command line')
    parser.add_argument('-q', '--quit', action='store_true', help='quit interpreter when execution stops')
    parser.add_argument('--debug', action='store_true', help='enable DEBUG keyword')
    parser.add_argument('--nosound', action='store_true', help='disable sound output')

    parser.add_argument('--peek', nargs='*', metavar=('ADDR:VAL'), help='define PEEK values')

    parser.add_argument('-p1', '--lpt1', nargs='*', metavar=('TYPE:VAL'), help='set LPT1: to FILE:file_name or CUPS:printer_name. Default is CUPS:default')
    parser.add_argument('-p2', '--lpt2', nargs='*', metavar=('TYPE:VAL'), help='set LPT2: to FILE:file_name or CUPS:printer_name.')
    parser.add_argument('-p3', '--lpt3', nargs='*', metavar=('TYPE:VAL'), help='set LPT3: to FILE:file_name or CUPS:printer_name.')
    parser.add_argument('-s1', '--com1', nargs='*', metavar=('TYPE:VAL'), help='set COM1: to FILE:file_name or CUPS:printer_name.')
    parser.add_argument('-s2', '--com2', nargs='*', metavar=('TYPE:VAL'), help='set COM2: to FILE:file_name or CUPS:printer_name.')

    args = parser.parse_args()
    

    ########################################
    
    # converter invocations
    if args.conv_asc:
        convert(args.infile, args.save, 'A')
    elif args.conv_byte:
        convert(args.infile, args.save, 'B')
    elif args.conv_prot:
        convert(args.infile, args.save, 'P')
    elif args.run or (not args.load and args.infile != None):
        args.run = True    
    
    ########################################
    
    # DEBUG mode
    tokenise.init_DEBUG(args.debug)
    if args.debug:
        debugstr=' [DEBUG mode]'
    else:
        debugstr=''

    ########################################
    
    # PEEK presets
    if args.peek !=None:
        for a in args.peek:
            [addr,val] = a.split(':')
            expressions.peek_values[int(addr)]=int(val)

    ########################################
    sound.backend = nosound
        
    # choose the screen 
    if args.dumb or not sys.stdout.isatty() or not sys.stdin.isatty():
        #import dumbterm
        #glob.console = dumbterm
        import backend_dumb
        import console
        
        glob.console = console
        console.backend = backend_dumb        
        
    elif args.text:
        import terminal
        import console
        glob.console = console   
        console.backend = terminal
        
    else:   
        import gameterm
        import console
        glob.console = console   
        console.backend = gameterm   
        graphics.backend = gameterm
        if not args.nosound:
            sound.backend = gameterm
    
    # initialise backends
    glob.console.init()    
    if not sound.init_sound():
        # fallback warning here?
        sound.backend = nosound
    
    # choose peripherals    
    deviceio.scrn = glob.console
    deviceio.kybd = glob.console
    deviceio.lpt1 = parse_arg_device(args.lpt1, printer)
    deviceio.lpt2 = parse_arg_device(args.lpt2)
    deviceio.lpt3 = parse_arg_device(args.lpt3)
    deviceio.com1 = parse_arg_device(args.com1)
    deviceio.com2 = parse_arg_device(args.com2)
    deviceio.init_devices()
    
        
    try:
        glob.console.set_attr(7, 0)
        glob.console.clear()
        
        if not args.run and args.cmd == None:
            statements.show_keys()
            glob.console.write("PC-BASIC 3.23"+debugstr+util.endl)
            glob.console.write('(C) Copyright 2013 PC-BASIC authors. Type RUN "INFO" for more.'+util.endl)
            glob.console.write(("%d Bytes free" % var.free_mem) +util.endl)
        
        run.init_run(args.run, args.load, args.quit, args.cmd, args.infile)
        run.main_loop()    
    finally:
        # fix the terminal
        glob.console.close()



def convert(infile, outfile, mode):
    import dumbterm 
    
    error.warnings_on=True
    glob.console=dumbterm
    glob.console.init()

    fin = sys.stdin
    if infile != None:
        fin = oslayer.safe_open(infile, 'rb')
    fout = sys.stdout
    if outfile!=None:
        fout = oslayer.safe_open(outfile, 'wb')
        
    program.load(fin)
    # allow conversion of protected files
    program.protected=False
    program.save(fout,mode)
    
    glob.console.close()
    run.exit()



def parse_arg_device(arg, default=None):
    device = None
    if arg !=None:
        for a in arg:
            [addr,val] = a.split(':')
            if addr.upper()=='CUPS':
                device = printer
                device.set_printer(val)            
            elif addr.upper()=='FILE':
                fileio.open_system_text_file(val, access='wb')
                device = fileio.files[-1]
    else:
        device= default
        
    if device != None:
        device.init()
    
    return device
    
        
    
     
#################################################################
  
main()

