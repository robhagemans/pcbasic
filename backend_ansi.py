#
# PC-BASIC 3.23 - backend_ansi.py
#
# ANSI backend for Console
#
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

## implements text screen I/O functions on an ANSI/AIX terminal
# using raw escape sequences (as curses module doesn't do UTF8 it seems)

# silent get character with no enter,  using raw terminal
# raw terminal, see http://stackoverflow.com/questions/1052107/reading-a-single-character-wait_char-style-in-python-is-not-working-in-unix
# non-blocking input with select, see http://repolinux.wordpress.com/2012/10/09/non-blocking-read-from-stdin-in-python/ 
# reading escape sequences with os.read, see http://stackoverflow.com/questions/8620878/check-for-extra-characters-in-linux-terminal-buffer

import time
import sys, tty, termios, select
import os
import sys

import ansi, unicodepage
import error
import console

palette = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

term_echo_on = True
term_attr = None
term = sys.stdout

esc_scroll_screen = '\x1b[r'
esc_clear_screen = '\x1b[2J'
esc_clear_line = '\x1b[2K'

def init():
    # we need raw terminal the whole time to keep control of stdin and keep it from waiting for 'enter'
    term_echo(False)
    
def init_screen_mode(mode, new_font_height):
    if mode != 0:
        raise error.RunError(5)
    
def setup_screen(height, width):
    term.write(esc_clear_screen)
    ansi.resize_term(height, width)   
    set_palette()
        
def close():
    term_echo()
    build_line_cursor(True)
    show_cursor(True, False)
    term.write(esc_clear_screen)
    ansi.reset()
    
def init_graphics():
    pass

def clear_rows(bg, start, stop):
    for r in range(start, stop+1):
        ansi.move_cursor(r,1)    
        term.write(esc_clear_line)
    ansi.move_cursor(console.row, console.col)
    term.flush()

def redraw():
   for y in range(console.height):
        console.redraw_row(0, y+1)

def set_palette(new_palette=None):
    global palette
    palette = new_palette if new_palette else [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] 
    redraw()
    
def set_palette_entry(index, colour):
    global palette
    palette[index] = colour
    redraw()
    
def get_palette_entry(index):
    return palette[index]

def set_scroll_area(view_start, height, width):
    pass
    #ansi.set_scroll_region(view_start, height)    
    
def set_cursor_colour(color):
    ansi.set_cursor_colour(apply_palette(color))

def build_line_cursor( is_line):
    #ansi.set_cursor_shape(is_line, True)
    pass
    
def show_cursor(do_show, prev):
    ansi.show_cursor(do_show)

def check_events():
    check_keyboard()
    if console.cursor:
        ansi.move_cursor(console.row,console.col)

def apply_palette(colour):
    return colour&0x8 | palette[colour&0x7]

last_attr = None
def set_attr(attr):
    global last_attr
    if attr == last_attr:
        return
    fore, back = attr & 0xf, (attr>>4) & 0x7
    ansi.set_colour(apply_palette(fore), apply_palette(back))
    ansi.set_cursor_colour(apply_palette(fore))  
    last_attr = attr

def putc_at(row, col, c):
    ansi.move_cursor(row, col)
    term.write(unicodepage.to_utf8(c))
    term.flush()
   
def scroll(from_line):
    ansi.set_scroll_region(console.view_start, console.scroll_height)    
    ansi.scroll_up(1)
    term.write(esc_scroll_screen)
    ansi.move_cursor(console.row, console.col)
    term.flush()
    
def scroll_down(from_line):
    ansi.set_scroll_region(console.view_start, console.scroll_height)    
    ansi.scroll_down(1)
    sys.stdout.write(esc_scroll_screen)
    ansi.move_cursor(console.row, console.col)
    sys.stdout.flush()

def term_echo(on=True):
    global term_attr, term_echo_on
    # sets raw terminal - no echo, by the character rather than by the line
    fd = sys.stdin.fileno()
    if (not on) and term_echo_on:
        term_attr = termios.tcgetattr(fd)
        tty.setraw(sys.stdin.fileno())
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
    if c == '\x03': # ctrl-C
        raise error.Break() 
    # move scancodes (starting \x00) or ascii into keybuf
    # also apply KEY replacements as they work at a low level
    console.insert_key(ansi.translate_char(c))

def copy_page(src, dst):
    pass
    
def idle():
    time.sleep(0.024)
        
def build_shape_cursor(from_line, to_line):
    pass

# no pen, stick

def get_pen(fn):
    # fn 6,7,8,9 refer to character coordinates, 0 not allowed
    return 1 if fn >= 6 else 0 

def get_stick(fn):
    return 0
  
def get_strig(fn):
    return False 
    
