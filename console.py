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

import event_loop
import util
# for Break, Exit, Reset
import error
# for aspect ratio
import fp

import state as state_module
from state import console_state as state

# codepage suggestion for backend
state.codepage = 437    

# number of columns, counting 1..width
state.width = 80
# number of rows, counting 1..height
state.height = 25

# viewport parameters
state.view_start = 1
state.scroll_height = 24
state.view_set = False
# writing on bottom row is allowed    
state.bottom_row_allowed = False

# current attribute
state.attr = 7
# current row and column
state.row = 1
state.col = 1

# cursor visible?
state.cursor = True
# overwrite mode (instead of insert)
state.overwrite_mode = False

# key buffer
# incoming keys, either ascii or \00 followed by INKEY$ scancode 
state.keybuf = ''
# INP(&H60) scancode
state.inp_key = 0

# echo to printer or dumb terminal
state.input_echos = []
state.output_echos = []

# input has closed
state.input_closed = False
# capslock mode 
state.caps = False

# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
state.colorswitch = 1
# SCREEN mode (0 is textmode)
state.screen_mode = 0
# number of active page
state.apagenum = 0
# number of visible page
state.vpagenum = 0

# palette
state.num_colours = 32    
state.num_palette = 64

# pen and stick
state.pen_is_on = False
state.stick_is_on = False
    

class ScreenRow(object):
    def __init__(self, bwidth):
        # screen buffer, initialised to spaces, dim white on black
        self.clear()
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self):
        self.buf = [(' ', state.attr)] * state.width
        # last non-white character
        self.end = 0    

class ScreenBuffer(object):
    def __init__(self, bwidth, bheight):
        self.row = [ScreenRow(bwidth) for _ in xrange(bheight)]
        
#  font_height, attr, num_colours, num_palette, width, num_pages
mode_data = {
    0: ( 16,  7, 32, 64, 80, 4 ),
    1: (  8,  3,  4, 16, 40, 1 ),
    2: (  8,  1,  2, 16, 80, 1 ), 
    7: (  8, 15, 16, 16, 40, 8 ),
    8: (  8, 15, 16, 16, 80, 4 ),
    9: ( 14, 15, 16, 64, 80, 2 ),
    }

# screen-mode dependent
# screen width and height in pixels
state.size = (0, 0)
state.pixel_aspect_ratio = fp.Single.one
state.bitsperpixel = 4

# default codes for KEY autotext
# F1-F10 
function_key = { 
        '\x00\x3b':0, '\x00\x3c':1, '\x00\x3d':2, '\x00\x3e':3, '\x00\x3f':4,     
        '\x00\x40':5, '\x00\x41':6, '\x00\x42':7, '\x00\x43':8, '\x00\x44':9 }

state.key_replace = [ 'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r','TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r' ]

alt_key_replace = {
    '\x00\x1E': 'AUTO',  '\x00\x30': 'BSAVE',  '\x00\x2E': 'COLOR',  '\x00\x20': 'DELETE', '\x00\x12': 'ELSE', 
    '\x00\x21': 'FOR',   '\x00\x22': 'GOT0',   '\x00\x23': 'HEX$',   '\x00\x17': 'INPUT',
    '\x00\x25': 'KEY',   '\x00\x26': 'LOCATE', '\x00\x32': 'MOTOR',  '\x00\x31': 'NEXT',   '\x00\x18': 'OPEN', 
    '\x00\x19': 'PRINT', '\x00\x13': 'RUN',    '\x00\x1F': 'SCREEN', '\x00\x14': 'THEN',   '\x00\x16': 'USING', 
    '\x00\x2F': 'VAL',   '\x00\x11': 'WIDTH',  '\x00\x2D': 'XOR' }

# KEY ON?
state.keys_visible = False

# on the keys line 25, what characters to replace & with which
keys_line_replace_chars = { 
        '\x07': '\x0e',    '\x08': '\xfe',    '\x09': '\x1a',    '\x0A': '\x1b',
        '\x0B': '\x7f',    '\x0C': '\x16',    '\x0D': '\x1b',    '\x1C': '\x10',
        '\x1D': '\x11',    '\x1E': '\x18',    '\x1F': '\x19',
    }        


#############################
# init


def init():
    global state
    if not state_module.video.init():
        return False
    # we need the correct mode and width here to ensure backend sets up correctly    
    state.width = state_module.console_state.width
    if not screen(state_module.console_state.screen_mode, None, None, None, first_run=True):
        import logging
        logging.warning("Screen mode not supported by display backend.")
        # fix the terminal
        state_module.video.close()
        return False
    # update state to what's set in state (if it was pickled, this overwrites earlier settings)
    state = state_module.console_state
    state_module.video.load_state()
    return True

def screen(new_mode, new_colorswitch, new_apagenum, new_vpagenum, first_run=False):
    new_mode = state.screen_mode if new_mode == None else new_mode
    new_colorswitch = state.colorswitch if new_colorswitch == None else (new_colorswitch != 0)
    new_vpagenum = state.vpagenum if new_vpagenum == None else new_vpagenum
    new_apagenum = state.apagenum if new_apagenum == None else new_apagenum
    do_redraw = (new_mode != state.screen_mode) or (new_colorswitch != state.colorswitch) or first_run
    # reset palette happens even if the function fails with Illegal Function Call
    try:
        info = mode_data[new_mode]
    except KeyError:
        # backend does not support mode
        set_palette()
        return False
    new_font_height, _, _, _, new_width, new_num_pages = info  
    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, illegal fn call before anything happens.
    if new_apagenum >= new_num_pages or new_vpagenum >= new_num_pages:
        set_palette()
        return False
    # switch modes if needed
    if do_redraw:
        if not state_module.video.init_screen_mode(new_mode, new_font_height):
            return False
        state.screen_mode, state.colorswitch = new_mode, new_colorswitch 
        # set all state vars except with
        state.font_height, state.attr, state.num_colours, state.num_palette, _, state.num_pages = info  
        # width persists on change to screen 0
        resize(25, state.width if new_mode == 0 else new_width)
        if not first_run:
            set_palette()
        else:
            set_palette(state_module.display_state.palette64)    
        set_overwrite_mode(True)
        init_graphics_mode(new_mode, new_font_height)      
        show_cursor(state.cursor)
        unset_view()
    # set active page & visible page, counting from 0.
    # this needs to be done after setup_screen!
    state.vpagenum, state.apagenum = new_vpagenum, new_apagenum
    state.vpage, state.apage = state.pages[state.vpagenum], state.pages[state.apagenum]
    # only redraw keys if screen has been cleared (any colours stay the same). state.screen_mode must be set for this
    if do_redraw and state.keys_visible:  
        show_keys()    
    state_module.video.screen_changed = True
    return True

def resize(to_height, to_width):
    state.width, state.height = to_width, to_height
    state.pages = []
    for _ in range(state.num_pages):
        state.pages.append(ScreenBuffer(state.width, state.height))
    state.vpage, state.apage = state.pages[0], state.pages[0]
    state_module.video.setup_screen(state.height, state.width)
    state.row, state.col = 1, 1

def init_graphics_mode(mode, new_font_height):
    if mode == 0:
        return
    state.size = (state.width*8, state.height*new_font_height)
    # centre of new graphics screen
    state.last_point = (state.width*4, state.height*new_font_height/2)
    # pixels e.g. 80*8 x 25*14, screen ratio 4x3 makes for pixel width/height (4/3)*(25*14/8*80)
    state.pixel_aspect_ratio = fp.div(
        fp.Single.from_int(state.height*new_font_height), 
        fp.Single.from_int(6*state.width)) 
    if mode in (1, 10):
        state.bitsperpixel = 2
    elif mode == 2:
        state.bitsperpixel = 1
    else:
        state.bitsperpixel = 4

def copy_page(src, dst):
    for x in range(state.height):
        dstrow, srcrow = state.pages[dst].row[x], state.pages[src].row[x]
        dstrow.buf[:] = srcrow.buf[:]
        dstrow.end = srcrow.end
        dstrow.wrap = srcrow.wrap            
    state_module.video.copy_page(src, dst)
    
# sort out the terminal, close the window, etc
def exit():
    if state_module.video:
        state_module.video.close()

#############################
    
def set_palette(new_palette=None):
    state_module.video.set_palette(new_palette)

def set_palette_entry(index, colour):
    state_module.video.set_palette_entry(index, colour)

def get_palette_entry(index):
    return state_module.video.get_palette_entry(index)
        
def show_cursor(do_show = True):
    prev = state.cursor
    state.cursor = do_show
    state_module.video.show_cursor(do_show, prev)
    return prev

def set_cursor_shape(from_line, to_line):
    state_module.video.build_shape_cursor(from_line, to_line)
    
############################### 
# interactive mode         

def wait_screenline(write_endl=True, from_start=False, alt_replace=False):
    prompt_row = state.row
    savecurs = show_cursor() 
    furthest_left, furthest_right = wait_interactive(from_start, alt_replace)
    show_cursor(savecurs)
    # find start of wrapped block
    crow = state.row
    while crow > 1 and state.apage.row[crow-2].wrap:
        crow -= 1
    line = []
    # add lines 
    while crow <= state.height:
        therow = state.apage.row[crow-1]
        # exclude prompt, if any; only go from furthest_left to furthest_right
        if crow == prompt_row and not from_start:
            line += therow.buf[:therow.end][furthest_left-1:furthest_right-1]
        else:    
            line += therow.buf[:therow.end]
        if therow.wrap:
            if therow.end < state.width:
                # wrap before end of line means LF
                line += ('\n', state.attr),
            crow += 1
        else:
            break
    # go to last line
    state.row = crow
    # echo the CR, if requested
    if write_endl:
        for echo in state.input_echos:
            echo('\r\n')
        set_pos(state.row+1, 1)
    # remove trailing whitespace 
    while len(line) > 0 and line[-1] in util.whitespace:
        line = line[:-1]
    outstr = bytearray()
    for c, _ in line:
        outstr += c
    return outstr[:255]    

def wait_interactive(from_start=False, alt_replace = True):
    # this is where we started
    start_row, furthest_left = state.row, (state.col if not from_start else 1)
    # this is where we arrow-keyed on the start line
    furthest_right = state.col 
    set_overwrite_mode(True) 
    while True: 
        if state.row == start_row:
            furthest_left = min(state.col, furthest_left)
            furthest_right = max(state.col, furthest_right)
        # wait_char returns one ascii ar MS-DOS/GW-BASIC style keyscan code
        d = pass_char(wait_char())
        if not d:
            # input stream closed
            raise error.Exit()
        if d not in ('\r', '\x03'):
            for echo in state.input_echos:
                echo(d)
        if d in ('\x00\x48', '\x1E', '\x00\x50', '\x1F',  '\x00\x4D', '\x1C', '\x00\x4B', 
                    '\x1D', '\x00\x47', '\x0B', '\x00\x4F', '\x0E' ):
            set_overwrite_mode(True)
        if d == '\x03':         
            for echo in state.input_echos:  
                echo ('\x0e')
            write_line()    
            raise error.Break()    # not caught in wait_char like <CTRL+BREAK>
        elif d == '\r':                     break                                   # <ENTER>
        elif d == '\a':                     state_module.sound.beep()                            # <CTRL+G>
        elif d == '\b':                     backspace(start_row, furthest_left)     # <BACKSPACE>
        elif d == '\t':                     tab()                                   # <TAB> or <CTRL+I>
        elif d == '\n':                     line_feed()                             # <CTRL+ENTER> or <CTRL+J>
        elif d == '\x1B':                   clear_line(state.row)                     # <ESC> or <CTRL+[>
        elif d in ('\x00\x75', '\x05'):     clear_rest_of_line(state.row, state.col)  # <CTRL+END> <CTRL+E>
        elif d in ('\x00\x48', '\x1E'):     set_pos(state.row-1, state.col, scroll_ok=False)    # <UP> <CTRL+6>
        elif d in ('\x00\x50', '\x1F'):     set_pos(state.row+1, state.col, scroll_ok=False)    # <DOWN> <CTRL+->
        elif d in ('\x00\x4D', '\x1C'):     set_pos(state.row, state.col+1, scroll_ok=False)    # <RIGHT> <CTRL+\>
        elif d in ('\x00\x4B', '\x1D'):     set_pos(state.row, state.col-1, scroll_ok=False)    # <LEFT> <CTRL+]>
        elif d in ('\x00\x74', '\x06'):     skip_word_right()                       # <CTRL+RIGHT> or <CTRL+F>
        elif d in ('\x00\x73', '\x02'):     skip_word_left()                        # <CTRL+LEFT> or <CTRL+B>
        elif d in ('\x00\x52', '\x12'):     set_overwrite_mode(not state.overwrite_mode)  # <INS> <CTRL+R>
        elif d in ('\x00\x53', '\x7F'):     delete_char(state.row, state.col)                   # <DEL> <CTRL+BACKSPACE>
        elif d in ('\x00\x47', '\x0B'):     set_pos(1, 1)                           # <HOME> <CTRL+K>
        elif d in ('\x00\x4F', '\x0E'):     end()                                   # <END> <CTRL+N>
        elif d in ('\x00\x77', '\x0C'):     clear()                                 # <CTRL+HOME> <CTRL+L>   
        elif d == '\x00\x37':               print_screen()                          # <SHIFT+PRT_SC>, already caught in wait_char()
        else:
            try:
                # these are done on a less deep level than the fn key replacement
                letters = list(alt_key_replace[d]) + [' ']
            except KeyError:
                letters = [d]
            if not alt_replace:
                letters = [d]
            for d in letters:        
                if d[0] not in ('\x00', '\r'): 
                    if not state.overwrite_mode:
                        insert_char(state.row, state.col, d, state.attr)
                        redraw_row(state.col-1, state.row)
                        set_pos(state.row, state.col+1)
                    else:    
                        put_char(d, do_scroll_down=True)
    set_overwrite_mode(True)
    return furthest_left, furthest_right
      
def set_overwrite_mode(new_overwrite=True):
    if new_overwrite != state.overwrite_mode:
        state.overwrite_mode = new_overwrite
        state_module.video.build_default_cursor(state.screen_mode, new_overwrite)
      
def insert_char(crow, ccol, c, cattr):
    while True:
        therow = state.apage.row[crow-1]
        therow.buf.insert(ccol-1, (c, cattr))
        if therow.end < state.width:
            therow.buf.pop()
            if therow.end > ccol-1:
                therow.end += 1
            else:
                therow.end = ccol
            break
        else:
            if crow == state.scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow -= 1
            if not therow.wrap and crow < state.height:
                scroll_down(crow+1)
                therow.wrap = True    
            c, cattr = therow.buf.pop()
            crow += 1
            ccol = 1
    return crow            
        
def delete_char(crow, ccol):
    save_col = ccol
    therow = state.apage.row[crow-1]
    if crow > 1 and ccol == therow.end+1 and therow.wrap:
        nextrow = state.apage.row[crow]
        # row was a LF-ending row
        therow.buf[ccol-1:] = nextrow.buf[:state.width-ccol+1] 
        therow.end = min(therow.end + nextrow.end, state.width)
        while crow < state.scroll_height and nextrow.wrap:
            nextrow2 = state.apage.row[crow+1]
            nextrow.buf = nextrow.buf[state.width-ccol+1:] + nextrow2.buf[:state.width-ccol+1]  
            nextrow.end = min(nextrow.end + nextrow2.end, state.width)
            crow += 1
            therow, nextrow = state.apage.row[crow-1], state.apage.row[crow]
        nextrow.buf = nextrow.buf[state.width-ccol+1:] + [(' ', state.attr)]*(state.width-ccol+1) 
        nextrow.end -= state.width - ccol    
        redraw_row(save_col-1, state.row)
        if nextrow.end <= 0:
            nextrow.end = 0
            ccol += 1
            therow.wrap = False
            scroll(crow+1)
    elif ccol <= therow.end:
        while True:            
            if therow.end < state.width or crow == state.scroll_height or not therow.wrap:
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, (' ', state.attr))
                break
            else:
                nextrow = state.apage.row[crow]
                # wrap and end[row-1]==width
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, nextrow.buf[0])
                crow += 1
                therow, nextrow = state.apage.row[crow-1], state.apage.row[crow]
                ccol = 1
        # this works from *global* row onwrds
        redraw_row(save_col-1, state.row)
        # this works on *local* row (last row edited)
        if therow.end > 0:
            therow.end -= 1
        else:
            scroll(crow)
            if crow > 1:
                state.apage.row[crow-2].wrap = False            

def redraw_row(start, crow):
    while True:
        therow = state.apage.row[crow-1]  
        state_module.video.set_attr(state.attr)
        for i in range(start, therow.end): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            therow.buf[i] = (therow.buf[i][0], state.attr)
            state_module.video.putc_at(crow, i+1, therow.buf[i][0])
        if therow.wrap and crow >= 0 and crow < state.height-1:
            crow += 1
            start = 0
        else:
            break    
    
def clear_line(the_row):
    # find start of line
    srow = the_row
    while srow > 1 and state.apage.row[srow-2].wrap:
        srow -= 1
    clear_rest_of_line(srow, 1)

def clear_rest_of_line(srow, scol):
    therow = state.apage.row[srow-1] 
    therow.buf = therow.buf[:scol-1] + [(' ', state.attr)]*(state.width-scol+1)
    therow.end = min(therow.end, scol-1)
    crow = srow
    while state.apage.row[crow-1].wrap:
        crow += 1
        state.apage.row[crow-1].clear() 
    for r in range(crow, srow, -1):
        state.apage.row[r-1].wrap = False
        scroll(r)
    therow = state.apage.row[srow-1]    
    therow.wrap = False
    set_pos(srow, scol)
    save_end = therow.end
    therow.end = state.width
    if scol > 1:
        redraw_row(scol-1, srow)
    else:
        state_module.video.clear_rows(state.attr, srow, srow)
    therow.end = save_end

def backspace(start_row, start_col):
    crow, ccol = state.row, state.col
    # don't backspace through prompt
    if ccol == 1:
        if crow > 1 and state.apage.row[crow-2].wrap:
            ccol = state.apage.row[crow-2].end
            crow -= 1
    elif ccol != start_col or state.row != start_row: 
        ccol -= 1
    delete_char(crow, ccol)
    set_pos(crow, max(1, ccol))

def tab():
    if state.overwrite_mode:
        set_pos(state.row, state.col+8, scroll_ok=False)
    else:
        for _ in range(8):
            insert_char(state.row, state.col, ' ', state.attr)
        redraw_row(state.col-1, state.row)
        set_pos(state.row, state.col+8)
        
def end():
    crow = state.row
    while state.apage.row[crow-1].wrap and crow < state.height:
        crow += 1
    set_pos(crow, state.apage.row[crow-1].end+1)

def line_feed():
    # moves rest of line to next line
    if state.col < state.apage.row[state.row-1].end:
        for _ in range(state.width-state.col+1):
            insert_char(state.row, state.col, ' ', state.attr)
        redraw_row(state.col-1, state.row)
        state.apage.row[state.row-1].end = state.col-1 
    else:
        crow = state.row
        while state.apage.row[crow-1].wrap and crow < state.scroll_height:
            crow += 1
        if crow >= state.scroll_height:
            scroll()
        if state.row < state.height:    
            scroll_down(state.row+1)
    # LF connects lines like word wrap
    state.apage.row[row-1].wrap = True
    set_pos(row+1, 1)
    
def skip_word_right():
    crow, ccol = state.row, state.col
    # find non-alphanumeric chars
    while True:
        c = state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
        ccol += 1
        if ccol > state.width:
            if crow >= state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    # find alphanumeric chars
    while True:
        c = state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
        ccol += 1
        if ccol > state.width:
            if crow >= state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    set_pos(crow, ccol)                            
        
def skip_word_left():
    crow, ccol = state.row, state.col
    # find alphanumeric chars
    while True:
        ccol -= 1
        if ccol < 1:
            if crow <= state.view_start:
                # not found
                return
            crow -= 1
            ccol = state.width
        c = state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
    # find non-alphanumeric chars
    while True:
        last_row, last_col = crow, ccol
        ccol -= 1
        if ccol < 1:
            if crow <= state.view_start:
                break
            crow -= 1
            ccol = state.width
        c = state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
    set_pos(last_row, last_col)                            

def print_screen():
    for crow in range(1, state.height+1):
        line = ''
        for c, _ in state.vpage.row[crow-1].buf:
            line += c
        state.io_state.devices['LPT1:'].write_line(line)

def toggle_echo_lpt1():
    lpt1 = state.io_state.devices['LPT1:']
    if lpt1.write in state.input_echos:
        state.input_echos.remove(lpt1.write)
        state.output_echos.remove(lpt1.write)
    else:    
        state.input_echos.append(lpt1.write)
        state.output_echos.append(lpt1.write)

def clear():
    save_view_set, save_view_start, save_scroll_height = state.view_set, state.view_start, state.scroll_height
    set_view(1,25)
    clear_view()
    if save_view_set:
        set_view(save_view_start, save_scroll_height)
    else:
        unset_view()
    if state.keys_visible:
        show_keys()
        
##### output methods

def write(s, scroll_ok=True): 
    for echo in state.output_echos:
        # CR -> CRLF, CRLF -> CRLF LF
        echo(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
    last = ''
    for c in s:
        if c == '\t':                                       # TAB
            num = (8 - (state.col-1 - 8*int((state.col-1)/8)))
            for _ in range(num):
                put_char(' ')
        elif c == '\n':                                     # LF
            # exclude CR/LF
            if last != '\r': 
                # LF connects lines like word wrap
                state.apage.row[state.row-1].wrap = True
                set_pos(state.row+1, 1, scroll_ok)
        elif c == '\r':     
            state.apage.row[state.row-1].wrap = False
            set_pos(state.row+1, 1, scroll_ok)     # CR
        elif c == '\a':     state_module.sound.beep()                     # BEL
        elif c == '\x0B':   set_pos(1, 1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(state.row, state.col+1, scroll_ok)
        elif c == '\x1D':   set_pos(state.row, state.col-1, scroll_ok)
        elif c == '\x1E':   set_pos(state.row-1, state.col, scroll_ok)
        elif c == '\x1F':   set_pos(state.row+1, state.col, scroll_ok)
        else:
            # includes \b, \0, and non-control chars
            put_char(c)
        last = c

def write_line(s='', scroll_ok=True): 
    write(s, scroll_ok=True)
    for echo in state.output_echos:
        echo('\r\n')
    state.apage.row[state.row-1].wrap = False
    set_pos(state.row + 1, 1)

def set_width(to_width):
    # raise an error if the width value doesn't make sense
    if to_width not in (40, 80):
        return False
    if to_width == state.width:
        return True
    success = True    
    if state.screen_mode == 0:
        resize(state.height, to_width)    
    elif state.screen_mode == 1 and to_width == 80:
        success = screen(2, None, None, None)
    elif state.screen_mode == 2 and to_width == 40:
        success = screen(1, None, None, None)
    elif state.screen_mode == 7 and to_width == 80:
        success = screen(8, None, None, None)
    elif state.screen_mode == 8 and to_width == 40:
        success = screen(7, None, None, None)
    elif state.screen_mode == 9 and to_width == 40:
        success = screen(7, None, None, None)
    if state.keys_visible:
        show_keys()
    return success

#####################
# key replacement

def list_keys():
    for i in range(10):
        text = bytearray(state.key_replace[i])
        for j in range(len(text)):
            try:
                text[j] = keys_line_replace_chars[chr(text[j])]
            except KeyError:
                pass    
        write_line('F' + str(i+1) + ' ' + str(text))    

def clear_key_row():
    state.apage.row[24].clear()
    state_module.video.clear_rows(state.attr, 25, 25)

def hide_keys():
    state.keys_visible = False
    clear_key_row()
                            
def show_keys():
    state.keys_visible = True
    clear_key_row()
    for i in range(state.width/8):
        text = str(state.key_replace[i][:6])
        kcol = 1+8*i
        write_for_keys(str(i+1)[-1], kcol, state.attr)
        if state.screen_mode:
            write_for_keys(text, kcol+1, state.attr)
        else:
            if (state.attr>>4) & 0x7 == 0:    
                write_for_keys(text, kcol+1, 0x70)
            else:
                write_for_keys(text, kcol+1, 0x07)
    state.apage.row[24].end = 80            

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
            state_module.video.set_attr(cattr)    
            state_module.video.putc_at(25, col, c)    
            state.apage.row[24].buf[col-1] = c, cattr
        col += 1
    state_module.video.set_attr(state.attr)     
    
##############################
# keyboard buffer read/write

# insert character into keyboard buffer; apply KEY repacement (for use by backends)
def insert_key(c):
    if state.caps:
        if c >= 'a' and c <= 'z':
            c = chr(ord(c)-32)
        elif c >= 'A' and c <= 'z':
            c = chr(ord(c)+32)
    if len(c) < 2:
        state.keybuf += c
    else:
        try:
            # only check F1-F10
            keynum = function_key[c]
            # can't be redefined in events - so must be event keys 1-10.
            if state_module.basic_state.run_mode and state.basic_state.key_handlers[keynum].enabled:
                state.keybuf += c
            else:
                state.keybuf += state.key_replace[keynum]
        except KeyError:
            state.keybuf += c
    
# non-blocking keystroke read
def get_char():
    event_loop.idle()    
    event_loop.check_events()
    return pass_char( peek_char() )
    
# peek character from keyboard buffer
def peek_char():
    ch = ''
    if len(state.keybuf)>0:
        ch = state.keybuf[0]
        if ch == '\x00' and len(state.keybuf) > 0:
            ch += state.keybuf[1]
    return ch 

# drop character from keyboard buffer
def pass_char(ch):
    state.keybuf = state.keybuf[len(ch):]        
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
    while len(state.keybuf)==0 and not state.input_closed:
        event_loop.idle()
        event_loop.check_events()
    return peek_char()
    
#####################
# screen read/write
    
def get_screen_char_attr(crow, ccol, want_attr):
    ca = state.apage.row[crow-1].buf[ccol-1][want_attr]
    return ca if want_attr else ord(ca)

def put_screen_char_attr(cpage, crow, ccol, c, cattr):
    cattr = cattr & 0xf if state.screen_mode else cattr
    state_module.video.set_attr(cattr) 
    state_module.video.putc_at(crow, ccol, c)    
    cpage.row[crow-1].buf[ccol-1] = (c, cattr)
    
def put_char(c, do_scroll_down=False):
    # check if scroll& repositioning needed
    check_pos(scroll_ok=True)
    put_screen_char_attr(state.apage, state.row, state.col, c, state.attr)
    therow = state.apage.row[state.row-1]
    therow.end = max(state.col, therow.end)
    state.col += 1
    if state.col > state.width:
        # wrap line
        therow.wrap = True
        if do_scroll_down:
            # scroll down
            if state.row < state.scroll_height:
                scroll_down(state.row+1)
        state.row += 1
        state.col = 1

def set_pos(to_row, to_col, scroll_ok=True):
    state.row, state.col = to_row, to_col
    check_pos(scroll_ok)
    state_module.video.set_cursor_colour(state.apage.row[state.row-1].buf[state.col-1][1] & 0xf)

def check_pos(scroll_ok=True):
    oldrow, oldcol = state.row, state.col
    if state.bottom_row_allowed:
        if state.row == state.height:
            state.col = min(state.width, state.col)
            if state.col < 1:
                state.col += 1    
            return state.col == oldcol    
        else:
             # adjust viewport if necessary
            state.bottom_row_allowed = False
    # if row > height, we also end up here
    if state.col > state.width:
        if state.row < state.scroll_height or scroll_ok:
            state.col -= state.width
            state.row += 1
        else:
            state.col = state.width        
    elif state.col < 1:
        if state.row > state.view_start:
            state.col += state.width
            state.row -= 1
        else:
            state.col = 1   
    if state.row > state.scroll_height:
        if scroll_ok:
            scroll()                # Scroll Here
        state.row = state.scroll_height
    elif state.row < state.view_start:
        state.row = state.view_start
    # signal position change
    return state.row == oldrow and state.col == oldcol

def start_line():
    if state.col != 1:
        for echo in state.input_echos:
            echo('\r\n')
        state.apage.row[state.row-1].wrap = False    
        set_pos(state.row + 1, 1)

#####################
# viewport / scroll area

def set_view(start=1, stop=24):
    state.view_set, state.view_start, state.scroll_height = True, start, stop
    set_pos(start, 1)
 
def unset_view():
    set_view()
    state.view_set = False

def clear_view():
    for r in range(state.view_start, state.scroll_height+1):
        state.apage.row[r-1].clear()
        state.apage.row[r-1].wrap = False
    state.row, state.col = state.view_start, 1
    state_module.video.clear_rows(state.attr, state.view_start, state.height if state.bottom_row_allowed else state.scroll_height)
            
def scroll(from_line=None): 
    if from_line == None:
        from_line = state.view_start
    state_module.video.scroll(from_line)
    # sync buffers with the new screen reality:
    if state.row > from_line:
        state.row -= 1
    state.apage.row.insert(state.scroll_height, ScreenRow(state.width))
    del state.apage.row[from_line-1]
   
def scroll_down(from_line):
    state_module.video.scroll_down(from_line)
    if state.row >= from_line:
        state.row += 1
    # sync buffers with the new screen reality:
    state.apage.row.insert(from_line-1, ScreenRow(state.width))
    del state.apage.row[state.scroll_height-1] 

################################################

def redraw_text_screen():
    if state.cursor:
        show_cursor(False)
    # this makes it feel faster
    state_module.video.clear_rows(state.attr, 1, 25)
    # redraw every character
    for crow in range(state.height):
        therow = state.apage.row[crow]  
        for i in range(state.width): 
            state_module.video.set_attr(therow.buf[i][1])
            state_module.video.putc_at(crow+1, i+1, therow.buf[i][0])
    if state.cursor:
        show_cursor(True)       

################################################
        
def write_error_message(msg, linenum):
    start_line()
    write(msg) 
    if linenum != None and linenum > -1 and linenum < 65535:
        write(' in %i' % linenum)
    write_line(' ')                  

