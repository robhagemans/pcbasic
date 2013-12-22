
# Codepage 437 to Unicode table
# http://en.wikipedia.org/wiki/Code_page_437


def to_utf8(s):
    output = ''
    for c in s:
        output += cp437_to_unicode[ord(c)].encode('utf-8')
            
    return output

def from_unicode(s):
    output=''
    for c in s:
        if c in unicode_to_cp437:
            output += chr(unicode_to_cp437[c])
        elif ord(c) <= 0xff:
            output += chr(ord(c))
    return output

def from_utf8(s):
    return from_unicode(s.decode('utf-8'))
    
        
cp437_to_unicode = {

# Special Graphic Characters:

    0x00:   u'\u0020',  # whitespace
    0x01:   u'\u263A',  # smiley face
    0x02:   u'\u263B',  # smiley face inverted
    0x03:   u'\u2665',  # hearts
    0x04:   u'\u2666',  # diamonds
    0x05:   u'\u2663',  # clubs
    0x06:   u'\u2660',  # spades
    0x07:   u'\u2022',  # centre dot
    0x08:   u'\u25D8',  # centre dot inverted
    0x09:   u'\u25CB',  # circle
    0x0a:   u'\u25D9',  # circle inverted
    0x0b:   u'\u2642',  # male sign
    0x0c:   u'\u2640',  # female sign
    0x0d:   u'\u266A',  # musical note
    0x0e:   u'\u266B',  # two musical notes
    0x0f:   u'\u263C',  # sun
    0x10:   u'\u25BA',  # wedge right
    0x11:   u'\u25C4',  # wedge left
    0x12:   u'\u2195',  # double vertical arrow
    0x13:   u'\u203C',  # double bang
    0x14:   u'\u00B6',  # paragraph sign
    0x15:   u'\u00A7',  # section sign
    0x16:   u'\u25AC',  # bar
    0x17:   u'\u21A8',  # double arrow vertical, bottom line
    0x18:   u'\u2191',  # arrow up
    0x19:   u'\u2193',  # arrow down
    0x1a:   u'\u2192',  # arrow right
    0x1b:   u'\u2190',  # arrow left
    0x1c:   u'\u221F',  # hook bottom left
    0x1d:   u'\u2194',  # double arrow horizontal
    0x1e:   u'\u25B2',  # wedge up
    0x1f:   u'\u25BC',  # wedge down

    0x7f:   u'\u2302',  # HOUSE  
    
# http://msdn.microsoft.com/en-us/library/cc195060.aspx
#
#    Name:     cp437_DOSLatinUS to Unicode table
#    Unicode version: 2.0
#    Table version: 2.00
#    Table format:  Format A
#    Date:          04/24/96
#    Contact: Shawn.Steele@microsoft.com
#                   
#    General notes: none
#
#    Format: Three tab-separated columns
#        Column #1 is the cp437_DOSLatinUS code (in hex)
#        Column #2 is the Unicode (in hex as 0xXXXX)
#        Column #3 is the Unicode name (follows a comment sign', '#')
#
#    The entries are in cp437_DOSLatinUS order
#

    #0x00: u'\u0000',  #NULL
    #0x01: u'\u0001',  #START OF HEADING
    #0x02: u'\u0002',  #START OF TEXT
    #0x03: u'\u0003',  #END OF TEXT
    #0x04: u'\u0004',  #END OF TRANSMISSION
    #0x05: u'\u0005',  #ENQUIRY
    #0x06: u'\u0006',  #ACKNOWLEDGE
    #0x07: u'\u0007',  #BELL
    #0x08: u'\u0008',  #BACKSPACE
    #0x09: u'\u0009',  #HORIZONTAL TABULATION
    #0x0a: u'\u000a',  #LINE FEED - gw: CRLF
    #0x0b: u'\u000b',  #VERTICAL TABULATION ' gw: to pos (1,1,)
    #0x0c: u'\u000c',  #FORM FEED  - gw: CLS
    #0x0d: u'\u000d',  #CARRIAGE RETURN - gw: CRLF
    #0x0e: u'\u000e',  #SHIFT OUT
    #0x0f: u'\u000f',  #SHIFT IN
    #0x10: u'\u0010',  #DATA LINK ESCAPE
    #0x11: u'\u0011',  #DEVICE CONTROL ONE
    #0x12: u'\u0012',  #DEVICE CONTROL TWO
    #0x13: u'\u0013',  #DEVICE CONTROL THREE
    #0x14: u'\u0014',  #DEVICE CONTROL FOUR
    #0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
    #0x16: u'\u0016',  #SYNCHRONOUS IDLE
    #0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
    #0x18: u'\u0018',  #CANCEL
    #0x19: u'\u0019',  #END OF MEDIUM
    #0x1a: u'\u001a',  #SUBSTITUTE
    #0x1b: u'\u001b',  #ESCAPE
    #0x1c: u'\u001c',  #FILE SEPARATOR - gw: move right (don't print space)
    #0x1d: u'\u001d',  #GROUP SEPARATOR - gw: move left
    #0x1e: u'\u001e',  #RECORD SEPARATOR - gw: move up
    #0x1f: u'\u001f',  #UNIT SEPARATOR - gw: move down 
    0x20: u'\u0020',  #SPACE
    0x21: u'\u0021',  #EXCLAMATION MARK
    0x22: u'\u0022',  #QUOTATION MARK
    0x23: u'\u0023',  #NUMBER SIGN
    0x24: u'\u0024',  #DOLLAR SIGN
    0x25: u'\u0025',  #PERCENT SIGN
    0x26: u'\u0026',  #AMPERSAND
    0x27: u'\u0027',  #APOSTROPHE
    0x28: u'\u0028',  #LEFT PARENTHESIS
    0x29: u'\u0029',  #RIGHT PARENTHESIS
    0x2a: u'\u002a',  #ASTERISK
    0x2b: u'\u002b',  #PLUS SIGN
    0x2c: u'\u002c',  #COMMA
    0x2d: u'\u002d',  #HYPHEN-MINUS
    0x2e: u'\u002e',  #FULL STOP
    0x2f: u'\u002f',  #SOLIDUS
    0x30: u'\u0030',  #DIGIT ZERO
    0x31: u'\u0031',  #DIGIT ONE
    0x32: u'\u0032',  #DIGIT TWO
    0x33: u'\u0033',  #DIGIT THREE
    0x34: u'\u0034',  #DIGIT FOUR
    0x35: u'\u0035',  #DIGIT FIVE
    0x36: u'\u0036',  #DIGIT SIX
    0x37: u'\u0037',  #DIGIT SEVEN
    0x38: u'\u0038',  #DIGIT EIGHT
    0x39: u'\u0039',  #DIGIT NINE
    0x3a: u'\u003a',  #COLON
    0x3b: u'\u003b',  #SEMICOLON
    0x3c: u'\u003c',  #LESS-THAN SIGN
    0x3d: u'\u003d',  #EQUALS SIGN
    0x3e: u'\u003e',  #GREATER-THAN SIGN
    0x3f: u'\u003f',  #QUESTION MARK
    0x40: u'\u0040',  #COMMERCIAL AT
    0x41: u'\u0041',  #LATIN CAPITAL LETTER A
    0x42: u'\u0042',  #LATIN CAPITAL LETTER B
    0x43: u'\u0043',  #LATIN CAPITAL LETTER C
    0x44: u'\u0044',  #LATIN CAPITAL LETTER D
    0x45: u'\u0045',  #LATIN CAPITAL LETTER E
    0x46: u'\u0046',  #LATIN CAPITAL LETTER F
    0x47: u'\u0047',  #LATIN CAPITAL LETTER G
    0x48: u'\u0048',  #LATIN CAPITAL LETTER H
    0x49: u'\u0049',  #LATIN CAPITAL LETTER I
    0x4a: u'\u004a',  #LATIN CAPITAL LETTER J
    0x4b: u'\u004b',  #LATIN CAPITAL LETTER K
    0x4c: u'\u004c',  #LATIN CAPITAL LETTER L
    0x4d: u'\u004d',  #LATIN CAPITAL LETTER M
    0x4e: u'\u004e',  #LATIN CAPITAL LETTER N
    0x4f: u'\u004f',  #LATIN CAPITAL LETTER O
    0x50: u'\u0050',  #LATIN CAPITAL LETTER P
    0x51: u'\u0051',  #LATIN CAPITAL LETTER Q
    0x52: u'\u0052',  #LATIN CAPITAL LETTER R
    0x53: u'\u0053',  #LATIN CAPITAL LETTER S
    0x54: u'\u0054',  #LATIN CAPITAL LETTER T
    0x55: u'\u0055',  #LATIN CAPITAL LETTER U
    0x56: u'\u0056',  #LATIN CAPITAL LETTER V
    0x57: u'\u0057',  #LATIN CAPITAL LETTER W
    0x58: u'\u0058',  #LATIN CAPITAL LETTER X
    0x59: u'\u0059',  #LATIN CAPITAL LETTER Y
    0x5a: u'\u005a',  #LATIN CAPITAL LETTER Z
    0x5b: u'\u005b',  #LEFT SQUARE BRACKET
    0x5c: u'\u005c',  #REVERSE SOLIDUS
    0x5d: u'\u005d',  #RIGHT SQUARE BRACKET
    0x5e: u'\u005e',  #CIRCUMFLEX ACCENT
    0x5f: u'\u005f',  #LOW LINE
    0x60: u'\u0060',  #GRAVE ACCENT
    0x61: u'\u0061',  #LATIN SMALL LETTER A
    0x62: u'\u0062',  #LATIN SMALL LETTER B
    0x63: u'\u0063',  #LATIN SMALL LETTER C
    0x64: u'\u0064',  #LATIN SMALL LETTER D
    0x65: u'\u0065',  #LATIN SMALL LETTER E
    0x66: u'\u0066',  #LATIN SMALL LETTER F
    0x67: u'\u0067',  #LATIN SMALL LETTER G
    0x68: u'\u0068',  #LATIN SMALL LETTER H
    0x69: u'\u0069',  #LATIN SMALL LETTER I
    0x6a: u'\u006a',  #LATIN SMALL LETTER J
    0x6b: u'\u006b',  #LATIN SMALL LETTER K
    0x6c: u'\u006c',  #LATIN SMALL LETTER L
    0x6d: u'\u006d',  #LATIN SMALL LETTER M
    0x6e: u'\u006e',  #LATIN SMALL LETTER N
    0x6f: u'\u006f',  #LATIN SMALL LETTER O
    0x70: u'\u0070',  #LATIN SMALL LETTER P
    0x71: u'\u0071',  #LATIN SMALL LETTER Q
    0x72: u'\u0072',  #LATIN SMALL LETTER R
    0x73: u'\u0073',  #LATIN SMALL LETTER S
    0x74: u'\u0074',  #LATIN SMALL LETTER T
    0x75: u'\u0075',  #LATIN SMALL LETTER U
    0x76: u'\u0076',  #LATIN SMALL LETTER V
    0x77: u'\u0077',  #LATIN SMALL LETTER W
    0x78: u'\u0078',  #LATIN SMALL LETTER X
    0x79: u'\u0079',  #LATIN SMALL LETTER Y
    0x7a: u'\u007a',  #LATIN SMALL LETTER Z
    0x7b: u'\u007b',  #LEFT CURLY BRACKET
    0x7c: u'\u007c',  #VERTICAL LINE
    0x7d: u'\u007d',  #RIGHT CURLY BRACKET
    0x7e: u'\u007e',  #TILDE
    #0x7f: u'\u007f',  #DELETE
    0x80: u'\u00c7',  #LATIN CAPITAL LETTER C WITH CEDILLA
    0x81: u'\u00fc',  #LATIN SMALL LETTER U WITH DIAERESIS
    0x82: u'\u00e9',  #LATIN SMALL LETTER E WITH ACUTE
    0x83: u'\u00e2',  #LATIN SMALL LETTER A WITH CIRCUMFLEX
    0x84: u'\u00e4',  #LATIN SMALL LETTER A WITH DIAERESIS
    0x85: u'\u00e0',  #LATIN SMALL LETTER A WITH GRAVE
    0x86: u'\u00e5',  #LATIN SMALL LETTER A WITH RING ABOVE
    0x87: u'\u00e7',  #LATIN SMALL LETTER C WITH CEDILLA
    0x88: u'\u00ea',  #LATIN SMALL LETTER E WITH CIRCUMFLEX
    0x89: u'\u00eb',  #LATIN SMALL LETTER E WITH DIAERESIS
    0x8a: u'\u00e8',  #LATIN SMALL LETTER E WITH GRAVE
    0x8b: u'\u00ef',  #LATIN SMALL LETTER I WITH DIAERESIS
    0x8c: u'\u00ee',  #LATIN SMALL LETTER I WITH CIRCUMFLEX
    0x8d: u'\u00ec',  #LATIN SMALL LETTER I WITH GRAVE
    0x8e: u'\u00c4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
    0x8f: u'\u00c5',  #LATIN CAPITAL LETTER A WITH RING ABOVE
    0x90: u'\u00c9',  #LATIN CAPITAL LETTER E WITH ACUTE
    0x91: u'\u00e6',  #LATIN SMALL LIGATURE AE
    0x92: u'\u00c6',  #LATIN CAPITAL LIGATURE AE
    0x93: u'\u00f4',  #LATIN SMALL LETTER O WITH CIRCUMFLEX
    0x94: u'\u00f6',  #LATIN SMALL LETTER O WITH DIAERESIS
    0x95: u'\u00f2',  #LATIN SMALL LETTER O WITH GRAVE
    0x96: u'\u00fb',  #LATIN SMALL LETTER U WITH CIRCUMFLEX
    0x97: u'\u00f9',  #LATIN SMALL LETTER U WITH GRAVE
    0x98: u'\u00ff',  #LATIN SMALL LETTER Y WITH DIAERESIS
    0x99: u'\u00d6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
    0x9a: u'\u00dc',  #LATIN CAPITAL LETTER U WITH DIAERESIS
    0x9b: u'\u00a2',  #CENT SIGN
    0x9c: u'\u00a3',  #POUND SIGN
    0x9d: u'\u00a5',  #YEN SIGN
    0x9e: u'\u20a7',  #PESETA SIGN
    0x9f: u'\u0192',  #LATIN SMALL LETTER F WITH HOOK
    0xa0: u'\u00e1',  #LATIN SMALL LETTER A WITH ACUTE
    0xa1: u'\u00ed',  #LATIN SMALL LETTER I WITH ACUTE
    0xa2: u'\u00f3',  #LATIN SMALL LETTER O WITH ACUTE
    0xa3: u'\u00fa',  #LATIN SMALL LETTER U WITH ACUTE
    0xa4: u'\u00f1',  #LATIN SMALL LETTER N WITH TILDE
    0xa5: u'\u00d1',  #LATIN CAPITAL LETTER N WITH TILDE
    0xa6: u'\u00aa',  #FEMININE ORDINAL INDICATOR
    0xa7: u'\u00ba',  #MASCULINE ORDINAL INDICATOR
    0xa8: u'\u00bf',  #INVERTED QUESTION MARK
    0xa9: u'\u2310',  #REVERSED NOT SIGN
    0xaa: u'\u00ac',  #NOT SIGN
    0xab: u'\u00bd',  #VULGAR FRACTION ONE HALF
    0xac: u'\u00bc',  #VULGAR FRACTION ONE QUARTER
    0xad: u'\u00a1',  #INVERTED EXCLAMATION MARK
    0xae: u'\u00ab',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    0xaf: u'\u00bb',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    0xb0: u'\u2591',  #LIGHT SHADE
    0xb1: u'\u2592',  #MEDIUM SHADE
    0xb2: u'\u2593',  #DARK SHADE
    0xb3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
    0xb4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
    0xb5: u'\u2561',  #BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE
    0xb6: u'\u2562',  #BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE
    0xb7: u'\u2556',  #BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE
    0xb8: u'\u2555',  #BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE
    0xb9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
    0xba: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
    0xbb: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
    0xbc: u'\u255d',  #BOX DRAWINGS DOUBLE UP AND LEFT
    0xbd: u'\u255c',  #BOX DRAWINGS UP DOUBLE AND LEFT SINGLE
    0xbe: u'\u255b',  #BOX DRAWINGS UP SINGLE AND LEFT DOUBLE
    0xbf: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
    0xc0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
    0xc1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
    0xc2: u'\u252c',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
    0xc3: u'\u251c',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
    0xc4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
    0xc5: u'\u253c',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
    0xc6: u'\u255e',  #BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE
    0xc7: u'\u255f',  #BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE
    0xc8: u'\u255a',  #BOX DRAWINGS DOUBLE UP AND RIGHT
    0xc9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
    0xca: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
    0xcb: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
    0xcc: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
    0xcd: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
    0xce: u'\u256c',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
    0xcf: u'\u2567',  #BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE
    0xd0: u'\u2568',  #BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE
    0xd1: u'\u2564',  #BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE
    0xd2: u'\u2565',  #BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE
    0xd3: u'\u2559',  #BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE
    0xd4: u'\u2558',  #BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE
    0xd5: u'\u2552',  #BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE
    0xd6: u'\u2553',  #BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE
    0xd7: u'\u256b',  #BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE
    0xd8: u'\u256a',  #BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE
    0xd9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
    0xda: u'\u250c',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
    0xdb: u'\u2588',  #FULL BLOCK
    0xdc: u'\u2584',  #LOWER HALF BLOCK
    0xdd: u'\u258c',  #LEFT HALF BLOCK
    0xde: u'\u2590',  #RIGHT HALF BLOCK
    0xdf: u'\u2580',  #UPPER HALF BLOCK
    0xe0: u'\u03b1',  #GREEK SMALL LETTER ALPHA
    0xe1: u'\u00df',  #LATIN SMALL LETTER SHARP S
    0xe2: u'\u0393',  #GREEK CAPITAL LETTER GAMMA
    0xe3: u'\u03c0',  #GREEK SMALL LETTER PI
    0xe4: u'\u03a3',  #GREEK CAPITAL LETTER SIGMA
    0xe5: u'\u03c3',  #GREEK SMALL LETTER SIGMA
    0xe6: u'\u00b5',  #MICRO SIGN
    0xe7: u'\u03c4',  #GREEK SMALL LETTER TAU
    0xe8: u'\u03a6',  #GREEK CAPITAL LETTER PHI
    0xe9: u'\u0398',  #GREEK CAPITAL LETTER THETA
    0xea: u'\u03a9',  #GREEK CAPITAL LETTER OMEGA
    0xeb: u'\u03b4',  #GREEK SMALL LETTER DELTA
    0xec: u'\u221e',  #INFINITY
    0xed: u'\u03c6',  #GREEK SMALL LETTER PHI
    0xee: u'\u03b5',  #GREEK SMALL LETTER EPSILON
    0xef: u'\u2229',  #INTERSECTION
    0xf0: u'\u2261',  #IDENTICAL TO
    0xf1: u'\u00b1',  #PLUS-MINUS SIGN
    0xf2: u'\u2265',  #GREATER-THAN OR EQUAL TO
    0xf3: u'\u2264',  #LESS-THAN OR EQUAL TO
    0xf4: u'\u2320',  #TOP HALF INTEGRAL
    0xf5: u'\u2321',  #BOTTOM HALF INTEGRAL
    0xf6: u'\u00f7',  #DIVISION SIGN
    0xf7: u'\u2248',  #ALMOST EQUAL TO
    0xf8: u'\u00b0',  #DEGREE SIGN
    0xf9: u'\u2219',  #BULLET OPERATOR
    0xfa: u'\u00b7',  #MIDDLE DOT
    0xfb: u'\u221a',  #SQUARE ROOT
    0xfc: u'\u207f',  #SUPERSCRIPT LATIN SMALL LETTER N
    0xfd: u'\u00b2',  #SUPERSCRIPT TWO
    0xfe: u'\u25a0',  #BLACK SQUARE
    0xff: u'\u00a0',  #NO-BREAK SPACE
}

unicode_to_cp437 = dict((reversed(item) for item in cp437_to_unicode.items()))
#cp437_to_utf8 = { c: cp437[c].encode('utf-8') for c in cp437 }
#utf8_to_cp437 = dict((reversed(item) for item in cp437_to_utf8.items()))

