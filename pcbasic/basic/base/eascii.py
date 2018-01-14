"""
PC-BASIC - eascii.py
Keyboard e-ASCII codes

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# based on Tandy-1000 basic manual, modified for IBM PC keyboard
# we don't specify the standard ASCII character values here
# nor the CTRL+a -> b'\x01' etc. series
# except where convenient

class _EASCIIBytes(object):
    """EASCII constants as bytes."""

    def __init__(self):
        """Set bytes constants."""
        self.NUL = b'\0\0'

        self.CTRL_b = b'\x02'
        self.CTRL_c = b'\x03'
        self.CTRL_d = b'\x04'
        self.CTRL_e = b'\x05'
        self.CTRL_f = b'\x06'
        self.CTRL_k = b'\x0B'
        self.CTRL_l = b'\x0C'
        self.CTRL_n = b'\x0E'
        self.CTRL_r = b'\x12'
        self.CTRL_z = b'\x1A'

        self.ESCAPE = b'\x1B'
        self.SHIFT_ESCAPE = b'\x1B'
        self.CTRL_ESCAPE = b'\x1B'

        self.BACKSPACE = b'\x08'
        self.SHIFT_BACKSPACE = b'\x08'
        self.CTRL_BACKSPACE = b'\x7F'
        self.ALT_BACKSPACE = b'\0\x8C'

        self.TAB = b'\x09'
        self.SHIFT_TAB = b'\0\x0F'
        self.CTRL_TAB = b'\0\x8D'
        self.ALT_TAB = b'\0\x8E'

        self.RETURN = b'\r'
        self.SHIFT_RETURN = b'\r'
        self.CTRL_RETURN = b'\n'
        self.ALT_RETURN = b'\0\x8F'

        self.SPACE = b' '
        self.SHIFT_SPACE = b' '
        self.CTRL_SPACE = b' '
        self.ALT_SPACE = b'\0 '

        self.CTRL_PRINT = b'\0\x72'
        self.ALT_PRINT = b'\0\x46'

        self.INSERT = b'\0\x52'
        self.SHIFT_INSERT = b'\0\x52'

        self.DELETE = b'\0\x53'
        self.SHIFT_DELETE = b'\0\x53'

        self.CTRL_2 = b'\0\x03'
        self.CTRL_6 = b'\x1E'
        self.CTRL_MINUS = b'\x1F'
        self.SHIFT_KP5 = b'5'
        self.ALT_KP5 = b'\x05'

        self.CTRL_BACKSLASH = b'\x1C'
        # CTRL+]
        self.CTRL_RIGHTBRACKET = b'\x1D'

        # Alt codes

        self.ALT_1 = b'\0\x78'
        self.ALT_2 = b'\0\x79'
        self.ALT_3 = b'\0\x7A'
        self.ALT_4 = b'\0\x7B'
        self.ALT_5 = b'\0\x7C'
        self.ALT_6 = b'\0\x7D'
        self.ALT_7 = b'\0\x7E'
        self.ALT_8 = b'\0\x7F'
        self.ALT_9 = b'\0\x80'
        self.ALT_0 = b'\0\x81'
        self.ALT_MINUS = b'\0\x82'
        self.ALT_EQUALS = b'\0\x83'

        self.ALT_q = b'\0\x10'
        self.ALT_w = b'\0\x11'
        self.ALT_e = b'\0\x12'
        self.ALT_r = b'\0\x13'
        self.ALT_t = b'\0\x14'
        self.ALT_y = b'\0\x15'
        self.ALT_u = b'\0\x16'
        self.ALT_i = b'\0\x17'
        self.ALT_o = b'\0\x18'
        self.ALT_p = b'\0\x19'

        self.ALT_a = b'\0\x1E'
        self.ALT_s = b'\0\x1F'
        self.ALT_d = b'\0\x20'
        self.ALT_f = b'\0\x21'
        self.ALT_g = b'\0\x22'
        self.ALT_h = b'\0\x23'
        self.ALT_j = b'\0\x24'
        self.ALT_k = b'\0\x25'
        self.ALT_l = b'\0\x26'

        self.ALT_z = b'\0\x2C'
        self.ALT_x = b'\0\x2D'
        self.ALT_c = b'\0\x2E'
        self.ALT_v = b'\0\x2F'
        self.ALT_b = b'\0\x30'
        self.ALT_n = b'\0\x31'
        self.ALT_m = b'\0\x32'

        # function keys

        self.F1 = b'\0\x3B'
        self.F2 = b'\0\x3C'
        self.F3 = b'\0\x3D'
        self.F4 = b'\0\x3E'
        self.F5 = b'\0\x3F'
        self.F6 = b'\0\x40'
        self.F7 = b'\0\x41'
        self.F8 = b'\0\x42'
        self.F9 = b'\0\x43'
        self.F10 = b'\0\x44'

        self.SHIFT_F1 = b'\0\x54'
        self.SHIFT_F2 = b'\0\x55'
        self.SHIFT_F3 = b'\0\x56'
        self.SHIFT_F4 = b'\0\x57'
        self.SHIFT_F5 = b'\0\x58'
        self.SHIFT_F6 = b'\0\x59'
        self.SHIFT_F7 = b'\0\x5A'
        self.SHIFT_F8 = b'\0\x5B'
        self.SHIFT_F9 = b'\0\x5C'
        self.SHIFT_F10 = b'\0\x5D'

        self.CTRL_F1 = b'\0\x5E'
        self.CTRL_F2 = b'\0\x5F'
        self.CTRL_F3 = b'\0\x60'
        self.CTRL_F4 = b'\0\x61'
        self.CTRL_F5 = b'\0\x62'
        self.CTRL_F6 = b'\0\x63'
        self.CTRL_F7 = b'\0\x64'
        self.CTRL_F8 = b'\0\x65'
        self.CTRL_F9 = b'\0\x66'
        self.CTRL_F10 = b'\0\x67'

        self.ALT_F1 = b'\0\x68'
        self.ALT_F2 = b'\0\x69'
        self.ALT_F3 = b'\0\x6A'
        self.ALT_F4 = b'\0\x6B'
        self.ALT_F5 = b'\0\x6C'
        self.ALT_F6 = b'\0\x6D'
        self.ALT_F7 = b'\0\x6E'
        self.ALT_F8 = b'\0\x6F'
        self.ALT_F9 = b'\0\x70'
        self.ALT_F10 = b'\0\x71'

        # numeric keypad
        self.HOME = b'\0\x47'
        self.UP = b'\0\x48'
        self.PAGEUP = b'\0\x49'
        self.LEFT = b'\0\x4B'
        self.RIGHT = b'\0\x4D'
        self.END = b'\0\x4F'
        self.DOWN = b'\0\x50'
        self.PAGEDOWN = b'\0\x51'

        self.SHIFT_HOME = b'\0\x47'
        self.SHIFT_UP = b'\0\x48'
        self.SHIFT_PAGEUP = b'\0\x49'
        self.SHIFT_LEFT = b'\0\x87'
        self.SHIFT_RIGHT = b'\0\x88'
        self.SHIFT_END = b'\0\x4F'
        self.SHIFT_DOWN = b'\0\x50'
        self.SHIFT_PAGEDOWN = b'\0\x51'

        self.CTRL_HOME = b'\0\x77'
        self.CTRL_PAGEUP = b'\0\x84'
        self.CTRL_LEFT = b'\0\x73'
        self.CTRL_RIGHT = b'\0\x74'
        self.CTRL_END = b'\0\x75'
        self.CTRL_PAGEDOWN = b'\0\x76'

        # Tandy e-ASCII codes
        self.F11 = b'\0\x98'
        self.F12 = b'\0\x99'
        self.SHIFT_F11 = b'\0\xA2'
        self.SHIFT_F12 = b'\0\xA3'
        self.CTRL_F11 = b'\0\xAC'
        self.CTRL_F12 = b'\0\xAD'
        self.ALT_F11 = b'\0\xB6'
        self.ALT_F12 = b'\0\xB7'


class _EASCIIUnicode(_EASCIIBytes):
    """EASCII constants as unicode."""

    def __init__(self):
        """Set unicode constants."""
        # override class variables
        #_EASCIIBytes.__init__(self)
        for name, value in _EASCIIBytes().__dict__.iteritems():
            if name[0] != b'_':
                self.__dict__[name] = u''.join([unichr(ord(x)) for x in value])


as_bytes = _EASCIIBytes()
as_unicode = _EASCIIUnicode()
