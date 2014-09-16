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

import unicodepage
import backend
import plat
import redirect

# replace lf with cr
lf_to_cr = False

##############################################        
        
if plat.system == 'Windows':
    import msvcrt
    kbhit = msvcrt.kbhit
else:
    import select
    def kbhit():
        return select.select([sys.stdin], [], [], 0)[0] != []
        
def prepare():
    global lf_to_cr
    # on unix ttys, replace input \n with \r 
    # setting termios won't do the trick as it will not trigger read_line, gets too complicated    
    if plat.system != 'Windows' and sys.stdin.isatty():
        lf_to_cr = True
        
def init():
    # use redirection echos; these are not kept in state 
    redirect.set_output(sys.stdout, utf8=True)
    return True    

def check_keys():
    # avoid blocking on ttys if there's no input 
    if sys.stdin.isatty() and not kbhit():
        return
    s = sys.stdin.readline().decode('utf-8')
    if s == '':
        backend.input_closed = True
    for u in s:
        c = u.encode('utf-8')
        # replace LF -> CR if needed
        if c == '\n' and lf_to_cr:
            c = '\r'
        try:
            backend.insert_chars(unicodepage.from_utf8(c))
        except KeyError:        
            backend.insert_chars(c)
        
def idle():
    time.sleep(0.024)
    
def check_events():
    check_keys()

##############################################

def set_page(vpage, apage):
    pass

def putc_at(row, col, c, for_keys=False):
    pass
        
def putwc_at(row, col, c, d, for_keys=False):
    pass
            
def close():
    pass
    
def clear_rows(attr, start, stop):
    pass

def supports_graphics_mode(mode_info):
    return False

def init_screen_mode(mode_info, is_text_mode=False):
    pass

def copy_page(src, dst):
    pass

def scroll(from_line, scroll_height, attr):
    pass
    
def scroll_down(from_line, scroll_height, attr):
    pass

def move_cursor(crow, ccol):
    pass

def update_cursor_attr(attr):
    pass

def update_palette(new_palette, colours, colours1):
    pass
    
def set_colorburst(on, palette, colours, colours1):
    pass
        
def update_cursor_visibility(cursor_on):
    pass

def set_attr(cattr):
    pass
    
def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass

def set_border(attr):
    pass

prepare()

