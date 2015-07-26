"""
PC-BASIC - video_cli.py
Command-line interface

(c) 2013, 2014, 2015 Rob Hagemans 
This file is released under the GNU GPL version 3.
"""

import sys
import time
import os
import logging
import threading
import Queue

import plat
import unicodepage
import backend
import scancode
# ANSI escape codes for output, need arrow movements and clear line and esc_to_scan under Unix.
import ansi

#D!!
import state

# fallback to filter interface if not working
fallback = 'video_none'

# cursor is visible
cursor_visible = True

# current row and column for cursor
cursor_row = 1
cursor_col = 1

# last row and column printed on
last_row = None
last_col = None

def prepare():
    """ Initialise the video_cli module. """
    pass

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position. """
    global last_col
    if for_keys:
        return
    update_position(row, col)
    # this doesn't recognise DBCS
    sys.stdout.write(unicodepage.UTF8Converter().to_utf8(c))
    sys.stdout.flush()
    last_col += 1

def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position. """
    global last_col
    if for_keys:
        return
    update_position(row, col)
    # this does recognise DBCS
    try:
        sys.stdout.write(unicodepage.UTF8Converter().to_utf8(c+d))
    except KeyError:
        sys.stdout.write('  ')
    sys.stdout.flush()
    last_col += 2


def init():
    """ Initialise command-line interface. """
    global stdin_q
    if not check_tty():
        return False
    term_echo(False)
    sys.stdout.flush()
    # start the stdin thread for non-blocking reads
    stdin_q = Queue.Queue()
    t = threading.Thread(target=read_stdin, args=(stdin_q,))
    t.daemon = True
    t.start()
    return True

def close():
    """ Close command-line interface. """
    update_position()
    term_echo()
    sys.stdout.flush()

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
    if start <= cursor_row and stop >= cursor_row:
        # clear_line before update_position to avoid redrawing old lines on CLS
        clear_line()
        update_position(cursor_row, 1)
        sys.stdout.flush()

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    sys.stdout.write('\r\n')
    sys.stdout.flush()

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

def show_cursor(cursor_on):
    """ Change visibility of cursor (no-op). """
    pass

def set_attr(cattr):
    """ Set the current attribute (no-op). """
    pass

def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape (no-op). """
    pass

def load_state(display_str):
    """ Restore display state from file (no-op). """
    pass

def save_state():
    """ Save display state to file (no-op). """
    return None

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    pass

###############################################################################
# IMPLEMENTATION

if plat.system == 'Windows':
    import ansipipe
    tty = ansipipe
    termios = ansipipe
    # Ctrl+Z to exit
    eof = '\x1A'
elif plat.system != 'Android':
    import tty, termios
    # Ctrl+D to exit
    eof = '\x04'

term_echo_on = True
term_attr = None

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

def read_stdin(queue):
    """ Wait for stdin and put any input on the queue. """
    while True:
        queue.put(sys.stdin.read(1))
        # don't be a hog
        time.sleep(0.0001)

def getc():
    """ Read character from keyboard, non-blocking. """
    try:
        return stdin_q.get_nowait()
    except Queue.Empty:
        return ''

def get_scancode(s):
    """ Convert ANSI sequences to BASIC scancodes. """
    # s should be at most one ansi sequence, if it contains ansi sequences.
    try:
        return ansi.esc_to_scan[s]
    except KeyError:
        return s;

def get_key():
    """ Retrieve one scancode, or one UTF-8 sequence from keyboard. """
    s = getc()
    esc = False
    more = 0
    if s == '':
        return None, None
    if s == '\x1b':
        # ansi sequence, +4 bytes max
        esc = True
        more = 4
    elif ord(s) >= 0b11110000:
        # utf-8, +3 bytes
        more = 3
    elif ord(s) >= 0b11100000:
        # utf-8, +2 bytes
        more = 2
    elif ord(s) >= 0b11000000:
        # utf-8, +1 bytes
        more = 1
    cutoff = 0
    while (more > 0) and (cutoff < 100):
        # give time for the queue to fill up
        time.sleep(0.0005)
        c = getc()
        cutoff += 1
        if c == '':
            continue
        more -= 1
        s += c
        if esc:
            code = get_scancode(s)
            if code != s:
                return None, code
    # convert into utf-8 if necessary
    if sys.stdin.encoding and sys.stdin.encoding != 'utf-8':
        return s.decode(sys.stdin.encoding).encode('utf-8'), None
    else:
        return s, None

def clear_line():
    """ Clear the current line. """
    sys.stdout.write(ansi.esc_clear_line)

def move_left(num):
    """ Move num positions to the left. """
    sys.stdout.write(ansi.esc_move_left*num)

def move_right(num):
    """ Move num positions to the right. """
    sys.stdout.write(ansi.esc_move_right*num)

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
    # s is one utf-8 sequence or one scancode
    # or a failed attempt at one of the above
    u8, sc = get_key()
    if sc:
        # if it's an ansi sequence/scan code, insert immediately
        backend.key_down(sc, '', check_full=False)
    elif u8:
        if u8 == '\x03':         # ctrl-C
            backend.insert_special_key('break')
        if u8 == eof:            # ctrl-D (unix) / ctrl-Z (windows)
            backend.insert_special_key('quit')
        elif u8 == '\x7f':       # backspace
            backend.insert_chars('\b', check_full=True)
        else:
            try:
                backend.insert_chars(unicodepage.from_utf8(u8))
            except KeyError:
                backend.insert_chars(u8)

def update_position(row=None, col=None):
    """ Update screen for new cursor position. """
    global last_row, last_col
    # this happens on resume
    if last_row == None:
        last_row = cursor_row
        state.console_state.screen.redraw_row(0, cursor_row, wrap=False)
    if last_col == None:
        last_col = cursor_col
    # allow updating without moving the cursor
    if row == None:
        row = cursor_row
    if col == None:
        col = cursor_col
    # move cursor if necessary
    if row != last_row:
        sys.stdout.write('\r\n')
        sys.stdout.flush()
        last_col = 1
        last_row = row
        # show what's on the line where we are.
        # note: recursive by one level, last_row now equals row
        # this reconstructs DBCS buffer, no need to do that
        state.console_state.screen.redraw_row(0, cursor_row, wrap=False)
    if col != last_col:
        move_left(last_col-col)
        move_right(col-last_col)
        sys.stdout.flush()
        last_col = col

prepare()
