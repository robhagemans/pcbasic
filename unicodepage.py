
# Codepage 437 to Unicode table 
# with Special Graphic Characters
# http://en.wikipedia.org/wiki/Code_page_437
# http://msdn.microsoft.com/en-us/library/cc195060.aspx
# http://msdn.microsoft.com/en-us/goglobal/cc305160

import logging
import os

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

def load_codepage(codepage_name):
    global cp_to_unicode, unicode_to_cp, cp_to_utf8, utf8_to_cp
    path = os.path.dirname(os.path.realpath(__file__))
    name = os.path.join(path, 'encoding', codepage_name + '.utf8')
    try:
        f = open(name, 'rb')
        # convert utf8 string to dict
        dict_string = f.read().decode('utf-8')[:128]
        cp_to_unicode = {}
        for i in range(128, 256):
            cp_to_unicode[i] = dict_string[i-128]
    except IOError:
        logging.warning('Could not find unicode mapping table for codepage %s. Falling back to codepage 437.', codepage_name)
        cp_to_unicode = cp437
        codepage_name = '437'
    # update dict with basic ASCII and special graphic characters
    cp_to_unicode.update(ascii)    
    cp_to_unicode.update(special_graphic)    
    unicode_to_cp = dict((reversed(item) for item in cp_to_unicode.items()))
    cp_to_utf8 = dict([ (chr(s[0]), s[1].encode('utf-8')) for s in cp_to_unicode.items()])
    utf8_to_cp = dict((reversed(item) for item in cp_to_utf8.items()))
    return codepage_name  
      
ascii = dict(( (c, unichr(c)) for c in range(127) ))

special_graphic = {
    0x00:   u'\u0000',     0x01:   u'\u263A',      0x02:   u'\u263B',     0x03:   u'\u2665',      0x04:   u'\u2666',    
    0x05:   u'\u2663',     0x06:   u'\u2660',      0x07:   u'\u2022',     0x08:   u'\u25D8',      0x09:   u'\u25CB',      
    0x0a:   u'\u25D9',     0x0b:   u'\u2642',      0x0c:   u'\u2640',     0x0d:   u'\u266A',      0x0e:   u'\u266B',      
    0x0f:   u'\u263C',     0x10:   u'\u25BA',      0x11:   u'\u25C4',     0x12:   u'\u2195',      0x13:   u'\u203C',      
    0x14:   u'\u00B6',     0x15:   u'\u00A7',      0x16:   u'\u25AC',     0x17:   u'\u21A8',      0x18:   u'\u2191',      
    0x19:   u'\u2193',     0x1a:   u'\u2192',      0x1b:   u'\u2190',     0x1c:   u'\u221F',      0x1d:   u'\u2194',     
    0x1e:   u'\u25B2',     0x1f:   u'\u25BC',      0x7f:   u'\u2302',
    }

cp437 = {
    128: u'\xc7', 129: u'\xfc', 130: u'\xe9', 131: u'\xe2', 132: u'\xe4', 133: u'\xe0', 134: u'\xe5', 135: u'\xe7', 
    136: u'\xea', 137: u'\xeb', 138: u'\xe8', 139: u'\xef', 140: u'\xee', 141: u'\xec', 142: u'\xc4', 143: u'\xc5', 
    144: u'\xc9', 145: u'\xe6', 146: u'\xc6', 147: u'\xf4', 148: u'\xf6', 149: u'\xf2', 150: u'\xfb', 151: u'\xf9', 
    152: u'\xff', 153: u'\xd6', 154: u'\xdc', 155: u'\xa2', 156: u'\xa3', 157: u'\xa5', 158: u'\u20a7', 159: u'\u0192', 
    160: u'\xe1', 161: u'\xed', 162: u'\xf3', 163: u'\xfa', 164: u'\xf1', 165: u'\xd1', 166: u'\xaa', 167: u'\xba',
    168: u'\xbf', 169: u'\u2310', 170: u'\xac', 171: u'\xbd', 172: u'\xbc', 173: u'\xa1', 174: u'\xab', 175: u'\xbb',
    176: u'\u2591', 177: u'\u2592', 178: u'\u2593', 179: u'\u2502', 180: u'\u2524', 181: u'\u2561', 182: u'\u2562', 
    183: u'\u2556', 184: u'\u2555', 185: u'\u2563', 186: u'\u2551', 187: u'\u2557', 188: u'\u255d', 189: u'\u255c', 
    190: u'\u255b', 191: u'\u2510', 192: u'\u2514', 193: u'\u2534', 194: u'\u252c', 195: u'\u251c', 196: u'\u2500', 
    197: u'\u253c', 198: u'\u255e', 199: u'\u255f', 200: u'\u255a', 201: u'\u2554', 202: u'\u2569', 203: u'\u2566', 
    204: u'\u2560', 205: u'\u2550', 206: u'\u256c', 207: u'\u2567', 208: u'\u2568', 209: u'\u2564', 210: u'\u2565', 
    211: u'\u2559', 212: u'\u2558', 213: u'\u2552', 214: u'\u2553', 215: u'\u256b', 216: u'\u256a', 217: u'\u2518', 
    218: u'\u250c', 219: u'\u2588', 220: u'\u2584', 221: u'\u258c', 222: u'\u2590', 223: u'\u2580', 224: u'\u03b1', 
    225: u'\xdf', 226: u'\u0393', 227: u'\u03c0', 228: u'\u03a3', 229: u'\u03c3', 230: u'\xb5', 231: u'\u03c4', 
    232: u'\u03a6', 233: u'\u0398', 234: u'\u03a9', 235: u'\u03b4', 236: u'\u221e', 237: u'\u03c6', 238: u'\u03b5', 
    239: u'\u2229', 240: u'\u2261', 241: u'\xb1', 242: u'\u2265', 243: u'\u2264', 244: u'\u2320', 245: u'\u2321', 
    246: u'\xf7', 247: u'\u2248', 248: u'\xb0', 249: u'\u2219', 250: u'\xb7', 251: u'\u221a', 252: u'\u207f', 
    253: u'\xb2', 254: u'\u25a0', 255: u'\xa0'
    }
     
