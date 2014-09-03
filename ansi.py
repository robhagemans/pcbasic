#
# PC-BASIC 3.23 - ansi.py
#
# Definitions for ANSI escape sequences
#
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# ANSI colour numbers for EGA colours: black, blue, green, cyan, red, magenta, yellow, white
colours = (0, 4, 2, 6, 1, 5, 3, 7)
# ANSI colour names for EGA colours
colournames = ('Black','Dark Blue','Dark Green','Dark Cyan','Dark Red','Dark Magenta','Brown','Light Gray',
'Dark Gray','Blue','Green','Cyan','Red','Magenta','Yellow','White')

# ANSI escape sequences
# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting

esc_reset = '\x1b[0m\x1bc'
esc_set_scroll_screen = '\x1b[r'
esc_set_scroll_region = '\x1b[%i;%ir'
esc_clear_screen = '\x1b[2J'
esc_clear_line = '\x1b[2K'
esc_scroll_up = '\x1b[%iS'
esc_scroll_down = '\x1b[%iT'
esc_show_cursor = '\x1b[?25h'
esc_hide_cursor = '\x1b[?25l'
esc_resize_term = '\x1b[8;%i;%i;t'
esc_move_cursor = '\x1b[%i;%if' 
esc_save_cursor_pos = '\x1b[s'
esc_restore_cursor_pos = '\x1b[u'
esc_request_size = '\x1b[18;t'
esc_set_cursor_colour = '\x1b]12;%s\x07'
esc_set_cursor_shape = '\x1b[%i q'  #% (2*(is_line+1) - blinks)    # 1 blinking block 2 block 3 blinking line 4 line
esc_set_colour = '\x1b[%im'      
esc_set_title = '\x1b]2;%s\x07'
esc_clear_line = '\x1b[2K'
esc_move_right = '\x1b\x5b\x43'
esc_move_left = '\x1b\x5b\x44'

# escape sequence to scancode dictionary
# for scan codes, see e.g. http://www.antonis.de/qbebooks/gwbasman/appendix%20h.html
esc_to_scan = {
    '\x1b\x4f\x50': '\x00\x3b', # F1
    '\x1b\x4f\x51': '\x00\x3c', # F2
    '\x1b\x4f\x52': '\x00\x3d', # F3
    '\x1b\x4f\x53': '\x00\x3e', # F4
    '\x1b\x5b\x31\x35\x7e':  '\x00\x3f', # F5
    '\x1b\x5b\x31\x37\x7e':  '\x00\x40', # F6
    '\x1b\x5b\x31\x38\x7e':  '\x00\x41', # F7
    '\x1b\x5b\x31\x39\x7e':  '\x00\x42', # F8
    '\x1b\x5b\x32\x30\x7e':  '\x00\x43', # F9
    '\x1b\x5b\x32\x31\x7e':  '\x00\x44', # F10
    '\x1b\x4f\x46': '\x00\x4F', # END
    '\x1b\x4f\x48': '\x00\x47', # HOME
    '\x1b\x5b\x41': '\x00\x48', # arrow up
    '\x1b\x5b\x42': '\x00\x50', # arrow down
    '\x1b\x5b\x43': '\x00\x4d', # arrow right
    '\x1b\x5b\x44': '\x00\x4b', # arrow left
    '\x1b\x5b\x32\x7e': '\x00\x52', # INS
    '\x1b\x5b\x33\x7e': '\x00\x53', # DEL
    '\x1b\x5b\x35\x7e': '\x00\x49', # PG UP
    '\x1b\x5b\x36\x7e': '\x00\x51', # PG DN
}

