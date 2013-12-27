#
# PC-BASIC 3.23 - backend_dumb.py
#
# Dumb terminal backend
# implements text screen I/O functions on a dumb, echoing unicode terminal
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
import error
import unicodepage
import time

# echoing terminal
echo = True


# this is called by set_vpage
screen_changed=False

    
def idle():
    time.sleep(0.024)
    
def init():
    pass
        
def close():
    pass

def check_events():
    check_keys()
    check_row(console.row)

    
def clear_row(the_row, bg):
    pass

def clear_scroll_area(bg):
    pass  
    
def init_screen_mode(mode, new_font_height):
    if mode != 0:
        raise error.RunError(5)    

def setup_screen(to_height, to_width):
    pass

def copy_page(src, dst):
    pass

def scroll(from_line):
    global last_row
    last_row -=1
    
def scroll_down(from_line):
    global last_row
    last_row +=1

def set_cursor_colour(c):
    pass

        
def set_palette(new_palette=[]):
    pass
    
def set_palette_entry(index, colour):
    pass

def get_palette_entry(index):
    return index

def show_cursor(do_show, prev):
    pass    

def set_scroll_area(view_start, scroll_height, width):
    pass

def putc_at(row, col, c, attr):
    global last_row
    
    # don't print bottom line
    if row==25:
        return
        
    check_row(row)    
    sys.stdout.write(unicodepage.to_utf8(c))
    sys.stdout.flush()
    

def build_line_cursor(is_line):
    pass
    
    

#################


import select
import os
import console

last_row=1

def check_row(row):    
    global last_row
    while row > last_row:
        sys.stdout.write('\n')
        last_row += 1#row

def check_keys():
    global last_row
    fd = sys.stdin.fileno()
    c = ''
    # check if stdin has characters to read
    d = select.select([sys.stdin], [], [], 0) 
    if d[0] != []:
        c = os.read(fd,1)
    
    if c=='\x0A':
        console.keybuf += '\x0D\x0A'
        last_row+=1
    else:
        console.keybuf += c

    
    
    
