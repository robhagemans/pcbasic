"""
PC-BASIC - eascii.py
Keyboard e-ASCII codes

(c) 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# based on Tandy-1000 basic manual, modified for IBM PC keyboard
# we don't specify the standard ASCII character values here
# nor the CTRL+a -> u'\x01' etc. series
# except where convenient

NUL = u'\0\0'

CTRL_b = u'\x02'
CTRL_c = u'\x03'
CTRL_d = u'\x04'
CTRL_e = u'\x05'
CTRL_f = u'\x06'
CTRL_k = u'\x0B'
CTRL_l = u'\x0C'
CTRL_n = u'\x0E'
CTRL_r = u'\x12'
CTRL_z = u'\x1A'

ESCAPE = u'\x1B'
SHIFT_ESCAPE = u'\x1B'
CTRL_ESCAPE = u'\x1B'

BACKSPACE = u'\x08'
SHIFT_BACKSPACE = u'\x08'
CTRL_BACKSPACE = u'\x7F'
ALT_BACKSPACE = u'\0\x8C'

TAB = u'\x09'
SHIFT_TAB = u'\0\x0F'
CTRL_TAB = u'\0\x8D'
ALT_TAB = u'\0\x8E'

RETURN = u'\r'
SHIFT_RETURN = u'\r'
CTRL_RETURN = u'\n'
ALT_RETURN = u'\0\x8F'

SPACE = u' '
SHIFT_SPACE = u' '
CTRL_SPACE = u' '
ALT_SPACE = u'\0 '

CTRL_PRINT = u'\0\x72'
ALT_PRINT = u'\0\x46'

INSERT = u'\0\x52'
SHIFT_INSERT = u'\0\x52'

DELETE = u'\0\x53'
SHIFT_DELETE = u'\0\x53'

CTRL_2 = u'\0\x03'
CTRL_6 = u'\x1E'
CTRL_MINUS = u'\x1F'
SHIFT_KP5 = u'5'
ALT_KP5 = u'\x05'

CTRL_BACKSLASH = u'\x1C'
# CTRL+]
CTRL_RIGHTBRACKET = u'\x1D'

# Alt codes

ALT_1 = u'\0\x78'
ALT_2 = u'\0\x79'
ALT_3 = u'\0\x7A'
ALT_4 = u'\0\x7B'
ALT_5 = u'\0\x7C'
ALT_6 = u'\0\x7D'
ALT_7 = u'\0\x7E'
ALT_8 = u'\0\x7F'
ALT_9 = u'\0\x80'
ALT_0 = u'\0\x81'
ALT_MINUS = u'\0\x82'
ALT_EQUALS = u'\0\x83'

ALT_q = u'\0\x10'
ALT_w = u'\0\x11'
ALT_e = u'\0\x12'
ALT_r = u'\0\x13'
ALT_t = u'\0\x14'
ALT_y = u'\0\x15'
ALT_u = u'\0\x16'
ALT_i = u'\0\x17'
ALT_o = u'\0\x18'
ALT_p = u'\0\x19'

ALT_a = u'\0\x1E'
ALT_s = u'\0\x1F'
ALT_d = u'\0\x20'
ALT_f = u'\0\x21'
ALT_g = u'\0\x22'
ALT_h = u'\0\x23'
ALT_j = u'\0\x24'
ALT_k = u'\0\x25'
ALT_l = u'\0\x26'

ALT_z = u'\0\x2C'
ALT_x = u'\0\x2D'
ALT_c = u'\0\x2E'
ALT_v = u'\0\x2F'
ALT_b = u'\0\x30'
ALT_n = u'\0\x31'
ALT_m = u'\0\x32'

# function keys

F1 = u'\0\x3B'
F2 = u'\0\x3C'
F3 = u'\0\x3D'
F4 = u'\0\x3E'
F5 = u'\0\x3F'
F6 = u'\0\x40'
F7 = u'\0\x41'
F8 = u'\0\x42'
F9 = u'\0\x43'
F10 = u'\0\x44'

SHIFT_F1 = u'\0\x54'
SHIFT_F2 = u'\0\x55'
SHIFT_F3 = u'\0\x56'
SHIFT_F4 = u'\0\x57'
SHIFT_F5 = u'\0\x58'
SHIFT_F6 = u'\0\x59'
SHIFT_F7 = u'\0\x5A'
SHIFT_F8 = u'\0\x5B'
SHIFT_F9 = u'\0\x5C'
SHIFT_F10 = u'\0\x5D'

CTRL_F1 = u'\0\x5E'
CTRL_F2 = u'\0\x5F'
CTRL_F3 = u'\0\x60'
CTRL_F4 = u'\0\x61'
CTRL_F5 = u'\0\x62'
CTRL_F6 = u'\0\x63'
CTRL_F7 = u'\0\x64'
CTRL_F8 = u'\0\x65'
CTRL_F9 = u'\0\x66'
CTRL_F10 = u'\0\x67'

ALT_F1 = u'\0\x68'
ALT_F2 = u'\0\x69'
ALT_F3 = u'\0\x6A'
ALT_F4 = u'\0\x6B'
ALT_F5 = u'\0\x6C'
ALT_F6 = u'\0\x6D'
ALT_F7 = u'\0\x6E'
ALT_F8 = u'\0\x6F'
ALT_F9 = u'\0\x70'
ALT_F10 = u'\0\x71'

# numeric keypad
HOME = u'\0\x47'
UP = u'\0\x48'
PAGEUP = u'\0\x49'
LEFT = u'\0\x4B'
RIGHT = u'\0\x4D'
END = u'\0\x4F'
DOWN = u'\0\x50'
PAGEDOWN = u'\0\x51'

SHIFT_HOME = u'\0\x47'
SHIFT_UP = u'\0\x48'
SHIFT_PAGEUP = u'\0\x49'
SHIFT_LEFT = u'\0\x87'
SHIFT_RIGHT = u'\0\x88'
SHIFT_END = u'\0\x4F'
SHIFT_DOWN = u'\0\x50'
SHIFT_PAGEDOWN = u'\0\x51'

CTRL_HOME = u'\0\x77'
CTRL_PAGEUP = u'\0\x84'
CTRL_LEFT = u'\0\x73'
CTRL_RIGHT = u'\0\x74'
CTRL_END = u'\0\x75'
CTRL_PAGEDOWN = u'\0\x76'

# Tandy e-ASCII codes
F11 = u'\0\x98'
F12 = u'\0\x99'
SHIFT_F11 = u'\0\xA2'
SHIFT_F12 = u'\0\xA3'
CTRL_F11 = u'\0\xAC'
CTRL_F12 = u'\0\xAD'
ALT_F11 = u'\0\xB6'
ALT_F12 = u'\0\xB7'
