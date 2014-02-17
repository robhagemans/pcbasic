#
# PC-BASIC 3.23 - console.py
#
# Console front-end
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

# this module contains all the screen and keyboard routines
# including file access to devices SCRN: and KEYB:
#
# this module is the front-end; it needs a back-end implementation
# known back-ends: 
# - gameterm (text, graphics and sound, using pygame)
# - terminal (textmode only, using escape sequences)

import copy

import util
import error
import graphics
import sound
import events
# for print_screen
import deviceio

# back end implememtation
backend = None

# number of columns, counting 1..width
width = 80
# number of rows, counting 1..height
height = 25

# viewport parameters
view_start = 1
scroll_height = 24
view_set = False
# writing on bottom row is allowed    
last_row_is_on=False

# cursor/current characteristics
attr = 7
row = 1
col = 1
cursor = True
cursor_is_line = False

# non-printing characters
control = ('\x07', '\x08', '\x09', '\x0a','\x0b','\x0c', '\x0d', '\x1c', '\x1d', '\x1e', '\x1f')

# incoming keys, either ascii or \00 followed by scancode 
keybuf = ''

# caps lock
caps = False

# echo to printer
echo_read = None
echo_write = None

class ScreenBuffer:
    def __init__(self, bwidth, bheight):
        # screen buffer, initialised to spaces, dim white on black
        self.charbuf = [[' ']*bwidth for _ in xrange(bheight)]
        self.attrbuf = [[7]*bwidth for _ in xrange(bheight)]
        # last non-white character
        self.end = [0 for _ in xrange(bheight)]
        # line continues on next row (either LF or word wrap happened)
        self.wrap = [False for _ in xrange(bheight)]

# screen pages        
num_pages = 1            
pages = [ ScreenBuffer(width, height) ]
vpage = pages[0]
apage = pages[0]
vpagenum = 0
apagenum = 0

# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
colorswitch = True

# graphics vs text mode 
graphics_mode = False
screen_mode = 0

# palette
num_colours = 32    
num_palette = 64

# pen and stick
pen_is_on = False
stick_is_on = False


# KEY ON?
keys_visible = False


def init():
    backend.init()

def close():
    backend.close()

def get_mode():
    return screen_mode

def idle():
    backend.idle()

def mode_info(mode):
    info_graphics_mode=True
    if mode == 0:
        info_graphics_mode = False
        info_font_height = 16
        info_attr = (7, 0)
        info_colour_depth = (32, 64)
        info_new_width = width
        info_num_pages = 4
    elif mode == 1:
        info_font_height = 8
        info_attr = (3, 0)
        info_colour_depth = (4, 16)
        info_new_width = 40
        info_num_pages = 1
    elif mode == 2:
        info_font_height = 8
        info_attr = (1, 0)
        info_colour_depth = (2, 16)
        info_new_width = 80
        info_num_pages = 1    
    elif mode ==7:
        info_font_height = 8
        info_attr = (15, 0)
        info_colour_depth = (16, 16)
        info_new_width = 40
        info_num_pages = 8
    elif mode==8:
        info_font_height = 8
        info_attr = (15, 0)
        info_colour_depth = (16, 16)
        info_new_width = 80
        info_num_pages = 4
    elif mode==9:
        info_font_height = 14
        info_attr = (15,0)
        info_colour_depth = (16,64)
        info_new_width = 80
        info_num_pages = 2
    else:
        return None
    return (info_graphics_mode, info_font_height, info_attr, info_colour_depth, info_new_width, info_num_pages)
    

def set_mode(mode):
    global screen_mode, graphics_mode, num_pages
    screen_mode = mode
    (graphics_mode, font_height, new_attr, colour_depth, new_width, num_pages) = mode_info(mode)
    set_attr(*new_attr)
    set_colour_depth(*colour_depth)
    backend.init_screen_mode(mode, font_height)  
    resize(25, new_width)
    set_line_cursor(True)
    graphics.init_graphics_mode(mode, font_height)      
    show_cursor(cursor)
    if keys_visible:
        show_keys()

def set_colour_depth(colours, palette):
    global num_colours
    global num_palette
    num_colours = colours
    num_palette = palette
    
def colours_ok(c):
    return (c >= 0 and c < num_colours)
    
# core event handler    
def check_events():
    # check console events
    backend.check_events()   
    # check&handle user events
    events.check_events()
    events.handle_events()
    # manage sound queue
    sound.check_sound()
    
def set_palette(new_palette=None):
    backend.set_palette(new_palette)

def set_palette_entry(index, colour):
    backend.set_palette_entry(index, colour)

def get_palette_entry(index):
    return backend.get_palette_entry(index)

def write(s, scroll_ok=True):
    global row, col, apage
    if echo_write != None and row < 25:
        # don't echo row 25 (keys line)
        echo_write.write(s)
    tab = 8
    last = ''
    for c in s:
        if c not in control or c=='\x08':                  # char 08 is written as symbol
            put_char(c)
        elif c=='\x09':                                     # TAB
            num = (tab - (col-1 - tab*int((col-1)/tab)))
            for _ in range(num):
                put_char(' ')
        elif c == '\x0A':                                   # LF
            # exclude CR/LF
            if last != '\x0D': 
                # LF connects lines like word wrap
                apage.wrap[row-1]=True
                set_pos(row+1, 1,scroll_ok)
        elif c == '\x0D':   set_pos(row+1, 1,scroll_ok)     # CR
        elif c == '\x00':   put_char('\x00')                # NUL
        elif c == '\x07':   sound.beep()                    # BEL
        elif c == '\x0B':   set_pos(1,1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(row, col+1,scroll_ok)
        elif c == '\x1D':   set_pos(row, col-1,scroll_ok)
        elif c == '\x1E':   set_pos(row-1, col,scroll_ok )
        elif c == '\x1F':   set_pos(row+1, col,scroll_ok)
        last = c

def insert_char(crow, ccol, c, cattr):
    global apage
    while True:
        apage.charbuf[crow-1].insert(ccol-1,c)
        apage.attrbuf[crow-1].insert(ccol-1,cattr)
        if apage.end[crow-1]<width:
            apage.charbuf[crow-1].pop()
            apage.attrbuf[crow-1].pop()
            if apage.end[crow-1] > ccol-1:
                apage.end[crow-1] += 1
            else:
                apage.end[crow-1] = ccol
            break
        else:
            if crow==scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow-=1
            if not apage.wrap[crow-1]:
                scroll_down(crow+1)
                apage.wrap[crow-1]=True    
            c = apage.charbuf[crow-1].pop()
            cattr = apage.attrbuf[crow-1].pop()
            crow += 1
            ccol = 1
    return crow            
        
        
def delete_char(crow, ccol):
    global apage
    save_col = ccol
    if crow>1 and ccol == apage.end[crow-1]+1 and apage.wrap[crow-1]:
        # row was a LF-ending row
        apage.charbuf[crow-1] = apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow][:width-ccol+1] 
        apage.attrbuf[crow-1] = apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow][:width-ccol+1] 
        apage.end[crow-1] += apage.end[crow]
        if apage.end[crow-1] > width:
            apage.end[crow-1] = width
        while apage.wrap[crow] and crow < scroll_height:
            apage.charbuf[crow] = apage.charbuf[crow][width-ccol+1:] + apage.charbuf[crow+1][:width-ccol+1]  
            apage.attrbuf[crow] = apage.attrbuf[crow][width-ccol+1:] + apage.attrbuf[crow+1][:width-ccol+1]
            apage.end[crow] += apage.end[crow+1]
            if apage.end[crow] > width:
                apage.end[crow] = width
            crow += 1    
        apage.charbuf[crow] = apage.charbuf[crow][width-ccol+1:] + [' ']*(width-ccol+1) 
        apage.attrbuf[crow] = apage.attrbuf[crow][width-ccol+1:] + [attr]*(width-ccol+1)
        apage.end[crow] -= width-ccol    
        redraw_row(save_col-1)
        if apage.end[crow] <= 0:
            apage.end[crow] = 0
            ccol += 1
            apage.wrap[crow-1] = False
            scroll(crow+1)
    elif ccol <= apage.end[crow-1]:
        while True:            
            if (not apage.wrap[crow-1]) or (apage.end[crow-1]<width) or crow==scroll_height:
                apage.charbuf[crow-1] = (apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow-1][ccol:apage.end[crow-1]] 
                                        + [' '] + apage.charbuf[crow-1][apage.end[crow-1]:])
                apage.attrbuf[crow-1] = (apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow-1][ccol:apage.end[crow-1]] 
                                        + [attr] + apage.attrbuf[crow-1][apage.end[crow-1]:])
                break
            else:
                # wrap and end[row-1]==width
                apage.charbuf[crow-1] = (apage.charbuf[crow-1][:ccol-1] + apage.charbuf[crow-1][ccol:apage.end[crow-1]] 
                                        + [ apage.charbuf[crow][0] ] )
                apage.attrbuf[crow-1] = (apage.attrbuf[crow-1][:ccol-1] + apage.attrbuf[crow-1][ccol:apage.end[crow-1]] 
                                        + [ apage.attrbuf[crow][0] ] )
                crow += 1
                ccol = 1
        # this works from *global* row onwrds
        redraw_row(save_col-1)
        # this works on *local* row (last row edited)
        if apage.end[crow-1] > 0:
            apage.end[crow-1] -= 1
        else:
            scroll(crow)
            if crow > 1:
                apage.wrap[crow-2] = False            

def read():
    global row, col, apage 
    insert = False
    c = ''
    inp = ''
    while c != '\x0d': 
        # wait_char returns a string of ascii and MS-DOS/GW-BASIC style keyscan codes
        c = wait_char() 
        if echo_read != None:
            echo_read.write(c)
        pos = 0
        while pos<len(c):
            d = c[pos]
            pos += 1
            if d == '\x00' and len(c)>pos:
                d += c[pos]
                pos += 1
            if d == '\x03':            # <CTRL+C>, probably already caught in wait_char()
                raise error.Break()
            elif d == '\x07':                   # <CTRL+G>
                sound.beep()    
            elif d == '\x08':                   # <BACKSPACE>
                inp = inp[:-1]
                if col==1:
                    if row>1 and apage.wrap[row-2]:
                        col=apage.end[row-2] #+1
                        row-=1
                    else:
                        col=1
                else: 
                    col=col-1
                delete_char(row,col)
                if col >= 1:
                    set_pos(row, col)
                else:
                    set_pos(row, 1)
            elif d == '\x09':                  #  <TAB> or <CTRL+I>
                inp = inp[:-1]
                if not insert:
                    set_pos(row, col+8, scroll_ok=False)
                else:
                    for _ in range(8):
                        insert_char(row, col, ' ', attr)
                    redraw_row(col-1, row)
                    set_pos(row, col+8)
            elif d == '\x0A':                   #  <CTRL+ENTER> or <CTRL+J>
                # moves rest of line to next line
                if col < apage.end[row-1]:
                    for _ in range(width-col+1):
                        insert_char(row, col, ' ', attr)
                    redraw_row(col-1, row)
                    apage.end[row-1]=col-1 
                else:
                    crow = row
                    while apage.wrap[crow-1] and crow<scroll_height:
                        crow+=1
                    if crow>=scroll_height:
                        scroll()
                    scroll_down(row+1)
                # LF connects lines like word wrap
                apage.wrap[row-1] = True
                set_pos(row+1, 1)
            elif d == '\x1B':                      # <ESC> or <CTRL+[>
                clear_line(row)
            elif d == '\x00\x75' or d == '\x05':   # <CTRL+END> <CTRL+E>
                clear_rest_of_line(row, col)   
            elif d == '\x00\x48' or d == '\x1E':   # <UP> <CTRL+6>
                insert = False
                set_line_cursor(True)
                set_pos(row-1, col, scroll_ok=False)
            elif d == '\x00\x50' or d == '\x1F':   # <DOWN> <CTRL+->
                insert = False
                set_line_cursor(True)
                set_pos(row+1, col, scroll_ok=False)
            elif d == '\x00\x4D' or d == '\x1C':   # <RIGHT> <CTRL+\>
                insert = False
                set_line_cursor(True)
                set_pos(row, col+1, scroll_ok=False)
            elif d == '\x00\x4B' or d == '\x1D':   # <LEFT> <CTRL+]>
                insert = False
                set_line_cursor(True)
                set_pos(row, col-1, scroll_ok=False)
            elif d == '\x00\x74' or d == '\x06':   # <CTRL+RIGHT> or <CTRL+F>
                skip_word_right()    
            elif d == '\x00\x73' or d == '\x02':   # <CTRL+LEFT> or <CTRL+B>
                skip_word_left() 
            elif d == '\x00\x52' or d == '\x12':   # <INS> <CTRL+R>
                insert = not insert
                set_line_cursor(not insert)  
            elif d == '\x00\x53' or d == '\x7F':   # <DEL> <CTRL+BACKSPACE>
                delete_char(row, col)
            elif d == '\x00\x47' or d == '\x0B':   # <HOME> <CTRL+K>
                insert = False
                set_line_cursor(True)
                set_pos(1,1)
            elif d == '\x00\x4F' or d == '\x0E':   # <END> <CTRL+N>
                insert = False
                set_line_cursor(True)
                while apage.wrap[row-1] and row<height:
                    row += 1
                set_pos(row, apage.end[row-1]+1)
            elif d == '\x00\x77' or d == '\x0C':    # <CTRL+HOME> <CTRL+L>   
                clear()
            elif d == '\x00\x37':                   # <SHIFT+PRT_SC>
                print_screen()
            elif d[0] not in control + ('\x00',): 
                inp += d
                if insert:
                    insert_char(row,col, d, attr)
                    redraw_row(col-1, row)
                    set_pos(row, col+1)
                else:    
                    put_char(d, echo=True)
    insert = False
    set_line_cursor(True)
    return inp  

def read_screenline(write_endl=True, from_start=False):
    global row, col, apage
    prompt_row = row
    prompt_col = col
    savecurs = show_cursor() 
    read()
    show_cursor(savecurs)
    # find start of wrapped block
    crow = row
    while crow>1 and apage.wrap[crow-2]:
        crow-=1
    line = []
    # add lines 
    while crow<height:
        add = apage.charbuf[crow-1][:apage.end[crow-1]]
        # exclude prompt, if any
        if crow == prompt_row and not from_start:
            add = add[prompt_col-1:]
        line += add
        if apage.wrap[crow-1]:
            if apage.end[crow-1]<width:
                # wrap before end of line means LF
                line += '\x0a'
            crow+=1
        else:
            break
    # go to last line
    row = crow
    if write_endl:
        write(util.endl)
    # remove trailing whitespace 
    while len(line)>0 and line[-1] in util.whitespace:
        line = line[:-1]
    return ''.join(line)    

def clear_line(the_row):
    global apage
    # find start of line
    srow = the_row
    while srow>1 and apage.wrap[srow-2]:
        srow -= 1
    clear_rest_of_line(srow, 1)

def clear_rest_of_line(srow, scol):
    crow = srow    
    apage.charbuf[crow-1] = apage.charbuf[crow-1][:scol-1] + [' ']*(width-scol+1)
    apage.attrbuf[crow-1] = apage.attrbuf[crow-1][:scol-1] + [attr]*(width-scol+1)
    apage.end[crow-1] = min(apage.end[crow-1], scol-1)
    while apage.wrap[crow-1]:
        crow += 1
        apage.charbuf[crow-1] = [' ']*width
        apage.attrbuf[crow-1] = [attr]*width
        apage.end[crow-1] = 0
    for r in range(crow, srow, -1):
        apage.wrap[r-1] = False
        scroll(r)
    apage.wrap[srow-1] = False
    set_pos(srow, scol)
    backend.clear_row(srow, colours(attr)[1] & 0xf)
    if scol>1:
        redraw_row(0, srow)

def skip_word_right():
    crow, ccol = row, col
    # find non-alphanumeric chars
    while True:
        c = apage.charbuf[crow-1][ccol-1].upper() 
        if (c<'0' or c>'9') and (c<'A' or c>'Z'):
            break
        ccol += 1
        if ccol > width:
            if crow >= scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    # find alphanumeric chars
    while True:
        c = apage.charbuf[crow-1][ccol-1].upper() 
        if not ((c<'0' or c>'9') and (c<'A' or c>'Z')):
            break
        ccol += 1
        if ccol > width:
            if crow >= scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    set_pos(crow, ccol)                            
        
def skip_word_left():
    crow, ccol = row, col
    # find alphanumeric chars
    while True:
        ccol -= 1
        if ccol < 1:
            if crow <= view_start:
                # not found
                return
            crow -= 1
            ccol = width
        c = apage.charbuf[crow-1][ccol-1].upper() 
        if not ((c<'0' or c>'9') and (c<'A' or c>'Z')):
            break
    # find non-alphanumeric chars
    while True:
        last_row, last_col = crow, ccol
        ccol -= 1
        if ccol < 1:
            if crow <= view_start:
                break
            crow -= 1
            ccol = width
        c = apage.charbuf[crow-1][ccol-1].upper() 
        if (c<'0' or c>'9') and (c<'A' or c>'Z'):
            break
    set_pos(last_row, last_col)                            
        

def print_screen():
    for crow in range(1, height+1):
        deviceio.lpt1.write(''.join(vpage.charbuf[crow-1]) + util.endl)
    deviceio.lpt1.flush()    
        
def start_line():
    if col!=1:
        set_pos(row+1, 1)        

def set_width(to_width):
    resize(height, to_width)    
    if keys_visible:
        show_keys()

def set_colorswitch(new_val):
    global colorswitch
    colorswitch = new_val

def read_screen(crow, ccol):
    char = apage.charbuf[crow-1][ccol-1]
    att = apage.attrbuf[crow-1][ccol-1]
    return (char, att)

# insert character into keyboard buffer (for use by backends)
def insert_key(c):
    global keybuf 
    keybuf += events.replace_key(c)

# non-blocking keystroke read
def get_char():
    check_events()
    return pass_char( peek_char() )
    
# peek character from keyboard buffer
def peek_char():
    ch = ''
    if len(keybuf)>0:
        ch = keybuf[0]
        if ch == '\x00' and len(keybuf) > 0:
            ch += keybuf[1]
    return ch 

# drop character from keyboard buffer
def pass_char(ch):
    global keybuf
    keybuf = keybuf[len(ch):]        
    return ch

# blocking keystroke read
def read_chars(num):
    for _ in range(num):
        word = ''
        a = ''
        savecurs = show_cursor(False)
        while a =='':
            idle()            
            a = get_char()
        word += a[0]
        show_cursor(savecurs)
    return word

# blocking keystroke read
def wait_char():
    while len(keybuf)==0:
        idle()
        check_events()
    return get_char()

def get_pos():
    return (row, col)

def get_row():
    return row
    
def get_col():
    return col        

def check_pos(scroll_ok=True):
    global row, col
    oldrow = row
    oldcol = col
    if last_row_is_on and row == height:
        if col > width:
            col = width
        elif col < 1:
            col += 1    
    else:
        # if row > height, we also end up here
        if col > width:
            if row < scroll_height or scroll_ok:
                col -= width
                row += 1
            else:
                col = width        
        elif col < 1:
            if row > view_start:
                col += width
                row -= 1
            else:
                col = 1   
        # adjust viewport if necessary
        last_row_off()
        if row > scroll_height:
            if scroll_ok:
                scroll()                # Scroll Here
            row = scroll_height
        elif row < view_start:
            row = view_start
    if row != oldrow or col != oldcol:
        # signal position change
        return False
    return True
    

def set_attr(fore, back):
    global attr
    blink = fore > 0xf
    attr = ((0x8 if blink else 0x0) + (back & 0x7))*0x10 + (fore & 0xf)                   
    
def get_attr():
    return colours(attr)            

def show_cursor(do_show = True):
    global cursor
    prev = cursor
    cursor = do_show
    backend.show_cursor(do_show, prev)
    return prev

def hide_cursor():
    return show_cursor(False)

def colours(at):
    back = (at>>4) & 0x7
    blink = (at>>7)
    fore = (blink*0x10) + (at&0xf)
    return (fore, back)

def clear():
    save_view_set, save_view_start, save_scroll_height = view_set, view_start, scroll_height
    set_view(1,25)
    clear_view()
    if save_view_set:
        set_view(save_view_start, save_scroll_height)
    else:
        unset_view()
    if keys_visible:
        show_keys()


def hide_keys():
    global keys_visible
    keys_visible = False
    pos = get_pos()
    last_row_on()
    set_pos(25, 1)
    write(' '*width, scroll_ok=False)
    set_pos(*pos)
        
                    
def show_keys():
    global keys_visible
    keys_visible = True
    pos = get_pos()
    attr = get_attr()
    save_curs = show_cursor(False)
    for i in range(width/8):
        text = list(events.key_replace[i][:6])
        for j in range(len(text)):
            if text[j] == '\x0d':   #  CR
                text[j] = '\x1b'  # arrow left
        # allow pos=25 without scroll, this is reset as soon as row changes again.
        last_row_on()
        set_pos(25, 1+i*8)
        set_attr(*attr)
        if i == 9:
            write('0')
        else:
            write(str(i+1))
        if not graphics.is_graphics_mode():
            if attr[1]==0:    
                set_attr(0, 7)
            else:
                set_attr(7, 0)
        write(''.join(text))
        set_attr(*attr)
        write(' '*(6-len(text)))
        write(' ')
    set_pos(*pos)
    set_attr(*attr)
    show_cursor(save_curs)

        
def set_view(start=1,stop=24):
    global view_start, scroll_height, view_set
    view_set = True    
    view_start = start
    scroll_height = stop       
    backend.set_scroll_area(view_start, scroll_height, width)
    set_pos(start, 1)
 
def unset_view():
    global view_set
    set_view()
    view_set = False
    
def last_row_on(on=True):
    global last_row_is_on
    # allow writing on bottom line    
    if last_row_is_on != on:
        if on:
            backend.set_scroll_area(view_start, height, width)
        else:
            backend.set_scroll_area(view_start, scroll_height, width)
        last_row_is_on = on

def last_row_off():
    last_row_on(False)

def resize(to_height, to_width):
    global height, width
    width = to_width
    height = to_height
    setup_screen(height, width)
    
def clear_all():
    setup_screen(height, width)
    if keys_visible:
        show_keys()
            
    
def setup_screen(to_height, to_width):    
    global pages, vpage, apage    
    global row, col
    pages = []
    for _ in range(num_pages):
        pages.append(ScreenBuffer(to_width, to_height))
    vpage = pages[0]
    apage = pages[0]
    backend.setup_screen(to_height, to_width)
    row = 1
    col = 1

def set_apage(page_num):
    global apage, apagenum
    if page_num < num_pages:
        apage = pages[page_num]
        apagenum = page_num
        return True
    else:
        return False    
        
def set_vpage(page_num):
    global vpage, vpagenum
    if page_num < num_pages:
        backend.screen_changed = True
        vpage = pages[page_num]
        vpagenum = page_num
        return True
    else:
        return False 
   
def copy_page(src, dst):
    global pages
    if src < num_pages and dst < num_pages:
        for x in range(height):
            pages[dst].charbuf[x] = copy.copy(pages[src].charbuf[x])
            pages[dst].attrbuf[x] = copy.copy(pages[src].attrbuf[x])
            pages[dst].end[x] = pages[src].end[x]
            pages[dst].wrap[x] = pages[src].wrap[x]
        backend.copy_page(src,dst)
        return True
    else:
        return False
         
def clear_view():
    global row, col, apage 
    for r in range(view_start, scroll_height+1):
        apage.charbuf[r-1] = [' ']*width
        apage.attrbuf[r-1] = [attr]*width
        apage.end[r-1] = 0
        apage.wrap[r-1]=False
    fore, back = colours(attr)
    bg = back & 0xf
    row = view_start
    col = 1
    backend.clear_scroll_area(bg)
    
def set_pos(to_row, to_col, scroll_ok=True):
    global row, col
    row = to_row
    col = to_col
    check_pos(scroll_ok)
    fore, back = colours(apage.attrbuf[row-1][col-1])
    color = fore & 0xf
    backend.set_cursor_colour(color)
    
def set_line_cursor(is_line=True):
    global cursor_is_line
    if is_line==cursor_is_line:
        return
    else:
        cursor_is_line = is_line
        backend.build_line_cursor(is_line)

def put_char(c, echo=False):
    global row, col, attr, apage
    # check if scroll& repositioning needed
    check_pos(scroll_ok=True)
    save_curs = show_cursor(False)
    if graphics_mode:
        # no blink, bg=0
        attr &= 0xf
    if not echo or not backend.echo:    
        backend.putc_at(row, col, c, attr)    
    show_cursor(save_curs)
    if row >0 and row <= height and col > 0 and col <= width:   
        apage.charbuf[row-1][col-1] = c
        apage.attrbuf[row-1][col-1] = attr
        if apage.end[row-1] <= col-1:
            apage.end[row-1] = col
    col += 1
    if col > width:
        # wrap line
        apage.wrap[row-1] = True
        row += 1
        col = 1

def redraw_row(start=0, crow=-1):
    if crow == -1:
        crow=row
    save_curs = hide_cursor()
    while True:
        if crow >= height or crow <0:
            break
        for i in range(start, apage.end[crow-1]): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            apage.attrbuf[crow-1][i] = attr
            backend.putc_at(crow, i+1, apage.charbuf[crow-1][i], apage.attrbuf[crow-1][i])
        if apage.wrap[crow-1]:
            crow += 1
            start = 0
        else:
            break    
    show_cursor(save_curs)

def scroll(from_line=-1): 
    global row, col, apage
    if from_line == -1:
        from_line = view_start
    save_curs = show_cursor(False)    
    backend.scroll(from_line)
    # sync buffers with the new screen reality:
    if row > from_line:
        row = row-1
    apage.charbuf.insert(scroll_height, [' ']*width)
    apage.attrbuf.insert(scroll_height, [attr]*width)
    apage.end.insert(scroll_height, 0)
    apage.wrap.insert(scroll_height, False)
    del apage.charbuf[from_line-1] 
    del apage.attrbuf[from_line-1]
    del apage.end[from_line-1]
    del apage.wrap[from_line-1]
    show_cursor(save_curs)
   
def scroll_down(from_line):
    global row, col, apage
    save_curs = show_cursor(False)    
    backend.scroll_down(from_line)
    if row >= from_line:
        row = row+1
    # sync buffers with the new screen reality:
    apage.charbuf.insert(from_line-1, [' ']*width)
    apage.attrbuf.insert(from_line-1, [attr]*width)
    apage.end.insert(from_line-1, 0)
    apage.wrap.insert(from_line-1, False)
    del apage.charbuf[scroll_height-1] 
    del apage.attrbuf[scroll_height-1]
    del apage.end[scroll_height-1]
    del apage.wrap[scroll_height-1]
    show_cursor(save_curs)

def pen_on():
    global pen_is_on
    pen_is_on = True

def pen_off():
    global pen_is_on
    pen_is_on=False    

def get_pen_pos():
    if pen_is_on and backend.supports_pen:
        return backend.get_pen_pos()
    else:    
        return (0,0)
    
def get_pen_pos_char():
    if pen_is_on and backend.supports_pen:
        return backend.get_pen_pos_char()
    else:    
        return (1, 1)
    
def get_last_pen_down_pos():
    if pen_is_on and backend.supports_pen:
        return backend.get_last_pen_down_pos()
    else:    
        return (0, 0)
           
def get_last_pen_down_pos_char():
    if pen_is_on and backend.supports_pen:
        return backend.get_last_pen_down_pos_char()
    else:    
        return (1, 1)
                
def pen_is_down():
    if pen_is_on and backend.supports_pen:
        return backend.pen_is_down()
    else:
        return False

def pen_has_been_down():
    if pen_is_on and backend.supports_pen:
        return backend.pen_has_been_down()
    else:
        return False
  
def stick_on():
    global stick_is_on
    stick_is_on = True

def stick_off():
    global stick_is_on
    stick_is_on = False    
  
def stick_coord(num):
    if stick_is_on and backend.supports_stick:
        return backend.stick_coord(num)
    else:    
        return 0,0
  
def stick_trig(num, ntrig):
    if stick_is_on and backend.supports_stick:
        return backend.stick_trig(num, ntrig)
    else:    
        return False
    
def stick_has_been_trig(num, ntrig):
    if stick_is_on and backend.supports_stick:
        return backend.stick_has_been_trig(num, ntrig)
    else:    
        return False

    
