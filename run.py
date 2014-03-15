#
# PC-BASIC 3.23 - run.py
# Main loops for pc-basic 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
from cStringIO import StringIO
#import cProfile

import error
import util
import var
import rnd
import events
import tokenise 
import program
import statements 
import oslayer
import fileio
import automode
import console
import fp
# allow floating-point functions to write messages to the screen (Overflow etc.)
fp.error_console = console


def init_run(arg_run, arg_load, arg_quit, arg_cmd, arg_infile):
    # initialise
    program.clear_program()
    var.clear_variables()
    rnd.clear()
    program.set_runmode(False)
    if arg_run or arg_load:
        fin = sys.stdin
        try:
            if arg_run != '':
                fin = fileio.open_file_or_device(0, arg_infile, mode='L', access='rb', defext='BAS')
            program.load(fin)
        except error.Error as e:
            if not handle_error(e):
                exit()
    if arg_run and arg_cmd == None:
        # if a command is given, the program is only loaded.
        arg_cmd = 'RUN'
    if arg_cmd != None:
        get_command_line(arg_cmd)
        program.set_runmode(False)
        #cProfile.run('run.execution_loop()')
        execution_loop()
        if arg_quit:
            # we were running as a script, exit after completion
            exit()

def main_loop(arg_run, arg_load, arg_quit, arg_cmd, arg_infile)
    init_run(arg_run, arg_load, arg_quit, arg_cmd, arg_infile):
    while True:
        # prompt for commands
        prompt()
        # input loop, checks events
        if automode.auto_mode:
            line = automode.auto_input_loop()
        else:
            line = input_loop()
        if line == '':
            continue    
        try:
            # store the direct line
            get_command_line(line)
        except error.Error as e:
            handle_error(e)
        # check for empty lines or lines that start with a line number & deal with them
        if parse_start_direct(program.direct_line):
            # execution loop, checks events
            # execute program or direct command             
            #cProfile.run('run.execution_loop()')
            execution_loop()

def input_loop():
    try:
        # input loop, checks events
        line = console.read_screenline(from_start=True) 
    except error.Break:
        line = ''
    if line == '':
        program.prompt=False
    # store the direct line
    return line

# execute any commands
def execution_loop():
    console.show_cursor(False)
    while True:
        try:
            console.check_events()
            if not statements.parse_statement():
                break
        except error.Error as e:
            if not handle_error(e):
                break
    console.show_cursor()
                   
# direct mode functions:               
               
def prompt(force=False):
    if program.prompt or force:
        console.start_line()
        console.write("Ok "+util.endl)
    else:
        program.prompt = True
              
def get_command_line(line):
    program.direct_line.truncate(0)
    sline = StringIO(line)
    tokenise.tokenise_stream(sline, program.direct_line, onfile=False)
    program.direct_line.seek(0)
               
def parse_start_direct(linebuf): 
    # ignore anything beyond 255
    pos = linebuf.tell()
    linebuf.truncate(255)              
    # restore position; this should not be necessary, but is.
    linebuf.seek(pos)
    if util.peek(linebuf) == '\x00':
        # line starts with a number, add to program memory, no prompt
        try:
            if program.protected:
                # don't list protected files
                raise error.RunError(5)
            linenum = program.store_line(linebuf, automode.auto_mode)
            automode.auto_last_stored = linenum
            program.prompt = False
        except error.RunError as e:
            handle_error(e)
        linebuf.seek(0)
        return False
    # check for empty line, no prompt
    if util.skip_white(linebuf) in util.end_line:
        linebuf.seek(0)
        program.prompt = False
        return False
    # it is a command, go and execute    
    return True        
   
# error handler                
def handle_error(e):
    program.prompt = True  
    if not program.run_mode or e.erl != -1:
        errline = e.erl
    else:
        errline = program.linenum
    if isinstance(e, error.Break):
        write_error_message(e.msg, errline)
        if program.run_mode:
            program.stop = [program.bytecode.tell(), program.linenum]
            program.unset_runmode()
        return False
    # set ERR and ERL
    error.set_error(e.err, errline)
    # don't jump if we're already busy handling an error
    if error.on_error != None and error.on_error != 0 and not error.error_handle_mode:
        error.error_resume = program.current_statement, program.current_codestream, program.run_mode
        program.jump(error.on_error)
        error.error_handle_mode = True
        program.set_runmode()
        # TODO: are events being trapped during error handling?
        return True
    else:
        # not handled by ON ERROR, stop execution
        write_error_message(e.msg, errline)   
        error.error_handle_mode = False
        program.unset_runmode()
        program.prompt = True
        # for syntax error, line edit gadget appears
        if e.err == 2 and errline != -1:
            prompt()
            program.edit_line(errline)
        # for some reason, err is reset to zero by GW-BASIC in this case.
        if e.err == 2:
            error.errn = 0
        return False    

def write_error_message(msg, linenum):
    console.start_line()
    console.write(msg) 
    if linenum > -1 and linenum < 65535:
        console.write(' in %i' % linenum)
    console.write(' ' + util.endl)          

def exit():
    fileio.close_all()
    sys.exit(0)
    
