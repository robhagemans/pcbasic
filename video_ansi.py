"""
PC-BASIC 3.23 - video_curses.py
Text interface implementation for Unix

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import sys
import os
import time
import logging
import threading
import Queue

import plat        
import config
import unicodepage
import scancode
import backend

#D!!
import state

# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards, 
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi

# cursor is visible
cursor_visible = True

# 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
cursor_shape = 1

# current cursor position
cursor_row = 1
cursor_col = 1

def prepare():
    """ Initialise the video_curses module. """
    global caption, wait_on_close
    caption = config.options['caption']
    wait_on_close = config.options['wait']


#### shared with video_cli

def init():
    """ Initialise the text interface. """
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
    sys.stdout.write(ansi.esc_set_title % caption)
    sys.stdout.flush()

# not shared by video_cli
    # prevent logger from defacing the screen
    if logging.getLogger().handlers[0].stream.name == sys.stderr.name:
        logger = logging.getLogger()
        logger.disabled = True
    return True

#######
    
def init_screen_mode(mode_info=None):
    """ Change screen mode. """
    global window, height, width
    # we don't support graphics
    if not mode_info.is_text_mode:
        return False
    height = 25
    width = mode_info.width
    sys.stdout.write(ansi.esc_resize_term % (height, width))
    sys.stdout.write(ansi.esc_clear_screen)
    sys.stdout.flush()
    return True
    
def close():
    """ Close the text interface. """
    if wait_on_close:
        sys.stdout.write(ansi.esc_set_title % (caption + 
                                              ' - press a key to close window'))
        # redraw in case terminal didn't recognise ansi sequence
        redraw()
        while getch() == '':
            sleep(0.01)
    term_echo()
    sys.stdout.write(ansi.esc_set_colour % 0)
    sys.stdout.write(ansi.esc_clear_screen)
    sys.stdout.write(ansi.esc_move_cursor % (1, 1))
    show_cursor(True)
    sys.stdout.flush()
    # re-enable logger
    logger.disabled = False

last_pos = None

def check_events():
    """ Handle screen and interface events. """
    global last_pos
    if cursor_visible and last_pos != (cursor_row, cursor_col):
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        sys.stdout.flush()
        last_pos = (cursor_row, cursor_col)
    check_keyboard()
    
def idle():
    """ Video idle process. """
    time.sleep(0.024)

def load_state(display_str):
    """ Restore display state from file. """
    # console has already been loaded; just redraw
    redraw()

def save_state():
    """ Save display state to file (no-op). """
    return None

def clear_rows(cattr, start, stop):
    """ Clear screen rows. """
    set_colours(cattr)
    for r in range(start, stop+1):
        sys.stdout.write(ansi.esc_move_cursor % (r, 1))
        sys.stdout.write(ansi.esc_clear_line)
    sys.stdout.flush()

        
def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
    """ Change attribute of cursor. """
    # sys.stdout.write(ansi.esc_set_cursor_colour % ansi.colournames[attr%16])
    pass

def show_cursor(cursor_on):
    """ Change visibility of cursor. """
    global cursor_visible, last_pos
    cursor_visible = cursor_on
    if cursor_on:
        sys.stdout.write(ansi.esc_show_cursor)
#        sys.stdout.write(ansi.esc_set_cursor_shape % cursor_shape)
    else:
        # force move when made visible again
        sys.stdout.write(ansi.esc_hide_cursor)
        last_pos = None
    sys.stdout.flush()
    
def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape. """
    if (to_line-from_line) >= 4:
        cursor_shape = 1
    else:
        cursor_shape = 3
    # 1 blinking block 2 block 3 blinking line 4 line
    if cursor_visible:
#        sys.stdout.write(ansi.esc_set_cursor_shape % cursor_shape)
        sys.stdout.flush()
        
last_attr = None
def set_attr(cattr):
    """ Set the current attribute. """
    global attr, last_attr
    attr = cattr
    if attr == last_attr:
        return
    last_attr = attr
    set_colours(attr)
    sys.stdout.flush()

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position. """
    global last_pos
    sys.stdout.write(ansi.esc_move_cursor % (row, col))
    sys.stdout.write(unicodepage.UTF8Converter().to_utf8(c))
    sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
    last_pos = (cursor_row, cursor_col)
    sys.stdout.flush()
    
def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position. """
    global last_pos
    sys.stdout.write(ansi.esc_move_cursor % (row, col))
    try:
        sys.stdout.write(unicodepage.UTF8Converter().to_utf8(c+d))
    except KeyError:
        sys.stdout.write('  ')
    sys.stdout.write(unicodepage.UTF8Converter().to_utf8(c))
    sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
    last_pos = (cursor_row, cursor_col)
    sys.stdout.flush()

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    global last_pos
    sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
    sys.stdout.write(ansi.esc_scroll_up % 1)
    sys.stdout.write(ansi.esc_set_scroll_screen)
    if cursor_row > 1:
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        last_pos = (cursor_row, cursor_col)
    sys.stdout.flush()
        
def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height. """
    sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
    sys.stdout.write(ansi.esc_scroll_down % 1)
    sys.stdout.write(ansi.esc_set_scroll_screen)
    if cursor_row > 1:
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        last_pos = (cursor_row, cursor_col)
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
    """ Change the border attribute (not implemented). """
    pass

def set_colorburst(on, palette, palette1):
    """ Change the NTSC colorburst setting (no-op). """
    pass

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    pass

def update_palette(new_palette, new_palette1):
    """ Build the game palette. """
    pass

###############################################################################
# IMPLEMENTATION

       
###### shared with video_cli:

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


#######
             
def redraw():
    """ Force redrawing of the screen (callback). """
    state.console_state.screen.redraw_text_screen()

def set_colours(at):
    """ Convert BASIC attribute byte to ansi colours. """
    back = (at>>4)&0x7
    blink = (at>>7)
    fore = (at & 15)
    bright = (at & 8)
    if (fore & 8) == 0:
        fore = 30 + ansi.colours[fore%8]
    else:
        fore = 90 + ansi.colours[fore%8]
    back = 40 + ansi.colours[back%8]
    sys.stdout.write(ansi.esc_set_colour % 0)
    sys.stdout.write(ansi.esc_set_colour % back)
    sys.stdout.write(ansi.esc_set_colour % fore)
    if blink:
        sys.stdout.write(ansi.esc_set_colour % 5)
    sys.stdout.flush()
    
prepare()

