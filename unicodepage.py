
# Codepage 437 to Unicode table 
# with Special Graphic Characters
# http://en.wikipedia.org/wiki/Code_page_437
# http://msdn.microsoft.com/en-us/library/cc195060.aspx
# http://msdn.microsoft.com/en-us/goglobal/cc305160

import sys

def from_unicode(s):
    output = ''
    for c in s:
        if ord(c) == 0:
            # double NUL characters as single NUL signals scan code
            output += '\x00\x00'
        else:
            try: 
                output += chr(unicode_to_cp[c])
            except KeyError:
                if ord(c) <= 0xff:
                    output += chr(ord(c))
    return output

def load_codepage(number=437):
    global cp_to_unicode, unicode_to_cp, cp_to_utf8, utf8_to_cp
    try:
        cp_to_unicode = codepage[number]
    except KeyError:
        sys.stderr.write('WARNING: Could not find unicode/codepage table. Falling back to codepage 437 (US).\n')
        cp_to_unicode = codepage[437]
    cp_to_unicode.update(special_graphic)    
    unicode_to_cp = dict((reversed(item) for item in cp_to_unicode.items()))
    cp_to_utf8 = dict([ (chr(s[0]), s[1].encode('utf-8')) for s in cp_to_unicode.items()])
    utf8_to_cp = dict((reversed(item) for item in cp_to_utf8.items()))
      
      
special_graphic = {
    0x00:   u'\u0000',  # whitespace
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
    0x7f:   u'\u2302',  # house  
}        
        
codepage = {
    437: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0a: u'\u000a',  #LINE FEED - gw: CRLF
        0x0b: u'\u000b',  #VERTICAL TABULATION ' gw: to pos (1,1,)
        0x0c: u'\u000c',  #FORM FEED  - gw: CLS
        0x0d: u'\u000d',  #CARRIAGE RETURN - gw: CRLF
        0x0e: u'\u000e',  #SHIFT OUT
        0x0f: u'\u000f',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1a: u'\u001a',  #SUBSTITUTE
        0x1b: u'\u001b',  #ESCAPE
        0x1c: u'\u001c',  #FILE SEPARATOR - gw: move right (don't print space)
        0x1d: u'\u001d',  #GROUP SEPARATOR - gw: move left
        0x1e: u'\u001e',  #RECORD SEPARATOR - gw: move up
        0x1f: u'\u001f',  #UNIT SEPARATOR - gw: move down 
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
        0x7f: u'\u007f',  #DELETE
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
    },
    850: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u00C7',  #LATIN CAPITAL LETTER C WITH CEDILLA
        0x81: u'\u00FC',  #LATIN SMALL LETTER U WITH DIAERESIS
        0x82: u'\u00E9',  #LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u00E2',  #LATIN SMALL LETTER A WITH CIRCUMFLEX
        0x84: u'\u00E4',  #LATIN SMALL LETTER A WITH DIAERESIS
        0x85: u'\u00E0',  #LATIN SMALL LETTER A WITH GRAVE
        0x86: u'\u00E5',  #LATIN SMALL LETTER A WITH RING ABOVE
        0x87: u'\u00E7',  #LATIN SMALL LETTER C WITH CEDILLA
        0x88: u'\u00EA',  #LATIN SMALL LETTER E WITH CIRCUMFLEX
        0x89: u'\u00EB',  #LATIN SMALL LETTER E WITH DIAERESIS
        0x8A: u'\u00E8',  #LATIN SMALL LETTER E WITH GRAVE
        0x8B: u'\u00EF',  #LATIN SMALL LETTER I WITH DIAERESIS
        0x8C: u'\u00EE',  #LATIN SMALL LETTER I WITH CIRCUMFLEX
        0x8D: u'\u00EC',  #LATIN SMALL LETTER I WITH GRAVE
        0x8E: u'\u00C4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
        0x8F: u'\u00C5',  #LATIN CAPITAL LETTER A WITH RING ABOVE
        0x90: u'\u00C9',  #LATIN CAPITAL LETTER E WITH ACUTE
        0x91: u'\u00E6',  #LATIN SMALL LETTER AE
        0x92: u'\u00C6',  #LATIN CAPITAL LETTER AE
        0x93: u'\u00F4',  #LATIN SMALL LETTER O WITH CIRCUMFLEX
        0x94: u'\u00F6',  #LATIN SMALL LETTER O WITH DIAERESIS
        0x95: u'\u00F2',  #LATIN SMALL LETTER O WITH GRAVE
        0x96: u'\u00FB',  #LATIN SMALL LETTER U WITH CIRCUMFLEX
        0x97: u'\u00F9',  #LATIN SMALL LETTER U WITH GRAVE
        0x98: u'\u00FF',  #LATIN SMALL LETTER Y WITH DIAERESIS
        0x99: u'\u00D6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
        0x9A: u'\u00DC',  #LATIN CAPITAL LETTER U WITH DIAERESIS
        0x9B: u'\u00F8',  #LATIN SMALL LETTER O WITH STROKE
        0x9C: u'\u00A3',  #POUND SIGN
        0x9D: u'\u00D8',  #LATIN CAPITAL LETTER O WITH STROKE
        0x9E: u'\u00D7',  #MULTIPLICATION SIGN
        0x9F: u'\u0192',  #LATIN SMALL LETTER F WITH HOOK
        0xA0: u'\u00E1',  #LATIN SMALL LETTER A WITH ACUTE
        0xA1: u'\u00ED',  #LATIN SMALL LETTER I WITH ACUTE
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u00FA',  #LATIN SMALL LETTER U WITH ACUTE
        0xA4: u'\u00F1',  #LATIN SMALL LETTER N WITH TILDE
        0xA5: u'\u00D1',  #LATIN CAPITAL LETTER N WITH TILDE
        0xA6: u'\u00AA',  #FEMININE ORDINAL INDICATOR
        0xA7: u'\u00BA',  #MASCULINE ORDINAL INDICATOR
        0xA8: u'\u00BF',  #INVERTED QUESTION MARK
        0xA9: u'\u00AE',  #REGISTERED SIGN
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u00BD',  #VULGAR FRACTION ONE HALF
        0xAC: u'\u00BC',  #VULGAR FRACTION ONE QUARTER
        0xAD: u'\u00A1',  #INVERTED EXCLAMATION MARK
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u00C1',  #LATIN CAPITAL LETTER A WITH ACUTE
        0xB6: u'\u00C2',  #LATIN CAPITAL LETTER A WITH CIRCUMFLEX
        0xB7: u'\u00C0',  #LATIN CAPITAL LETTER A WITH GRAVE
        0xB8: u'\u00A9',  #COPYRIGHT SIGN
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u00A2',  #CENT SIGN
        0xBE: u'\u00A5',  #YEN SIGN
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u00E3',  #LATIN SMALL LETTER A WITH TILDE
        0xC7: u'\u00C3',  #LATIN CAPITAL LETTER A WITH TILDE
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u00A4',  #CURRENCY SIGN
        0xD0: u'\u00F0',  #LATIN SMALL LETTER ETH
        0xD1: u'\u00D0',  #LATIN CAPITAL LETTER ETH
        0xD2: u'\u00CA',  #LATIN CAPITAL LETTER E WITH CIRCUMFLEX
        0xD3: u'\u00CB',  #LATIN CAPITAL LETTER E WITH DIAERESIS
        0xD4: u'\u00C8',  #LATIN CAPITAL LETTER E WITH GRAVE
        0xD5: u'\u0131',  #LATIN SMALL LETTER DOTLESS I
        0xD6: u'\u00CD',  #LATIN CAPITAL LETTER I WITH ACUTE
        0xD7: u'\u00CE',  #LATIN CAPITAL LETTER I WITH CIRCUMFLEX
        0xD8: u'\u00CF',  #LATIN CAPITAL LETTER I WITH DIAERESIS
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u00A6',  #BROKEN BAR
        0xDE: u'\u00CC',  #LATIN CAPITAL LETTER I WITH GRAVE
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u00D3',  #LATIN CAPITAL LETTER O WITH ACUTE
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u00D4',  #LATIN CAPITAL LETTER O WITH CIRCUMFLEX
        0xE3: u'\u00D2',  #LATIN CAPITAL LETTER O WITH GRAVE
        0xE4: u'\u00F5',  #LATIN SMALL LETTER O WITH TILDE
        0xE5: u'\u00D5',  #LATIN CAPITAL LETTER O WITH TILDE
        0xE6: u'\u00B5',  #MICRO SIGN
        0xE7: u'\u00FE',  #LATIN SMALL LETTER THORN
        0xE8: u'\u00DE',  #LATIN CAPITAL LETTER THORN
        0xE9: u'\u00DA',  #LATIN CAPITAL LETTER U WITH ACUTE
        0xEA: u'\u00DB',  #LATIN CAPITAL LETTER U WITH CIRCUMFLEX
        0xEB: u'\u00D9',  #LATIN CAPITAL LETTER U WITH GRAVE
        0xEC: u'\u00FD',  #LATIN SMALL LETTER Y WITH ACUTE
        0xED: u'\u00DD',  #LATIN CAPITAL LETTER Y WITH ACUTE
        0xEE: u'\u00AF',  #MACRON
        0xEF: u'\u00B4',  #ACUTE ACCENT
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u00B1',  #PLUS-MINUS SIGN
        0xF2: u'\u2017',  #DOUBLE LOW LINE
        0xF3: u'\u00BE',  #VULGAR FRACTION THREE QUARTERS
        0xF4: u'\u00B6',  #PILCROW SIGN
        0xF5: u'\u00A7',  #SECTION SIGN
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u00B8',  #CEDILLA
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u00A8',  #DIAERESIS
        0xFA: u'\u00B7',  #MIDDLE DOT
        0xFB: u'\u00B9',  #SUPERSCRIPT ONE
        0xFC: u'\u00B3',  #SUPERSCRIPT THREE
        0xFD: u'\u00B2',  #SUPERSCRIPT TWO
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    720: {
        0x00: u'\u0000',  # NULL
        0x01: u'\u0001',  # START OF HEADING
        0x02: u'\u0002',  # START OF TEXT
        0x03: u'\u0003',  # END OF TEXT
        0x04: u'\u0004',  # END OF TRANSMISSION
        0x05: u'\u0005',  # ENQUIRY
        0x06: u'\u0006',  # ACKNOWLEDGE
        0x07: u'\u0007',  # BELL
        0x08: u'\u0008',  # BACKSPACE
        0x09: u'\u0009',  # HORIZONTAL TABULATION
        0x0A: u'\u000A',  # LINE FEED
        0x0B: u'\u000B',  # VERTICAL TABULATION
        0x0C: u'\u000C',  # FORM FEED
        0x0D: u'\u000D',  # CARRIAGE RETURN
        0x0E: u'\u000E',  # SHIFT OUT
        0x0F: u'\u000F',  # SHIFT IN
        0x10: u'\u0010',  # DATA LINK ESCAPE
        0x11: u'\u0011',  # DEVICE CONTROL ONE
        0x12: u'\u0012',  # DEVICE CONTROL TWO
        0x13: u'\u0013',  # DEVICE CONTROL THREE
        0x14: u'\u0014',  # DEVICE CONTROL FOUR
        0x15: u'\u0015',  # NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  # SYNCHRONOUS IDLE
        0x17: u'\u0017',  # END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  # CANCEL
        0x19: u'\u0019',  # END OF MEDIUM
        0x1A: u'\u001A',  # SUBSTITUTE
        0x1B: u'\u001B',  # ESCAPE
        0x1C: u'\u001C',  # FILE SEPARATOR
        0x1D: u'\u001D',  # GROUP SEPARATOR
        0x1E: u'\u001E',  # RECORD SEPARATOR
        0x1F: u'\u001F',  # UNIT SEPARATOR
        0x20: u'\u0020',  # SPACE
        0x21: u'\u0021',  # EXCLAMATION MARK
        0x22: u'\u0022',  # QUOTATION MARK
        0x23: u'\u0023',  # NUMBER SIGN
        0x24: u'\u0024',  # DOLLAR SIGN
        0x25: u'\u0025',  # PERCENT SIGN
        0x26: u'\u0026',  # AMPERSAND
        0x27: u'\u0027',  # APOSTROPHE
        0x28: u'\u0028',  # LEFT PARENTHESIS
        0x29: u'\u0029',  # RIGHT PARENTHESIS
        0x2A: u'\u002A',  # ASTERISK
        0x2B: u'\u002B',  # PLUS SIGN
        0x2C: u'\u002C',  # COMMA
        0x2D: u'\u002D',  # HYPHEN-MINUS
        0x2E: u'\u002E',  # FULL STOP
        0x2F: u'\u002F',  # SOLIDUS
        0x30: u'\u0030',  # DIGIT ZERO
        0x31: u'\u0031',  # DIGIT ONE
        0x32: u'\u0032',  # DIGIT TWO
        0x33: u'\u0033',  # DIGIT THREE
        0x34: u'\u0034',  # DIGIT FOUR
        0x35: u'\u0035',  # DIGIT FIVE
        0x36: u'\u0036',  # DIGIT SIX
        0x37: u'\u0037',  # DIGIT SEVEN
        0x38: u'\u0038',  # DIGIT EIGHT
        0x39: u'\u0039',  # DIGIT NINE
        0x3A: u'\u003A',  # COLON
        0x3B: u'\u003B',  # SEMICOLON
        0x3C: u'\u003C',  # LESS-THAN SIGN
        0x3D: u'\u003D',  # EQUALS SIGN
        0x3E: u'\u003E',  # GREATER-THAN SIGN
        0x3F: u'\u003F',  # QUESTION MARK
        0x40: u'\u0040',  # COMMERCIAL AT
        0x41: u'\u0041',  # LATIN CAPITAL LETTER A
        0x42: u'\u0042',  # LATIN CAPITAL LETTER B
        0x43: u'\u0043',  # LATIN CAPITAL LETTER C
        0x44: u'\u0044',  # LATIN CAPITAL LETTER D
        0x45: u'\u0045',  # LATIN CAPITAL LETTER E
        0x46: u'\u0046',  # LATIN CAPITAL LETTER F
        0x47: u'\u0047',  # LATIN CAPITAL LETTER G
        0x48: u'\u0048',  # LATIN CAPITAL LETTER H
        0x49: u'\u0049',  # LATIN CAPITAL LETTER I
        0x4A: u'\u004A',  # LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  # LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  # LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  # LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  # LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  # LATIN CAPITAL LETTER O
        0x50: u'\u0050',  # LATIN CAPITAL LETTER P
        0x51: u'\u0051',  # LATIN CAPITAL LETTER Q
        0x52: u'\u0052',  # LATIN CAPITAL LETTER R
        0x53: u'\u0053',  # LATIN CAPITAL LETTER S
        0x54: u'\u0054',  # LATIN CAPITAL LETTER T
        0x55: u'\u0055',  # LATIN CAPITAL LETTER U
        0x56: u'\u0056',  # LATIN CAPITAL LETTER V
        0x57: u'\u0057',  # LATIN CAPITAL LETTER W
        0x58: u'\u0058',  # LATIN CAPITAL LETTER X
        0x59: u'\u0059',  # LATIN CAPITAL LETTER Y
        0x5A: u'\u005A',  # LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  # LEFT SQUARE BRACKET
        0x5C: u'\u005C',  # REVERSE SOLIDUS
        0x5D: u'\u005D',  # RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  # CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  # LOW LINE
        0x60: u'\u0060',  # GRAVE ACCENT
        0x61: u'\u0061',  # LATIN SMALL LETTER A
        0x62: u'\u0062',  # LATIN SMALL LETTER B
        0x63: u'\u0063',  # LATIN SMALL LETTER C
        0x64: u'\u0064',  # LATIN SMALL LETTER D
        0x65: u'\u0065',  # LATIN SMALL LETTER E
        0x66: u'\u0066',  # LATIN SMALL LETTER F
        0x67: u'\u0067',  # LATIN SMALL LETTER G
        0x68: u'\u0068',  # LATIN SMALL LETTER H
        0x69: u'\u0069',  # LATIN SMALL LETTER I
        0x6A: u'\u006A',  # LATIN SMALL LETTER J
        0x6B: u'\u006B',  # LATIN SMALL LETTER K
        0x6C: u'\u006C',  # LATIN SMALL LETTER L
        0x6D: u'\u006D',  # LATIN SMALL LETTER M
        0x6E: u'\u006E',  # LATIN SMALL LETTER N
        0x6F: u'\u006F',  # LATIN SMALL LETTER O
        0x70: u'\u0070',  # LATIN SMALL LETTER P
        0x71: u'\u0071',  # LATIN SMALL LETTER Q
        0x72: u'\u0072',  # LATIN SMALL LETTER R
        0x73: u'\u0073',  # LATIN SMALL LETTER S
        0x74: u'\u0074',  # LATIN SMALL LETTER T
        0x75: u'\u0075',  # LATIN SMALL LETTER U
        0x76: u'\u0076',  # LATIN SMALL LETTER V
        0x77: u'\u0077',  # LATIN SMALL LETTER W
        0x78: u'\u0078',  # LATIN SMALL LETTER X
        0x79: u'\u0079',  # LATIN SMALL LETTER Y
        0x7A: u'\u007A',  # LATIN SMALL LETTER Z
        0x7B: u'\u007B',  # LEFT CURLY BRACKET
        0x7C: u'\u007C',  # VERTICAL LINE
        0x7D: u'\u007D',  # RIGHT CURLY BRACKET
        0x7E: u'\u007E',  # TILDE
        0x7F: u'\u007F',  # DELETE
        0x82: u'\u00E9',  # LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u00E2',  # LATIN SMALL LETTER A WITH CIRCUMFLEX
        0x85: u'\u00E0',  # LATIN SMALL LETTER A WITH GRAVE
        0x87: u'\u00E7',  # LATIN SMALL LETTER C WITH CEDILLA
        0x88: u'\u00EA',  # LATIN SMALL LETTER E WITH CIRCUMFLEX
        0x89: u'\u00EB',  # LATIN SMALL LETTER E WITH DIAERESIS
        0x8A: u'\u00E8',  # LATIN SMALL LETTER E WITH GRAVE
        0x8B: u'\u00EF',  # LATIN SMALL LETTER I WITH DIAERESIS
        0x8C: u'\u00EE',  # LATIN SMALL LETTER I WITH CIRCUMFLEX
        0x91: u'\u0651',  # ARABIC SHADDA
        0x92: u'\u0652',  # ARABIC SUKUN
        0x93: u'\u00F4',  # LATIN SMALL LETTER O WITH CIRCUMFLEX
        0x94: u'\u00A4',  # CURRENCY SIGN
        0x95: u'\u0640',  # ARABIC TATWEEL
        0x96: u'\u00FB',  # LATIN SMALL LETTER U WITH CIRCUMFLEX
        0x97: u'\u00F9',  # LATIN SMALL LETTER U WITH GRAVE
        0x98: u'\u0621',  # ARABIC LETTER HAMZA
        0x99: u'\u0622',  # ARABIC LETTER ALEF WITH MADDA ABOVE
        0x9A: u'\u0623',  # ARABIC LETTER ALEF WITH HAMZA ABOVE
        0x9B: u'\u0624',  # ARABIC LETTER WAW WITH HAMZA ABOVE
        0x9C: u'\u00A3',  # POUND SIGN
        0x9D: u'\u0625',  # ARABIC LETTER ALEF WITH HAMZA BELOW
        0x9E: u'\u0626',  # ARABIC LETTER YEH WITH HAMZA ABOVE
        0x9F: u'\u0627',  # ARABIC LETTER ALEF
        0xA0: u'\u0628',  # ARABIC LETTER BEH
        0xA1: u'\u0629',  # ARABIC LETTER TEH MARBUTA
        0xA2: u'\u062A',  # ARABIC LETTER TEH
        0xA3: u'\u062B',  # ARABIC LETTER THEH
        0xA4: u'\u062C',  # ARABIC LETTER JEEM
        0xA5: u'\u062D',  # ARABIC LETTER HAH
        0xA6: u'\u062E',  # ARABIC LETTER KHAH
        0xA7: u'\u062F',  # ARABIC LETTER DAL
        0xA8: u'\u0630',  # ARABIC LETTER THAL
        0xA9: u'\u0631',  # ARABIC LETTER REH
        0xAA: u'\u0632',  # ARABIC LETTER ZAIN
        0xAB: u'\u0633',  # ARABIC LETTER SEEN
        0xAC: u'\u0634',  # ARABIC LETTER SHEEN
        0xAD: u'\u0635',  # ARABIC LETTER SAD
        0xAE: u'\u00AB',  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  # LIGHT SHADE
        0xB1: u'\u2592',  # MEDIUM SHADE
        0xB2: u'\u2593',  # DARK SHADE
        0xB3: u'\u2502',  # BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  # BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u2561',  # BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE
        0xB6: u'\u2562',  # BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE
        0xB7: u'\u2556',  # BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE
        0xB8: u'\u2555',  # BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE
        0xB9: u'\u2563',  # BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  # BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  # BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  # BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u255C',  # BOX DRAWINGS UP DOUBLE AND LEFT SINGLE
        0xBE: u'\u255B',  # BOX DRAWINGS UP SINGLE AND LEFT DOUBLE
        0xBF: u'\u2510',  # BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  # BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  # BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  # BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  # BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  # BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  # BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u255E',  # BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE
        0xC7: u'\u255F',  # BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE
        0xC8: u'\u255A',  # BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  # BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  # BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  # BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  # BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  # BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  # BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u2567',  # BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE
        0xD0: u'\u2568',  # BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE
        0xD1: u'\u2564',  # BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE
        0xD2: u'\u2565',  # BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE
        0xD3: u'\u2559',  # BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE
        0xD4: u'\u2558',  # BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE
        0xD5: u'\u2552',  # BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE
        0xD6: u'\u2553',  # BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE
        0xD7: u'\u256B',  # BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE
        0xD8: u'\u256A',  # BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE
        0xD9: u'\u2518',  # BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  # BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  # FULL BLOCK
        0xDC: u'\u2584',  # LOWER HALF BLOCK
        0xDD: u'\u258C',  # LEFT HALF BLOCK
        0xDE: u'\u2590',  # RIGHT HALF BLOCK
        0xDF: u'\u2580',  # UPPER HALF BLOCK
        0xE0: u'\u0636',  # ARABIC LETTER DAD
        0xE1: u'\u0637',  # ARABIC LETTER TAH
        0xE2: u'\u0638',  # ARABIC LETTER ZAH
        0xE3: u'\u0639',  # ARABIC LETTER AIN
        0xE4: u'\u063A',  # ARABIC LETTER GHAIN
        0xE5: u'\u0641',  # ARABIC LETTER FEH
        0xE6: u'\u00B5',  # MICRO SIGN
        0xE7: u'\u0642',  # ARABIC LETTER QAF
        0xE8: u'\u0643',  # ARABIC LETTER KAF
        0xE9: u'\u0644',  # ARABIC LETTER LAM
        0xEA: u'\u0645',  # ARABIC LETTER MEEM
        0xEB: u'\u0646',  # ARABIC LETTER NOON
        0xEC: u'\u0647',  # ARABIC LETTER HEH
        0xED: u'\u0648',  # ARABIC LETTER WAW
        0xEE: u'\u0649',  # ARABIC LETTER ALEF MAKSURA
        0xEF: u'\u064A',  # ARABIC LETTER YEH
        0xF0: u'\u2261',  # IDENTICAL TO
        0xF1: u'\u064B',  # ARABIC FATHATAN
        0xF2: u'\u064C',  # ARABIC DAMMATAN
        0xF3: u'\u064D',  # ARABIC KASRATAN
        0xF4: u'\u064E',  # ARABIC FATHA
        0xF5: u'\u064F',  # ARABIC DAMMA
        0xF6: u'\u0650',  # ARABIC KASRA
        0xF7: u'\u2248',  # ALMOST EQUAL TO
        0xF8: u'\u00B0',  # DEGREE SIGN
        0xF9: u'\u2219',  # BULLET OPERATOR
        0xFA: u'\u00B7',  # MIDDLE DOT
        0xFB: u'\u221A',  # SQUARE ROOT
        0xFC: u'\u207F',  # SUPERSCRIPT LATIN SMALL LETTER N
        0xFD: u'\u00B2',  # SUPERSCRIPT TWO
        0xFE: u'\u25A0',  # BLACK SQUARE
        0xFF: u'\u00A0',  # NO-BREAK SPACE
    },
    737: {
        0x00: u'\u0000',  # NULL
        0x01: u'\u0001',  # START OF HEADING
        0x02: u'\u0002',  # START OF TEXT
        0x03: u'\u0003',  # END OF TEXT
        0x04: u'\u0004',  # END OF TRANSMISSION
        0x05: u'\u0005',  # ENQUIRY
        0x06: u'\u0006',  # ACKNOWLEDGE
        0x07: u'\u0007',  # BELL
        0x08: u'\u0008',  # BACKSPACE
        0x09: u'\u0009',  # HORIZONTAL TABULATION
        0x0A: u'\u000A',  # LINE FEED
        0x0B: u'\u000B',  # VERTICAL TABULATION
        0x0C: u'\u000C',  # FORM FEED
        0x0D: u'\u000D',  # CARRIAGE RETURN
        0x0E: u'\u000E',  # SHIFT OUT
        0x0F: u'\u000F',  # SHIFT IN
        0x10: u'\u0010',  # DATA LINK ESCAPE
        0x11: u'\u0011',  # DEVICE CONTROL ONE
        0x12: u'\u0012',  # DEVICE CONTROL TWO
        0x13: u'\u0013',  # DEVICE CONTROL THREE
        0x14: u'\u0014',  # DEVICE CONTROL FOUR
        0x15: u'\u0015',  # NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  # SYNCHRONOUS IDLE
        0x17: u'\u0017',  # END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  # CANCEL
        0x19: u'\u0019',  # END OF MEDIUM
        0x1A: u'\u001A',  # SUBSTITUTE
        0x1B: u'\u001B',  # ESCAPE
        0x1C: u'\u001C',  # FILE SEPARATOR
        0x1D: u'\u001D',  # GROUP SEPARATOR
        0x1E: u'\u001E',  # RECORD SEPARATOR
        0x1F: u'\u001F',  # UNIT SEPARATOR
        0x20: u'\u0020',  # SPACE
        0x21: u'\u0021',  # EXCLAMATION MARK
        0x22: u'\u0022',  # QUOTATION MARK
        0x23: u'\u0023',  # NUMBER SIGN
        0x24: u'\u0024',  # DOLLAR SIGN
        0x25: u'\u0025',  # PERCENT SIGN
        0x26: u'\u0026',  # AMPERSAND
        0x27: u'\u0027',  # APOSTROPHE
        0x28: u'\u0028',  # LEFT PARENTHESIS
        0x29: u'\u0029',  # RIGHT PARENTHESIS
        0x2A: u'\u002A',  # ASTERISK
        0x2B: u'\u002B',  # PLUS SIGN
        0x2C: u'\u002C',  # COMMA
        0x2D: u'\u002D',  # HYPHEN-MINUS
        0x2E: u'\u002E',  # FULL STOP
        0x2F: u'\u002F',  # SOLIDUS
        0x30: u'\u0030',  # DIGIT ZERO
        0x31: u'\u0031',  # DIGIT ONE
        0x32: u'\u0032',  # DIGIT TWO
        0x33: u'\u0033',  # DIGIT THREE
        0x34: u'\u0034',  # DIGIT FOUR
        0x35: u'\u0035',  # DIGIT FIVE
        0x36: u'\u0036',  # DIGIT SIX
        0x37: u'\u0037',  # DIGIT SEVEN
        0x38: u'\u0038',  # DIGIT EIGHT
        0x39: u'\u0039',  # DIGIT NINE
        0x3A: u'\u003A',  # COLON
        0x3B: u'\u003B',  # SEMICOLON
        0x3C: u'\u003C',  # LESS-THAN SIGN
        0x3D: u'\u003D',  # EQUALS SIGN
        0x3E: u'\u003E',  # GREATER-THAN SIGN
        0x3F: u'\u003F',  # QUESTION MARK
        0x40: u'\u0040',  # COMMERCIAL AT
        0x41: u'\u0041',  # LATIN CAPITAL LETTER A
        0x42: u'\u0042',  # LATIN CAPITAL LETTER B
        0x43: u'\u0043',  # LATIN CAPITAL LETTER C
        0x44: u'\u0044',  # LATIN CAPITAL LETTER D
        0x45: u'\u0045',  # LATIN CAPITAL LETTER E
        0x46: u'\u0046',  # LATIN CAPITAL LETTER F
        0x47: u'\u0047',  # LATIN CAPITAL LETTER G
        0x48: u'\u0048',  # LATIN CAPITAL LETTER H
        0x49: u'\u0049',  # LATIN CAPITAL LETTER I
        0x4A: u'\u004A',  # LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  # LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  # LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  # LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  # LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  # LATIN CAPITAL LETTER O
        0x50: u'\u0050',  # LATIN CAPITAL LETTER P
        0x51: u'\u0051',  # LATIN CAPITAL LETTER Q
        0x52: u'\u0052',  # LATIN CAPITAL LETTER R
        0x53: u'\u0053',  # LATIN CAPITAL LETTER S
        0x54: u'\u0054',  # LATIN CAPITAL LETTER T
        0x55: u'\u0055',  # LATIN CAPITAL LETTER U
        0x56: u'\u0056',  # LATIN CAPITAL LETTER V
        0x57: u'\u0057',  # LATIN CAPITAL LETTER W
        0x58: u'\u0058',  # LATIN CAPITAL LETTER X
        0x59: u'\u0059',  # LATIN CAPITAL LETTER Y
        0x5A: u'\u005A',  # LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  # LEFT SQUARE BRACKET
        0x5C: u'\u005C',  # REVERSE SOLIDUS
        0x5D: u'\u005D',  # RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  # CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  # LOW LINE
        0x60: u'\u0060',  # GRAVE ACCENT
        0x61: u'\u0061',  # LATIN SMALL LETTER A
        0x62: u'\u0062',  # LATIN SMALL LETTER B
        0x63: u'\u0063',  # LATIN SMALL LETTER C
        0x64: u'\u0064',  # LATIN SMALL LETTER D
        0x65: u'\u0065',  # LATIN SMALL LETTER E
        0x66: u'\u0066',  # LATIN SMALL LETTER F
        0x67: u'\u0067',  # LATIN SMALL LETTER G
        0x68: u'\u0068',  # LATIN SMALL LETTER H
        0x69: u'\u0069',  # LATIN SMALL LETTER I
        0x6A: u'\u006A',  # LATIN SMALL LETTER J
        0x6B: u'\u006B',  # LATIN SMALL LETTER K
        0x6C: u'\u006C',  # LATIN SMALL LETTER L
        0x6D: u'\u006D',  # LATIN SMALL LETTER M
        0x6E: u'\u006E',  # LATIN SMALL LETTER N
        0x6F: u'\u006F',  # LATIN SMALL LETTER O
        0x70: u'\u0070',  # LATIN SMALL LETTER P
        0x71: u'\u0071',  # LATIN SMALL LETTER Q
        0x72: u'\u0072',  # LATIN SMALL LETTER R
        0x73: u'\u0073',  # LATIN SMALL LETTER S
        0x74: u'\u0074',  # LATIN SMALL LETTER T
        0x75: u'\u0075',  # LATIN SMALL LETTER U
        0x76: u'\u0076',  # LATIN SMALL LETTER V
        0x77: u'\u0077',  # LATIN SMALL LETTER W
        0x78: u'\u0078',  # LATIN SMALL LETTER X
        0x79: u'\u0079',  # LATIN SMALL LETTER Y
        0x7A: u'\u007A',  # LATIN SMALL LETTER Z
        0x7B: u'\u007B',  # LEFT CURLY BRACKET
        0x7C: u'\u007C',  # VERTICAL LINE
        0x7D: u'\u007D',  # RIGHT CURLY BRACKET
        0x7E: u'\u007E',  # TILDE
        0x7F: u'\u007F',  # DELETE
        0x80: u'\u0391',  # GREEK CAPITAL LETTER ALPHA
        0x81: u'\u0392',  # GREEK CAPITAL LETTER BETA
        0x82: u'\u0393',  # GREEK CAPITAL LETTER GAMMA
        0x83: u'\u0394',  # GREEK CAPITAL LETTER DELTA
        0x84: u'\u0395',  # GREEK CAPITAL LETTER EPSILON
        0x85: u'\u0396',  # GREEK CAPITAL LETTER ZETA
        0x86: u'\u0397',  # GREEK CAPITAL LETTER ETA
        0x87: u'\u0398',  # GREEK CAPITAL LETTER THETA
        0x88: u'\u0399',  # GREEK CAPITAL LETTER IOTA
        0x89: u'\u039A',  # GREEK CAPITAL LETTER KAPPA
        0x8A: u'\u039B',  # GREEK CAPITAL LETTER LAMDA
        0x8B: u'\u039C',  # GREEK CAPITAL LETTER MU
        0x8C: u'\u039D',  # GREEK CAPITAL LETTER NU
        0x8D: u'\u039E',  # GREEK CAPITAL LETTER XI
        0x8E: u'\u039F',  # GREEK CAPITAL LETTER OMICRON
        0x8F: u'\u03A0',  # GREEK CAPITAL LETTER PI
        0x90: u'\u03A1',  # GREEK CAPITAL LETTER RHO
        0x91: u'\u03A3',  # GREEK CAPITAL LETTER SIGMA
        0x92: u'\u03A4',  # GREEK CAPITAL LETTER TAU
        0x93: u'\u03A5',  # GREEK CAPITAL LETTER UPSILON
        0x94: u'\u03A6',  # GREEK CAPITAL LETTER PHI
        0x95: u'\u03A7',  # GREEK CAPITAL LETTER CHI
        0x96: u'\u03A8',  # GREEK CAPITAL LETTER PSI
        0x97: u'\u03A9',  # GREEK CAPITAL LETTER OMEGA
        0x98: u'\u03B1',  # GREEK SMALL LETTER ALPHA
        0x99: u'\u03B2',  # GREEK SMALL LETTER BETA
        0x9A: u'\u03B3',  # GREEK SMALL LETTER GAMMA
        0x9B: u'\u03B4',  # GREEK SMALL LETTER DELTA
        0x9C: u'\u03B5',  # GREEK SMALL LETTER EPSILON
        0x9D: u'\u03B6',  # GREEK SMALL LETTER ZETA
        0x9E: u'\u03B7',  # GREEK SMALL LETTER ETA
        0x9F: u'\u03B8',  # GREEK SMALL LETTER THETA
        0xA0: u'\u03B9',  # GREEK SMALL LETTER IOTA
        0xA1: u'\u03BA',  # GREEK SMALL LETTER KAPPA
        0xA2: u'\u03BB',  # GREEK SMALL LETTER LAMDA
        0xA3: u'\u03BC',  # GREEK SMALL LETTER MU
        0xA4: u'\u03BD',  # GREEK SMALL LETTER NU
        0xA5: u'\u03BE',  # GREEK SMALL LETTER XI
        0xA6: u'\u03BF',  # GREEK SMALL LETTER OMICRON
        0xA7: u'\u03C0',  # GREEK SMALL LETTER PI
        0xA8: u'\u03C1',  # GREEK SMALL LETTER RHO
        0xA9: u'\u03C3',  # GREEK SMALL LETTER SIGMA
        0xAA: u'\u03C2',  # GREEK SMALL LETTER FINAL SIGMA
        0xAB: u'\u03C4',  # GREEK SMALL LETTER TAU
        0xAC: u'\u03C5',  # GREEK SMALL LETTER UPSILON
        0xAD: u'\u03C6',  # GREEK SMALL LETTER PHI
        0xAE: u'\u03C7',  # GREEK SMALL LETTER CHI
        0xAF: u'\u03C8',  # GREEK SMALL LETTER PSI
        0xB0: u'\u2591',  # LIGHT SHADE
        0xB1: u'\u2592',  # MEDIUM SHADE
        0xB2: u'\u2593',  # DARK SHADE
        0xB3: u'\u2502',  # BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  # BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u2561',  # BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE
        0xB6: u'\u2562',  # BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE
        0xB7: u'\u2556',  # BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE
        0xB8: u'\u2555',  # BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE
        0xB9: u'\u2563',  # BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  # BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  # BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  # BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u255C',  # BOX DRAWINGS UP DOUBLE AND LEFT SINGLE
        0xBE: u'\u255B',  # BOX DRAWINGS UP SINGLE AND LEFT DOUBLE
        0xBF: u'\u2510',  # BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  # BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  # BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  # BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  # BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  # BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  # BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u255E',  # BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE
        0xC7: u'\u255F',  # BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE
        0xC8: u'\u255A',  # BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  # BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  # BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  # BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  # BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  # BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  # BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u2567',  # BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE
        0xD0: u'\u2568',  # BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE
        0xD1: u'\u2564',  # BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE
        0xD2: u'\u2565',  # BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE
        0xD3: u'\u2559',  # BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE
        0xD4: u'\u2558',  # BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE
        0xD5: u'\u2552',  # BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE
        0xD6: u'\u2553',  # BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE
        0xD7: u'\u256B',  # BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE
        0xD8: u'\u256A',  # BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE
        0xD9: u'\u2518',  # BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  # BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  # FULL BLOCK
        0xDC: u'\u2584',  # LOWER HALF BLOCK
        0xDD: u'\u258C',  # LEFT HALF BLOCK
        0xDE: u'\u2590',  # RIGHT HALF BLOCK
        0xDF: u'\u2580',  # UPPER HALF BLOCK
        0xE0: u'\u03C9',  # GREEK SMALL LETTER OMEGA
        0xE1: u'\u03AC',  # GREEK SMALL LETTER ALPHA WITH TONOS
        0xE2: u'\u03AD',  # GREEK SMALL LETTER EPSILON WITH TONOS
        0xE3: u'\u03AE',  # GREEK SMALL LETTER ETA WITH TONOS
        0xE4: u'\u03CA',  # GREEK SMALL LETTER IOTA WITH DIALYTIKA
        0xE5: u'\u03AF',  # GREEK SMALL LETTER IOTA WITH TONOS
        0xE6: u'\u03CC',  # GREEK SMALL LETTER OMICRON WITH TONOS
        0xE7: u'\u03CD',  # GREEK SMALL LETTER UPSILON WITH TONOS
        0xE8: u'\u03CB',  # GREEK SMALL LETTER UPSILON WITH DIALYTIKA
        0xE9: u'\u03CE',  # GREEK SMALL LETTER OMEGA WITH TONOS
        0xEA: u'\u0386',  # GREEK CAPITAL LETTER ALPHA WITH TONOS
        0xEB: u'\u0388',  # GREEK CAPITAL LETTER EPSILON WITH TONOS
        0xEC: u'\u0389',  # GREEK CAPITAL LETTER ETA WITH TONOS
        0xED: u'\u038A',  # GREEK CAPITAL LETTER IOTA WITH TONOS
        0xEE: u'\u038C',  # GREEK CAPITAL LETTER OMICRON WITH TONOS
        0xEF: u'\u038E',  # GREEK CAPITAL LETTER UPSILON WITH TONOS
        0xF0: u'\u038F',  # GREEK CAPITAL LETTER OMEGA WITH TONOS
        0xF1: u'\u00B1',  # PLUS-MINUS SIGN
        0xF2: u'\u2265',  # GREATER-THAN OR EQUAL TO
        0xF3: u'\u2264',  # LESS-THAN OR EQUAL TO
        0xF4: u'\u03AA',  # GREEK CAPITAL LETTER IOTA WITH DIALYTIKA
        0xF5: u'\u03AB',  # GREEK CAPITAL LETTER UPSILON WITH DIALYTIKA
        0xF6: u'\u00F7',  # DIVISION SIGN
        0xF7: u'\u2248',  # ALMOST EQUAL TO
        0xF8: u'\u00B0',  # DEGREE SIGN
        0xF9: u'\u2219',  # BULLET OPERATOR
        0xFA: u'\u00B7',  # MIDDLE DOT
        0xFB: u'\u221A',  # SQUARE ROOT
        0xFC: u'\u207F',  # SUPERSCRIPT LATIN SMALL LETTER N
        0xFD: u'\u00B2',  # SUPERSCRIPT TWO
        0xFE: u'\u25A0',  # BLACK SQUARE
        0xFF: u'\u00A0',  # NO-BREAK SPACE
    },
    775: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u0106',  #LATIN CAPITAL LETTER C WITH ACUTE
        0x81: u'\u00FC',  #LATIN SMALL LETTER U WITH DIAERESIS
        0x82: u'\u00E9',  #LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u0101',  #LATIN SMALL LETTER A WITH MACRON
        0x84: u'\u00E4',  #LATIN SMALL LETTER A WITH DIAERESIS
        0x85: u'\u0123',  #LATIN SMALL LETTER G WITH CEDILLA
        0x86: u'\u00E5',  #LATIN SMALL LETTER A WITH RING ABOVE
        0x87: u'\u0107',  #LATIN SMALL LETTER C WITH ACUTE
        0x88: u'\u0142',  #LATIN SMALL LETTER L WITH STROKE
        0x89: u'\u0113',  #LATIN SMALL LETTER E WITH MACRON
        0x8A: u'\u0156',  #LATIN CAPITAL LETTER R WITH CEDILLA
        0x8B: u'\u0157',  #LATIN SMALL LETTER R WITH CEDILLA
        0x8C: u'\u012B',  #LATIN SMALL LETTER I WITH MACRON
        0x8D: u'\u0179',  #LATIN CAPITAL LETTER Z WITH ACUTE
        0x8E: u'\u00C4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
        0x8F: u'\u00C5',  #LATIN CAPITAL LETTER A WITH RING ABOVE
        0x90: u'\u00C9',  #LATIN CAPITAL LETTER E WITH ACUTE
        0x91: u'\u00E6',  #LATIN SMALL LETTER AE
        0x92: u'\u00C6',  #LATIN CAPITAL LETTER AE
        0x93: u'\u014D',  #LATIN SMALL LETTER O WITH MACRON
        0x94: u'\u00F6',  #LATIN SMALL LETTER O WITH DIAERESIS
        0x95: u'\u0122',  #LATIN CAPITAL LETTER G WITH CEDILLA
        0x96: u'\u00A2',  #CENT SIGN
        0x97: u'\u015A',  #LATIN CAPITAL LETTER S WITH ACUTE
        0x98: u'\u015B',  #LATIN SMALL LETTER S WITH ACUTE
        0x99: u'\u00D6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
        0x9A: u'\u00DC',  #LATIN CAPITAL LETTER U WITH DIAERESIS
        0x9B: u'\u00F8',  #LATIN SMALL LETTER O WITH STROKE
        0x9C: u'\u00A3',  #POUND SIGN
        0x9D: u'\u00D8',  #LATIN CAPITAL LETTER O WITH STROKE
        0x9E: u'\u00D7',  #MULTIPLICATION SIGN
        0x9F: u'\u00A4',  #CURRENCY SIGN
        0xA0: u'\u0100',  #LATIN CAPITAL LETTER A WITH MACRON
        0xA1: u'\u012A',  #LATIN CAPITAL LETTER I WITH MACRON
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u017B',  #LATIN CAPITAL LETTER Z WITH DOT ABOVE
        0xA4: u'\u017C',  #LATIN SMALL LETTER Z WITH DOT ABOVE
        0xA5: u'\u017A',  #LATIN SMALL LETTER Z WITH ACUTE
        0xA6: u'\u201D',  #RIGHT DOUBLE QUOTATION MARK
        0xA7: u'\u00A6',  #BROKEN BAR
        0xA8: u'\u00A9',  #COPYRIGHT SIGN
        0xA9: u'\u00AE',  #REGISTERED SIGN
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u00BD',  #VULGAR FRACTION ONE HALF
        0xAC: u'\u00BC',  #VULGAR FRACTION ONE QUARTER
        0xAD: u'\u0141',  #LATIN CAPITAL LETTER L WITH STROKE
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u0104',  #LATIN CAPITAL LETTER A WITH OGONEK
        0xB6: u'\u010C',  #LATIN CAPITAL LETTER C WITH CARON
        0xB7: u'\u0118',  #LATIN CAPITAL LETTER E WITH OGONEK
        0xB8: u'\u0116',  #LATIN CAPITAL LETTER E WITH DOT ABOVE
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u012E',  #LATIN CAPITAL LETTER I WITH OGONEK
        0xBE: u'\u0160',  #LATIN CAPITAL LETTER S WITH CARON
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u0172',  #LATIN CAPITAL LETTER U WITH OGONEK
        0xC7: u'\u016A',  #LATIN CAPITAL LETTER U WITH MACRON
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u017D',  #LATIN CAPITAL LETTER Z WITH CARON
        0xD0: u'\u0105',  #LATIN SMALL LETTER A WITH OGONEK
        0xD1: u'\u010D',  #LATIN SMALL LETTER C WITH CARON
        0xD2: u'\u0119',  #LATIN SMALL LETTER E WITH OGONEK
        0xD3: u'\u0117',  #LATIN SMALL LETTER E WITH DOT ABOVE
        0xD4: u'\u012F',  #LATIN SMALL LETTER I WITH OGONEK
        0xD5: u'\u0161',  #LATIN SMALL LETTER S WITH CARON
        0xD6: u'\u0173',  #LATIN SMALL LETTER U WITH OGONEK
        0xD7: u'\u016B',  #LATIN SMALL LETTER U WITH MACRON
        0xD8: u'\u017E',  #LATIN SMALL LETTER Z WITH CARON
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u258C',  #LEFT HALF BLOCK
        0xDE: u'\u2590',  #RIGHT HALF BLOCK
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u00D3',  #LATIN CAPITAL LETTER O WITH ACUTE
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u014C',  #LATIN CAPITAL LETTER O WITH MACRON
        0xE3: u'\u0143',  #LATIN CAPITAL LETTER N WITH ACUTE
        0xE4: u'\u00F5',  #LATIN SMALL LETTER O WITH TILDE
        0xE5: u'\u00D5',  #LATIN CAPITAL LETTER O WITH TILDE
        0xE6: u'\u00B5',  #MICRO SIGN
        0xE7: u'\u0144',  #LATIN SMALL LETTER N WITH ACUTE
        0xE8: u'\u0136',  #LATIN CAPITAL LETTER K WITH CEDILLA
        0xE9: u'\u0137',  #LATIN SMALL LETTER K WITH CEDILLA
        0xEA: u'\u013B',  #LATIN CAPITAL LETTER L WITH CEDILLA
        0xEB: u'\u013C',  #LATIN SMALL LETTER L WITH CEDILLA
        0xEC: u'\u0146',  #LATIN SMALL LETTER N WITH CEDILLA
        0xED: u'\u0112',  #LATIN CAPITAL LETTER E WITH MACRON
        0xEE: u'\u0145',  #LATIN CAPITAL LETTER N WITH CEDILLA
        0xEF: u'\u2019',  #RIGHT SINGLE QUOTATION MARK
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u00B1',  #PLUS-MINUS SIGN
        0xF2: u'\u201C',  #LEFT DOUBLE QUOTATION MARK
        0xF3: u'\u00BE',  #VULGAR FRACTION THREE QUARTERS
        0xF4: u'\u00B6',  #PILCROW SIGN
        0xF5: u'\u00A7',  #SECTION SIGN
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u201E',  #DOUBLE LOW-9 QUOTATION MARK
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u2219',  #BULLET OPERATOR
        0xFA: u'\u00B7',  #MIDDLE DOT
        0xFB: u'\u00B9',  #SUPERSCRIPT ONE
        0xFC: u'\u00B3',  #SUPERSCRIPT THREE
        0xFD: u'\u00B2',  #SUPERSCRIPT TWO
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    852: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u00C7',  #LATIN CAPITAL LETTER C WITH CEDILLA
        0x81: u'\u00FC',  #LATIN SMALL LETTER U WITH DIAERESIS
        0x82: u'\u00E9',  #LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u00E2',  #LATIN SMALL LETTER A WITH CIRCUMFLEX
        0x84: u'\u00E4',  #LATIN SMALL LETTER A WITH DIAERESIS
        0x85: u'\u016F',  #LATIN SMALL LETTER U WITH RING ABOVE
        0x86: u'\u0107',  #LATIN SMALL LETTER C WITH ACUTE
        0x87: u'\u00E7',  #LATIN SMALL LETTER C WITH CEDILLA
        0x88: u'\u0142',  #LATIN SMALL LETTER L WITH STROKE
        0x89: u'\u00EB',  #LATIN SMALL LETTER E WITH DIAERESIS
        0x8A: u'\u0150',  #LATIN CAPITAL LETTER O WITH DOUBLE ACUTE
        0x8B: u'\u0151',  #LATIN SMALL LETTER O WITH DOUBLE ACUTE
        0x8C: u'\u00EE',  #LATIN SMALL LETTER I WITH CIRCUMFLEX
        0x8D: u'\u0179',  #LATIN CAPITAL LETTER Z WITH ACUTE
        0x8E: u'\u00C4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
        0x8F: u'\u0106',  #LATIN CAPITAL LETTER C WITH ACUTE
        0x90: u'\u00C9',  #LATIN CAPITAL LETTER E WITH ACUTE
        0x91: u'\u0139',  #LATIN CAPITAL LETTER L WITH ACUTE
        0x92: u'\u013A',  #LATIN SMALL LETTER L WITH ACUTE
        0x93: u'\u00F4',  #LATIN SMALL LETTER O WITH CIRCUMFLEX
        0x94: u'\u00F6',  #LATIN SMALL LETTER O WITH DIAERESIS
        0x95: u'\u013D',  #LATIN CAPITAL LETTER L WITH CARON
        0x96: u'\u013E',  #LATIN SMALL LETTER L WITH CARON
        0x97: u'\u015A',  #LATIN CAPITAL LETTER S WITH ACUTE
        0x98: u'\u015B',  #LATIN SMALL LETTER S WITH ACUTE
        0x99: u'\u00D6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
        0x9A: u'\u00DC',  #LATIN CAPITAL LETTER U WITH DIAERESIS
        0x9B: u'\u0164',  #LATIN CAPITAL LETTER T WITH CARON
        0x9C: u'\u0165',  #LATIN SMALL LETTER T WITH CARON
        0x9D: u'\u0141',  #LATIN CAPITAL LETTER L WITH STROKE
        0x9E: u'\u00D7',  #MULTIPLICATION SIGN
        0x9F: u'\u010D',  #LATIN SMALL LETTER C WITH CARON
        0xA0: u'\u00E1',  #LATIN SMALL LETTER A WITH ACUTE
        0xA1: u'\u00ED',  #LATIN SMALL LETTER I WITH ACUTE
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u00FA',  #LATIN SMALL LETTER U WITH ACUTE
        0xA4: u'\u0104',  #LATIN CAPITAL LETTER A WITH OGONEK
        0xA5: u'\u0105',  #LATIN SMALL LETTER A WITH OGONEK
        0xA6: u'\u017D',  #LATIN CAPITAL LETTER Z WITH CARON
        0xA7: u'\u017E',  #LATIN SMALL LETTER Z WITH CARON
        0xA8: u'\u0118',  #LATIN CAPITAL LETTER E WITH OGONEK
        0xA9: u'\u0119',  #LATIN SMALL LETTER E WITH OGONEK
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u017A',  #LATIN SMALL LETTER Z WITH ACUTE
        0xAC: u'\u010C',  #LATIN CAPITAL LETTER C WITH CARON
        0xAD: u'\u015F',  #LATIN SMALL LETTER S WITH CEDILLA
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u00C1',  #LATIN CAPITAL LETTER A WITH ACUTE
        0xB6: u'\u00C2',  #LATIN CAPITAL LETTER A WITH CIRCUMFLEX
        0xB7: u'\u011A',  #LATIN CAPITAL LETTER E WITH CARON
        0xB8: u'\u015E',  #LATIN CAPITAL LETTER S WITH CEDILLA
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u017B',  #LATIN CAPITAL LETTER Z WITH DOT ABOVE
        0xBE: u'\u017C',  #LATIN SMALL LETTER Z WITH DOT ABOVE
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u0102',  #LATIN CAPITAL LETTER A WITH BREVE
        0xC7: u'\u0103',  #LATIN SMALL LETTER A WITH BREVE
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u00A4',  #CURRENCY SIGN
        0xD0: u'\u0111',  #LATIN SMALL LETTER D WITH STROKE
        0xD1: u'\u0110',  #LATIN CAPITAL LETTER D WITH STROKE
        0xD2: u'\u010E',  #LATIN CAPITAL LETTER D WITH CARON
        0xD3: u'\u00CB',  #LATIN CAPITAL LETTER E WITH DIAERESIS
        0xD4: u'\u010F',  #LATIN SMALL LETTER D WITH CARON
        0xD5: u'\u0147',  #LATIN CAPITAL LETTER N WITH CARON
        0xD6: u'\u00CD',  #LATIN CAPITAL LETTER I WITH ACUTE
        0xD7: u'\u00CE',  #LATIN CAPITAL LETTER I WITH CIRCUMFLEX
        0xD8: u'\u011B',  #LATIN SMALL LETTER E WITH CARON
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u0162',  #LATIN CAPITAL LETTER T WITH CEDILLA
        0xDE: u'\u016E',  #LATIN CAPITAL LETTER U WITH RING ABOVE
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u00D3',  #LATIN CAPITAL LETTER O WITH ACUTE
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u00D4',  #LATIN CAPITAL LETTER O WITH CIRCUMFLEX
        0xE3: u'\u0143',  #LATIN CAPITAL LETTER N WITH ACUTE
        0xE4: u'\u0144',  #LATIN SMALL LETTER N WITH ACUTE
        0xE5: u'\u0148',  #LATIN SMALL LETTER N WITH CARON
        0xE6: u'\u0160',  #LATIN CAPITAL LETTER S WITH CARON
        0xE7: u'\u0161',  #LATIN SMALL LETTER S WITH CARON
        0xE8: u'\u0154',  #LATIN CAPITAL LETTER R WITH ACUTE
        0xE9: u'\u00DA',  #LATIN CAPITAL LETTER U WITH ACUTE
        0xEA: u'\u0155',  #LATIN SMALL LETTER R WITH ACUTE
        0xEB: u'\u0170',  #LATIN CAPITAL LETTER U WITH DOUBLE ACUTE
        0xEC: u'\u00FD',  #LATIN SMALL LETTER Y WITH ACUTE
        0xED: u'\u00DD',  #LATIN CAPITAL LETTER Y WITH ACUTE
        0xEE: u'\u0163',  #LATIN SMALL LETTER T WITH CEDILLA
        0xEF: u'\u00B4',  #ACUTE ACCENT
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u02DD',  #DOUBLE ACUTE ACCENT
        0xF2: u'\u02DB',  #OGONEK
        0xF3: u'\u02C7',  #CARON
        0xF4: u'\u02D8',  #BREVE
        0xF5: u'\u00A7',  #SECTION SIGN
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u00B8',  #CEDILLA
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u00A8',  #DIAERESIS
        0xFA: u'\u02D9',  #DOT ABOVE
        0xFB: u'\u0171',  #LATIN SMALL LETTER U WITH DOUBLE ACUTE
        0xFC: u'\u0158',  #LATIN CAPITAL LETTER R WITH CARON
        0xFD: u'\u0159',  #LATIN SMALL LETTER R WITH CARON
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    855: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u0452',  #CYRILLIC SMALL LETTER DJE
        0x81: u'\u0402',  #CYRILLIC CAPITAL LETTER DJE
        0x82: u'\u0453',  #CYRILLIC SMALL LETTER GJE
        0x83: u'\u0403',  #CYRILLIC CAPITAL LETTER GJE
        0x84: u'\u0451',  #CYRILLIC SMALL LETTER IO
        0x85: u'\u0401',  #CYRILLIC CAPITAL LETTER IO
        0x86: u'\u0454',  #CYRILLIC SMALL LETTER UKRAINIAN IE
        0x87: u'\u0404',  #CYRILLIC CAPITAL LETTER UKRAINIAN IE
        0x88: u'\u0455',  #CYRILLIC SMALL LETTER DZE
        0x89: u'\u0405',  #CYRILLIC CAPITAL LETTER DZE
        0x8A: u'\u0456',  #CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
        0x8B: u'\u0406',  #CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
        0x8C: u'\u0457',  #CYRILLIC SMALL LETTER YI
        0x8D: u'\u0407',  #CYRILLIC CAPITAL LETTER YI
        0x8E: u'\u0458',  #CYRILLIC SMALL LETTER JE
        0x8F: u'\u0408',  #CYRILLIC CAPITAL LETTER JE
        0x90: u'\u0459',  #CYRILLIC SMALL LETTER LJE
        0x91: u'\u0409',  #CYRILLIC CAPITAL LETTER LJE
        0x92: u'\u045A',  #CYRILLIC SMALL LETTER NJE
        0x93: u'\u040A',  #CYRILLIC CAPITAL LETTER NJE
        0x94: u'\u045B',  #CYRILLIC SMALL LETTER TSHE
        0x95: u'\u040B',  #CYRILLIC CAPITAL LETTER TSHE
        0x96: u'\u045C',  #CYRILLIC SMALL LETTER KJE
        0x97: u'\u040C',  #CYRILLIC CAPITAL LETTER KJE
        0x98: u'\u045E',  #CYRILLIC SMALL LETTER SHORT U
        0x99: u'\u040E',  #CYRILLIC CAPITAL LETTER SHORT U
        0x9A: u'\u045F',  #CYRILLIC SMALL LETTER DZHE
        0x9B: u'\u040F',  #CYRILLIC CAPITAL LETTER DZHE
        0x9C: u'\u044E',  #CYRILLIC SMALL LETTER YU
        0x9D: u'\u042E',  #CYRILLIC CAPITAL LETTER YU
        0x9E: u'\u044A',  #CYRILLIC SMALL LETTER HARD SIGN
        0x9F: u'\u042A',  #CYRILLIC CAPITAL LETTER HARD SIGN
        0xA0: u'\u0430',  #CYRILLIC SMALL LETTER A
        0xA1: u'\u0410',  #CYRILLIC CAPITAL LETTER A
        0xA2: u'\u0431',  #CYRILLIC SMALL LETTER BE
        0xA3: u'\u0411',  #CYRILLIC CAPITAL LETTER BE
        0xA4: u'\u0446',  #CYRILLIC SMALL LETTER TSE
        0xA5: u'\u0426',  #CYRILLIC CAPITAL LETTER TSE
        0xA6: u'\u0434',  #CYRILLIC SMALL LETTER DE
        0xA7: u'\u0414',  #CYRILLIC CAPITAL LETTER DE
        0xA8: u'\u0435',  #CYRILLIC SMALL LETTER IE
        0xA9: u'\u0415',  #CYRILLIC CAPITAL LETTER IE
        0xAA: u'\u0444',  #CYRILLIC SMALL LETTER EF
        0xAB: u'\u0424',  #CYRILLIC CAPITAL LETTER EF
        0xAC: u'\u0433',  #CYRILLIC SMALL LETTER GHE
        0xAD: u'\u0413',  #CYRILLIC CAPITAL LETTER GHE
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u0445',  #CYRILLIC SMALL LETTER HA
        0xB6: u'\u0425',  #CYRILLIC CAPITAL LETTER HA
        0xB7: u'\u0438',  #CYRILLIC SMALL LETTER I
        0xB8: u'\u0418',  #CYRILLIC CAPITAL LETTER I
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u0439',  #CYRILLIC SMALL LETTER SHORT I
        0xBE: u'\u0419',  #CYRILLIC CAPITAL LETTER SHORT I
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u043A',  #CYRILLIC SMALL LETTER KA
        0xC7: u'\u041A',  #CYRILLIC CAPITAL LETTER KA
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u00A4',  #CURRENCY SIGN
        0xD0: u'\u043B',  #CYRILLIC SMALL LETTER EL
        0xD1: u'\u041B',  #CYRILLIC CAPITAL LETTER EL
        0xD2: u'\u043C',  #CYRILLIC SMALL LETTER EM
        0xD3: u'\u041C',  #CYRILLIC CAPITAL LETTER EM
        0xD4: u'\u043D',  #CYRILLIC SMALL LETTER EN
        0xD5: u'\u041D',  #CYRILLIC CAPITAL LETTER EN
        0xD6: u'\u043E',  #CYRILLIC SMALL LETTER O
        0xD7: u'\u041E',  #CYRILLIC CAPITAL LETTER O
        0xD8: u'\u043F',  #CYRILLIC SMALL LETTER PE
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u041F',  #CYRILLIC CAPITAL LETTER PE
        0xDE: u'\u044F',  #CYRILLIC SMALL LETTER YA
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u042F',  #CYRILLIC CAPITAL LETTER YA
        0xE1: u'\u0440',  #CYRILLIC SMALL LETTER ER
        0xE2: u'\u0420',  #CYRILLIC CAPITAL LETTER ER
        0xE3: u'\u0441',  #CYRILLIC SMALL LETTER ES
        0xE4: u'\u0421',  #CYRILLIC CAPITAL LETTER ES
        0xE5: u'\u0442',  #CYRILLIC SMALL LETTER TE
        0xE6: u'\u0422',  #CYRILLIC CAPITAL LETTER TE
        0xE7: u'\u0443',  #CYRILLIC SMALL LETTER U
        0xE8: u'\u0423',  #CYRILLIC CAPITAL LETTER U
        0xE9: u'\u0436',  #CYRILLIC SMALL LETTER ZHE
        0xEA: u'\u0416',  #CYRILLIC CAPITAL LETTER ZHE
        0xEB: u'\u0432',  #CYRILLIC SMALL LETTER VE
        0xEC: u'\u0412',  #CYRILLIC CAPITAL LETTER VE
        0xED: u'\u044C',  #CYRILLIC SMALL LETTER SOFT SIGN
        0xEE: u'\u042C',  #CYRILLIC CAPITAL LETTER SOFT SIGN
        0xEF: u'\u2116',  #NUMERO SIGN
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u044B',  #CYRILLIC SMALL LETTER YERU
        0xF2: u'\u042B',  #CYRILLIC CAPITAL LETTER YERU
        0xF3: u'\u0437',  #CYRILLIC SMALL LETTER ZE
        0xF4: u'\u0417',  #CYRILLIC CAPITAL LETTER ZE
        0xF5: u'\u0448',  #CYRILLIC SMALL LETTER SHA
        0xF6: u'\u0428',  #CYRILLIC CAPITAL LETTER SHA
        0xF7: u'\u044D',  #CYRILLIC SMALL LETTER E
        0xF8: u'\u042D',  #CYRILLIC CAPITAL LETTER E
        0xF9: u'\u0449',  #CYRILLIC SMALL LETTER SHCHA
        0xFA: u'\u0429',  #CYRILLIC CAPITAL LETTER SHCHA
        0xFB: u'\u0447',  #CYRILLIC SMALL LETTER CHE
        0xFC: u'\u0427',  #CYRILLIC CAPITAL LETTER CHE
        0xFD: u'\u00A7',  #SECTION SIGN
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    857: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u00C7',  #LATIN CAPITAL LETTER C WITH CEDILLA
        0x81: u'\u00FC',  #LATIN SMALL LETTER U WITH DIAERESIS
        0x82: u'\u00E9',  #LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u00E2',  #LATIN SMALL LETTER A WITH CIRCUMFLEX
        0x84: u'\u00E4',  #LATIN SMALL LETTER A WITH DIAERESIS
        0x85: u'\u00E0',  #LATIN SMALL LETTER A WITH GRAVE
        0x86: u'\u00E5',  #LATIN SMALL LETTER A WITH RING ABOVE
        0x87: u'\u00E7',  #LATIN SMALL LETTER C WITH CEDILLA
        0x88: u'\u00EA',  #LATIN SMALL LETTER E WITH CIRCUMFLEX
        0x89: u'\u00EB',  #LATIN SMALL LETTER E WITH DIAERESIS
        0x8A: u'\u00E8',  #LATIN SMALL LETTER E WITH GRAVE
        0x8B: u'\u00EF',  #LATIN SMALL LETTER I WITH DIAERESIS
        0x8C: u'\u00EE',  #LATIN SMALL LETTER I WITH CIRCUMFLEX
        0x8D: u'\u0131',  #LATIN SMALL LETTER DOTLESS I
        0x8E: u'\u00C4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
        0x8F: u'\u00C5',  #LATIN CAPITAL LETTER A WITH RING ABOVE
        0x90: u'\u00C9',  #LATIN CAPITAL LETTER E WITH ACUTE
        0x91: u'\u00E6',  #LATIN SMALL LETTER AE
        0x92: u'\u00C6',  #LATIN CAPITAL LETTER AE
        0x93: u'\u00F4',  #LATIN SMALL LETTER O WITH CIRCUMFLEX
        0x94: u'\u00F6',  #LATIN SMALL LETTER O WITH DIAERESIS
        0x95: u'\u00F2',  #LATIN SMALL LETTER O WITH GRAVE
        0x96: u'\u00FB',  #LATIN SMALL LETTER U WITH CIRCUMFLEX
        0x97: u'\u00F9',  #LATIN SMALL LETTER U WITH GRAVE
        0x98: u'\u0130',  #LATIN CAPITAL LETTER I WITH DOT ABOVE
        0x99: u'\u00D6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
        0x9A: u'\u00DC',  #LATIN CAPITAL LETTER U WITH DIAERESIS
        0x9B: u'\u00F8',  #LATIN SMALL LETTER O WITH STROKE
        0x9C: u'\u00A3',  #POUND SIGN
        0x9D: u'\u00D8',  #LATIN CAPITAL LETTER O WITH STROKE
        0x9E: u'\u015E',  #LATIN CAPITAL LETTER S WITH CEDILLA
        0x9F: u'\u015F',  #LATIN SMALL LETTER S WITH CEDILLA
        0xA0: u'\u00E1',  #LATIN SMALL LETTER A WITH ACUTE
        0xA1: u'\u00ED',  #LATIN SMALL LETTER I WITH ACUTE
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u00FA',  #LATIN SMALL LETTER U WITH ACUTE
        0xA4: u'\u00F1',  #LATIN SMALL LETTER N WITH TILDE
        0xA5: u'\u00D1',  #LATIN CAPITAL LETTER N WITH TILDE
        0xA6: u'\u011E',  #LATIN CAPITAL LETTER G WITH BREVE
        0xA7: u'\u011F',  #LATIN SMALL LETTER G WITH BREVE
        0xA8: u'\u00BF',  #INVERTED QUESTION MARK
        0xA9: u'\u00AE',  #REGISTERED SIGN
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u00BD',  #VULGAR FRACTION ONE HALF
        0xAC: u'\u00BC',  #VULGAR FRACTION ONE QUARTER
        0xAD: u'\u00A1',  #INVERTED EXCLAMATION MARK
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u00C1',  #LATIN CAPITAL LETTER A WITH ACUTE
        0xB6: u'\u00C2',  #LATIN CAPITAL LETTER A WITH CIRCUMFLEX
        0xB7: u'\u00C0',  #LATIN CAPITAL LETTER A WITH GRAVE
        0xB8: u'\u00A9',  #COPYRIGHT SIGN
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u00A2',  #CENT SIGN
        0xBE: u'\u00A5',  #YEN SIGN
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u00E3',  #LATIN SMALL LETTER A WITH TILDE
        0xC7: u'\u00C3',  #LATIN CAPITAL LETTER A WITH TILDE
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u00A4',  #CURRENCY SIGN
        0xD0: u'\u00BA',  #MASCULINE ORDINAL INDICATOR
        0xD1: u'\u00AA',  #FEMININE ORDINAL INDICATOR
        0xD2: u'\u00CA',  #LATIN CAPITAL LETTER E WITH CIRCUMFLEX
        0xD3: u'\u00CB',  #LATIN CAPITAL LETTER E WITH DIAERESIS
        0xD4: u'\u00C8',  #LATIN CAPITAL LETTER E WITH GRAVE
        0xD6: u'\u00CD',  #LATIN CAPITAL LETTER I WITH ACUTE
        0xD7: u'\u00CE',  #LATIN CAPITAL LETTER I WITH CIRCUMFLEX
        0xD8: u'\u00CF',  #LATIN CAPITAL LETTER I WITH DIAERESIS
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u00A6',  #BROKEN BAR
        0xDE: u'\u00CC',  #LATIN CAPITAL LETTER I WITH GRAVE
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u00D3',  #LATIN CAPITAL LETTER O WITH ACUTE
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u00D4',  #LATIN CAPITAL LETTER O WITH CIRCUMFLEX
        0xE3: u'\u00D2',  #LATIN CAPITAL LETTER O WITH GRAVE
        0xE4: u'\u00F5',  #LATIN SMALL LETTER O WITH TILDE
        0xE5: u'\u00D5',  #LATIN CAPITAL LETTER O WITH TILDE
        0xE6: u'\u00B5',  #MICRO SIGN
        0xE8: u'\u00D7',  #MULTIPLICATION SIGN
        0xE9: u'\u00DA',  #LATIN CAPITAL LETTER U WITH ACUTE
        0xEA: u'\u00DB',  #LATIN CAPITAL LETTER U WITH CIRCUMFLEX
        0xEB: u'\u00D9',  #LATIN CAPITAL LETTER U WITH GRAVE
        0xEC: u'\u00EC',  #LATIN SMALL LETTER I WITH GRAVE
        0xED: u'\u00FF',  #LATIN SMALL LETTER Y WITH DIAERESIS
        0xEE: u'\u00AF',  #MACRON
        0xEF: u'\u00B4',  #ACUTE ACCENT
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u00B1',  #PLUS-MINUS SIGN
        0xF3: u'\u00BE',  #VULGAR FRACTION THREE QUARTERS
        0xF4: u'\u00B6',  #PILCROW SIGN
        0xF5: u'\u00A7',  #SECTION SIGN
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u00B8',  #CEDILLA
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u00A8',  #DIAERESIS
        0xFA: u'\u00B7',  #MIDDLE DOT
        0xFB: u'\u00B9',  #SUPERSCRIPT ONE
        0xFC: u'\u00B3',  #SUPERSCRIPT THREE
        0xFD: u'\u00B2',  #SUPERSCRIPT TWO
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    858: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u00C7',  #LATIN CAPITAL LETTER C WITH CEDILLA
        0x81: u'\u00FC',  #LATIN SMALL LETTER U WITH DIAERESIS
        0x82: u'\u00E9',  #LATIN SMALL LETTER E WITH ACUTE
        0x83: u'\u00E2',  #LATIN SMALL LETTER A WITH CIRCUMFLEX
        0x84: u'\u00E4',  #LATIN SMALL LETTER A WITH DIAERESIS
        0x85: u'\u00E0',  #LATIN SMALL LETTER A WITH GRAVE
        0x86: u'\u00E5',  #LATIN SMALL LETTER A WITH RING ABOVE
        0x87: u'\u00E7',  #LATIN SMALL LETTER C WITH CEDILLA
        0x88: u'\u00EA',  #LATIN SMALL LETTER E WITH CIRCUMFLEX
        0x89: u'\u00EB',  #LATIN SMALL LETTER E WITH DIAERESIS
        0x8A: u'\u00E8',  #LATIN SMALL LETTER E WITH GRAVE
        0x8B: u'\u00EF',  #LATIN SMALL LETTER I WITH DIAERESIS
        0x8C: u'\u00EE',  #LATIN SMALL LETTER I WITH CIRCUMFLEX
        0x8D: u'\u00EC',  #LATIN SMALL LETTER I WITH GRAVE
        0x8E: u'\u00C4',  #LATIN CAPITAL LETTER A WITH DIAERESIS
        0x8F: u'\u00C5',  #LATIN CAPITAL LETTER A WITH RING ABOVE
        0x90: u'\u00C9',  #LATIN CAPITAL LETTER E WITH ACUTE
        0x91: u'\u00E6',  #LATIN SMALL LETTER AE
        0x92: u'\u00C6',  #LATIN CAPITAL LETTER AE
        0x93: u'\u00F4',  #LATIN SMALL LETTER O WITH CIRCUMFLEX
        0x94: u'\u00F6',  #LATIN SMALL LETTER O WITH DIAERESIS
        0x95: u'\u00F2',  #LATIN SMALL LETTER O WITH GRAVE
        0x96: u'\u00FB',  #LATIN SMALL LETTER U WITH CIRCUMFLEX
        0x97: u'\u00F9',  #LATIN SMALL LETTER U WITH GRAVE
        0x98: u'\u00FF',  #LATIN SMALL LETTER Y WITH DIAERESIS
        0x99: u'\u00D6',  #LATIN CAPITAL LETTER O WITH DIAERESIS
        0x9A: u'\u00DC',  #LATIN CAPITAL LETTER U WITH DIAERESIS
        0x9B: u'\u00F8',  #LATIN SMALL LETTER O WITH STROKE
        0x9C: u'\u00A3',  #POUND SIGN
        0x9D: u'\u00D8',  #LATIN CAPITAL LETTER O WITH STROKE
        0x9E: u'\u00D7',  #MULTIPLICATION SIGN
        0x9F: u'\u0192',  #LATIN SMALL LETTER F WITH HOOK
        0xA0: u'\u00E1',  #LATIN SMALL LETTER A WITH ACUTE
        0xA1: u'\u00ED',  #LATIN SMALL LETTER I WITH ACUTE
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u00FA',  #LATIN SMALL LETTER U WITH ACUTE
        0xA4: u'\u00F1',  #LATIN SMALL LETTER N WITH TILDE
        0xA5: u'\u00D1',  #LATIN CAPITAL LETTER N WITH TILDE
        0xA6: u'\u00AA',  #FEMININE ORDINAL INDICATOR
        0xA7: u'\u00BA',  #MASCULINE ORDINAL INDICATOR
        0xA8: u'\u00BF',  #INVERTED QUESTION MARK
        0xA9: u'\u00AE',  #REGISTERED SIGN
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u00BD',  #VULGAR FRACTION ONE HALF
        0xAC: u'\u00BC',  #VULGAR FRACTION ONE QUARTER
        0xAD: u'\u00A1',  #INVERTED EXCLAMATION MARK
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u00C1',  #LATIN CAPITAL LETTER A WITH ACUTE
        0xB6: u'\u00C2',  #LATIN CAPITAL LETTER A WITH CIRCUMFLEX
        0xB7: u'\u00C0',  #LATIN CAPITAL LETTER A WITH GRAVE
        0xB8: u'\u00A9',  #COPYRIGHT SIGN
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u00A2',  #CENT SIGN
        0xBE: u'\u00A5',  #YEN SIGN
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u00E3',  #LATIN SMALL LETTER A WITH TILDE
        0xC7: u'\u00C3',  #LATIN CAPITAL LETTER A WITH TILDE
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u00A4',  #CURRENCY SIGN
        0xD0: u'\u00F0',  #LATIN SMALL LETTER ETH
        0xD1: u'\u00D0',  #LATIN CAPITAL LETTER ETH
        0xD2: u'\u00CA',  #LATIN CAPITAL LETTER E WITH CIRCUMFLEX
        0xD3: u'\u00CB',  #LATIN CAPITAL LETTER E WITH DIAERESIS
        0xD4: u'\u00C8',  #LATIN CAPITAL LETTER E WITH GRAVE
        0xD5: u'\u20AC',  #EURO SIGN
        0xD6: u'\u00CD',  #LATIN CAPITAL LETTER I WITH ACUTE
        0xD7: u'\u00CE',  #LATIN CAPITAL LETTER I WITH CIRCUMFLEX
        0xD8: u'\u00CF',  #LATIN CAPITAL LETTER I WITH DIAERESIS
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u00A6',  #BROKEN BAR
        0xDE: u'\u00CC',  #LATIN CAPITAL LETTER I WITH GRAVE
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u00D3',  #LATIN CAPITAL LETTER O WITH ACUTE
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u00D4',  #LATIN CAPITAL LETTER O WITH CIRCUMFLEX
        0xE3: u'\u00D2',  #LATIN CAPITAL LETTER O WITH GRAVE
        0xE4: u'\u00F5',  #LATIN SMALL LETTER O WITH TILDE
        0xE5: u'\u00D5',  #LATIN CAPITAL LETTER O WITH TILDE
        0xE6: u'\u00B5',  #MICRO SIGN
        0xE7: u'\u00FE',  #LATIN SMALL LETTER THORN
        0xE8: u'\u00DE',  #LATIN CAPITAL LETTER THORN
        0xE9: u'\u00DA',  #LATIN CAPITAL LETTER U WITH ACUTE
        0xEA: u'\u00DB',  #LATIN CAPITAL LETTER U WITH CIRCUMFLEX
        0xEB: u'\u00D9',  #LATIN CAPITAL LETTER U WITH GRAVE
        0xEC: u'\u00FD',  #LATIN SMALL LETTER Y WITH ACUTE
        0xED: u'\u00DD',  #LATIN CAPITAL LETTER Y WITH ACUTE
        0xEE: u'\u00AF',  #MACRON
        0xEF: u'\u00B4',  #ACUTE ACCENT
        0xF0: u'\u00AD',  #SOFT HYPHEN
        0xF1: u'\u00B1',  #PLUS-MINUS SIGN
        0xF2: u'\u2017',  #DOUBLE LOW LINE
        0xF3: u'\u00BE',  #VULGAR FRACTION THREE QUARTERS
        0xF4: u'\u00B6',  #PILCROW SIGN
        0xF5: u'\u00A7',  #SECTION SIGN
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u00B8',  #CEDILLA
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u00A8',  #DIAERESIS
        0xFA: u'\u00B7',  #MIDDLE DOT
        0xFB: u'\u00B9',  #SUPERSCRIPT ONE
        0xFC: u'\u00B3',  #SUPERSCRIPT THREE
        0xFD: u'\u00B2',  #SUPERSCRIPT TWO
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    862: {
        0x00: u'\u0000',  #NULL
        0x01: u'\u0001',  #START OF HEADING
        0x02: u'\u0002',  #START OF TEXT
        0x03: u'\u0003',  #END OF TEXT
        0x04: u'\u0004',  #END OF TRANSMISSION
        0x05: u'\u0005',  #ENQUIRY
        0x06: u'\u0006',  #ACKNOWLEDGE
        0x07: u'\u0007',  #BELL
        0x08: u'\u0008',  #BACKSPACE
        0x09: u'\u0009',  #HORIZONTAL TABULATION
        0x0A: u'\u000A',  #LINE FEED
        0x0B: u'\u000B',  #VERTICAL TABULATION
        0x0C: u'\u000C',  #FORM FEED
        0x0D: u'\u000D',  #CARRIAGE RETURN
        0x0E: u'\u000E',  #SHIFT OUT
        0x0F: u'\u000F',  #SHIFT IN
        0x10: u'\u0010',  #DATA LINK ESCAPE
        0x11: u'\u0011',  #DEVICE CONTROL ONE
        0x12: u'\u0012',  #DEVICE CONTROL TWO
        0x13: u'\u0013',  #DEVICE CONTROL THREE
        0x14: u'\u0014',  #DEVICE CONTROL FOUR
        0x15: u'\u0015',  #NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  #SYNCHRONOUS IDLE
        0x17: u'\u0017',  #END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  #CANCEL
        0x19: u'\u0019',  #END OF MEDIUM
        0x1A: u'\u001A',  #SUBSTITUTE
        0x1B: u'\u001B',  #ESCAPE
        0x1C: u'\u001C',  #FILE SEPARATOR
        0x1D: u'\u001D',  #GROUP SEPARATOR
        0x1E: u'\u001E',  #RECORD SEPARATOR
        0x1F: u'\u001F',  #UNIT SEPARATOR
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
        0x2A: u'\u002A',  #ASTERISK
        0x2B: u'\u002B',  #PLUS SIGN
        0x2C: u'\u002C',  #COMMA
        0x2D: u'\u002D',  #HYPHEN-MINUS
        0x2E: u'\u002E',  #FULL STOP
        0x2F: u'\u002F',  #SOLIDUS
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
        0x3A: u'\u003A',  #COLON
        0x3B: u'\u003B',  #SEMICOLON
        0x3C: u'\u003C',  #LESS-THAN SIGN
        0x3D: u'\u003D',  #EQUALS SIGN
        0x3E: u'\u003E',  #GREATER-THAN SIGN
        0x3F: u'\u003F',  #QUESTION MARK
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
        0x4A: u'\u004A',  #LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  #LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  #LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  #LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  #LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  #LATIN CAPITAL LETTER O
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
        0x5A: u'\u005A',  #LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  #LEFT SQUARE BRACKET
        0x5C: u'\u005C',  #REVERSE SOLIDUS
        0x5D: u'\u005D',  #RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  #CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  #LOW LINE
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
        0x6A: u'\u006A',  #LATIN SMALL LETTER J
        0x6B: u'\u006B',  #LATIN SMALL LETTER K
        0x6C: u'\u006C',  #LATIN SMALL LETTER L
        0x6D: u'\u006D',  #LATIN SMALL LETTER M
        0x6E: u'\u006E',  #LATIN SMALL LETTER N
        0x6F: u'\u006F',  #LATIN SMALL LETTER O
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
        0x7A: u'\u007A',  #LATIN SMALL LETTER Z
        0x7B: u'\u007B',  #LEFT CURLY BRACKET
        0x7C: u'\u007C',  #VERTICAL LINE
        0x7D: u'\u007D',  #RIGHT CURLY BRACKET
        0x7E: u'\u007E',  #TILDE
        0x7F: u'\u007F',  #DELETE
        0x80: u'\u05D0',  #HEBREW LETTER ALEF
        0x81: u'\u05D1',  #HEBREW LETTER BET
        0x82: u'\u05D2',  #HEBREW LETTER GIMEL
        0x83: u'\u05D3',  #HEBREW LETTER DALET
        0x84: u'\u05D4',  #HEBREW LETTER HE
        0x85: u'\u05D5',  #HEBREW LETTER VAV
        0x86: u'\u05D6',  #HEBREW LETTER ZAYIN
        0x87: u'\u05D7',  #HEBREW LETTER HET
        0x88: u'\u05D8',  #HEBREW LETTER TET
        0x89: u'\u05D9',  #HEBREW LETTER YOD
        0x8A: u'\u05DA',  #HEBREW LETTER FINAL KAF
        0x8B: u'\u05DB',  #HEBREW LETTER KAF
        0x8C: u'\u05DC',  #HEBREW LETTER LAMED
        0x8D: u'\u05DD',  #HEBREW LETTER FINAL MEM
        0x8E: u'\u05DE',  #HEBREW LETTER MEM
        0x8F: u'\u05DF',  #HEBREW LETTER FINAL NUN
        0x90: u'\u05E0',  #HEBREW LETTER NUN
        0x91: u'\u05E1',  #HEBREW LETTER SAMEKH
        0x92: u'\u05E2',  #HEBREW LETTER AYIN
        0x93: u'\u05E3',  #HEBREW LETTER FINAL PE
        0x94: u'\u05E4',  #HEBREW LETTER PE
        0x95: u'\u05E5',  #HEBREW LETTER FINAL TSADI
        0x96: u'\u05E6',  #HEBREW LETTER TSADI
        0x97: u'\u05E7',  #HEBREW LETTER QOF
        0x98: u'\u05E8',  #HEBREW LETTER RESH
        0x99: u'\u05E9',  #HEBREW LETTER SHIN
        0x9A: u'\u05EA',  #HEBREW LETTER TAV
        0x9B: u'\u00A2',  #CENT SIGN
        0x9C: u'\u00A3',  #POUND SIGN
        0x9D: u'\u00A5',  #YEN SIGN
        0x9E: u'\u20A7',  #PESETA SIGN
        0x9F: u'\u0192',  #LATIN SMALL LETTER F WITH HOOK
        0xA0: u'\u00E1',  #LATIN SMALL LETTER A WITH ACUTE
        0xA1: u'\u00ED',  #LATIN SMALL LETTER I WITH ACUTE
        0xA2: u'\u00F3',  #LATIN SMALL LETTER O WITH ACUTE
        0xA3: u'\u00FA',  #LATIN SMALL LETTER U WITH ACUTE
        0xA4: u'\u00F1',  #LATIN SMALL LETTER N WITH TILDE
        0xA5: u'\u00D1',  #LATIN CAPITAL LETTER N WITH TILDE
        0xA6: u'\u00AA',  #FEMININE ORDINAL INDICATOR
        0xA7: u'\u00BA',  #MASCULINE ORDINAL INDICATOR
        0xA8: u'\u00BF',  #INVERTED QUESTION MARK
        0xA9: u'\u2310',  #REVERSED NOT SIGN
        0xAA: u'\u00AC',  #NOT SIGN
        0xAB: u'\u00BD',  #VULGAR FRACTION ONE HALF
        0xAC: u'\u00BC',  #VULGAR FRACTION ONE QUARTER
        0xAD: u'\u00A1',  #INVERTED EXCLAMATION MARK
        0xAE: u'\u00AB',  #LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xAF: u'\u00BB',  #RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        0xB0: u'\u2591',  #LIGHT SHADE
        0xB1: u'\u2592',  #MEDIUM SHADE
        0xB2: u'\u2593',  #DARK SHADE
        0xB3: u'\u2502',  #BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  #BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u2561',  #BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE
        0xB6: u'\u2562',  #BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE
        0xB7: u'\u2556',  #BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE
        0xB8: u'\u2555',  #BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE
        0xB9: u'\u2563',  #BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  #BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  #BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  #BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u255C',  #BOX DRAWINGS UP DOUBLE AND LEFT SINGLE
        0xBE: u'\u255B',  #BOX DRAWINGS UP SINGLE AND LEFT DOUBLE
        0xBF: u'\u2510',  #BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  #BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  #BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  #BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  #BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  #BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  #BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u255E',  #BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE
        0xC7: u'\u255F',  #BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE
        0xC8: u'\u255A',  #BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  #BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  #BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  #BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  #BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  #BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  #BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u2567',  #BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE
        0xD0: u'\u2568',  #BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE
        0xD1: u'\u2564',  #BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE
        0xD2: u'\u2565',  #BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE
        0xD3: u'\u2559',  #BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE
        0xD4: u'\u2558',  #BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE
        0xD5: u'\u2552',  #BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE
        0xD6: u'\u2553',  #BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE
        0xD7: u'\u256B',  #BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE
        0xD8: u'\u256A',  #BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE
        0xD9: u'\u2518',  #BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  #BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  #FULL BLOCK
        0xDC: u'\u2584',  #LOWER HALF BLOCK
        0xDD: u'\u258C',  #LEFT HALF BLOCK
        0xDE: u'\u2590',  #RIGHT HALF BLOCK
        0xDF: u'\u2580',  #UPPER HALF BLOCK
        0xE0: u'\u03B1',  #GREEK SMALL LETTER ALPHA
        0xE1: u'\u00DF',  #LATIN SMALL LETTER SHARP S
        0xE2: u'\u0393',  #GREEK CAPITAL LETTER GAMMA
        0xE3: u'\u03C0',  #GREEK SMALL LETTER PI
        0xE4: u'\u03A3',  #GREEK CAPITAL LETTER SIGMA
        0xE5: u'\u03C3',  #GREEK SMALL LETTER SIGMA
        0xE6: u'\u00B5',  #MICRO SIGN
        0xE7: u'\u03C4',  #GREEK SMALL LETTER TAU
        0xE8: u'\u03A6',  #GREEK CAPITAL LETTER PHI
        0xE9: u'\u0398',  #GREEK CAPITAL LETTER THETA
        0xEA: u'\u03A9',  #GREEK CAPITAL LETTER OMEGA
        0xEB: u'\u03B4',  #GREEK SMALL LETTER DELTA
        0xEC: u'\u221E',  #INFINITY
        0xED: u'\u03C6',  #GREEK SMALL LETTER PHI
        0xEE: u'\u03B5',  #GREEK SMALL LETTER EPSILON
        0xEF: u'\u2229',  #INTERSECTION
        0xF0: u'\u2261',  #IDENTICAL TO
        0xF1: u'\u00B1',  #PLUS-MINUS SIGN
        0xF2: u'\u2265',  #GREATER-THAN OR EQUAL TO
        0xF3: u'\u2264',  #LESS-THAN OR EQUAL TO
        0xF4: u'\u2320',  #TOP HALF INTEGRAL
        0xF5: u'\u2321',  #BOTTOM HALF INTEGRAL
        0xF6: u'\u00F7',  #DIVISION SIGN
        0xF7: u'\u2248',  #ALMOST EQUAL TO
        0xF8: u'\u00B0',  #DEGREE SIGN
        0xF9: u'\u2219',  #BULLET OPERATOR
        0xFA: u'\u00B7',  #MIDDLE DOT
        0xFB: u'\u221A',  #SQUARE ROOT
        0xFC: u'\u207F',  #SUPERSCRIPT LATIN SMALL LETTER N
        0xFD: u'\u00B2',  #SUPERSCRIPT TWO
        0xFE: u'\u25A0',  #BLACK SQUARE
        0xFF: u'\u00A0',  #NO-BREAK SPACE
    },
    856: {
        0x00: u'\u0000',  # NULL
        0x01: u'\u0001',  # START OF HEADING
        0x02: u'\u0002',  # START OF TEXT
        0x03: u'\u0003',  # END OF TEXT
        0x04: u'\u0004',  # END OF TRANSMISSION
        0x05: u'\u0005',  # ENQUIRY
        0x06: u'\u0006',  # ACKNOWLEDGE
        0x07: u'\u0007',  # BELL
        0x08: u'\u0008',  # BACKSPACE
        0x09: u'\u0009',  # HORIZONTAL TABULATION
        0x0A: u'\u000A',  # LINE FEED
        0x0B: u'\u000B',  # VERTICAL TABULATION
        0x0C: u'\u000C',  # FORM FEED
        0x0D: u'\u000D',  # CARRIAGE RETURN
        0x0E: u'\u000E',  # SHIFT OUT
        0x0F: u'\u000F',  # SHIFT IN
        0x10: u'\u0010',  # DATA LINK ESCAPE
        0x11: u'\u0011',  # DEVICE CONTROL ONE
        0x12: u'\u0012',  # DEVICE CONTROL TWO
        0x13: u'\u0013',  # DEVICE CONTROL THREE
        0x14: u'\u0014',  # DEVICE CONTROL FOUR
        0x15: u'\u0015',  # NEGATIVE ACKNOWLEDGE
        0x16: u'\u0016',  # SYNCHRONOUS IDLE
        0x17: u'\u0017',  # END OF TRANSMISSION BLOCK
        0x18: u'\u0018',  # CANCEL
        0x19: u'\u0019',  # END OF MEDIUM
        0x1A: u'\u001A',  # SUBSTITUTE
        0x1B: u'\u001B',  # ESCAPE
        0x1C: u'\u001C',  # FILE SEPARATOR
        0x1D: u'\u001D',  # GROUP SEPARATOR
        0x1E: u'\u001E',  # RECORD SEPARATOR
        0x1F: u'\u001F',  # UNIT SEPARATOR
        0x20: u'\u0020',  # SPACE
        0x21: u'\u0021',  # EXCLAMATION MARK
        0x22: u'\u0022',  # QUOTATION MARK
        0x23: u'\u0023',  # NUMBER SIGN
        0x24: u'\u0024',  # DOLLAR SIGN
        0x25: u'\u0025',  # PERCENT SIGN
        0x26: u'\u0026',  # AMPERSAND
        0x27: u'\u0027',  # APOSTROPHE
        0x28: u'\u0028',  # LEFT PARENTHESIS
        0x29: u'\u0029',  # RIGHT PARENTHESIS
        0x2A: u'\u002A',  # ASTERISK
        0x2B: u'\u002B',  # PLUS SIGN
        0x2C: u'\u002C',  # COMMA
        0x2D: u'\u002D',  # HYPHEN-MINUS
        0x2E: u'\u002E',  # FULL STOP
        0x2F: u'\u002F',  # SOLIDUS
        0x30: u'\u0030',  # DIGIT ZERO
        0x31: u'\u0031',  # DIGIT ONE
        0x32: u'\u0032',  # DIGIT TWO
        0x33: u'\u0033',  # DIGIT THREE
        0x34: u'\u0034',  # DIGIT FOUR
        0x35: u'\u0035',  # DIGIT FIVE
        0x36: u'\u0036',  # DIGIT SIX
        0x37: u'\u0037',  # DIGIT SEVEN
        0x38: u'\u0038',  # DIGIT EIGHT
        0x39: u'\u0039',  # DIGIT NINE
        0x3A: u'\u003A',  # COLON
        0x3B: u'\u003B',  # SEMICOLON
        0x3C: u'\u003C',  # LESS-THAN SIGN
        0x3D: u'\u003D',  # EQUALS SIGN
        0x3E: u'\u003E',  # GREATER-THAN SIGN
        0x3F: u'\u003F',  # QUESTION MARK
        0x40: u'\u0040',  # COMMERCIAL AT
        0x41: u'\u0041',  # LATIN CAPITAL LETTER A
        0x42: u'\u0042',  # LATIN CAPITAL LETTER B
        0x43: u'\u0043',  # LATIN CAPITAL LETTER C
        0x44: u'\u0044',  # LATIN CAPITAL LETTER D
        0x45: u'\u0045',  # LATIN CAPITAL LETTER E
        0x46: u'\u0046',  # LATIN CAPITAL LETTER F
        0x47: u'\u0047',  # LATIN CAPITAL LETTER G
        0x48: u'\u0048',  # LATIN CAPITAL LETTER H
        0x49: u'\u0049',  # LATIN CAPITAL LETTER I
        0x4A: u'\u004A',  # LATIN CAPITAL LETTER J
        0x4B: u'\u004B',  # LATIN CAPITAL LETTER K
        0x4C: u'\u004C',  # LATIN CAPITAL LETTER L
        0x4D: u'\u004D',  # LATIN CAPITAL LETTER M
        0x4E: u'\u004E',  # LATIN CAPITAL LETTER N
        0x4F: u'\u004F',  # LATIN CAPITAL LETTER O
        0x50: u'\u0050',  # LATIN CAPITAL LETTER P
        0x51: u'\u0051',  # LATIN CAPITAL LETTER Q
        0x52: u'\u0052',  # LATIN CAPITAL LETTER R
        0x53: u'\u0053',  # LATIN CAPITAL LETTER S
        0x54: u'\u0054',  # LATIN CAPITAL LETTER T
        0x55: u'\u0055',  # LATIN CAPITAL LETTER U
        0x56: u'\u0056',  # LATIN CAPITAL LETTER V
        0x57: u'\u0057',  # LATIN CAPITAL LETTER W
        0x58: u'\u0058',  # LATIN CAPITAL LETTER X
        0x59: u'\u0059',  # LATIN CAPITAL LETTER Y
        0x5A: u'\u005A',  # LATIN CAPITAL LETTER Z
        0x5B: u'\u005B',  # LEFT SQUARE BRACKET
        0x5C: u'\u005C',  # REVERSE SOLIDUS
        0x5D: u'\u005D',  # RIGHT SQUARE BRACKET
        0x5E: u'\u005E',  # CIRCUMFLEX ACCENT
        0x5F: u'\u005F',  # LOW LINE
        0x60: u'\u0060',  # GRAVE ACCENT
        0x61: u'\u0061',  # LATIN SMALL LETTER A
        0x62: u'\u0062',  # LATIN SMALL LETTER B
        0x63: u'\u0063',  # LATIN SMALL LETTER C
        0x64: u'\u0064',  # LATIN SMALL LETTER D
        0x65: u'\u0065',  # LATIN SMALL LETTER E
        0x66: u'\u0066',  # LATIN SMALL LETTER F
        0x67: u'\u0067',  # LATIN SMALL LETTER G
        0x68: u'\u0068',  # LATIN SMALL LETTER H
        0x69: u'\u0069',  # LATIN SMALL LETTER I
        0x6A: u'\u006A',  # LATIN SMALL LETTER J
        0x6B: u'\u006B',  # LATIN SMALL LETTER K
        0x6C: u'\u006C',  # LATIN SMALL LETTER L
        0x6D: u'\u006D',  # LATIN SMALL LETTER M
        0x6E: u'\u006E',  # LATIN SMALL LETTER N
        0x6F: u'\u006F',  # LATIN SMALL LETTER O
        0x70: u'\u0070',  # LATIN SMALL LETTER P
        0x71: u'\u0071',  # LATIN SMALL LETTER Q
        0x72: u'\u0072',  # LATIN SMALL LETTER R
        0x73: u'\u0073',  # LATIN SMALL LETTER S
        0x74: u'\u0074',  # LATIN SMALL LETTER T
        0x75: u'\u0075',  # LATIN SMALL LETTER U
        0x76: u'\u0076',  # LATIN SMALL LETTER V
        0x77: u'\u0077',  # LATIN SMALL LETTER W
        0x78: u'\u0078',  # LATIN SMALL LETTER X
        0x79: u'\u0079',  # LATIN SMALL LETTER Y
        0x7A: u'\u007A',  # LATIN SMALL LETTER Z
        0x7B: u'\u007B',  # LEFT CURLY BRACKET
        0x7C: u'\u007C',  # VERTICAL LINE
        0x7D: u'\u007D',  # RIGHT CURLY BRACKET
        0x7E: u'\u007E',  # TILDE
        0x7F: u'\u007F',  # DELETE
        0x80: u'\u0410',  # CYRILLIC CAPITAL LETTER A
        0x81: u'\u0411',  # CYRILLIC CAPITAL LETTER BE
        0x82: u'\u0412',  # CYRILLIC CAPITAL LETTER VE
        0x83: u'\u0413',  # CYRILLIC CAPITAL LETTER GHE
        0x84: u'\u0414',  # CYRILLIC CAPITAL LETTER DE
        0x85: u'\u0415',  # CYRILLIC CAPITAL LETTER IE
        0x86: u'\u0416',  # CYRILLIC CAPITAL LETTER ZHE
        0x87: u'\u0417',  # CYRILLIC CAPITAL LETTER ZE
        0x88: u'\u0418',  # CYRILLIC CAPITAL LETTER I
        0x89: u'\u0419',  # CYRILLIC CAPITAL LETTER SHORT I
        0x8A: u'\u041A',  # CYRILLIC CAPITAL LETTER KA
        0x8B: u'\u041B',  # CYRILLIC CAPITAL LETTER EL
        0x8C: u'\u041C',  # CYRILLIC CAPITAL LETTER EM
        0x8D: u'\u041D',  # CYRILLIC CAPITAL LETTER EN
        0x8E: u'\u041E',  # CYRILLIC CAPITAL LETTER O
        0x8F: u'\u041F',  # CYRILLIC CAPITAL LETTER PE
        0x90: u'\u0420',  # CYRILLIC CAPITAL LETTER ER
        0x91: u'\u0421',  # CYRILLIC CAPITAL LETTER ES
        0x92: u'\u0422',  # CYRILLIC CAPITAL LETTER TE
        0x93: u'\u0423',  # CYRILLIC CAPITAL LETTER U
        0x94: u'\u0424',  # CYRILLIC CAPITAL LETTER EF
        0x95: u'\u0425',  # CYRILLIC CAPITAL LETTER HA
        0x96: u'\u0426',  # CYRILLIC CAPITAL LETTER TSE
        0x97: u'\u0427',  # CYRILLIC CAPITAL LETTER CHE
        0x98: u'\u0428',  # CYRILLIC CAPITAL LETTER SHA
        0x99: u'\u0429',  # CYRILLIC CAPITAL LETTER SHCHA
        0x9A: u'\u042A',  # CYRILLIC CAPITAL LETTER HARD SIGN
        0x9B: u'\u042B',  # CYRILLIC CAPITAL LETTER YERU
        0x9C: u'\u042C',  # CYRILLIC CAPITAL LETTER SOFT SIGN
        0x9D: u'\u042D',  # CYRILLIC CAPITAL LETTER E
        0x9E: u'\u042E',  # CYRILLIC CAPITAL LETTER YU
        0x9F: u'\u042F',  # CYRILLIC CAPITAL LETTER YA
        0xA0: u'\u0430',  # CYRILLIC SMALL LETTER A
        0xA1: u'\u0431',  # CYRILLIC SMALL LETTER BE
        0xA2: u'\u0432',  # CYRILLIC SMALL LETTER VE
        0xA3: u'\u0433',  # CYRILLIC SMALL LETTER GHE
        0xA4: u'\u0434',  # CYRILLIC SMALL LETTER DE
        0xA5: u'\u0435',  # CYRILLIC SMALL LETTER IE
        0xA6: u'\u0436',  # CYRILLIC SMALL LETTER ZHE
        0xA7: u'\u0437',  # CYRILLIC SMALL LETTER ZE
        0xA8: u'\u0438',  # CYRILLIC SMALL LETTER I
        0xA9: u'\u0439',  # CYRILLIC SMALL LETTER SHORT I
        0xAA: u'\u043A',  # CYRILLIC SMALL LETTER KA
        0xAB: u'\u043B',  # CYRILLIC SMALL LETTER EL
        0xAC: u'\u043C',  # CYRILLIC SMALL LETTER EM
        0xAD: u'\u043D',  # CYRILLIC SMALL LETTER EN
        0xAE: u'\u043E',  # CYRILLIC SMALL LETTER O
        0xAF: u'\u043F',  # CYRILLIC SMALL LETTER PE
        0xB0: u'\u2591',  # LIGHT SHADE
        0xB1: u'\u2592',  # MEDIUM SHADE
        0xB2: u'\u2593',  # DARK SHADE
        0xB3: u'\u2502',  # BOX DRAWINGS LIGHT VERTICAL
        0xB4: u'\u2524',  # BOX DRAWINGS LIGHT VERTICAL AND LEFT
        0xB5: u'\u2561',  # BOX DRAWINGS VERTICAL SINGLE AND LEFT DOUBLE
        0xB6: u'\u2562',  # BOX DRAWINGS VERTICAL DOUBLE AND LEFT SINGLE
        0xB7: u'\u2556',  # BOX DRAWINGS DOWN DOUBLE AND LEFT SINGLE
        0xB8: u'\u2555',  # BOX DRAWINGS DOWN SINGLE AND LEFT DOUBLE
        0xB9: u'\u2563',  # BOX DRAWINGS DOUBLE VERTICAL AND LEFT
        0xBA: u'\u2551',  # BOX DRAWINGS DOUBLE VERTICAL
        0xBB: u'\u2557',  # BOX DRAWINGS DOUBLE DOWN AND LEFT
        0xBC: u'\u255D',  # BOX DRAWINGS DOUBLE UP AND LEFT
        0xBD: u'\u255C',  # BOX DRAWINGS UP DOUBLE AND LEFT SINGLE
        0xBE: u'\u255B',  # BOX DRAWINGS UP SINGLE AND LEFT DOUBLE
        0xBF: u'\u2510',  # BOX DRAWINGS LIGHT DOWN AND LEFT
        0xC0: u'\u2514',  # BOX DRAWINGS LIGHT UP AND RIGHT
        0xC1: u'\u2534',  # BOX DRAWINGS LIGHT UP AND HORIZONTAL
        0xC2: u'\u252C',  # BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
        0xC3: u'\u251C',  # BOX DRAWINGS LIGHT VERTICAL AND RIGHT
        0xC4: u'\u2500',  # BOX DRAWINGS LIGHT HORIZONTAL
        0xC5: u'\u253C',  # BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
        0xC6: u'\u255E',  # BOX DRAWINGS VERTICAL SINGLE AND RIGHT DOUBLE
        0xC7: u'\u255F',  # BOX DRAWINGS VERTICAL DOUBLE AND RIGHT SINGLE
        0xC8: u'\u255A',  # BOX DRAWINGS DOUBLE UP AND RIGHT
        0xC9: u'\u2554',  # BOX DRAWINGS DOUBLE DOWN AND RIGHT
        0xCA: u'\u2569',  # BOX DRAWINGS DOUBLE UP AND HORIZONTAL
        0xCB: u'\u2566',  # BOX DRAWINGS DOUBLE DOWN AND HORIZONTAL
        0xCC: u'\u2560',  # BOX DRAWINGS DOUBLE VERTICAL AND RIGHT
        0xCD: u'\u2550',  # BOX DRAWINGS DOUBLE HORIZONTAL
        0xCE: u'\u256C',  # BOX DRAWINGS DOUBLE VERTICAL AND HORIZONTAL
        0xCF: u'\u2567',  # BOX DRAWINGS UP SINGLE AND HORIZONTAL DOUBLE
        0xD0: u'\u2568',  # BOX DRAWINGS UP DOUBLE AND HORIZONTAL SINGLE
        0xD1: u'\u2564',  # BOX DRAWINGS DOWN SINGLE AND HORIZONTAL DOUBLE
        0xD2: u'\u2565',  # BOX DRAWINGS DOWN DOUBLE AND HORIZONTAL SINGLE
        0xD3: u'\u2559',  # BOX DRAWINGS UP DOUBLE AND RIGHT SINGLE
        0xD4: u'\u2558',  # BOX DRAWINGS UP SINGLE AND RIGHT DOUBLE
        0xD5: u'\u2552',  # BOX DRAWINGS DOWN SINGLE AND RIGHT DOUBLE
        0xD6: u'\u2553',  # BOX DRAWINGS DOWN DOUBLE AND RIGHT SINGLE
        0xD7: u'\u256B',  # BOX DRAWINGS VERTICAL DOUBLE AND HORIZONTAL SINGLE
        0xD8: u'\u256A',  # BOX DRAWINGS VERTICAL SINGLE AND HORIZONTAL DOUBLE
        0xD9: u'\u2518',  # BOX DRAWINGS LIGHT UP AND LEFT
        0xDA: u'\u250C',  # BOX DRAWINGS LIGHT DOWN AND RIGHT
        0xDB: u'\u2588',  # FULL BLOCK
        0xDC: u'\u2584',  # LOWER HALF BLOCK
        0xDD: u'\u258C',  # LEFT HALF BLOCK
        0xDE: u'\u2590',  # RIGHT HALF BLOCK
        0xDF: u'\u2580',  # UPPER HALF BLOCK
        0xE0: u'\u0440',  # CYRILLIC SMALL LETTER ER
        0xE1: u'\u0441',  # CYRILLIC SMALL LETTER ES
        0xE2: u'\u0442',  # CYRILLIC SMALL LETTER TE
        0xE3: u'\u0443',  # CYRILLIC SMALL LETTER U
        0xE4: u'\u0444',  # CYRILLIC SMALL LETTER EF
        0xE5: u'\u0445',  # CYRILLIC SMALL LETTER HA
        0xE6: u'\u0446',  # CYRILLIC SMALL LETTER TSE
        0xE7: u'\u0447',  # CYRILLIC SMALL LETTER CHE
        0xE8: u'\u0448',  # CYRILLIC SMALL LETTER SHA
        0xE9: u'\u0449',  # CYRILLIC SMALL LETTER SHCHA
        0xEA: u'\u044A',  # CYRILLIC SMALL LETTER HARD SIGN
        0xEB: u'\u044B',  # CYRILLIC SMALL LETTER YERU
        0xEC: u'\u044C',  # CYRILLIC SMALL LETTER SOFT SIGN
        0xED: u'\u044D',  # CYRILLIC SMALL LETTER E
        0xEE: u'\u044E',  # CYRILLIC SMALL LETTER YU
        0xEF: u'\u044F',  # CYRILLIC SMALL LETTER YA
        0xF0: u'\u0401',  # CYRILLIC CAPITAL LETTER IO
        0xF1: u'\u0451',  # CYRILLIC SMALL LETTER IO
        0xF2: u'\u0404',  # CYRILLIC CAPITAL LETTER UKRAINIAN IE
        0xF3: u'\u0454',  # CYRILLIC SMALL LETTER UKRAINIAN IE
        0xF4: u'\u0407',  # CYRILLIC CAPITAL LETTER YI
        0xF5: u'\u0457',  # CYRILLIC SMALL LETTER YI
        0xF6: u'\u040E',  # CYRILLIC CAPITAL LETTER SHORT U
        0xF7: u'\u045E',  # CYRILLIC SMALL LETTER SHORT U
        0xF8: u'\u00B0',  # DEGREE SIGN
        0xF9: u'\u2219',  # BULLET OPERATOR
        0xFA: u'\u00B7',  # MIDDLE DOT
        0xFB: u'\u221A',  # SQUARE ROOT
        0xFC: u'\u2116',  # NUMERO SIGN
        0xFD: u'\u00A4',  # CURRENCY SIGN
        0xFE: u'\u25A0',  # BLACK SQUARE
        0xFF: u'\u00A0',  # NO-BREAK SPACE
    },
}
