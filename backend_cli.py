#
# PC-BASIC 3.23 - backend_cli.py
#
# CLI interface 
#
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
import time
import os
import plat
import unicodepage
import error
import console
import state

# palette is ignored
max_palette = 64

# output to stdout
term = sys.stdout

# unused, but needs to be defined
colorburst = False

# cursor is visible
cursor_visible = True

# ANSI escape codes for output, need arrow movements and clear line and esc_to_scan under Unix.
# WINE handles these, does Windows?
from ansi import *

if plat.system == 'Windows':
    import msvcrt

    # Ctrl+Z to exit
    eof = '\x1A'
    
    def term_echo(on=True):
        pass
            
    def getc():
        # won't work under WINE
        if not msvcrt.kbhit():
            return ''
        return msvcrt.getch()    
    
    def replace_scancodes(s):
        # windows scancodes should be the same as gw-basic ones
        return s.replace('\xe0', '\0')
        
else:
    import tty, termios, select
    
    # Ctrl+D to exit
    eof = '\x04'

    term_echo_on = True
    term_attr = None

    def term_echo(on=True):
        global term_attr, term_echo_on
        # sets raw terminal - no echo, by the character rather than by the line
        fd = sys.stdin.fileno()
        if (not on) and term_echo_on:
            term_attr = termios.tcgetattr(fd)
            tty.setraw(fd)
        elif not term_echo_on and term_attr != None:
            termios.tcsetattr(fd, termios.TCSADRAIN, term_attr)
        previous = term_echo_on
        term_echo_on = on    
        return previous

    def getc():
        if select.select([sys.stdin], [], [], 0)[0] == []:
            return ''
        return os.read(sys.stdin.fileno(), 1)        
        
    def replace_scancodes(s):    
        # avoid confusion of NUL with scancodes    
        s = s.replace('\0', '\0\0')
        # first replace escape sequences in s with scancodes
        # this plays nice with utf8 as long as the scan codes are all in 7 bit ascii, ie no \00\f0 or above    
        for esc in esc_to_scan:
            s = s.replace(esc, esc_to_scan[esc])
        return s

def prepare(args):
    pass

def init():
    term_echo(False)
    term.flush()
    return True
        
def supports_graphics_mode(mode_info):
    return False
    
def init_screen_mode(mode_info, is_text_mode=False):
    pass
    
def close():
    term_echo()
    term.flush()

def idle():
    time.sleep(0.024)
    
def clear_rows(cattr, start, stop):
    if start == state.console_state.row and stop == state.console_state.row:
        update_position(None, 1)
        term.write(esc_clear_line)
        term.flush()
        update_position()
        
def update_palette():
    pass

def update_cursor_attr(attr):
    pass
    
def update_cursor_visibility(cursor_on):
    pass

def check_events():
    check_keyboard()
    update_position()

def update_position(row=None, col=None):
    global last_row, last_col
    if row == None:
        row = state.console_state.row
    if col == None:
        col = state.console_state.col
    # move cursor if necessary
    if row != last_row:
        term.write('\r\n')
        term.flush()
        last_col = 1
        last_row = row
        # show what's on the line where we are. 
        # note: recursive by one level, last_row now equals row
        console.redraw_row(0, state.console_state.row)
    if col != last_col:
        term.write(esc_move_left*(last_col-col))
        term.write(esc_move_right*(col-last_col))
        term.flush()
        last_col = col
            
def set_attr(attr):
    pass

last_row = 1
last_col = 1
    
def putc_at(row, col, c, for_keys=False):
    global last_col
    if for_keys:
        return
    update_position(row, col)
    # this doesn't recognise DBCS
    term.write(unicodepage.UTF8Converter().to_utf8(c))
    term.flush()
    last_col += 1

def putwc_at(row, col, c, d, for_keys=False):
    global last_col
    if for_keys:
        return
    update_position(row, col)
    # this does recognise DBCS
    try:
        term.write(unicodepage.UTF8Converter().to_utf8(c+d))
    except KeyError:
        term.write('  ')
    term.flush()
    last_col += 2
   
def scroll(from_line):
    term.write('\r\n')
    term.flush()
    
def scroll_down(from_line):
    pass
        
def check_keyboard():
    global pre_buffer
    s = ''
    # drain input buffer of all charaters available
    while True:
        c = getc()
        # break if stdin has no more characters to read
        if c == '':
            break
        s += c    
    if s == '':    
        return
    s = replace_scancodes(s)
    # replace utf-8 with codepage
    # convert into unicode codepoints
    u = s.decode('utf-8')
    # then handle these one by one as UTF-8 sequences
    c = ''
    for uc in u:                    
        c += uc.encode('utf-8')
        if c == '\x03':         # ctrl-C
            raise error.Break() 
        if c == eof:            # ctrl-D (unix) / ctrl-Z (windows)
            raise error.Exit() 
        elif c == '\x7f':       # backspace
            console.insert_key('\b')
        elif c == '\0':    
            # scancode; go add next char
            continue
        else:
            try:
                console.insert_key(unicodepage.from_utf8(c))
            except KeyError:    
                console.insert_key(c)    
        c = ''

def copy_page(src, dst):
    pass
        
def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass
            
