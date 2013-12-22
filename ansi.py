#
# PC-BASIC 3.23 - ansi.py
#
# ANSI escape codes for use by terminal.py
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys, tty, termios


# ANSI escape sequences

# for reference, see:
# http://en.wikipedia.org/wiki/ANSI_escape_code
# http://misc.flogisoft.com/bash/tip_colors_and_formatting

# black, blue, green, cyan, red, magenta, yellow, white
colours = [0, 4, 2, 6, 1, 5, 3, 7]
colournames = ['Black','Dark Blue','Dark Green','Dark Cyan','Dark Red','Dark Magenta','Brown','Light Gray',
'Dark Gray','Blue','Green','Cyan','Red','Magenta','Yellow','White']



def commit():
    sys.stdout.flush()
    

def save_pos():
    sys.stdout.write('\x1b[s') # save cursor position

def restore_pos():
    sys.stdout.write('\x1b[u') # restore cursor position


def clear_screen():
    sys.stdout.write('\x1b[2J')
    commit()

def clear_line():
    sys.stdout.write('\x1b[2K')
    commit()


def set_scroll_region(top, bot):
    sys.stdout.write('\x1b[%i;%ir' % (top, bot))
    commit()

def move_cursor(row=1, col=1):
    sys.stdout.write('\x1b[%i;%if' % (row, col))
    commit()

def show_cursor(do_show=True):
    
    if do_show:
        sys.stdout.write('\x1b[?25h')
    else:
        sys.stdout.write('\x1b[?25l')
    commit()        

    
def resize_term(rows=25, cols=80):
    sys.stdout.write('\x1b[8;%i;%i;t' % (rows , cols))    


def scroll_up(lines=1):
    sys.stdout.write('\x1b[%iS' % lines)

def scroll_down(lines=1):
    sys.stdout.write('\x1b[%iT' % lines)


def reset():
    sys.stdout.write('\x1b[0m')
    sys.stdout.write('\x1bc')
    
def set_colour(fore=None, back=None):
    if fore != None:
        if (fore%16)<8:
            sys.stdout.write('\x1b[%im' % (30+colours[fore%8]))
        else:
            sys.stdout.write('\x1b[%im' % (90+colours[fore%8]))
    if back!=None:
        sys.stdout.write('\x1b[%im' % (40+colours[back%8]))
        

def set_cursor_shape(is_line=False, blinks=False):
    # works on xterm, not on xfce
    # on xfce, gibberish is printed
    
    # 1,2,3,4
    num = 0
    if blinks:
        if is_line:
            num = 3
        else:
            num = 1
    else:
        if is_line:
            num = 4
        else:
            num = 2
                
    sys.stdout.write('\x1b[%i q' % num)
    commit()


def set_cursor_colour(fore):
    sys.stdout.write('\x1b]12;' +colournames[fore%16] +'\x07')
    commit()


# translate to scancodes
def translate_char(c):
    if c=='':
        return c
    elif len(c)>0 and c in esc_to_scan:
        return esc_to_scan[c]       
    elif c=='\x00':      # to avoid confusion with scancodes
        return '\x00\x00'      
    elif c=='\x7f':      # backspace
        return '\x08'
    else:
        # all other codes are chopped off, 
        # so other escape sequences will register as an escape keypress.
        return c[0]    
        

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
    
    # this is not an esc sequence, but UTF-8 for GBP symbol
    '\xc2\xa3': '\x9c'  # pound sterling symbol
}
 
 
 
 


