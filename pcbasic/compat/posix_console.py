"""
PC-BASIC - compat.posix_console
POSIX console support with ANSI escape sequences

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# pylint: disable=no-name-in-module

import os
import sys
import tty
import time
import termios
import select
import fcntl
import array
import struct
import atexit
from collections import deque
try:
    import curses
except Exception:
    curses = None

from .base import MACOS, PY2, HOME_DIR, wrap_input_stream, wrap_output_stream

if PY2:
    from .python2 import SimpleNamespace
else:
    from types import SimpleNamespace


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
ANSI = SimpleNamespace(
    # 1 blinking block 2 block 3 blinking line 4 line
    SET_CURSOR_BLOCK = u'\x1B[1 q', # Ss 1 ?
    SET_CURSOR_LINE = u'\x1B[3 q', # Ss 3 ?
    SET_CURSOR_COLOUR = u'\x1B]12;#%02x%02x%02x\a', # Cs ?
    # window properties
    RESIZE_TERM = u'\x1B[8;%i;%i;t', ## ?
    SET_TITLE = u'\x1B]2;%s\a', ## ?
)

# overrides for the linux framebuffer console
if os.getenv('TERM').startswith('linux'):
    # 1 invisible 2 line 3 third 4 half block 5 two thirds 6 full block
    ANSI.SET_CURSOR_BLOCK = u'\x1B[?4c'
    ANSI.SET_CURSOR_LINE = u'\x1B[?2c'


# ANSI base key codes
BASE_KEYS = dict(
    F1 = u'\x1B[11~',
    F2 = u'\x1B[12~',
    F3 = u'\x1B[13~',
    F4 = u'\x1B[14~',
    F5 = u'\x1B[15~',
    F6 = u'\x1B[17~',
    F7 = u'\x1B[18~',
    F8 = u'\x1B[19~',
    F9 = u'\x1B[20~',
    F10 = u'\x1B[21~',
    F11 = u'\x1B[23~',
    F12 = u'\x1B[24~',
    END = u'\x1B[1F',
    HOME = u'\x1B[1H',
    UP = u'\x1B[1A',
    DOWN = u'\x1B[1B',
    RIGHT = u'\x1B[1C',
    LEFT = u'\x1B[1D',
    INSERT = u'\x1B[2~',
    DELETE = u'\x1B[3~',
    PAGEUP = u'\x1B[5~',
    PAGEDOWN = u'\x1B[6~',
)

# CSI-based key codes
CSI_KEYS = dict(
    END = u'\x1B[F',
    HOME = u'\x1B[H',
    UP = u'\x1B[A',
    DOWN = u'\x1B[B',
    RIGHT = u'\x1B[C',
    LEFT = u'\x1B[D',
)

# SS3-based key codes
SS3_KEYS = dict(
    F1 = u'\x1BOP',
    F2 = u'\x1BOQ',
    F3 = u'\x1BOR',
    F4 = u'\x1BOS',
    END = u'\x1BOF',
    HOME = u'\x1BOH',
)

def _mod_csi(number):
    """Generate dict of modified CSI key sequences."""
    return {
        key: sequence[:-1] + u';%d' % (number,) + sequence[-1]
        for key, sequence in BASE_KEYS.items()
    }

# modified key codes
MOD_KEYS = {
    ('SHIFT',): _mod_csi(2),
    ('ALT',): _mod_csi(3),
    ('SHIFT', 'ALT'): _mod_csi(4),
    ('CTRL',): _mod_csi(5),
    ('SHIFT', 'CTRL'): _mod_csi(6),
    ('CTRL', 'ALT'): _mod_csi(7),
    ('SHIFT', 'CTRL', 'ALT'): _mod_csi(8),
}

# construct ansi to output mapping
ANSI_TO_KEYMOD = {
    sequence: (key, set(mods))
    for mods, mod_key_dict in MOD_KEYS.items()
    for key, sequence in mod_key_dict.items()
}
ANSI_TO_KEYMOD.update({sequence: (key, set()) for key, sequence in BASE_KEYS.items()})
ANSI_TO_KEYMOD.update({sequence: (key, set()) for key, sequence in CSI_KEYS.items()})
ANSI_TO_KEYMOD.update({sequence: (key, set()) for key, sequence in SS3_KEYS.items()})

# esc + char means alt+key; lowercase
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c + 32,): (chr(c + 32), {'ALT'}) for c in range(65, 91)})
# uppercase
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c + 32), {'ALT', 'SHIFT'}) for c in range(65, 91)})
# digits, controls & everything else
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c), {'ALT'}) for c in range(0, 65)})
ANSI_TO_KEYMOD.update({u'\x1b%c' % (c,): (chr(c), {'ALT'}) for c in range(91, 128)})


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


# output buffer for ioctl call
_sock_size = array.array('i', [0])


# standard unicode streams
if PY2:
    stdin = wrap_input_stream(sys.stdin)
    stdout = wrap_output_stream(sys.stdout)
    stderr = wrap_output_stream(sys.stderr)
else:
    stdin, stdout, stderr = sys.stdin, sys.stdout, sys.stderr


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

    def write(self, unicode_str):
        """Write unicode to console."""
        stdout.write(unicode_str)
        stdout.flush()

    def _emit_ansi(self, ansistr):
        """Emit escape code."""
        stdout.write(ansistr)
        stdout.flush()

    def _emit_ti(self, capability, *args):
        """Emit escape code."""
        if not curses:
            return
        pattern = curses.tigetstr(capability)
        if pattern:
            ansistr = curses.tparm(pattern, *args).decode('ascii')
            self._emit_ansi(ansistr)

    def set_caption(self, caption):
        """Set terminal caption."""
        self._emit_ansi(ANSI.SET_TITLE % (caption,))

    def resize(self, height, width):
        """Resize terminal."""
        self._emit_ansi(ANSI.RESIZE_TERM % (height, width))
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
            self._emit_ansi(ANSI.SET_CURSOR_BLOCK)
        else:
            self._emit_ansi(ANSI.SET_CURSOR_LINE)

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
            rgb = self._palette[colour]
            self._emit_ansi(ANSI.SET_CURSOR_COLOUR % rgb)
        except KeyError:
            pass

    def reset(self):
        """Reset to defaults."""
        self._emit_ti('oc')
        self._emit_ti('op')
        self._emit_ti('sgr0')
        self._emit_ti('cnorm')
        self._emit_ansi(
            ANSI.RESIZE_TERM % self._orig_size +
            ANSI.SET_CURSOR_COLOUR % (0xff, 0xff, 0xff) +
            ANSI.SET_CURSOR_BLOCK
        )

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
        sequence = read_all_available(stdin)
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
atexit.register(lambda: console.unset_raw() if console else None)


def read_all_available(stream):
    """Read all available characters from a stream; nonblocking; None if closed."""
    # this function works for everything on unix, and sockets on Windows
    instr = []
    # we're getting bytes counts for unicode which is pretty useless - so back to bytes
    try:
        encoding = stream.encoding
        stream = stream.buffer
    except:
        encoding = None
    # if buffer has characters/lines to read
    if select.select([stream], [], [], 0)[0]:
        # find number of bytes available
        fcntl.ioctl(stream, termios.FIONREAD, _sock_size)
        count = _sock_size[0]
        # and read them all
        c = stream.read(count)
        if not c and not instr:
            # break out, we're closed
            return None
        instr.append(c)
    if encoding:
        return b''.join(instr).decode(encoding, 'replace')
    return b''.join(instr)
