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
import console
import run
import util

auto_mode = False

def auto_loop(linenum=None, increment=None):
    global auto_mode
    # don't nest
    if not auto_mode:
        auto_mode = True   
        linenum = linenum if linenum else 10
        increment = increment if increment != None else 10    
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
            stored_line = run.execute(line, ignore_empty_number=True)
            if stored_line != None:
                linenum = stored_line + increment
        auto_mode = False
        program.set_runmode(False)
        
