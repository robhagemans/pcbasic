"""
PC-BASIC 3.23 - video_none.py
Filter interface - implements basic "video" I/O for redirected input streams

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import sys
import time

import unicodepage
import backend
import plat
import redirect

# replace lf with cr
lf_to_cr = False

if plat.system == 'Windows':
    from msvcrt import kbhit
else:
    import select
    
    def kbhit():
        """ Return whether a character is ready to be read from the keyboard. """
        return select.select([sys.stdin], [], [], 0)[0] != []

###############################################################################
        
def prepare():
    """ Initialise video_none module. """
    global lf_to_cr
    # on unix ttys, replace input \n with \r 
    # setting termios won't do the trick as it will not trigger read_line, gets too complicated    
    if plat.system != 'Windows' and plat.stdin_is_tty:
        lf_to_cr = True

###############################################################################
        
def init():
    """ Initialise filter interface. """
    # use redirection echos; these are not kept in state 
    redirect.set_output(sys.stdout, utf8=True)
    return True    

def idle():
    """ Video idle process. """
    time.sleep(0.024)
    
def check_events():
    """ Handle screen and interface events. """
    check_keys()

def check_keys():
    """ Handle keyboard events. """
    # avoid blocking on ttys if there's no input 
    if plat.stdin_is_tty and not kbhit():
        return
    s = sys.stdin.readline().decode('utf-8')
    if s == '':
        backend.close_input()
    for u in s:
        c = u.encode('utf-8')
        # replace LF -> CR if needed
        if c == '\n' and lf_to_cr:
            c = '\r'
        try:
            backend.insert_chars(unicodepage.from_utf8(c))
        except KeyError:        
            backend.insert_chars(c)

def supports_graphics_mode(mode_info):
    """ We do not support graphics modes. """
    return False

def close():
    """ Close the filter interface. """
    pass

###############################################################################
# The following are no-op responses to requests from backend

def load_state():
    """ Restore display state from file. """
    pass

def init_screen_mode(mode_info):
    """ Change screen mode (no-op). """
    return True

def set_page(vpage, apage):
    """ Set the visible and active page (no-op). """
    pass

def copy_page(src, dst):
    """ Copy source to destination page (no-op). """
    pass

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position (done through echo). """
    pass
        
def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position (done through echo). """
    pass
    
def clear_rows(attr, start, stop):
    """ Clear screen rows (no-op). """
    pass

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height (no-op). """
    pass
    
def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height (no-op). """
    pass

def update_palette(new_palette, new_palette1):
    """ Build the game palette (no-op). """
    pass
    
def set_colorburst(on, palette, palette1):
    """ Change the NTSC colorburst setting (no-op). """
    pass

def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape (no-op). """
    pass

def move_cursor(crow, ccol):
    """ Move the cursor to a new position (no-op). """
    pass

def update_cursor_visibility(cursor_on):
    """ Change visibility of cursor (no-op). """
    pass

def update_cursor_attr(attr):
    """ Change attribute of cursor (no-op). """
    pass

def set_attr(cattr):
    """ Set the current attribute (no-op). """
    pass
    
def set_border(attr):
    """ Change the border attribute (no-op). """
    pass

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    pass

prepare()

