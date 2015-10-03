"""
PC-BASIC - video_curses.py
Text interface implementation for Unix

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import sys
import os
import locale
import logging
try:
    import curses
except ImportError:
    curses = None

import config
import unicodepage
import scancode
import backend
import video

# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards,
# so you don't see gibberish if the terminal doesn't support the sequence.
import ansi

###############################################################################

def prepare():
    """ Initialise the video_curses module. """
    global caption
    caption = config.get('caption')
    video.plugin_dict['curses'] = VideoCurses

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


###############################################################################

class VideoCurses(video.VideoPlugin):
    """ Curses-based text interface. """

    def __init__(self):
        """ Initialise the text interface. """
        self.curses_init = False
        if not curses:
            raise video.InitFailed()
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
            raise video.InitFailed()
        # set the ESC-key delay to 25 ms unless otherwise set
        # set_escdelay seems to be unavailable on python curses.
        if not os.environ.has_key('ESCDELAY'):
            os.environ['ESCDELAY'] = '25'
        self.curses_init = True
        self.screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.nonl()
        curses.raw()
        curses.start_color()
        self.screen.clear()
        self.window = curses.newwin(25, 80, 0, 0)
        self.window.nodelay(True)
        self.window.keypad(True)
        self.window.scrollok(False)
        self.can_change_palette = (curses.can_change_color() and curses.COLORS >= 16
                              and curses.COLOR_PAIRS > 128)
        sys.stdout.write(ansi.esc_set_title % caption)
        sys.stdout.flush()
        if self.can_change_palette:
            self.default_colors = range(16, 32)
        else:
            # curses colours mapped onto EGA
            self.default_colors = (
                curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
                curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
                curses.COLOR_YELLOW, curses.COLOR_WHITE,
                curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
                curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
                curses.COLOR_YELLOW, curses.COLOR_WHITE)
        # cursor is visible
        self.cursor_visible = True
        # 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
        self.cursor_shape = 1
        # current cursor position
        self.cursor_row = 1
        self.cursor_col = 1
        # last colour used
        self.last_colour = None
        # text and colour buffer
        self.num_pages = 1
        self.vpagenum, self.apagenum = 0, 0
        self.height, self.width = 25, 80
        self.text = [[[(' ', 0)]*80 for _ in range(25)]]
        video.VideoPlugin.__init__(self)

    def close(self):
        """ Close the text interface. """
        video.VideoPlugin.close(self)
        if self.curses_init:
            curses.noraw()
            curses.nl()
            curses.nocbreak()
            self.screen.keypad(False)
            curses.echo()
            curses.endwin()

    def _check_display(self):
        """ Handle screen and interface events. """
        if self.cursor_visible:
            self.window.move(self.cursor_row-1, self.cursor_col-1)
        self.window.refresh()

    def _check_input(self):
        """ Handle keyboard events. """
        s = ''
        i = 0
        while True:
            i = self.window.getch()
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
                    sys.stdout.write(ansi.esc_resize_term % (self.height, self.width))
                    sys.stdout.flush()
                    self.window.resize(self.height, self.width)
                    self._redraw()
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

    def _redraw(self):
        """ Redraw the screen. """
        self.window.clear()
        if self.last_colour != 0:
            self.window.bkgdset(' ', 0)
        for row, textrow in enumerate(self.text[self.vpagenum]):
            for col, charattr in enumerate(textrow):
                try:
                    self.window.addstr(row, col, charattr[0], charattr[1])
                except curses.error:
                    pass
        if self.cursor_visible:
            self.window.move(self.cursor_row-1, self.cursor_col-1)
        self.window.refresh()

    def _set_curses_palette(self):
        """ Initialise the curses colour palette. """
        if self.can_change_palette:
            for back in range(8):
                for fore in range(16):
                    curses.init_pair(back*16+fore+1,
                            self.default_colors[fore], self.default_colors[back])
        else:
            for back in range(8):
                for fore in range(8):
                    if back == 0 and fore == 7:
                        # black on white mandatorily mapped on color 0
                        pass
                    elif back == 0:
                        curses.init_pair(back*8+fore+1,
                                self.default_colors[fore], self.default_colors[back])
                    else:
                        curses.init_pair(back*8+fore,
                                self.default_colors[fore], self.default_colors[back])

    def _curses_colour(self, fore, back, blink):
        """ Convert split attribute to curses colour. """
        if self.can_change_palette:
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

    def set_mode(self, mode_info):
        """ Change screen mode. """
        self.height = mode_info.height
        self.width = mode_info.width
        self.num_pages = mode_info.num_pages
        self.text = [[[(' ', 0)]*self.width for _ in range(self.height)]
                                            for _ in range(self.num_pages)]
        self.window.clear()
        self.window.refresh()
        self.window.move(0, 0)
        sys.stdout.write(ansi.esc_resize_term % (self.height, self.width))
        sys.stdout.flush()
        #curses.resizeterm(self.height, self.width)
        self.window.resize(self.height, self.width)
        self._set_curses_palette()

    def set_page(self, new_vpagenum, new_apagenum):
        """ Set visible and active page. """
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw()

    def copy_page(self, src, dst):
        """ Copy screen pages. """
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw()

    def clear_rows(self, back_attr, start, stop):
        """ Clear screen rows. """
        self.text[self.apagenum][start-1:stop] = [
                [(' ', 0)]*len(self.text[self.apagenum][0])
                for _ in range(start-1, stop)]
        if self.apagenum != self.vpagenum:
            return
        self.window.bkgdset(' ', self._curses_colour(7, back_attr, False))
        for r in range(start, stop+1):
            try:
                self.window.move(r-1, 0)
                self.window.clrtoeol()
            except curses.error:
                pass

    def set_palette(self, new_palette, new_palette1):
        """ Build the game palette. """
        if self.can_change_palette:
            for i in range(len(new_palette)):
                r, g, b = new_palette[i]
                curses.init_color(self.default_colors[i],
                                (r*1000)//255, (g*1000)//255, (b*1000)//255)

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """ Change attribute of cursor. """
        # term.write(ansi.esc_set_cursor_colour % ansi.colournames[attr%16])

    def show_cursor(self, cursor_on):
        """ Change visibility of cursor. """
        self.cursor_visible = cursor_on
        curses.curs_set(self.cursor_shape if cursor_on else 0)

    def set_cursor_shape(self, width, height, from_line, to_line):
        """ Set the cursor shape. """
        if (to_line-from_line) >= 4:
            self.cursor_shape = 2
        else:
            self.cursor_shape = 1
        curses.curs_set(self.cursor_shape if self.cursor_visible else 0)

    def put_glyph(self, pagenum, row, col, c, fore, back, blink, underline, for_keys):
        """ Put a character at a given position. """
        if c == '\0':
            c = ' '
        try:
            char = unicodepage.UTF8Converter().to_utf8(c)
        except KeyError:
            char = ' '*len(c)
        colour = self._curses_colour(fore, back, blink)
        self.text[pagenum][row-1][col-1] = char, colour
        if len(c) > 1:
            self.text[pagenum][row-1][col] = '', colour
        if pagenum == self.vpagenum:
            if colour != self.last_colour:
                self.last_colour = colour
                self.window.bkgdset(' ', colour)
            try:
                self.window.addstr(row-1, col-1, char, colour)
            except curses.error:
                pass

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                    self.text[self.apagenum][from_line:scroll_height]
                    + [[(' ', 0)]*len(self.text[self.apagenum][0])])
        if self.apagenum != self.vpagenum:
            return
        self.window.scrollok(True)
        self.window.setscrreg(from_line-1, scroll_height-1)
        try:
            self.window.scroll(1)
        except curses.error:
            pass
        self.window.scrollok(False)
        self.window.setscrreg(1, self.height-1)
        self.clear_rows(back_attr, scroll_height, scroll_height)
        if self.cursor_row > 1:
            self.window.move(self.cursor_row-2, self.cursor_col-1)

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                    [[(' ', 0)]*len(self.text[self.apagenum][0])]
                    + self.text[self.apagenum][from_line-1:scroll_height-1])
        if self.apagenum != self.vpagenum:
            return
        self.window.scrollok(True)
        self.window.setscrreg(from_line-1, scroll_height-1)
        try:
            self.window.scroll(-1)
        except curses.error:
            pass
        self.window.scrollok(False)
        self.window.setscrreg(1, self.height-1)
        self.clear_rows(back_attr, from_line, from_line)
        if self.cursor_row < self.height:
            self.window.move(self.cursor_row, self.cursor_col-1)

    def set_caption_message(self, msg):
        """ Add a message to the window caption. """
        if msg:
            sys.stdout.write(ansi.esc_set_title % (caption + ' - ' + msg))
        else:
            sys.stdout.write(ansi.esc_set_title % caption)
        sys.stdout.flush()
        # redraw in case terminal didn't recognise ansi sequence
        self._redraw()



prepare()
