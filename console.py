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
# for dbcs
import unicodepage
import typeface

class ScreenRow(object):
    def __init__(self, bwidth):
        # screen buffer, initialised to spaces, dim white on black
        self.clear()
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self):
        self.buf = [(' ', state.console_state.attr)] * state.console_state.width
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * state.console_state.width
        # last non-white character
        self.end = 0    

class ScreenBuffer(object):
    def __init__(self, bwidth, bheight):
        self.row = [ScreenRow(bwidth) for _ in xrange(bheight)]
        
# default codes for KEY autotext
# F1-F10 
function_key = { 
        '\x00\x3b':0, '\x00\x3c':1, '\x00\x3d':2, '\x00\x3e':3, '\x00\x3f':4,     # F1-F5
        '\x00\x40':5, '\x00\x41':6, '\x00\x42':7, '\x00\x43':8, '\x00\x44':9,     # F6-F10    
        '\x00\x98':10, '\x00\x99':11 } # Tandy F11 and F12, these scancodes should *only* be sent on Tandy

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
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r','TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '' ]

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
# true if we're on 80 but should be on 81
state.console_state.overflow = False

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
    1: (  8,  3,  4, 16, 40, 1, 2, 8 ), # 04h 320x200x4  16384B 2bpp 0xb8000 tandy:2 pages if 32k memory; ega: 1 page only 
    2: (  8,  1,  2, 16, 80, 1, 1, 8 ), # 06h 640x200x2  16384B 1bpp 0xb8000
    3: (  8, 15, 16, 16, 20, 2, 4, 8 ), # 08h 160x200x16 16384B 4bpp 0xb8000
    4: (  8,  3,  4, 16, 40, 2, 2, 8 ), #     320x200x4  16384B 2bpp 0xb8000   
    5: (  8, 15, 16, 16, 40, 1, 4, 8 ), # 09h 320x200x16 32768B 4bpp 0xb8000    
    6: (  8,  3,  4, 16, 80, 1, 2, 8 ), # 0Ah 640x200x4  32768B 2bpp 0xb8000   
    7: (  8, 15, 16, 16, 40, 8, 4, 8 ), # 0Dh 320x200x16 32768B 4bpp 0xa0000
    8: (  8, 15, 16, 16, 80, 4, 4, 8 ), # 0Eh 640x200x16 
    9: ( 14, 15, 16, 64, 80, 2, 4, 8 ), # 10h 640x350x16 
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

# ega, tandy, pcjr
video_capabilities = 'ega'
# video memory size - currently only used by tandy/pcjr (would be bigger for EGA systems anyway)
state.console_state.pcjr_video_mem_size = 16384

# cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
cga_palette_1_hi = [0, 11, 13, 15]
cga_palette_1_lo = [0, 3, 5, 7]
# cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
cga_palette_0_hi = [0, 10, 12, 14]
cga_palette_0_lo = [0, 2, 4, 6]
# tandy/pcjr cga palette
cga_palette_1_pcjr = [0, 3, 5, 15]
cga_palette_0_pcjr = [0, 2, 4, 6]
# mode 5 (SCREEN 1 + colorburst) palette on RGB monitor
cga_palette_5_hi = [0, 11, 12, 15]
cga_palette_5_lo = [0, 3, 4, 7]
# default: high intensity 
cga_palette_0 = cga_palette_0_hi
cga_palette_1 = cga_palette_1_hi
cga_palette_5 = cga_palette_5_hi
cga_palettes = [cga_palette_0, cga_palette_1]

# default font family
font_families = ['unifont', 'univga', 'freedos']
fonts = {}

#############################
# init

def init():
    global cga_palettes, fonts, mode_data
    if not backend.video.init():
        return False
    state.console_state.backend_name = backend.video.__name__
    # only allow the screen modes that the given machine supports
    if video_capabilities in ('pcjr', 'tandy'):
        # no EGA modes (though apparently there were Tandy machines with EGA cards too)
        unavailable_modes = [7, 8, 9]
        # 8-pixel characters, 16 colours in screen 0
        mode_data[0] = ( 8, 7, 32, 16, 80, 4, 4, 8 ) 
        # select pcjr cga palettes
        cga_palettes[:] = [cga_palette_0_pcjr, cga_palette_1_pcjr]       
        # TODO: determine the number of pages based on video memory size, not hard coded. 
    elif video_capabilities in ('cga', 'cga_old'):
        unavailable_modes = [3, 4, 5, 6, 7, 8, 9]
        # 8-pixel characters, 16 colours in screen 0
        mode_data[0] = ( 8, 7, 32, 16, 80, 4, 4, 8 ) 
    else:
        # EGA
        # no PCjr modes
        unavailable_modes = [3, 4, 5, 6]
    for mode in unavailable_modes:
        del mode_data[mode]
    if not backend.video.supports_graphics:    
        mode_data = { 0: ( 16,  7, 32, 64, 80, 4, 4, 8 ) }
    else:
        # load fonts
        heights_needed = reversed(sorted(set([mode_data[mode][0] for mode in mode_data])))
        for height in heights_needed:
            if height in fonts:
                # already force loaded
                continue
            # load a Unifont .hex font and take the codepage subset
            fonts[height] = typeface.load(font_families, height, unicodepage.cp_to_utf8)
            # fix missing code points font based on 16-line font
            if 16 in fonts:
                typeface.fixfont(height, fonts[height], unicodepage.cp_to_utf8, fonts[16])
        # remove modes for which we don't have fonts
        disabled_modes = []
        for i in mode_data:
            mode = mode_data[i]
            if mode[0] not in fonts or not fonts[mode[0]]:
                logging.warning("No font of height %d found. Screen mode %d not supported.", mode[0], i )
                disabled_modes.append(i)
        for mode in disabled_modes:
            del mode_data[mode]
    # text mode backends: delete all graphics modes    
    # reload the screen in resumed state
    if state.loaded:
        if state.console_state.screen_mode not in mode_data:
            logging.error("Resumed screen mode %d not supported by display backend.",  state.console_state.screen_mode)
            # fix the terminal
            backend.video.close()
            return False
        # set up the appropriate screen resolution
        backend.video.init_screen_mode()
        # load the screen contents from storage
        backend.video.load_state()
    else:        
        if 0 not in mode_data:
            logging.error("Text mode not supported by display backend.")
            # fix the terminal
            backend.video.close()
            return False        
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
    # video memory size check for SCREENs 5 and 6: (pcjr/tandy only; this is a bit of a hack as is) 
    # (32753 determined experimentally on DOSBox)
    if new_mode in (5, 6) and state.console_state.pcjr_video_mem_size < 32753:
        raise error.RunError(5)
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
                if new_width == 20:
                    new_width = 40
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
        if video_capabilities in ('pcjr', 'tandy'):
            if new_mode in (2,6):
                 state.console_state.pixel_aspect_ratio = fp.div(fp.Single.from_int(48), fp.Single.from_int(100))       
            elif new_mode in (1,4,5):
                 state.console_state.pixel_aspect_ratio = fp.div(fp.Single.from_int(96), fp.Single.from_int(100))       
            elif new_mode == 3:
                 state.console_state.pixel_aspect_ratio = fp.div(fp.Single.from_int(1968), fp.Single.from_int(1000))       
        else:    
            # pixels e.g. 80*8 x 25*14, screen ratio 4x3 makes for pixel width/height (4/3)*(25*14/8*80)
            # FIXME - hard coded 8-pixel width for graphics screens here.
            state.console_state.pixel_aspect_ratio = fp.div(
                fp.Single.from_int(state.console_state.height*state.console_state.font_height), 
                fp.Single.from_int(6*state.console_state.width)) 
        state.console_state.cursor_width = state.console_state.font_width        
        # set the palette (essential on first run, or not all globals are defined)
        set_palette()
        # signal the backend to change the screen resolution
        backend.video.init_screen_mode()
        # only redraw keys if screen has been cleared (any colours stay the same). state.console_state.screen_mode must be set for this
        if state.console_state.keys_visible:  
            show_keys()    
        set_default_cursor()
        set_pos(1, 1)
        update_cursor_visibility()
        # FIXME: are there different views for different pages?
        unset_view()
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if new_mode in (0, 1):
            set_colorburst(new_colorswitch)
        elif new_mode ==2:
            set_colorburst(False)    
    else:
        # set active page & visible page, counting from 0. 
        state.console_state.vpagenum, state.console_state.apagenum = new_vpagenum, new_apagenum
        state.console_state.vpage = state.console_state.pages[state.console_state.vpagenum]
        state.console_state.apage = state.console_state.pages[state.console_state.apagenum]
        backend.video.screen_changed = True
        # FIXME: keys visible?
    return True


# set the composite colorburst bit 
# on SCREEN 2 on composite monitor this enables artifacting
# on SCREEN 1 this switches between colour and greyscale (composite) or mode 4/5 palettes (RGB)
# on SCREEN 0 this switches between colour and greyscale (composite) or is ignored (RGB)
def set_colorburst(on=True):
    global cga_palettes
    old_colorburst = backend.video.colorburst
    backend.video.colorburst = ( on and video_capabilities in ('cga', 'cga_old', 'tandy', 'pcjr') )
    if state.console_state.screen_mode == 1:
        if backend.video.colorburst:
            cga_palettes = [cga_palette_0, cga_palette_1]
        else:
            cga_palettes = [cga_palette_5, cga_palette_5]
        set_palette()    
        backend.video.screen_changed = True
    elif backend.video.colorburst != old_colorburst:
        backend.video.update_palette()
        backend.video.screen_changed = True
        

def check_video_memory():
    if state.console_state.screen_mode in (5, 6) and state.console_state.pcjr_video_mem_size < 32753:
        screen (0, None, None, None)

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
            state.console_state.palette = cga_palettes[1]
        else:
            state.console_state.palette = [0, 15]
    backend.video.update_palette()

def show_cursor(do_show):
    ''' Force cursor to be visible/invisible. '''
    backend.video.update_cursor_visibility(do_show)

def update_cursor_visibility():
    ''' Set cursor visibility: visible if in interactive mode, unless forced visible in text mode. '''
    visible = (not state.basic_state.execute_mode)
    if state.console_state.screen_mode == 0:
        visible = visible or state.console_state.cursor
    backend.video.update_cursor_visibility(visible)

def set_cursor_shape(from_line, to_line):
    ''' Set the cursor shape as a block from from_line to to_line (in 8-line modes). Use compatibility algo in higher resolutions. '''
    if video_capabilities == 'ega':
        # odd treatment of cursors on EGA machines, presumably for backward compatibility
        # the following algorithm is based on DOSBox source int10_char.cpp INT10_SetCursorShape(Bit8u first,Bit8u last)    
        max_line = state.console_state.font_height-1
        if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
            if (to_line < from_line):
                # invisible only if to_line is zero and to_line < from_line           
                if to_line != 0: 
                    # block shape from *to_line* to end
                    from_line = to_line
                    to_line = max_line
            elif (from_line | to_line) >= max_line or to_line != max_line-1 or from_line != max_line:
                if to_line > 3:
                    if from_line+2 < to_line:
                        if from_line > 2:
                            from_line = (max_line+1) // 2
                        to_line = max_line
                    else:
                        from_line = from_line - to_line + max_line                        
                        to_line = max_line
                        if max_line > 0xc:
                            from_line -= 1
                            to_line -= 1
    state.console_state.cursor_from = max(0, min(from_line, state.console_state.font_height-1))
    state.console_state.cursor_to = max(0, min(to_line, state.console_state.font_height-1))
    backend.video.build_cursor(state.console_state.cursor_width, state.console_state.font_height, 
                state.console_state.cursor_from, state.console_state.cursor_to)
    
############################### 
# interactive mode         

def wait_screenline(write_endl=True, from_start=False, alt_replace=False):
    prompt_row = state.console_state.row
    # force cursor visibility in all cases
    show_cursor(True) 
    try:
        furthest_left, furthest_right = wait_interactive(from_start, alt_replace)
    except error.Break:
        for echo in state.console_state.input_echos:  
            echo ('\x0e')
        write_line()    
        raise        
    update_cursor_visibility()
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
        elif d in ('\x00\x48', '\x1E'):                                             # <UP> <CTRL+6>
            set_pos(state.console_state.row - 1, state.console_state.col, scroll_ok=False)    
        elif d in ('\x00\x50', '\x1F'):                                             # <DOWN> <CTRL+->
            set_pos(state.console_state.row + 1, state.console_state.col, scroll_ok=False)    
        elif d in ('\x00\x4D', '\x1C'):                                             # <RIGHT> <CTRL+\>
            # skip dbcs trail byte
            skip = 2 if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 1 else 1   
            set_pos(state.console_state.row, state.console_state.col + skip, scroll_ok=False)
        elif d in ('\x00\x4B', '\x1D'):                                             # <LEFT> <CTRL+]>
            set_pos(state.console_state.row, state.console_state.col - 1, scroll_ok=False)                
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
        # move left if we end up on dbcs trail byte
        if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 2:
            set_pos(state.console_state.row, state.console_state.col-1, scroll_ok=False) 
        # adjust cursor width
        if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 1:
            cursor_width = 2*state.console_state.font_width
        else:
            cursor_width = state.console_state.font_width
        if cursor_width != state.console_state.cursor_width:
            state.console_state.cursor_width = cursor_width
            backend.video.build_cursor(state.console_state.cursor_width, state.console_state.font_height, 
                    state.console_state.cursor_from, state.console_state.cursor_to)
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
    double = state.console_state.apage.row[crow-1].double[ccol-1]
    if double == 0:
        delete_sbcs_char(crow, ccol)
    elif double == 1:    
        delete_sbcs_char(crow, ccol)
        delete_sbcs_char(crow, ccol)
    elif double == 2:    
        delete_sbcs_char(crow, ccol-1)
        delete_sbcs_char(crow, ccol-1)
        
def delete_sbcs_char(crow, ccol):
    save_col = ccol
    therow = state.console_state.apage.row[crow-1]
    if crow > 1 and ccol >= therow.end and therow.wrap:
        nextrow = state.console_state.apage.row[crow]
        # row was a LF-ending row
        therow.buf[ccol-1:] = nextrow.buf[:state.console_state.width-ccol+1] 
        therow.end = min(max(therow.end, ccol) + nextrow.end, state.console_state.width)
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
            # don't update all dbcs chars behind at each put
            put_screen_char_attr(state.console_state.apage, crow, i+1, therow.buf[i][0], state.console_state.attr, one_only=True)
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
            ccol = state.console_state.width 
            crow -= 1
    elif ccol != start_col or state.console_state.row != start_row: 
        ccol -= 1
    set_pos(crow, max(1, ccol))
    if state.console_state.apage.row[state.console_state.row-1].double[state.console_state.col-1] == 2:
        # we're on a trail byte, move to the lead
        set_pos(state.console_state.row, state.console_state.col-1)
    delete_char(crow, ccol)
    
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
    if state.console_state.apage.row[crow-1].end == state.console_state.width:
        set_pos(crow, state.console_state.apage.row[crow-1].end)
        state.console_state.overflow = True
    else:        
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
    check_pos(scroll_ok=True)
    state.console_state.apage.row[state.console_state.row-1].wrap = False
    set_pos(state.console_state.row + 1, 1)

# print a line from a program listing - no wrap if 80-column line, clear row before printing.
def list_line(line):
    # flow of listing is visible on screen
    backend.check_events()
    for i in range( 1 + (len(line)-1)// 80):
        # does not take into account LFs
        if state.console_state.row+i <= state.console_state.scroll_height:
            clear_line(state.console_state.row+i)
    # clear_line moves the position, undo        
    set_pos(state.console_state.row - (len(line)-1)// 80, 1)
    write_line(str(line))
    # remove empty line after 80-column program line
    if len(line) == state.console_state.width and state.console_state.row > 2:
        state.console_state.apage.row[state.console_state.row-3].wrap = False
        set_pos(state.console_state.row-1, 1)

def set_width(to_width):
    # raise an error if the width value doesn't make sense
    if to_width not in (20, 40, 80):
        return False
    if to_width == state.console_state.width:
        return True
    if to_width == 20:
        return screen(3, None, None, None)
    elif state.console_state.screen_mode == 0:
        return screen(0, None, None, None, new_width=to_width) 
    elif state.console_state.screen_mode == 1 and to_width == 80:
        return screen(2, None, None, None)
    elif state.console_state.screen_mode == 2 and to_width == 40:
        return screen(1, None, None, None)
    elif state.console_state.screen_mode == 3 and to_width == 40:
        return screen(1, None, None, None)
    elif state.console_state.screen_mode == 3 and to_width == 80:
        return screen(2, None, None, None)
    elif state.console_state.screen_mode == 4 and to_width == 80:
        return screen(2, None, None, None)
    elif state.console_state.screen_mode == 5 and to_width == 80:
        return screen(6, None, None, None)
    elif state.console_state.screen_mode == 6 and to_width == 40:
        return screen(5, None, None, None)
    elif state.console_state.screen_mode == 7 and to_width == 80:
        return screen(8, None, None, None)
    elif state.console_state.screen_mode == 8 and to_width == 40:
        return screen(7, None, None, None)
    elif state.console_state.screen_mode == 9 and to_width == 40:
        return screen(7, None, None, None)

#####################
# key replacement

def list_keys():
    for i in range(on_event.num_fn_keys):
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
            put_screen_char_attr(state.console_state.apage, 25, col, c, cattr)    
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
            if state.basic_state.run_mode and state.basic_state.key_handlers[keynum].enabled or keynum > 9:
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

def put_screen_char_attr(cpage, crow, ccol, c, cattr, one_only=False):
    cattr = cattr & 0xf if state.console_state.screen_mode else cattr
    # update the screen buffer
    cpage.row[crow-1].buf[ccol-1] = (c, cattr)
    backend.video.set_attr(cattr) 
    if not unicodepage.dbcs:
        backend.video.putc_at(crow, ccol, c)    
    else:
        # replace chars from here until necessary to update double-width chars
        therow = cpage.row[crow-1]    
        # replacing a trail byte? take one step back
        # previous char could be a lead byte? take a step back
        orig_col = ccol
        if (ccol > 1 and therow.double[ccol-2] != 2 and 
                (therow.buf[ccol-1] in unicodepage.trail or therow.buf[ccol-2][0] in unicodepage.lead)):
            ccol -= 1
        # check all dbcs characters between here until it doesn't matter anymore    
        while ccol < state.console_state.width:
            c = therow.buf[ccol-1][0]
            d = therow.buf[ccol][0]  
            if c in unicodepage.lead and d in unicodepage.trail:
                therow.double[ccol-1:ccol] = [1, 2]
                backend.video.putwc_at(crow, ccol, c, d)
                ccol += 2
            else:    
                therow.double[ccol-1] = 0
                backend.video.putc_at(crow, ccol, c)    
                if therow.double[ccol] == 0:
                    break
                ccol += 1
            if one_only and ccol > orig_col:
                break  
        if ccol == state.console_state.width and therow.double[state.console_state.width-1] == 0:
            backend.video.set_attr(therow.buf[state.console_state.width-1][1]) 
            backend.video.putc_at(crow, state.console_state.width, therow.buf[state.console_state.width-1][0])    
        
def put_char(c, do_scroll_down=False):
    # check if scroll& repositioning needed
    if state.console_state.overflow:
        state.console_state.col += 1
        state.console_state.overflow = False
    # see if we need to wrap and scroll down
    check_wrap(do_scroll_down)
    # move cursor and see if we need to scroll up
    check_pos(scroll_ok=True) 
    # put the character
    put_screen_char_attr(state.console_state.apage, state.console_state.row, state.console_state.col, c, state.console_state.attr)
    # adjust end of line marker
    if state.console_state.col > state.console_state.apage.row[state.console_state.row-1].end:
         state.console_state.apage.row[state.console_state.row-1].end = state.console_state.col
    # move cursor. if on col 80, only move cursor to the next row when the char is printed
    if state.console_state.col < state.console_state.width:
        state.console_state.col += 1
    else:
        state.console_state.overflow = True
    # move cursor and see if we need to scroll up
    check_pos(scroll_ok=True)
    
def check_wrap(do_scroll_down):    
    if state.console_state.col > state.console_state.width:
        # wrap line
        state.console_state.apage.row[state.console_state.row-1].wrap = True
        if do_scroll_down:
            # scroll down (make space by shifting the next rows down)
            if state.console_state.row < state.console_state.scroll_height:
                scroll_down(state.console_state.row+1)
        state.console_state.row += 1
        state.console_state.col = 1
            
def set_pos(to_row, to_col, scroll_ok=True):
    state.console_state.overflow = False
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
            # if row > height, we also end up here (eg if we do INPUT on the bottom row)
            # adjust viewport if necessary
            state.console_state.bottom_row_allowed = False
    # see if we need to move to the next row        
    if state.console_state.col > state.console_state.width:
        if state.console_state.row < state.console_state.scroll_height or scroll_ok:
            # either we don't nee to scroll, or we're allowed to
            state.console_state.col -= state.console_state.width
            state.console_state.row += 1
        else:
            # we can't scroll, so we just stop at the right border 
            state.console_state.col = state.console_state.width        
    # see if we eed to move a row up
    elif state.console_state.col < 1:
        if state.console_state.row > state.console_state.view_start:
            state.console_state.col += state.console_state.width
            state.console_state.row -= 1
        else:
            state.console_state.col = 1   
    # see if we need to scroll 
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
        check_pos(scroll_ok=True)
        set_pos(state.console_state.row + 1, 1)
    # ensure line above doesn't wrap    
    state.console_state.apage.row[state.console_state.row-2].wrap = False    


#####################
# viewport / scroll area

def set_view(start=1, stop=24):
    state.console_state.view_set, state.console_state.view_start, state.console_state.scroll_height = True, start, stop
    set_pos(start, 1)
 
def unset_view():
    set_view()
    state.console_state.view_set = False

def clear_view():
    if video_capabilities in ('ega', 'cga', 'cga_old'):
        # keep background, set foreground to 7
        attr_save, state.console_state.attr = state.console_state.attr, state.console_state.attr & 0x70 | 0x7
    for r in range(state.console_state.view_start, state.console_state.scroll_height+1):
        state.console_state.apage.row[r-1].clear()
        state.console_state.apage.row[r-1].wrap = False
    state.console_state.row, state.console_state.col = state.console_state.view_start, 1
    backend.video.clear_rows(state.console_state.attr, state.console_state.view_start, state.console_state.height if state.console_state.bottom_row_allowed else state.console_state.scroll_height)
    if video_capabilities in ('ega', 'cga', 'cga_old'):
        # restore attr
        state.console_state.attr = attr_save
            
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
    # force cursor invisible during redraw
    show_cursor(False)
    # this makes it feel faster
    backend.video.clear_rows(state.console_state.attr, 1, 25)
    # redraw every character
    for crow in range(state.console_state.height):
        therow = state.console_state.apage.row[crow]  
        for i in range(state.console_state.width): 
            put_screen_char_attr(state.console_state.apage, crow+1, i+1, therow.buf[i][0], therow.buf[i][1])
    update_cursor_visibility()

################################################
        
def write_error_message(msg, linenum):
    start_line()
    write(msg) 
    if linenum != None and linenum > -1 and linenum < 65535:
        write(' in %i' % linenum)
    write_line(' ')                  

