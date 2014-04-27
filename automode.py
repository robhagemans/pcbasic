#
# PC-BASIC 3.23 - automode.py
#
# Automatic line numbering though AUTO
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import program
import tokenise
import console
import run
import util
import state

state.basic_state.auto_mode = False

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
                    run.execution_loop()
            except error.Break as e:
                e.handle_break() 
                run.show_prompt()
            except error.RunError as e:
                e.handle_break()             
                run.show_prompt()
        state.basic_state.auto_mode = False
        program.set_runmode(False)

        
