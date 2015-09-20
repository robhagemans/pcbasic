"""
PC-BASIC - video_curses.py
Text interface implementation for Unix

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import sys
import os
import time
import locale
import logging
import threading
import Queue
try:
    import curses
except ImportError:
    curses = None

import config
import unicodepage
import scancode
import backend

# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards,
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi

# fallback to ANSI interface if not working
fallback = 'video_ansi'

###############################################################################

def prepare():
    """ Initialise the video_curses module. """
    global caption
    caption = config.get('caption')

###############################################################################

def init():
    """ Initialise the text interface. """
    global screen, default_colors, can_change_palette, window
    if not curses:
        # fail silently, we're going to try ANSI
        return False
    # find a supported UTF-8 locale, with a preference for C, en-us, default
    languages = (['C', 'en-US', locale.getdefaultlocale()[0]] +
                 [a for a in locale.locale_alias.values()
                    if '.' in a and a.split('.')[1] == 'UTF-8'])
    for lang in languages:
        try:
            locale.setlocale(locale.LC_ALL,(lang, 'utf-8'))
            break
        except locale.Error:
            pass
    if locale.getlocale()[1] != 'UTF-8':
        logging.warning('No supported UTF-8 locale found.')
        return False
    # set the ESC-key delay to 25 ms unless otherwise set
    # set_escdelay seems to be unavailable on python curses.
    if not os.environ.has_key('ESCDELAY'):
        os.environ['ESCDELAY'] = '25'
    screen = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.nonl()
    curses.raw()
    curses.start_color()
    screen.clear()
    window = curses.newwin(25, 80, 0, 0)
    # init_screen_mode()
    can_change_palette = (curses.can_change_color() and curses.COLORS >= 16
                          and curses.COLOR_PAIRS > 128)
    sys.stdout.write(ansi.esc_set_title % caption)
    sys.stdout.flush()
    if can_change_palette:
        default_colors = range(16, 32)
    else:
        # curses colours mapped onto EGA
        default_colors = (
            curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
            curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
            curses.COLOR_YELLOW, curses.COLOR_WHITE,
            curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
            curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
            curses.COLOR_YELLOW, curses.COLOR_WHITE)
    # start video thread
    launch_thread()
    return True

def close():
    """ Close the text interface. """
    # drain signal queue (to allow for persistence) and request exit
    if backend.video_queue:
        backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
        backend.video_queue.join()
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()
    if curses:
        curses.noraw()
        curses.nl()
        curses.nocbreak()
        screen.keypad(False)
        curses.echo()
        curses.endwin()


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
    # if I don't write something here, I get a blank unresponsive screen for some reason.
    sys.stdout.write(' ')
    sys.stdout.flush()
    while drain_video_queue():
        if cursor_visible:
            window.move(cursor_row-1, cursor_col-1)
        window.refresh()
        check_keyboard()
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
            init_screen_mode(signal.params)
        elif signal.event_type == backend.VIDEO_PUT_CHAR:
            putc_at(*signal.params)
        elif signal.event_type == backend.VIDEO_PUT_WCHAR:
            putwc_at(*signal.params)
        elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
            move_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_CLEAR_ROWS:
            clear_rows(*signal.params)
        elif signal.event_type == backend.VIDEO_SCROLL_UP:
            scroll(*signal.params)
        elif signal.event_type == backend.VIDEO_SCROLL_DOWN:
            scroll_down(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_ATTR:
            set_attr(signal.params)
        elif signal.event_type == backend.VIDEO_SET_PALETTE:
            update_palette(*signal.params)
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


###############################################################################

# cursor is visible
cursor_visible = True

# curses screen and window
screen = None
window = None

# 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
cursor_shape = 1

# current cursor position
cursor_row = 1
cursor_col = 1

if curses:
    # curses keycodes
    curses_to_scan = {
        curses.KEY_F1: scancode.F1, curses.KEY_F2: scancode.F2,
        curses.KEY_F3: scancode.F3, curses.KEY_F4: scancode.F4,
        curses.KEY_F5: scancode.F5, curses.KEY_F6: scancode.F6,
        curses.KEY_F7: scancode.F7, curses.KEY_F8: scancode.F8,
        curses.KEY_F9: scancode.F9, curses.KEY_F10: scancode.F10,
        curses.KEY_F11: scancode.F11, curses.KEY_F12: scancode.F12,
        curses.KEY_END: scancode.END, curses.KEY_HOME: scancode.HOME,
        curses.KEY_UP: scancode.UP, curses.KEY_DOWN: scancode.DOWN,
        curses.KEY_RIGHT: scancode.RIGHT, curses.KEY_LEFT: scancode.LEFT,
        curses.KEY_IC: scancode.INSERT, curses.KEY_DC: scancode.DELETE,
        curses.KEY_PPAGE: scancode.PAGEUP, curses.KEY_NPAGE: scancode.PAGEDOWN,
        curses.KEY_BACKSPACE: scancode.BACKSPACE,
        curses.KEY_PRINT: scancode.PRINT, curses.KEY_CANCEL: scancode.ESCAPE,
    }

    last_attr = None
    attr = curses.A_NORMAL


text = [ [(' ', 0)]*80 for _ in range(25)]


def init_screen_mode(mode_info):
    """ Change screen mode. """
    global window, height, width, text
    height = mode_info.height
    width = mode_info.width
    text = [ [(' ', 0)]*width for _ in range(height)]
    if window:
        window.clear()
        window.refresh()
    else:
        window = curses.newwin(height, width, 0, 0)
    window.move(0, 0)
    sys.stdout.write(ansi.esc_resize_term % (height, width))
    sys.stdout.flush()
    #curses.resizeterm(height, width)
    window.resize(height, width)
    window.nodelay(True)
    window.keypad(True)
    window.scrollok(False)
    set_curses_palette()

def clear_rows(cattr, start, stop):
    """ Clear screen rows. """
    text[start-1:stop] = [ [(' ', colours(7))]*len(text[0]) for _ in range(start-1, stop)]
    window.bkgdset(' ', colours(cattr))
    for r in range(start, stop+1):
        try:
            window.move(r-1, 0)
            window.clrtoeol()
        except curses.error:
            pass

def update_palette(new_palette, new_palette1):
    """ Build the game palette. """
    if can_change_palette:
        for i in range(len(new_palette)):
            r, g, b = new_palette[i]
            curses.init_color(default_colors[i], (r*1000)//255, (g*1000)//255, (b*1000)//255)

def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
    """ Change attribute of cursor. """
    # term.write(ansi.esc_set_cursor_colour % ansi.colournames[attr%16])
    pass

def show_cursor(cursor_on):
    """ Change visibility of cursor. """
    global cursor_visible
    cursor_visible = cursor_on
    curses.curs_set(cursor_shape if cursor_on else 0)

def build_cursor(width, height, from_line, to_line):
    """ Set the cursor shape. """
    if (to_line-from_line) >= 4:
        cursor_shape = 2
    else:
        cursor_shape = 1
    curses.curs_set(cursor_shape if cursor_visible else 0)

def set_attr(cattr):
    """ Set the current attribute. """
    global attr, last_attr
    attr = cattr
    if attr == last_attr:
        return
    last_attr = attr
    window.bkgdset(' ', colours(attr))

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position. """
    if c == '\0':
        c = ' '
    char = unicodepage.UTF8Converter().to_utf8(c)
    try:
        window.addstr(row-1, col-1, char, colours(attr))
    except curses.error:
        pass
    text[row-1][col-1] = char, colours(attr)

def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position. """
    try:
        wchar = unicodepage.UTF8Converter().to_utf8(c+d)
    except KeyError:
        wchar = '  '
    try:
        window.addstr(row-1, col-1, wchar, colours(attr))
    except curses.error:
        pass
    text[row-1][col-1] = wchar, colours(attr)
    text[row-1][col] = '', colours(attr)

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    window.scrollok(True)
    window.setscrreg(from_line-1, scroll_height-1)
    try:
        window.scroll(1)
    except curses.error:
        pass
    window.scrollok(False)
    window.setscrreg(1, height-1)
    clear_rows(attr, scroll_height, scroll_height)
    if cursor_row > 1:
        window.move(cursor_row-2, cursor_col-1)

def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height. """
    window.scrollok(True)
    window.setscrreg(from_line-1, scroll_height-1)
    try:
        window.scroll(-1)
    except curses.error:
        pass
    window.scrollok(False)
    window.setscrreg(1, height-1)
    clear_rows(attr, from_line, from_line)
    if cursor_row < height:
        window.move(cursor_row, cursor_col-1)

def set_caption_message(msg):
    """ Add a message to the window caption. """
    if msg:
        sys.stdout.write(ansi.esc_set_title % (caption + ' - ' + msg))
    else:
        sys.stdout.write(ansi.esc_set_title % caption)
    sys.stdout.flush()
    # redraw in case terminal didn't recognise ansi sequence
    redraw()

###############################################################################

def check_keyboard():
    """ Handle keyboard events. """
    s = ''
    i = 0
    while True:
        i = window.getch()
        if i == -1:
            break
        elif i == 0:
            s += '\0\0'
        elif i < 256:
            s += chr(i)
        else:
            if i == curses.KEY_BREAK:
                # this is fickle, on many terminals doesn't work
                backend.input_queue.put(backend.Event(backend.KEYB_BREAK))
            elif i == curses.KEY_RESIZE:
                sys.stdout.write(ansi.esc_resize_term % (height, width))
                sys.stdout.flush()
                window.resize(height, width)
                redraw()
            try:
                # scancode, insert here and now
                # there shouldn't be a mix of special keys and utf8 in one
                # uninterrupted string, since the only reason an uninterrupted
                # string would be longer than 1 char is because it's a single
                # utf-8 sequence or a pasted utf-8 string, neither of which
                # can contain special characters.
                # however, if that does occur, this won't work correctly.
                #check_full=False?
                backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                                    (curses_to_scan[i], '')))
            except KeyError:
                pass
    # replace utf-8 with codepage
    # convert into unicode codepoints
    u = s.decode('utf-8')
    # then handle these one by one as UTF-8 sequences
    c = ''
    for uc in u:
        c += uc.encode('utf-8')
        if c == '\x03':
            # send BREAK for ctrl-C
            backend.input_queue.put(backend.Event(backend.KEYB_BREAK))
        elif c == '\0':
            # scancode; go add next char
            continue
        else:
            try:
                #check_full=False?
                backend.input_queue.put(backend.Event(backend.KEYB_CHAR,
                                                    unicodepage.from_utf8(c)))
            except KeyError:
                #check_full=False?
                backend.input_queue.put(backend.Event(backend.KEYB_CHAR, c))
        c = ''

def set_curses_palette():
    """ Initialise the curses colour palette. """
    global default_colors
    if can_change_palette:
        for back in range(8):
            for fore in range(16):
                curses.init_pair(back*16+fore+1, default_colors[fore], default_colors[back])
    else:
        for back in range(8):
            for fore in range(8):
                if back == 0 and fore == 7:
                    # black on white mandatorily mapped on color 0
                    pass
                elif back == 0:
                    curses.init_pair(back*8+fore+1, default_colors[fore], default_colors[back])
                else:
                    curses.init_pair(back*8+fore, default_colors[fore], default_colors[back])

def colours(at):
    """ Convert BASIC attribute byte to curses colour. """
    back = (at>>4)&0x7
    blink = (at>>7)
    fore = (blink*0x10) + (at&0xf)
    if can_change_palette:
        cursattr = curses.color_pair(1 + (back&7)*16 + (fore&15))
    else:
        if back == 0 and fore&7 == 7:
            cursattr = 0
        elif back == 0:
            cursattr = curses.color_pair(1 + (back&7)*8 + (fore&7))
        else:
            cursattr = curses.color_pair((back&7)*8 + (fore&7))
        if fore&15 > 7:
            cursattr |= curses.A_BOLD
    if blink:
        cursattr |= curses.A_BLINK
    return cursattr

def redraw():
    """ Redraw the screen. """
    window.clear()
    set_attr(7)
    for row, textrow in enumerate(text):
        for col, charattr in enumerate(textrow):
            try:
                window.addstr(row, col, charattr[0], charattr[1])
            except curses.error:
                pass
    window.refresh()

prepare()
