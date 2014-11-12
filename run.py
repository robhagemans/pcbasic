"""
PC-BASIC 3.23 - run.py
Main loops for pc-basic 

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import error
import util
import tokenise 
import program
import statements 
import console
import state
import backend
import reset
import flow

# suppress one prompt by setting to False (used by EDIT)
state.basic_state.prompt = True
# input mode is AUTO (used by AUTO)
state.basic_state.auto_mode = False
# interpreter is executing a command
state.basic_state.execute_mode = False
# interpreter is waiting for INPUT or LINE INPUT
state.basic_state.input_mode = False


def loop(quit=False):
    """ Read-eval-print loop. """
    while True:
        if state.basic_state.execute_mode:
            try:
                # may raise Break
                backend.check_events()
                handle_basic_events()
                keep_running = statements.parse_statement()
                # may raise Break or Error
                set_execute_mode(keep_running, quit)
            except error.RunError as e:
                handle_error(e, quit) 
            except error.Break as e:
                handle_break(e)
        elif state.basic_state.auto_mode:
            try:
                # auto step, checks events
                auto_step()
            except error.Break:
                show_prompt()
                state.basic_state.auto_mode = False    
        else:    
            try:
                # input loop, checks events
                line = console.wait_screenline(from_start=True, alt_replace=True) 
                if line:
                    execute(line)
            except error.Break:
                continue
            except error.RunError as e:
                handle_error(e, quit) 

def set_execute_mode(on, quit=False):
    """ Switch to or from execute mode and show prompt when needed. """
    if not on:
        if quit:
            check_quit()
        # always show prompt at the end of execution
        show_prompt()
    if on == state.basic_state.execute_mode:
        return
    # move pointer to the start of direct line (for both on and off!)
    flow.set_pointer(False, 0)
    state.basic_state.execute_mode = on        
    backend.update_cursor_visibility()

def execute(line):
    """ Store a program line or schedule a command line for execution. """
    state.basic_state.direct_line = tokenise.tokenise_line(line)    
    c = util.peek(state.basic_state.direct_line)
    if c == '\x00':
        # check for lines starting with numbers (6553 6) and empty lines
        program.check_number_start(state.basic_state.direct_line)
        program.store_line(state.basic_state.direct_line)
        reset.clear()
        # no prompt
    elif c != '':
        # it is a command, go and execute    
        set_execute_mode(True)
                        
def show_prompt():
    """ Show the Ok prompt, unless suppressed. """
    if state.basic_state.prompt:
        console.start_line()
        console.write_line("Ok\xff")
    state.basic_state.prompt = True
                   
def auto_step():
    """ Generate an AUTO line number and wait for input. """
    numstr = str(state.basic_state.auto_linenum)
    console.write(numstr)
    if state.basic_state.auto_linenum in state.basic_state.line_numbers:
        console.write('*')
        line = console.wait_screenline(from_start=True)
        if line[:len(numstr)+1] == numstr+'*':
            line[len(numstr)] = ' '
    else:
        console.write(' ')
        line = console.wait_screenline(from_start=True)
    while len(line) > 0 and line[-1] in util.whitespace:
        line = line[:-1]
    # run or store it; don't clear lines or raise undefined line number
    state.basic_state.direct_line = tokenise.tokenise_line(line)    
    c = util.peek(state.basic_state.direct_line)
    if c == '\x00':
        # check for lines starting with numbers (6553 6) and empty lines
        empty, scanline = program.check_number_start(state.basic_state.direct_line)
        if not empty:
            program.store_line(state.basic_state.direct_line)
            reset.clear()
        state.basic_state.auto_linenum = scanline + state.basic_state.auto_increment
    elif c != '':    
        # it is a command, go and execute    
        set_execute_mode(True)

############################
# event and error handling

def handle_basic_events():
    """ Jump to user-defined event subs if events triggered. """
    if state.basic_state.suspend_all_events or not state.basic_state.run_mode:
        return
    for event in state.basic_state.all_handlers:
        if (event.enabled and event.triggered 
                and not event.stopped and event.gosub != None):
            # release trigger
            event.triggered = False
            # stop this event while handling it 
            event.stopped = True 
            # execute 'ON ... GOSUB' subroutine; 
            # attach handler to allow un-stopping event on RETURN
            flow.jump_gosub(event.gosub, event)
        
def handle_error(s, quit):
    """ Handle a BASIC error through trapping or error message. """
    error.set_err(s)
    # not handled by ON ERROR, stop execution
    console.write_error_message(error.get_message(s.err), program.get_line_number(s.pos))   
    state.basic_state.error_handle_mode = False
    if quit:
        check_quit()
    # prompt is shown here
    set_execute_mode(False)
    state.basic_state.input_mode = False    
    # special case: syntax error
    if s.err == 2:
        # for some reason, err is reset to zero by GW-BASIC in this case.
        state.basic_state.errn = 0
        # line edit gadget appears
        if s.pos != -1:
            try:    
                program.edit(program.get_line_number(s.pos), state.basic_state.bytecode.tell())
                # reinstate prompt suppressed by edit
                state.basic_state.prompt = True
            except error.RunError as e:
                handle_error(e, quit)

def handle_break(e):
    """ Handle a Break event. """
    # print ^C at current position
    if not state.basic_state.input_mode and not e.stop:
        console.write('^C')
    # if we're in a program, save pointer
    if state.basic_state.run_mode:
        console.write_error_message("Break", program.get_line_number(e.pos))
        state.basic_state.stop = state.basic_state.bytecode.tell()
    else:
        console.write_error_message("Break", -1)
    set_execute_mode(False)
    state.basic_state.input_mode = False    

def check_quit():
    """ Check if keyboard buffer is empty; exit the interpreter if so. """
    # only quit if all keys have been handled
    if len(state.console_state.keybuf) == 0:
        raise error.Exit()
        
