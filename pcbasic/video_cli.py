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

# fallback to filter interface if not working
fallback = 'video_none'

###############################################################################

def prepare():
    """ Initialise the video_cli module. """
    pass


###############################################################################

def init():
    """ Initialise command-line interface. """
    global stdin_q, ok
    if not check_tty():
        ok = False
        return ok
    term_echo(False)
    sys.stdout.flush()
    # start the stdin thread for non-blocking reads
    stdin_q = Queue.Queue()
    t = threading.Thread(target=read_stdin, args=(stdin_q,))
    t.daemon = True
    t.start()
    ok = True
    # start video thread
    launch_thread()
    return ok

def close():
    """ Close command-line interface. """
    # drain signal queue (to allow for persistence) and request exit
    if backend.video_queue:
        backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
        backend.video_queue.join()
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()
    if ok:
        update_position()
        term_echo()
    sys.stdout.flush()


###############################################################################
# IMPLEMENTATION

thread = None
tick_s = 0.024

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.start()

def consumer_thread():
    """ Video signal queue consumer thread. """
    while drain_video_queue():
        check_keyboard()
        update_position()
        # do not hog cpu
        time.sleep(tick_s)

def drain_video_queue():
    """ Drain signal queue. """
    alive = True
    while alive:
        try:
            signal = backend.video_queue.get(False)
        except Queue.Empty:
            return True
        if signal.event_type == backend.VIDEO_QUIT:
            # close thread after task_done
            alive = False
        elif signal.event_type == backend.VIDEO_MODE:
            set_mode(signal.params)
        elif signal.event_type == backend.VIDEO_SET_PAGE:
            set_page(*signal.params)
        elif signal.event_type == backend.VIDEO_COPY_PAGE:
            copy_page(*signal.params)
        elif signal.event_type == backend.VIDEO_PUT_GLYPH:
            put_glyph(*signal.params)
        elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
            move_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_CLEAR_ROWS:
            clear_rows(*signal.params)
        elif signal.event_type == backend.VIDEO_SCROLL_UP:
            scroll(*signal.params)
        # drop other messages
        backend.video_queue.task_done()


###############################################################################

def put_glyph(pagenum, row, col, c, fore, back, blink, underline, for_keys):
    """ Put a single-byte character at a given position. """
    global last_col
    try:
        char = unicodepage.UTF8Converter().to_utf8(c)
    except KeyError:
        char = ' ' * len(c)
    text[pagenum][row-1][col-1] = char
    if len(c) > 1:
        text[aagenum][row-1][col] = ''
    if vpagenum != pagenum:
        return
    if for_keys:
        return
    update_position(row, col)
    sys.stdout.write(char)
    sys.stdout.flush()
    last_col += len(c)

def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def clear_rows(back_attr, start, stop):
    """ Clear screen rows. """
    text[apagenum][start-1:stop] = [ [' ']*len(text[apagenum][0]) for _ in range(start-1, stop)]
    if start <= cursor_row and stop >= cursor_row and vpagenum == apagenum:
        # clear_line before update_position to avoid redrawing old lines on CLS
        clear_line()
        update_position(cursor_row, 1)
        sys.stdout.flush()

def scroll(from_line, scroll_height, back_attr):
    """ Scroll the screen up between from_line and scroll_height. """
    text[apagenum][from_line-1:scroll_height] = text[apagenum][from_line:scroll_height] + [[' ']*len(text[apagenum][0])]
    if vpagenum != apagenum:
        return
    sys.stdout.write('\r\n')
    sys.stdout.flush()

def set_mode(mode_info):
    """ Initialise video mode """
    global text, num_pages
    num_pages = mode_info.num_pages
    text = [[[' ']*mode_info.width for _ in range(mode_info.height)] for _ in range(num_pages)]

def set_page(new_vpagenum, new_apagenum):
    """ Set visible and active page. """
    global vpagenum, apagenum
    vpagenum, apagenum = new_vpagenum, new_apagenum
    redraw_row(cursor_row)

def copy_page(src, dst):
    """ Copy screen pages. """
    text[dst] = [row[:] for row in text[src]]
    if dst == vpagenum:
        redraw_row(cursor_row)


###############################################################################

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

# cursor is visible
cursor_visible = True

# current row and column for cursor
cursor_row = 1
cursor_col = 1

# last row and column printed on
last_row = None
last_col = None

# initialised correctly
ok = False

# text buffer
num_pages = 1
vpagenum, apagenum = 0, 0
text = [[[' ']*80 for _ in range(25)]]

def term_echo(on=True):
    """ Set/unset raw terminal attributes. """
    global term_attr, term_echo_on
    # sets raw terminal - no echo, by the character rather than by the line
    fd = sys.stdin.fileno()
    if (not on) and term_echo_on:
        term_attr = termios.tcgetattr(fd)
        tty.setraw(fd)
    elif not term_echo_on and term_attr is not None:
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
        # check_full=False?
        backend.input_queue.put(backend.Event(backend.KEYB_DOWN, (sc, '')))
    elif u8:
        if u8 == '\x03':
            # ctrl-C
            backend.input_queue.put(backend.Event(backend.KEYB_BREAK))
        if u8 == eof:
            # ctrl-D (unix) / ctrl-Z (windows)
            backend.input_queue.put(backend.Event(backend.KEYB_QUIT))
        elif u8 == '\x7f':
            # backspace
            backend.input_queue.put(backend.Event(backend.KEYB_CHAR, '\b'))
        else:
            try:
                # check_full=False?
                backend.input_queue.put(backend.Event(backend.KEYB_CHAR,
                                                    unicodepage.from_utf8(u8)))
            except KeyError:
                # check_full=False?
                backend.input_queue.put(backend.Event(backend.KEYB_CHAR, u8))

def redraw_row(row):
    """ Draw the stored text in a row. """
    rowtext = ''.join(text[vpagenum][row-1])
    sys.stdout.write(rowtext)
    move_left(len(rowtext))
    sys.stdout.flush()

def update_position(row=None, col=None):
    """ Update screen for new cursor position. """
    global last_row, last_col
    # this happens on resume
    if last_row is None:
        last_row = cursor_row
        redraw_row(cursor_row)
    if last_col is None:
        last_col = cursor_col
    # allow updating without moving the cursor
    if row is None:
        row = cursor_row
    if col is None:
        col = cursor_col
    # move cursor if necessary
    if row != last_row:
        sys.stdout.write('\r\n')
        sys.stdout.flush()
        last_col = 1
        last_row = row
        # show what's on the line where we are.
        redraw_row(cursor_row)
    if col != last_col:
        move_left(last_col-col)
        move_right(col-last_col)
        sys.stdout.flush()
        last_col = col

prepare()
