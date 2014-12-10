"""
PC-BASIC 3.23 - video_wconio.py
Text interface implementation for Windows

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import sys
import os
import time
import locale
import logging
import msvcrt
try:
    import WConio as wconio
except ImportError:
    wconio = None

import config
import unicodepage
import scancode
import backend

#D!!
import state

# cursor is visible
cursor_visible = True

# 0 invisible, 1 line, 2 block
cursor_shape = 1

# current cursor position
cursor_row = 1
cursor_col = 1

last_attr = None
attr = 7
 
def prepare():
    """ Initialise the video_wconio module. """
    global caption
    caption = config.options['caption']

def init():
    """ Initialise the text interface. """
    if not wconio:
        logging.warning('WConio module not found. Text interface not supported.')
    wconio.settitle(caption)
    return True
    
def init_screen_mode(mode_info=None):
    """ Change screen mode. """
    global height, width
    # we don't support graphics
    if not mode_info.is_text_mode:
        return False
    height = 25
    width = mode_info.width
    wconio.clrscr()
    ### set console width, height
    return True
    
def close():
    """ Close the text interface. """
    wconio.clrscr()
    
def idle():
    """ Video idle process. """
    time.sleep(0.024)

def check_events():
    """ Handle screen and interface events. """
    if cursor_visible:
        wconio.gotoxy(cursor_col-1, cursor_row-1)
    check_keyboard()
    
def load_state(display_str):
    """ Restore display state from file. """
    # console has already been loaded; just redraw
    redraw()
    
def save_state():
    """ Save display state to file (no-op). """
    return None

def clear_rows(cattr, start, stop):
    """ Clear screen rows. """
    for r in range(start, stop+1):
        wconio.gotoxy(0, r-1)
        wconio.clreol()
                    
def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_visibility(cursor_on):
    """ Change visibility of cursor. """
    global cursor_visible
    cursor_visible = cursor_on
    wconio.setcursortype(cursor_shape if cursor_on else 0)

def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape. """
    if (to_line-from_line) >= 4:
        cursor_shape = 2
    else:
        cursor_shape = 1
    wconio.setcursortype(cursor_shape if cursor_visible else 0)

def set_attr(cattr):
    """ Set the current attribute. """
    global attr, last_attr
    attr = cattr
    if attr == last_attr:
        return
    last_attr = attr
    wconio.textattr(colours(attr))

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position. """
    wconio.gotoxy(col-1, row-1)
    # output in cli codepage
    uc = unicodepage.UTF8Converter().to_utf8(c).decode('utf-8')
    wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))    

def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position. """
    wconio.gotoxy(col-1, row-1)
    # output in cli codepage
    uc = unicodepage.UTF8Converter().to_utf8(c+d).decode('utf-8')
    wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        
def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    wconio.gotoxy(0, from_line-1)
    wconio.delline()
    wconio.gotoxy(0, scroll_height-1)
    wconio.insline()
    if cursor_row > 1:
        wconio.gotoxy(cursor_col-1, cursor_row-2)
    
def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height. """
    wconio.gotoxy(0, from_line-1)
    wconio.insline()
    wconio.gotoxy(0, scroll_height-1)
    wconio.delline()
    if cursor_row < height:
        wconio.gotoxy(cursor_col-1, cursor_row)

###############################################################################
# The following are no-op responses to requests from backend

def update_palette(new_palette, new_palette1):
    """ Build the game palette (not implemented). """
    pass

def update_cursor_attr(attr):
    """ Change attribute of cursor (not implemented). """
    pass

def set_page(vpage, apage):
    """ Set the visible and active page (not implemented). """
    pass

def copy_page(src, dst):
    """ Copy source to destination page (not implemented). """
    pass

def set_border(attr):
    """ Change the border attribute (not implemented). """
    pass

def set_colorburst(on, palette, palette1):
    """ Change the NTSC colorburst setting (no-op). """
    pass

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    pass

###############################################################################
# IMPLEMENTATION

def redraw():
    """ Force redrawing of the screen (callback). """
    state.console_state.screen.redraw_text_screen()

def colours(at):
    """ Convert BASIC attribute byte to console attribute. """
    # blink not supported
    return at & 0x7f 

def getc():
    """ Read character from keyboard, non-blocking. """
    # won't work under WINE
    if not msvcrt.kbhit():
        return ''
    return msvcrt.getch()

def get_scancode(s):
    """ Convert BASIC scancodes to Windows scancodes. """
    # windows scancodes should be the same as gw-basic ones
    if len(s) > 1 and s[0] in ('\xe0', '\0'):
        return ord(s[1])
    else:
        raise KeyError    

def check_keyboard():
    """ Handle keyboard events. """
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
    try:    
        # if it's an ansi sequence/scan code, insert immediately
        backend.key_down(get_scancode(s), '', check_full=False)
    except KeyError:    
        # convert into unicode codepoints
        u = s.decode(sys.stdin.encoding)
        c = ''
        for uc in u:                    
            c += uc.encode('utf-8')
            if c == '\x03':         # ctrl-C
                backend.insert_special_key('break')
            if c == '\x1A':         # ctrl-Z (windows EOF)
                backend.insert_special_key('quit')
            elif c == '\x7f':       # backspace
                backend.insert_chars('\b')
            elif c == '\0':    
                # scancode; go add next char
                continue
            else:
                try:
                    backend.insert_chars(unicodepage.from_utf8(c))
                except KeyError:    
                    backend.insert_chars(c)    
            c = ''
        

        
prepare()

