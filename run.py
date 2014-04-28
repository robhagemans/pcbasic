#
# PC-BASIC 3.23 - run.py
# Main loops for pc-basic 
# 
# (c) 2013, 3014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import util
import tokenise 
import program
import statements 
import console
import state

# suppress one prompt by setting to False (used by EDIT)
state.basic_state.prompt = True
# AUTO mode    
state.basic_state.auto_mode = False

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
        state.basic_state.direct_line = tokenise.tokenise_line(line)    
        c = util.peek(state.basic_state.direct_line)
        if c == '\x00':
            # check for lines starting with numbers (6553 6) and empty lines
            program.check_number_start(state.basic_state.direct_line)
            program.store_line(state.basic_state.direct_line)
            # no prompt
            return
        elif c == '':
            return    
        else:    
            # it is a command, go and execute    
            execution_loop()
    except error.Break as e:
        handle_break(e) 
    except error.RunError as e:
        handle_error_break(e) 
    # prompt
    show_prompt()

def show_prompt():
    if state.basic_state.prompt:
        console.start_line()
        console.write_line("Ok\xff")
    state.basic_state.prompt = True
                   
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
        except error.RunError as e:
            if not handle_error_continue(e):
                console.show_cursor()
                raise e
    console.show_cursor()

def auto_loop(new_linenum, new_increment):
    # don't nest, but reset linenum and increment
    state.basic_state.auto_linenum = new_linenum if new_linenum != None else 10
    state.basic_state.auto_increment = new_increment if new_increment != None else 10    
    if not state.basic_state.auto_mode:
        state.basic_state.auto_mode = True   
        while True:
            numstr = str(state.basic_state.auto_linenum)
            console.write(numstr)
            try:
                if state.basic_state.auto_linenum in state.basic_state.line_numbers:
                    console.write('*')
                    line = console.wait_screenline(from_start=True)
                    if line[:len(numstr)+1] == numstr+'*':
                        line[len(numstr)] = ' '
                else:
                    console.write(' ')
                    line = console.wait_screenline(from_start=True)
            except error.Break:
                # exit auto mode
                break
            while len(line) > 0 and line[-1] in util.whitespace:
                line = line[:-1]
            # run or store it; don't clear lines or raise undefined line number
            try:
                state.basic_state.direct_line = tokenise.tokenise_line(line)    
                c = util.peek(state.basic_state.direct_line)
                if c == '\x00':
                    # check for lines starting with numbers (6553 6) and empty lines
                    empty, scanline = program.check_number_start(state.basic_state.direct_line)
                    if not empty:
                        program.store_line(state.basic_state.direct_line)
                    state.basic_state.auto_linenum = scanline + state.basic_state.auto_increment
                elif c != '':    
                    # it is a command, go and execute    
                    execution_loop()
            except error.Break as e:
                handle_break(e) 
                show_prompt()
            except error.RunError as e:
                handle_error_break(e)             
                show_prompt()
        state.basic_state.auto_mode = False
        program.set_runmode(False)

        
#########################
        
        
def handle_error_continue(s):
    error.set_err(s)
    # don't jump if we're already busy handling an error
    if state.basic_state.on_error != None and state.basic_state.on_error != 0 and not state.basic_state.error_handle_mode:
        state.basic_state.error_resume = state.basic_state.current_statement, state.basic_state.run_mode
        program.jump(state.basic_state.on_error)
        state.basic_state.error_handle_mode = True
        state.basic_state.suspend_all_events = True
        return True
        
def handle_error_break(s):
    error.set_err(s)
    # not handled by ON ERROR, stop execution
    console.write_error_message(error.get_message(s.err), program.get_line_number(s.pos))   
    state.basic_state.error_handle_mode = False
    program.set_runmode(False)
    # special case
    if s.err == 2:
        # for some reason, err is reset to zero by GW-BASIC in this case.
        state.basic_state.errn = 0
        # for syntax error, line edit gadget appears
        if s.pos != -1:
            console.start_line()
            console.write_line("Ok\xff")
            try:    
                program.edit(program.get_line_number(s.pos), state.basic_state.bytecode.tell())
            except RunError as e:
                handle_error_break(e)

def handle_break(s):
    console.write_error_message("Break", program.get_line_number(s.pos))
    if state.basic_state.run_mode:
        state.basic_state.stop = state.basic_state.bytecode.tell()
        program.set_runmode(False)

