#
# PC-BASIC 3.23 - pygame_android.py
#
# Graphical console backend based on PyGame - Android-specific
# 
# (c) 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import pygame
import android
import backend_pygame
import state

# unicode returned by pygame for android is incorrect, work around this.
keycode_to_unicode = {
    # these are likely unused
    pygame.K_EXCLAIM     : u'!',    pygame.K_QUOTEDBL    : u'"',    pygame.K_HASH        : u'#',    pygame.K_AMPERSAND   : u'&',       
    pygame.K_LEFTPAREN   : u'(',    pygame.K_RIGHTPAREN  : u')',    pygame.K_ASTERISK    : u'*',    pygame.K_PLUS        : u'+',  
    pygame.K_QUESTION    : u'?',    pygame.K_AT          : u'@',    pygame.K_LESS        : u'<',    pygame.K_GREATER     : u'>',  
    pygame.K_BACKQUOTE   : u'`',    pygame.K_CARET       : u'^',    pygame.K_UNDERSCORE  : u'_',    pygame.K_COLON       : u':',  
    pygame.K_ESCAPE      : u'\x1b', pygame.K_BACKSPACE   : u'\b',   pygame.K_TAB         : u'\t',   pygame.K_RETURN      : u'\r',
    pygame.K_SPACE       : u' ',
    # these are used
    pygame.K_DOLLAR      : u'`',    pygame.K_0           : u'0',    pygame.K_1           : u'1',    pygame.K_2           : u'2',  
    pygame.K_3           : u'3',    pygame.K_4           : u'4',    pygame.K_5           : u'5',    pygame.K_6           : u'6',  
    pygame.K_7           : u'7',    pygame.K_8           : u'8',    pygame.K_9           : u'9',    pygame.K_SEMICOLON   : u';',  
    pygame.K_QUOTE       : u"'",    pygame.K_COMMA       : u',',    pygame.K_MINUS       : u'-',    pygame.K_KP_MINUS    : u'-',  
    pygame.K_PERIOD      : u'.',    pygame.K_SLASH       : u'/',    pygame.K_EQUALS      : u'=',    pygame.K_LEFTBRACKET : u'[',  
    pygame.K_BACKSLASH   : u'\\',   pygame.K_RIGHTBRACKET: u']',    pygame.K_a           : u'a',    pygame.K_b           : u'b',  
    pygame.K_c           : u'c',    pygame.K_d           : u'd',    pygame.K_e           : u'e',    pygame.K_f           : u'f',
    pygame.K_g           : u'g',    pygame.K_h           : u'h',    pygame.K_i           : u'i',    pygame.K_j           : u'j',
    pygame.K_k           : u'k',    pygame.K_l           : u'l',    pygame.K_m           : u'm',    pygame.K_n           : u'n',
    pygame.K_o           : u'o',    pygame.K_p           : u'p',    pygame.K_q           : u'q',    pygame.K_r           : u'r',
    pygame.K_s           : u's',    pygame.K_t           : u't',    pygame.K_u           : u'u',    pygame.K_v           : u'v',
    pygame.K_w           : u'w',    pygame.K_x           : u'x',    pygame.K_y           : u'y',    pygame.K_z           : u'z',
}

# android sends LSHIFT + key according to US keyboard
shift_keycode_to_unicode = {
    pygame.K_ESCAPE      : u'\x1b', pygame.K_BACKSPACE   : u'\b',    pygame.K_TAB         : u'\t',    pygame.K_RETURN      : u'\r',
    pygame.K_SPACE       : u' ',
    #
    pygame.K_DOLLAR      : u'~',    pygame.K_1           : u'!',    pygame.K_2           : u'@',    pygame.K_3           : u'#',
    pygame.K_4           : u'$',    pygame.K_5           : u'%',    pygame.K_6           : u'^',    pygame.K_7           : u'&',       
    pygame.K_8           : u'*',    pygame.K_9           : u'(',    pygame.K_0           : u')',    pygame.K_SEMICOLON   : u':',  
    pygame.K_QUOTE       : u'"',    pygame.K_COMMA       : u'<',    pygame.K_MINUS       : u'_',    pygame.K_KP_MINUS    : u'_',  
    pygame.K_PERIOD      : u'>',    pygame.K_SLASH       : u'?',    pygame.K_EQUALS      : u'+',    pygame.K_LEFTBRACKET : u'{',  
    pygame.K_BACKSLASH   : u'|',    pygame.K_RIGHTBRACKET: u'}',    pygame.K_a           : u'A',    pygame.K_b           : u'B',  
    pygame.K_c           : u'C',    pygame.K_d           : u'D',    pygame.K_e           : u'E',    pygame.K_f           : u'F',
    pygame.K_g           : u'G',    pygame.K_h           : u'H',    pygame.K_i           : u'I',    pygame.K_j           : u'J',
    pygame.K_k           : u'K',    pygame.K_l           : u'L',    pygame.K_m           : u'M',    pygame.K_n           : u'N',
    pygame.K_o           : u'O',    pygame.K_p           : u'P',    pygame.K_q           : u'Q',    pygame.K_r           : u'R',
    pygame.K_s           : u'S',    pygame.K_t           : u'T',    pygame.K_u           : u'U',    pygame.K_v           : u'V',
    pygame.K_w           : u'W',    pygame.K_x           : u'X',    pygame.K_y           : u'Y',    pygame.K_z           : u'Z',
}

ctrl_keycode_to_unicode = {
    pygame.K_a       : u'\x01',    pygame.K_b       : u'\x02',  pygame.K_c       : u'\x03',    pygame.K_d       : u'\x04',
    pygame.K_e       : u'\x05',    pygame.K_f       : u'\x06',  pygame.K_g       : u'\x07',    pygame.K_h       : u'\x08',
    pygame.K_i       : u'\x09',    pygame.K_j       : u'\x0A',  pygame.K_k       : u'\x0B',    pygame.K_l       : u'\x0C',
    pygame.K_m       : u'\x0D',    pygame.K_n       : u'\x0E',  pygame.K_o       : u'\x0F',    pygame.K_p       : u'\x10',
    pygame.K_q       : u'\x11',    pygame.K_r       : u'\x12',  pygame.K_s       : u'\x13',    pygame.K_t       : u'\x14',
    pygame.K_u       : u'\x15',    pygame.K_v       : u'\x16',  pygame.K_w       : u'\x17',    pygame.K_x       : u'\x18',
    pygame.K_y       : u'\x19',    pygame.K_z       : u'\x20',
}

android_to_pygame = {
    android.KEYCODE_BACK:         pygame.K_ESCAPE,              android.KEYCODE_ESCAPE:       pygame.K_ESCAPE,
    android.KEYCODE_F1:           pygame.K_F1,                  android.KEYCODE_F2:           pygame.K_F2,
    android.KEYCODE_F3:           pygame.K_F3,                  android.KEYCODE_F4:           pygame.K_F4,
    android.KEYCODE_F5:           pygame.K_F5,                  android.KEYCODE_F6:           pygame.K_F6,
    android.KEYCODE_F7:           pygame.K_F7,                  android.KEYCODE_F8:           pygame.K_F8,
    android.KEYCODE_F9:           pygame.K_F9,                  android.KEYCODE_F10:          pygame.K_F10,
    android.KEYCODE_FORWARD_DEL:  pygame.K_DELETE,              android.KEYCODE_CAPS_LOCK:    pygame.K_CAPSLOCK,
    android.KEYCODE_SCROLL_LOCK:  pygame.K_SCROLLOCK,           android.KEYCODE_SYSRQ:        pygame.K_PRINT,
    android.KEYCODE_BREAK:        pygame.K_BREAK,               android.KEYCODE_MOVE_HOME:    pygame.K_HOME,
    android.KEYCODE_MOVE_END:     pygame.K_END,                 android.KEYCODE_INSERT:       pygame.K_INSERT,
    android.KEYCODE_CTRL_LEFT:    pygame.K_LCTRL,               android.KEYCODE_CTRL_RIGHT:   pygame.K_RCTRL,
    android.KEYCODE_ALT_LEFT:     pygame.K_LALT,                android.KEYCODE_ALT_RIGHT:    pygame.K_RALT,
}

shift = False    
ctrl = False
alt = False
keyboard_visible = False

# fix unicode and set mods    
def get_unicode(e, mods):
    global shift, ctrl, alt
    if e.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
        shift = True
        return ''
    elif e.key in (pygame.K_LCTRL, pygame.K_RCTRL):
        ctrl = True
        return ''
    elif e.key in (pygame.K_LALT, pygame.K_RALT):
        alt = True
        return ''
    try:
        if mods & pygame.KMOD_SHIFT:
            return shift_keycode_to_unicode[e.key]
        elif mods & pygame.KMOD_CTRL:
            return ctrl_keycode_to_unicode[e.key]
        else:
            return keycode_to_unicode[e.key]
    except KeyError:
        # ignore; the pgs4a unicode values are actually android scancodes and not useful to us
        return '' #e.unicode

# android keybard sends a sequence LSHIFT, KEY rather than mods
def apply_mods(e):
    global shift, ctrl, alt
    mod_mask = 0
    if shift:
        mod_mask |= pygame.KMOD_SHIFT
    if ctrl:
        mod_mask |= pygame.KMOD_CTRL
    if alt:
        mod_mask |= pygame.KMOD_ALT
    # clear mods on non-mod keypress only   
    if e.key not in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT):
        shift = False
        ctrl = False
        alt = False
    return mod_mask            

def toggle_keyboard():
    global keyboard_visible
    if keyboard_visible:
        android.hide_keyboard()
    else:    
        android.show_keyboard()
    keyboard_visible = not keyboard_visible

def check_events():
    if android.check_pause():
        android.hide_keyboard()
        # save emulator state
        state.save()
        # hibernate; we may not wake up
        android.wait_for_resume()
        return True
    return False
        
def init():
    android.init()
    # map android keycodes that aren't yet mapped in PGS4A
    for key in android_to_pygame:
        android.map_key(key, android_to_pygame[key])

def close():
    android.hide_keyboard()

