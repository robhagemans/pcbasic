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

import glob
import program

auto_mode = False
auto_increment = 10
auto_linenum = 10


def auto_input_loop():
    global auto_mode
    
    auto_mode_show_line()
    try:
        # input loop, checks events
        line = glob.scrn.read_screenline(from_start=True) 
    except error.Break:
        program.prompt=True
        auto_mode=False
        return ''
    
    return auto_mode_remove_star(line)
            
            
def auto_mode_show_line():
    global auto_linenum, auto_increment
    
    auto_linenum += auto_increment
    glob.scrn.write(str(auto_linenum))
    if auto_linenum in program.line_numbers:
        glob.scrn.write('*')
    else:
        glob.scrn.write(' ')

                
def auto_mode_remove_star(line):                
    global auto_linenum
    
    if auto_linenum in program.line_numbers:
        num_len=len(str(auto_linenum))
        if line[:num_len] == str(auto_linenum):
            line=list(line)
            line[num_len]=' '
            line=''.join(line)
    return line


            


