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

import logging

import state
import backend
import on_event
import sound
# for Break, Exit, Reset
import error
# for aspect ratio
import fp

class ScreenRow(object):
    def __init__(self, bwidth):
        # screen buffer, initialised to spaces, dim white on black
        self.clear()
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self):
        self.buf = [(' ', state.console_state.attr)] * state.console_state.width
        # last non-white character
        self.end = 0    

class ScreenBuffer(object):
    def __init__(self, bwidth, bheight):
        self.row = [ScreenRow(bwidth) for _ in xrange(bheight)]
        
# default codes for KEY autotext
# F1-F10 
function_key = { 
        '\x00\x3b':0, '\x00\x3c':1, '\x00\x3d':2, '\x00\x3e':3, '\x00\x3f':4,     
        '\x00\x40':5, '\x00\x41':6, '\x00\x42':7, '\x00\x43':8, '\x00\x44':9 }

alt_key_replace = {
    '\x00\x1E': 'AUTO',  '\x00\x30': 'BSAVE',  '\x00\x2E': 'COLOR',  '\x00\x20': 'DELETE', '\x00\x12': 'ELSE', 
    '\x00\x21': 'FOR',   '\x00\x22': 'GOT0',   '\x00\x23': 'HEX$',   '\x00\x17': 'INPUT',
    '\x00\x25': 'KEY',   '\x00\x26': 'LOCATE', '\x00\x32': 'MOTOR',  '\x00\x31': 'NEXT',   '\x00\x18': 'OPEN', 
    '\x00\x19': 'PRINT', '\x00\x13': 'RUN',    '\x00\x1F': 'SCREEN', '\x00\x14': 'THEN',   '\x00\x16': 'USING', 
    '\x00\x2F': 'VAL',   '\x00\x11': 'WIDTH',  '\x00\x2D': 'XOR' }

# on the keys line 25, what characters to replace & with which
keys_line_replace_chars = { 
        '\x07': '\x0e',    '\x08': '\xfe',    '\x09': '\x1a',    '\x0A': '\x1b',
        '\x0B': '\x7f',    '\x0C': '\x16',    '\x0D': '\x1b',    '\x1C': '\x10',
        '\x1D': '\x11',    '\x1E': '\x18',    '\x1F': '\x19',
    }        
    
# KEY ON?
state.console_state.keys_visible = True
# user definable key list
state.console_state.key_replace = [ 
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r','TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r' ]

# number of columns, counting 1..width
state.console_state.width = 80
# number of rows, counting 1..height
state.console_state.height = 25

# viewport parameters
state.console_state.view_start = 1
state.console_state.scroll_height = 24
state.console_state.view_set = False
# writing on bottom row is allowed    
state.console_state.bottom_row_allowed = False

# current attribute
state.console_state.attr = 7
# current row and column
state.console_state.row = 1
state.console_state.col = 1

# cursor visible?
state.console_state.cursor = True
# overwrite mode (instead of insert)
state.console_state.overwrite_mode = True
# cursor shape
state.console_state.cursor_from = 0
state.console_state.cursor_to = 0    

# key buffer
# incoming keys, either ascii or \00 followed by INKEY$ scancode 
state.console_state.keybuf = ''
# INP(&H60) scancode
state.console_state.inp_key = 0

# echo to printer or dumb terminal
state.console_state.input_echos = []
state.console_state.output_echos = []

# input has closed
state.console_state.input_closed = False
# capslock mode 
state.console_state.caps = False


# pen and stick
state.console_state.pen_is_on = False
state.console_state.stick_is_on = False

# for SCREEN

#  font_height, attr, num_colours, num_palette, width, num_pages, bitsperpixel, font_width
mode_data = {
    0: ( 16,  7, 32, 64, 80, 4, 4, 8 ), # height 8, 14, or 16; font width 8 or 9; height 40 or 80 
    1: (  8,  3,  4, 16, 40, 1, 2, 8 ),
    2: (  8,  1,  2, 16, 80, 1, 1, 8 ), 
    3: (  8, 15, 16, 16, 20, 2, 4, 8 ),
    4: (  8, 15,  4, 16, 40, 2, 2, 8 ),      
    5: (  8, 15, 16, 16, 40, 1, 4, 8 ),      
    6: (  8, 15,  4, 16, 80, 1, 2, 8 ),      
    7: (  8, 15, 16, 16, 40, 8, 4, 8 ),
    8: (  8, 15, 16, 16, 80, 4, 4, 8 ),
    9: ( 14, 15, 16, 64, 80, 2, 4, 8 ),
    }

# default is EGA 64K
state.console_state.video_mem_size = 65536
# officially, whether colours are displayed. in reality, SCREEN just clears the screen if this value is changed
state.console_state.colorswitch = 1
# SCREEN mode (0 is textmode)
state.console_state.screen_mode = 0
# number of active page
state.console_state.apagenum = 0
# number of visible page
state.console_state.vpagenum = 0

# codepage suggestion for backend
state.console_state.codepage = '437'    


#############################
# init

def init():
    if not backend.video.init():
        return False
    state.console_state.backend_name = backend.video.__name__
    # only allow the screen modes that the given machine supports
    if state.basic_state.machine in ('pcjr', 'tandy'):
        # no EGA modes (though apparently there were Tandy machines with EGA cards too)
        unavailable_modes = (7, 8, 9)
        # 8-pixel characters in screen 0
        mode_data[0] = ( 8, 7, 32, 64, 80, 4, 4, 8 ) 
        # TODO: determine the number of pages based on video memory size, not hard coded. 
    else:
        # no PCjr modes
        unavailable_modes = (3, 4, 5, 6)
    for mode in unavailable_modes:
        del mode_data[mode]
    if state.loaded:
        if state.console_state.screen_mode != 0 and not backend.video.supports_graphics:
            logging.warning("Screen mode not supported by display backend.")
            # fix the terminal
            backend.video.close()
            return False
        # set up the appropriate screen resolution
        backend.video.init_screen_mode()
        # load the screen contents from storage
        backend.video.load_state()
    else:        
        screen(None, None, None, None, first_run=True)
    return True

def screen(new_mode, new_colorswitch, new_apagenum, new_vpagenum, erase=1, first_run=False, new_width=None):
    new_mode = state.console_state.screen_mode if new_mode == None else new_mode
    new_colorswitch = state.console_state.colorswitch if new_colorswitch == None else (new_colorswitch != 0)
    new_vpagenum = state.console_state.vpagenum if new_vpagenum == None else new_vpagenum
    new_apagenum = state.console_state.apagenum if new_apagenum == None else new_apagenum
    do_redraw = (   (new_mode != state.console_state.screen_mode) or (new_colorswitch != state.console_state.colorswitch) 
                    or first_run or (new_width and new_width != state.console_state.width) )
    # TODO: implement erase level (Tandy/pcjr)
    # Erase tells basic how much video memory to erase
    # 0: do not erase video memory
    # 1: (default) erase old and new page if screen or bust changes
    # 2: erase all video memory if screen or bust changes 
    try:
        info = mode_data[new_mode]
    except KeyError:
        # no such mode
        info = None
    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, illegal fn call before anything happens.
    if not info or new_apagenum >= info[5] or new_vpagenum >= info[5] or (new_mode != 0 and not backend.video.supports_graphics):
        # reset palette happens even if the function fails with Illegal Function Call
        set_palette()
        return False
    # switch modes if needed
    if do_redraw:
        if new_width == None:
            if new_mode == 0:
                new_width = state.console_state.width
            else:
                new_width = info[4]        
        if not (state.console_state.screen_mode == 0 and new_mode == 0 
                and state.console_state.apagenum == new_apagenum and state.console_state.vpagenum == new_vpagenum):
            # preserve attribute (but not palette) on screen 0 width switch
            state.console_state.attr = info[1]            
        # set all state vars
        state.console_state.screen_mode, state.console_state.colorswitch = new_mode, new_colorswitch 
        state.console_state.width, state.console_state.height = new_width, 25
        (   state.console_state.font_height, _, 
            state.console_state.num_colours, state.console_state.num_palette, _, 
            state.console_state.num_pages, state.console_state.bitsperpixel, state.console_state.font_width ) = info  
        # enforce backend palette maximum
        state.console_state.num_palette = min(state.console_state.num_palette, backend.video.max_palette)
        # width persists on change to screen 0
        state.console_state.pages = []
        for _ in range(state.console_state.num_pages):
            state.console_state.pages.append(ScreenBuffer(state.console_state.width, state.console_state.height))
        # set active page & visible page, counting from 0. 
        state.console_state.vpagenum, state.console_state.apagenum = new_vpagenum, new_apagenum
        state.console_state.vpage = state.console_state.pages[state.console_state.vpagenum]
        state.console_state.apage = state.console_state.pages[state.console_state.apagenum]
        # resolution
        state.console_state.size = (state.console_state.width*state.console_state.font_width,          
                                         state.console_state.height*state.console_state.font_height)
        # centre of new graphics screen
        state.console_state.last_point = (state.console_state.size[0]/2, state.console_state.size[1]/2)
        # pixels e.g. 80*8 x 25*14, screen ratio 4x3 makes for pixel width/height (4/3)*(25*14/8*80)
        # FIXME - hard coded 8-pixel width for graphics screens here.
        state.console_state.pixel_aspect_ratio = fp.div(
            fp.Single.from_int(state.console_state.height*state.console_state.font_height), 
            fp.Single.from_int(6*state.console_state.width)) 
        set_palette()
        # signal the backend to change the screen resolution
        backend.video.init_screen_mode()
        # only redraw keys if screen has been cleared (any colours stay the same). state.console_state.screen_mode must be set for this
        if state.console_state.keys_visible:  
            show_keys()    
        set_default_cursor()
        set_pos(1, 1)
        backend.video.update_cursor_visibility()
        # FIXME: are there different views for different pages?
        unset_view()
    else:
        # set active page & visible page, counting from 0. 
        state.console_state.vpagenum, state.console_state.apagenum = new_vpagenum, new_apagenum
        state.console_state.vpage = state.console_state.pages[state.console_state.vpagenum]
        state.console_state.apage = state.console_state.pages[state.console_state.apagenum]
        backend.video.screen_changed = True
        # FIXME: keys visible?
    return True


def copy_page(src, dst):
    for x in range(state.console_state.height):
        dstrow, srcrow = state.console_state.pages[dst].row[x], state.console_state.pages[src].row[x]
        dstrow.buf[:] = srcrow.buf[:]
        dstrow.end = srcrow.end
        dstrow.wrap = srcrow.wrap            
    backend.video.copy_page(src, dst)
    
# sort out the terminal, close the window, etc
def close():
    if backend.video:
        backend.video.close()

#############################

def set_palette_entry(index, colour):
    state.console_state.palette[index] = colour
    backend.video.update_palette()
    
def get_palette_entry(index):
    return state.console_state.palette[index]

def set_palette(new_palette=None):
    if new_palette:
        state.console_state.palette = new_palette
    else:    
        if state.console_state.num_palette == 64:
            state.console_state.palette = [0, 1, 2, 3, 4, 5, 20, 7, 56, 57, 58, 59, 60, 61, 62, 63]
        elif state.console_state.num_colours >= 16:
            state.console_state.palette = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        elif state.console_state.num_colours == 4:
            state.console_state.palette = [0, 11, 13, 15]
        else:
            state.console_state.palette = [0, 15]
    backend.video.update_palette()

def show_cursor(do_show = True):
    prev = state.console_state.cursor
    state.console_state.cursor = do_show
    backend.video.update_cursor_visibility()
    return prev

def set_cursor_shape(from_line, to_line):
    state.console_state.cursor_from = max(0, min(from_line, state.console_state.font_height-1))
    state.console_state.cursor_to = max(0, min(to_line, state.console_state.font_height-1))
    backend.video.build_cursor()
    
############################### 
# interactive mode         

def wait_screenline(write_endl=True, from_start=False, alt_replace=False):
    prompt_row = state.console_state.row
    savecurs = show_cursor() 
    try:
        furthest_left, furthest_right = wait_interactive(from_start, alt_replace)
    except error.Break:
        for echo in state.console_state.input_echos:  
            echo ('\x0e')
        write_line()    
        raise        
    show_cursor(savecurs)
    # find start of wrapped block
    crow = state.console_state.row
    while crow > 1 and state.console_state.apage.row[crow-2].wrap:
        crow -= 1
    line = []
    # add lines 
    while crow <= state.console_state.height:
        therow = state.console_state.apage.row[crow-1]
        # exclude prompt, if any; only go from furthest_left to furthest_right
        if crow == prompt_row and not from_start:
            line += therow.buf[:therow.end][furthest_left-1:furthest_right-1]
        else:    
            line += therow.buf[:therow.end]
        if therow.wrap:
            if therow.end < state.console_state.width:
                # wrap before end of line means LF
                line += ('\n', state.console_state.attr),
            crow += 1
        else:
            break
    # go to last line
    state.console_state.row = crow
    # echo the CR, if requested
    if write_endl:
        for echo in state.console_state.input_echos:
            echo('\r\n')
        set_pos(state.console_state.row+1, 1)
    # remove trailing whitespace 
    while len(line) > 0 and line[-1] in (' ', '\t', '\x0a'):
        line = line[:-1]
    outstr = bytearray()
    for c, _ in line:
        outstr += c
    return outstr[:255]    

def wait_interactive(from_start=False, alt_replace = True):
    # this is where we started
    start_row, furthest_left = state.console_state.row, (state.console_state.col if not from_start else 1)
    # this is where we arrow-keyed on the start line
    furthest_right = state.console_state.col 
    while True: 
        if state.console_state.row == start_row:
            furthest_left = min(state.console_state.col, furthest_left)
            furthest_right = max(state.console_state.col, furthest_right)
        # wait_char returns one ascii ar MS-DOS/GW-BASIC style keyscan code
        d = pass_char(wait_char())
        if not d:
            # input stream closed
            raise error.Exit()
        if d not in ('\r', '\x03'):
            for echo in state.console_state.input_echos:
                echo(d)
        if d in ('\x00\x48', '\x1E', '\x00\x50', '\x1F',  '\x00\x4D', '\x1C', '\x00\x4B', 
                    '\x1D', '\x00\x47', '\x0B', '\x00\x4F', '\x0E' ):
            set_overwrite_mode(True)
        if d == '\x03':         
            raise error.Break()    # not caught in wait_char like <CTRL+BREAK>
        elif d == '\r':                     break                                   # <ENTER>
        elif d == '\a':                     sound.beep()                            # <CTRL+G>
        elif d == '\b':                     backspace(start_row, furthest_left)     # <BACKSPACE>
        elif d == '\t':                     tab()                                   # <TAB> or <CTRL+I>
        elif d == '\n':                     line_feed()                             # <CTRL+ENTER> or <CTRL+J>
        elif d == '\x1B':                   clear_line(state.console_state.row)                     # <ESC> or <CTRL+[>
        elif d in ('\x00\x75', '\x05'):     clear_rest_of_line(state.console_state.row, state.console_state.col)  # <CTRL+END> <CTRL+E>
        elif d in ('\x00\x48', '\x1E'):     set_pos(state.console_state.row-1, state.console_state.col, scroll_ok=False)    # <UP> <CTRL+6>
        elif d in ('\x00\x50', '\x1F'):     set_pos(state.console_state.row+1, state.console_state.col, scroll_ok=False)    # <DOWN> <CTRL+->
        elif d in ('\x00\x4D', '\x1C'):     set_pos(state.console_state.row, state.console_state.col+1, scroll_ok=False)    # <RIGHT> <CTRL+\>
        elif d in ('\x00\x4B', '\x1D'):     set_pos(state.console_state.row, state.console_state.col-1, scroll_ok=False)    # <LEFT> <CTRL+]>
        elif d in ('\x00\x74', '\x06'):     skip_word_right()                       # <CTRL+RIGHT> or <CTRL+F>
        elif d in ('\x00\x73', '\x02'):     skip_word_left()                        # <CTRL+LEFT> or <CTRL+B>
        elif d in ('\x00\x52', '\x12'):     set_overwrite_mode(not state.console_state.overwrite_mode)  # <INS> <CTRL+R>
        elif d in ('\x00\x53', '\x7F'):     delete_char(state.console_state.row, state.console_state.col)                   # <DEL> <CTRL+BACKSPACE>
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
                    if not state.console_state.overwrite_mode:
                        insert_char(state.console_state.row, state.console_state.col, d, state.console_state.attr)
                        redraw_row(state.console_state.col-1, state.console_state.row)
                        set_pos(state.console_state.row, state.console_state.col+1)
                    else:    
                        put_char(d, do_scroll_down=True)
    set_overwrite_mode(True)
    return furthest_left, furthest_right
      
def set_overwrite_mode(new_overwrite=True):
    if new_overwrite != state.console_state.overwrite_mode:
        state.console_state.overwrite_mode = new_overwrite
        set_default_cursor()

def set_default_cursor():
    if state.console_state.overwrite_mode:
        if state.console_state.screen_mode != 0:
            set_cursor_shape(0, state.console_state.font_height-1)
        else:
            set_cursor_shape(state.console_state.font_height-2, state.console_state.font_height-2)
    else:
        set_cursor_shape(state.console_state.font_height/2, state.console_state.font_height-1)
      
def insert_char(crow, ccol, c, cattr):
    while True:
        therow = state.console_state.apage.row[crow-1]
        therow.buf.insert(ccol-1, (c, cattr))
        if therow.end < state.console_state.width:
            therow.buf.pop()
            if therow.end > ccol-1:
                therow.end += 1
            else:
                therow.end = ccol
            break
        else:
            if crow == state.console_state.scroll_height:
                scroll()
                # this is not the global row which is changed by scroll()
                crow -= 1
            if not therow.wrap and crow < state.console_state.height:
                scroll_down(crow+1)
                therow.wrap = True    
            c, cattr = therow.buf.pop()
            crow += 1
            ccol = 1
    return crow            
        
def delete_char(crow, ccol):
    save_col = ccol
    therow = state.console_state.apage.row[crow-1]
    if crow > 1 and ccol == therow.end+1 and therow.wrap:
        nextrow = state.console_state.apage.row[crow]
        # row was a LF-ending row
        therow.buf[ccol-1:] = nextrow.buf[:state.console_state.width-ccol+1] 
        therow.end = min(therow.end + nextrow.end, state.console_state.width)
        while crow < state.console_state.scroll_height and nextrow.wrap:
            nextrow2 = state.console_state.apage.row[crow+1]
            nextrow.buf = nextrow.buf[state.console_state.width-ccol+1:] + nextrow2.buf[:state.console_state.width-ccol+1]  
            nextrow.end = min(nextrow.end + nextrow2.end, state.console_state.width)
            crow += 1
            therow, nextrow = state.console_state.apage.row[crow-1], state.console_state.apage.row[crow]
        nextrow.buf = nextrow.buf[state.console_state.width-ccol+1:] + [(' ', state.console_state.attr)]*(state.console_state.width-ccol+1) 
        nextrow.end -= state.console_state.width - ccol    
        redraw_row(save_col-1, state.console_state.row)
        if nextrow.end <= 0:
            nextrow.end = 0
            ccol += 1
            therow.wrap = False
            scroll(crow+1)
    elif ccol <= therow.end:
        while True:            
            if therow.end < state.console_state.width or crow == state.console_state.scroll_height or not therow.wrap:
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, (' ', state.console_state.attr))
                break
            else:
                nextrow = state.console_state.apage.row[crow]
                # wrap and end[row-1]==width
                del therow.buf[ccol-1]
                therow.buf.insert(therow.end-1, nextrow.buf[0])
                crow += 1
                therow, nextrow = state.console_state.apage.row[crow-1], state.console_state.apage.row[crow]
                ccol = 1
        # this works from *global* row onwrds
        redraw_row(save_col-1, state.console_state.row)
        # this works on *local* row (last row edited)
        if therow.end > 0:
            therow.end -= 1
        else:
            scroll(crow)
            if crow > 1:
                state.console_state.apage.row[crow-2].wrap = False            

def redraw_row(start, crow):
    while True:
        therow = state.console_state.apage.row[crow-1]  
        backend.video.set_attr(state.console_state.attr)
        for i in range(start, therow.end): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            therow.buf[i] = (therow.buf[i][0], state.console_state.attr)
            backend.video.putc_at(crow, i+1, therow.buf[i][0])
        if therow.wrap and crow >= 0 and crow < state.console_state.height-1:
            crow += 1
            start = 0
        else:
            break    
    
def clear_line(the_row):
    # find start of line
    srow = the_row
    while srow > 1 and state.console_state.apage.row[srow-2].wrap:
        srow -= 1
    clear_rest_of_line(srow, 1)

def clear_rest_of_line(srow, scol):
    therow = state.console_state.apage.row[srow-1] 
    therow.buf = therow.buf[:scol-1] + [(' ', state.console_state.attr)]*(state.console_state.width-scol+1)
    therow.end = min(therow.end, scol-1)
    crow = srow
    while state.console_state.apage.row[crow-1].wrap:
        crow += 1
        state.console_state.apage.row[crow-1].clear() 
    for r in range(crow, srow, -1):
        state.console_state.apage.row[r-1].wrap = False
        scroll(r)
    therow = state.console_state.apage.row[srow-1]    
    therow.wrap = False
    set_pos(srow, scol)
    save_end = therow.end
    therow.end = state.console_state.width
    if scol > 1:
        redraw_row(scol-1, srow)
    else:
        backend.video.clear_rows(state.console_state.attr, srow, srow)
    therow.end = save_end

def backspace(start_row, start_col):
    crow, ccol = state.console_state.row, state.console_state.col
    # don't backspace through prompt
    if ccol == 1:
        if crow > 1 and state.console_state.apage.row[crow-2].wrap:
            ccol = state.console_state.apage.row[crow-2].end
            crow -= 1
    elif ccol != start_col or state.console_state.row != start_row: 
        ccol -= 1
    delete_char(crow, ccol)
    set_pos(crow, max(1, ccol))

def tab():
    if state.console_state.overwrite_mode:
        set_pos(state.console_state.row, state.console_state.col+8, scroll_ok=False)
    else:
        for _ in range(8):
            insert_char(state.console_state.row, state.console_state.col, ' ', state.console_state.attr)
        redraw_row(state.console_state.col-1, state.console_state.row)
        set_pos(state.console_state.row, state.console_state.col+8)
        
def end():
    crow = state.console_state.row
    while state.console_state.apage.row[crow-1].wrap and crow < state.console_state.height:
        crow += 1
    set_pos(crow, state.console_state.apage.row[crow-1].end+1)

def line_feed():
    # moves rest of line to next line
    if state.console_state.col < state.console_state.apage.row[state.console_state.row-1].end:
        for _ in range(state.console_state.width-state.console_state.col+1):
            insert_char(state.console_state.row, state.console_state.col, ' ', state.console_state.attr)
        redraw_row(state.console_state.col-1, state.console_state.row)
        state.console_state.apage.row[state.console_state.row-1].end = state.console_state.col-1 
    else:
        crow = state.console_state.row
        while state.console_state.apage.row[crow-1].wrap and crow < state.console_state.scroll_height:
            crow += 1
        if crow >= state.console_state.scroll_height:
            scroll()
        if state.console_state.row < state.console_state.height:    
            scroll_down(state.console_state.row+1)
    # LF connects lines like word wrap
    state.console_state.apage.row[state.console_state.row-1].wrap = True
    set_pos(state.console_state.row+1, 1)
    
def skip_word_right():
    crow, ccol = state.console_state.row, state.console_state.col
    # find non-alphanumeric chars
    while True:
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
        ccol += 1
        if ccol > state.console_state.width:
            if crow >= state.console_state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    # find alphanumeric chars
    while True:
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
        ccol += 1
        if ccol > state.console_state.width:
            if crow >= state.console_state.scroll_height:
                # nothing found
                return
            crow += 1
            ccol = 1
    set_pos(crow, ccol)                            
        
def skip_word_left():
    crow, ccol = state.console_state.row, state.console_state.col
    # find alphanumeric chars
    while True:
        ccol -= 1
        if ccol < 1:
            if crow <= state.console_state.view_start:
                # not found
                return
            crow -= 1
            ccol = state.console_state.width
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if not ((c < '0' or c > '9') and (c < 'A' or c > 'Z')):
            break
    # find non-alphanumeric chars
    while True:
        last_row, last_col = crow, ccol
        ccol -= 1
        if ccol < 1:
            if crow <= state.console_state.view_start:
                break
            crow -= 1
            ccol = state.console_state.width
        c = state.console_state.apage.row[crow-1].buf[ccol-1][0].upper()
        if (c < '0' or c > '9') and (c < 'A' or c > 'Z'):
            break
    set_pos(last_row, last_col)                            

def print_screen():
    for crow in range(1, state.console_state.height+1):
        line = ''
        for c, _ in state.console_state.vpage.row[crow-1].buf:
            line += c
        state.io_state.devices['LPT1:'].write_line(line)

def toggle_echo_lpt1():
    lpt1 = state.io_state.devices['LPT1:']
    if lpt1.write in state.console_state.input_echos:
        state.console_state.input_echos.remove(lpt1.write)
        state.console_state.output_echos.remove(lpt1.write)
    else:    
        state.console_state.input_echos.append(lpt1.write)
        state.console_state.output_echos.append(lpt1.write)

def clear():
    save_view_set, save_view_start, save_scroll_height = state.console_state.view_set, state.console_state.view_start, state.console_state.scroll_height
    set_view(1,25)
    clear_view()
    if save_view_set:
        set_view(save_view_start, save_scroll_height)
    else:
        unset_view()
    if state.console_state.keys_visible:
        show_keys()
        
##### output methods

def write(s, scroll_ok=True): 
    for echo in state.console_state.output_echos:
        # CR -> CRLF, CRLF -> CRLF LF
        echo(''.join([ ('\r\n' if c == '\r' else c) for c in s ]))
    last = ''
    for c in s:
        if c == '\t':                                       # TAB
            num = (8 - (state.console_state.col-1 - 8*int((state.console_state.col-1)/8)))
            for _ in range(num):
                put_char(' ')
        elif c == '\n':                                     # LF
            # exclude CR/LF
            if last != '\r': 
                # LF connects lines like word wrap
                state.console_state.apage.row[state.console_state.row-1].wrap = True
                set_pos(state.console_state.row+1, 1, scroll_ok)
        elif c == '\r':     
            state.console_state.apage.row[state.console_state.row-1].wrap = False
            set_pos(state.console_state.row+1, 1, scroll_ok)     # CR
        elif c == '\a':     sound.beep()                     # BEL
        elif c == '\x0B':   set_pos(1, 1, scroll_ok)         # HOME
        elif c == '\x0C':   clear()
        elif c == '\x1C':   set_pos(state.console_state.row, state.console_state.col+1, scroll_ok)
        elif c == '\x1D':   set_pos(state.console_state.row, state.console_state.col-1, scroll_ok)
        elif c == '\x1E':   set_pos(state.console_state.row-1, state.console_state.col, scroll_ok)
        elif c == '\x1F':   set_pos(state.console_state.row+1, state.console_state.col, scroll_ok)
        else:
            # includes \b, \0, and non-control chars
            put_char(c)
        last = c

def write_line(s='', scroll_ok=True): 
    write(s, scroll_ok=scroll_ok)
    for echo in state.console_state.output_echos:
        echo('\r\n')
    state.console_state.apage.row[state.console_state.row-1].wrap = False
    set_pos(state.console_state.row + 1, 1)

def set_width(to_width):
    # raise an error if the width value doesn't make sense
    if to_width not in (40, 80):
        return False
    if to_width == state.console_state.width:
        return True
    if state.console_state.screen_mode == 0:
        return screen(0, None, None, None, new_width=to_width) 
    elif state.console_state.screen_mode == 1 and to_width == 80:
        return screen(2, None, None, None)
    elif state.console_state.screen_mode == 2 and to_width == 40:
        return screen(1, None, None, None)
    elif state.console_state.screen_mode == 7 and to_width == 80:
        return screen(8, None, None, None)
    elif state.console_state.screen_mode == 8 and to_width == 40:
        return screen(7, None, None, None)
    elif state.console_state.screen_mode == 9 and to_width == 40:
        return screen(7, None, None, None)

#####################
# key replacement

def list_keys():
    for i in range(10):
        text = bytearray(state.console_state.key_replace[i])
        for j in range(len(text)):
            try:
                text[j] = keys_line_replace_chars[chr(text[j])]
            except KeyError:
                pass    
        write_line('F' + str(i+1) + ' ' + str(text))    

def clear_key_row():
    state.console_state.apage.row[24].clear()
    backend.video.clear_rows(state.console_state.attr, 25, 25)

def hide_keys():
    state.console_state.keys_visible = False
    clear_key_row()
                            
def show_keys():
    state.console_state.keys_visible = True
    clear_key_row()
    for i in range(state.console_state.width/8):
        text = str(state.console_state.key_replace[i][:6])
        kcol = 1+8*i
        write_for_keys(str(i+1)[-1], kcol, state.console_state.attr)
        if state.console_state.screen_mode:
            write_for_keys(text, kcol+1, state.console_state.attr)
        else:
            if (state.console_state.attr>>4) & 0x7 == 0:    
                write_for_keys(text, kcol+1, 0x70)
            else:
                write_for_keys(text, kcol+1, 0x07)
    state.console_state.apage.row[24].end = state.console_state.width           

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
            backend.video.set_attr(cattr)    
            backend.video.putc_at(25, col, c)    
            state.console_state.apage.row[24].buf[col-1] = c, cattr
        col += 1
    backend.video.set_attr(state.console_state.attr)     
    
##############################
# keyboard buffer read/write

# insert character into keyboard buffer; apply KEY repacement (for use by backends)
def insert_key(c):
    if len(c) > 0:
        try:
            keynum = state.basic_state.event_keys.index(c)
            if keynum > -1 and keynum < 20:
                if state.basic_state.key_handlers[keynum].enabled:
                    # trigger only once at most
                    state.basic_state.key_handlers[keynum].triggered = True
                    # don't enter into key buffer
                    return
        except ValueError:
            pass
    if state.console_state.caps:
        if c >= 'a' and c <= 'z':
            c = chr(ord(c)-32)
        elif c >= 'A' and c <= 'z':
            c = chr(ord(c)+32)
    if len(c) < 2:
        state.console_state.keybuf += c
    else:
        try:
            # only check F1-F10
            keynum = function_key[c]
            # can't be redefined in events - so must be event keys 1-10.
            if state.basic_state.run_mode and state.basic_state.key_handlers[keynum].enabled:
                # this key is being trapped, don't replace
                state.console_state.keybuf += c
            else:
                state.console_state.keybuf += state.console_state.key_replace[keynum]
        except KeyError:
            state.console_state.keybuf += c
    
# non-blocking keystroke read
def get_char():
    on_event.wait()    
    return pass_char( peek_char() )
    
# peek character from keyboard buffer
def peek_char():
    ch = ''
    if len(state.console_state.keybuf)>0:
        ch = state.console_state.keybuf[0]
        if ch == '\x00' and len(state.console_state.keybuf) > 0:
            ch += state.console_state.keybuf[1]
    return ch 

# drop character from keyboard buffer
def pass_char(ch):
    state.console_state.keybuf = state.console_state.keybuf[len(ch):]        
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
    while len(state.console_state.keybuf) == 0 and not state.console_state.input_closed:
        on_event.wait()
    return peek_char()
    
#####################
# screen read/write
    
def get_screen_char_attr(crow, ccol, want_attr):
    ca = state.console_state.apage.row[crow-1].buf[ccol-1][want_attr]
    return ca if want_attr else ord(ca)

def put_screen_char_attr(cpage, crow, ccol, c, cattr):
    cattr = cattr & 0xf if state.console_state.screen_mode else cattr
    backend.video.set_attr(cattr) 
    backend.video.putc_at(crow, ccol, c)    
    cpage.row[crow-1].buf[ccol-1] = (c, cattr)
    
def put_char(c, do_scroll_down=False):
    # check if scroll& repositioning needed
    check_pos(scroll_ok=True)
    put_screen_char_attr(state.console_state.apage, state.console_state.row, state.console_state.col, c, state.console_state.attr)
    therow = state.console_state.apage.row[state.console_state.row-1]
    therow.end = max(state.console_state.col, therow.end)
    state.console_state.col += 1
    if state.console_state.col > state.console_state.width:
        # wrap line
        therow.wrap = True
        if do_scroll_down:
            # scroll down
            if state.console_state.row < state.console_state.scroll_height:
                scroll_down(state.console_state.row+1)
        state.console_state.row += 1
        state.console_state.col = 1

def set_pos(to_row, to_col, scroll_ok=True):
    state.console_state.row, state.console_state.col = to_row, to_col
    check_pos(scroll_ok)
    backend.video.update_pos()

def check_pos(scroll_ok=True):
    oldrow, oldcol = state.console_state.row, state.console_state.col
    if state.console_state.bottom_row_allowed:
        if state.console_state.row == state.console_state.height:
            state.console_state.col = min(state.console_state.width, state.console_state.col)
            if state.console_state.col < 1:
                state.console_state.col += 1    
            return state.console_state.col == oldcol    
        else:
             # adjust viewport if necessary
            state.console_state.bottom_row_allowed = False
    # if row > height, we also end up here
    if state.console_state.col > state.console_state.width:
        if state.console_state.row < state.console_state.scroll_height or scroll_ok:
            state.console_state.col -= state.console_state.width
            state.console_state.row += 1
        else:
            state.console_state.col = state.console_state.width        
    elif state.console_state.col < 1:
        if state.console_state.row > state.console_state.view_start:
            state.console_state.col += state.console_state.width
            state.console_state.row -= 1
        else:
            state.console_state.col = 1   
    if state.console_state.row > state.console_state.scroll_height:
        if scroll_ok:
            scroll()                # Scroll Here
        state.console_state.row = state.console_state.scroll_height
    elif state.console_state.row < state.console_state.view_start:
        state.console_state.row = state.console_state.view_start
    # signal position change
    return state.console_state.row == oldrow and state.console_state.col == oldcol

def start_line():
    if state.console_state.col != 1:
        for echo in state.console_state.input_echos:
            echo('\r\n')
        state.console_state.apage.row[state.console_state.row-1].wrap = False    
        set_pos(state.console_state.row + 1, 1)

#####################
# viewport / scroll area

def set_view(start=1, stop=24):
    state.console_state.view_set, state.console_state.view_start, state.console_state.scroll_height = True, start, stop
    set_pos(start, 1)
 
def unset_view():
    set_view()
    state.console_state.view_set = False

def clear_view():
    for r in range(state.console_state.view_start, state.console_state.scroll_height+1):
        state.console_state.apage.row[r-1].clear()
        state.console_state.apage.row[r-1].wrap = False
    state.console_state.row, state.console_state.col = state.console_state.view_start, 1
    backend.video.clear_rows(state.console_state.attr, state.console_state.view_start, state.console_state.height if state.console_state.bottom_row_allowed else state.console_state.scroll_height)
            
def scroll(from_line=None): 
    if from_line == None:
        from_line = state.console_state.view_start
    backend.video.scroll(from_line)
    # sync buffers with the new screen reality:
    if state.console_state.row > from_line:
        state.console_state.row -= 1
    state.console_state.apage.row.insert(state.console_state.scroll_height, ScreenRow(state.console_state.width))
    del state.console_state.apage.row[from_line-1]
   
def scroll_down(from_line):
    backend.video.scroll_down(from_line)
    if state.console_state.row >= from_line:
        state.console_state.row += 1
    # sync buffers with the new screen reality:
    state.console_state.apage.row.insert(from_line-1, ScreenRow(state.console_state.width))
    del state.console_state.apage.row[state.console_state.scroll_height-1] 

################################################

def redraw_text_screen():
    if state.console_state.cursor:
        show_cursor(False)
    # this makes it feel faster
    backend.video.clear_rows(state.console_state.attr, 1, 25)
    # redraw every character
    for crow in range(state.console_state.height):
        therow = state.console_state.apage.row[crow]  
        for i in range(state.console_state.width): 
            backend.video.set_attr(therow.buf[i][1])
            backend.video.putc_at(crow+1, i+1, therow.buf[i][0])
    if state.console_state.cursor:
        show_cursor(True)       

################################################
        
def write_error_message(msg, linenum):
    start_line()
    write(msg) 
    if linenum != None and linenum > -1 and linenum < 65535:
        write(' in %i' % linenum)
    write_line(' ')                  

