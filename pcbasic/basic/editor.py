"""
PC-BASIC - editor.py
Direct mode environment

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

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

    def __init__(self, screen, keyboard, sound, output_redirection, lpt1_file):
        """Initialise environment."""
        # overwrite mode (instead of insert)
        self._overwrite_mode = True
        self._screen = screen
        self._sound = sound
        self._keyboard = keyboard
        self._redirect = output_redirection
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
            self._redirect.write('\x0e')
            # while only a line break appears on the console
            self._screen.write_line()
            raise
        # get contents of the logical line
        if from_start:
            outstr = self._get_logical_line(self._screen.current_row)
        else:
            outstr = self._get_logical_line_input(self._screen.current_row,
                                            prompt_row, left, right)
        # redirects output exactly the contents of the logical line
        # including any trailing whitespace and chars past 255
        self._redirect.write(outstr)
        # go to last row of logical line
        self._screen.current_row = self._find_end_of_line(self._screen.current_row)
        # echo the CR, if requested
        if write_endl:
            self._screen.write_line()
        # to the parser/INPUT, only the first 255 chars are returned
        # with trailing whitespace removed
        return str(outstr[:255].rstrip(' \t\n'))

    def _find_start_of_line(self, srow):
        """Find the start of the logical line that includes our current position."""
        # move up as long as previous line wraps
        while srow > 1 and self._screen.apage.row[srow-2].wrap:
            srow -= 1
        return srow

    def _find_end_of_line(self, srow):
        """Find the end of the logical line that includes our current position."""
        # move down as long as this line wraps
        while srow <= self._screen.mode.height and self._screen.apage.row[srow-1].wrap:
            srow += 1
        return srow

    def _get_logical_line(self, srow):
        """Get bytearray of the contents of the logical line."""
        # find start of logical line
        srow = self._find_start_of_line(srow)
        line = bytearray()
        # add all rows of the logical line
        for therow in self._screen.apage.row[
                                    srow-1:self._screen.mode.height]:
            line += bytearray(pair[0] for pair in therow.buf[:therow.end])
            # continue so long as the line wraps
            if not therow.wrap:
                break
            # wrap before end of line means LF
            if therow.end < self._screen.mode.width:
                line += '\n'
        return line

    def _get_logical_line_input(self, srow, prompt_row, left, right):
        """Get bytearray of the contents of the logical line, adapted for INPUT."""
        # INPUT: the prompt starts at the beginning of a logical line
        # but the row may have moved up: this happens on line 24
        # in this case we need to move up to the start of the logical line
        prompt_row = self._find_start_of_line(prompt_row)
        # find start of logical line
        srow = self._find_start_of_line(srow)
        line = bytearray()
        # INPUT returns empty string if enter pressed below prompt row
        if srow <= prompt_row:
            # add all rows of the logical line
            for crow in range(srow, self._screen.mode.height+1):
                therow = self._screen.apage.row[crow-1]
                # exclude prompt, if any; only go from furthest_left to furthest_right
                if crow == prompt_row:
                    rowpairs = therow.buf[:therow.end][left-1:right-1]
                else:
                    rowpairs = therow.buf[:therow.end]
                # get characters from char/attr pairs and convert to bytearray
                line += bytearray(pair[0] for pair in rowpairs)
                if not therow.wrap:
                    break
                # wrap before end of line means LF
                if therow.end < self._screen.mode.width:
                    line += '\n'
        return line

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
                # wait_char returns one e-ASCII code
                d = self._keyboard.get_char_block()
                # insert dbcs chars from keyboard buffer two bytes at a time
                if (d in self._keyboard.codepage.lead and
                        self._keyboard.buf.peek() in self._keyboard.codepage.trail):
                    d += self._keyboard.buf.getc()
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
                    self.line_feed()
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
                    # RIGHT, CTRL+\
                    # skip dbcs trail byte
                    if self._screen.apage.row[row-1].double[col-1] == 1:
                        self._screen.set_pos(row, col + 2, scroll_ok=False)
                    else:
                        self._screen.set_pos(row, col + 1, scroll_ok=False)
                elif d in (ea.LEFT, ea.CTRL_RIGHTBRACKET):
                    # LEFT, CTRL+]
                    self._screen.set_pos(row, col - 1, scroll_ok=False)
                elif d in (ea.CTRL_RIGHT, ea.CTRL_f):
                    self.skip_word_right()
                elif d in (ea.CTRL_LEFT, ea.CTRL_b):
                    self.skip_word_left()
                elif d in (ea.INSERT, ea.CTRL_r):
                    self.set_overwrite_mode(not self._overwrite_mode)
                elif d in (ea.DELETE, ea.CTRL_BACKSPACE):
                    self.delete(row, col)
                elif d in (ea.HOME, ea.CTRL_k):
                    self._screen.set_pos(1, 1)
                elif d in (ea.END, ea.CTRL_n):
                    self.end()
                elif d in (ea.CTRL_HOME, ea.CTRL_l):
                    self._screen.clear_view()
                elif d == ea.CTRL_PRINT:
                    # ctrl+printscreen toggles printer copy
                    self._redirect.toggle_echo(self._lpt1_file)
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
                                for c in d:
                                    self.insert(self._screen.current_row, col, c, self._screen.attr)
                                    col += 1
                                # row and col have changed
                                self._screen.redraw_row(
                                        self._screen.current_col-1, self._screen.current_row)
                                self._screen.set_pos(self._screen.current_row,
                                        self._screen.current_col + len(d))
                            else:
                                # put all dbcs in before messing with cursor position
                                for c in d:
                                    self._screen.write_char(c, do_scroll_down=True)
                # move left if we end up on dbcs trail byte
                row, col = self._screen.current_row, self._screen.current_col
                if self._screen.apage.row[row-1].double[col-1] == 2:
                    self._screen.set_pos(row, col-1, scroll_ok=False)
                # adjust cursor width
                row, col = self._screen.current_row, self._screen.current_col
                if self._screen.apage.row[row-1].double[col-1] == 1:
                    self._screen.cursor.set_width(2)
                else:
                    self._screen.cursor.set_width(1)
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

    def insert(self, crow, ccol, c, cattr):
        """Insert a single byte at the current position."""
        while True:
            therow = self._screen.apage.row[crow-1]
            therow.buf.insert(ccol-1, (c, cattr))
            if therow.end < self._screen.mode.width:
                therow.buf.pop()
                if therow.end > ccol-1:
                    therow.end += 1
                else:
                    therow.end = ccol
                break
            else:
                if crow == self._screen.scroll_height:
                    self._screen.scroll()
                    # this is not the global row which is changed by scroll()
                    crow -= 1
                if not therow.wrap and crow < self._screen.mode.height:
                    self._screen.scroll_down(crow+1)
                    therow.wrap = True
                c, cattr = therow.buf.pop()
                crow += 1
                ccol = 1

    def delete(self, crow, ccol):
        """Delete the character (single/double width) at the current position."""
        double = self._screen.apage.row[crow-1].double[ccol-1]
        if double == 0:
            # we're on an sbcs byte.
            self._delete_sbcs_char(crow, ccol)
        elif double == 1:
            # we're on a lead byte, delete this and the next.
            self._delete_sbcs_char(crow, ccol)
            self._delete_sbcs_char(crow, ccol)
        elif double == 2:
            # we're on a trail byte, delete the previous and this.
            self._delete_sbcs_char(crow, ccol-1)
            self._delete_sbcs_char(crow, ccol-1)

    def _delete_sbcs_char(self, crow, ccol):
        """Delete a single-byte character at the current position."""
        save_col = ccol
        thepage = self._screen.apage
        therow = thepage.row[crow-1]
        width = self._screen.mode.width
        if crow > 1 and ccol >= therow.end and therow.wrap:
            # row was an LF-ending row & we're deleting past the LF
            nextrow = thepage.row[crow]
            # replace everything after the delete location with
            # stuff from the next row
            therow.buf[ccol-1:] = nextrow.buf[:width-ccol+1]
            therow.end = min(max(therow.end, ccol) + nextrow.end, width)
            # and continue on the following rows as long as we wrap.
            while crow < self._screen.scroll_height and nextrow.wrap:
                nextrow2 = thepage.row[crow+1]
                nextrow.buf = (nextrow.buf[width-ccol+1:] +
                               nextrow2.buf[:width-ccol+1])
                nextrow.end = min(nextrow.end + nextrow2.end, width)
                crow += 1
                therow, nextrow = thepage.row[crow-1], thepage.row[crow]
            # replenish last row with empty space
            nextrow.buf = (nextrow.buf[width-ccol+1:] +
                           [(' ', self._screen.attr)] * (width-ccol+1))
            # adjust the row end
            nextrow.end -= width - ccol
            # redraw the full logical line from the original position onwards
            self._screen.redraw_row(save_col-1, self._screen.current_row)
            # if last row was empty, scroll up.
            if nextrow.end <= 0:
                nextrow.end = 0
                ccol += 1
                therow.wrap = False
                self._screen.scroll(crow+1)
        elif ccol <= therow.end:
            # row not ending with LF
            while True:
                if (therow.end < width or crow == self._screen.scroll_height
                        or not therow.wrap):
                    # no knock on to next row, just delete the char
                    del therow.buf[ccol-1]
                    # and replenish the buffer at the end of the line
                    therow.buf.insert(therow.end-1, (' ', self._screen.attr))
                    break
                else:
                    # wrap and end[row-1]==width
                    nextrow = thepage.row[crow]
                    # delete the char and replenish from next row
                    del therow.buf[ccol-1]
                    therow.buf.insert(therow.end-1, nextrow.buf[0])
                    # then move on to the next row and delete the first char
                    crow += 1
                    therow, nextrow = thepage.row[crow-1], thepage.row[crow]
                    ccol = 1
            # redraw the full logical line
            # this works from *global* row onwards
            self._screen.redraw_row(save_col-1, self._screen.current_row)
            # change the row end
            # this works on *local* row (last row edited)
            if therow.end > 0:
                therow.end -= 1
            else:
                # if there was nothing on the line, scroll the next line up.
                self._screen.scroll(crow)
                if crow > 1:
                    thepage.row[crow-2].wrap = False

    def clear_line(self, the_row, from_col=1):
        """Clear whole logical line (ESC), leaving prompt."""
        self._screen.clear_from(self._find_start_of_line(the_row), from_col)

    def backspace(self, start_row, start_col):
        """Delete the char to the left (BACKSPACE)."""
        crow, ccol = self._screen.current_row, self._screen.current_col
        # don't backspace through prompt
        if ccol == 1:
            if crow > 1 and self._screen.apage.row[crow-2].wrap:
                ccol = self._screen.mode.width
                crow -= 1
        elif ccol != start_col or self._screen.current_row != start_row:
            ccol -= 1
        self._screen.set_pos(crow, max(1, ccol))
        if self._screen.apage.row[self._screen.current_row-1].double[self._screen.current_col-1] == 2:
            # we're on a trail byte, move to the lead
            self._screen.set_pos(self._screen.current_row, self._screen.current_col-1)
        self.delete(crow, ccol)

    def tab(self):
        """Jump to next 8-position tab stop (TAB)."""
        row, col = self._screen.current_row, self._screen.current_col
        newcol = 9 + 8 * int((col-1) / 8)
        if self._overwrite_mode:
            self._screen.set_pos(row, newcol, scroll_ok=False)
        else:
            for _ in range(8):
                self.insert(row, col, ' ', self._screen.attr)
            self._screen.redraw_row(col - 1, row)
            self._screen.set_pos(row, newcol)

    def end(self):
        """Jump to end of logical line; follow wraps (END)."""
        crow = self._screen.current_row
        while (self._screen.apage.row[crow-1].wrap and
                crow < self._screen.mode.height):
            crow += 1
        if self._screen.apage.row[crow-1].end == self._screen.mode.width:
            self._screen.set_pos(crow, self._screen.apage.row[crow-1].end)
            self._screen.overflow = True
        else:
            self._screen.set_pos(crow, self._screen.apage.row[crow-1].end+1)

    def line_feed(self):
        """Move the remainder of the line to the next row and wrap (LF)."""
        crow, ccol = self._screen.current_row, self._screen.current_col
        if ccol < self._screen.apage.row[crow-1].end:
            for _ in range(self._screen.mode.width - ccol + 1):
                self.insert(crow, ccol, ' ', self._screen.attr)
            self._screen.redraw_row(ccol - 1, crow)
            self._screen.apage.row[crow-1].end = ccol - 1
        else:
            while (self._screen.apage.row[crow-1].wrap and
                    crow < self._screen.scroll_height):
                crow += 1
            if crow >= self._screen.scroll_height:
                self._screen.scroll()
            # self._screen.current_row has changed, don't use crow
            if self._screen.current_row < self._screen.mode.height:
                self._screen.scroll_down(self._screen.current_row+1)
        # LF connects lines like word wrap
        self._screen.apage.row[self._screen.current_row-1].wrap = True
        self._screen.set_pos(self._screen.current_row+1, 1)

    def skip_word_right(self):
        """Skip one word to the right (CTRL+RIGHT)."""
        crow, ccol = self._screen.current_row, self._screen.current_col
        # find non-alphanumeric chars
        while True:
            c = self._screen.apage.row[crow-1].buf[ccol-1][0]
            if (c not in string.digits + string.ascii_letters):
                break
            ccol += 1
            if ccol > self._screen.mode.width:
                if crow >= self._screen.scroll_height:
                    # nothing found
                    return
                crow += 1
                ccol = 1
        # find alphanumeric chars
        while True:
            c = self._screen.apage.row[crow-1].buf[ccol-1][0]
            if (c in string.digits + string.ascii_letters):
                break
            ccol += 1
            if ccol > self._screen.mode.width:
                if crow >= self._screen.scroll_height:
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
                if crow <= self._screen.view_start:
                    # not found
                    return
                crow -= 1
                ccol = self._screen.mode.width
            c = self._screen.apage.row[crow-1].buf[ccol-1][0]
            if (c in string.digits + string.ascii_letters):
                break
        # find non-alphanumeric chars
        while True:
            last_row, last_col = crow, ccol
            ccol -= 1
            if ccol < 1:
                if crow <= self._screen.view_start:
                    break
                crow -= 1
                ccol = self._screen.mode.width
            c = self._screen.apage.row[crow-1].buf[ccol-1][0]
            if (c not in string.digits + string.ascii_letters):
                break
        self._screen.set_pos(last_row, last_col)
