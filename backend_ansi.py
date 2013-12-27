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


import console

import sys, tty, termios, select
import os
import ansi, unicodepage
import events
import error

# not an echoing terminal
echo = False

palette = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

term_echo_on=True
term_attr=None


def init():
    # we need raw terminal the whole time to keep control of stdin and keep it from waiting for 'enter'
    term_echo(False)
    console.set_mode(0)
    
    
def init_screen_mode(mode, new_font_height):
    if mode != 0:
        raise error.RunError(5)
    
    
def setup_screen(height, width):
    ansi.resize_term(height, width)   
    set_palette()
    
        
def close():
    term_echo()
    build_line_cursor(True)
    show_cursor(True, False)
    ansi.clear_screen()
    ansi.reset()

    
def init_graphics():
    pass
   

def clear_scroll_area(bg):
    ansi.set_colour(0, apply_palette(bg))
    for r in range(console.view_start, console.scroll_height+1):
        ansi.move_cursor(r,1)    
        ansi.clear_line()
    ansi.move_cursor(console.row,console.col)


def clear_row(this_row, bg):
    ansi.move_cursor(this_row,1)    
    ansi.clear_line()
    ansi.move_cursor(console.row,console.col)

    
def redraw():
   for y in range(console.height):
        console.redraw_row(0, y+1)
    
         

def set_palette(new_palette=None):
    global palette
    if new_palette==None:
        new_palette=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
    palette= new_palette
    redraw()
    
def set_palette_entry(index, colour):
    global palette
    palette[index] = colour
    redraw()

    
def get_palette_entry(index):
    return palette[index]


def set_scroll_area(view_start, height, width):
    ansi.set_scroll_region(view_start, height)    

    
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
       
    events.check_events()
    events.handle_events()


def apply_palette(colour):
    return colour&0x8 | palette[colour&0x7]


def putc_at(row, col, c, attr):
    ansi.move_cursor(row, col)
    fore, back = console.colours(attr)
    ansi.set_colour(apply_palette(fore),apply_palette(back))
    ansi.set_cursor_colour(apply_palette(fore))    
    sys.stdout.write(unicodepage.to_utf8(c))
    sys.stdout.flush()
    
      
   
def scroll(from_line):
    ansi.scroll_up(1)

    
def scroll_down(from_line):
    ansi.scroll_down(1)
    

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

    if d[0] != []:
        c = os.read(fd,5)
    
    # handle key
    if c == '\x03': # ctrl-C
        raise error.Break() 
    
    
    # move scancodes (starting \x00) or ascii into keybuf
    # also apply KEY replacements as they work at a low level
    console.keybuf += events.replace_key(ansi.translate_char(c))


def copy_page(src, dst):
    pass
    
    
def idle():
    pass
    
        
