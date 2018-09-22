"""
PC-BASIC - compat.posix_console
POSIX console support with ANSI escape sequences

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

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

from .base import MACOS, PY2, HOME_DIR, wrap_input_stream, wrap_output_stream

if PY2:
    from .python2 import SimpleNamespace
else:
    from types import SimpleNamespace



# output key codes - these can be anything
KEYS = SimpleNamespace(
    PAGEUP = 0x21,
    PAGEDOWN = 0x22,
    END = 0x23,
    HOME = 0x24,
    LEFT = 0x25,
    UP = 0x26,
    RIGHT = 0x27,
    DOWN = 0x28,
    INSERT = 0x2d,
    DELETE = 0x2e,
    F1 = 0x70,
    F2 = 0x71,
    F3 = 0x72,
    F4 = 0x73,
    F5 = 0x74,
    F6 = 0x75,
    F7 = 0x76,
    F8 = 0x77,
    F9 = 0x78,
    F10 = 0x79,
    F11 = 0x7a,
    F12 = 0x7b,
)
# can't access namespace with indexing directly
KEYDICT = KEYS.__dict__

MODS = SimpleNamespace(
    SHIFT = 0x10,
    CTRL = 0x0c,
    ALT = 0x03,
)


# ANSI escape codes
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting
# http://www.termsys.demon.co.uk/vtansi.htm
# http://ascii-table.com/ansi-escape-sequences-vt-100.php
# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html


# ANSI escape sequences
ANSI = SimpleNamespace(
    RESET = u'\x1Bc',
    SET_SCROLL_SCREEN = u'\x1B[r',
    SET_SCROLL_REGION = u'\x1B[%i;%ir',
    RESIZE_TERM = u'\x1B[8;%i;%i;t',
    SET_TITLE = u'\x1B]2;%s\a',
    CLEAR_SCREEN = u'\x1B[2J',
    CLEAR_LINE = u'\x1B[2K',
    SCROLL_UP = u'\x1B[%iS',
    SCROLL_DOWN = u'\x1B[%iT',
    MOVE_CURSOR = u'\x1B[%i;%if',
    MOVE_RIGHT = u'\x1B[C',
    MOVE_LEFT = u'\x1B[D',
    MOVE_N_RIGHT = u'\x1B[%iC',
    MOVE_N_LEFT = u'\x1B[%iD',
    SHOW_CURSOR = u'\x1B[?25h',
    HIDE_CURSOR = u'\x1B[?25l',
    # 1 blinking block 2 block 3 blinking line 4 line
    SET_CURSOR_SHAPE = u'\x1B[%i q',
    SET_COLOUR = u'\x1B[%im',
    SET_CURSOR_COLOUR = u'\x1B]12;#%02x%02x%02x\a',
    SET_PALETTE_ENTRY = u'\x1B]4;%i;#%02x%02x%02x\a',
    RESET_PALETTE_ENTRY = u'\x1B]104;%i\a',
    #SAVE_CURSOR_POS = u'\x1B[s',
    #RESTORE_CURSOR_POS = u'\x1B[u',
    #REQUEST_SIZE = u'\x1B[18;t',
    #SET_FOREGROUND_RGB = u'\x1B[38;2;%i;%i;%im',
    #SET_BACKGROUND_RGB = u'\x1B[48;2;%i;%i;%im',
)

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
    (MODS.SHIFT,): _mod_csi(2),
    (MODS.ALT,): _mod_csi(3),
    (MODS.SHIFT, MODS.ALT): _mod_csi(4),
    (MODS.CTRL,): _mod_csi(5),
    (MODS.SHIFT, MODS.CTRL): _mod_csi(6),
    (MODS.CTRL, MODS.ALT): _mod_csi(7),
    (MODS.SHIFT, MODS.CTRL, MODS.ALT): _mod_csi(8),
}

# construct ansi to output mapping
ANSI_TO_KEYMOD = {
    sequence: (KEYDICT[key], set(mods))
    for mods, mod_key_dict in MOD_KEYS.items()
    for key, sequence in mod_key_dict.items()
}
ANSI_TO_KEYMOD.update({sequence: (KEYDICT[key], ()) for key, sequence in BASE_KEYS.items()})
ANSI_TO_KEYMOD.update({sequence: (KEYDICT[key], ()) for key, sequence in CSI_KEYS.items()})
ANSI_TO_KEYMOD.update({sequence: (KEYDICT[key], ()) for key, sequence in SS3_KEYS.items()})


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

    keys = KEYS
    mods = MODS

    def __init__(self):
        """Set up the console."""
        # buffer to save termios state
        self._term_attr = termios.tcgetattr(sys.stdin.fileno())
        # preserve original terminal size
        self._orig_size = self.get_size()
        # input buffer
        self._read_buffer = deque()
        # palette
        self._palette = list(DEFAULT_PALETTE)

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

    def set_caption(self, caption):
        """Set terminal caption."""
        self._emit_ansi(ANSI.SET_TITLE % (caption,))

    def resize(self, height, width):
        """Resize terminal."""
        self._emit_ansi(ANSI.RESIZE_TERM % (height, width))
        # start below the current output
        self.clear()

    def clear(self):
        """Clear the screen."""
        self._emit_ansi(
            ANSI.CLEAR_SCREEN +
            ANSI.MOVE_CURSOR % (1, 1)
        )

    def clear_row(self):
        """Clear the current row."""
        self._emit_ansi(ANSI.CLEAR_LINE)

    def show_cursor(self, block=False):
        """Show the cursor."""
        self._emit_ansi(
            ANSI.SHOW_CURSOR +
            ANSI.SET_CURSOR_SHAPE % (1 if block else 3,)
        )

    def hide_cursor(self):
        """Hide the cursor."""
        self._emit_ansi(ANSI.HIDE_CURSOR)

    def move_cursor_left(self, n):
        """Move cursor n cells to the left."""
        self._emit_ansi(ANSI.MOVE_N_LEFT % (n,))

    def move_cursor_right(self, n):
        """Move cursor n cells to the right."""
        self._emit_ansi(ANSI.MOVE_N_RIGHT % (n,))

    def move_cursor_to(self, row, col):
        """Move cursor to a new position."""
        self._emit_ansi(ANSI.MOVE_CURSOR % (row, col))

    def scroll_up(self, top, bottom):
        """Scroll the region between top and bottom one row up."""
        self._emit_ansi(
            ANSI.SET_SCROLL_REGION % (top, bottom) +
            ANSI.SCROLL_UP % (1,) +
            ANSI.SET_SCROLL_SCREEN
        )

    def scroll_down(self, top, bottom):
        """Scroll the region between top and bottom one row down."""
        self._emit_ansi(
            ANSI.SET_SCROLL_REGION % (top, bottom) +
            ANSI.SCROLL_DOWN % (1,) +
            ANSI.SET_SCROLL_SCREEN
        )

    def set_cursor_colour(self, colour):
        """Set the current cursor colour attribute."""
        try:
            rgb = self._palette[colour]
            self._emit_ansi(ANSI.SET_CURSOR_COLOUR % rgb)
        except KeyError:
            pass

    def reset(self):
        """Reset to defaults."""
        self._emit_ansi(
            ANSI.RESIZE_TERM % self._orig_size +
            u''.join(ANSI.RESET_PALETTE_ENTRY % (attr,) for attr in range(16)) +
            ANSI.SET_COLOUR % (0,) +
            ANSI.SHOW_CURSOR +
            ANSI.SET_CURSOR_SHAPE % (1,)
        )

    def set_attributes(self, fore, back, blink, underline):
        """Set current attributes."""
        # use "bold" ANSI colours for the upper 8 EGA attributes
        style = 90 if (fore > 8) else 30
        self._emit_ansi(
            ANSI.SET_COLOUR % (0,) +
            ANSI.SET_COLOUR % (40 + EGA_TO_ANSI[back],) +
            ANSI.SET_COLOUR % (style + EGA_TO_ANSI[fore % 8],)
        )
        if blink:
            self._emit_ansi(ANSI.SET_COLOUR % (5,))
        if underline:
            self._emit_ansi(ANSI.SET_COLOUR % (4,))

    def set_palette_entry(self, attr, red, green, blue):
        """Set palette entry for attribute (0--16)."""
        # keep a record, mainly for cursor colours
        self._palette[attr] = red, green, blue
        # set the ANSI palette
        self._emit_ansi(ANSI.SET_PALETTE_ENTRY % (
            8*(attr//8) + EGA_TO_ANSI[attr%8], red, green, blue
        ))

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
            return u'\x04', 'd', {mods.CTRL}
        elif not sequence:
            return u'', None, set()
        # ansi sequences start with ESC (\x1b), but let ESC by itself through
        if len(sequence) > 1 and sequence[0] == u'\x1b':
            # esc+character represents alt+key
            if len(sequence) == 2:
                return u'', sequence[1], {MODS.ALT}
            # drop unrecognised sequences
            key, mod = ANSI_TO_KEYMOD.get(sequence, (u'', ()))
            return u'', key, mod
        else:
            return sequence, None, set()


def _has_console():
    """To see if we are a console app, check if we can treat stdin like a tty, file or socket."""
    if not sys.stdin.isatty():
        try:
            fcntl.ioctl(sys.stdin, termios.FIONREAD, _sock_size)
        except EnvironmentError:
            # maybe /dev/null, but not a real file or console
            return False
    return True


if _has_console():
    console = PosixConsole()
else:
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
