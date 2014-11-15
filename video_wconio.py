#
# PC-BASIC 3.23 - backend_curses.py
#
# Curses interface (Unix only)
#
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys
import os
import time
import locale
import logging
try:
    import WConio as wconio
except ImportError:
    wconio = None
import msvcrt

import unicodepage
import scancode
import backend

# cursor is visible
cursor_visible = True

# 0 invisible, 1 line, 2 block
cursor_shape = 1

# current cursor position
cursor_row = 1
cursor_col = 1

last_attr = None
attr = 7
 
def prepare(args):
    pass

def init():
    if not wconio:
        logging.warning('WConio module not found. Text interface not supported.')
    wconio.settitle('PC-BASIC 3.23')
    return True
    
def supports_graphics_mode(mode_info):
    return False
    
def init_screen_mode(mode_info=None):
    global height, width
    height = 25
    width = mode_info.width
    wconio.clrscr()
    ### set console width, height
    return True
    
def close():
    wconio.clrscr()
    
def idle():
    time.sleep(0.024)
    
######

def clear_rows(cattr, start, stop):
    for r in range(start, stop+1):
        try:
            wconio.gotoxy(0, r-1)
            wconio.clreol()
        except curses.error:
            pass
                    
def redraw():
    backend.redraw_text_screen()

def colours(at):
    # blink not supported
    return at & 0x7f 

def update_palette(new_palette, new_palette1):
    pass
    
def set_colorburst(on, palette, palette1):
    pass
    
####

def move_cursor(crow, ccol):
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
    pass

def update_cursor_visibility(cursor_on):
    global cursor_visible
    cursor_visible = cursor_on
    wconio.setcursortype(cursor_shape if cursor_on else 0)

def build_cursor(width, height, from_line, to_line):
    if (to_line-from_line) >= 4:
        cursor_shape = 2
    else:
        cursor_shape = 1
    wconio.setcursortype(cursor_shape if cursor_visible else 0)

def check_events():
    if cursor_visible:
        wconio.gotoxy(cursor_col-1, cursor_row-1)
    check_keyboard()
    
def set_attr(cattr):
    global attr, last_attr
    attr = cattr
    if attr == last_attr:
        return
    last_attr = attr
    wconio.textattr(colours(attr))

def putc_at(pagenum, row, col, c, for_keys=False):
    # this doesn't recognise DBCS
    wconio.gotoxy(col-1, row-1)
    # output in cli codepage
    uc = unicodepage.UTF8Converter().to_utf8(c).decode('utf-8')
    wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))    

def putwc_at(pagenum, row, col, c, d, for_keys=False):
    # this does recognise DBCS
    wconio.gotoxy(col-1, row-1)
    # output in cli codepage
    uc = unicodepage.UTF8Converter().to_utf8(c+d).decode('utf-8')
    wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        
def scroll(from_line, scroll_height, attr):
    wconio.gotoxy(0, from_line-1)
    wconio.delline()
    wconio.gotoxy(0, scroll_height-1)
    wconio.insline()
    if cursor_row > 1:
        wconio.gotoxy(cursor_col-1, cursor_row-2)
    
def scroll_down(from_line, scroll_height, attr):
    wconio.gotoxy(0, from_line-1)
    wconio.insline()
    wconio.gotoxy(0, scroll_height-1)
    wconio.delline()
    if cursor_row < height:
        window.move(cursor_col-1, cursor_row)
    
#######

def getc():
    # won't work under WINE
    if not msvcrt.kbhit():
        return ''
    return msvcrt.getch()

def get_scancode(s):
    # windows scancodes should be the same as gw-basic ones
    if len(s) > 1 and s[0] in ('\xe0', '\0'):
        return ord(s[1])
    else:
        raise KeyError    

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
    try:    
        # if it's an ansi sequence/scan code, insert immediately
        backend.key_down(get_scancode(s), '')
    except KeyError:    
        # convert into unicode codepoints
        u = s.decode(sys.stdin.encoding)
        c = ''
        for uc in u:                    
            c += uc.encode('utf-8')
            if c == '\x03':         # ctrl-C
                backend.insert_special_key('break')
            if c == eof:            # ctrl-D (unix) / ctrl-Z (windows)
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
        
########

def set_page(vpage, apage):
    pass

def copy_page(src, dst):
    pass

def load_state():
    # console has already been loaded; just redraw
    redraw()

def set_border(attr):
    pass
        
