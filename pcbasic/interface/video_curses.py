"""
PC-BASIC - video_curses.py
Text interface implementation for Unix

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import locale
import logging
try:
    import curses
except ImportError:
    curses = None

from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea
from ..basic.base import signals
from ..compat import MACOS, PY2, console
from ..compat import iter_chunks

from .video import VideoPlugin
from .base import video_plugins, InitFailed

if PY2: # pragma: no cover
    # curses works with bytes in Python 2
    _ENCODING = locale.getpreferredencoding()

    def _to_str(unistr):
        """Convert unicode to str."""
        return unistr.encode(_ENCODING, 'replace')

    def _get_wch(window):
        """Get input from keyboard; unicode if character, int otherwise."""
        s = bytearray()
        while True:
            i = window.getch()
            if i > 255:
                return i
            if i < 0:
                return bytes(s).decode(_ENCODING, 'replace')
            s.append(i)

else:

    def _to_str(unistr):
        """Convert unicode to str."""
        return unistr

    def _get_wch(window):
        """Get input from keyboard; unicode if character, int otherwise."""
        try:
            return window.get_wch()
        except curses.error:
            # no input
            return u''

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
        logging.warning('The `curses` interface is deprecated, please use the `text` interface instead.')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # we need to ensure setlocale() has been run first to allow unicode input
        if not curses:
            raise InitFailed('`Module `curses` not found')
        if not console:
            raise InitFailed('This interface requires a console terminal (tty).')
        # set the ESC-key delay to 25 ms unless otherwise set
        # set_escdelay seems to be unavailable on python curses.
        if 'ESCDELAY' not in os.environ:
            os.environ['ESCDELAY'] = '25'
        self.height, self.width = 25, 80
        # curses borders are 1 character wide
        self.border_y = 1
        self.border_x = 1
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
        self.f12_active = False
        # initialised by __enter__
        self.screen = None
        self.orig_size = None
        self.window = None
        self.can_change_palette = None
        self._attributes = []

    def __enter__(self):
        """Open ANSI interface."""
        VideoPlugin.__enter__(self)
        try:
            self.screen = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.nonl()
            curses.raw()
            self.orig_size = self.screen.getmaxyx()
            self.window = curses.newwin(
                self.height + self.border_y*2, self.width + self.border_x*2, 0, 0
            )
            self.window.nodelay(True)
            self.window.keypad(True)
            self.window.scrollok(False)
            curses.start_color()
            # curses mistakenly believes changing palettes works on macOS's Terminal.app
            self.can_change_palette = (not MACOS) and (
                curses.can_change_color() and curses.COLORS >= 16 and curses.COLOR_PAIRS > 128
            )
            self._set_default_colours(16)
            bgcolor = self._curses_colour(7, 0, False)
            self.set_border_attr(0)
            self._resize(self.height, self.width)
            self.screen.clear()
        except Exception as e:
            # if setup fails, don't leave the terminal raw
            self._close()
            raise

    def __exit__(self, type, value, traceback):
        """Close the curses interface."""
        try:
            self._close()
        finally:
            VideoPlugin.__exit__(self, type, value, traceback)

    def _close(self):
        """Close the curses interface."""
        try:
            curses.noraw()
            curses.nl()
            curses.nocbreak()
            if self.screen:
                self.screen.keypad(False)
            curses.echo()
            curses.endwin()
            # restore original terminal size, colours and cursor
            console.reset()
        except Exception as e:
            logging.error('Exception on closing curses interface: %s', e)

    def _work(self):
        """Handle screen and interface events."""
        if self.cursor_visible:
            self.window.move(self.border_y+self.cursor_row-1, self.border_x+self.cursor_col-1)
        self.window.refresh()

    def _check_input(self):
        """Handle keyboard events."""
        inp = _get_wch(self.window)
        if isinstance(inp, int):
            # replace Mac backspace - or it will come through as ctrl+backspace which is delete
            if inp == 127:
                inp = curses.KEY_BACKSPACE
            else:
                if inp == curses.KEY_BREAK:
                    # this is fickle, on many terminals doesn't work
                    self._input_queue.put(signals.Event(
                        signals.KEYB_DOWN, (u'', scancode.BREAK, [scancode.CTRL])
                    ))
                # scancode, insert here and now
                # there shouldn't be a mix of special keys and utf8 in one
                # uninterrupted string, since the only reason an uninterrupted
                # string would be longer than 1 char is because it's a single
                # utf-8 sequence or a pasted utf-8 string, neither of which
                # can contain special characters.
                # however, if that does occur, this won't work correctly.
                scan = CURSES_TO_SCAN.get(inp, None)
                char = CURSES_TO_EASCII.get(inp, u'')
                if scan or char:
                    self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, scan, [])))
                    if inp == curses.KEY_F12:
                        self.f12_active = True
                    else:
                        self._unset_f12()
        else:
            # could be more than one code point, handle these one by one
            for char in inp:
                #check_full=False to allow pasting chunks of text
                self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, None, [])))
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
        console.resize(height + by*2, width + bx*2)
        self.window.resize(height + by*2, width + bx*2)
        self.set_border_attr(self.border_attr)

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
                    curses.init_pair(
                        back*16+fore+1, self.default_colors[fore], self.default_colors[back]
                    )
        else:
            try:
                for back in range(8):
                    for fore in range(8):
                        if back == 0 and fore == 7:
                            # black on white mandatorily mapped on color 0
                            pass
                        elif back == 0:
                            curses.init_pair(
                                back*8+fore+1, self.default_colors[fore], self.default_colors[back]
                            )
                        else:
                            curses.init_pair(
                                back*8+fore, self.default_colors[fore], self.default_colors[back]
                            )
            except curses.error:
                pass

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

    def set_mode(self, canvas_height, canvas_width, text_height, text_width):
        """Change screen mode."""
        self.height = text_height
        self.width = text_width
        bgcolor = self._curses_colour(7, 0, False)
        self._resize(self.height, self.width)
        self._set_curses_palette()
        self.window.clear()
        self.window.refresh()
        self.window.move(0, 0)

    def clear_rows(self, back_attr, start, stop):
        """Clear screen rows."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self.window.bkgdset(32, bgcolor)
        for r in range(start, stop+1):
            try:
                self.window.move(self.border_y + r - 1, self.border_x)
                self.window.clrtoeol()
            except curses.error:
                pass
        # fix border
        self.set_border_attr(self.border_attr)

    def set_palette(self, attributes, dummy_pack_pixels):
        """Build the palette."""
        self._set_default_colours(len(attributes))
        rgb_table = [_fore for _fore, _, _, _ in attributes[:16]]
        if len(attributes) > 16:
            # *assume* the first 16 attributes are foreground-on-black
            # this is the usual textmode byte attribute arrangement
            fore = range(16) * 16
            back = tuple(_b for _b in range(8) for _ in range(16)) * 2
        else:
            fore = range(len(attributes))
            # assume black background
            # blink dim-to-bright etc won't work on terminals anyway
            back = (0,) * len(attributes)
        blink = tuple(_blink for _, _, _blink, _ in attributes)
        under = tuple(_under for _, _, _, _under in attributes)
        int_attributes = zip(fore, back, blink, under)
        self._attributes = int_attributes
        if self.can_change_palette:
            for i, rgb in enumerate(rgb_table):
                r, g, b = rgb
                curses.init_color(
                    self.default_colors[i], (r*1000)//255, (g*1000)//255, (b*1000)//255
                )

    def set_border_attr(self, attr):
        """Change border attribute."""
        self.border_attr = attr
        self.window.attrset(self._curses_colour(attr, attr, False))
        self.window.border()

    def move_cursor(self, row, col, attr, width):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = row, col
        # cursor attr and width not supported

    def show_cursor(self, cursor_on, cursor_blinks):
        """Change visibility of cursor."""
        # blinking/non-blinking not supported
        self._show_cursor(cursor_on)

    def _show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self.cursor_visible = cursor_on
        if cursor_on:
            console.show_cursor(block=self.cursor_shape == 2)
        else:
            console.hide_cursor()

    def set_cursor_shape(self, from_line, to_line):
        """Set the cursor shape."""
        if (to_line-from_line) >= 4:
            self.cursor_shape = 2
        else:
            self.cursor_shape = 1
        self._show_cursor(self.cursor_visible)

    def update(self, row, col, unicode_matrix, attr_matrix, y0, x0, sprite):
        """Put text or pixels at a given position."""
        start_col = col
        for text, attrs in zip(unicode_matrix, attr_matrix):
            for unicode_list, attr in iter_chunks(text, attrs):
                fore, back, blink, underline = self._attributes[attr]
                unicode_list = [_c if _c != u'\0' else u' ' for _c in unicode_list]
                colour = self._curses_colour(fore, back, blink)
                #if colour != self.last_colour:
                self.last_colour = colour
                self.window.bkgdset(32, colour)
                try:
                    self.window.addstr(
                        self.border_y+row-1, self.border_x+col-1,
                        _to_str(u''.join(unicode_list)), colour
                    )
                except curses.error:
                    pass
                col += len(unicode_list)
            row += 1
            col = start_col

    def scroll(self, direction, from_line, scroll_height, back_attr):
        """Scroll the screen between from_line and scroll_height."""
        if direction == -1:
            self._scroll_up(from_line, scroll_height, back_attr)
        else:
            self._scroll_down(from_line, scroll_height, back_attr)

    def _scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self._curses_scroll(from_line, scroll_height, -1)
        self.clear_rows(back_attr, scroll_height, scroll_height)
        if self.cursor_row > 1:
            self.window.move(self.border_y+self.cursor_row-2, self.border_x+self.cursor_col-1)

    def _scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        bgcolor = self._curses_colour(7, back_attr, False)
        self._curses_scroll(from_line, scroll_height, 1)
        self.clear_rows(back_attr, from_line, from_line)
        if self.cursor_row < self.height:
            self.window.move(self.border_y+self.cursor_row, self.border_x+self.cursor_col-1)

    def _curses_scroll(self, from_line, scroll_height, direction):
        """Perform a scroll in curses."""
        if from_line != scroll_height:
            self.window.scrollok(True)
            self.window.setscrreg(self.border_y+from_line-1, self.border_y+scroll_height-1)
            try:
                self.window.scroll(-direction)
            except curses.error:
                pass
            self.window.scrollok(False)
            self.window.setscrreg(self.border_y+1, self.border_y+self.height-1)
