"""
PC-BASIC - editor.py
Direct mode environment

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import string

from .base import error
from .base import tokens as tk
from .base.eascii import as_bytes as ea

# alt+key macros for interactive mode
# these happen at a higher level than F-key macros
alt_key_replace = {
    ea.ALT_a: tk.KW_AUTO,
    ea.ALT_b: tk.KW_BSAVE,
    ea.ALT_c: tk.KW_COLOR,
    ea.ALT_d: tk.KW_DELETE,
    ea.ALT_e: tk.KW_ELSE,
    ea.ALT_f: tk.KW_FOR,
    ea.ALT_g: tk.KW_GOTO,
    ea.ALT_h: tk.KW_HEX,
    ea.ALT_i: tk.KW_INPUT,
    ea.ALT_k: tk.KW_KEY,
    ea.ALT_l: tk.KW_LOCATE,
    ea.ALT_m: tk.KW_MOTOR,
    ea.ALT_n: tk.KW_NEXT,
    ea.ALT_o: tk.KW_OPEN,
    ea.ALT_p: tk.KW_PRINT,
    ea.ALT_r: tk.KW_RUN,
    ea.ALT_s: tk.KW_SCREEN,
    ea.ALT_t: tk.KW_THEN,
    ea.ALT_u: tk.KW_USING,
    ea.ALT_v: tk.KW_VAL,
    ea.ALT_w: tk.KW_WIDTH,
    ea.ALT_x: tk.KW_XOR,
    }


class FunctionKeyMacros(object):
    """Handles display of function-key macro strings."""

    # characters to replace
    _replace_chars = {
        b'\x07': b'\x0e', b'\x08': b'\xfe', b'\x09': b'\x1a', b'\x0A': b'\x1b',
        b'\x0B': b'\x7f', b'\x0C': b'\x16', b'\x0D': b'\x1b', b'\x1C': b'\x10',
        b'\x1D': b'\x11', b'\x1E': b'\x18', b'\x1F': b'\x19'}

    def __init__(self, keyboard, screen, num_fn_keys):
        """Initialise user-definable key list."""
        self._keyboard = keyboard
        self._screen = screen
        self._bar = screen.bottom_bar
        self._num_fn_keys = num_fn_keys
        self._update_bar()

    def list_keys(self):
        """Print a list of the function key macros."""
        for i in range(self._num_fn_keys):
            text = self._keyboard.get_macro(i)
            text = b''.join(self._replace_chars.get(s, s) for s in text)
            self._screen.write_line(b'F%d %s' % (i+1, text))

    def set(self, num, macro):
        """Set macro for given function key."""
        # NUL terminates macro string, rest is ignored
        # macro starting with NUL is empty macro
        self._keyboard.set_macro(num, macro)
        self._update_bar()

    def key_(self, args):
        """KEY: show/hide/list macros."""
        command, = args
        if command == tk.ON:
            self._bar.show(True, self._screen)
        elif command == tk.OFF:
            self._bar.show(False, self._screen)
        elif command == tk.LIST:
            self.list_keys()

    def _update_bar(self):
        """Show/hide the function keys line on the active page."""
        self._bar.clear()
        for i in range(10):
            text = self._keyboard.get_macro(i)[:6]
            text = b''.join(self._replace_chars.get(s, s) for s in text)
            kcol = 1 + 8*i
            self._bar.write(str(i+1)[-1], kcol, False)
            self._bar.write(text, kcol+1, True)


class Editor(object):
    """Interactive environment."""

    def __init__(self, screen, keyboard, sound, io_streams, lpt1_file):
        """Initialise environment."""
        # overwrite mode (instead of insert)
        self._overwrite_mode = True
        self._screen = screen
        self._sound = sound
        self._keyboard = keyboard
        self._io_streams = io_streams
        self._lpt1_file = lpt1_file

    def wait_screenline(self, write_endl=True, from_start=False):
        """Enter interactive mode and read string from console."""
        # from_start means direct entry mode, otherwise input mode
        prompt_width = 0 if from_start else self._screen.current_col-1
        try:
            # give control to user for interactive mode
            prompt_row, left, right = self._interact(prompt_width)
        except error.Break:
            # x0E CR LF is printed to redirects at break
            self._io_streams.write(b'\x0e')
            # while only a line break appears on the console
            self._screen.write_line()
            raise
        # get contents of the logical line
        if from_start:
            outstr = self._screen.text.get_logical_line(
                    self._screen.apagenum, self._screen.current_row)
        else:
            outstr = self._screen.text.get_logical_line_from(
                    self._screen.apagenum, self._screen.current_row,
                    prompt_row, left, right)
        # redirects output exactly the contents of the logical line
        # including any trailing whitespace and chars past 255
        self._io_streams.write(outstr)
        # go to last row of logical line
        self._screen.current_row = self._screen.text.find_end_of_line(
                self._screen.apagenum, self._screen.current_row)
        # echo the CR, if requested
        if write_endl:
            self._screen.write_line()
        # to the parser/INPUT, only the first 255 chars are returned
        # with trailing whitespace removed
        return outstr[:255].rstrip(b' \t\n')

    def _interact(self, prompt_width):
        """Manage the interactive mode."""
        # force cursor visibility in all cases
        self._screen.cursor.show(True)
        try:
            # this is where we started
            start_row = self._screen.current_row
            furthest_left = 1 + prompt_width
            # this is where we arrow-keyed on the start line
            furthest_right = self._screen.current_col
            while True:
                row, col = self._screen.current_row, self._screen.current_col
                if row == start_row:
                    furthest_left = min(col, furthest_left)
                    furthest_right = max(col, furthest_right)
                    if col == self._screen.mode.width and self._screen.overflow:
                        furthest_right += 1
                # get one e-ASCII or dbcs code
                d = self._keyboard.get_fullchar_block()
                if not d:
                    # input stream closed
                    raise error.Exit()
                if d in (ea.UP, ea.CTRL_6, ea.DOWN, ea.CTRL_MINUS,  ea.RIGHT, ea.CTRL_BACKSLASH,
                          ea.LEFT, ea.CTRL_RIGHTBRACKET, ea.HOME, ea.CTRL_k, ea.END, ea.CTRL_n):
                    # arrow keys drop us out of insert mode
                    self.set_overwrite_mode(True)
                if d == ea.CTRL_c:
                    # CTRL-C -- only caught here, not in wait_char like <CTRL+BREAK>
                    raise error.Break()
                elif d == b'\r':
                    # ENTER, CTRL+M
                    break
                elif d == b'\a':
                    # BEL, CTRL+G
                    self._sound.play_alert()
                elif d == b'\b':
                    # BACKSPACE, CTRL+H
                    self.backspace(start_row, furthest_left)
                elif d == b'\t':
                    # TAB, CTRL+I
                    self.tab()
                elif d == b'\n':
                    # CTRL+ENTER, CTRL+J
                    self._screen.line_feed()
                elif d == ea.ESCAPE:
                    # ESC, CTRL+[
                    self.clear_line(row, furthest_left)
                elif d in (ea.CTRL_END, ea.CTRL_e):
                    self._screen.clear_from(row, col)
                elif d in (ea.UP, ea.CTRL_6):
                    self._screen.set_pos(row - 1, col, scroll_ok=False)
                elif d in (ea.DOWN, ea.CTRL_MINUS):
                    self._screen.set_pos(row + 1, col, scroll_ok=False)
                elif d in (ea.RIGHT, ea.CTRL_BACKSLASH):
                    self._screen.incr_pos()
                elif d in (ea.LEFT, ea.CTRL_RIGHTBRACKET):
                    self._screen.decr_pos()
                elif d in (ea.CTRL_RIGHT, ea.CTRL_f):
                    self.skip_word_right()
                elif d in (ea.CTRL_LEFT, ea.CTRL_b):
                    self.skip_word_left()
                elif d in (ea.INSERT, ea.CTRL_r):
                    self.set_overwrite_mode(not self._overwrite_mode)
                elif d in (ea.DELETE, ea.CTRL_BACKSPACE):
                    self._screen.delete_fullchar()
                elif d in (ea.HOME, ea.CTRL_k):
                    self._screen.set_pos(1, 1)
                elif d in (ea.END, ea.CTRL_n):
                    self._screen.move_to_end()
                elif d in (ea.CTRL_HOME, ea.CTRL_l):
                    self._screen.clear_view()
                elif d == ea.CTRL_PRINT:
                    # ctrl+printscreen toggles printer copy
                    self._io_streams.toggle_echo(self._lpt1_file)
                else:
                    try:
                        # these are done on a less deep level than the fn key macros
                        letters = list(alt_key_replace[d]) + [' ']
                    except KeyError:
                        letters = [d]
                    for d in letters:
                        # ignore eascii by this point, but not dbcs
                        if d[0] not in (b'\0', b'\r'):
                            if not self._overwrite_mode:
                                self._screen.insert_fullchars(
                                        self._screen.current_row, col, d, self._screen.attr)
                                self._screen.set_pos(self._screen.current_row,
                                        self._screen.current_col + len(d))
                            else:
                                # put all dbcs in before messing with cursor position
                                for c in d:
                                    self._screen.write_char(c, do_scroll_down=True)
        finally:
            self.set_overwrite_mode(True)
            # reset cursor visibility
            self._screen.cursor.reset_visibility()
        return start_row, furthest_left, furthest_right

    def set_overwrite_mode(self, new_overwrite=True):
        """Set or unset the overwrite mode (INS)."""
        if new_overwrite != self._overwrite_mode:
            self._overwrite_mode = new_overwrite
            self._screen.cursor.set_default_shape(new_overwrite)

    def clear_line(self, the_row, from_col=1):
        """Clear whole logical line (ESC), leaving prompt."""
        self._screen.clear_from(
                self._screen.text.find_start_of_line(self._screen.apagenum, the_row), from_col)

    def backspace(self, start_row, start_col):
        """Delete the char to the left (BACKSPACE)."""
        row, col = self._screen.current_row, self._screen.current_col
        start_row = self._screen.text.find_start_of_line(self._screen.apagenum, row)
        # don't backspace through prompt or through start of logical line
        if ((col == 1 and row > start_row) or (col != start_col or row != start_row)):
            self._screen.decr_pos()
        self._screen.delete_fullchar()

    def tab(self):
        """Jump to next 8-position tab stop (TAB)."""
        row, col = self._screen.current_row, self._screen.current_col
        newcol = 9 + 8 * int((col-1) / 8)
        if self._overwrite_mode:
            self._screen.set_pos(row, newcol, scroll_ok=False)
        else:
            self._screen.insert_fullchars(row, col, b' ' * 8, self._screen.attr)
            self._screen.set_pos(row, newcol)

    def skip_word_right(self):
        """Skip one word to the right (CTRL+RIGHT)."""
        crow, ccol = self._screen.current_row, self._screen.current_col
        # find non-alphanumeric chars
        while True:
            c = chr(self._screen.text.get_char(self._screen.apagenum, crow, ccol))
            if (c not in string.digits + string.ascii_letters):
                break
            ccol += 1
            if ccol > self._screen.mode.width:
                if crow >= self._screen.scroll_area.bottom:
                    # nothing found
                    return
                crow += 1
                ccol = 1
        # find alphanumeric chars
        while True:
            c = chr(self._screen.text.get_char(self._screen.apagenum, crow, ccol))
            if (c in string.digits + string.ascii_letters):
                break
            ccol += 1
            if ccol > self._screen.mode.width:
                if crow >= self._screen.scroll_area.bottom:
                    # nothing found
                    return
                crow += 1
                ccol = 1
        self._screen.set_pos(crow, ccol)

    def skip_word_left(self):
        """Skip one word to the left (CTRL+LEFT)."""
        crow, ccol = self._screen.current_row, self._screen.current_col
        # find alphanumeric chars
        while True:
            ccol -= 1
            if ccol < 1:
                if crow <= self._screen.scroll_area.top:
                    # not found
                    return
                crow -= 1
                ccol = self._screen.mode.width
            c = chr(self._screen.text.get_char(self._screen.apagenum, crow, ccol))
            if (c in string.digits + string.ascii_letters):
                break
        # find non-alphanumeric chars
        while True:
            last_row, last_col = crow, ccol
            ccol -= 1
            if ccol < 1:
                if crow <= self._screen.scroll_area.top:
                    break
                crow -= 1
                ccol = self._screen.mode.width
            c = chr(self._screen.text.get_char(self._screen.apagenum, crow, ccol))
            if (c not in string.digits + string.ascii_letters):
                break
        self._screen.set_pos(last_row, last_col)
