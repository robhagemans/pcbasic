"""
PC-BASIC - ansi.py
Definitions for ANSI escape sequences

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting
# http://www.termsys.demon.co.uk/vtansi.htm
# http://ascii-table.com/ansi-escape-sequences-vt-100.php
# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html

try:
    from types import SimpleNamespace
except ImportError:
    from .python2 import SimpleNamespace


# ANSI escape sequences
ESC = u'\x1B'
RESET = u'\x1Bc'
SET_SCROLL_SCREEN = u'\x1B[r'
SET_SCROLL_REGION = u'\x1B[%i;%ir'
RESIZE_TERM = u'\x1B[8;%i;%i;t'
SET_TITLE = u'\x1B]2;%s\a'
CLEAR_SCREEN = u'\x1B[2J'
CLEAR_LINE = u'\x1B[2K'
SCROLL_UP = u'\x1B[%iS'
SCROLL_DOWN = u'\x1B[%iT'
MOVE_CURSOR = u'\x1B[%i;%if'
MOVE_RIGHT = u'\x1B[C'
MOVE_LEFT = u'\x1B[D'
MOVE_N_RIGHT = u'\x1B[%iC'
MOVE_N_LEFT = u'\x1B[%iD'
SHOW_CURSOR = u'\x1B[?25h'
HIDE_CURSOR = u'\x1B[?25l'
# 1 blinking block 2 block 3 blinking line 4 line
SET_CURSOR_SHAPE = u'\x1B[%i q'
SET_COLOUR = u'\x1B[%im'
SET_CURSOR_COLOUR = u'\x1B]12;#%02x%02x%02x\a'
SET_PALETTE_ENTRY = u'\x1B]4;%i;#%02x%02x%02x\a'
RESET_PALETTE_ENTRY = u'\x1B]104;%i\a'
#SAVE_CURSOR_POS = u'\x1B[s'
#RESTORE_CURSOR_POS = u'\x1B[u'
#REQUEST_SIZE = u'\x1B[18;t'
#SET_FOREGROUND_RGB = u'\x1B[38;2;%i;%i;%im'
#SET_BACKGROUND_RGB = u'\x1B[48;2;%i;%i;%im'


# ANSI colour constants
COLOURS = SimpleNamespace(
    BLACK = 0,
    BLUE = 4,
    GREEN = 2,
    CYAN = 6,
    RED = 1,
    MAGENTA = 5,
    YELLOW = 3,
    WHITE = 7,
)

# keystrokes
KEYS = SimpleNamespace(
    F1 = u'\x1BOP',
    F2 = u'\x1BOQ',
    F3 = u'\x1BOR',
    F4 = u'\x1BOS',
    F1_OLD = u'\x1B[11~',
    F2_OLD = u'\x1B[12~',
    F3_OLD = u'\x1B[13~',
    F4_OLD = u'\x1B[14~',
    F5 = u'\x1B[15~',
    F6 = u'\x1B[17~',
    F7 = u'\x1B[18~',
    F8 = u'\x1B[19~',
    F9 = u'\x1B[20~',
    F10 = u'\x1B[21~',
    F11 = u'\x1B[23~',
    F12 = u'\x1B[24~',
    END = u'\x1BOF',
    END2 = u'\x1B[F',
    HOME = u'\x1BOH',
    HOME2 = u'\x1B[H',
    UP = u'\x1B[A',
    DOWN = u'\x1B[B',
    RIGHT = u'\x1B[C',
    LEFT = u'\x1B[D',
    INSERT = u'\x1B[2~',
    DELETE = u'\x1B[3~',
    PAGEUP = u'\x1B[5~',
    PAGEDOWN = u'\x1B[6~',
    CTRL_F1 = u'\x1b[1;5P',
    CTRL_F2 = u'\x1b[1;5Q',
    CTRL_F3 = u'\x1b[1;5R',
    CTRL_F4 = u'\x1b[1;5S',
    CTRL_F5 = u'\x1b[15;5~',
    CTRL_F6 = u'\x1B[17;5~',
    CTRL_F7 = u'\x1B[18;5~',
    CTRL_F8 = u'\x1B[19;5~',
    CTRL_F9 = u'\x1B[20;5~',
    CTRL_F10 = u'\x1B[21;5~',
    CTRL_F11 = u'\x1B[23;5~',
    CTRL_F12 = u'\x1B[24;5~',
    CTRL_END = u'\x1B[1;5F',
    CTRL_HOME = u'\x1B[1;5H',
    CTRL_UP = u'\x1B[1;5A',
    CTRL_DOWN = u'\x1B[1;5B',
    CTRL_RIGHT = u'\x1B[1;5C',
    CTRL_LEFT = u'\x1B[1;5D',
    CTRL_INSERT = u'\x1B[2;5~',
    CTRL_DELETE = u'\x1B[3;5~',
    CTRL_PAGEUP = u'\x1B[5;5~',
    CTRL_PAGEDOWN = u'\x1B[6;5~',
    ALT_F1 = u'\x1b[1;3P',
    ALT_F2 = u'\x1b[1;3Q',
    ALT_F3 = u'\x1b[1;3R',
    ALT_F4 = u'\x1b[1;3S',
    ALT_F5 = u'\x1b[15;3~',
    ALT_F6 = u'\x1B[17;3~',
    ALT_F7 = u'\x1B[18;3~',
    ALT_F8 = u'\x1B[19;3~',
    ALT_F9 = u'\x1B[20;3~',
    ALT_F10 = u'\x1B[21;3~',
    ALT_F11 = u'\x1B[23;3~',
    ALT_F12 = u'\x1B[24;3~',
    ALT_END = u'\x1B[1;3F',
    ALT_HOME = u'\x1B[1;3H',
    ALT_UP = u'\x1B[1;3A',
    ALT_DOWN = u'\x1B[1;3B',
    ALT_RIGHT = u'\x1B[1;3C',
    ALT_LEFT = u'\x1B[1;3D',
    ALT_INSERT = u'\x1B[2;3~',
    ALT_DELETE = u'\x1B[3;3~',
    ALT_PAGEUP = u'\x1B[5;3~',
    ALT_PAGEDOWN = u'\x1B[6;3~',
)
