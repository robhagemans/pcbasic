#
# PC-BASIC 3.23 - backend_ansi.py
#
# ANSI backend for Console (Unix only)
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

supports_graphics = False
max_palette = 16

term_echo_on = True
term_attr = None
term = sys.stdout

# black, blue, green, cyan, red, magenta, yellow, white
colours = (0, 4, 2, 6, 1, 5, 3, 7)
colournames = ('Black','Dark Blue','Dark Green','Dark Cyan','Dark Red','Dark Magenta','Brown','Light Gray',
'Dark Gray','Blue','Green','Cyan','Red','Magenta','Yellow','White')
palette_changed = True

# ANSI escape sequences
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting

esc_reset = '\x1b[0m\x1bc'
esc_set_scroll_screen = '\x1b[r'
esc_set_scroll_region = '\x1b[%i;%ir'
esc_clear_screen = '\x1b[2J'
esc_clear_line = '\x1b[2K'
esc_scroll_up = '\x1b[%iS'
esc_scroll_down = '\x1b[%iT'
esc_show_cursor = '\x1b[?25h'
esc_hide_cursor = '\x1b[?25l'
esc_resize_term = '\x1b[8;%i;%i;t'
esc_move_cursor = '\x1b[%i;%if' 
esc_save_cursor_pos = '\x1b[s'
esc_restore_cursor_pos = '\x1b[u'
esc_request_size = '\x1b[18;t'
esc_set_cursor_colour = '\x1b]12;%s\x07'
esc_set_cursor_shape = '\x1b[%i q'  #% (2*(is_line+1) - blinks)    # 1 blinking block 2 block 3 blinking line 4 line
esc_set_colour = '\x1b[%im'      
esc_set_title = '\x1b]2;%s\x07'

# escape sequence to scancode dictionary
# for scan codes, see e.g. http://www.antonis.de/qbebooks/gwbasman/appendix%20h.html
esc_to_scan = {
    '\x1b\x4f\x50': '\x00\x3b', # F1
    '\x1b\x4f\x51': '\x00\x3c', # F2
    '\x1b\x4f\x52': '\x00\x3d', # F3
    '\x1b\x4f\x53': '\x00\x3e', # F4
    '\x1b\x5b\x31\x35\x7e':  '\x00\x3f', # F5
    '\x1b\x5b\x31\x37\x7e':  '\x00\x40', # F6
    '\x1b\x5b\x31\x38\x7e':  '\x00\x41', # F7
    '\x1b\x5b\x31\x39\x7e':  '\x00\x42', # F8
    '\x1b\x5b\x32\x30\x7e':  '\x00\x43', # F9
    '\x1b\x5b\x32\x31\x7e':  '\x00\x44', # F10
    '\x1b\x4f\x46': '\x00\x4F', # END
    '\x1b\x4f\x48': '\x00\x47', # HOME
    '\x1b\x5b\x41': '\x00\x48', # arrow up
    '\x1b\x5b\x42': '\x00\x50', # arrow down
    '\x1b\x5b\x43': '\x00\x4d', # arrow right
    '\x1b\x5b\x44': '\x00\x4b', # arrow left
    '\x1b\x5b\x32\x7e': '\x00\x52', # INS
    '\x1b\x5b\x33\x7e': '\x00\x53', # DEL
    '\x1b\x5b\x35\x7e': '\x00\x49', # PG UP
    '\x1b\x5b\x36\x7e': '\x00\x51', # PG DN
    # this is not an esc sequence, but UTF-8 for GBP symbol
    '\xc2\xa3': '\x9c'  # pound sterling symbol
}
 
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
        logging.warning('ANSI terminal not supported.\n')
        return False
    term_echo(False)
    term.write(esc_set_title % 'PC-BASIC 3.23')
    term.flush()
    return True
    
def init_screen_mode():
    term.write(esc_clear_screen)
    term.write(esc_resize_term % (state.console_state.height, state.console_state.width))
    term.flush()
    
def close():
    term_echo()
    build_cursor()
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

def update_palette():
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

def update_pos():
    attr = state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf
    term.write(esc_set_cursor_colour % get_fg_colourname(attr))
    term.flush()
    
def update_cursor_visibility():
    term.write(esc_show_cursor if state.console_state.cursor else esc_hide_cursor)
    term.flush()

def check_events():
    check_keyboard()
    if state.console_state.cursor:
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

def putc_at(row, col, c):
    term.write(esc_move_cursor % (row, col))
    term.write(unicodepage.cp_to_utf8[c])
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
    pass
    
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
    fd = sys.stdin.fileno()
    c = ''
    # check if stdin has characters to read
    d = select.select([sys.stdin], [], [], 0) 
    # longest escape sequence I use is 5 bytes
    if d[0] != []:
        c = os.read(fd,5)
    # handle key
    if c == '':
        pass
    elif c == '\x03': # ctrl-C
        raise error.Break() 
    elif c == '\x00':      # to avoid confusion with scancodes
        console.insert_key('\x00\x00')      
    elif c == '\x7f':      # backspace
        console.insert_key('\b')
    else:
        try:
            console.insert_key(esc_to_scan[c])       
        except KeyError:
            try:
                console.insert_key(unicodepage.utf8_to_cp[c])
            except KeyError:    
                # all other codes are chopped off, 
                # so other escape sequences will register as an escape keypress.
                console.insert_key(c[0])    
        
########

def copy_page(src, dst):
    pass
        
def build_cursor():
    # works on xterm, not on xfce
    # on xfce, gibberish is printed
    #is_line = state.console_state.cursor_to - state.console_state.cursor_from < 4
    #term.write(esc_set_cursor_shape % 2*(is_line+1) - 1)
    pass

def load_state():
    # console has already been loaded; just redraw
    redraw()
        
