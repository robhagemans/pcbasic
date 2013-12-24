#
# PC-BASIC 3.23 - dumbterm.py
#
# Dumb terminal backend
# implements text screen I/O functions on an dumb, echoing unicode terminal
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import sys, select
# for os.read
import os

import error
# for to_utf8
import unicodepage

# screen dimensions - these are read by some code, so need to be present
# number of columns, counting 1..width
width = 80
# number of rows, counting 1..height
height = 25
view_start=1
scroll_height=24
view_set=False
graphics_view_set=False


graphics_mode=False

# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
colorswitch = True


# current column position
col = 1

# non-printing characters
control = ('\x07', '\x09', '\x0a','\x0b','\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')

# incoming keys, either ascii or \00 followed by scancode 
keybuf = ''
      
last_row_is_on = False


def check_events():
    pass


def set_colorswitch(new_val):
    global colorswitch
    colorswitch=new_val


def init():
    last_row_is_on=False

    
def pause():
    pass


def cont():
    pass    

        
def close():
    pass
    
    
def clear_all():
    pass

        
def clear():
    pass    

    
def clear_view():
    pass


def clear_graphics_view():
    pass
    
    
def mode_info(mode):
    global width
    if mode ==0:
        return (False, 16, (7,0), (32,64), width, 4)
    else:
        return None

    
def set_mode(mode):
    if mode != 0:
        raise error.RunError(5)    


def clear_line(row):
    pass

    
def set_apage(dummy):
    return True

        
def set_vpage(dummy):
    return True


def copy_page(src, dst):
    pass

        
def unset_view():
    global view_set
    set_view()
    view_set=False        


def set_view(start=1,stop=24):
    global view_start, scroll_height, view_set
    view_start = start
    scroll_height = stop       
    view_set=True

    
def last_row_on():
    global last_row_is_on
    last_row_is_on=True
    

def last_row_off():
    global last_row_is_on
    last_row_is_on=False


        
def redraw():
    pass

    
def get_mode():
    return 0    

    
def colours_ok(dummy):
    return True    

    
def idle():
    pass    

    
def set_palette(new_palette=[]):
    pass

    
def set_palette_entry(index, colour):
    pass

    
def get_palette_entry(index):
    return index
    
    
def set_width(to_width):
    global width
    width = to_width

        
def resize(to_height, to_width):
    global width, height
    width = to_width
    height = to_height
    
    
def start_line():
    global col
    if col!=1:
        sys.stdout.write('\n')
        col=1


def read_screenline(write_endl=True, from_start=False):
    global col
    line = read()
    col=1
    return line    


def read_screen(row, col):
    return (' ', 7)


def read_chars(num):
    for _ in range(num):
        word = ''
        a = ''
        while a =='':
            a = get_char()
        word += a[0]
    return word

    
def set_pos(to_row, to_col, scroll_ok=True):
    if to_row != height:
        last_row_off()


def get_pos():
    global col
    return (1, col)


def get_row():
    return 1

    
def get_col():
    global col
    return col        


def write(s, scroll_ok=True):
    global row, col
    tab = 8
    
    last=''
    for c in s:
        if c not in control or c=='\x00':
            put_char(c)
                
        elif c=='\x09': # TAB
            num = (tab - (col - tab*int((col-1)/tab)))
            for _ in range(num):
                put_char(' ') 
    
        if c in ('\x0d', '\x0a'): # CR, LF
            if c=='\x0a' and last=='\x0d':
                pass
            elif last_row_is_on:
                last_row_off()
            else:
                sys.stdout.write('\r\n')
                col=1
        elif c == '\x07': # BEL
            sys.stdout.write(c)   
        else:
            # ignore all other controls - HOME, END, arrow keys
            pass
        last=c
        
             
def set_attr(fore, back):
    pass

    
def get_attr():
    return (7,0)            
        
        
def set_line_cursor(is_line=True):
    pass
        

def show_cursor(do_show = True):
    pass

    
def hide_cursor():
    return True


def read():
    global col, charbuf, attrbuf
    
    insert = False
    
    c = ''
    inp = ''
    while c not in ('\x0d', '\x0a'): 
        # wait_char returns a string of ascii and MS-DOS/GW-BASIC style keyscan codes
        c = wait_char() 
            
        pos=0
        while pos<len(c):
            
            if c[pos] == '\x7f': #  backspace
                inp = inp[:-1]
                col -=1
            elif c[pos] not in control + ('', '\x00'): 
                inp += c[pos]
            elif c[pos] == '\x00' and pos+1<len(c):
                pos+=1
                pass
                     
            pos+=1
                       
    return inp 



def redraw_row():
    pass


      
def put_char(c):
    global col
    if not last_row_is_on:
        sys.stdout.write(unicodepage.to_utf8(c))
        sys.stdout.flush()
        col += 1


def wait_char():
    global keybuf
    
    if len(keybuf)==0:
        fd = sys.stdin.fileno()
        # esc sequences are up to 5 byteslong. this returns even if only one char found.
        # move scancodes (starting \x00) or ascii into keybuf
        # also apply KEY replacements as they work at a low level
        keybuf += os.read(fd,5)
               
    ch = keybuf[0]
    keybuf = keybuf[1:]
    
    if ch=='\x00' and len(keybuf)>0:
        ch += keybuf[0]
        keybuf = keybuf[1:]
        
    return ch 

    
def peek_char():
    # not supported by dumb term
    return ''    


def get_char():
    global keybuf
    
    fd = sys.stdin.fileno()
    c = ''
    # check if stdin has characters to read
    d = select.select([sys.stdin], [], [], 0) 
    if d[0] != []:
        c = os.read(fd,5)
    
    # move scancodes (starting \x00) or ascii into keybuf
    # also apply KEY replacements as they work at a low level
    keybuf += c
    
    ch =''
    if len(keybuf)>0:
        ch = keybuf[0]
        keybuf = keybuf[1:]

        if ch=='\x00' and len(keybuf)>0:
            ch += keybuf[0]
            keybuf = keybuf[1:]
        
    return ch 
    

