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

import unicodepage
import console
import plat
import state

supports_graphics = False
# palette is ignored
max_palette = 64

# unused, but needs to be defined
colorburst = False

##############################################        
        
def prepare(args):
    pass        
        
def init():
    global check_keys
    if plat.system == 'Windows':
        logging.warning('Command-line interface not supported on Windows.')
        return False
    # close input after redirected input ends
    if sys.stdin.isatty():
        check_keys = check_keys_interactive
    else:
        check_keys = check_keys_dumb
    if not state.loaded or state.console_state.backend_name != __name__:
        # don't append if the saving backend was us: the echos are already there.
        state.console_state.output_echos.append(echo_stdout_utf8)
        # if both stdin and stdout are ttys, avoid doubling the input echo
        if not(sys.stdin.isatty() and sys.stdout.isatty()):
            state.console_state.input_echos.append(echo_stdout_utf8)
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
        state.console_state.input_closed = True

check_keys = check_keys_dumb

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
        return unicodepage.from_utf8(utf8)
    except KeyError:        
        return utf8

# non-blocking read of one char        
def getc():
    fd = sys.stdin.fileno()
    # check if stdin has characters to read
    sel = select.select([sys.stdin], [], [], 0) 
    c = os.read(fd,1) if sel[0] != [] else ''
    return c

# coverter with DBCS lead-byte buffer
utf8conv = unicodepage.UTF8Converter()
    
def echo_stdout_utf8(s):
    sys.stdout.write(utf8conv.to_utf8(s, preserve_control=True)) 
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

def init_screen_mode():
    pass

def copy_page(src, dst):
    pass

def scroll(from_line):
    pass
    
def scroll_down(from_line):
    pass

def update_pos():
    pass
        
def update_palette():
    pass

def update_cursor_visibility(cursor_on):
    pass

def set_attr(cattr):
    pass

def putc_at(row, col, c):
    pass    

def putwc_at(row, col, c, d):
    pass    

def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass

