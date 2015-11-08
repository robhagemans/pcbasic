"""
PC-BASIC - eascii.py
Keyboard e-ASCII codes

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

# based on Tandy-1000 basic manual, modified for IBM PC keyboard
# we don't specify the standard ASCII character values here
# nor the CTRL+a -> '\x01' etc. series
# except where convenient
NUL = '\0\0'
CTRL_c = '\x03'
CTRL_d = '\x04'
CTRL_z = '\x1A'

ESCAPE = '\x1B'
SHIFT_ESCAPE = '\x1B'
CTRL_ESCAPE = '\x1B'

BACKSPACE = '\x08'
SHIFT_BACKSPACE = '\x08'
CTRL_BACKSPACE = '\x7F'
ALT_BACKSPACE = '\0\x8C'

TAB = '\x09'
SHIFT_TAB = '\0\x0F'
CTRL_TAB = '\0\x8D'
ALT_TAB = '\0\x8E'

RETURN = '\r'
SHIFT_RETURN = '\r'
CTRL_RETURN = '\n'
ALT_RETURN = '\0\x8F'

SPACE = ' '
SHIFT_SPACE = ' '
CTRL_SPACE = ' '
ALT_SPACE = '\0 '

CTRL_PRINT = '\0\x72'
ALT_PRINT = '\0\x46'

INSERT = '\0\x52'
SHIFT_INSERT = '\0\x52'

DELETE = '\0\x53'
SHIFT_DELETE = '\0\x53'

CTRL_2 = '\0\x03'
CTRL_6 = '\x1E'
CTRL_MINUS = '\x1F'
SHIFT_KP5 = '5'
ALT_KP5 = '\x05'

# Alt codes

ALT_1 = '\0\x78'
ALT_2 = '\0\x79'
ALT_3 = '\0\x7A'
ALT_4 = '\0\x7B'
ALT_5 = '\0\x7C'
ALT_6 = '\0\x7D'
ALT_7 = '\0\x7E'
ALT_8 = '\0\x7F'
ALT_9 = '\0\x80'
ALT_0 = '\0\x81'
ALT_MINUS = '\0\x82'
ALT_EQUALS = '\0\x83'

ALT_q = '\0\x10'
ALT_w = '\0\x11'
ALT_e = '\0\x12'
ALT_r = '\0\x13'
ALT_t = '\0\x14'
ALT_y = '\0\x15'
ALT_u = '\0\x16'
ALT_i = '\0\x17'
ALT_o = '\0\x18'
ALT_p = '\0\x19'

ALT_a = '\0\x1E'
ALT_s = '\0\x1F'
ALT_d = '\0\x20'
ALT_f = '\0\x21'
ALT_g = '\0\x22'
ALT_h = '\0\x23'
ALT_j = '\0\x24'
ALT_k = '\0\x25'
ALT_l = '\0\x26'

ALT_z = '\0\x2C'
ALT_x = '\0\x2D'
ALT_c = '\0\x2E'
ALT_v = '\0\x2F'
ALT_b = '\0\x30'
ALT_n = '\0\x31'
ALT_m = '\0\x32'

# function keys

F1 = '\0\x3B'
F2 = '\0\x3C'
F3 = '\0\x3D'
F4 = '\0\x3E'
F5 = '\0\x3F'
F6 = '\0\x40'
F7 = '\0\x41'
F8 = '\0\x42'
F9 = '\0\x43'
F10 = '\0\x44'

SHIFT_F1 = '\0\x54'
SHIFT_F2 = '\0\x55'
SHIFT_F3 = '\0\x56'
SHIFT_F4 = '\0\x57'
SHIFT_F5 = '\0\x58'
SHIFT_F6 = '\0\x59'
SHIFT_F7 = '\0\x5A'
SHIFT_F8 = '\0\x5B'
SHIFT_F9 = '\0\x5C'
SHIFT_F10 = '\0\x5D'

CTRL_F1 = '\0\x5E'
CTRL_F2 = '\0\x5F'
CTRL_F3 = '\0\x60'
CTRL_F4 = '\0\x61'
CTRL_F5 = '\0\x62'
CTRL_F6 = '\0\x63'
CTRL_F7 = '\0\x64'
CTRL_F8 = '\0\x65'
CTRL_F9 = '\0\x66'
CTRL_F10 = '\0\x67'

ALT_F1 = '\0\x68'
ALT_F2 = '\0\x69'
ALT_F3 = '\0\x6A'
ALT_F4 = '\0\x6B'
ALT_F5 = '\0\x6C'
ALT_F6 = '\0\x6D'
ALT_F7 = '\0\x6E'
ALT_F8 = '\0\x6F'
ALT_F9 = '\0\x70'
ALT_F10 = '\0\x71'

# numeric keypad
HOME = '\0\x47'
UP = '\0\x48'
PAGEUP = '\0\x49'
LEFT = '\0\x4B'
RIGHT = '\0\x4D'
END = '\0\x4F'
DOWN = '\0\x50'
PAGEDOWN = '\0\x51'

SHIFT_HOME = '\0\x47'
SHIFT_UP = '\0\x48'
SHIFT_PAGEUP = '\0\x49'
SHIFT_LEFT = '\0\x87'
SHIFT_RIGHT = '\0\x88'
SHIFT_END = '\0\x4F'
SHIFT_DOWN = '\0\x50'
SHIFT_PAGEDOWN = '\0\x51'

CTRL_HOME = '\0\x77'
CTRL_PAGEUP = '\0\x84'
CTRL_LEFT = '\0\x73'
CTRL_RIGHT = '\0\x74'
CTRL_END = '\0\x75'
CTRL_PAGEDOWN = '\0\x76'

# Tandy e-ASCII codes
F11 = '\0\x98'
F12 = '\0\x99'
SHIFT_F11 = '\0\xA2'
SHIFT_F12 = '\0\xA3'
CTRL_F11 = '\0\xAC'
CTRL_F12 = '\0\xAD'
ALT_F11 = '\0\xB6'
ALT_F12 = '\0\xB7'
