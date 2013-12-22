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

    glob.args = parser.parse_args()
    

    ########################################
    
    # converter invocations

    if glob.args.conv_asc:
        convert(glob.args.infile, glob.args.save, 'A')
    elif glob.args.conv_byte:
        convert(glob.args.infile, glob.args.save, 'B')
    elif glob.args.conv_prot:
        convert(glob.args.infile, glob.args.save, 'P')
    elif glob.args.run or (not glob.args.load and glob.args.infile != None):
        glob.args.run = True    
    
    ########################################
    
    # DEBUG mode
    
    glob.debug = glob.args.debug

    # ensure tokenise module is not imported before here, as debug variable influences import
    
    import run
    import error

    import printer
    import oslayer
    import statements
    import nosound
    import fileio


    ########################################
    
    if glob.args.peek !=None:
        for a in glob.args.peek:
            [addr,val] = a.split(':')
            glob.peek_values[int(addr)]=int(val)

    ########################################
    
    
    
    ########################################
    # choose the screen 
    if glob.args.dumb or not sys.stdout.isatty() or not sys.stdin.isatty():
        import dumbterm
        
        glob.scrn = dumbterm
        glob.sound = nosound
        
    elif glob.args.text:
        import terminal
        #import cursterm
        import console
    
        glob.scrn = console   
        glob.scrn.backend = terminal
        #glob.scrn.backend = cursterm
        glob.sound = nosound
        
    else:   
        import gameterm
        import console
    
        glob.scrn = console   
        glob.scrn.backend = gameterm   
        glob.graph = gameterm
        glob.sound = gameterm
    
    if glob.args.nosound:
        glob.sound = nosound
    
    glob.scrn.init()    
        
        
        
    # choose peripherals    
    glob.lpt1 = parse_arg_device(glob.args.lpt1, printer)
    glob.lpt2 = parse_arg_device(glob.args.lpt2)
    glob.lpt3 = parse_arg_device(glob.args.lpt3)
    glob.com1 = parse_arg_device(glob.args.com1)
    glob.com2 = parse_arg_device(glob.args.com2)

    # these are the *output* devices
    glob.devices = { 'SCRN:': glob.scrn, 'LPT1:': glob.lpt1, 
            'LPT2:': glob.lpt2,  'LPT3:': glob.lpt3, 'COM1:': glob.com1, 'COM2:': glob.com2 }    
    # input devices
    glob.input_devices = { 'KYBD:': glob.scrn, 'COM1:': glob.com1, 'COM2:': glob.com2 }
    # random access devices
    glob.random_devices = { 'COM1:': glob.com1, 'COM2:': glob.com2 }
    
    
        
    try:
        glob.scrn.set_attr(7, 0)
        glob.scrn.clear()
        
        if not glob.args.run and glob.args.cmd == None:
            statements.show_keys()
            debugstr=''
            if glob.debug:
                debugstr=' [DEBUG mode]'
                
            glob.scrn.write("PC-BASIC 3.23"+debugstr+glob.endl)
            glob.scrn.write('(C) Copyright 2013 PC-BASIC authors. Type RUN "INFO" for more.'+glob.endl)
            glob.scrn.write(("%d Bytes free" % glob.free_mem) +glob.endl)
        
        run.init_run()
        run.main_loop()    
    finally:
        # fix the terminal
        glob.scrn.close()



def convert(infile, outfile, mode):
    import program
    import dumbterm 
    import error
    import oslayer
    
    error.warnings_on=True
    glob.scrn=dumbterm
    glob.scrn.init()

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
    
    glob.scrn.close()
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

