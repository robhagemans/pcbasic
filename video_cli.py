"""
PC-BASIC 3.23 - video_cli.py
Command-line interface 

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import sys
import time
import os
import logging

import plat
import unicodepage
import backend
import scancode

#D!!
import state

# cursor is visible
cursor_visible = True

# current row and column for cursor
cursor_row = 1 
cursor_col = 1

# last row and column printed on
last_row = 1
last_col = 1


def prepare():
    """ Initialise the video_cli module. """
    pass

if plat.system == 'Windows':
    try:
        import WConio as wconio
    except ImportError:
        wconio = None
    import msvcrt

    # Ctrl+Z to exit
    eof = '\x1A'
    
    def init():
        """ Initialise command-line interface. """
        if not check_tty():
            return False
        if not wconio:
            logging.warning('WConio module not found. '
                            'CLI interface not supported.')
            return False
        # on windows, clear the screen or we get a messy console.
        wconio.clrscr()
        return True

    def close():
        """ Close command-line interface. """
        update_position()
            
    def getc():
        """ Read character from keyboard, non-blocking. """
        # won't work under WINE
        if not msvcrt.kbhit():
            return ''
        return msvcrt.getch()
    
    def get_scancode(s):
        """ Convert Windows scancodes to BASIC scancodes. """
        # windows scancodes should be the same as gw-basic ones
        if len(s) > 1 and s[0] in ('\xe0', '\0'):
            return ord(s[1])
        else:
            raise KeyError    
        
    def clear_line():
        """ Clear the current line. """
        wconio.gotoxy(0, wconio.wherey())
        wconio.clreol()
    
    def move_left(num):
        """ Move num positions to the left. """
        if num < 0:
            return
        x = wconio.wherex() - num
        if x < 0:
            x = 0
        wconio.gotoxy(x, wconio.wherey())
        
    def move_right(num):
        """ Move num positions to the right. """
        if num < 0:
            return
        x = wconio.wherex() + num
        wconio.gotoxy(x, wconio.wherey())

    def putc_at(pagenum, row, col, c, for_keys=False):
        """ Put a single-byte character at a given position. """
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # output in cli codepage
        uc = unicodepage.UTF8Converter().to_utf8(c).decode('utf-8')
        wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        last_col += 1

    def putwc_at(pagenum, row, col, c, d, for_keys=False):
        """ Put a double-byte character at a given position. """
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # Windows CMD doesn't do UTF8, output raw & set codepage with CHCP
        # output in cli codepage
        uc = unicodepage.UTF8Converter().to_utf8(c+d).decode('utf-8')
        wconio.putch(uc.encode(sys.stdout.encoding, 'replace'))
        last_col += 2

    class WinTerm(object):
        """ Minimal stream interface for Windows terminal (stdout shim). """
        
        def write(self, s):
            """ Write string to terminal. """
            for c in s:
                wconio.putch(c)

        def flush(self):
            """ No buffer to flush. """
            pass

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

    def init():
        """ Initialise command-line interface. """
        if not check_tty():
            return False
        term_echo(False)
        term.flush()
        return True

    def close():
        """ Close command-line interface. """
        update_position()
        term_echo()
        term.flush()

    def term_echo(on=True):
        """ Set/unset raw terminal attributes. """
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
        """ Read character from keyboard, non-blocking. """
        if select.select([sys.stdin], [], [], 0)[0] == []:
            return ''
        return os.read(sys.stdin.fileno(), 1)        
        
    def get_scancode(s):    
        """ Convert ANSI sequences to BASIC scancodes. """
        # s should be at most one ansi sequence, if it contains ansi sequences.
        return ansi.esc_to_scan[s]

    def clear_line():
        """ Clear the current line. """
        term.write(ansi.esc_clear_line)
    
    def move_left(num):
        """ Move num positions to the left. """
        term.write(ansi.esc_move_left*num)

    def move_right(num):
        """ Move num positions to the right. """
        term.write(ansi.esc_move_right*num)

    def putc_at(pagenum, row, col, c, for_keys=False):
        """ Put a single-byte character at a given position. """
        global last_col
        if for_keys:
            return
        update_position(row, col)
        # this doesn't recognise DBCS
        term.write(unicodepage.UTF8Converter().to_utf8(c))
        term.flush()
        last_col += 1

    def putwc_at(pagenum, row, col, c, d, for_keys=False):
        """ Put a double-byte character at a given position. """
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


def check_events():
    """ Handle screen and interface events. """
    check_keyboard()
    update_position()

def idle():
    """ Video idle process. """
    time.sleep(0.024)

def init_screen_mode(mode_info):
    """ Change screen mode. """
    # we don't support graphics
    return mode_info.is_text_mode
    
def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def clear_rows(cattr, start, stop):
    """ Clear screen rows. """
    if start == cursor_row and stop == cursor_row:
        update_position(None, 1)
        clear_line()
        term.flush()
        update_position()

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    term.write('\r\n')
    term.flush()

###############################################################################
# The following are no-op responses to requests from backend

def set_page(vpage, apage):
    """ Set the visible and active page (not implemented). """
    pass

def copy_page(src, dst):
    """ Copy source to destination page (not implemented). """
    pass

def set_border(attr):
    """ Change the border attribute (no-op). """
    pass

def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height (no-op). """
    pass

def set_colorburst(on, palette, palette1):
    """ Change the NTSC colorburst setting (no-op). """
    pass

def update_palette(new_palette, new_palette1):
    """ Build the game palette (no-op). """
    pass

def update_cursor_attr(attr):
    """ Change attribute of cursor (no-op). """
    pass
    
def update_cursor_visibility(cursor_on):
    """ Change visibility of cursor (no-op). """
    pass

def set_attr(cattr):
    """ Set the current attribute (no-op). """
    pass

def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape (no-op). """
    pass

def load_state():
    """ Restore display state from file (no-op). """
    pass

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    pass
            
###############################################################################
# IMPLEMENTATION

def check_tty():
    """ Check if input stream is a typewriter. """
    if not plat.stdin_is_tty:
        logging.warning('Input device is not a terminal. '
                        'Could not initialise CLI interface.')
        return False
    return True

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
    # s is either (1) a character (a) (2) a utf-8 character (e.g. sterling)
    # (3) a string of utf-8 characters (when pasting) or 
    # (4) one ansi sequence (Unix) or one scancode (Windows)
    try:    
        # if it's an ansi sequence/scan code, insert immediately
        backend.key_down(get_scancode(s), '', check_full=False)
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
                backend.insert_chars('\b', check_full=True)
            elif c == '\0':    
                # scancode; go add next char
                continue
            else:
                try:
                    backend.insert_chars(unicodepage.from_utf8(c))
                except KeyError:    
                    backend.insert_chars(c)    
            c = ''

def update_position(row=None, col=None):
    """ Update screen for new cursor position. """
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
        state.console_state.screen.redraw_row(0, cursor_row, wrap=False)
    if col != last_col:
        move_left(last_col-col)
        move_right(col-last_col)
        term.flush()
        last_col = col


prepare()

