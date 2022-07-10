"""
PC-BASIC - scancode.py
Keyboard scancodes

(c) 2014--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# these are PC-XT keyboard scancodes without E0 extended codes
# they are labelled by their value on an IBM PC/XT US keyboard
# but they correspond to a physical key regardless of its logical value
# http://www.quadibloc.com/comp/scan.htm
#
# ROW 0
ESCAPE = 0x01
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
# ROW 1
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
# ROW 2
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
# ROW 3
LSHIFT = 0x2A
BACKSLASH = 0x2B
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
PRINT = 0x37; KPTIMES = 0x37;
# ROW 4
ALT = 0x38
SPACE = 0x39
CAPSLOCK = 0x3A
# function keypad
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
# numeric keypad
NUMLOCK = 0x45
SCROLLOCK = 0x46; BREAK = 0x46; PAUSE = 0x46;
KP7 = 0x47; HOME = 0x47
KP8 = 0x48; UP = 0x48
KP9 = 0x49; PAGEUP = 0x49
KPMINUS = 0x4A
KP4 = 0x4B; LEFT = 0x4B
KP5 = 0x4C
KP6 = 0x4D; RIGHT = 0x4D
KPPLUS = 0x4E
KP1 = 0x4F; END = 0x4F
KP2 = 0x50; DOWN = 0x50
KP3 = 0x51; PAGEDOWN = 0x51
KP0 = 0x52; INSERT = 0x52
KPPOINT = 0x53; DELETE = 0x53
# extensions (keys not on the US PC/XT keyboard)
SYSREQ = 0x54
# 56 - INT1, next to left shift, (\ on UK keyboard)
INT1 = 0x56
F11 = 0x57
F12 = 0x58
# Windows or Logo keys
LSUPER = 0x5B
RSUPER = 0x5C
MENU = 0x5D

# Japanese and Brazilian keyboards
# https://www.win.tue.nl/~aeb/linux/kbd/scancodes-8.html
# https://en.wikipedia.org/wiki/Language_input_keys
HIRAGANA_KATAKANA = 0x70
# backslash/underscore on Japanese keyboard
# /? on Brazilian keyboard
INT3 = 0x73
HENKAN = 0x79
MUHENKAN = 0x7B
ZENKAKU_HANKAKU = 0x29
# yen key on Japanese keyboard
INT4 = 0x7D
# keypad . on Brazilian keyboard
INT5 = 0x7E

# Korean keyboards
# https://www.win.tue.nl/~aeb/linux/kbd/scancodes-9.html
# Hanja key (left of Space on Korean keyboard)
HANJA = 0xF1
# Hangul/English key (right of Space on Korean keyboard)
HAN_YEONG = 0xF2


# tandy scancodes
#F11 = 0xF9
#F12 = 0xFA
