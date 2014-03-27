#
# PC-BASIC 3.23 - console.py
#
# Console front-end
# 
# (c) 2013, 2014 Rob Hagemans 
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

import util
import error
import graphics
import nosound
import nopenstick
import events
# for print_screen
import deviceio
# for replace key
import program
# for exit
import run

# back end implementations
backend = None
sound = nosound
penstick = nopenstick

# number of columns, counting 1..width
width = 80
# number of rows, counting 1..height
height = 25
# viewport parameters
view_start = 1
scroll_height = 24
view_set = False
# writing on bottom row is allowed    
bottom_row_allowed = False

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

# echo to printer or dumb terminal
input_echos = []
output_echos = []

# input has closed
input_closed = False
    
# codepage suggestion for backend
codepage = 437    
    
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
        
# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
colorswitch = None
# force building screen on start
screen_mode = None

# palette
num_colours = 32    
num_palette = 64
#  font_height, attr, num_colours, num_palette, width, num_pages
mode_data = {
    0: ( 16,  7, 32, 64, 80, 4 ),
    1: (  8,  3,  4, 16, 40, 1 ),
    2: (  8,  1,  2, 16, 80, 1 ), 
    7: (  8, 15, 16, 16, 40, 8 ),
    8: (  8, 15, 16, 16, 80, 4 ),
    9: ( 14, 15, 16, 64, 80, 2 ),
    }

# pen and stick
pen_is_on = False
stick_is_on = False

# default codes for KEY autotext
# F1-F10 
function_key = { 
        '\x00\x3b':0, '\x00\x3c':1, '\x00\x3d':2, '\x00\x3e':3, '\x00\x3f':4,     
        '\x00\x40':5, '\x00\x41':6, '\x00\x42':7, '\x00\x43':8, '\x00\x44':9 }
key_replace = [ 'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r','TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r' ]

# KEY ON?
keys_visible = False
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

#############################
# core event handler    

def check_events():
    # check console events
    backend.check_events()   
    # check&handle user events
    events.check_events()
    # manage sound queue
    sound.check_sound()

def idle():
    backend.idle()

#############################
# init

def init():
    if not backend.init():
        return False
    set_mode(0, 1, 0, 0)
    return True

def set_mode(mode, new_colorswitch, new_apagenum, new_vpagenum):
    global screen_mode, num_pages, colorswitch, apagenum, vpagenum, apage, vpage, attr, num_colours, num_palette
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
        new_font_height = info[0]
        backend.init_screen_mode(mode, new_font_height) # this can fail with err(5)
        screen_mode, colorswitch = mode, new_colorswitch 
        font_height, attr, num_colours, num_palette, new_width, num_pages = info  
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
    for x in range(height):
        dstrow, srcrow = pages[dst].row[x], pages[src].row[x]
        dstrow.buf[:] = srcrow.buf[:]
        dstrow.end = srcrow.end
        dstrow.wrap = srcrow.wrap            
    backend.copy_page(src,dst)
    
# sort out the terminal, close the window, etc
def exit():
    if backend:
        backend.close()

#############################
    
def set_palette(new_palette=None):
    backend.set_palette(new_palette)

def set_palette_entry(index, colour):
    backend.set_palette_entry(index, colour)

def get_palette_entry(index):
    return backend.get_palette_entry(index)
    
def debug_print(s):
    return backend.debug_print(s)
        
def show_cursor(do_show = True):
    global cursor
    prev = cursor
    cursor = do_show
    backend.show_cursor(do_show, prev)
    return prev

def set_cursor_shape(from_line, to_line):
    backend.build_shape_cursor(from_line, to_line)
    
############################### 
# interactive mode         

def wait_screenline(write_endl=True, from_start=False):
    global row, col
    prompt_row, prompt_col = row, col
    savecurs = show_cursor() 
    wait_interactive()
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
                line += ('\n', attr),
            crow += 1
        else:
            break
    # go to last line
    row = crow
    # echo the CR, if requested
    if write_endl:
        for echo in input_echos:
            echo('\r\n')
        set_pos(row+1, 1)
    # remove trailing whitespace 
    while len(line) > 0 and line[-1] in util.whitespace:
        line = line[:-1]
    outstr = bytearray()
    for c, _ in line:
        outstr += c
    return outstr[:255]    

def wait_interactive():
    global row, col
    set_overwrite_mode(True) 
    while True: 
        # wait_char returns one ascii ar MS-DOS/GW-BASIC style keyscan code
        d = pass_char(wait_char())
        if not d:
            # input stream closed
            run.exit()
        if d != '\r':
            for echo in input_echos:
                echo(d)
        if d in ('\x00\x48', '\x1E', '\x00\x50', '\x1F',  '\x00\x4D', '\x1C', '\x00\x4B', 
                    '\x1D', '\x00\x47', '\x0B', '\x00\x4F', '\x0E' ):
            set_overwrite_mode(True)
        if d == '\x03':                     raise error.Break()                     # <CTRL+C>, probably already caught in wait_char()
        elif d == '\r':                     break                                   # <ENTER>
        elif d == '\a':                     sound.beep()                            # <CTRL+G>
        elif d == '\b':                     backspace()                             # <BACKSPACE>
        elif d == '\t':                     tab()                                   # <TAB> or <CTRL+I>
        elif d == '\n':                     line_feed()                             # <CTRL+ENTER> or <CTRL+J>
        elif d == '\x1B':                   clear_line(row)                         # <ESC> or <CTRL+[>
        elif d in ('\x00\x75', '\x05'):     clear_rest_of_line(row, col)            # <CTRL+END> <CTRL+E>
        elif d in ('\x00\x48', '\x1E'):     set_pos(row-1, col, scroll_ok=False)    # <UP> <CTRL+6>
        elif d in ('\x00\x50', '\x1F'):     set_pos(row+1, col, scroll_ok=False)    # <DOWN> <CTRL+->
        elif d in ('\x00\x4D', '\x1C'):     set_pos(row, col+1, scroll_ok=False)    # <RIGHT> <CTRL+\>
        elif d in ('\x00\x4B', '\x1D'):     set_pos(row, col-1, scroll_ok=False)    # <LEFT> <CTRL+]>
        elif d in ('\x00\x74', '\x06'):     skip_word_right()                       # <CTRL+RIGHT> or <CTRL+F>
        elif d in ('\x00\x73', '\x02'):     skip_word_left()                        # <CTRL+LEFT> or <CTRL+B>
        elif d in ('\x00\x52', '\x12'):     set_overwrite_mode(not overwrite_mode)  # <INS> <CTRL+R>
        elif d in ('\x00\x53', '\x7F'):     delete_char(row, col)                   # <DEL> <CTRL+BACKSPACE>
        elif d in ('\x00\x47', '\x0B'):     set_pos(1, 1)                           # <HOME> <CTRL+K>
        elif d in ('\x00\x4F', '\x0E'):     end()                                   # <END> <CTRL+N>
        elif d in ('\x00\x77', '\x0C'):     clear()                                 # <CTRL+HOME> <CTRL+L>   
        elif d == '\x00\x37':               print_screen()                          # <SHIFT+PRT_SC>, already caught in wait_char()
        elif d[0] not in ('\x00', '\r'): 
            if not overwrite_mode:
                insert_char(row, col, d, attr)
                redraw_row(col-1, row)
                set_pos(row, col+1)
            else:    
                put_char(d)
    set_overwrite_mode(True)
      
def set_overwrite_mode(new_overwrite=True):
    global overwrite_mode
    if new_overwrite != overwrite_mode:
        overwrite_mode = new_overwrite
        backend.build_default_cursor(screen_mode, new_overwrite)
      
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
            if not therow.wrap and crow < height:
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
        backend.clear_rows(attr, srow, srow)
    therow.end = save_end

def backspace():
    crow, ccol = row, col
    if ccol == 1:
        if crow > 1 and apage.row[crow-2].wrap:
            ccol = apage.row[crow-2].end
            crow -= 1
        else:
            ccol = 1
    else: 
        ccol -= 1
    delete_char(crow, ccol)
    set_pos(crow, max(1, ccol))

def tab():
    if overwrite_mode:
        set_pos(row, col+8, scroll_ok=False)
    else:
        for _ in range(8):
            insert_char(row, col, ' ', attr)
        redraw_row(col-1, row)
        set_pos(row, col+8)
        
def end():
    crow = row
    while apage.row[crow-1].wrap and crow < height:
        crow += 1
    set_pos(crow, apage.row[crow-1].end+1)

def line_feed():
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
        if row < height:    
            scroll_down(row+1)
    # LF connects lines like word wrap
    apage.row[row-1].wrap = True
    set_pos(row+1, 1)
    
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
        for c, _ in vpage.row[crow-1].buf:
            line += c
        deviceio.devices['LPT1:'].write_line(line)

def toggle_echo_lpt1():
    lpt1 = deviceio.devices['LPT1:']
    if lpt1.write in input_echos:
        input_echos.remove(lpt1.write)
        output_echos.remove(lpt1.write)
    else:    
        input_echos.append(lpt1.write)
        output_echos.append(lpt1.write)

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
        
##### i/o methods

def write(s, scroll_ok=True): 
    for echo in output_echos:
        # CR -> CRLF, CRLF -> CRLF LF
        echo(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
    last = ''
    for c in s:
        if c == '\t':                                       # TAB
            num = (8 - (col-1 - 8*int((col-1)/8)))
            for _ in range(num):
                put_char(' ')
        elif c == '\n':                                     # LF
            # exclude CR/LF
            if last != '\r': 
                # LF connects lines like word wrap
                apage.row[row-1].wrap = True
                set_pos(row+1, 1, scroll_ok)
        elif c == '\r':     set_pos(row+1, 1, scroll_ok)     # CR
        elif c == '\a':     sound.beep()                     # BEL
        elif c == '\x0B':   set_pos(1, 1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(row, col+1, scroll_ok)
        elif c == '\x1D':   set_pos(row, col-1, scroll_ok)
        elif c == '\x1E':   set_pos(row-1, col, scroll_ok)
        elif c == '\x1F':   set_pos(row+1, col, scroll_ok)
        else:
            # includes \b, \0, and non-control chars
            put_char(c)
        last = c

def write_line(s='', scroll_ok=True): 
    write(s, scroll_ok=True)
    for echo in output_echos:
        echo('\r\n')
    set_pos(row+1, 1)

def set_width(to_width):
    # raise an error if the width value doesn't make sense
    if to_width not in (40, 80):
        raise error.RunError(5)
    if to_width == width:
        return    
    if screen_mode == 0:
        resize(height, to_width)    
    elif screen_mode == 1 and to_width == 80:
        set_mode(2, None, None, None)
    elif screen_mode == 2 and to_width == 40:
        set_mode(1, None, None, None)
    elif screen_mode == 7 and to_width == 80:
        set_mode(8, None, None, None)
    elif screen_mode == 8 and to_width == 40:
        set_mode(7, None, None, None)
    elif screen_mode == 9 and to_width == 40:
        set_mode(7, None, None, None)
    if keys_visible:
        show_keys()

def close():
    pass

#####################
# key replacement

def list_keys():
    for i in range(10):
        text = bytearray(key_replace[i])
        for j in range(len(text)):
            try:
                text[j] = keys_line_replace_chars[chr(text[j])]
            except KeyError:
                pass    
        write_line('F' + str(i+1) + ' ' + str(text))    

def clear_key_row():
    apage.row[24].clear()
    backend.clear_rows(attr, 25, 25)

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
    apage.row[24].end = 80            

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
    backend.set_attr(attr)     
    
##############################
# keyboard buffer read/write

# insert character into keyboard buffer; apply KEY repacement (for use by backends)
def insert_key(c):
    global keybuf 
    if len(c) < 2:
        keybuf += c
    else:
        try:
            # only check F1-F10
            keynum = function_key[c]
            # can't be redefined in events - so must be event keys 1-10.
            if program.run_mode and events.key_handlers[keynum].enabled:
                keybuf += c
            else:
                keybuf += key_replace[keynum]
        except KeyError:
            keybuf += c
    
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
    while len(keybuf)==0 and not input_closed:
        idle()
        check_events()
    return peek_char()
    
#####################
# screen read/write
    
def get_screen_char_attr(crow, ccol, want_attr):
    ca = apage.row[crow-1].buf[ccol-1][want_attr]
    return ca if want_attr else ord(ca)
    
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
        if row < height:
            scroll_down(row+1)
        row += 1
        col = 1

def set_pos(to_row, to_col, scroll_ok=True):
    global row, col
    row, col = to_row, to_col
    check_pos(scroll_ok)
    backend.set_cursor_colour(apage.row[row-1].buf[col-1][1] & 0xf)

def check_pos(scroll_ok=True):
    global row, col, bottom_row_allowed
    oldrow, oldcol = row, col
    if bottom_row_allowed:
        if row == height:
            col = min(width, col)
            if col < 1:
                col += 1    
            return col == oldcol    
        else:
             # adjust viewport if necessary
            bottom_row_allowed = False
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

def start_line():
    if col != 1:
        for echo in input_echos:
            echo('\r\n')
        set_pos(row+1, 1)

#####################
# viewport / scroll area

def set_view(start=1, stop=24):
    global view_start, scroll_height, view_set
    view_set, view_start, scroll_height = True, start, stop
    set_pos(start, 1)
 
def unset_view():
    global view_set
    set_view()
    view_set = False

def clear_view():
    global row, col, apage 
    for r in range(view_start, scroll_height+1):
        apage.row[r-1].clear()
        apage.row[r-1].wrap = False
    row, col = view_start, 1
    backend.clear_rows(attr, view_start, height if bottom_row_allowed else scroll_height)
            
def scroll(from_line=None): 
    global row, col
    if from_line == None:
        from_line = view_start
    backend.scroll(from_line)
    # sync buffers with the new screen reality:
    if row > from_line:
        row -= 1
    apage.row.insert(scroll_height, ScreenRow(width))
    del apage.row[from_line-1]
   
def scroll_down(from_line):
    global row, col
    backend.scroll_down(from_line)
    if row >= from_line:
        row += 1
    # sync buffers with the new screen reality:
    apage.row.insert(from_line-1, ScreenRow(width))
    del apage.row[scroll_height-1] 

