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

# output buffer
output_buffer = [unichr(0)] * state.console_state.width

last_row = 1

##############################################        
        
def prepare(args):
    pass        
        
def init():
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
        
def flush_output_buffer():
    global output_buffer
    trimmed = u''.join(output_buffer).encode('utf-8').rstrip('\0').replace('\0', ' ')
    if trimmed:
        sys.stdout.write(trimmed + '\n')
    output_buffer = [unichr(0)] * state.console_state.width

def putc_at(row, col, c):
    global last_row
    if row != last_row:
        flush_output_buffer()
    last_row = row
    if row == 25:
        return
    output_buffer[col-1:col] = unicodepage.UTF8Converter().to_utf8(c).decode('utf-8')
    
def putwc_at(row, col, c, d):
    global last_row
    if row != last_row:
        flush_output_buffer()
    last_row = row
    if row == 25:
        return
    try:
        output_buffer[col-1:col+1] = [unicodepage.UTF8Converter().to_utf8(c+d).decode('utf-8'), u'']
    except KeyError:
        output_buffer[col-1:col+1] = [u' ', u' ']
        
def close():
    flush_output_buffer()
    
def idle():
    time.sleep(0.024)
    
def check_events():
    check_keys()

##############################################
    
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
    
def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass

