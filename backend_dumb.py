#
# PC-BASIC 3.23 - novideo.py
#
# Filter interface 
# implements basic "video" I/O for redirected input streams
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
import time
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
    if not state.loaded or state.console_state.backend_name != __name__:
        # don't append if the saving backend was us: the echos are already there.
        state.console_state.output_echos.append(echo_stdout_utf8)
        # if both stdin and stdout are ttys, avoid doubling the input echo
        state.console_state.input_echos.append(echo_stdout_utf8)
    return True    

def check_keys():
    s = sys.stdin.readline().decode('utf-8')
    if s == '':
        state.console_state.input_closed = True
    for u in s:
        c = u.encode('utf-8')
        try:
            console.insert_key(unicodepage.from_utf8(c))
        except KeyError:        
            console.insert_key(c)
        
# converter with DBCS lead-byte buffer
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

def update_cursor_attr(attr):
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

