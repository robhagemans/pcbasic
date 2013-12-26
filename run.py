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
import StringIO

import glob
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

#######################################################


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
                fin = oslayer.safe_open(arg_infile, 'rb')
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
        execution_loop()

        if arg_quit:
            # we were running as a script, exit after completion
            exit()



def main_loop():
    while True:
        # prompt for commands
        prompt()
    
        # input loop, checks events
        if automode.auto_mode:
            line = automode.auto_input_loop()
        else:
            line = input_loop()
        
        if line=='':
            continue    
    
        # store the direct line
        get_command_line(line)
    
        # check for empty lines or lines that start with a line number & deal with them
        if parse_start_direct(program.direct_line):
            # execution loop, checks events
            # execute program or direct command             
            execution_loop()



def input_loop():
    try:
        # input loop, checks events
        line = console.read_screenline(from_start=True) 
    except error.Break:
        line = ''
        
    if line=='':
        program.prompt=False
            
    # store the direct line
    return line



# execute any commands
def execution_loop():
    console.hide_cursor()
    while True:
        try:
            console.check_events()
            events.handle_events()
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
    sline = StringIO.StringIO(line)
    tokenise.tokenise_stream(sline, program.direct_line, onfile=False)
    program.direct_line.seek(0)
    
               
               
               
def parse_start_direct(linebuf):               
    c = util.peek(linebuf) 
    if c=='\x00':
        # line starts with a number, add to program memory, no prompt
        try:
            if program.protected:
                # don't list protected files
                raise error.RunError(5)
    
            linenum = program.store_line(linebuf, automode.auto_mode)
            automode.auto_linenum = linenum
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
    #if linum == None or linum==-1:
    #    linum = e.erl              
    program.prompt=True  
    if not program.runmode() or e.erl != -1:
        errline = e.erl
    else:
        errline = program.linenum
    
    if isinstance(e, error.Break):
        error.write_error_message(e.msg, errline)
        if program.runmode():
            program.stop = [program.bytecode.tell()-1, program.linenum]
            program.unset_runmode()
        return False
                
    # set ERR and ERL
    error.set_error(e.err, errline)
    
    # don't jump if we're already busy handling an error
    if error.on_error != None and error.on_error !=0 and not error.error_handle_mode:
        error.error_resume = program.current_statement, program.current_codestream, program.runmode()
       
        program.jump(error.on_error)
        error.error_handle_mode = True
        program.set_runmode()
        events.enable_events=False
        return True
    else:
        # not handled by ON ERROR, stop execution
        error.write_error_message(e.msg, errline)   
        error.error_handle_mode = False
        program.unset_runmode()
        program.prompt = True
        
        # for syntax error, line edit gadget appears
        if e.err==2 and errline !=-1:
            prompt()
            program.edit_line(errline)
        return False    


def exit():
    fileio.close_all_all_all()
    sys.exit(0)
