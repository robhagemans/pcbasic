"""
PC-BASIC - video_ansi.py
Text interface implementation for Unix

(c) 2013, 2014, 2015 Rob Hagemans
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

# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards,
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi

# fallback to filter interface if not working
fallback = 'video_none'

###############################################################################


def prepare():
    """ Initialise the video_curses module. """
    global caption
    caption = config.get('caption')


###############################################################################

#### shared with video_cli

def init():
    """ Initialise the text interface. """
    global stdin_q
    global logger
    if not check_tty():
        return False
    term_echo(False)
    sys.stdout.flush()
    # start the stdin thread for non-blocking reads
    stdin_q = Queue.Queue()
    t = threading.Thread(target=read_stdin, args=(stdin_q,))
    t.daemon = True
    t.start()

# not shared by video_cli
    set_caption_message('')
    # prevent logger from defacing the screen
    if logging.getLogger().handlers[0].stream.name == sys.stderr.name:
        logger = logging.getLogger()
        logger.disabled = True

    launch_thread()
    return True

#######

def close():
    """ Close the text interface. """
    # drain signal queue (to allow for persistence) and request exit
    if backend.video_queue:
        backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
        backend.video_queue.join()
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()
    term_echo()
    sys.stdout.write(ansi.esc_set_colour % 0)
    sys.stdout.write(ansi.esc_clear_screen)
    sys.stdout.write(ansi.esc_move_cursor % (1, 1))
    show_cursor(True)
    sys.stdout.flush()
    # re-enable logger
    logger.disabled = False


###############################################################################
# implementation

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
        check_events()
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
        elif signal.event_type == backend.VIDEO_SET_MODE:
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
        elif signal.event_type == backend.VIDEO_SCROLL_DOWN:
            scroll_down(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CURSOR_SHAPE:
            build_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CURSOR_ATTR:
            update_cursor_attr(signal.params)
        elif signal.event_type == backend.VIDEO_SHOW_CURSOR:
            show_cursor(signal.params)
        elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
            move_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CAPTION:
            set_caption_message(signal.params)
        # drop other messages
        backend.video_queue.task_done()

def check_events():
    """ Handle screen and interface events. """
    global last_pos
    if cursor_visible and last_pos != (cursor_row, cursor_col):
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        sys.stdout.flush()
        last_pos = (cursor_row, cursor_col)
    check_keyboard()


###############################################################################

# cursor is visible
cursor_visible = True

# 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
cursor_shape = 1

# current cursor position
cursor_row = 1
cursor_col = 1

# last used colour attributes
last_attributes = None

# text and colour buffer
num_pages = 1
vpagenum, apagenum = 0, 0
text = [[[(' ', (7, 0, False, False))]*80 for _ in range(25)]]

last_pos = None


def set_mode(mode_info=None):
    """ Change screen mode. """
    global window, height, width, num_pages, text
    height = mode_info.height
    width = mode_info.width
    num_pages = mode_info.num_pages
    text = [[[(' ', (7, 0, False, False))]*width for _ in range(height)] for _ in range(num_pages)]
    sys.stdout.write(ansi.esc_resize_term % (height, width))
    sys.stdout.write(ansi.esc_clear_screen)
    sys.stdout.flush()
    return True

def set_page(new_vpagenum, new_apagenum):
    """ Set visible and active page. """
    global vpagenum, apagenum
    vpagenum, apagenum = new_vpagenum, new_apagenum
    redraw()

def copy_page(src, dst):
    """ Copy screen pages. """
    text[dst] = [row[:] for row in text[src]]
    if dst == vpagenum:
        redraw()

def clear_rows(back_attr, start, stop):
    """ Clear screen rows. """
    text[apagenum][start-1:stop] = [[(' ', (7, 0, False, False))]*len(text[apagenum][0]) for _ in range(start-1, stop)]
    if vpagenum == apagenum:
        set_attributes(7, back_attr, False, False)
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

def put_glyph(pagenum, row, col, c, fore, back, blink, underline, for_keys):
    """ Put a single-byte character at a given position. """
    global last_pos, last_attributes
    try:
        char = unicodepage.UTF8Converter().to_utf8(c)
    except KeyError:
        char = ' ' * len(c)
    text[pagenum][row-1][col-1] = char, (fore, back, blink, underline)
    if len(c) > 1:
        text[pagenum][row-1][col] = '', (fore, back, blink, underline)
    if vpagenum != pagenum:
        return
    sys.stdout.write(ansi.esc_move_cursor % (row, col))
    if last_attributes != (fore, back, blink, underline):
        last_attributes = fore, back, blink, underline
        set_attributes(fore, back, blink, underline)
    sys.stdout.write(char)
    if len(c) > 1:
        sys.stdout.write(' ')
    sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
    last_pos = (cursor_row, cursor_col)
    sys.stdout.flush()

def scroll(from_line, scroll_height, back_attr):
    """ Scroll the screen up between from_line and scroll_height. """
    global last_pos
    text[apagenum][from_line-1:scroll_height] = text[apagenum][from_line:scroll_height] + [[(' ', 0)]*len(text[apagenum][0])]
    if apagenum != vpagenum:
        return
    sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
    sys.stdout.write(ansi.esc_scroll_up % 1)
    sys.stdout.write(ansi.esc_set_scroll_screen)
    if cursor_row > 1:
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        last_pos = (cursor_row, cursor_col)
    clear_rows(back_attr, scroll_height, scroll_height)

def scroll_down(from_line, scroll_height, back_attr):
    """ Scroll the screen down between from_line and scroll_height. """
    text[apagenum][from_line-1:scroll_height] = [[(' ', 0)]*len(text[apagenum][0])] + text[apagenum][from_line-1:scroll_height-1]
    if apagenum != vpagenum:
        return
    sys.stdout.write(ansi.esc_set_scroll_region % (from_line, scroll_height))
    sys.stdout.write(ansi.esc_scroll_down % 1)
    sys.stdout.write(ansi.esc_set_scroll_screen)
    if cursor_row > 1:
        sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
        last_pos = (cursor_row, cursor_col)
    clear_rows(back_attr, from_line, from_line)

def set_caption_message(msg):
    """ Add a message to the window caption. """
    if msg:
        sys.stdout.write(ansi.esc_set_title % (caption + ' - ' + msg))
    else:
        sys.stdout.write(ansi.esc_set_title % caption)
    sys.stdout.flush()


###############################################################################

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

def check_tty():
    """ Check if input stream is a typewriter. """
    if not plat.stdin_is_tty:
        logging.warning('Input device is not a terminal. '
                        'Could not initialise ansi interface.')
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
        #check_full=False?
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
                u8 = unicodepage.from_utf8(u8)
            except KeyError:
                pass
            backend.input_queue.put(backend.Event(backend.KEYB_CHAR, u8))


#######

def set_attributes(fore, back, blink, underline):
    """ Set ANSI colours based on split attribute. """
    bright = (fore & 8)
    if bright == 0:
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

def redraw():
    """ Redraw the screen. """
    sys.stdout.write(ansi.esc_clear_screen)
    for row, textrow in enumerate(text[vpagenum]):
        for col, charattr in enumerate(textrow):
            sys.stdout.write(ansi.esc_move_cursor % (row+1, col+1))
            set_attributes(*charattr[1])
            sys.stdout.write(charattr[0])
    sys.stdout.write(ansi.esc_move_cursor % (cursor_row, cursor_col))
    sys.stdout.flush()

prepare()
