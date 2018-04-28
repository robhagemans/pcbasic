"""
PC-BASIC - video_curses.py
Text interface implementation for Unix

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import locale
try:
    import curses
except ImportError:
    curses = None

from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea
from ..basic.base import signals
from ..compat import MACOS

from .video import VideoPlugin
from .base import video_plugins, InitFailed
# for a few ansi sequences not supported by curses
# only use these if you clear the screen afterwards,
# so you don't see gibberish if the terminal doesn't support the sequence.
from . import ansi

# sys.stdout expects bytes
SET_TITLE = ansi.SET_TITLE.encode('ascii')
RESIZE_TERM = ansi.RESIZE_TERM.encode('ascii')


ENCODING = locale.getpreferredencoding()

if curses:
    # curses keycodes
    CURSES_TO_SCAN = {
        curses.KEY_F1: scancode.F1, curses.KEY_F2: scancode.F2, curses.KEY_F3: scancode.F3,
        curses.KEY_F4: scancode.F4, curses.KEY_F5: scancode.F5, curses.KEY_F6: scancode.F6,
        curses.KEY_F7: scancode.F7, curses.KEY_F8: scancode.F8, curses.KEY_F9: scancode.F9,
        curses.KEY_F10: scancode.F10, curses.KEY_F11: scancode.F11, curses.KEY_F12: scancode.F12,
        curses.KEY_END: scancode.END, curses.KEY_HOME: scancode.HOME, curses.KEY_UP: scancode.UP,
        curses.KEY_DOWN: scancode.DOWN, curses.KEY_RIGHT: scancode.RIGHT,
        curses.KEY_LEFT: scancode.LEFT, curses.KEY_IC: scancode.INSERT,
        curses.KEY_DC: scancode.DELETE, curses.KEY_PPAGE: scancode.PAGEUP,
        curses.KEY_NPAGE: scancode.PAGEDOWN, curses.KEY_BACKSPACE: scancode.BACKSPACE,
        curses.KEY_PRINT: scancode.PRINT, curses.KEY_CANCEL: scancode.ESCAPE,
    }
    CURSES_TO_EASCII = {
        curses.KEY_F1: uea.F1, curses.KEY_F2: uea.F2, curses.KEY_F3: uea.F3, curses.KEY_F4: uea.F4,
        curses.KEY_F5: uea.F5, curses.KEY_F6: uea.F6, curses.KEY_F7: uea.F7, curses.KEY_F8: uea.F8,
        curses.KEY_F9: uea.F9, curses.KEY_F10: uea.F10, curses.KEY_F11: uea.F11,
        curses.KEY_F12: uea.F12, curses.KEY_END: uea.END, curses.KEY_HOME: uea.HOME,
        curses.KEY_UP: uea.UP, curses.KEY_DOWN: uea.DOWN, curses.KEY_RIGHT: uea.RIGHT,
        curses.KEY_LEFT: uea.LEFT, curses.KEY_IC: uea.INSERT, curses.KEY_DC: uea.DELETE,
        curses.KEY_PPAGE: uea.PAGEUP, curses.KEY_NPAGE: uea.PAGEDOWN,
        curses.KEY_BACKSPACE: uea.BACKSPACE, curses.KEY_CANCEL: uea.ESCAPE,
    }


@video_plugins.register('curses')
class VideoCurses(VideoPlugin):
    """Curses-based text interface."""

    def __init__(self, input_queue, video_queue, caption=u'', border_width=0, **kwargs):
        """Initialise the text interface."""
        VideoPlugin.__init__(self, input_queue, video_queue)
        # we need to ensure setlocale() has been run first to allow unicode input
        if not curses:
            raise InitFailed('`Module `curses` not found')
        # set the ESC-key delay to 25 ms unless otherwise set
        # set_escdelay seems to be unavailable on python curses.
        if not os.environ.has_key('ESCDELAY'):
            os.environ['ESCDELAY'] = '25'
        self.height, self.width = 25, 80
        self.border_y = int(round((self.height * border_width)/200.))
        self.border_x = int(round((self.width * border_width)/200.))
        self.caption = caption
        # cursor is visible
        self.cursor_visible = True
        # 1 is line ('visible'), 2 is block ('highly visible'), 3 is invisible
        self.cursor_shape = 1
        # current cursor position
        self.cursor_row = 1
        self.cursor_col = 1
        # last colour used
        self.last_colour = None
        self.vpagenum, self.apagenum = 0, 0
        self.f12_active = False
        # initialised by __enter__
        self.screen = None
        self.orig_size = None
        self.underlay = None
        self.window = None
        self.can_change_palette = None
        self.text = None

    def __enter__(self):
        """Open ANSI interface."""
        VideoPlugin.__enter__(self)
        self.screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.nonl()
        curses.raw()
        self.orig_size = self.screen.getmaxyx()
        self.underlay = curses.newwin(
            self.height + self.border_y*2, self.width + self.border_x*2, 0, 0)
        self.window = curses.newwin(self.height, self.width, self.border_y, self.border_x)
        self.window.nodelay(True)
        self.window.keypad(True)
        self.window.scrollok(False)
        curses.start_color()
        # curses mistakenly believes changing palettes works on macOS's Terminal.app
        self.can_change_palette = (not MACOS) and (
                curses.can_change_color() and curses.COLORS >= 16 and curses.COLOR_PAIRS > 128)
        sys.stdout.write(SET_TITLE % self.caption)
        sys.stdout.flush()
        self._set_default_colours(16)
        bgcolor = self._curses_colour(7, 0, False)
        # text and colour buffer
        self.text = [[[(u' ', bgcolor)]*self.width for _ in range(self.height)]]
        self.set_border_attr(0)
        self.screen.clear()

    def __exit__(self, type, value, traceback):
        """Close the curses interface."""
        try:
            # restore original terminal size
            self._resize(*self.orig_size)
            # restore sane terminal state
            curses.noraw()
            curses.nl()
            curses.nocbreak()
            self.screen.keypad(False)
            curses.echo()
            curses.endwin()
        finally:
            VideoPlugin.__exit__(self, type, value, traceback)

    def _work(self):
        """Handle screen and interface events."""
        if self.cursor_visible:
            self.window.move(self.cursor_row-1, self.cursor_col-1)
        self.window.refresh()

    def _check_input(self):
        """Handle keyboard events."""
        s = ''
        i = 0
        while True:
            i = self.window.getch()
            # replace Mac backspace - or it will come through as ctrl+backspace which is delete
            if i == 127:
                i = curses.KEY_BACKSPACE
            if i < 0:
                break
            elif i < 256:
                s += chr(i)
            else:
                if i == curses.KEY_BREAK:
                    # this is fickle, on many terminals doesn't work
                    self._input_queue.put(signals.Event(
                            signals.KEYB_DOWN, (u'', scancode.BREAK, [scancode.CTRL])))
                elif i == curses.KEY_RESIZE:
                    self._resize(self.height, self.width)
                # scancode, insert here and now
                # there shouldn't be a mix of special keys and utf8 in one
                # uninterrupted string, since the only reason an uninterrupted
                # string would be longer than 1 char is because it's a single
                # utf-8 sequence or a pasted utf-8 string, neither of which
                # can contain special characters.
                # however, if that does occur, this won't work correctly.
                scan = CURSES_TO_SCAN.get(i, None)
                c = CURSES_TO_EASCII.get(i, '')
                if scan or c:
                    self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, scan, [])))
                    if i == curses.KEY_F12:
                        self.f12_active = True
                    else:
                        self._unset_f12()
        # convert into unicode chars
        u = s.decode(ENCODING, 'replace')
        # then handle these one by one
        for c in u:
            #check_full=False to allow pasting chunks of text
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, None, [])))
            self._unset_f12()

    def _unset_f12(self):
        """Deactivate F12 """
        if self.f12_active:
            self._input_queue.put(signals.Event(signals.KEYB_UP, (scancode.F12,)))
            self.f12_active = False

    def _resize(self, height, width):
        """Resize the terminal."""
        by, bx = self.border_y, self.border_x
        # curses.resizeterm triggers KEY_RESIZE leading to a flickering loop
        # curses.resize_term doesn't resize the terminal
        sys.stdout.write(RESIZE_TERM % (height + by*2, width + bx*2))
        sys.stdout.flush()
        self.underlay.resize(height + by*2, width + bx*2)
        self.window.resize(height, width)
        self.set_border_attr(self.border_attr)

    def _redraw(self):
        """Redraw the screen."""
        self.window.clear()
        if self.last_colour != 0:
            self.window.bkgdset(' ', self._curses_colour(7, 0, False))
        for row, textrow in enumerate(self.text[self.vpagenum]):
            for col, charattr in enumerate(textrow):
                try:
                    self.window.addstr(
                            row, col, charattr[0].encode(ENCODING, 'replace'), charattr[1])
                except curses.error:
                    pass
        if self.cursor_visible:
            self.window.move(self.cursor_row-1, self.cursor_col-1)
        self.window.refresh()

    def _set_default_colours(self, num_attrs):
        """Initialise the default colours for the palette."""
        if self.can_change_palette:
            self.default_colors = range(16, 32)
        elif num_attrs == 2:
            self.default_colors = (curses.COLOR_BLACK, curses.COLOR_WHITE) * 8
        elif num_attrs == 4:
            self.default_colors = (
                curses.COLOR_BLACK, curses.COLOR_CYAN,
                curses.COLOR_MAGENTA, curses.COLOR_WHITE) * 4
        else:
            # curses colours mapped onto EGA
            self.default_colors = (
                curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
                curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
                curses.COLOR_YELLOW, curses.COLOR_WHITE,
                curses.COLOR_BLACK, curses.COLOR_BLUE, curses.COLOR_GREEN,
                curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA,
                curses.COLOR_YELLOW, curses.COLOR_WHITE)

    def _set_curses_palette(self):
        """Initialise the curses colour palette."""
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
        """Convert split attribute to curses colour."""
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
        """Change screen mode."""
        self.height = mode_info.height
        self.width = mode_info.width
        self._set_default_colours(len(mode_info.palette))
        bgcolor = self._curses_colour(7, 0, False)
        self.text = [
                [[(u' ', bgcolor)]*self.width for _ in xrange(self.height)]
                for _ in xrange(mode_info.num_pages)
            ]
        self._resize(self.height, self.width)
        self._set_curses_palette()
        self.window.clear()
        self.window.refresh()
        self.window.move(0, 0)

    def set_page(self, new_vpagenum, new_apagenum):
        """Set visible and active page."""
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw()

    def copy_page(self, src, dst):
        """Copy screen pages."""
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw()

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self.text[self.apagenum][start-1:stop] = [
                [(u' ', bgcolor)]*len(self.text[self.apagenum][0])
                for _ in range(start-1, stop)]
        if self.apagenum != self.vpagenum:
            return
        self.window.bkgdset(' ', bgcolor)
        for r in range(start, stop+1):
            try:
                self.window.move(r-1, 0)
                self.window.clrtoeol()
            except curses.error:
                pass

    def set_palette(self, new_palette, new_palette1):
        """Build the game palette."""
        if self.can_change_palette:
            for i in range(len(new_palette)):
                r, g, b = new_palette[i]
                curses.init_color(self.default_colors[i],
                                (r*1000)//255, (g*1000)//255, (b*1000)//255)

    def set_border_attr(self, attr):
        """Change border attribute."""
        self.border_attr = attr
        self.underlay.bkgd(' ', self._curses_colour(0, attr, False))
        self.underlay.refresh()
        self._redraw()

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        # term.write(ansi.SET_CURSOR_COLOUR % ansi.COLOUR_NAMES[attr%16])

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        curses.curs_set(self.cursor_shape if cursor_on else 0)

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Set the cursor shape."""
        if (to_line-from_line) >= 4:
            self.cursor_shape = 2
        else:
            self.cursor_shape = 1
        curses.curs_set(self.cursor_shape if self.cursor_visible else 0)

    def put_glyph(self, pagenum, row, col, c, is_fullwidth, fore, back, blink, underline):
        """Put a character at a given position."""
        if c == u'\0':
            c = u' '
        colour = self._curses_colour(fore, back, blink)
        self.text[pagenum][row-1][col-1] = c, colour
        if is_fullwidth:
            self.text[pagenum][row-1][col] = u'', colour
        if pagenum == self.vpagenum:
            if colour != self.last_colour:
                self.last_colour = colour
                self.window.bkgdset(' ', colour)
            try:
                self.window.addstr(row-1, col-1, c.encode(ENCODING, 'replace'), colour)
            except curses.error:
                pass

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self.text[self.apagenum][from_line-1:scroll_height] = (
                    self.text[self.apagenum][from_line:scroll_height]
                    + [[(u' ', bgcolor)]*len(self.text[self.apagenum][0])])
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
        """Scroll the screen down between from_line and scroll_height."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self.text[self.apagenum][from_line-1:scroll_height] = (
                    [[(u' ', bgcolor)]*len(self.text[self.apagenum][0])]
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
        """Add a message to the window caption."""
        if msg:
            sys.stdout.write(SET_TITLE % (self.caption + ' - ' + msg))
        else:
            sys.stdout.write(SET_TITLE % self.caption)
        sys.stdout.flush()
        # redraw in case terminal didn't recognise ansi sequence
        self._redraw()
