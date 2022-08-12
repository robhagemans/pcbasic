"""
PC-BASIC - compat.posix_console
POSIX console support with ANSI escape sequences

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# pylint: disable=no-name-in-module

import os
import io
import sys
import tty
import time
import termios
import select
import fcntl
import array
import struct
import atexit
import locale
import logging
from collections import deque
from contextlib import contextmanager
try:
    import curses
except ImportError:
    curses = None

from .base import MACOS, PY2, HOME_DIR
from .streams import StdIOBase


# ANSI escape codes
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting
# http://www.termsys.demon.co.uk/vtansi.htm
# http://ascii-table.com/ansi-escape-sequences-vt-100.php
# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html


# ANSI escape sequences
# - these are supported by xterm, gnome-terminal
# - konsole and Terminal.app ignore the palette sequences
# - konsole (pre 18.08) breaks on the cursor shape sequence
# - Terminal.app ignores cursor shape but does not break
# - we use the delete/insert lines sequences rather than scroll as they are better supported
# unfortunately terminfo is spotty on cursor shape and palette functionality,
# plus most consoles claim to be xterm anyway

if os.getenv('TERM', default='').startswith('linux'):
    # linux framebuffer console
    ANSI_OVERRIDES = dict(
        # 1 invisible 2 line 3 third 4 half block 5 two thirds 6 full block
        # https://linuxgazette.net/137/anonymous.html
        _cursor_block = b'\x1b[?4c',
        _cursor_line = b'\x1b[?2c',
        _reset_cursor = b'\x1b[?0c',
    )
else:
    # xterm and family
    ANSI_OVERRIDES = dict(
        # 1 blinking block 2 block 3 blinking line 4 line
        _cursor_block = b'\x1b[1 q', # Ss 1 ?
        _cursor_line = b'\x1b[3 q', # Ss 3 ?
        # reset colour and shape
        _reset_cursor = b'\x1b]112\a\x1b[1 q',
        # follow the format of initc
        # Cs ?
        _cursor_color = b'\x1b]12;#%p1%{255}%*%{1000}%/%2.2X%p2%{255}%*%{1000}%/%2.2X%p3%{255}%*%{1000}%/%2.2X\a',
        # window properties
        _resize = b'\x1b[8;%p1%d;%p2%d;t', ## ?
        # status line (caption)
        tsl = b'\x1b]2;',
        fsl = b'\a',
    )


# input key codes
###################################################################################################

# terminfo has only a few keycodes
# fortunately we can just include all codes for all systems
# as there are no conflicting definitions

# xterm keys that support modifiers
_MOD_PATTERNS = {
    u'\x1b[11%s~': 'F1',
    u'\x1b[12%s~': 'F2',
    u'\x1b[13%s~': 'F3',
    u'\x1b[14%s~': 'F4',
    u'\x1b[15%s~': 'F5',
    u'\x1b[17%s~': 'F6',
    u'\x1b[18%s~': 'F7',
    u'\x1b[19%s~': 'F8',
    u'\x1b[20%s~': 'F9',
    u'\x1b[21%s~': 'F10',
    u'\x1b[23%s~': 'F11',
    u'\x1b[24%s~': 'F12',
    u'\x1b[1%sF': 'END',
    u'\x1b[1%sH': 'HOME',
    u'\x1b[1%sA': 'UP',
    u'\x1b[1%sB': 'DOWN',
    u'\x1b[1%sC': 'RIGHT',
    u'\x1b[1%sD': 'LEFT',
    u'\x1b[2%s~': 'INSERT',
    u'\x1b[3%s~': 'DELETE',
    u'\x1b[5%s~': 'PAGEUP',
    u'\x1b[6%s~': 'PAGEDOWN',
}

# xterm modifier codes
_MOD_CODES = {
    u'': set(),
    u';2': {'SHIFT'},
    u';3': {'ALT'},
    u';4': {'SHIFT', 'ALT'},
    u';5': {'CTRL'},
    u';6': {'SHIFT', 'CTRL'},
    u':7': {'CTRL', 'ALT'},
    u';8': {'SHIFT', 'CTRL', 'ALT'},
}

# construct ansi to output mapping for xterm codes
ANSI_TO_KEYMOD = {
    pattern % (modcode,): (key, mods)
    for modcode, mods in _MOD_CODES.items()
    for pattern, key in _MOD_PATTERNS.items()
}

# unmodified keys
_UNMOD_KEYS = {
    # used by the linux framebuffer console
    # also, \e[25~ is shift+F1, etc
    u'\x1b[[A': 'F1',
    u'\x1b[[B': 'F2',
    u'\x1b[[C': 'F3',
    u'\x1b[[D': 'F4',
    u'\x1b[[E': 'F5',
    u'\x1b[4~': 'END',
    u'\x1b[1~': 'HOME',
    # CSI-based key codes (without the number 1)
    u'\x1b[F': 'END',
    u'\x1b[H': 'HOME',
    u'\x1b[A': 'UP',
    u'\x1b[B': 'DOWN',
    u'\x1b[C': 'RIGHT',
    u'\x1b[D': 'LEFT',
    # SS3-based key codes (used by xterm in smkx mode)
    u'\x1bOP': 'F1',
    u'\x1bOQ': 'F2',
    u'\x1bOR': 'F3',
    u'\x1bOS': 'F4',
    u'\x1bOF': 'END',
    u'\x1bOH': 'HOME',
    u'\x1bOA': 'UP',
    u'\x1bOB': 'DOWN',
    u'\x1bOC': 'RIGHT',
    u'\x1bOD': 'LEFT',
}
ANSI_TO_KEYMOD.update({sequence: (key, set()) for sequence, key in _UNMOD_KEYS.items()})

# shifted keys
_SHIFT_KEYS = {
    # shifted F-keys used by the linux framebuffer console
    u'\x1b[25~': 'F1',
    u'\x1b[26~': 'F2',
    u'\x1b[28~': 'F3',
    u'\x1b[29~': 'F4',
    u'\x1b[31~': 'F5',
    u'\x1b[32~': 'F6',
    u'\x1b[33~': 'F7',
    u'\x1b[34~': 'F8',
    # xterm shift+TAB
    u'\x1b[[Z': 'TAB',
}
ANSI_TO_KEYMOD.update({sequence: (key, {'SHIFT'}) for sequence, key in _SHIFT_KEYS.items()})

# keypad codes with numlock off
# arrow keys, ins, del etc already included
# u'\x1bOE': keypad 5
# u'\x1bOM': keypad Enter
# u'\x1bOk': keypad +
# u'\x1bOm': keypad -
# u'\x1bOj': keypad *
# u'\x1bOo': keypad /

# esc + char means alt+key; lowercase
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c + 32,): (chr(c + 32), {'ALT'}) for c in range(65, 91)})
# uppercase
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c + 32), {'ALT', 'SHIFT'}) for c in range(65, 91)})
# digits, controls & everything else
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c), {'ALT'}) for c in range(0, 65)})
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c), {'ALT'}) for c in range(91, 128)})


# colour palettes
###################################################################################################

# mapping of the first 8 attributes of the default CGA palette
# so that non-RGB terminals use sensible colours
# black, blue, green, cyan, red, magenta, yellow, white
EGA_TO_ANSI = (0, 4, 2, 6, 1, 5, 3, 7)

# default palette - these are in fact the 16 CGA colours
# this gets overwritten anyway
DEFAULT_PALETTE = (
    (0x00, 0x00, 0x00), (0x00, 0x00, 0xaa), (0x00, 0xaa, 0x00), (0x00, 0xaa, 0xaa),
    (0xaa, 0x00, 0x00), (0xaa, 0x00, 0xaa), (0xaa, 0x55, 0x00), (0xaa, 0xaa, 0xaa),
    (0x55, 0x55, 0x55), (0x55, 0x55, 0xff), (0x55, 0xff, 0x55), (0x55, 0xff, 0xff),
    (0xff, 0x55, 0x55), (0xff, 0x55, 0xff), (0xff, 0xff, 0x55), (0xff, 0xff, 0xff)
)


# implementation
###################################################################################################


class StdIO(StdIOBase):
    """Holds standard unicode streams."""

    if PY2: # pragma: no cover
        def _attach_stdin(self):
            self.stdin = self._wrap_input_stream(sys.stdin)

        def _attach_output_stream(self, stream_name, redirected=False):
            stream = getattr(sys, '__%s__' % (stream_name,))
            new_stream = self._wrap_output_stream(stream)
            setattr(self, stream_name, new_stream)

stdio = StdIO()


def init_stdio():
    """Platform-specific initialisation."""
    # set locale - this is necessary for curses and *maybe* for clipboard handling
    # there's only one locale setting so best to do it all upfront here
    # NOTE that this affects str.upper() etc.
    # don't do this on Windows as it makes the console codepage different from the stdout encoding ?
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error as e:
        # mis-configured locale can throw an error here, no need to crash
        logging.error(e)


# output buffer for ioctl call
_sock_size = array.array('i', [0])


class PosixConsole(object):
    """POSIX-based console implementation."""

    def __init__(self):
        """Set up the console."""
        # buffer to save termios state
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise EnvironmentError('Not a terminal')
        self._term_attr = termios.tcgetattr(sys.stdin.fileno())
        # preserve original terminal size
        self._orig_size = self.get_size()
        self._height, _ = self._orig_size
        # input buffer
        self._read_buffer = deque()
        # palette
        self._palette = list(DEFAULT_PALETTE)
        # needed to access curses.tiget* functions
        if curses:
            curses.setupterm()
        self._muffle = None

    ##########################################################################
    # terminal modes

    def get_size(self):
        """Get terminal size."""
        try:
            return struct.unpack(
                'HHHH', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0'*8)
            )[:2]
        except Exception:
            return 25, 80

    def set_raw(self):
        """Enter raw terminal mode (no echo, don't exit on ctrl-C, ...)."""
        tty.setraw(sys.stdin.fileno())

    def unset_raw(self):
        """Leave raw terminal mode."""
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._term_attr)


    ##########################################################################
    # ansi output

    def start_screen(self):
        """Enter full-screen/application mode."""
        # suppress stderr to avoid log messages defacing the application screen
        self._muffle = stdio.pause('stderr')
        self._muffle.__enter__()  # pylint: disable=no-member
        self.set_raw()
        # switch to alternate buffer
        self._emit_ti('smcup')
        # set application keypad / keypad transmit mode
        self._emit_ti('smkx')

    def close_screen(self):
        """Leave full-screen/application mode."""
        self.reset()
        self._emit_ti('rmkx')
        if not self._emit_ti('rmcup'):
            self._emit_ti('clear')
        self.unset_raw()
        if self._muffle is not None:
            self._muffle.__exit__(None, None, None)  # pylint: disable=no-member

    def reset(self):
        """Reset to defaults."""
        self._emit_ti('oc')
        self._emit_ti('op')
        self._emit_ti('sgr0')
        self._emit_ti('cnorm')
        self._emit_ti('_reset_cursor')
        self._emit_ti('_resize', *self._orig_size)

    def write(self, unicode_str):
        """Write (unicode) text to console."""
        stdio.stdout.write(unicode_str)
        stdio.stdout.flush()

    def _emit_ti(self, capability, *args):
        """Emit escape code."""
        if not curses:
            return False
        try:
            pattern = ANSI_OVERRIDES[capability]
        except KeyError:
            pattern = curses.tigetstr(capability)
        if pattern:
            ansistr = curses.tparm(pattern, *args).decode('ascii')
            stdio.stdout.write(ansistr)
            stdio.stdout.flush()
            return True
        return False

    def set_caption(self, caption):
        """Set terminal caption."""
        if self._emit_ti('tsl'):
            stdio.stdout.write(caption)
            self._emit_ti('fsl')

    def resize(self, height, width):
        """Resize terminal."""
        self._emit_ti('_resize', height, width)
        self._height = height
        # start below the current output
        self.clear()

    def clear(self):
        """Clear the screen and home the cursor."""
        self._emit_ti('clear')

    def clear_row(self, width=None):
        """Clear the current row."""
        if width is None:
            self._emit_ti('cr')
            self._emit_ti('el')
        else:
            self._emit_ti('sc')
            self._emit_ti('hpa', width-1)
            self._emit_ti('el1')
            self._emit_ti('rc')

    def show_cursor(self, block=False):
        """Show the cursor."""
        self._emit_ti('cnorm')
        if block:
            self._emit_ti('_cursor_block')
        else:
            self._emit_ti('_cursor_line')

    def hide_cursor(self):
        """Hide the cursor."""
        self._emit_ti('civis')

    def move_cursor_to(self, row, col):
        """Move cursor to a new position."""
        self._emit_ti('hpa', col-1)
        self._emit_ti('vpa', row-1)

    def scroll(self, top, bottom, rows):
        """Scroll the region between top and bottom one row up (-) or down (+)."""
        if bottom > top:
            self._emit_ti('csr', top-1, bottom-1)
            self._emit_ti('hpa', 0)
            self._emit_ti('vpa', top-1)
            if rows < 0:
                self._emit_ti('dl', -rows)
            elif rows > 0:
                self._emit_ti('il', rows)
            self._emit_ti('csr', 0, self._height-1)

    def set_cursor_colour(self, colour):
        """Set the current cursor colour attribute."""
        try:
            red, green, blue = self._palette[colour]
            self._emit_ti('_cursor_color', (red*1000)//255, (green*1000)//255, (blue*1000)//255)
        except KeyError:
            pass

    def set_attributes(self, fore, back, blink, underline):
        """Set current attributes."""
        # use "bold" ANSI colours for the upper 8 EGA attributes
        self._emit_ti('sgr0')
        self._emit_ti('setaf', 8 * (fore // 8) + EGA_TO_ANSI[fore % 8])
        self._emit_ti('setab', EGA_TO_ANSI[back])
        if blink:
            self._emit_ti('blink')
        if underline:
            self._emit_ti('smul')

    def set_palette_entry(self, attr, red, green, blue):
        """Set palette entry for attribute (0--16)."""
        # keep a record, mainly for cursor colours
        self._palette[attr] = red, green, blue
        # set the ANSI palette
        ansi_attr = 8*(attr//8) + EGA_TO_ANSI[attr%8]
        self._emit_ti('initc', ansi_attr, (red*1000)//255, (green*1000)//255, (blue*1000)//255)

    ##########################################################################
    # input

    def key_pressed(self):
        """Return whether a character is ready to be read from the keyboard."""
        return select.select([sys.stdin], [], [], 0)[0] != []

    def read_key(self):
        """
        Read keypress from console. Non-blocking.
        Returns tuple (unicode, keycode, set of mods)
        """
        sequence = read_all_available(stdio.stdin)
        if sequence is None:
            # stream closed, send ctrl-d
            return u'\x04', 'd', {'CTRL'}
        elif not sequence:
            return u'', None, set()
        # ansi sequences start with ESC (\x1b), but let ESC by itself through
        if len(sequence) > 1 and sequence[0] == u'\x1b':
            # drop unrecognised sequences
            key, mod = ANSI_TO_KEYMOD.get(sequence, (u'', ()))
            return u'', key, mod
        else:
            return sequence, None, set()


def _is_console_app():
    """To see if we are a console app, check if we can treat stdin like a tty, file or socket."""
    if not sys.stdin.isatty():
        try:
            fcntl.ioctl(sys.stdin, termios.FIONREAD, _sock_size)
        except EnvironmentError:
            # maybe /dev/null, but not a real file or console
            return False
    return True

IS_CONSOLE_APP = _is_console_app()

try:
    console = PosixConsole()
except EnvironmentError:
    console = None


# don't crash into raw terminal
def _atexit_unset_raw():
    try:
        console.unset_raw()
    except Exception:
        pass
atexit.register(_atexit_unset_raw)


def read_all_available(stream):
    """Read all available bytes or unicode from a stream; nonblocking; None if closed."""
    try:
        # select: check if buffer has characters/lines to read
        # NOTE - select call works for files & sockets & character devices on unix; sockets only on Windows
        has_bytes_available = select.select([stream], [], [], 0)[0]
    except io.UnsupportedOperation:
        # select needs an actual file or socket that has a fileno, BytesIO, StringIO etc not supported
        return stream.read() or None
    try:
        # select gives bytes counts for unicode streams which is pretty useless
        # so if provided with a unicode stream, take the buffer and decode back to unicode ourselves
        encoding = stream.encoding
        stream = stream.buffer
    except AttributeError as exception:
        encoding = None
        # we might still have a unicode stream it just doesn't have the attributes
        # raise an error here, otherwise we might try to read too many chars and block later
        # we need to check type as b'' == u'' in python2
        if type(stream.read(0)) == type(u''):
            raise TypeError(
                "Can't perform non-blocking read from this text stream: %s"
                % (exception,)
            )
    if not has_bytes_available:
        # nothing currently available to read.
        # return an empty of the type the stream produces.
        # fingers crossed this also works in Python 2
        return stream.read(0)
    # find number of bytes available (this always returns a count of *bytes*)
    fcntl.ioctl(stream, termios.FIONREAD, _sock_size)
    count = _sock_size[0]
    # and read them all
    # note that count should not be zero unless the stream is closed
    # or the select call would have failed above. if we read nothing, the stream has closed.
    c = stream.read(count)
    if not c:
        # report that stream has closed
        return None
    # if we were provided with a unicode stream *and* managed to get its buffer, convert back
    if encoding:
        return c.decode(encoding, 'replace')
    return c
