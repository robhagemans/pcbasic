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
import logging

import plat
import unicodepage
import backend
import scancode

# cursor is visible
cursor_visible = True

# current row and column for cursor
cursor_row = 1 
cursor_col = 1

# last row and column printed on
last_row = 1
last_col = 1
    

if plat.system == 'Windows':
    import WConio as wconio
    import msvcrt

    # Ctrl+Z to exit
    eof = '\x1A'
    
    def init():
        if not check_tty():
            return False
        # on windows, clear the screen or we get a messy console.
        wconio.clrscr()
        return True

    def close():
        update_position()
            
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
        
    def clear_line():
        wconio.gotoxy(0, wconio.wherey())
        wconio.clreol()
    
    def move_left(num):
        if num < 0:
            return
        x = wconio.wherex() - num
        if x < 0:
            x = 0
        wconio.gotoxy(x, wconio.wherey())
        
    def move_right(num):
        if num < 0:
            return
        x = wconio.wherex() + num
        wconio.gotoxy(x, wconio.wherey())

    class WinTerm(object):
        def write(self, s):
            for c in s:
                wconio.putch(c)
        def flush(self):
            pass

    def putc_at(pagenum, row, col, c, for_keys=False):
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # output in cli codepage
        uc = unicodepage.UTF8Converter().to_utf8(c).decode('utf-8')
        wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        last_col += 1

    def putwc_at(pagenum, row, col, c, d, for_keys=False):
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # Windows CMD doesn't do UTF8, output raw & set codepage with CHCP
        # output in cli codepage
        uc = unicodepage.UTF8Converter().to_utf8(c+d).decode('utf-8')
        wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        last_col += 2

    term = WinTerm()

elif plat.system != 'Android':
    import tty, termios, select
    # ANSI escape codes for output, need arrow movements and clear line and esc_to_scan under Unix.
    import ansi

    # output to stdout
    term = sys.stdout

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
        
    def get_scancode(s):    
        # s should be at most one ansi sequence, if it contains ansi sequences.
        return ansi.esc_to_scan[s]

    def clear_line():
        term.write(ansi.esc_clear_line)
    
    def move_left(num):
        term.write(ansi.esc_move_left*num)

    def move_right(num):
        term.write(ansi.esc_move_right*num)

    def putc_at(pagenum, row, col, c, for_keys=False):
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # this doesn't recognise DBCS
        term.write(unicodepage.UTF8Converter().to_utf8(c))
        term.flush()
        last_col += 1

    def putwc_at(pagenum, row, col, c, d, for_keys=False):
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

    def init():
        if not check_tty():
            return False
        term_echo(False)
        term.flush()
        return True

    def close():
        update_position()
        term_echo()
        term.flush()

def check_tty():
    if not plat.stdin_is_tty:
        logging.warning('Input device is not a terminal. '
                        'Could not initialise cli interface.')
        return False
    return True

def prepare(args):
    pass

def supports_graphics_mode(mode_info):
    return False
    
def init_screen_mode(mode_info):
    return True
    
def idle():
    time.sleep(0.024)
    
def move_cursor(crow, ccol):
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def check_events():
    check_keyboard()
    update_position()

def update_position(row=None, col=None):
    global last_row, last_col
    if row == None:
        row = cursor_row
    if col == None:
        col = cursor_col
    # move cursor if necessary
    if row != last_row:
        term.write('\r\n')
        term.flush()
        last_col = 1
        last_row = row
        # show what's on the line where we are. 
        # note: recursive by one level, last_row now equals row
        # this reconstructs DBCS buffer, no need to do that
        backend.redraw_row(0, cursor_row, wrap=False)
    if col != last_col:
        move_left(last_col-col)
        move_right(col-last_col)
        term.flush()
        last_col = col

def clear_rows(cattr, start, stop):
    if start == cursor_row and stop == cursor_row:
        update_position(None, 1)
        clear_line()
        term.flush()
        update_position()

def scroll(from_line, scroll_height, attr):
    term.write('\r\n')
    term.flush()

def scroll_down(from_line, scroll_height, attr):
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
    # s is either (1) a character (a) (2) a utf-8 character (e.g. sterling)
    # (3) a string of utf-8 characters (when pasting) or 
    # (4) one ansi sequence (Unix) or one scancode (Windows)
    try:    
        # if it's an ansi sequence/scan code, insert immediately
        backend.key_down(get_scancode(s), '')
    except KeyError:    
        # replace utf-8 with codepage
        # convert into unicode codepoints
        u = s.decode(sys.stdin.encoding)
        # then handle these one by one as UTF-8 sequences
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

def update_palette(new_palette, new_palette1):
    pass
    
def set_colorburst(on, palette, palette1):
    pass

def update_cursor_attr(attr):
    pass
    
def update_cursor_visibility(cursor_on):
    pass
            
def set_attr(attr):
    pass

def set_page(vpage, apage):
    pass

def copy_page(src, dst):
    pass
        
def build_cursor(width, height, from_line, to_line):
    pass

def load_state():
    pass
            
def set_border(attr):
    pass
                
