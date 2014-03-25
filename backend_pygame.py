#
# PC-BASIC 3.23 - backend_pygame.py
#
# Graphical console backend based on PyGame
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
# Acknowledgements:
# Kosta Kostis/FreeDOS project for .CPI font files

import pygame

import error
import cpi_font
import unicodepage 
import console
import events
import deviceio
import graphics
# for fast get & put only
import var
# for debug_print only
import sys


# CGA palette choices
colours16 = [
 (0x00,0x00,0x00),(0x00,0x00,0xaa),(0x00,0xaa,0x00),(0x00,0xaa,0xaa),
 (0xaa,0x00,0x00),(0xaa,0x00,0xaa),(0xaa,0x55,0x00),(0xaa,0xaa,0xaa), 
 (0x55,0x55,0x55),(0x55,0x55,0xff),(0x55,0xff,0x55),(0x55,0xff,0xff),
 (0xff,0x55,0x55),(0xff,0x55,0xff),(0xff,0xff,0x55),(0xff,0xff,0xff)
] 

# EGA palette choices
colours64= [
 (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
 (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0xaa,0x00), (0xaa,0xaa,0xaa), 
 
 (0x00,0x00,0x55), (0x00,0x00,0xff), (0x00,0xaa,0x55), (0x00,0xaa,0xff),
 (0xaa,0x00,0xff), (0xaa,0x00,0xff), (0xaa,0xaa,0x55), (0xaa,0xaa,0xff),
 
 (0x00,0x55,0x00), (0x00,0x55,0xaa), (0x00,0xff,0x00), (0x00,0xff,0xaa),
 (0xaa,0x55,0x00), (0xaa,0x55,0xaa), (0xaa,0xff,0x00), (0xaa,0xff,0xaa),
  
 (0x00,0x55,0x55), (0x00,0x55,0xff), (0x00,0xff,0x55), (0x00,0xff,0xff),
 (0xaa,0x55,0x55), (0xaa,0x55,0xff), (0xaa,0xff,0x55), (0xaa,0xff,0xff),
  
  
 (0x55,0x00,0x00), (0x55,0x00,0xaa), (0x55,0xaa,0x00), (0x55,0xaa,0xaa),
 (0xff,0x00,0x00), (0xff,0x00,0xaa), (0xff,0xaa,0x00), (0xff,0xaa,0xaa),
 
 (0x55,0x00,0x55), (0x55,0x00,0xff), (0x55,0xaa,0x55), (0x55,0xaa,0xff),
 (0xff,0x00,0x55), (0xff,0x00,0xff), (0xff,0xaa,0x55), (0xff,0xaa,0xff),
 
 (0x55,0x55,0x00), (0x55,0x55,0xaa), (0x55,0xff,0x00), (0x55,0xff,0xaa),
 (0xff,0x55,0x00), (0xff,0x55,0xaa), (0xff,0xff,0x00), (0xff,0xff,0xaa),
 
 (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
 (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff)
]

# cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
# cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
#
gamecolours16 = [ pygame.Color(*rgb) for rgb in colours16 ]
gamecolours64 = [ pygame.Color(*rgb) for rgb in colours64 ]

# for use with get_at
workaround_palette= [ (0,0,0),(0,0,1),(0,0,2),(0,0,3),(0,0,4),(0,0,5),(0,0,6),(0,0,7),(0,0,8),(0,0,9),(0,0,10),(0,0,11),(0,0,12),(0,0,13),(0,0,14),(0,0,15) ]

# standard palettes
palette64=[0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]

# screen width and height in pixels
size = (0,0)

# letter shapes
glyphs = []
fonts = None
font = None
font_height = 16
# cursor shape
cursor_from = 0
cursor_to = 0    
cursor0 = None
# screen & updating 
screen = None
screen_changed = True
cycle = 0
blink_state = 0
last_cycle = 0
cycle_time = 120 #120
blink_cycles = 5
# current cursor location
last_row = 1
last_col = 1    
cursor_visible = True
under_cursor = None
under_top_left = None

# available joy sticks
joysticks = []    

# store for fast get & put arrays
get_put_store = {}

keycode_to_scancode = {
    pygame.K_UP:    '\x00\x48',
    pygame.K_DOWN:  '\x00\x50',
    pygame.K_RIGHT: '\x00\x4D',
    pygame.K_LEFT:  '\x00\x4B',
    pygame.K_INSERT:'\x00\x52',
    pygame.K_DELETE:'\x00\x53',
    pygame.K_HOME:  '\x00\x47',
    pygame.K_END:   '\x00\x4F',
    pygame.K_PAGEUP:'\x00\x49',
    pygame.K_PAGEDOWN:'\x00\x51',
    pygame.K_F1:    '\x00\x3B',
    pygame.K_F2:    '\x00\x3C',
    pygame.K_F3:    '\x00\x3D',
    pygame.K_F4:    '\x00\x3E',
    pygame.K_F5:    '\x00\x3F',
    pygame.K_F6:    '\x00\x40',
    pygame.K_F7:    '\x00\x41',
    pygame.K_F8:    '\x00\x42',
    pygame.K_F9:    '\x00\x43',
    pygame.K_F10:   '\x00\x44',
    pygame.K_PRINT: '\x00\x37',
}
#K_SYSREQ              sysrq

ctrl_keycode_to_scancode = {
    pygame.K_RIGHT:     '\x00\x74',
    pygame.K_LEFT:      '\x00\x73',
    pygame.K_HOME:      '\x00\x77',
    pygame.K_END:       '\x00\x75',
    pygame.K_PAGEUP:    '\x00\x84',
    pygame.K_PAGEDOWN:  '\x00\x76',
    pygame.K_BACKSPACE: '\x7F',
    pygame.K_RETURN:    '\x0A',
    pygame.K_TAB:       '',
    pygame.K_1:         '',
    pygame.K_2:         '\x00\x03',
    pygame.K_3:         '',
    pygame.K_4:         '',
    pygame.K_5:         '',
    # <CTRL+6> is passed normally
    pygame.K_7:         '',
    pygame.K_8:         '',
    pygame.K_9:         '\x00\x84',
    pygame.K_0:         '',
    pygame.K_F2:        '\x00\x5F',
    pygame.K_F3:        '\x00\x60',
    pygame.K_MINUS:     '\x1F',
}
   
keycode_to_inpcode = {
    # top row
    pygame.K_ESCAPE:    '\x01',
    pygame.K_1:         '\x02',
    pygame.K_2:         '\x03',
    pygame.K_3:         '\x04',
    pygame.K_4:         '\x05',
    pygame.K_5:         '\x06',
    pygame.K_6:         '\x07',
    pygame.K_7:         '\x08',
    pygame.K_8:         '\x09',
    pygame.K_9:         '\x0A',
    pygame.K_0:         '\x0B',
    pygame.K_MINUS:     '\x0C',
    pygame.K_EQUALS:    '\x0D',
    pygame.K_BACKSPACE: '\x0E',
    # row 1
    pygame.K_TAB:       '\x0F',
    pygame.K_q:         '\x10',
    pygame.K_w:         '\x11',
    pygame.K_e:         '\x12',
    pygame.K_r:         '\x13',
    pygame.K_t:         '\x14',
    pygame.K_y:         '\x15',
    pygame.K_u:         '\x16',
    pygame.K_i:         '\x17',
    pygame.K_o:         '\x18',
    pygame.K_p:         '\x19',
    pygame.K_LEFTBRACKET:'\x1A',
    pygame.K_RIGHTBRACKET:'\x1B',
    pygame.K_RETURN:    '\x1C',
    # row 2
    pygame.K_RCTRL:     '\x1D',
    pygame.K_LCTRL:     '\x1D',
    pygame.K_a:         '\x1E',
    pygame.K_s:         '\x1F',
    pygame.K_d:         '\x20',
    pygame.K_f:         '\x21',
    pygame.K_g:         '\x22',
    pygame.K_h:         '\x23',
    pygame.K_j:         '\x24',
    pygame.K_k:         '\x25',
    pygame.K_l:         '\x26',
    pygame.K_SEMICOLON: '\x27',
    pygame.K_QUOTE:     '\x28',
    pygame.K_BACKQUOTE :     '\x29',
    # row 3        
    pygame.K_LSHIFT:    '\x2A',
    pygame.K_HASH:      '\x2B',     # assumes UK keyboard?
    pygame.K_z:         '\x2C',
    pygame.K_x:         '\x2D',
    pygame.K_c:         '\x2E',
    pygame.K_v:         '\x2F',
    pygame.K_b:         '\x30',
    pygame.K_n:         '\x31',
    pygame.K_m:         '\x32',
    pygame.K_COMMA:     '\x33',
    pygame.K_PERIOD:    '\x34',
    pygame.K_SLASH:     '\x35',
    pygame.K_RSHIFT:    '\x36',
    pygame.K_PRINT:     '\x37',
    pygame.K_SYSREQ:    '\x37',
    pygame.K_RALT:      '\x38',
    pygame.K_LALT:      '\x38',
    pygame.K_SPACE:     '\x39',
    pygame.K_CAPSLOCK:  '\x3A',
    # others    
    pygame.K_F1:        '\x3B',
    pygame.K_F2:        '\x3C',
    pygame.K_F3:        '\x3D',
    pygame.K_F4:        '\x3E',
    pygame.K_F5:        '\x3F',
    pygame.K_F6:        '\x40',
    pygame.K_F7:        '\x41',
    pygame.K_F8:        '\x42',
    pygame.K_F9:        '\x43',
    pygame.K_F10:       '\x44',
    pygame.K_NUMLOCK:   '\x45',
    pygame.K_SCROLLOCK: '\x46',
    pygame.K_HOME:      '\x47',
    pygame.K_UP:        '\x48',
    pygame.K_PAGEUP:    '\x49',
    pygame.K_KP_MINUS:  '\x4A',
    pygame.K_LEFT:      '\x4B',
    pygame.K_KP5:       '\x4C',
    pygame.K_RIGHT:     '\x4D',
    pygame.K_KP_PLUS:   '\x4E',
    pygame.K_END:       '\x4F',
    pygame.K_DOWN:      '\x50',
    pygame.K_PAGEDOWN:  '\x51',
    pygame.K_INSERT:    '\x52',
    pygame.K_DELETE:    '\x53',
    pygame.K_BACKSLASH: '\x56',
}

def init():
    global fonts, num_sticks, joysticks
    pre_init_mixer()    
    pygame.init()
    pygame.display.set_caption('PC-BASIC 3.23')
    pygame.key.set_repeat(500, 24)
    fonts = cpi_font.load_codepage()
    init_mixer()
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
    for j in joysticks:
        j.init()
    return True
        
def close():
    pygame.joystick.quit()
    pygame.display.quit()    

def debug_print(s):
    sys.stderr.write(s)    

def get_palette_entry(index):
    return palette64[index]

def set_palette(new_palette=None):
    global palette64 
    if console.num_palette==64:
        if new_palette==None:
            new_palette=[0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]
        palette64 = new_palette
        gamepalette = [ gamecolours64[i] for i in new_palette ]
    elif console.num_colours>=16:
        if new_palette==None:
            new_palette=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
        palette64 = new_palette
        gamepalette = [ gamecolours16[i] for i in new_palette ]
    elif console.num_colours==4:
        if new_palette==None:
            new_palette=[0,11,13,15]
        palette64 = new_palette
        gamepalette = [ gamecolours16[i] for i in new_palette ]
    else:
        if new_palette==None:
            new_palette=[0,15]
        palette64 = new_palette
        gamepalette = [ gamecolours16[i] for i in new_palette ]
    screen.set_palette(gamepalette)
    under_cursor.set_palette(gamepalette) 

def set_palette_entry(index, colour):
    global palette64 
    palette64[index] = colour
    if console.num_palette==64:
        gamecolor = gamecolours64[colour]
    else:
        gamecolor = gamecolours16[colour]
    screen.set_palette_at(index,gamecolor)
    under_cursor.set_palette_at(index,gamecolor)
    
def clear_rows(bg, start, stop):
    global screen_changed
    scroll_area = pygame.Rect(0, (start-1)*font_height, size[0], (stop-start+1)*font_height) 
    console.apage.surface0.fill(bg, scroll_area)
    console.apage.surface1.fill(bg, scroll_area)
    screen_changed = True
    
# not in interface
def set_font(new_font_height):
    global fonts, font, font_height, under_cursor
    font_height = new_font_height
    if font_height==16:
        font=fonts[0]
    elif font_height==14:
        font=fonts[1]
    elif font_height==8:
        font=fonts[2]
    else:
        font=None
    under_cursor = pygame.Surface((8,font_height),depth=8)    

def init_screen_mode(mode, new_font_height):
    global glyphs, cursor0
    set_font(new_font_height)    
    glyphs = [ build_glyph(c, font, font_height) for c in range(256) ]
    # set standard cursor
    cursor0 = pygame.Surface((8, font_height), depth=8)
    build_default_cursor(mode, True)
    
def setup_screen(to_height, to_width):
    global screen, size 
    global screen_changed
    size = to_width*8, to_height*font_height
    screen = pygame.display.set_mode(size, 0,8)
    # whole screen (blink on & off)
    for i in range(console.num_pages):
        console.pages[i].surface0 = pygame.Surface(size, depth=8)
        console.pages[i].surface1 = pygame.Surface(size, depth=8)
        console.pages[i].surface0.set_palette(workaround_palette)
        console.pages[i].surface1.set_palette(workaround_palette)
    set_palette()
    screen_changed = True

def copy_page(src,dst):
    global screen_changed
    console.pages[dst].surface0.blit(console.pages[src].surface0, (0,0))
    console.pages[dst].surface1.blit(console.pages[src].surface1, (0,0))
    screen_changed = True
    
def show_cursor(do_show, prev):
    global screen_changed
    if do_show != prev:
        screen_changed = True

def set_cursor_colour(color):
    cursor0.set_palette_at(254, screen.get_palette_at(color))

def build_default_cursor(mode, overwrite):
    global cursor_from, cursor_to, screen_changed
    if overwrite and not mode:
        cursor_from, cursor_to = font_height-2, font_height-2
    elif overwrite and mode:
        cursor_from, cursor_to = 0, font_height-1
    else:
        cursor_from, cursor_to = font_height/2, font_height-1
    build_cursor()
    screen_changed = True

def build_shape_cursor(from_line, to_line):
    global cursor_from, cursor_to, screen_changed
    if not console.screen_mode:
        cursor_from = max(0, min(from_line, font_height-1))
        cursor_to = max(0, min(to_line, font_height-1))
        build_cursor()
        screen_changed = True

def scroll(from_line):
    global screen_changed
    temp_scroll_area = pygame.Rect(0,(from_line-1)*font_height,console.width*8, (console.scroll_height-from_line+1)*font_height)
    # scroll
    console.apage.surface0.set_clip(temp_scroll_area)
    console.apage.surface1.set_clip(temp_scroll_area)
    console.apage.surface0.scroll(0, -font_height)
    console.apage.surface1.scroll(0, -font_height)
    # empty new line
    blank = pygame.Surface( (console.width*8, font_height) , depth=8)
    bg = (console.attr>>4) & 0x7
    blank.set_palette(workaround_palette)
    blank.fill(bg)
    console.apage.surface0.blit(blank, (0, (console.scroll_height-1)*font_height))
    console.apage.surface1.blit(blank, (0, (console.scroll_height-1)*font_height))
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    screen_changed = True
   
def scroll_down(from_line):
    global screen_changed
    temp_scroll_area = pygame.Rect(0,(from_line-1)*font_height, console.width*8, (console.scroll_height-from_line+1)*font_height)
    console.apage.surface0.set_clip(temp_scroll_area)
    console.apage.surface1.set_clip(temp_scroll_area)
    console.apage.surface0.scroll(0, font_height)
    console.apage.surface1.scroll(0, font_height)
    # empty new line
    blank = pygame.Surface( (console.width*8, font_height), depth=8 )
    bg = (console.attr>>4) & 0x7
    blank.set_palette(workaround_palette)
    blank.fill(bg)
    console.apage.surface0.blit(blank, (0, (from_line-1)*font_height))
    console.apage.surface1.blit(blank, (0, (from_line-1)*font_height))
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    screen_changed = True

last_attr = None

def set_attr(cattr):
    global last_attr
    if cattr == last_attr:
        return    
    color = (0, 0, cattr & 0xf)
    bg = (0, 0, (cattr>>4) & 0x7)    
    for glyph in glyphs:
        glyph.set_palette_at(255, bg)
        glyph.set_palette_at(254, color)
    last_attr = cattr
        
def putc_at(row, col, c):
    global screen_changed
    glyph = glyphs[ord(c)]
    blank = glyphs[32] # using SPACE for blank 
    top_left = ((col-1)*8, (row-1)*font_height)
    if not console.screen_mode:
        console.apage.surface1.blit(glyph, top_left )
    if last_attr>>7: #blink:
        console.apage.surface0.blit(blank, top_left )
    else:
        console.apage.surface0.blit(glyph, top_left )
    screen_changed = True

def build_glyph(c, font_face, glyph_height):
    color = 254 
    bg = 255 
    glyph = pygame.Surface((8, glyph_height), depth=8)
    glyph.fill(bg)
    face = font_face[c]
    for yy in range(glyph_height):
        c = ord(face[yy])
        for xx in range(8):
            pos = (xx, yy)
            bit = (c >> (7-xx)) & 1
            if bit == 1:
                glyph.set_at(pos, color)
    return glyph            
    
def build_cursor():
    color, bg = 254, 255
    cursor0.set_colorkey(bg)
    cursor0.fill(bg)
    for yy in range(font_height):
        for xx in range(8):
            if yy < cursor_from or yy > cursor_to:
                pass
            else:
                cursor0.set_at((xx, yy), color)

def refresh_screen():
    save_palette = screen.get_palette()
    if console.screen_mode or blink_state == 0:
        console.vpage.surface0.set_palette(save_palette)
        screen.blit(console.vpage.surface0, (0, 0))
        console.vpage.surface0.set_palette(workaround_palette)
    elif blink_state == 1: 
        console.vpage.surface1.set_palette(save_palette)
        screen.blit(console.vpage.surface1, (0, 0))
        console.vpage.surface1.set_palette(workaround_palette)
            
def remove_cursor():
    if not console.cursor or console.vpage != console.apage:
        return
    if under_top_left != None:
        screen.blit(under_cursor, under_top_left)

def refresh_cursor():
    global last_row, last_col, under_top_left
    if not console.cursor or console.vpage != console.apage:
        return
    # copy screen under cursor
    under_top_left = ( (console.col-1)*8, (console.row-1)*font_height)
    under_char_area = pygame.Rect((console.col-1)*8, (console.row-1)*font_height, console.col*8, console.row*font_height)
    under_cursor.blit(screen, (0,0), area=under_char_area)
    if not console.screen_mode:
        # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
        if (cycle/blink_cycles==1 or cycle/blink_cycles==3): 
            screen.blit(cursor0, ( (console.col-1)*8, (console.row-1)*font_height) )
    else:
        index = console.attr & 0xf
        # reference the destination area
        dest_array = pygame.surfarray.pixels2d(screen.subsurface(pygame.Rect(
                            (console.col-1)*8, (console.row-1)*font_height + cursor_from, 8, cursor_to - cursor_from + 1))) 
        dest_array ^= index       
    last_row = console.row
    last_col = console.col
        
def pause_key():
    # pause key press waits for any key down. continues to process screen events (blink) but not user events.
    while not check_events(pause=True):
        # continue playing background music
        console.sound.check_sound()
        idle()
        
def idle():
    pygame.time.wait(cycle_time/blink_cycles)  

def check_events(pause=False):
    # check and handle pygame events    
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if not pause:
                handle_key(event)
            else:
                return True    
        if event.type == pygame.KEYUP:
            if not pause:
                handle_key_up(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            handle_mouse(event)
        elif event.type == pygame.JOYBUTTONDOWN:
            handle_stick(event)    
    check_screen()
    return False
    
def check_screen():
    global cycle, last_cycle
    global screen_changed
    global blink_state
    if not console.screen_mode:
        if cycle == 0:
            blink_state = 0
            screen_changed = True
        elif cycle == blink_cycles*2: 
            blink_state = 1
            screen_changed = True
    tock = pygame.time.get_ticks() 
    if (tock - last_cycle) >= (cycle_time/blink_cycles):
        last_cycle = tock
        cycle += 1
        if cycle == blink_cycles*4: 
            cycle = 0
        cursor_changed = ( (not console.screen_mode and cycle%blink_cycles == 0) 
                           or (console.row != last_row) or (console.col != last_col) )
        if screen_changed:
            refresh_screen()
            refresh_cursor()
            pygame.display.flip()             
        elif cursor_changed and console.cursor:
            remove_cursor()
            refresh_cursor()
            pygame.display.flip()             
        screen_changed = False

def handle_key(e):
    c = ''
    mods = pygame.key.get_mods() 
    if e.key in (pygame.K_PAUSE, pygame.K_BREAK):
        if mods & pygame.KMOD_CTRL:
            # ctrl-break
            raise error.Break()
        else:
            # pause until keypress
            pause_key()    
    elif e.key == pygame.K_NUMLOCK and mods & pygame.KMOD_CTRL:
        pause_key()    
    elif e.key == pygame.K_SCROLLOCK and mods & pygame.KMOD_CTRL:
        # ctrl+SCROLLLOCK breaks too
        raise error.Break()
    elif e.key == pygame.K_CAPSLOCK:
        # let CAPS LOCK be handled by the window manager
        pass
    elif e.key == pygame.K_PRINT:
        # these can't be caught by INKEY$ etc:
        if mods & pygame.KMOD_CTRL:
            console.toggle_echo_lpt1()
        elif mods & pygame.KMOD_SHIFT:
            console.print_screen()
    elif e.key == pygame.K_TAB and mods & pygame.KMOD_SHIFT:
        # shift+tab -> \x00\x0F (scancode for TAB) but TAB -> \x09
        c = '\x00\x0F'
    else:
        try:
            c = ctrl_keycode_to_scancode[e.key] if (mods & pygame.KMOD_CTRL) else keycode_to_scancode[e.key]
        except KeyError:
            c = unicodepage.from_unicode(e.unicode)
    console.insert_key(c) 
    # current key pressed; modifiers ignored 
    try:
        console.inp_key = ord(keycode_to_inpcode[e.key])
    except KeyError:
        pass    
                    
def handle_key_up(e):
    # last key released gets remembered
    try:
        console.inp_key = 0x80 + ord(keycode_to_inpcode[e.key])
    except KeyError:
        pass    
           
def handle_mouse(e):
    if e.button == 1: # LEFT BUTTON
        console.penstick.trigger_pen(e.pos)
                
def handle_stick(e):
    if e.joy < 2 and e.button < 2:
        console.penstick.trigger_stick(e.joy, e.button)
            
##############################################
# penstick interface
# light pen (emulated by mouse) & joystick

# should be True on mouse click events
pen_down = 0
pen_down_pos = (0,0)

stick_fired = [[False, False], [False, False]]

def trigger_pen(pos):
    global pen_down, pen_down_pos
    events.pen_triggered = True
    pen_down = -1 # TRUE
    pen_down_pos = pos
                
def trigger_stick(joy, button):
    stick_fired[joy][button] = True
    events.strig_handlers[joy*2 + button] = True

def get_pen(fn):
    global pen_down
    if fn == 0:
        pen_down_old, pen_down = pen_down, 0
        return pen_down_old
    elif fn == 1:
        return min(size[0]-1, max(0, pen_down_pos[0]))
    elif fn == 2:
        return min(size[1]-1, max(0, pen_down_pos[1]))  
    elif fn == 3:
        return -pygame.mouse.get_pressed()[0]
    elif fn == 4:
        return min(size[0]-1, max(0, pygame.mouse.get_pos()[0]))
    elif fn == 5:
        return min(size[1]-1, max(0, pygame.mouse.get_pos()[1]))
    elif fn == 6:
        return min(console.width, max(1, 1+pen_down_pos[0]//8))
    elif fn == 7:
        return min(console.height, max(1, 1+pen_down_pos[1]//font_height)) 
    elif fn == 8:
        return min(console.width, max(1, 1+pygame.mouse.get_pos()[0]//8))
    elif fn == 9:
        return min(console.height, max(1, 1+pygame.mouse.get_pos()[1]//font_height))     

def get_stick(fn):
    stick_num, axis = fn//2, fn%2
    if len(joysticks) < stick_num + 1:
        return 128
    else:
        return int(joysticks[stick_num].get_axis(axis)*127)+128

def get_strig(fn):       
    joy, trig = fn//4, (fn//2)%2
    if joy >= len(joysticks) or trig >= joysticks[joy].get_numbuttons():
        return False
    if fn%2 == 0:
        # has been trig
        stick_was_trig = stick_fired[joy][trig]
        stick_fired[joy][trig] = False
        return stick_was_trig
    else:
        # trig
        return joysticks[joy].get_button(trig)
      
###############################################
# graphics backend interface
# low-level methods (pygame implementation)

graph_view = None


def put_pixel(x,y, index):
    global screen_changed
    console.apage.surface0.set_at((x,y), index)
    # empty the console buffer of affected characters
    cx, cy = min(console.width-1, max(0, x//8)), min(console.height-1, max(0, y//font_height)) 
    console.apage.row[cy].buf[cx] = (' ', console.attr)
    screen_changed = True

def get_pixel(x,y):    
    return console.apage.surface0.get_at((x,y)).b

def get_graph_clip():
    view = graph_view if graph_view else console.apage.surface0.get_rect()
    return view.left, view.top, view.right-1, view.bottom-1

def set_graph_clip(x0, y0, x1, y1):
    global graph_view
    graph_view = pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)    
    
def unset_graph_clip():
    global graph_view
    graph_view = None    
    return console.apage.surface0.get_rect().center

def clear_graph_clip(bg):
    global screen_changed
    console.apage.surface0.set_clip(graph_view)
    console.apage.surface0.fill(bg)
    console.apage.surface0.set_clip(None)
    screen_changed = True

def remove_graph_clip():
    console.apage.surface0.set_clip(None)

def apply_graph_clip():
    console.apage.surface0.set_clip(graph_view)

def fill_rect(x0, y0, x1, y1, index):
    global screen_changed
    rect = pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)
    console.apage.surface0.fill(index, rect)
    cx0, cy0 = min(console.width-1, max(0, x0//8)), min(console.height-1, max(0, y0//font_height)) 
    cx1, cy1 = min(console.width-1, max(0, x1//8)), min(console.height-1, max(0, y1//font_height))
    for r in range(cy0, cy1+1):
        console.apage.row[r].buf[cx0:cx1+1] = [(' ', console.attr)] * (cx1 - cx0 + 1)
    screen_changed = True

def numpy_set(left, right):
    left[:] = right

def numpy_not(left, right):
    left[:] = right
    left ^= (1<<graphics.bitsperpixel)-1

def numpy_iand(left, right):
    left &= right

def numpy_ior(left, right):
    left |= right

def numpy_ixor(left, right):
    left ^= right
        
fast_operations = {
    '\xC6': numpy_set, #PSET
    '\xC7': numpy_not, #PRESET
    '\xEE': numpy_iand,
    '\xEF': numpy_ior,
    '\xF0': numpy_ixor,
    }

def fast_get(x0, y0, x1, y1, varname):
    # arrays[varname] must exist at this point (or GET would have raised error 5)
    version = var.arrays[varname][2]
    # copy a numpy array of the target area
    clip = pygame.surfarray.array2d(console.apage.surface0.subsurface(pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)))
    get_put_store[varname] = ( x1-x0+1, y1-y0+1, clip, version )

def fast_put(x0, y0, varname, operation_char):
    global screen_changed
    try:
        width, height, clip, version = get_put_store[varname]
    except KeyError:
        # not yet stored, do it the slow way
        return False
    if x0 < 0 or x0+width > size[0] or y0 < 0 or y0+ height > size[1]:
        # let the normal version handle errors
        return False    
    # varname must exist at this point (or PUT would have raised error 5)       
    # if the versions are not the same, use the slow method (array has changed since clip was stored)
    if version != var.arrays[varname][2]:
        return False
    # reference the destination area
    dest_array = pygame.surfarray.pixels2d(console.apage.surface0.subsurface(pygame.Rect(x0, y0, width, height))) 
    # apply the operation
    operation = fast_operations[operation_char]
    operation(dest_array, clip)
    cx0, cy0 = min(console.width-1, max(0, x0//8)), min(console.height-1, max(0, y0//font_height)) 
    cx1, cy1 = min(console.width-1, max(0, (x0+width)//8)), min(console.height-1, max(0, (y0+height)//font_height))
    for r in range(cy0, cy1+1):
        console.apage.row[r].buf[cx0:cx1+1] = [(' ', console.attr)] * (cx1 - cx0 + 1)
    screen_changed = True
    return True

####################################
# sound interface

from math import ceil

music_foreground = True

def music_queue_length():
    # top of sound_queue is currently playing
    return max(0, len(sound_queue)-1)
        
def init_sound():
    return numpy != None
    
def beep():
    play_sound(800, 0.25)

def stop_all_sound():
    global sound_queue
    pygame.mixer.quit()
    sound_queue = []
    
# process sound queue in event loop
def check_sound():
    global last_chunk, same_chunk_ticks, loop_sound, loop_sound_playing
    if not sound_queue:
        check_quit_sound()
    else:    
        check_init_mixer()
        # check for hangups
        check_hangs()
        # stop looping sound, allow queue to pass
        if loop_sound_playing:
            loop_sound_playing.stop()
            loop_sound_playing = None
        if pygame.mixer.Channel(0).get_queue() == None:
            if loop_sound:
                # loop the current playing sound; ok to interrupt it with play cos it's the same sound as is playing
                pygame.mixer.Channel(0).play(loop_sound, loops=-1)
                sound_queue.pop(0)
                loop_sound_playing = loop_sound                
                loop_sound = None
            else:
                current_list = sound_queue[0]
                if not current_list:
                    sound_queue.pop(0)
                    try:
                        current_list = sound_queue[0]
                    except IndexError:
                        check_quit_sound()
                        return
                pair_to_play = current_list.pop(0)         
                pygame.mixer.Channel(0).queue(pair_to_play[0])
                if pair_to_play[1]:
                    loop_sound = pair_to_play[0] 
                    # any next sound in the sound queue will stop this looping sound
                else:   
                    loop_sound = None
        
def wait_music(wait_length=0, wait_last=True):
    while not loop_sound_playing and (
            len(sound_queue) + wait_last - 1 > wait_length 
            or (wait_last and music_queue_length() == 0 and pygame.mixer.get_busy())):
        idle()
        console.check_events()

def play_sound(frequency, total_duration, fill=1, loop=False):
    check_init_mixer()
    # one wavelength at 37 Hz is 1192 samples at 44100 Hz
    chunk_length = 1192 * 2
    # actual duration and gap length
    duration, gap = fill * total_duration, (1-fill) * total_duration
    if frequency == 0 or frequency == 32767:
        chunk = numpy.zeros(chunk_length)
    else:
        num_samples = sample_rate / (2.*frequency)
        num_half = ceil(sample_rate/ (2.*frequency))
        # build wavelength of a square wave at max amplitude
        wave0 = numpy.ones(num_half, numpy.int16) * (1<<mixer_bits - 1)
        wave1 = -wave0
        wave0_1 = wave0[:-1]
        wave1_1 = wave1[:-1]
        # build chunk of waves
        chunk = numpy.array([])
        half_waves, samples = 0, 0
        while len(chunk) < chunk_length:
            if samples > int(num_samples*half_waves):
                chunk = numpy.concatenate((chunk, wave0_1))
                samples += num_half-1
            else:    
                chunk = numpy.concatenate((chunk, wave0))
                samples += num_half
            half_waves += 1
            if samples > int(num_samples*half_waves):
                chunk = numpy.concatenate((chunk, wave1_1))
                samples += num_half-1
            else:    
                chunk = numpy.concatenate((chunk, wave1))
                samples += num_half                
            chunk = numpy.concatenate((chunk, wave1))
            half_waves += 1
        chunk_length = len(chunk)    
    if not loop:    
        # make the last chunk longer than a normal chunk rather than shorter, to avoid jumping sound    
        floor_num_chunks = max(0, -1 + int((duration * sample_rate) / chunk_length))
        sound_list = [] if floor_num_chunks == 0 else [ (pygame.sndarray.make_sound(chunk), False) ]*floor_num_chunks
        rest_length = int(duration * sample_rate) - chunk_length * floor_num_chunks
    else:
        # attach one chunk to loop
        sound_list = []
        rest_length = chunk_length
    # create the sound queue entry
    sound_list.append((pygame.sndarray.make_sound(chunk[:rest_length]), loop))
    # append quiet gap if requested
    if gap:
        gap_length = gap * sample_rate
        chunk = numpy.zeros(gap_length)
        sound_list.append((pygame.sndarray.make_sound(chunk), False))
    # at most 16 notes in the sound queue (not 32 as the guide says!)
    wait_music(15)
    sound_queue.append(sound_list)

# implementation

sound_queue = []

mixer_bits = 16
sample_rate = 44100

# quit sound server after quiet period of quiet_quit ticks, to avoid high-ish cpu load from the sound server.
quiet_ticks = 0        
quiet_quit = 200

# kill the mixer after encountering the same chunk for may times - it has a tendency to hang.
last_chunk = None
same_chunk_ticks = 0
max_ticks_same = 150

# loop the sound  in the mixer queue
loop_sound = None
# currrent sound that is looping
loop_sound_playing = None

try:
    import numpy
except Exception:
    numpy = None



def pre_init_mixer():
    global sample_rate, mixer_bits
    pygame.mixer.pre_init(sample_rate*4, -mixer_bits, channels=1, buffer=128) #4096

def init_mixer():    
    pygame.mixer.quit()
    
def check_init_mixer():
    if pygame.mixer.get_init() == None:
        pygame.mixer.init()
        
def check_quit_sound():
    global quiet_ticks
    if pygame.mixer.get_init() == None:
        return
    if music_queue_length() > 0 or pygame.mixer.get_busy():
        quiet_ticks = 0
    else:
        quiet_ticks += 1    
        if quiet_ticks > quiet_quit:
            # this is to avoid high pulseaudio cpu load
            pygame.mixer.quit()

def check_hangs():
    global last_chunk, same_chunk_ticks
    current_chunk = pygame.mixer.Channel(0).get_queue() 
    if current_chunk == last_chunk:
        same_chunk_ticks += 1
        if same_chunk_ticks > max_ticks_same:
            same_chunk_ticks = 0
            # too long for the sort of chunks we use, it's hung.
            pygame.mixer.quit()
            pygame.mixer.init()
    else:
        same_chunk_ticks = 0    
    last_chunk = current_chunk
        
