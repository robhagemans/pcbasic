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
import plat
import unicodepage
import error
import console
import state

supports_graphics = False
# palette is ignored
max_palette = 64

term = sys.stdout

# unused, but needs to be defined
colorburst = False

# cursor is visible
cursor_visible = True

# ANSI escape codes for output
# WINE handles these, does Windows?
esc_clear_line = '\x1b[2K'
esc_move_right = '\x1b\x5b\x43'
esc_move_left = '\x1b\x5b\x44'

if plat.system == 'Windows':
    import msvcrt

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

    # escape sequence to scancode dictionary
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
        '\x1b\x4f\x48': '', #'\x00\x47', # HOME, ignore
        '\x1b\x5b\x41': '', #'\x00\x48', # arrow up, ignore
        '\x1b\x5b\x42': '', #'\x00\x50', # arrow down, ignore
        esc_move_right: '\x00\x4d', # arrow right
        esc_move_left: '\x00\x4b', # arrow left
        '\x1b\x5b\x32\x7e': '\x00\x52', # INS
        '\x1b\x5b\x33\x7e': '\x00\x53', # DEL
        '\x1b\x5b\x35\x7e': '\x00\x49', # PG UP
        '\x1b\x5b\x36\x7e': '\x00\x51', # PG DN
    }
     
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
    
def init_screen_mode():
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
    if col != last_col:
        term.write(esc_move_left*(last_col-col))
        term.write(esc_move_right*(col-last_col))
        term.flush()
    last_row = row
    last_col = col    

def set_attr(attr):
    pass

last_row = 1
last_col = 1
    
def putc_at(row, col, c):
    global last_col
    if row == 25:
        return
    update_position(row, col)
    # this doesn't recognise DBCS
    term.write(unicodepage.UTF8Converter().to_utf8(c))
    term.flush()
    last_col += 1

def putwc_at(row, col, c, d):
    global last_col
    if row == 25:
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
        
#######


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
        if c == '\x04':         # ctrl-D
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
        
########

def copy_page(src, dst):
    pass
        
def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass
            
