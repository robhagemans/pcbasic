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

import video
import plat
import unicodepage
import backend
import scancode
# ANSI escape codes for output, need arrow movements and clear line and esc_to_scan under Unix.
import ansi


###############################################################################

def prepare():
    """ Initialise the video_cli module. """
    video.plugin_dict['cli'] = VideoCLI


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


###############################################################################

class VideoCLI(video.VideoPlugin):
    """ Command-line interface. """

    def __init__(self):
        """ Initialise command-line interface. """
        if not plat.stdin_is_tty:
            logging.warning('Input device is not a terminal. '
                            'Could not initialise CLI interface.')
            self.ok = False
            return
        term_echo(False)
        sys.stdout.flush()
        # start the stdin thread for non-blocking reads
        self.input_handler = InputHandlerCLI()
        # cursor is visible
        self.cursor_visible = True
        # current row and column for cursor
        self.cursor_row = 1
        self.cursor_col = 1
        # last row and column printed on
        self.last_row = None
        self.last_col = None
        # text buffer
        self.num_pages = 1
        self.vpagenum, self.apagenum = 0, 0
        self.text = [[[' ']*80 for _ in range(25)]]
        video.VideoPlugin.__init__(self)

    def close(self):
        """ Close command-line interface. """
        video.VideoPlugin.close(self)
        if self.ok:
            self._update_position()
            term_echo()
        sys.stdout.flush()

    def _check_display(self):
        """ Display update cycle. """
        self._update_position()

    def _check_input(self):
        """ Handle keyboard events. """
        # s is one utf-8 sequence or one scancode
        # or a failed attempt at one of the above
        u8, sc = self.input_handler.get_key()
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


    ###############################################################################

    def put_glyph(self, pagenum, row, col, c, fore, back, blink, underline, for_keys):
        """ Put a single-byte character at a given position. """
        try:
            char = unicodepage.UTF8Converter().to_utf8(c)
        except KeyError:
            char = ' ' * len(c)
        self.text[pagenum][row-1][col-1] = char
        if len(c) > 1:
            self.text[pagenum][row-1][col] = ''
        if self.vpagenum != pagenum:
            return
        if for_keys:
            return
        self._update_position(row, col)
        sys.stdout.write(char)
        sys.stdout.flush()
        self.last_col += len(c)

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """
        self.cursor_row, self.cursor_col = crow, ccol

    def clear_rows(self, back_attr, start, stop):
        """ Clear screen rows. """
        self.text[self.apagenum][start-1:stop] = [
            [' ']*len(self.text[self.apagenum][0]) for _ in range(start-1, stop)]
        if (start <= self.cursor_row and stop >= self.cursor_row and
                    self.vpagenum == self.apagenum):
            # clear_line before update_position to avoid redrawing old lines on CLS
            sys.stdout.write(ansi.esc_clear_line)
            self._update_position(self.cursor_row, 1)
            sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height]
                + [[' ']*len(self.text[self.apagenum][0])])
        if self.vpagenum != self.apagenum:
            return
        sys.stdout.write('\r\n')
        sys.stdout.flush()

    def set_mode(self, mode_info):
        """ Initialise video mode """
        self.num_pages = mode_info.num_pages
        self.text = [[[' ']*mode_info.width for _ in range(mode_info.height)]
                                            for _ in range(self.num_pages)]

    def set_page(self, new_vpagenum, new_apagenum):
        """ Set visible and active page. """
        self.vpagenum, self.apagenum = new_vpagenum, new_apagenum
        self._redraw_row(self.cursor_row)

    def copy_page(self, src, dst):
        """ Copy screen pages. """
        self.text[dst] = [row[:] for row in self.text[src]]
        if dst == self.vpagenum:
            self._redraw_row(self.cursor_row)

    def _redraw_row(self, row):
        """ Draw the stored text in a row. """
        rowtext = ''.join(self.text[self.vpagenum][row-1])
        sys.stdout.write(rowtext)
        sys.stdout.write(ansi.esc_move_left*len(rowtext))
        sys.stdout.flush()

    def _update_position(self, row=None, col=None):
        """ Update screen for new cursor position. """
        # this happens on resume
        if self.last_row is None:
            self.last_row = self.cursor_row
            self._redraw_row(self.cursor_row)
        if self.last_col is None:
            self.last_col = self.cursor_col
        # allow updating without moving the cursor
        if row is None:
            row = self.cursor_row
        if col is None:
            col = self.cursor_col
        # move cursor if necessary
        if row != self.last_row:
            sys.stdout.write('\r\n')
            sys.stdout.flush()
            self.last_col = 1
            self.last_row = row
            # show what's on the line where we are.
            self._redraw_row(self.cursor_row)
        if col != self.last_col:
            sys.stdout.write(ansi.esc_move_left*(self.last_col-col))
            sys.stdout.write(ansi.esc_move_right*(col-self.last_col))
            sys.stdout.flush()
            self.last_col = col



###############################################################################

class InputHandlerCLI(object):
    """ Keyboard reader thread. """

    # Note that we use a separate thread implementation because:
    # * sys.stdin.read(1) is a blocking read
    # * we need this to work on Windows as well as Unix, so select() won't do.

    def __init__(self):
        """ Start the keyboard reader. """
        self._launch_thread()

    def _launch_thread(self):
        """ Start the keyboard reader thread. """
        self.stdin_q = Queue.Queue()
        t = threading.Thread(target=self._read_stdin)
        t.daemon = True
        t.start()

    def _read_stdin(self):
        """ Wait for stdin and put any input on the queue. """
        while True:
            self.stdin_q.put(sys.stdin.read(1))
            # don't be a hog
            time.sleep(0.0001)

    def _getc(self):
        """ Read character from keyboard, non-blocking. """
        try:
            return self.stdin_q.get_nowait()
        except Queue.Empty:
            return ''

    def get_key(self):
        """ Retrieve one scancode, or one UTF-8 sequence from keyboard. """
        s = self._getc()
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
            c = self._getc()
            cutoff += 1
            if c == '':
                continue
            more -= 1
            s += c
            if esc:
                try:
                    return None, ansi.esc_to_scan[s]
                except KeyError:
                    pass
        # convert into utf-8 if necessary
        if sys.stdin.encoding and sys.stdin.encoding != 'utf-8':
            return s.decode(sys.stdin.encoding).encode('utf-8'), None
        else:
            return s, None


prepare()
