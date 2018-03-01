"""
PC-BASIC - ansi.py
Definitions for ANSI escape sequences

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# ANSI colour numbers for EGA colours: black, blue, green, cyan, red, magenta, yellow, white
COLOURS_8 = (0, 4, 2, 6, 1, 5, 3, 7)
# CGA colours: black, cyan, magenta, white
COLOURS_4 = (0, 6, 5, 7) * 4
# Mono colours: black, white
COLOURS_2 = (0, 7) * 8
# ANSI colour names for EGA colours
COLOUR_NAMES = (
    'Black', 'Dark Blue', 'Dark Green', 'Dark Cyan',
    'Dark Red', 'Dark Magenta', 'Brown', 'Light Gray',
    'Dark Gray', 'Blue', 'Green', 'Cyan',
    'Red', 'Magenta', 'Yellow', 'White')

# ANSI escape sequences
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting
ESC = b'\x1B'
RESET = b'\x1B[0m\x1Bc'
SET_SCROLL_SCREEN = b'\x1B[r'
SET_SCROLL_REGION = b'\x1B[%i;%ir'
CLEAR_SCREEN = b'\x1B[2J'
CLEAR_LINE = b'\x1B[2K'
SCROLL_UP = b'\x1B[%iS'
SCROLL_DOWN = b'\x1B[%iT'
SHOW_CURSOR = b'\x1B[?25h'
HIDE_CURSOR = b'\x1B[?25l'
RESIZE_TERM = b'\x1B[8;%i;%i;t'
MOVE_CURSOR = b'\x1B[%i;%if'
SAVE_CURSOR_POS = b'\x1B[s'
RESTORE_CURSOR_POS = b'\x1B[u'
REQUEST_SIZE = b'\x1B[18;t'
SET_CURSOR_COLOUR = b'\x1B]12;%s\a'
#% (2*(is_line+1) - blinks)
# 1 blinking block 2 block 3 blinking line 4 line
SET_CURSOR_SHAPE = b'\x1B[%i q'
SET_COLOUR = b'\x1B[%im'
SET_TITLE = b'\x1B]2;%s\a'
MOVE_RIGHT = b'\x1B[C'
MOVE_LEFT = b'\x1B[D'

# keystrokes
F1 = b'\x1BOP'
F2 = b'\x1BOQ'
F3 = b'\x1BOR'
F4 = b'\x1BOS'
F1_OLD = '\x1B[11~'
F2_OLD = '\x1B[12~'
F3_OLD = '\x1B[13~'
F4_OLD = '\x1B[14~'
F5 = b'\x1B[15~'
F6 = b'\x1B[17~'
F7 = b'\x1B[18~'
F8 = b'\x1B[19~'
F9 = b'\x1B[20~'
F10 = b'\x1B[21~'
F11 = b'\x1B[23~'
F12 = b'\x1B[24~'
END = b'\x1BOF'
END2 = b'\x1B[F'
HOME = b'\x1BOH'
HOME2 = b'\x1B[H'
UP = b'\x1B[A'
DOWN = b'\x1B[B'
RIGHT = b'\x1B[C'
LEFT = b'\x1B[D'
INSERT = b'\x1B[2~'
DELETE = b'\x1B[3~'
PAGEUP = b'\x1B[5~'
PAGEDOWN = b'\x1B[6~'
