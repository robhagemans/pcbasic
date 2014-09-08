#
# PC-BASIC 3.23 - backend_ansi.py
#
# ANSI interface (Unix only)
#
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# implements text screen I/O functions on an ANSI/AIX terminal using escape sequences 

# silent get character with no enter,  using raw terminal
# raw terminal, see http://stackoverflow.com/questions/1052107/reading-a-single-character-wait_char-style-in-python-is-not-working-in-unix
# non-blocking input with select, see http://repolinux.wordpress.com/2012/10/09/non-blocking-read-from-stdin-in-python/ 
# reading escape sequences with os.read, see http://stackoverflow.com/questions/8620878/check-for-extra-characters-in-linux-terminal-buffer

import sys
import time
import os

try:
    # this fails on Windows
    import tty, termios, select
except ImportError:
    tty = None

import unicodepage
import error
import console
import state

# escape sequences
from ansi import *

max_palette = 16

term_echo_on = True
term_attr = None
term = sys.stdout

palette_changed = True

# unused, but needs to be defined
colorburst = False

# cursor is visible
cursor_visible = True

 
def get_size():
    sys.stdout.write(esc_request_size)
    sys.stdout.flush()
    # Read response one char at a time until 't'
    resp = char = ""
    while char != 't':
        char = sys.stdin.read(1)
        resp += char
    return resp[4:-1].split(';')

######

def prepare(args):
    pass

def init():
    if tty == None:
        import logging
        logging.warning('ANSI text interface not supported on Windows.\n')
        return False
    term_echo(False)
    term.write(esc_set_title % 'PC-BASIC 3.23')
    term.flush()
    return True

    
def supports_graphics_mode(mode_info):
    return False
    
def init_screen_mode(mode_info, is_text_mode=False):
    term.write(esc_clear_screen)
    term.write(esc_resize_term % (state.console_state.height, state.console_state.width))
    term.flush()
    
def close():
    term_echo()
    #term.write(esc_set_cursor_shape % 3)
    term.write(esc_show_cursor)
    term.write(esc_clear_screen)
    term.write(esc_reset)
    term.flush()

def idle():
    time.sleep(0.024)
    
######

def clear_rows(cattr, start, stop):
    set_attr(cattr)
    for r in range(start, stop+1):
        term.write(esc_move_cursor % (r, 1))    
        term.write(esc_clear_line)
    term.write(esc_move_cursor % (state.console_state.row, state.console_state.col))
    term.flush()

def redraw():
    console.redraw_text_screen()
     

#####

def update_palette(palette, num_palette):
    global palette_changed
    palette_changed = True
    redraw()     

####

def get_fg_colourname(attr):
    colour = state.console_state.palette[attr & 15] & 15
    return colournames[colour]

def get_colours(attr):
    fore = state.console_state.palette[attr & 15] & 15  
    back = state.console_state.palette[(attr>>4) & 7] & 7 
    if (fore & 8) == 0:
        fore = 30 + colours[fore%8]
    else:
        fore = 90 + colours[fore%8]
    back = 40 + colours[back%8]
    return fore, back

def move_cursor(crow, ccol):
    global row, col
    row, col = crow, ccol

def update_cursor_attr(attr):
    term.write(esc_set_cursor_colour % get_fg_colourname(attr))
    term.flush()
    
def update_cursor_visibility(cursor_on):
    global cursor_visible
    cursor_visible = cursor_on
    term.write(esc_show_cursor if cursor_on else esc_hide_cursor)
    term.flush()

def check_events():
    check_keyboard()
    if cursor_visible:
        term.write(esc_move_cursor % (state.console_state.row,state.console_state.col))
        term.flush()

last_attr = None
def set_attr(attr):
    global last_attr, palette_changed
    if attr == last_attr and not palette_changed:
        return
    palette_changed = False    
    term.write(esc_set_colour % 0) 
    if attr & 0x80:
        # blink
        term.write(esc_set_colour % 5)   
    fore, back = get_colours(attr)    
    term.write(esc_set_colour % fore)       
    term.write(esc_set_colour % back)
    term.flush()  
    last_attr = attr

def putc_at(row, col, c, for_keys=False):
    term.write(esc_move_cursor % (row, col))
    # this doesn't recognise DBCS
    term.write(unicodepage.UTF8Converter().to_utf8(c))
    term.flush()

def putwc_at(row, col, c, d, for_keys=False):
    term.write(esc_move_cursor % (row, col))
    # this does recognise DBCS
    try:
        term.write(unicodepage.UTF8Converter().to_utf8(c+d))
    except KeyError:
        term.write('  ')
    term.flush()
   
def scroll(from_line):
    term.write(esc_set_scroll_region % (from_line, state.console_state.scroll_height))
    term.write(esc_scroll_up % 1)
    term.write(esc_set_scroll_screen)
    if state.console_state.row > 1:
        term.write(esc_move_cursor % (state.console_state.row-1, state.console_state.col))
    term.flush()
    
def scroll_down(from_line):
    term.write(esc_set_scroll_region % (from_line, state.console_state.scroll_height))
    term.write(esc_scroll_down % 1)
    term.write(esc_set_scroll_screen)
    if state.console_state.row < state.console_state.height:
        term.write(esc_move_cursor % (state.console_state.row+1, state.console_state.col))
    term.flush()
    
#######

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

def check_keyboard():
    global pre_buffer
    fd = sys.stdin.fileno()
    s = ''
    # drain input buffer of all charaters available
    while True:
        # break if stdin has no more characters to read
        if select.select([sys.stdin], [], [], 0)[0] == []:
            break
        s += os.read(fd, 1)
    # avoid confusion of NUL with scancodes    
    s.replace('\0', '\0\0')
    # first replace escape sequences in s with scancodes
    # this plays nice with utf8 as long as the scan codes are all in 7 bit ascii, ie no \00\f0 or above    
    for esc in esc_to_scan:
        s = s.replace(esc, esc_to_scan[esc])
    # replace utf-8 with codepage
    # convert into unicode codepoints
    u = s.decode('utf-8')
    # then handle these one by one as UTF-8 sequences
    c = ''
    for uc in u:                    
        c += uc.encode('utf-8')
        if c == '\x03':         # ctrl-C
            raise error.Break() 
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
        
########

def set_page(vpage, apage):
    pass

def copy_page(src, dst):
    pass
        
def build_cursor(width, height, from_line, to_line):
    # works on xterm, not on xfce
    # on xfce, gibberish is printed
    #is_line = to_line - from_line < 4
    #term.write(esc_set_cursor_shape % 2*(is_line+1) - 1)
    pass

def load_state():
    # console has already been loaded; just redraw
    redraw()
        
