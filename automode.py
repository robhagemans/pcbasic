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

auto_mode = False

def auto_loop(new_linenum, new_increment):
    global auto_mode, linenum, increment
    # don't nest, but reset linenum and increment
    linenum = new_linenum if new_linenum != None else 10
    increment = new_increment if new_increment != None else 10    
    if not auto_mode:
        auto_mode = True   
        while True:
            numstr = str(linenum)
            console.write(numstr)
            try:
                if linenum in program.line_numbers:
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
                program.direct_line = tokenise.tokenise_line(line)    
                c = util.peek(program.direct_line)
                if c == '\x00':
                    # check for lines starting with numbers (6553 6) and empty lines
                    empty, scanline = program.check_number_start(program.direct_line)
                    if not empty:
                        program.store_line(program.direct_line)
                    linenum = scanline + increment
                elif c != '':    
                    # it is a command, go and execute    
                    run.execution_loop()
            except error.Break as e:
                e.handle_break() 
                run.show_prompt()
            except error.RunError as e:
                e.handle_break()             
                run.show_prompt()
        auto_mode = False
        program.set_runmode(False)

        
