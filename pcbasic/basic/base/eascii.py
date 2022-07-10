"""
PC-BASIC - eascii.py
Keyboard e-ASCII codes

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ...compat import iteritems, unichr, SimpleNamespace


# based on Tandy-1000 basic manual, modified for IBM PC keyboard
# we don't specify the standard ASCII character values here
# nor the CTRL+a -> b'\x01' etc. series
# except where convenient

as_bytes = SimpleNamespace(

    NUL = b'\0\0',

    CTRL_b = b'\x02',
    CTRL_c = b'\x03',
    CTRL_d = b'\x04',
    CTRL_e = b'\x05',
    CTRL_f = b'\x06',
    CTRL_k = b'\x0B',
    CTRL_l = b'\x0C',
    CTRL_n = b'\x0E',
    CTRL_r = b'\x12',
    CTRL_z = b'\x1A',

    ESCAPE = b'\x1B',
    SHIFT_ESCAPE = b'\x1B',
    CTRL_ESCAPE = b'\x1B',

    BACKSPACE = b'\x08',
    SHIFT_BACKSPACE = b'\x08',
    CTRL_BACKSPACE = b'\x7F',
    ALT_BACKSPACE = b'\0\x8C',

    TAB = b'\x09',
    SHIFT_TAB = b'\0\x0F',
    CTRL_TAB = b'\0\x8D',
    ALT_TAB = b'\0\x8E',

    RETURN = b'\r',
    SHIFT_RETURN = b'\r',
    CTRL_RETURN = b'\n',
    ALT_RETURN = b'\0\x8F',

    SPACE = b' ',
    SHIFT_SPACE = b' ',
    CTRL_SPACE = b' ',
    ALT_SPACE = b'\0 ',

    CTRL_PRINT = b'\0\x72',
    ALT_PRINT = b'\0\x46',

    INSERT = b'\0\x52',
    SHIFT_INSERT = b'\0\x52',

    DELETE = b'\0\x53',
    SHIFT_DELETE = b'\0\x53',

    CTRL_2 = b'\0\x03',
    CTRL_6 = b'\x1E',
    CTRL_MINUS = b'\x1F',
    SHIFT_KP5 = b'5',
    ALT_KP5 = b'\x05',

    CTRL_BACKSLASH = b'\x1C',
    # CTRL+]
    CTRL_RIGHTBRACKET = b'\x1D',

    # Alt codes

    ALT_1 = b'\0\x78',
    ALT_2 = b'\0\x79',
    ALT_3 = b'\0\x7A',
    ALT_4 = b'\0\x7B',
    ALT_5 = b'\0\x7C',
    ALT_6 = b'\0\x7D',
    ALT_7 = b'\0\x7E',
    ALT_8 = b'\0\x7F',
    ALT_9 = b'\0\x80',
    ALT_0 = b'\0\x81',
    ALT_MINUS = b'\0\x82',
    ALT_EQUALS = b'\0\x83',

    ALT_q = b'\0\x10',
    ALT_w = b'\0\x11',
    ALT_e = b'\0\x12',
    ALT_r = b'\0\x13',
    ALT_t = b'\0\x14',
    ALT_y = b'\0\x15',
    ALT_u = b'\0\x16',
    ALT_i = b'\0\x17',
    ALT_o = b'\0\x18',
    ALT_p = b'\0\x19',

    ALT_a = b'\0\x1E',
    ALT_s = b'\0\x1F',
    ALT_d = b'\0\x20',
    ALT_f = b'\0\x21',
    ALT_g = b'\0\x22',
    ALT_h = b'\0\x23',
    ALT_j = b'\0\x24',
    ALT_k = b'\0\x25',
    ALT_l = b'\0\x26',

    ALT_z = b'\0\x2C',
    ALT_x = b'\0\x2D',
    ALT_c = b'\0\x2E',
    ALT_v = b'\0\x2F',
    ALT_b = b'\0\x30',
    ALT_n = b'\0\x31',
    ALT_m = b'\0\x32',

    # function keys

    F1 = b'\0\x3B',
    F2 = b'\0\x3C',
    F3 = b'\0\x3D',
    F4 = b'\0\x3E',
    F5 = b'\0\x3F',
    F6 = b'\0\x40',
    F7 = b'\0\x41',
    F8 = b'\0\x42',
    F9 = b'\0\x43',
    F10 = b'\0\x44',

    SHIFT_F1 = b'\0\x54',
    SHIFT_F2 = b'\0\x55',
    SHIFT_F3 = b'\0\x56',
    SHIFT_F4 = b'\0\x57',
    SHIFT_F5 = b'\0\x58',
    SHIFT_F6 = b'\0\x59',
    SHIFT_F7 = b'\0\x5A',
    SHIFT_F8 = b'\0\x5B',
    SHIFT_F9 = b'\0\x5C',
    SHIFT_F10 = b'\0\x5D',

    CTRL_F1 = b'\0\x5E',
    CTRL_F2 = b'\0\x5F',
    CTRL_F3 = b'\0\x60',
    CTRL_F4 = b'\0\x61',
    CTRL_F5 = b'\0\x62',
    CTRL_F6 = b'\0\x63',
    CTRL_F7 = b'\0\x64',
    CTRL_F8 = b'\0\x65',
    CTRL_F9 = b'\0\x66',
    CTRL_F10 = b'\0\x67',

    ALT_F1 = b'\0\x68',
    ALT_F2 = b'\0\x69',
    ALT_F3 = b'\0\x6A',
    ALT_F4 = b'\0\x6B',
    ALT_F5 = b'\0\x6C',
    ALT_F6 = b'\0\x6D',
    ALT_F7 = b'\0\x6E',
    ALT_F8 = b'\0\x6F',
    ALT_F9 = b'\0\x70',
    ALT_F10 = b'\0\x71',

    # numeric keypad
    HOME = b'\0\x47',
    UP = b'\0\x48',
    PAGEUP = b'\0\x49',
    LEFT = b'\0\x4B',
    RIGHT = b'\0\x4D',
    END = b'\0\x4F',
    DOWN = b'\0\x50',
    PAGEDOWN = b'\0\x51',

    SHIFT_HOME = b'\0\x47',
    SHIFT_UP = b'\0\x48',
    SHIFT_PAGEUP = b'\0\x49',
    SHIFT_LEFT = b'\0\x87',
    SHIFT_RIGHT = b'\0\x88',
    SHIFT_END = b'\0\x4F',
    SHIFT_DOWN = b'\0\x50',
    SHIFT_PAGEDOWN = b'\0\x51',

    CTRL_HOME = b'\0\x77',
    CTRL_PAGEUP = b'\0\x84',
    CTRL_LEFT = b'\0\x73',
    CTRL_RIGHT = b'\0\x74',
    CTRL_END = b'\0\x75',
    CTRL_PAGEDOWN = b'\0\x76',

    # Tandy e-ASCII codes
    F11 = b'\0\x98',
    F12 = b'\0\x99',
    SHIFT_F11 = b'\0\xA2',
    SHIFT_F12 = b'\0\xA3',
    CTRL_F11 = b'\0\xAC',
    CTRL_F12 = b'\0\xAD',
    ALT_F11 = b'\0\xB6',
    ALT_F12 = b'\0\xB7',
)

as_unicode = SimpleNamespace(**{
    key: value.decode('latin-1')
    for key, value in iteritems(as_bytes.__dict__)
})
