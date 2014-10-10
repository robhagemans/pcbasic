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
import state

# insert keycodes that android module left undefined
# http://pygame.renpy.org/forum/viewtopic.php?f=5&t=618
# https://android.googlesource.com/platform/frameworks/native/+/jb-mr1.1-dev/include/android/keycodes.h
android.KEYCODE_ESCAPE          = 111
android.KEYCODE_FORWARD_DEL     = 112
android.KEYCODE_CTRL_LEFT       = 113
android.KEYCODE_CTRL_RIGHT      = 114
android.KEYCODE_CAPS_LOCK       = 115
android.KEYCODE_SCROLL_LOCK     = 116
android.KEYCODE_META_LEFT       = 117
android.KEYCODE_META_RIGHT      = 118
android.KEYCODE_FUNCTION        = 119
android.KEYCODE_SYSRQ           = 120
android.KEYCODE_BREAK           = 121
android.KEYCODE_MOVE_HOME       = 122
android.KEYCODE_MOVE_END        = 123
android.KEYCODE_INSERT          = 124
android.KEYCODE_FORWARD         = 125
android.KEYCODE_MEDIA_PLAY      = 126
android.KEYCODE_MEDIA_PAUSE     = 127
android.KEYCODE_MEDIA_CLOSE     = 128
android.KEYCODE_MEDIA_EJECT     = 129
android.KEYCODE_MEDIA_RECORD    = 130
android.KEYCODE_F1              = 131
android.KEYCODE_F2              = 132
android.KEYCODE_F3              = 133
android.KEYCODE_F4              = 134
android.KEYCODE_F5              = 135
android.KEYCODE_F6              = 136
android.KEYCODE_F7              = 137
android.KEYCODE_F8              = 138
android.KEYCODE_F9              = 139
android.KEYCODE_F10             = 140
android.KEYCODE_F11             = 141
android.KEYCODE_F12             = 142
android.KEYCODE_NUM_LOCK        = 143
android.KEYCODE_NUMPAD_0        = 144
android.KEYCODE_NUMPAD_1        = 145
android.KEYCODE_NUMPAD_2        = 146
android.KEYCODE_NUMPAD_3        = 147
android.KEYCODE_NUMPAD_4        = 148
android.KEYCODE_NUMPAD_5        = 149
android.KEYCODE_NUMPAD_6        = 150
android.KEYCODE_NUMPAD_7        = 151
android.KEYCODE_NUMPAD_8        = 152
android.KEYCODE_NUMPAD_9        = 153
android.KEYCODE_NUMPAD_DIVIDE   = 154
android.KEYCODE_NUMPAD_MULTIPLY = 155
android.KEYCODE_NUMPAD_SUBTRACT = 156
android.KEYCODE_NUMPAD_ADD      = 157
android.KEYCODE_NUMPAD_DOT      = 158
android.KEYCODE_NUMPAD_COMMA    = 159
android.KEYCODE_NUMPAD_ENTER    = 160
android.KEYCODE_NUMPAD_EQUALS   = 161
android.KEYCODE_NUMPAD_LEFT_PAREN = 162
android.KEYCODE_NUMPAD_RIGHT_PAREN = 163

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
    android.KEYCODE_MENU:         pygame.K_MENU,
}

keyboard_visible = False


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

