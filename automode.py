#
# PC-BASIC 3.23 - automode.py
#
# Automatic line numbering though AUTO
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import program
import console

auto_mode = False
auto_increment = 10
auto_linenum = 0
auto_last_stored = -1

def auto_input_loop():
    global auto_mode, auto_linenum
    auto_mode_show_line()
    try:
        # input loop, checks events
        line = console.read_screenline(from_start=True) 
    except error.Break:
        program.prompt = True
        auto_mode = False
        return ''
    if line == '':
        # linenum remains the same, remove increment
        auto_linenum -= auto_increment
        program.prompt = False
    return auto_mode_remove_star(line)
            
def auto_mode_show_line():
    global auto_linenum
    auto_linenum += auto_increment
    console.write(str(auto_linenum))
    if auto_linenum in program.line_numbers:
        console.write('*')
    else:
        console.write(' ')
                
def auto_mode_remove_star(line):                
    if auto_linenum in program.line_numbers:
        num_len = len(str(auto_linenum))
        if line[:num_len] == str(auto_linenum):
            line = list(line)
            line[num_len] = ' '
            line = ''.join(line)
    return line


            


