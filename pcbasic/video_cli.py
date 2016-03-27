"""
PC-BASIC - video_cli.py
Command-line interface

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import time
import logging
import threading
import Queue

import interface as video
import plat
import backend
import scancode
import eascii
import ansi

encoding = sys.stdin.encoding or 'utf-8'

###############################################################################

def prepare():
    """ Initialise the video_cli module. """
    video.video_plugin_dict['cli'] = VideoCLI


###############################################################################

if plat.system == 'Windows':
    import ansipipe
    tty = ansipipe
    termios = ansipipe
    # Ctrl+Z to exit
    eof = eascii.CTRL_z
elif plat.system != 'Android':
    import tty, termios
    # Ctrl+D to exit
    eof = eascii.CTRL_d

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
    sys.stdout.flush()
    return previous


###############################################################################

class VideoCLI(video.VideoPlugin):
    """ Command-line interface. """

    def __init__(self, **kwargs):
        """ Initialise command-line interface. """
        if not plat.stdin_is_tty:
            logging.warning('Input device is not a terminal. '
                            'Could not initialise text-based interface.')
            raise video.InitFailed()
        # set codepage
        try:
            self.codepage = kwargs['codepage']
        except KeyError:
            logging.error('No codepage supplied to text-based interface.')
            raise video.InitFailed()
        video.VideoPlugin.__init__(self)
        term_echo(False)
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
        self.text = [[[u' ']*80 for _ in range(25)]]
        self.f12_active = False

    def close(self):
        """ Close command-line interface. """
        video.VideoPlugin.close(self)
        term_echo()
        if self.last_col and self.cursor_col != self.last_col:
            sys.stdout.write('\n')

    def _check_display(self):
        """ Display update cycle. """
        self._update_position()

    def _check_input(self):
        """ Handle keyboard events. """
        while True:
            # s is one unicode char or one scancode
            uc, sc = self.input_handler.get_key()
            if not uc and not sc:
                break
            if uc == eof:
                # ctrl-D (unix) / ctrl-Z (windows)
                backend.input_queue.put(backend.Event(backend.KEYB_QUIT))
            elif uc == u'\x7f':
                # backspace
                backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                        (eascii.BACKSPACE, scancode.BACKSPACE, [])))
            elif sc or uc:
                # check_full=False to allow pasting chunks of text
                backend.input_queue.put(backend.Event(
                                        backend.KEYB_DOWN, (uc, sc, [], False)))
                if sc == scancode.F12:
                    self.f12_active = True
                else:
                    backend.input_queue.put(backend.Event(
                                            backend.KEYB_UP, (scancode.F12,)))
                    self.f12_active = False

    ###############################################################################

    def put_glyph(self, pagenum, row, col, cp, is_fullwidth, fore, back, blink, underline, for_keys):
        """ Put a character at a given position. """
        char = self.codepage.to_unicode(cp, replace=u' ')
        if char == u'\0':
            char = u' '
        self.text[pagenum][row-1][col-1] = char
        if is_fullwidth:
            self.text[pagenum][row-1][col] = u''
        if self.vpagenum != pagenum:
            return
        if for_keys:
            return
        self._update_position(row, col)
        sys.stdout.write(char.encode(encoding, 'replace'))
        sys.stdout.flush()
        self.last_col += 2 if is_fullwidth else 1

    def move_cursor(self, crow, ccol):
        """ Move the cursor to a new position. """
        self.cursor_row, self.cursor_col = crow, ccol

    def clear_rows(self, back_attr, start, stop):
        """ Clear screen rows. """
        self.text[self.apagenum][start-1:stop] = [
            [u' ']*len(self.text[self.apagenum][0]) for _ in range(start-1, stop)]
        if (start <= self.cursor_row and stop >= self.cursor_row and
                    self.vpagenum == self.apagenum):
            self._update_position(self.cursor_row, 1)
            sys.stdout.write(ansi.esc_clear_line)
            sys.stdout.flush()

    def scroll_up(self, from_line, scroll_height, back_attr):
        """ Scroll the screen up between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                self.text[self.apagenum][from_line:scroll_height]
                + [[u' ']*len(self.text[self.apagenum][0])])
        if self.vpagenum != self.apagenum:
            return
        sys.stdout.write('\r\n')
        sys.stdout.flush()

    def scroll_down(self, from_line, scroll_height, back_attr):
        """ Scroll the screen down between from_line and scroll_height. """
        self.text[self.apagenum][from_line-1:scroll_height] = (
                [[u' ']*len(self.text[self.apagenum][0])] +
                self.text[self.apagenum][from_line-1:scroll_height-1])

    def set_mode(self, mode_info):
        """ Initialise video mode """
        self.num_pages = mode_info.num_pages
        self.text = [[[u' ']*mode_info.width for _ in range(mode_info.height)]
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
        rowtext = u''.join(self.text[self.vpagenum][row-1]).encode(encoding, 'replace')
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
        """ Retrieve one scancode sequence or one unicode char from keyboard. """
        s = self._getc()
        if s == '':
            return None, None
        # ansi sequences start with \x1b
        esc = (s == ansi.ESC)
        # escape sequences are at most 5 and UTF-8 at most 4 chars long
        more = 5
        cutoff = 100
        while (more > 0) and (cutoff > 0):
            if esc:
                # return the first recognised escape sequence
                uc = esc_to_eascii.get(s, '')
                scan = esc_to_scan.get(s, None)
                if uc or scan:
                    return uc, scan
            else:
                # return the first recognised encoding sequence
                try:
                    return s.decode(encoding), None
                except UnicodeDecodeError:
                    pass
            # give time for the queue to fill up
            time.sleep(0.0005)
            c = self._getc()
            cutoff -= 1
            if c == '':
                continue
            more -= 1
            s += c
        # no sequence or decodable string found
        # decode as good as it gets
        return s.decode(encoding, errors='replace'), None



# escape sequence to scancode dictionary
esc_to_scan = {
    ansi.F1: scancode.F1,
    ansi.F2: scancode.F2,
    ansi.F3: scancode.F3,
    ansi.F4: scancode.F4,
    ansi.F5: scancode.F5,
    ansi.F6: scancode.F6,
    ansi.F7: scancode.F7,
    ansi.F8: scancode.F8,
    ansi.F9: scancode.F9,
    ansi.F10: scancode.F10,
    ansi.F11: scancode.F11,
    ansi.F12: scancode.F12,
    ansi.END: scancode.END,
    ansi.END2: scancode.END,
    ansi.HOME: scancode.HOME,
    ansi.HOME2: scancode.HOME,
    ansi.UP: scancode.UP,
    ansi.DOWN: scancode.DOWN,
    ansi.RIGHT: scancode.RIGHT,
    ansi.LEFT: scancode.LEFT,
    ansi.INSERT: scancode.INSERT,
    ansi.DELETE: scancode.DELETE,
    ansi.PAGEUP: scancode.PAGEUP,
    ansi.PAGEDOWN: scancode.PAGEDOWN,
    }

esc_to_eascii = {
    ansi.F1: eascii.F1,
    ansi.F2: eascii.F2,
    ansi.F3: eascii.F3,
    ansi.F4: eascii.F4,
    ansi.F5: eascii.F5,
    ansi.F6: eascii.F6,
    ansi.F7: eascii.F7,
    ansi.F8: eascii.F8,
    ansi.F9: eascii.F9,
    ansi.F10: eascii.F10,
    ansi.F11: eascii.F11,
    ansi.F12: eascii.F12,
    ansi.END: eascii.END,
    ansi.END2: eascii.END,
    ansi.HOME: eascii.HOME,
    ansi.HOME2: eascii.HOME,
    ansi.UP: eascii.UP,
    ansi.DOWN: eascii.DOWN,
    ansi.RIGHT: eascii.RIGHT,
    ansi.LEFT: eascii.LEFT,
    ansi.INSERT: eascii.INSERT,
    ansi.DELETE: eascii.DELETE,
    ansi.PAGEUP: eascii.PAGEUP,
    ansi.PAGEDOWN: eascii.PAGEDOWN,
    }


prepare()
