#
# PC-BASIC 3.23 - backend_dumb.py
#
# Dumb terminal backend (Unix only)
# implements text screen I/O functions on a dumb, echoing unicode terminal
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
import time
import select
import os
import logging

import error
import unicodepage
import console
import plat
from state import console_state

# these values are not shown as special graphic chars but as their normal effect
control = (
    '\x07', # BEL
    #'\x08',# BACKSPACE
    '\x09', # TAB 
    '\x0a', # LF
    '\x0b', # HOME
    '\x0c', # clear screen
    '\x0d', # CR
    '\x1c', # RIGHT
    '\x1d', # LEFT
    '\x1e', # UP
    '\x1f', # DOWN
    ) 


##############################################        
        
def prepare(args):
    pass        
        
def init():
    global check_keys
    if plat.system == 'Windows':
        logging.warning('Text terminal not supported on Windows.\n')
        return False
    # close input after redirected input ends
    if sys.stdin.isatty():
        check_keys = check_keys_interactive
    else:
        check_keys = check_keys_dumb
    console_state.output_echos.append(echo_stdout_utf8)
    # if both stdin and stdout are ttys, avoid doubling the input echo
    if not(sys.stdin.isatty() and sys.stdout.isatty()):
        console_state.input_echos.append(echo_stdout_utf8)
    return True    

def check_keys_interactive():
    c = getc_utf8() 
    # terminals send \n instead of \r on enter press
    if c == '\n':
        console.insert_key('\r') 
    else:
        console.insert_key(c)
    return c    

def check_keys_dumb():
    if check_keys_interactive() == '':
        console_state.input_closed = True
    

def getc_utf8():
    c = getc()
    utf8 = c
    # UTF8 read, max 6 chars long
    if c and ord(c) > 0x80:
        mask = 0x40
        for _ in range(5):
            if ord(c)&mask == 0:
                break    
            utf8 += getc()
            mask >>= 1 
    try:
        return unicodepage.utf8_to_cp[utf8]
    except KeyError:        
        return utf8

# non-blocking read of one char        
def getc():
    fd = sys.stdin.fileno()
    # check if stdin has characters to read
    sel = select.select([sys.stdin], [], [], 0) 
    c = os.read(fd,1) if sel[0] != [] else ''
    return c
    
##############################################        


def echo_stdout_utf8(s):
    for c in s:
        if c in control:    
            sys.stdout.write(c)    
        else:
            sys.stdout.write(unicodepage.cp_to_utf8[c]) 
    sys.stdout.flush()        

        
##############################################
        
def close():
    pass
    
def idle():
    time.sleep(0.004)
    
def check_events():
    check_keys()
    
def clear_rows(attr, start, stop):
    pass

def init_screen_mode(mode, new_font_height):
    if mode != 0:
        raise error.RunError(5)    

def setup_screen(to_height, to_width):
    pass

def copy_page(src, dst):
    pass

def scroll(from_line):
    pass
    
def scroll_down(from_line):
    pass

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

def set_attr(cattr):
    pass

def putc_at(row, col, c):
    pass    

def build_default_cursor(mode, is_line):
    pass

def build_shape_cursor(from_line, to_line):
    pass

