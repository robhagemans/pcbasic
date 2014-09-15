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
import time
import locale
import logging
try:
    import curses
except ImportError:
    curses = None
        
import unicodepage
import backend

# for a few ansi sequences not supported by curses
# onlu yse these if you clear the screen afterwards, 
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi

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
        curses.KEY_F1: '\x00\x3b', # F1
        curses.KEY_F2: '\x00\x3c', # F2
        curses.KEY_F3: '\x00\x3d', # F3
        curses.KEY_F4: '\x00\x3e', # F4
        curses.KEY_F5:  '\x00\x3f', # F5
        curses.KEY_F6:  '\x00\x40', # F6
        curses.KEY_F7:  '\x00\x41', # F7
        curses.KEY_F8:  '\x00\x42', # F8
        curses.KEY_F9:  '\x00\x43', # F9
        curses.KEY_F10:  '\x00\x44', # F10
        curses.KEY_END: '\x00\x4F', # END
        curses.KEY_HOME: '\x00\x47', # HOME
        curses.KEY_UP: '\x00\x48', # arrow up
        curses.KEY_DOWN: '\x00\x50', # arrow down
        curses.KEY_RIGHT: '\x00\x4d', # arrow right
        curses.KEY_LEFT: '\x00\x4b', # arrow left
        curses.KEY_IC: '\x00\x52', # INS
        curses.KEY_DC: '\x00\x53', # DEL
        curses.KEY_PPAGE: '\x00\x49', # PG UP
        curses.KEY_NPAGE: '\x00\x51', # PG DN
        curses.KEY_BACKSPACE: '\b'
    }

        
    last_attr = None
    attr = curses.A_NORMAL
 
def prepare(args):
    pass

def init():
    global screen, default_colors, can_change_palette
    if not curses:
        logging.warning('ANSI interface not supported.')
    locale.setlocale(locale.LC_ALL,('C', 'utf-8'))
    screen = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.nonl()
    curses.raw()
    curses.start_color()
    screen.clear()
#    init_screen_mode()
    can_change_palette = (curses.can_change_color() and curses.COLORS >= 16 
                          and curses.COLOR_PAIRS > 128)
    sys.stdout.write(ansi.esc_set_title % 'PC-BASIC 3.23 %d' % can_change_palette)
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
    return True
    
def supports_graphics_mode(mode_info):
    return False
    
def init_screen_mode(mode_info=None, is_text_mode=False):
    global window, height, width
    height = 25
    width = mode_info.width
    if window:
        window.clear()
        window.refresh()
    else:
        window = curses.newwin(height, width, 0, 0)
    window.move(0, 0)
    sys.stdout.write(ansi.esc_resize_term % (height, width))
    #curses.resizeterm(height, width)
    window.resize(height, width)
    window.nodelay(True)
    window.keypad(True)
    window.scrollok(False)
    set_curses_palette()

def close():
    curses.noraw()
    curses.nl()
    curses.nocbreak()
    screen.keypad(False)
    curses.echo()
    curses.endwin()
    
def idle():
    time.sleep(0.024)
    
######

def clear_rows(cattr, start, stop):
    window.bkgdset(' ', colours(cattr))
    for r in range(start, stop+1):
        try:
            window.move(r-1, 0)
            window.clrtoeol()
        except curses.error:
            pass
                    
def redraw():
    backend.redraw_text_screen()

def set_curses_palette():
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

def update_palette(new_palette, colours, colours1):
    if can_change_palette:
        for i in range(len(new_palette)):
            r, g, b = colours[new_palette[i]]
            curses.init_color(default_colors[i], (r*1000)//255, (g*1000)//255, (b*1000)//255)             
    
def set_colorburst(on, palette, colours, colours1):
    pass
    
####

def move_cursor(crow, ccol):
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
#    term.write(esc_set_cursor_colour % get_fg_colourname(attr))
    pass

def update_cursor_visibility(cursor_on):
    global cursor_visible
    cursor_visible = cursor_on
    curses.curs_set(cursor_shape if cursor_on else 0)

def build_cursor(width, height, from_line, to_line):
    if (to_line-from_line) >= 4:
        cursor_shape = 2
    else:
        cursor_shape = 1
    curses.curs_set(cursor_shape if cursor_visible else 0)

def check_events():
    if cursor_visible:
        window.move(cursor_row-1, cursor_col-1)
    window.refresh()
    check_keyboard()
    
def set_attr(cattr):
    global attr, last_attr
    attr = cattr
    if attr == last_attr:
        return
    last_attr = attr
    window.bkgdset(' ', colours(attr))

def putc_at(row, col, c, for_keys=False):
    # this doesn't recognise DBCS
    try:
        window.addstr(row-1, col-1, unicodepage.UTF8Converter().to_utf8(c), colours(attr))
    except curses.error:
        pass

def putwc_at(row, col, c, d, for_keys=False):
    # this does recognise DBCS
    try:
        try:
            window.addstr(row-1, col-1, unicodepage.UTF8Converter().to_utf8(c+d), colours(attr))
        except KeyError:
            window.addstr(row-1, col-1, '  ', attr)
    except curses.error:
        pass
        
def scroll(from_line, scroll_height, attr):
    window.scrollok(True)
    window.setscrreg(from_line-1, scroll_height-1)
    try:
        window.scroll(1)
    except curses.error:
        pass
    window.scrollok(False)
    window.setscrreg(1, height-1)
    if cursor_row > 1:
        window.move(cursor_row-2, cursor_col-1)
    
def scroll_down(from_line, scroll_height, attr):
    window.scrollok(True)
    window.setscrreg(from_line-1, scroll_height-1)
    try:
        window.scroll(-1)
    except curses.error:
        pass
    window.scrollok(False)
    window.setscrreg(1, height-1)
    if cursor_row < height:
        window.move(cursor_row, cursor_col-1)
    
#######

def check_keyboard():
    s = ''
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
                backend.insert_special_key('break')
            elif i == curses.KEY_RESIZE:
                sys.stdout.write(ansi.esc_resize_term % (height, width))
                window.resize(height, width)
                window.clear()
                redraw()
            try:
                s += curses_to_scan[i] 
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
            backend.insert_special_key('break')
        elif c == '\0':    
            # scancode; go add next char
            continue
        else:
            try:
                backend.insert_key(unicodepage.from_utf8(c))
            except KeyError:    
                backend.insert_key(c)    
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
        
