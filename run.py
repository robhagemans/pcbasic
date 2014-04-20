#
# PC-BASIC 3.23 - run.py
# Main loops for pc-basic 
# 
# (c) 2013, 3014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
    
import error
import util
import tokenise 
import program
import statements 
import fileio
import deviceio
import console

# suppress one prompt by setting to False (used by EDIT)
prompt = True

def loop():
    # main loop
    while True:
        try:
            # input loop, checks events
            line = console.wait_screenline(from_start=True, alt_replace=True) 
        except error.Break:
            continue
        if line:
            execute(line)
                        
def execute(line):
    try:
        program.direct_line = tokenise.tokenise_line(line)    
        c = util.peek(program.direct_line)
        if c == '\x00':
            # check for lines starting with numbers (6553 6) and empty lines
            empty, _ = program.check_number_start(program.direct_line)
            program.store_line(program.direct_line)
            # no prompt
            return
        elif c == '':
            return    
        else:    
            # it is a command, go and execute    
            execution_loop()
    except error.Error as e:
        e.handle_break() 
    # prompt
    show_prompt()

def show_prompt():
    global prompt
    if prompt:
        console.start_line()
        console.write_line("Ok\xff")
    prompt = True
                   
# execute any commands
def execution_loop():
    # always start on the direct line
    program.set_runmode(False, 0)
    console.show_cursor(False)
    while True:
        try:
            console.check_events()
            if not statements.parse_statement():
                break
        except error.Error as e:
            if not e.handle_continue():
                console.show_cursor()
                raise e
    console.show_cursor()
                   
def exit():
    fileio.close_all()
    deviceio.close_devices()
    sys.exit(0)
    
