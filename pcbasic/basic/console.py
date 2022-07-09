"""
PC-BASIC - console.py
Console and interactive environment

(c) 2013--2021 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging

from ..compat import iterchar, int2byte

from .base import error
from .base import tokens as tk
from .base import scancode
from .base.eascii import as_bytes as ea


# alt+key macros for interactive mode
# these happen at a higher level (in the console) than F-key macros (in the keyboard buffer)
ALT_KEY_REPLACE = {
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


# characters to replace in bottom bar
FKEY_MACRO_REPLACE_CHARS = {
    b'\x07': b'\x0e', b'\x08': b'\xfe', b'\x09': b'\x1a', b'\x0A': b'\x1b',
    b'\x0B': b'\x7f', b'\x0C': b'\x16', b'\x0D': b'\x1b', b'\x1C': b'\x10',
    b'\x1D': b'\x11', b'\x1E': b'\x18', b'\x1F': b'\x19'
}


class Console(object):
    """Console / interactive environment."""

    def __init__(self, text_screen, cursor, keyboard, sound, io_streams, num_fn_keys):
        """Initialise environment."""
        self._text_screen = text_screen
        self._cursor = cursor
        self._sound = sound
        self._keyboard = keyboard
        self._io_streams = io_streams
        self._num_fn_keys = num_fn_keys
        # overwrite mode (instead of insert)
        self._overwrite_mode = True
        # needs to be set later due to init order
        self._lpt1_file = None
        self._update_bar()

    def set_lpt1_file(self, lpt1_file):
        """Set the LPT1: file."""
        self._lpt1_file = lpt1_file

    ##########################################################################
    # properties

    @property
    def width(self):
        """Number of columns."""
        return self._text_screen.mode.width

    @property
    def height(self):
        """Number of rows."""
        return self._text_screen.mode.height

    @property
    def current_row(self):
        """Cursor row."""
        return self._text_screen.current_row

    @property
    def current_col(self):
        """Cursor column."""
        return self._text_screen.current_col

    @property
    def overflow(self):
        """Cursor is to the right of rightmost row."""
        return self._text_screen.overflow

    def set_pos(self, row, col):
        """Set cursor position."""
        self._text_screen.set_pos(row, col)

    ##########################################################################
    # interaction

    def read_line(self, prompt=b'', write_endl=True, from_start=False, is_input=False):
        """Enter interactive mode and read string from console."""
        self.write(prompt)
        # disconnect the wrap between line with the prompt and previous line
        if self._text_screen.current_row > 1:
            self._text_screen.set_wrap(self._text_screen.current_row-1, False)
        # from_start means direct entry mode, otherwise input mode
        prompt_width = 0 if from_start else self._text_screen.current_col - 1
        try:
            # give control to user for interactive mode
            prompt_row, left, right = self._interact(prompt_width, is_input=is_input)
        except error.Break:
            # x0E CR LF is printed to redirects at break
            self._io_streams.write(b'\x0e')
            # while only a line break appears on the console
            self.write_line()
            raise
        # get contents of the logical line
        outstr = self._text_screen.get_logical_line(self._text_screen.current_row)
        # if we're on the logical prompt row, only return the contents between left and right
        if not from_start:
            start_row = self._text_screen.find_start_of_line(self._text_screen.current_row)
            # INPUT: the prompt starts at the beginning of a logical line
            # but the row may have moved up: this happens on line 24
            # in this case we need to move up to the start of the logical line
            prompt_row == self._text_screen.find_start_of_line(prompt_row)
            if start_row == prompt_row:
                outstr = outstr[left-1:right-1]
        # redirects output exactly the contents of the logical line
        # including any trailing whitespace and chars past 255
        self._io_streams.write(outstr)
        # go to last row of logical line
        self._text_screen.move_to_end()
        # echo the CR, if requested
        if write_endl:
            self.write_line()
        # to the parser/INPUT, only the first 255 chars are returned
        # with trailing whitespace removed
        return outstr[:255].rstrip(b' \t\n')

    def _interact(self, prompt_width, is_input=False):
        """Manage the interactive mode."""
        # force cursor visibility in all case
        self._cursor.set_override(True)
        self._io_streams.flush()
        try:
            # this is where we started
            start_row = self._text_screen.current_row
            furthest_left = 1 + prompt_width
            # this is where we arrow-keyed on the start line
            furthest_right = self._text_screen.current_col
            while True:
                # get one e-ASCII or dbcs code
                d = self._keyboard.get_fullchar_block()
                if not d:
                    # input stream closed
                    raise error.Exit()
                if d in (
                        ea.UP, ea.CTRL_6, ea.DOWN, ea.CTRL_MINUS,  ea.RIGHT, ea.CTRL_BACKSLASH,
                        ea.LEFT, ea.CTRL_RIGHTBRACKET, ea.HOME, ea.CTRL_k, ea.END, ea.CTRL_n
                    ):
                    # arrow keys drop us out of insert mode
                    self._set_overwrite_mode(True)
                if d == ea.CTRL_c:
                    # CTRL-C -- only caught here, not in wait_char like <CTRL+BREAK>
                    raise error.Break()
                elif d == b'\r':
                    # ENTER, CTRL+M
                    break
                elif d == b'\a':
                    # BEL, CTRL+G
                    self._sound.beep()
                elif d == b'\b':
                    # BACKSPACE, CTRL+H
                    self._text_screen.backspace(start_row, furthest_left)
                elif d == b'\t':
                    # TAB, CTRL+I
                    self._text_screen.tab(self._overwrite_mode)
                elif d == b'\n':
                    # CTRL+ENTER, CTRL+J
                    self._text_screen.line_feed()
                elif d == ea.ESCAPE:
                    # ESC, CTRL+[
                    logic_start = self._text_screen.find_start_of_line(self._text_screen.current_row)
                    if logic_start == start_row:
                        self._text_screen.clear_line(
                            logic_start, furthest_left, quirky_scrolling=is_input
                        )
                    else:
                        self._text_screen.clear_line(logic_start, 1)
                elif d in (ea.CTRL_END, ea.CTRL_e):
                    self._text_screen.clear_line(
                        self._text_screen.current_row, self._text_screen.current_col
                    )
                elif d in (ea.UP, ea.CTRL_6):
                    self._text_screen.up()
                elif d in (ea.DOWN, ea.CTRL_MINUS):
                    self._text_screen.down()
                elif d in (ea.RIGHT, ea.CTRL_BACKSLASH):
                    self._text_screen.incr_pos()
                elif d in (ea.LEFT, ea.CTRL_RIGHTBRACKET):
                    self._text_screen.decr_pos()
                elif d in (ea.CTRL_RIGHT, ea.CTRL_f):
                    self._text_screen.skip_word_right()
                elif d in (ea.CTRL_LEFT, ea.CTRL_b):
                    self._text_screen.skip_word_left()
                elif d in (ea.INSERT, ea.CTRL_r):
                    self._set_overwrite_mode(not self._overwrite_mode)
                elif d in (ea.DELETE, ea.CTRL_BACKSPACE):
                    self._text_screen.delete_fullchar()
                elif d in (ea.HOME, ea.CTRL_k):
                    self._text_screen.set_pos(1, 1)
                elif d in (ea.END, ea.CTRL_n):
                    self._text_screen.move_to_end()
                elif d in (ea.CTRL_HOME, ea.CTRL_l):
                    self._text_screen.clear_view()
                elif d == ea.CTRL_PRINT:
                    # ctrl+printscreen toggles printer copy
                    self._io_streams.toggle_echo(self._lpt1_file)
                else:
                    try:
                        # these are done on a less deep level than the fn key macros
                        letters = list(iterchar(ALT_KEY_REPLACE[d])) + [b' ']
                    except KeyError:
                        letters = [d]
                    for d in letters:
                        # ignore eascii by this point, but not dbcs
                        if d[:1] not in (b'\0', b'\r'):
                            if not self._overwrite_mode:
                                self._text_screen.insert_fullchars(d)
                            else:
                                # put all dbcs in before messing with cursor position
                                self._text_screen.write_chars(d, do_scroll_down=True)
                if self._text_screen.current_row == start_row:
                    furthest_left = min(self._text_screen.current_col, furthest_left)
                    furthest_right = max(self._text_screen.current_col, furthest_right)
                    if (
                            self._text_screen.current_col == self._text_screen.mode.width
                            and self._text_screen.overflow
                        ):
                        furthest_right += 1
        finally:
            self._set_overwrite_mode(True)
            # reset cursor visibility
            self._cursor.set_override(False)
        return start_row, furthest_left, furthest_right

    def _set_overwrite_mode(self, new_overwrite):
        """Set or unset the overwrite mode (INS)."""
        if new_overwrite != self._overwrite_mode:
            self._overwrite_mode = new_overwrite
            self._cursor.set_default_shape(new_overwrite)

    ##########################################################################
    # output

    def write(self, s, do_echo=True):
        """Write a string to the screen at the current position."""
        if not s:
            # don't disconnect line wrap if no output
            return
        if do_echo:
            # CR -> CRLF, CRLF -> CRLF LF
            self._io_streams.write(b''.join([(b'\r\n' if c == b'\r' else c) for c in iterchar(s)]))
        last = b''
        # if our line wrapped at the end before, it doesn't anymore
        self._text_screen.set_wrap(self.current_row, False)
        out_chars = []
        for c in iterchar(s):
            if c in b'\t\n\r\a\x0B\x0C\x1C\x1D\x1E\x1F':
                # non-printing or position-dependent chars, dump buffer first
                self._text_screen.write_chars(b''.join(out_chars), do_scroll_down=False)
                out_chars = []
                row, col = self.current_row, self.current_col
                if c == b'\t':
                    # TAB
                    num = (8 - (col - 1 - 8 * int((col-1) // 8)))
                    self._text_screen.write_chars(b' ' * num, do_scroll_down=False)
                elif c == b'\n' or c == b'\r':
                    # CR or LF
                    # note that a PRINTed LF chr$(10) does not cause a wrapped/connected line
                    # in contrast to a typed Ctrl+J
                    self._text_screen.newline(wrap=False)
                elif c == b'\a':
                    # BEL
                    self._sound.beep()
                elif c == b'\x0B':
                    # HOME
                    self._text_screen.set_pos(1, 1, scroll_ok=False)
                elif c == b'\x0C':
                    # CLS
                    self._text_screen.clear_view()
                elif c == b'\x1C':
                    # RIGHT
                    self._text_screen.set_pos(row, col + 1, scroll_ok=False)
                elif c == b'\x1D':
                    # LEFT
                    self._text_screen.set_pos(row, col - 1, scroll_ok=False)
                elif c == b'\x1E':
                    # UP
                    self._text_screen.set_pos(row - 1, col, scroll_ok=False)
                elif c == b'\x1F':
                    # DOWN
                    self._text_screen.set_pos(row + 1, col, scroll_ok=False)
            else:
                # includes \b, \0, and non-control chars
                out_chars.append(c)
            last = c
        self._text_screen.write_chars(b''.join(out_chars), do_scroll_down=False)

    def write_line(self, s=b'', do_echo=True):
        """Write a string to the screen and end with a newline."""
        self.write(b'%s\r' % (s,), do_echo)

    def list_line(self, line, newline):
        """Print a line from a program listing or EDIT prompt."""
        # no wrap if 80-column line, clear row before printing.
        # replace LF CR with LF
        line = line.replace(b'\n\r', b'\n')
        cuts = line.split(b'\n')
        for i, l in enumerate(cuts):
            if i > 0:
                # echo
                self._io_streams.write(b'\n')
                # when using LIST, we *do* print LF as a wrap
                self._text_screen.newline(wrap=True)
            self._text_screen.clear_line(self._text_screen.current_row, 1)
            self.write(l)
        if newline:
            self.write_line()
        # remove wrap after 80-column program line
        if len(line) == self.width and self._text_screen.current_row > 2:
            self._text_screen.set_wrap(self._text_screen.current_row-2, False)

    def start_line(self):
        """
        Move the cursor to the start of the next line, this line if empty.
        Used for prompt and error or break messages.
        """
        if self.current_col != 1:
            self._io_streams.write(b'\r\n')
            self._text_screen.set_pos(self._text_screen.current_row + 1, 1)
        # ensure line above doesn't wrap
        self._text_screen.set_wrap(self._text_screen.current_row-1, False)


    ##########################################################################
    # function key macros

    def key_(self, args):
        """KEY: show/hide/list macros."""
        command, = args
        if command == tk.ON:
            self._text_screen.show_bar(True)
        elif command == tk.OFF:
            self._text_screen.show_bar(False)
        elif command == tk.LIST:
            self._list_macros()

    def set_macro(self, num, macro):
        """Set macro for given function key."""
        if num > self._num_fn_keys:
            raise ValueError('Function key number out of range')
        # NUL terminates macro string, rest is ignored
        # macro starting with NUL is empty macro
        self._keyboard.set_macro(num, macro)
        self._update_bar()
        self._text_screen.redraw_bar()

    def _list_macros(self):
        """Print a list of the function key macros."""
        for i in range(self._num_fn_keys):
            text = self._keyboard.get_macro(i)
            text = b''.join(FKEY_MACRO_REPLACE_CHARS.get(s, s) for s in iterchar(text))
            self.write_line(b'F%d %s' % (i+1, text))

    def _update_bar(self):
        """Show/hide the function keys line on the active page."""
        macros = (
            self._keyboard.get_macro(_i)
            for _i in range(10)
        )
        descriptions = [
            b''.join(FKEY_MACRO_REPLACE_CHARS.get(_s, _s) for _s in iterchar(_macro[:6]))
            for _macro in macros
        ]
        self._text_screen.update_bar(descriptions)
