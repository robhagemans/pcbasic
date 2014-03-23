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
import os

import error
import unicodepage
import console


# non-printing characters
control = ('\x07', '\x08', '\x09', '\x0a','\x0b','\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')

# keep track of enter presses, to work well on echoing terminal with human operator
enter_pressed = False

# this is called by set_vpage
screen_changed = False
    
class DumbTerm(object):
    def write(self, s):
        global enter_pressed
        c = ''
        for i in range(len(s)):
            last = c
            c = s[i]
            # ignore CR/LF if enter has been pressed (and echoed!)
            if last == '\x0d':
                if c == '\x0a':
                    if enter_pressed:
                        enter_pressed = False
                    else:
                        sys.stdout.write(last + c)
                    continue
                else:
                    sys.stdout.write(last)        
                    # parse as normal
            if c == '\x0d' and i < len(s)-1:
                # first CR, hold till next char
                continue
            if c in control:    
                sys.stdout.write(c)    
            else:
                sys.stdout.write(unicodepage.to_utf8(c))    
        sys.stdout.flush()
    
class DumberTermRead(object):
    def write(self, s):
        if s not in ('\r', '\n'):
            sys.stdout.write(s)    

class DumberTermWrite(object):
    def write(self, s):
        sys.stdout.write(s)
                    
                    
def set_dumbterm():
    console.echo_read = None
    console.echo_write = DumbTerm()
    
def set_dumberterm():
    console.echo_read = DumberTermRead()
    console.echo_write = DumberTermWrite()

def debug_print(s):
    sys.stderr.write(s)    
    
def idle():
    time.sleep(0.004)
    
def init():
    return True
        
def close():
    pass

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

#################
    
def check_keys():
    global enter_pressed
    fd = sys.stdin.fileno()
    c = ''
    # check if stdin has characters to read
    d = select.select([sys.stdin], [], [], 0) 
    if d[0] != []:
        c = os.read(fd,1)
    if c == '\x0A':
        console.insert_key('\x0D') #\x0A')
        enter_pressed = True
    else:
        console.insert_key(c)

