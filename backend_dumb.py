#
# PC-BASIC 3.23 - backend_dumb.py
#
# Dumb terminal backend
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
import termios
import os

import error
import unicodepage
import console
import run

# non-printing characters
control = ('\x07', '\x08', '\x09', '\x0a','\x0b','\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')


class DumbTermWrite(object):
    def write(self, s):
        for c in s:
            if c in control:    
                sys.stdout.write(c)    
            else:
                sys.stdout.write(unicodepage.to_utf8(c))    
        sys.stdout.flush()
                    
class DumberTermRead(object):
    def write(self, s):
        for c in s:
            if c == '\r':
                sys.stdout.write('\r\n')
            elif c in control:    
                sys.stdout.write(c)    
            else:
                sys.stdout.write(unicodepage.to_utf8(c))       
            
class DumberTermWrite(object):
    def write(self, s):
        sys.stdout.write(s)
    
def init():
    global check_keys
    if sys.stdin.isatty():
        check_keys = check_keys_interactive
    else:
        check_keys = check_keys_dumb
    # on ttys, use unicode and echo suppression
    if sys.stdout.isatty():
        console.echo_write = DumbTermWrite()
    else:
        console.echo_write = DumberTermWrite()
    # if both are ttys, avoid doubling input echo
    if sys.stdin.isatty() and sys.stdout.isatty():
        console.echo_read = console.NoneTerm()
    else:    
        console.echo_read = DumberTermRead()
    return True    

def check_keys_dumb():
    # read everything up to \n
    all_input = sys.stdin.readline()
    if not all_input:
        # signal to quit when done
        console.input_closed = True
    # ends in \r\n? strip off newline
    if len(all_input) > 1 and all_input[-2] == '\r':
        all_input = all_input[:-1]
    for c in all_input:
        console.insert_key(c)

# interactive input    
def check_keys_interactive():
    global enter_pressed
    fd = sys.stdin.fileno()
    c = ''
    # check if stdin has characters to read
    d = select.select([sys.stdin], [], [], 0) 
    if d[0] != []:
        c = os.read(fd,1)
    # terminals send \n instead of \r on enter press
    if c == '\n':
        console.insert_key('\r') 
    else:
        console.insert_key(c)
        
def close():
    pass
    
def debug_print(s):
    sys.stderr.write(s)    
    
def idle():
    time.sleep(0.004)
    
def check_events():
    check_keys()
    
def clear_rows(bg, start, stop):
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

