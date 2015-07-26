"""
PC-BASIC - scancode.py
Keyboard scancodes

(c) 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

# these are PC keyboard scancodes for a UK keyboard
ESCAPE = 0x01
# top-row numbers
N1 = 0x02
N2 = 0x03
N3 = 0x04
N4 = 0x05
N5 = 0x06
N6 = 0x07
N7 = 0x08
N8 = 0x09
N9 = 0x0A
N0 = 0x0B
MINUS = 0x0C
EQUALS = 0x0D
BACKSPACE = 0x0E
TAB = 0x0F
q = 0x10
w = 0x11
e = 0x12
r = 0x13
t = 0x14
y = 0x15
u = 0x16
i = 0x17
o = 0x18
p = 0x19
LEFTBRACKET = 0x1A
RIGHTBRACKET = 0x1B
RETURN = 0x1C
CTRL = 0x1D
a = 0x1E
s = 0x1F
d = 0x20
f = 0x21
g = 0x22
h = 0x23
j = 0x24
k = 0x25
l = 0x26
SEMICOLON = 0x27
QUOTE = 0x28
BACKQUOTE = 0x29
LSHIFT = 0x2A
BACKSLASH = 0x2B    # hash on UK keyboard
z = 0x2C
x = 0x2D
c = 0x2E
v = 0x2F
b = 0x30
n = 0x31
m = 0x32
COMMA = 0x33
PERIOD = 0x34
SLASH = 0x35
RSHIFT = 0x36
PRINT = 0x37
SYSREQ = 0x37
ALT = 0x38
SPACE = 0x39
CAPSLOCK = 0x3A
# function keys
F1 = 0x3B
F2 = 0x3C
F3 = 0x3D
F4 = 0x3E
F5 = 0x3F
F6 = 0x40
F7 = 0x41
F8 = 0x42
F9 = 0x43
F10 = 0x44
NUMLOCK = 0x45
SCROLLOCK = 0x46
KP7 = 0x47
HOME = 0x47
KP8 = 0x48
UP = 0x48
KP9 = 0x49
PAGEUP = 0x49
KPMINUS = 0x4A
KP4 = 0x4B
LEFT = 0x4B
KP5 = 0x4C
KP6 = 0x4D
RIGHT = 0x4D
KPPLUS = 0x4E
KP1 = 0x4F
END = 0x4F
KP2 = 0x50
DOWN = 0x50
KP3 = 0x51
PAGEDOWN = 0x51
KP0 = 0x52
INSERT = 0x52
#keypaddot
#times
#div
#enter?
# various
DELETE = 0x53
BREAK = 0x54
# tandy scancodes
F11 = 0xF9  # 0x57 on IBM PC
F12 = 0xFA  # 0x58 on IBM PC

# numeric keypad
keypad = {
    KP0: '0', KP1: '1', KP2: '2', KP3: '3', KP4: '4',
    KP5: '5', KP6: '6', KP7: '7', KP8: '8', KP9: '9' }

# eascii code for keys based on US keyboard
# normal, shift, ctrl, alt
# backends can override the eascii code using the override string
# so that the OS's keyboard settings are used.
# based on Tandy-1000 basic manual, modified for IBM PC keyboard
eascii_table = {
    ESCAPE: ('\x1b', '\x1b', '\x1b', ''),
    N1: ('1', '!', '', '\0\x78'),
    N2: ('2', '@', '\0\0', '\0\x79'),
    N3: ('3', '#', '', '\0\x7a'),
    N4: ('4', '$', '', '\0\x7b'),
    N5: ('5', '%', '', '\0\x7c'),
    N6: ('6', '^', '\x1e', '\0\x7d'),
    N7: ('7', '&', '', '\0\x7e'),
    N8: ('8', '*', '', '\0\x7f'),
    N9: ('9', '(', '', '\0\x80'),
    N0: ('0', ')', '', '\0\x81'),
    MINUS: ('-', '_', '\x1f', '\0\x82'),
    EQUALS: ('=', '+', '', '\0\x83'),
    BACKSPACE: ('\x08', '\x08', '\x7f', '\0\x8c'),
    TAB: ('\x09', '\0\x0f', '\0\x8d', '\0\x8e'),
    q: ('q', 'Q', '\x11', '\0\x10'),
    w: ('w', 'W', '\x17', '\0\x11'),
    e: ('e', 'E', '\x05', '\0\x12'),
    r: ('r', 'R', '\x12', '\0\x13'),
    t: ('t', 'T', '\x14', '\0\x14'),
    y: ('y', 'Y', '\x19', '\0\x15'),
    u: ('u', 'U', '\x15', '\0\x16'),
    i: ('i', 'I', '\x09', '\0\x17'),
    o: ('o', 'O', '\x0f', '\0\x18'),
    p: ('p', 'P', '\x10', '\0\x19'),
    LEFTBRACKET: ('[', '{', '\x1b', ''),
    RIGHTBRACKET: (']', '}', '\x1d', ''),
    RETURN: ('\r', '\r', '\n', '\0\x8f'),
    CTRL: ('', '', '', ''),
    a: ('a', 'A', '\x01', '\0\x1e'),
    s: ('s', 'S', '\x13', '\0\x1f'),
    d: ('d', 'D', '\x04', '\0\x20'),
    f: ('f', 'F', '\x06', '\0\x21'),
    g: ('g', 'G', '\x07', '\0\x22'),
    h: ('h', 'H', '\x08', '\0\x23'),
    j: ('j', 'J', '\x0a', '\0\x24'),
    k: ('k', 'K', '\x0b', '\0\x25'),
    l: ('l', 'L', '\x0c', '\0\x26'),
    SEMICOLON: (';', ':', '', ''),
    QUOTE: ("'", '"', '', ''),
    BACKQUOTE: ('`', '~', '', ''),
    LSHIFT: ('', '', '', ''),
    BACKSLASH: ('\\', '|', '\x1c', ''),
    z: ('z', 'Z', '\x1a', '\0\x2c'),
    x: ('x', 'X', '\x18', '\0\x2d'),
    c: ('c', 'C', '\x03', '\0\x2e'),
    v: ('v', 'V', '\x16', '\0\x2f'),
    b: ('b', 'B', '\x02', '\0\x30'),
    n: ('n', 'N', '\x0e', '\0\x31'),
    m: ('m', 'M', '\x0d', '\0\x32'),
    COMMA: (',', '<', '', ''),
    PERIOD: ('.', '>', '', ''),
    SLASH: ('/', '?', '', ''),
    RSHIFT: ('', '', '', ''),
    PRINT: ('', '', '\0\x72', '\0\x46'),
    ALT: ('', '', '', ''),
    SPACE: (' ', ' ', '\0\x72', '\0\x46'),
    CAPSLOCK: ('', '', '', ''),
    # function keys
    F1: ('\0\x3b', '\0\x54', '\0\x5e', '\0\x68'),
    F2: ('\0\x3c', '\0\x55', '\0\x5f', '\0\x69'),
    F3: ('\0\x3d', '\0\x56', '\0\x60', '\0\x6a'),
    F4: ('\0\x3e', '\0\x57', '\0\x61', '\0\x6c'),
    F5: ('\0\x3f', '\0\x58', '\0\x62', '\0\x6d'),
    F6: ('\0\x40', '\0\x59', '\0\x63', '\0\x6e'),
    F7: ('\0\x41', '\0\x5a', '\0\x64', '\0\x6f'),
    F8: ('\0\x42', '\0\x5b', '\0\x65', '\0\x70'),
    F9: ('\0\x43', '\0\x5c', '\0\x66', '\0\x71'),
    F10: ('\0\x44', '\0\x5d', '\0\x67', '\0\x72'),
    NUMLOCK: ('', '', '', ''),
    SCROLLOCK: ('', '', '', ''),
    HOME: ('\0\x47', '\0\x47', '\0\x77', ''), # KP7 HOME
    UP: ('\0\x48', '\0\x48', '', ''), # KP8 UP
    PAGEUP: ('\0\x49', '\0\x49', '\0\x84', ''), # KP9 PGUP
    KPMINUS: ('-', '-', '', ''),
    LEFT: ('\0\x4b', '\0\x87', '\0\x73', ''), # KP4 LEFT
    KP5: ('', '5', '', '\x05'),
    RIGHT: ('\0\x4d', '\0\x88', '\0\x74', ''), # KP6 RIGHT
    KPPLUS: ('+', '+', '', ''),
    END: ('\0\x4f', '\0\x4f', '\0\x75', ''), # KP1 END
    DOWN: ('\0\x50', '\0\x50', '', ''), # KP2 DOWN
    PAGEDOWN: ('\0\x51', '\0\x51', '\0\x76', ''), # KP3 PGDN
    INSERT: ('\0\x52', '\0\x52', '', ''), # KP0 INS
    # various
    DELETE: ('\0\x53', '\0\x53', '', ''),
    BREAK: ('', '', '', ''),
    # tandy scancodes
    F11: ('\x98', '\0\xa2', '\0\xac', '\0\xb6'),
    F12: ('\x99', '\0\xa3', '\0\xad', '\0\xb7'),
    }
