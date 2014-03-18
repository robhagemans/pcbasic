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
# for replace key
import program

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
last_row_is_on = False

# cursor/current characteristics
attr = 7
row = 1
col = 1
cursor = True
overwrite_mode = False

# incoming keys, either ascii or \00 followed by INKEY$ scancode 
keybuf = ''
# INP(&H60) scancode
inp_key = 0

# caps lock
caps = False

# echo to printer
echo_read = None
echo_write = None
    
class ScreenRow(object):
    def __init__(self, bwidth):
        # screen buffer, initialised to spaces, dim white on black
        self.clear()
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self):
        self.buf = [(' ', attr)] * width
        # last non-white character
        self.end = 0    

class ScreenBuffer(object):
    def __init__(self, bwidth, bheight):
        self.row = [ScreenRow(bwidth) for _ in xrange(bheight)]
        
# screen pages        
num_pages = 1            
pages = [ ScreenBuffer(width, height) ]
vpage = pages[0]
apage = pages[0]
vpagenum = 0
apagenum = 0

# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
colorswitch = None
# force building screen on start
screen_mode = None

# palette
num_colours = 32    
num_palette = 64
#  font_height, attr, colour_depth, width, num_pages
mode_data = {
    0: ( 16,  7, (32, 64), 80, 4 ),
    1: (  8,  3, ( 4, 16), 40, 1 ),
    2: (  8,  1, ( 2, 16), 80, 1 ), 
    7: (  8, 15, (16, 16), 40, 8 ),
    8: (  8, 15, (16, 16), 80, 4 ),
    9: ( 14, 15, (16, 64), 80, 2 ),
    }

# pen and stick
pen_is_on = False
stick_is_on = False

# KEY ON?
keys_visible = False
# default codes for KEY autotext
key_replace = [ 'LIST ', 'RUN\x0d', 'LOAD"', 'SAVE"', 'CONT\x0d', ',"LPT1:"\x0d','TRON\x0d', 'TROFF\x0d', 'KEY ', 'SCREEN 0,0,0\x0d' ]
# on the keys line 25, what characters to replace & with which
keys_line_replace_chars = { 
        '\x07': '\x0e',
        '\x08': '\xfe',
        '\x09': '\x1a',
        '\x0A': '\x1b',
        '\x0B': '\x7f',
        '\x0C': '\x16',
        '\x0D': '\x1b',
        '\x1C': '\x10',
        '\x1D': '\x11',
        '\x1E': '\x18',
        '\x1F': '\x19',
    }        


# KEY replacement    
# apply KEY autotext to scancodes
def replace_key(c):
    if len(c) < 2 or c[0] != '\x00':
        return c
    # only check F1-F10
    for keynum in range(10):
        # enabled means enabled for ON KEY events 
        if c == events.event_keys[keynum] and (not program.run_mode or not events.key_handlers[keynum].enabled): 
            return key_replace[keynum]
    return c

def init():
    backend.init()
    set_mode(0, 1, 0, 0)
    
def close():
    backend.close()

def idle():
    backend.idle()
    
def set_palette(new_palette=None):
    backend.set_palette(new_palette)

def set_palette_entry(index, colour):
    backend.set_palette_entry(index, colour)

def get_palette_entry(index):
    return backend.get_palette_entry(index)

def set_mode(mode, new_colorswitch, new_apagenum, new_vpagenum):
    global screen_mode, num_pages, colorswitch, apagenum, vpagenum, apage, vpage, attr
    new_colorswitch = colorswitch if new_colorswitch == None else (new_colorswitch != 0)
    new_vpagenum = vpagenum if new_vpagenum == None else new_vpagenum
    new_apagenum = apagenum if new_apagenum == None else new_apagenum
    try:
        info = mode_data[mode]
    except KeyError:
        # palette is reset if this happens
        set_palette()
        # backend does not support mode
        raise error.RunError(5)
    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, illegal fn call before anything happens.
    if new_apagenum >= info[4] or new_vpagenum >= info[4]:
        set_palette()
        raise error.RunError(5)    
    # switch modes if needed
    if mode != screen_mode or new_colorswitch != colorswitch:
        screen_mode, colorswitch = mode, new_colorswitch 
        font_height, attr, colour_depth, new_width, num_pages = info
        set_colour_depth(*colour_depth)
        backend.init_screen_mode(mode, font_height)  
        # width persists on change to screen 0
        resize(25, width if mode == 0 else new_width)
        set_overwrite_mode(True)
        graphics.init_graphics_mode(mode, font_height)      
        show_cursor(cursor)
        unset_view()
        if keys_visible:
            show_keys()
    # reset palette     
    set_palette()
    # set active page & visible page, counting from 0. if higher than max pages, illegal fn call.            
    # this needs to be done after setup_screen!
    vpagenum, apagenum = new_vpagenum, new_apagenum
    vpage, apage = pages[apagenum], pages[vpagenum]
    backend.screen_changed = True
    
def set_colour_depth(colours, palette):
    global num_colours
    global num_palette
    num_colours = colours
    num_palette = palette
    
# core event handler    
def check_events():
    # check console events
    backend.check_events()   
    # check&handle user events
    events.check_events()
    # manage sound queue
    sound.check_sound()

def write(s, scroll_ok=True): 
    if echo_write != None: 
        echo_write.write(s)
    last = ''
    for c in s:
        if c == '\x09':                                     # TAB
            num = (8 - (col-1 - 8*int((col-1)/8)))
            for _ in range(num):
                put_char(' ')
        elif c == '\x0A':                                   # LF
            # exclude CR/LF
            if last != '\x0D': 
                # LF connects lines like word wrap
                apage.row[row-1].wrap = True
                set_pos(row+1, 1, scroll_ok)
        elif c == '\x0D':   set_pos(row+1, 1, scroll_ok)     # CR
        elif c == '\x00':   put_char('\x00')                # NUL
        elif c == '\x07':   sound.beep()                    # BEL
        elif c == '\x0B':   set_pos(1, 1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(row, col+1, scroll_ok)
        elif c == '\x1D':   set_pos(row, col-1, scroll_ok)
        elif c == '\x1E':   set_pos(row-1, col, scroll_ok )
        elif c == '\x1F':   set_pos(row+1, col, scroll_ok)
        else:
            # \x08, \x00, and non-control chars
            put_char(c)
        last = c

def insert_char(crow, ccol, c, cattr):
    while True:
        therow = apage.row[crow-1]
        therow.buf.insert(ccol-1, (c, cattr))
        if therow.end < width:
            therow.buf.pop()
            if therow.end > ccol-1:
                therow.end += 1
            else:
                therow.end = ccol
            break
        else:
            if crow == scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow -= 1
            if not therow.wrap:
                scroll_down(crow+1)
                therow.wrap = True    
            c, cattr = therow.buf.pop()
            crow += 1
            ccol = 1
    return crow            
        
def delete_char(crow, ccol):
    save_col = ccol
    therow, nextrow = apage.row[crow-1], apage.row[crow]
    if crow > 1 and ccol == therow.end+1 and therow.wrap:
        # row was a LF-ending row
        therow.buf[ccol-1:] = nextrow.buf[:width-ccol+1] 
        therow.end = min(therow.end + nextrow.end, width)
        while nexrow.wrap and crow < scroll_height:
            nextrow2 = apage.row[crow+1]
            nextrow.buf = nextrow.buf[width-ccol+1:] + nextrow2.buf[:width-ccol+1]  
            nextrow.end = min(nextrow.end + nextrow2.end, width)
            crow += 1
            therow, nextrow = apage.row[crow-1], apage.row[crow]
        nextrow.buf = nextrow.buf[width-ccol+1:] + [(' ', attr)]*(width-ccol+1) 
        nextrow.end -= width - ccol    
        redraw_row(save_col-1, row)
        if nextrow.end <= 0:
            nextrow.end = 0
            ccol += 1
            therow.wrap = False
            scroll(crow+1)
    elif ccol <= therow.end:
        while True:            
            if therow.end < width or crow == scroll_height or not therow.wrap:
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, (' ', attr))
                break
            else:
                # wrap and end[row-1]==width
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, nextrow.buf[0])
                crow += 1
                therow, nextrow = apage.row[crow-1], apage.row[crow]
                ccol = 1
        # this works from *global* row onwrds
        redraw_row(save_col-1, row)
        # this works on *local* row (last row edited)
        if therow.end > 0:
            therow.end -= 1
        else:
            scroll(crow)
            if crow > 1:
                apage.row[crow-2].wrap = False            

def read_line():
    global row, col
    set_overwrite_mode(True) 
    c, inp = '', ''
    while c != '\x0d': 
        # get_char returns a string of ascii and MS-DOS/GW-BASIC style keyscan codes
        wait_char() 
        c = get_char()
        if echo_read:
            echo_read.write(c)
        pos = 0
        while pos < len(c):
            d = c[pos]
            pos += 1
            if d == '\x00' and len(c) > pos:
                d += c[pos]
                pos += 1
            if d == '\x03':            # <CTRL+C>, probably already caught in wait_char()
                raise error.Break()
            elif d == '\x07':                   # <CTRL+G>
                sound.beep()    
            elif d == '\x08':                   # <BACKSPACE>
                inp = inp[:-1]
                if col == 1:
                    if row > 1 and apage.row[row-2].wrap:
                        col = apage.row[row-2].end
                        row -= 1
                    else:
                        col = 1
                else: 
                    col -= 1
                delete_char(row, col)
                if col >= 1:
                    set_pos(row, col)
                else:
                    set_pos(row, 1)
            elif d == '\x09':                  #  <TAB> or <CTRL+I>
                inp = inp[:-1]
                if overwrite_mode:
                    set_pos(row, col+8, scroll_ok=False)
                else:
                    for _ in range(8):
                        insert_char(row, col, ' ', attr)
                    redraw_row(col-1, row)
                    set_pos(row, col+8)
            elif d == '\x0A':                   #  <CTRL+ENTER> or <CTRL+J>
                # moves rest of line to next line
                if col < apage.row[row-1].end:
                    for _ in range(width-col+1):
                        insert_char(row, col, ' ', attr)
                    redraw_row(col-1, row)
                    apage.row[row-1].end = col-1 
                else:
                    crow = row
                    while apage.row[crow-1].wrap and crow < scroll_height:
                        crow += 1
                    if crow >= scroll_height:
                        scroll()
                    scroll_down(row+1)
                # LF connects lines like word wrap
                apage.row[row-1].wrap = True
                set_pos(row+1, 1)
            elif d == '\x1B':                      # <ESC> or <CTRL+[>
                clear_line(row)
            elif d == '\x00\x75' or d == '\x05':   # <CTRL+END> <CTRL+E>
                clear_rest_of_line(row, col)   
            elif d == '\x00\x48' or d == '\x1E':   # <UP> <CTRL+6>
                set_overwrite_mode(True)
                set_pos(row-1, col, scroll_ok=False)
            elif d == '\x00\x50' or d == '\x1F':   # <DOWN> <CTRL+->
                set_overwrite_mode(True)
                set_pos(row+1, col, scroll_ok=False)
            elif d == '\x00\x4D' or d == '\x1C':   # <RIGHT> <CTRL+\>
                set_overwrite_mode(True)
                set_pos(row, col+1, scroll_ok=False)
            elif d == '\x00\x4B' or d == '\x1D':   # <LEFT> <CTRL+]>
                set_overwrite_mode(True)
                set_pos(row, col-1, scroll_ok=False)
            elif d == '\x00\x74' or d == '\x06':   # <CTRL+RIGHT> or <CTRL+F>
                skip_word_right()    
            elif d == '\x00\x73' or d == '\x02':   # <CTRL+LEFT> or <CTRL+B>
                skip_word_left() 
            elif d == '\x00\x52' or d == '\x12':   # <INS> <CTRL+R>
                set_overwrite_mode(not overwrite_mode)  
            elif d == '\x00\x53' or d == '\x7F':   # <DEL> <CTRL+BACKSPACE>
                delete_char(row, col)
            elif d == '\x00\x47' or d == '\x0B':   # <HOME> <CTRL+K>
                set_overwrite_mode(True)
                set_pos(1,1)
            elif d == '\x00\x4F' or d == '\x0E':   # <END> <CTRL+N>
                set_overwrite_mode(True)
                while apage.row[row-1].wrap and row < height:
                    row += 1
                set_pos(row, apage.row[row-1].end+1)
            elif d == '\x00\x77' or d == '\x0C':    # <CTRL+HOME> <CTRL+L>   
                clear()
            elif d == '\x00\x37':                   # <SHIFT+PRT_SC>
                print_screen()
            elif d[0] not in ('\x00', '\x0d'): 
                inp += d
                if not overwrite_mode:
                    insert_char(row, col, d, attr)
                    redraw_row(col-1, row)
                    set_pos(row, col+1)
                else:    
                    put_char(d)
    set_overwrite_mode(True)
    return inp  

def read_screenline(write_endl=True, from_start=False):
    global row, col
    prompt_row, prompt_col = row, col
    savecurs = show_cursor() 
    read_line()
    show_cursor(savecurs)
    # find start of wrapped block
    crow = row
    while crow > 1 and apage.row[crow-2].wrap:
        crow -= 1
    line = []
    # add lines 
    while crow <= height:
        therow = apage.row[crow-1]
        add = therow.buf[:therow.end]
        # exclude prompt, if any
        if crow == prompt_row and not from_start:
            add = add[prompt_col-1:]
        line += add
        if therow.wrap:
            if therow.end < width:
                # wrap before end of line means LF
                line += '\x0a'
            crow += 1
        else:
            break
    # go to last line
    row = crow
    if write_endl:
        write(util.endl)
    # remove trailing whitespace 
    while len(line) > 0 and line[-1] in util.whitespace:
        line = line[:-1]
    outstr = ''    
    for c, _ in line:
        outstr += c
    return outstr    

def clear_line(the_row):
    # find start of line
    srow = the_row
    while srow > 1 and apage.row[srow-2].wrap:
        srow -= 1
    clear_rest_of_line(srow, 1)

def clear_rest_of_line(srow, scol):
    therow = apage.row[srow-1] 
    therow.buf = therow.buf[:scol-1] + [(' ', attr)]*(width-scol+1)
    therow.end = min(therow.end, scol-1)
    crow = srow
    while apage.row[crow-1].wrap:
        crow += 1
        apage.row[crow-1].clear() 
    for r in range(crow, srow, -1):
        apage.row[r-1].wrap = False
        scroll(r)
    therow = apage.row[srow-1]    
    therow.wrap = False
    set_pos(srow, scol)
    save_end = therow.end
    therow.end = width
    if scol > 1:
        redraw_row(scol-1, srow)
    else:
        backend.clear_row(srow, (attr>>4) & 0x7)
    therow.end = save_end
    
def skip_word_right():
    crow, ccol = row, col
    # find non-alphanumeric chars
    while True:
        c = apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
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
        c = apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
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
        c = apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
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
        c = apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
    set_pos(last_row, last_col)                            

def print_screen():
    for crow in range(1, height+1):
        line = ''
        for c, _ in vpage[crow-1].buf:
            line += c
        deviceio.lpt1.write(line + util.endl)
    deviceio.lpt1.flush()    
        
def start_line():
    if col != 1:
        set_pos(row+1, 1)        

def set_width(to_width):
    resize(height, to_width)    
    if keys_visible:
        show_keys()

def read_screen(crow, ccol):
    return apage.row[crow-1].buf[ccol-1]

# insert character into keyboard buffer (for use by backends)
def insert_key(c):
    global keybuf 
    keybuf += replace_key(c)

# non-blocking keystroke read
def get_char():
    idle()    
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
    word = []
    for _ in range(num):
        wait_char()
        word.append(get_char())
    return word

# blocking keystroke peek
def wait_char():
    while len(keybuf)==0:
        idle()
        check_events()
    return peek_char()

def check_pos(scroll_ok=True):
    global row, col
    oldrow, oldcol = row, col
    if last_row_is_on:
        if row == height:
            col = min(width, col)
            if col < 1:
                col += 1    
            return col == oldcol    
        else:
             # adjust viewport if necessary
            last_row_on(False)            
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
    if row > scroll_height:
        if scroll_ok:
            scroll()                # Scroll Here
        row = scroll_height
    elif row < view_start:
        row = view_start
    # signal position change
    return row == oldrow and col == oldcol

def show_cursor(do_show = True):
    global cursor
    prev = cursor
    cursor = do_show
    backend.show_cursor(do_show, prev)
    return prev

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

def list_keys():
    for i in range(10):
        text = bytearray(key_replace[i])
        for j in range(len(text)):
            try:
                text[j] = keys_line_replace_chars[chr(text[j])]
            except KeyError:
                pass    
        write('F' + str(i+1) + ' ' + str(text) + util.endl)    

def write_for_keys(s, col, cattr):
    # write chars for the keys line - yes, it's different :)
    # with no echo
    for c in s:
        if c == '\x00':
            break
        else:
            try:
                c = keys_line_replace_chars[c]
            except KeyError:
                pass    
            backend.set_attr(cattr)    
            backend.putc_at(25, col, c)    
            apage.row[24].buf[col-1] = c, cattr
        col += 1

def clear_key_row():
    apage.row[24].clear()
    backend.clear_row(25, (attr>>4) & 0x7)

def hide_keys():
    global keys_visible
    keys_visible = False
    clear_key_row()
                            
def show_keys():
    global keys_visible
    keys_visible = True
    clear_key_row()
    for i in range(width/8):
        text = str(key_replace[i][:6])
        kcol = 1+8*i
        write_for_keys(str(i+1)[-1], kcol, attr)
        if screen_mode:
            write_for_keys(text, kcol+1, attr)
        else:
            if (attr>>4) & 0x7 == 0:    
                write_for_keys(text, kcol+1, 0x70)
            else:
                write_for_keys(text, kcol+1, 0x07)

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

def resize(to_height, to_width):
    global height, width
    global pages, vpage, apage    
    global row, col
    width, height = to_width, to_height
    pages = []
    for _ in range(num_pages):
        pages.append(ScreenBuffer(width, height))
    vpage, apage = pages[0], pages[0]
    backend.setup_screen(height, width)
    row, col = 1, 1

def copy_page(src, dst):
    global pages
    if src < num_pages and dst < num_pages:
        for x in range(height):
            dstrow, srcrow = pages[dst].row[x], pages[src].row[x]
            dstrow.buf = copy.copy(srcrow.buf)
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap            
        backend.copy_page(src,dst)
        return True
    else:
        return False
         
def clear_view():
    global row, col, apage 
    for r in range(view_start, scroll_height+1):
        apage.row[r-1].clear()
        apage.row[r-1].wrap = False
    row, col = view_start, 1
    backend.clear_scroll_area((attr>>4) & 0x7)
    
def set_pos(to_row, to_col, scroll_ok=True):
    global row, col
    row, col = to_row, to_col
    check_pos(scroll_ok)
    backend.set_cursor_colour(apage.row[row-1].buf[col-1][1] & 0xf)
    
def set_overwrite_mode(new_overwrite=True):
    global overwrite_mode
    if new_overwrite != overwrite_mode:
        overwrite_mode = new_overwrite
        backend.build_line_cursor(new_overwrite)

def set_cursor_shape(from_line, to_line):
    backend.build_shape_cursor(from_line, to_line)

def put_char(c):
    global row, col, attr
    # check if scroll& repositioning needed
    check_pos(scroll_ok=True)
    # no blink, bg=0
    cattr = attr & 0xf if screen_mode else attr
    backend.set_attr(cattr)
    backend.putc_at(row, col, c)    
    therow = apage.row[row-1]
    therow.buf[col-1] = (c, cattr)
    therow.end = max(col, therow.end)
    col += 1
    if col > width:
        # wrap line
        therow.wrap = True
        # scroll down
        scroll_down(row+1)
        row += 1
        col = 1
        
def redraw_row(start, crow):
    while True:
        therow = apage.row[crow-1]    
        backend.set_attr(attr)
        for i in range(start, therow.end): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            therow.buf[i] = (therow.buf[i][0], attr)
            backend.putc_at(crow, i+1, therow.buf[i][0])
        if therow.wrap and crow >= 0 and crow < height-1:
            crow += 1
            start = 0
        else:
            break    
    
def scroll(from_line=-1): 
    global row, col
    if from_line == -1:
        from_line = view_start
    backend.scroll(from_line)
    # sync buffers with the new screen reality:
    if row > from_line:
        row = row-1
    apage.row.insert(scroll_height, ScreenRow(width))
    del apage.row[from_line-1]
   
def scroll_down(from_line):
    global row, col, apage
    backend.scroll_down(from_line)
    if row >= from_line:
        row = row+1
    # sync buffers with the new screen reality:
    apage.row.insert(from_line-1, ScreenRow(width))
    del apage.row[scroll_height-1] 

def get_pen(fn):
    if events.pen_handler.enabled and backend.supports_pen:
        return backend.get_pen(fn)
    elif fn >= 6:
        return 1
    else:
        return 0    

def get_stick(fn):
    return backend.get_stick(fn) if (stick_is_on and backend.supports_stick) else 0
  
def get_strig(fn):
    return stick_is_on and backend.supports_stick and backend.get_strig(fn)
   
