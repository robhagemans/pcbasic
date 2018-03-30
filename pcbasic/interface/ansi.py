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
#COLOUR_NAMES = (
#    'Black', 'Dark Blue', 'Dark Green', 'Dark Cyan',
#    'Dark Red', 'Dark Magenta', 'Brown', 'Light Gray',
#    'Dark Gray', 'Blue', 'Green', 'Cyan',
#    'Red', 'Magenta', 'Yellow', 'White')

# ANSI escape sequences
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting
ESC = u'\x1B'
RESET = u'\x1B[0m\x1Bc'
SET_SCROLL_SCREEN = u'\x1B[r'
SET_SCROLL_REGION = u'\x1B[%i;%ir'
CLEAR_SCREEN = u'\x1B[2J'
CLEAR_LINE = u'\x1B[2K'
SCROLL_UP = u'\x1B[%iS'
SCROLL_DOWN = u'\x1B[%iT'
SHOW_CURSOR = u'\x1B[?25h'
HIDE_CURSOR = u'\x1B[?25l'
RESIZE_TERM = u'\x1B[8;%i;%i;t'
MOVE_CURSOR = u'\x1B[%i;%if'
SAVE_CURSOR_POS = u'\x1B[s'
RESTORE_CURSOR_POS = u'\x1B[u'
REQUEST_SIZE = u'\x1B[18;t'
SET_CURSOR_COLOUR = u'\x1B]12;%s\a'
#% (2*(is_line+1) - blinks)
# 1 blinking block 2 block 3 blinking line 4 line
SET_CURSOR_SHAPE = u'\x1B[%i q'
SET_COLOUR = u'\x1B[%im'
SET_TITLE = u'\x1B]2;%s\a'
MOVE_RIGHT = u'\x1B[C'
MOVE_LEFT = u'\x1B[D'
MOVE_N_RIGHT = u'\x1B[%iC'
MOVE_N_LEFT = u'\x1B[%iD'


# keystrokes
F1 = u'\x1BOP'
F2 = u'\x1BOQ'
F3 = u'\x1BOR'
F4 = u'\x1BOS'
F1_OLD = u'\x1B[11~'
F2_OLD = u'\x1B[12~'
F3_OLD = u'\x1B[13~'
F4_OLD = u'\x1B[14~'
F5 = u'\x1B[15~'
F6 = u'\x1B[17~'
F7 = u'\x1B[18~'
F8 = u'\x1B[19~'
F9 = u'\x1B[20~'
F10 = u'\x1B[21~'
F11 = u'\x1B[23~'
F12 = u'\x1B[24~'
END = u'\x1BOF'
END2 = u'\x1B[F'
HOME = u'\x1BOH'
HOME2 = u'\x1B[H'
UP = u'\x1B[A'
DOWN = u'\x1B[B'
RIGHT = u'\x1B[C'
LEFT = u'\x1B[D'
INSERT = u'\x1B[2~'
DELETE = u'\x1B[3~'
PAGEUP = u'\x1B[5~'
PAGEDOWN = u'\x1B[6~'
