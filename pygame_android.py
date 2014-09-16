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

