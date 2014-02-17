#
# PC-BASIC 3.23 - backend_pygame.py
#
# Graphical console backend based on PyGame
# 
# (c) 2013 Rob Hagemans 
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
import sound
import events
import deviceio
import graphics
# for fast get & put only
import var

# not an echoing terminal
echo = False

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
# screen scroll area rect
scroll_area = None
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

    
def init():
    global fonts, num_sticks, joysticks
    pre_init_mixer()    
    pygame.init()
    pygame.display.set_caption('PC-BASIC 3.23')
    pygame.key.set_repeat(500,24)
    fonts = cpi_font.load_codepage()
    console.set_mode(0)
    init_mixer()
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
 
        
def close():
    pygame.joystick.quit()
    pygame.display.quit()    
    

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
    
def clear_scroll_area(bg):
    global screen_changed
    console.apage.surface0.fill(bg, scroll_area)
    console.apage.surface1.fill(bg, scroll_area)
    screen_changed = True
    
def clear_row(this_row, bg):
    global screen_changed
    rect = pygame.Rect(0,(this_row-1)*font_height, 1+console.width*8,1+font_height)
    console.apage.surface0.fill(bg, rect)
    console.apage.surface1.fill(bg, rect)
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
    cursor0 = pygame.Surface((8, font_height), depth=8)
    build_cursor()            
    glyphs = []
    for c in range(256):
        glyphs.append(build_glyph(c, font, font_height) )      
    # set standard cursor
    build_line_cursor(True)
    
    
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

    
def set_scroll_area(view_start, scroll_height, width):    
    global scroll_area
    scroll_area = pygame.Rect(0,(view_start-1)*font_height, width*8, (scroll_height-view_start+1)*font_height)    
    
   
def show_cursor(do_show, prev):
    global screen_changed
    if do_show != prev:
        screen_changed = True
    

def set_cursor_colour(color):
    cursor0.set_palette_at(254, screen.get_palette_at(color))


def build_line_cursor(is_line):
    global cursor_from, cursor_to, screen_changed
    if is_line and not console.graphics_mode:
        cursor_from = font_height-2
        cursor_to = font_height-2
    elif is_line and console.graphics_mode:
        cursor_from = 0
        cursor_to = font_height
    else:
        cursor_from = font_height/2
        cursor_to = font_height-1
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
    fore, back = console.colours(console.attr)
    bg = back & 0xf
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
    fore, back = console.colours(console.attr)
    bg = back & 0xf
    blank.set_palette(workaround_palette)
    blank.fill(bg)
    console.apage.surface0.blit(blank, (0, (from_line-1)*font_height))
    console.apage.surface1.blit(blank, (0, (from_line-1)*font_height))
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    screen_changed = True
    
    
def putc_at(row, col, c, attr):
    global screen_changed
    fore, back = console.colours(attr)
    color = (0, 0, fore & 0xf)
    bg = (0, 0, back & 0x7)
    blink = (fore>15 and fore<32)     
    glyph = glyphs[ord(c)]
    glyph.set_palette_at(255, bg)
    glyph.set_palette_at(254, color)
    blank = glyphs[32] # using SPACE for blank 
    blank.set_palette_at(255, bg)
    blank.set_palette_at(254, color)
    top_left = ((col-1)*8, (row-1)*font_height)
    console.apage.surface1.blit(glyph, top_left )
    if blink:
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
    color = 254
    bg = 255
    cursor0.set_colorkey(bg)
    cursor0.fill(bg)
    for yy in range(font_height):
        for xx in range(8):
            if yy<cursor_from or yy>cursor_to:
                pass
            else:
                cursor0.set_at((xx, yy), color)

def refresh_screen():
    save_palette = screen.get_palette()
    if console.graphics_mode or blink_state == 0:
        console.vpage.surface0.set_palette(save_palette)
        screen.blit(console.vpage.surface0, (0, 0))
        console.vpage.surface0.set_palette(workaround_palette)
    elif blink_state == 1: 
        console.vpage.surface1.set_palette(save_palette)
        screen.blit(console.vpage.surface1, (0, 0))
        console.vpage.surface1.set_palette(workaround_palette)
            
    
def remove_cursor():
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
    if not console.graphics_mode:
        # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
        if (cycle/blink_cycles==1 or cycle/blink_cycles==3): 
            screen.blit(cursor0, ( (console.col-1)*8, (console.row-1)*font_height) )
    else:
        xor_cursor_screen(console.row, console.col)        
    last_row = console.row
    last_col = console.col
    
    
            
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
        elif event.type == pygame.MOUSEBUTTONDOWN:
            handle_mouse(event)
    check_screen()
    return False
    
    
def check_screen():
    global cycle, last_cycle
    global screen_changed
    global blink_state
    if not console.graphics_mode:
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
        cursor_changed = (not console.graphics_mode and cycle%blink_cycles == 0) or (console.row != last_row) or (console.col != last_col)
        if screen_changed:
            refresh_screen()
            refresh_cursor()
            pygame.display.flip()             
        elif cursor_changed and console.cursor:
            remove_cursor()
            refresh_cursor()
            pygame.display.flip()             
        screen_changed = False

    
def handle_mouse(e):
    global pen_down, pen_down_pos
    if e.button == 1: # LEFT BUTTON
        events.pen_triggered = True
        pen_down = True
        pen_down_pos = e.pos
                

def handle_stick(e):
    if e.joy<2 and e.button<2:
        stick_fired[e.joy][e.button]=True
        events.stick_triggered[e.joy][e.button]=True
        
        
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
        console.caps = not console.caps 
    elif e.key == pygame.K_PRINT and  mods & pygame.KMOD_CTRL:
        if console.echo_read == None:
            console.echo_read = deviceio.lpt1
            console.echo_write = deviceio.lpt1
        else:  
            console.echo_read = None
            console.echo_write = None
    elif e.key == pygame.K_TAB and mods & pygame.KMOD_SHIFT:
        # shift+tab -> \x00\x0F (scancode for TAB) but TAB -> \x09
        c = '\x00\x0F'
    else:
        if (mods & pygame.KMOD_CTRL):
            try:
                c = ctrl_keycode_to_scancode[e.key]
            except KeyError:
                c = unicodepage.from_unicode(e.unicode)
        else:    
            try:
                c = keycode_to_scancode[e.key]
            except KeyError:
                c = unicodepage.from_unicode(e.unicode)
    console.insert_key(c) 
    

def pause_key():
    # pause key press waits for any key down. continues to process screen events (blink) but not user events.
    # TODO: does background music play ??
    while not check_events(pause=True):
        idle()
            
##############################################
# light pen (emulated by mouse)

supports_pen = True
supports_stick = True

# should be True on mouse click events
pen_down = False
pen_down_pos = (0,0)

stick_fired = [[False, False], [False, False]]

def get_pen_pos():
    x, y = pygame.mouse.get_pos()
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    if x >= console.width*8:
        x = console.width*8-1
    if y >= console.height*font_height:
        y = console.height*font_height-1
    return (x,y)
    
def get_last_pen_down_pos():
    x, y = pen_down_pos
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    if x >= console.width*8:
        x = console.width*8-1
    if y >= console.height*font_height:
        y = console.height*font_height-1
    return (x,y)
                
def pen_is_down():
    return (pygame.mouse.get_pressed()[0]==1)

def pen_has_been_down():
    global pen_down
    pen_down_old = pen_down
    pen_down = False
    return pen_down_old

def get_pen_pos_char():
    x, y = get_pen_pos()
    return 1 + x//8, 1 + y//font_height
      
def get_last_pen_down_pos_char():
    x, y = get_last_pen_down_pos()
    return 1 + x//8, 1 + y//font_height

def stick_coord(stick_num):
    if len(joysticks)<stick_num+1:
        return 0,0
    else:
        return int(joysticks[stick_num].get_axis(0)*100)+100, int(joysticks[stick_num].get_axis(1)*100)+100
    

def stick_trig(stick_num, trig_num):
    if len(joysticks)<stick_num+1 or joysticks[stick_num].get_numbuttons()<trig_num+1:
        return False
    else:
        return joysticks[stick_num].get_button(trig_num)
    
    
def stick_has_been_trig(stick_num, trig_num):
    if len(joysticks)<stick_num+1 or joysticks[stick_num].get_numbuttons()<trig_num+1:
        return False
    else:
        stick_trig_old = stick_fired
        stick_fired[stick_num][trig_num]=False
        return stick_trig_old[stick_num][trig_num]


###############################################
# graphical
# low-level methods (pygame implementation)


def put_pixel(x,y, index):
    global screen_changed
    console.apage.surface0.set_at((x,y), index)
    screen_changed=True
   

def get_pixel(x,y):    
    return console.apage.surface0.get_at((x,y)).b


def get_graph_clip():
    if graph_view == None:
        view = console.apage.surface0.get_rect()
    else:
        view = graph_view
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

    
def fill_rect(x0,y0, x1,y1, index):
    global screen_changed
    rect = pygame.Rect(x0,y0,x1-x0+1,y1-y0+1)
    console.apage.surface0.fill(index, rect)
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
    # varname must exist at this point (or PUT would have raised error 5)       
    # if the versions are not the same, use the slow method (array has changed since clip was stored)
    if version != var.arrays[varname][2]:
        return False
    # reference the destination area
    dest_array = pygame.surfarray.pixels2d(console.apage.surface0.subsurface(pygame.Rect(x0, y0, width, height))) 
    # apply the operation
    operation = fast_operations[operation_char]
    operation(dest_array, clip)
    screen_changed = True
    return True

######## end interface

graph_view = None


# cursor for graphics mode
def xor_cursor_screen(row,col):
    fore, back = console.colours(console.attr)
    index = fore & 0xf
    for x in range((col-1)*8,col*8):
        for y in range((row-1)*font_height+cursor_from,(row-1)*font_height+cursor_to):
            pixel = get_pixel(x,y)
            screen.set_at((x,y), pixel^index)

    
    
   

####################################
# SOUND
#
# see e.g. http://stackoverflow.com/questions/7816294/simple-pygame-audio-at-a-frequency


mixer_bits = 16
mixer_samplerate = 44100*4

# quit sound server after quiet period of quiet_quit ticks, to avoid high-ish cpu load from the sound server.
quiet_ticks = 0        
quiet_quit = 100

try:
    import numpy
except Exception:
    numpy = None
        

def pre_init_mixer():
    global mixer_samplerate, mixer_bits
    pygame.mixer.pre_init(mixer_samplerate, -mixer_bits, channels=1, buffer=128) #4096


def init_mixer():    
    pygame.mixer.quit()
    
def init_sound():
    return numpy != None
    
def stop_all_sound():
    pygame.mixer.quit()
        
    
def check_init_mixer():
    if pygame.mixer.get_init() ==None:
        pygame.mixer.init()
        
        
def check_quit_sound():
    global quiet_ticks
    if pygame.mixer.get_init() == None:
        return
    if len(sound.sound_queue) > 0 or pygame.mixer.get_busy():
        quiet_ticks = 0
    else:
        quiet_ticks += 1    
        if quiet_ticks > quiet_quit:
            # this is to avoid high pulseaudio cpu load
            pygame.mixer.quit()
            
    
def append_sound(frequency, duration):
    check_init_mixer()
    amplitude = 2**(mixer_bits - 1) - 1
    # not clear why 8*freq instead of 2* ?
    numf = mixer_samplerate/(8*frequency)
    num = int(numf)
    rest = 0
    wave0 = numpy.ones(num, numpy.int16) * amplitude
    wave1 = -wave0
    wave2 = numpy.ones(num+1, numpy.int16) * amplitude    
    wave3 = -wave2
    # not clear why sample rate /4 ?
    buf = numpy.array([])
    while len(buf) < duration*mixer_samplerate/4:
        rest += (numf-num)
        if int(rest)>0:
            buf = numpy.concatenate((buf, wave0, wave1))
        else:
            buf = numpy.concatenate((buf, wave2, wave3))
        rest -= int(rest)
    the_sound = pygame.sndarray.make_sound(buf)
    sound.sound_queue.append(the_sound)
        
        
def append_pause(duration):
    check_init_mixer()
    buf = numpy.zeros(duration*mixer_samplerate/4)
    pause = pygame.sndarray.make_sound(buf)
    sound.sound_queue.append(pause)
    

# process sound queue in event loop
def check_sound():
    if len(sound.sound_queue)>0:
        check_init_mixer()
        if pygame.mixer.Channel(0).get_queue() == None:
            pygame.mixer.Channel(0).queue(sound.sound_queue.pop(0))
    else:
        check_quit_sound()

        
def wait_music():
    while len(sound.sound_queue)>0 or pygame.mixer.get_busy():
        idle()
        console.check_events()
        
        
