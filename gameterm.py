#
# PC-BASIC 3.23 - gameterm.py
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


import console

import pygame
import sys
import numpy

import util
import tokenise
import error
import cpi_font
import unicodepage 

import events
import fp

import var





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

# for use with get_at
workaround_palette= [ (0,0,0),(0,0,1),(0,0,2),(0,0,3),(0,0,4),(0,0,5),(0,0,6),(0,0,7),(0,0,8),(0,0,9),(0,0,10),(0,0,11),(0,0,12),(0,0,13),(0,0,14),(0,0,15) ]


# cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
# cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
#

gamecolours16 = [ pygame.Color(*rgb) for rgb in colours16 ]
gamecolours64 = [ pygame.Color(*rgb) for rgb in colours64 ]

palette64=None


glyphs = []

#num_surfaces = 0
#surfaces = []
#surface0=None
#surface1=None

screen=None
cursor0=None

cycle=0

screen_changed=True
    
scroll_area=None


fonts=None
font=None
font_height=16

bitsperpixel=4


# backend interface


def init():
    global fonts
    pre_init_sound()    
    pygame.init()
    pygame.display.set_caption('PC-BASIC 3.23')
    pygame.key.set_repeat(500,24)
    fonts = cpi_font.load_codepage()
    console.set_mode(0)
    init_sound()
        
def close():
    pygame.display.quit()    

def pause():
    pass

def cont():
    pass
    
    
# standard palettes
palette64=[0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]

def get_palette_entry(index):
    return palette64[index]




    
def set_palette(new_palette=None):
    global palette64 #, surface0, surface1, 
    global cursor0, screen
    
    if console.num_palette==64:
        if new_palette==None:
            new_palette=[0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]
        
        palette64= new_palette
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
    global palette64 #, surface0, surface1, 
    global cursor0, screen
    palette64[index] = colour
    
    if console.num_palette==64:
        gamecolor = gamecolours64[colour]
    else:
        gamecolor = gamecolours16[colour]
 
    screen.set_palette_at(index,gamecolor)
    under_cursor.set_palette_at(index,gamecolor)
    
    
def clear_scroll_area(bg):
    global screen #, surface0,surface1
    global scroll_area
    global screen_changed
    
    console.apage.surface0.set_clip(scroll_area)
    console.apage.surface1.set_clip(scroll_area)
    
    console.apage.surface0.fill(bg)
    console.apage.surface1.fill(bg)
    
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    
    screen_changed=True
   
        

def set_font_height(new_font_height):
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


def init_screen_mode(mode):
    global surface0, last_point, pixel_aspect_ratio, bitsperpixel, screen_changed
    global glyphs
    
    build_cursor()            
    
    glyphs = []
    for c in range(256):
        glyphs.append(build_glyph(c, font, font_height) )      
        
    if mode != 0:
        last_point = console.apage.surface0.get_rect().center
        # pixels e.g. 80*8 x 25*14, screen ratio 4x3 makes for pixel width/height (4/3)*(25*14/8*80)
        pixel_aspect_ratio = fp.div(fp.from_int(fp.MBF_class, console.height*font_height), fp.from_int(fp.MBF_class, 6*console.width)) 
        
    
    if mode in (1,10):
        bitsperpixel=2
    elif mode==2:
        bitsperpixel=1
    else:
        bitsperpixel=4
        
    # set standard cursor
    build_line_cursor(True)
    
    
def setup_screen(to_height, to_width):
    global screen, font_height, palette64
    #global surface0, surface1, 
    global cursor0
    global screen_changed
    
    size = to_width*8, to_height*font_height
    screen = pygame.display.set_mode(size, 0,8)
    
    # whole screen (blink on & off)
    for i in range(console.num_pages):
        console.pages[i].surface1 = pygame.Surface(size, depth=8)
        console.pages[i].surface0 = pygame.Surface(size, depth=8)
    ##
        console.pages[i].surface0.set_palette(workaround_palette)
        console.pages[i].surface1.set_palette(workaround_palette)
    ##  

    cursor0 = pygame.Surface((8, font_height), depth=8)
    build_cursor()            
    set_palette()
    
    screen_changed=True
    

def copy_page(src,dst):
    global screen_changed
    
    console.pages[dst].surface0.blit(console.pages[src].surface0, (0,0))
    console.pages[dst].surface1.blit(console.pages[src].surface1, (0,0))
    screen_changed=True
    
def set_scroll_area(view_start, scroll_height, width):    
    global scroll_area
    scroll_area = pygame.Rect(0,(view_start-1)*font_height, width*8, (scroll_height-view_start+1)*font_height)    

    
   
def show_cursor(do_show, prev):
    global screen_changed
    screen_changed=True
    

    

def set_cursor_colour(color):
    global screen, cursor0
    cursor0.set_palette_at(254, screen.get_palette_at(color))



def build_line_cursor(is_line):
    
    global font_height
    global cursor_from, cursor_to
    global screen_changed
    
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
    
    screen_changed=True
                



def debug_write(trow, tcol, msg):
    global width
    sys.stderr.write(msg)
    return
    


def debug_write_char(row, pos, c):
    if c != '':
        debug_write(row, pos, c.encode('hex'))






   


   
def scroll(from_line):
    #global surface0, surface1, 
    global font_height, scroll_area, screen_changed
  
    temp_scroll_area = pygame.Rect(0,(from_line-1)*font_height,console.width*8, (console.scroll_height-from_line+1)*font_height)
    
    # scroll
    console.apage.surface0.set_clip(temp_scroll_area)
    console.apage.surface1.set_clip(temp_scroll_area)
    
    console.apage.surface0.scroll(0, -font_height)
    console.apage.surface1.scroll(0, -font_height)
    
    # empty new line
    blank = pygame.Surface( (console.width*8, font_height) , depth=8)
    fore, back = console.colours(console.attr)
    
    bg = back& 0xf
  
    blank.set_palette(workaround_palette)
    
    blank.fill(bg)
    console.apage.surface0.blit(blank, (0, (console.scroll_height-1)*font_height))
    console.apage.surface1.blit(blank, (0, (console.scroll_height-1)*font_height))
        
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    
    
    screen_changed=True
    


   
def scroll_down(from_line):
    #global surface0, surface1, 
    global font_height
    global screen_changed

    temp_scroll_area = pygame.Rect(0,(from_line-1)*font_height, console.width*8, (console.scroll_height-from_line+1)*font_height)
    
    console.apage.surface0.set_clip(temp_scroll_area)
    console.apage.surface1.set_clip(temp_scroll_area)
    
    console.apage.surface0.scroll(0, font_height)
    console.apage.surface1.scroll(0, font_height)
    
    # empty new line
    blank = pygame.Surface( (console.width*8, font_height), depth=8 )
    fore, back = console.colours(console.attr)
    bg = back& 0xf
  
    blank.set_palette(workaround_palette)
    
    
    blank.fill(bg)
    console.apage.surface0.blit(blank, (0, (from_line-1)*font_height))
    console.apage.surface1.blit(blank, (0, (from_line-1)*font_height))
        
    console.apage.surface0.set_clip(None)
    console.apage.surface1.set_clip(None)
    
    screen_changed=True
    
   




blink_state=0

cursor_from = 0
cursor_to = 0    

last_cycle=0
cycle_time=120 #120
blink_cycles=5


    
    
def putc_at(row, col, c, attr):
    global font, font_height, gamecolours
    #global surface0, surface1, 
    global blink_state 
    global glyphs    
    global screen_changed
    
    fore, back = console.colours(attr)
    
    ##color = console.apage.surface0.get_palette_at(fore&0xf)
    ##bg = console.apage.surface0.get_palette_at(back&0x7)
    color = (0,0,fore&0xf)
    bg = (0,0,back&0x7)
    
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

    screen_changed=True
    
    
    
    
    
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
            if bit==1:
                glyph.set_at(pos, color)
    
    return glyph            
    
    
def build_cursor():
    global font_height
    global cursor0
    global cursor_from, cursor_to
    
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
        
        
  
        
last_row=1
last_col=1    
under_cursor=None
under_top_left=None

def refresh_screen():
    global blink_state, screen # surface0, console.apage.surface1
    global last_row, last_col
    
    save_palette = screen.get_palette()
      
    if console.graphics_mode or blink_state==0:
        console.vpage.surface0.set_palette(save_palette)
        screen.blit(console.vpage.surface0, (0,0))
        console.vpage.surface0.set_palette(workaround_palette)
    elif blink_state==1: 
        console.vpage.surface1.set_palette(save_palette)
        screen.blit(console.vpage.surface1, (0,0))
        console.vpage.surface1.set_palette(workaround_palette)
     
            
    
def remove_cursor():
    global under_top_left, under_cursor, screen
    
    #import sys
    #sys.stderr.write(repr(screen)+repr(under_top_left)+repr(under_cursor))
    
    if under_top_left != None:
        screen.blit(under_cursor, under_top_left)
         


def refresh_cursor():
    global screen, last_row, last_col
    global under_top_left, under_cursor

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
    
    
            

def check_events():
    global screen #, surface0, surface, 
    global cursor0, font_height, last_row, last_col
    global cycle
    global blink_state
    global last_cycle, cycle_time, blink_cycles
    global screen_changed
    
    
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            handle_key(event)

    if not console.graphics_mode:
        if cycle==0:
            blink_state=0
            screen_changed=True
        elif cycle==blink_cycles*2: 
            blink_state=1
            screen_changed=True
    
    
    tock = pygame.time.get_ticks() 
    if (tock - last_cycle) >= (cycle_time/blink_cycles):
        last_cycle = tock
        cycle+=1
        if cycle == blink_cycles*4: 
            cycle=0
     
     
        cursor_changed = (not console.graphics_mode and cycle%blink_cycles==0) or (console.row !=last_row) or (console.col != last_col)
        
        if screen_changed:
            refresh_screen()
            refresh_cursor()
            pygame.display.flip()             
        elif cursor_changed and console.cursor:
            remove_cursor()
            refresh_cursor()
            pygame.display.flip()             
        
        screen_changed=False
        
        # check user events
        events.check_events()
        events.handle_events()
            
        # manage sound queue
        check_sound()
            
            
            
            
def idle():
    global cycle_time, blink_cycles
    pygame.time.wait(cycle_time/blink_cycles)  
  

  
def handle_key(e):
    c=''
    if e.key in (pygame.K_PAUSE, pygame.K_BREAK):
        mods = pygame.key.get_mods() 
        if mods & pygame.KMOD_CTRL:
            # ctrl-break
            raise error.Break()
    elif e.key==pygame.K_DELETE:
        c+= keycode_to_scancode[e.key]    
    elif len(e.unicode)>0 and ord(e.unicode)== 0:   # NUL
        c+= '\x00\x00'
    elif len(e.unicode)>0 and ord(e.unicode)>=0x20:# and (ord(e.unicode) in unicodepage.from_unicode): 
        c += unicodepage.from_unicode(e.unicode)    
    elif e.key in keycode_to_scancode:
        c += keycode_to_scancode[e.key]
    elif len(e.unicode)>0 and ord(e.unicode) < 0x20:
        c += chr(ord(e.unicode))    
    console.keybuf+= events.replace_key(c)


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
    pygame.K_F10:   '\x00\x44'

}
    #K_PRINT               print screen
    #K_SYSREQ              sysrq
    






###############################################

# graphical

graph_view=None
view_graph_absolute=True
graph_window=None
graph_window_bounds=None


last_point = (0,0)    
pixel_aspect_ratio = fp.MBF_class.one


            
# cursor for graphics mode
def xor_cursor_screen(row,col):
    global screen, font_height, cursor_from, cursor_to
    
    fore, back = console.colours(console.attr)
    index = fore&0xf
    
    
    for x in range((col-1)*8,col*8):
        for y in range((row-1)*font_height+cursor_from,(row-1)*font_height+cursor_to):
        
            pixel = console.apage.surface0.get_at((x,y)).b
            screen.set_at((x,y), pixel^index)

    
def get_coord():
    return last_point


def get_aspect_ratio():
    return pixel_aspect_ratio

def set_graph_view(x0,y0,x1,y1, absolute=True):
    global graph_view, view_graph_absolute, last_point
    
    # VIEW orders the coordinates
    if x0>x1:
        x0,x1 = x1,x0
    if y0>y1:
        y0,y1 = y1,y0
        
    view_graph_absolute=absolute
    graph_view=pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)    
    last_point = graph_view.center
    if graph_window_bounds !=None:
        set_graph_window(*graph_window_bounds)

def unset_graph_view():
    global graph_view, view_graph_absolute, last_point #, surface0
    view_graph_absolute=False
    graph_view=None    
    last_point = console.apage.surface0.get_rect().center
    if graph_window_bounds !=None:
        set_graph_window(*graph_window_bounds)


def apply_graph_view(crop=None):
    global graph_view
    view = console.apage.surface0.get_rect()
    if graph_view != None:
        view=view.clip(graph_view)
    if crop != None:
        view=view.clip(crop)
    console.apage.surface0.set_clip(view)
    
    
def remove_graph_view():
    global surface0
    console.apage.surface0.set_clip(None)
    
    
def view_coords(x,y):
    global view_graph_absolute
    
    if graph_view==None or view_graph_absolute:
        return x,y
    else:
        return x+graph_view.left, y+graph_view.top
        


def clear_graphics_view():
    #global surface0, 
    global screen_changed
    fore, back = console.colours(console.attr)
    bg = back&0x7    

    apply_graph_view()
    console.apage.surface0.fill(bg)
    remove_graph_view()
    
    screen_changed=True
    
    
def set_graph_window(fx0, fy0, fx1, fy1, cartesian=True):
    global graph_view, view_graph_absolute, graph_window, graph_window_bounds
    #global surface0
    
    if fp.gt(fy0,fy1):
        fy0, fy1 = fy1,fy0
    if fp.gt(fx0,fx1):
        fx0, fx1 = fx1,fx0
    
    if cartesian:
        fy0, fy1 = fy1, fy0

    
    if view_graph_absolute or graph_view==None:
        view = console.apage.surface0.get_rect()    
    else:
        view = graph_view    
        
    x0,y0 = fp.MBF_class.zero, fp.MBF_class.zero #fp.from_int(fp.MBF_class, view.left), fp.from_int(fp.MBF_class, view.top)
    x1,y1 = fp.from_int(fp.MBF_class, view.right-view.left-1), fp.from_int(fp.MBF_class, view.bottom-view.top-1)        

    scalex, scaley = fp.div(fp.sub(x1, x0), fp.sub(fx1,fx0)), fp.div(fp.sub(y1, y0), fp.sub(fy1,fy0)) 
    offsetx, offsety = fp.sub(x0, fp.mul(fx0,scalex)), fp.sub(y0, fp.mul(fy0,scaley))
    
    graph_window = scalex, scaley, offsetx, offsety
    graph_window_bounds = fx0, fy0, fx1, fy1, cartesian


def unset_graph_window():
    global graph_window, graph_window_bounds
    graph_window=None
    graph_window_bounds=None


def window_coords(fx, fy):
    global graph_window
    if graph_window!=None:
        scalex, scaley, offsetx, offsety = graph_window
        x = fp.round_to_int(fp.add(offsetx, fp.mul(fx, scalex)))
        y = fp.round_to_int(fp.add(offsety, fp.mul(fy, scaley)))
    else:
        x = fp.round_to_int(fx)
        y = fp.round_to_int(fy)
    
    return x, y

# inverse function
def get_window_coords(x, y):
    global graph_window
    
    x = fp.from_int(fp.MBF_class, x)
    y = fp.from_int(fp.MBF_class, y)
    
    if graph_window!=None:
        scalex, scaley, offsetx, offsety = graph_window
        fx = fp.div(fp.sub(x, offsetx), scalex)
        fy = fp.div(fp.sub(y, offsety), scaley)
    else:
        fx = x
        fy = y
    
    return fx, fy


def window_scale(fx, fy):
    global graph_window
    
    if graph_window!=None:
        scalex, scaley, offsetx, offsety = graph_window
        x = fp.round_to_int(fp.mul(fx, scalex))
        y = fp.round_to_int(fp.mul(fy, scaley))
    else:
        x = fp.round_to_int(fx)
        y = fp.round_to_int(fy)
    
    return x, y


def put_pixel(x,y, index):
    #global surface0, 
    global screen_changed
    console.apage.surface0.set_at((x,y), index)
    screen_changed=True

def get_colour_index(c):
    if c==-1:
        fore, back = console.colours(console.attr)
        c = fore&0xf
    elif c==-2:
        fore, back = console.colours(console.attr)
        c = back&0x7    
    
    else:
        if c<0:
            c=0
        if c>=console.num_colours:
            c=console.num_colours-1
    return c





def put_point(x, y, c):
    global last_point
    last_point = (x,y)
    
    apply_graph_view()
    x, y = view_coords(x,y)
    put_pixel(x,y,get_colour_index(c))
    remove_graph_view()
    
    
def get_point (x,y):
    #global surface0
    
    # need 1.9.2 for this
    #return console.apage.surface0.get_at_mapped(x,y)
    
    x,y = view_coords(x,y)
    return console.apage.surface0.get_at((x,y)).b
    
    
def draw_line(x0,y0, x1,y1, c, pattern=0xffff):
    global last_point
    
    last_point=x1,y1
    
    c = get_colour_index(c)
    apply_graph_view()
    
    x0,y0 = view_coords(x0,y0)
    x1,y1 = view_coords(x1,y1)
    
    # Bresenham algorithm
    dx, dy  = abs(x1-x0), abs(y1-y0)
    
    steep = dy > dx
    if steep:
        x0, y0, x1, y1 = y0, x0, y1, x1
        dx, dy = dy, dx
    
    sx = 1 if x1>x0 else -1
    sy = 1 if y1>y0 else -1
    
    mask = 0x8000
    error = dx/2
    x, y = x0, y0
    #while x>=min(x0,x1) and x<=max(x0,x1):
    
    for x in xrange(x0,x1+sx,sx):
        if pattern&mask!=0:
            if steep:
                put_pixel(y, x, c)
            else:
                put_pixel(x, y, c)
        
        mask= mask>>1
        if mask==0:
            mask = 0x8000
                
        error -= dy
        if error<0:
            y += sy
            error += dx    
        #x += sx    
        
    remove_graph_view()
    
def draw_straight(p0,p1,q, c, pattern, mask, xy=0):
    sp = 1 if p1>p0 else -1
    for p in range (p0,p1+sp,sp):
        if pattern&mask!=0:
            if xy==0:
                put_pixel(p, q, c)
            else:
                put_pixel(q, p, c)
        mask= mask>>1
        if mask==0:
            mask = 0x8000
        
    return mask

                        
def draw_box(x0,y0, x1,y1, c, pattern=0xffff):
    global last_point
    
    last_point=x1,y1
    
    apply_graph_view()
    x0,y0 = view_coords(x0,y0)
    x1,y1 = view_coords(x1,y1)
    
    c = get_colour_index(c)
    mask = 0x8000
    
    mask = draw_straight(y0,y1,x0,c, pattern,mask,1)
    mask = draw_straight(x0,x1,y1,c, pattern,mask,0)
    mask = draw_straight(y1,y0,x1,c, pattern,mask,1)
    mask = draw_straight(x1,x0,y0,c, pattern,mask,0)
    
    remove_graph_view()

        
def draw_box_filled(x0,y0, x1,y1, c):
    global last_point 
    #, surface0
    
    last_point=x1,y1
    
    x0,y0 = view_coords(x0,y0)
    x1,y1 = view_coords(x1,y1)
    
    c = get_colour_index(c)
    
    if y1<y0:
        y0,y1 = y1,y0
    if x1<x0:
        x0,x1 = x1,x0    
    
    rect = pygame.Rect(x0,y0,x1-x0+1,y1-y0+1)
    
    apply_graph_view()
    console.apage.surface0.fill(c, rect)
    remove_graph_view()
    

# causes problems with zero radius
def draw_circle2(x0,y0,r,c):
    global last_point, screen_changed
    #global surface0
    
    last_point=x0,y0
    c = get_colour_index(c)
    
    apply_graph_view()
    x0,y0 = view_coords(x0,y0)
    pygame.draw.circle(console.apage.surface0,c, (x0,y0), r+1, 1)
    remove_graph_view()
    screen_changed=True


# pygrame.draw implementation - ellipses don't quite look right, won't do zero radius
def draw_ellipse2(x0,y0,x1,y1,c):
    global last_point, screen_changed
    #global surface0
    last_point=x0,y0
    
    c = get_colour_index(c)
    rect = pygame.Rect(x0,y0,x1-x0+1,y1-y0+1)
    apply_graph_view()
    x0,y0 = view_coords(x0,y0)
    
    pygame.draw.ellipse(console.apage.surface0,c, rect, 1)
    remove_graph_view()

    screen_changed=True

# http://en.wikipedia.org/wiki/Midpoint_circle_algorithm
def draw_circle(x0,y0,r,c, oct0=-1, coo0=-1, line0=False, oct1=-1, coo1=-1, line1=False):
    global last_point
    
    #x0,y0 = window_coords(x0,y0)
    
    last_point=x0,y0
    
    c = get_colour_index(c)
    apply_graph_view()
    x0,y0 = view_coords(x0,y0)
    
     
    if oct0==-1:
        hide_oct = range(0,0)
    elif oct0<oct1 or oct0==oct1 and octant_gte(oct0, coo1, coo0):
        hide_oct = range(0, oct0) + range(oct1+1, 8)
    else:
        hide_oct = range(oct1+1,oct0)
 
    # if oct1==oct0: 
    # ----|.....|--- : coo1 lt coo0 : print if y in [0,coo1] or in [coo0, r]  
    # ....|-----|... ; coo1 gte coo0: print if y in [coo0,coo1]
    
    
    #ymin = 0 
    #ymax = r+1 # won't trigger
    ## limit y range for arcs that fall within one octant (essential to avoid drawing too much arc) 
    ## or two consecutive octants (non-essential optimisation) 
    #if oct0==oct1 and octant_gte(oct0, coo1, coo0):
    #    ymin = min(coo0, coo1)
    #    ymax = max(coo0, coo1)
    #elif (oct1-oct0)%8==1:
    #    if oct0%2==0:
    #        ymin = min(coo0,coo1)    
    #    else:
    #        ymax = max(coo0,coo1)

    x, y= r, 0
    error=1-r 
    while x>=y:
      #  if y>=ymin:
        for octant in range(0,8):
            if octant in hide_oct:
                continue
            elif oct0!=oct1 and (octant==oct0 and octant_gte(oct0, coo0, y)):
                continue
            elif oct0!=oct1 and (octant==oct1 and octant_gte(oct1, y, coo1)):
                continue
            elif oct0==oct1 and octant==oct0:
                if octant_gte(oct0, coo1, coo0):
                    if octant_gte(oct0, y, coo1) or octant_gte(oct0, coo0,y):
                        continue
                else:
                    if octant_gte(oct0, y, coo1) and octant_gte(oct0, coo0, y):
                        continue
            
            put_pixel(*octant_coord(octant, x0,y0,x,y),index=c) 
            
        # remember endpoints for pie sectors
        if y==coo0:
            coo0x = x
        if y==coo1:
            coo1x = x    
        
        # bresenham error step
        y+=1
        if error<0:
            error += 2*y+1
        else:
            x-=1
            error += 2*(y-x+1)
        
     #   if y>ymax:
     #       break
    
    if line0:
        draw_line(x0,y0, *octant_coord(oct0, x0, y0, coo0x, coo0), c=c)
    if line1:
        draw_line(x0,y0, *octant_coord(oct1, x0, y0, coo1x, coo1), c=c)

    remove_graph_view()
    
    
def octant_coord(octant, x0,y0, x,y):    
    if   octant==7:     return x0+x, y0+y
    elif octant==0:     return x0+x, y0-y
    elif octant==4:     return x0-x, y0+y
    elif octant==3:     return x0-x, y0-y
    
    elif octant==6:     return x0+y, y0+x
    elif octant==1:     return x0+y, y0-x
    elif octant==5:     return x0-y, y0+x
    elif octant==2:     return x0-y, y0-x
    
    
def octant_gte(octant, y, coord):
    if octant%2==1: 
        return y<=coord 
    else: 
        return y>=coord
    
    
# notes on midpoint algo implementation:
#    
# x*x + y*y == r*r
# look at y'=y+1
# err(y) = y*y+x*x-r*r
# err(y') = y*y + 2y+1 + x'*x' - r*r == err(y) + x'*x' -x*x + 2y+1 
# if x the same:
#   err(y') == err(y) +2y+1
# if x -> x-1:
#   err(y') == err(y) +2y+1 -2x+1 == err(y) +2(y-x+1)

# why initialise error with 1-x == 1-r?
# we change x if the radius is more than 0.5pix out so err(y, r+0.5) == y*y + x*x - (r*r+r+0.25) == err(y,r) - r - 0.25 >0
# with err and r both integers, this just means err - r > 0 <==> err - r +1 >= 0
# above, error == err(y) -r + 1 and we change x if it's >=0.



# ellipse: 
# ry^2*x^2 + rx^2*y^2 == rx^2*ry^2
# look at y'=y+1 (quadrant between points of 45deg slope)
# err == ry^2*x^2 + rx^2*y^2 - rx^2*ry^2
# err(y') == rx^2*(y^2+2y+1) + ry^2(x'^2)- rx^2*ry^2 == err(y) + ry^2(x'^2-x^2) + rx^2*(2y+1)
# if x the same:
#   err(y') == err(y) + rx^2*(2y+1)
# if x' -> x-1:
#   err(y') == err(y) + rx^2*(2y+1) +rx^2(-2x+1)

# change x if radius more than 0.5pix out: err(y, rx+0.5, ry) == ry^2*y*y+rx^2*x*x - (ry*ry)*(rx*rx+rx+0.25) > 0
#  ==> err(y) - (rx+0.25)*(ry*ry) >0
#  ==> err(y) - (rx*ry*ry + 0.25*ry*ry ) > 0 

# break yinc loop if one step no longer suffices


    
# ellipse using midpoint algorithm
# for algorithm see http://members.chello.at/~easyfilter/bresenham.html
def draw_ellipse(cx,cy,rx,ry,c, qua0=-1, x0=-1, y0=-1, line0=False, qua1=-1, x1=-1,y1=-1, line1=False):
    global last_point
    
    #x0,y0 = window_coords(x0,y0)
    
    last_point=x0,y0
    
    c = get_colour_index(c)
    
    apply_graph_view()        
    cx,cy = view_coords(cx,cy)
    
    # find invisible quadrants
    if qua0==-1:
        hide_qua = range(0,0)
    elif qua0<qua1 or qua0==qua1 and quadrant_gte(qua0, x1,y1,x0,y0):
        hide_qua = range(0, qua0) + range(qua1+1, 4)
    else:
        hide_qua = range(qua1+1,qua0)
 
    # error increment
    dx = 16*(1-2*rx)*ry*ry    
    dy = 16*rx*rx 
    ddy = 32*rx*rx
    ddx = 32*ry*ry
    
    # error for first step
    err = dx+dy   

    x, y = rx, 0
    while True: 
        
        for quadrant in range(0,4):
            
            # skip invisible arc sectors
            if quadrant in hide_qua:
                continue
            elif qua0!=qua1 and (quadrant==qua0 and quadrant_gte(qua0, x0,y0, x, y)):
                continue
            elif qua0!=qua1 and (quadrant==qua1 and quadrant_gte(qua1, x, y, x1,y1)):
                continue
            elif qua0==qua1 and quadrant==qua0:
                if quadrant_gte(qua0, x1,y1, x0,y0):
                    if quadrant_gte(qua0, x,y, x1,y1) or quadrant_gte(qua0, x0,y0, x, y):
                        continue
                else:
                    if quadrant_gte(qua0, x,y, x1,y1) and quadrant_gte(qua0, x0, y0, x, y):
                        continue
            
            put_pixel(*quadrant_coord(quadrant, cx,cy,x,y), index=c) 
        
        # bresenham error step
        e2 = 2*err
        if (e2 <= dy):
            y += 1
            dy += ddy
            err += dy
        if (e2 >= dx or e2 > dy):
            x -= 1
            dx += ddx
            err += dx
            
        # NOTE - err changes sign at the change from y increase to x increase
        
        if (x < 0):
            break
   
    # too early stop of flat vertical ellipses
    # finish tip of ellipse
    while (y < ry): 
        put_pixel(cx, cy+y, c) 
        put_pixel(cx, cy-y, c) 
        y += 1 
    
    
    if line0:
        draw_line(cx,cy, *quadrant_coord(qua0, cx, cy, x0, y0), c=c)
    if line1:
        draw_line(cx,cy, *quadrant_coord(qua1, cx, cy, x1, y1), c=c)

        
    remove_graph_view()     
                

    
def quadrant_coord(quadrant, x0,y0, x,y):    
    if   quadrant==3:     return x0+x, y0+y
    elif quadrant==0:     return x0+x, y0-y
    elif quadrant==2:     return x0-x, y0+y
    elif quadrant==1:     return x0-x, y0-y
    
    
def quadrant_gte(quadrant, x,y, x0,y0):
    if quadrant%2==0:
        if y!=y0: return y>y0
        else: return x<=x0
    else:
        if y!=y0: return y<y0 
        else: return x>=x0 
        
        
#####        
        
      
# 4-way scanline flood fill
# http://en.wikipedia.org/wiki/Flood_fill


def check_scanline (line_seed, x_start, x_stop, y, c, border, ydir):
    #global surface0
    
    if x_stop< x_start:
        return line_seed
        
    x_start_next = x_start
    x_stop_next = x_start_next-1
    for x in range(x_start, x_stop+1):
        # here we check for border *as well as* fill colour, to avoid infinite loops over bits already painted (eg. 00 shape)
        if console.apage.surface0.get_at((x,y)).b not in (border,c):
            x_stop_next = x
        else:
            if x_stop_next >= x_start_next:
                line_seed.append([x_start_next, x_stop_next, y, ydir])
            x_start_next = x+1
    if x_stop_next >= x_start_next:
        line_seed.append([x_start_next, x_stop_next, y, ydir])
    
    return line_seed    


def fill_scanline(x_start, x_stop, y, pattern):
    global screen_changed
    #global surface0
    
    mask = 7-x_start%8
    for x in range(x_start, x_stop+1):
        c=0
        for b in range(bitsperpixel-1,-1,-1):
            c=c<<1
            c+=(pattern[b]&(1<<mask))>>mask
        
        mask-=1
        if mask<0:
            mask=7

        console.apage.surface0.set_at((x,y),c)
    
    screen_changed=True    
      
      
# flood fill stops on border colour in all directions; it also stops on scanlines in fill_colour
def flood_fill (x, y, pattern, c, border): 
    #global surface0
    
    if get_point(x,y)==border:
        return

    view = console.apage.surface0.get_rect()
    if graph_view != None:
        view=view.clip(graph_view)
    bound_x0, bound_y0 = view.left, view.top
    bound_x1, bound_y1 = view.right-1, view.bottom-1  
    
    x,y = view_coords(x,y)
    
            
    line_seed = [(x, x, y, 0)]

    while len(line_seed)>0:
        x_start, x_stop, y, ydir = line_seed.pop()
        
        # check left extension
        x_left = x_start
        while x_left-1 >= bound_x0 and console.apage.surface0.get_at((x_left-1,y)).b !=border:
            x_left -= 1
        
        # check right extension
        x_right = x_stop
        while x_right+1 <= bound_x1 and console.apage.surface0.get_at((x_right+1,y)).b!=border:
            x_right+=1
        
        if ydir==0:
            if y+1 <= bound_y1:
                line_seed = check_scanline(line_seed, x_left, x_right, y+1, c, border, 1)
            if y-1 >= bound_y0:
                line_seed = check_scanline(line_seed, x_left, x_right, y-1, c, border, -1)
        else:
            # check in proper direction
            if y+ydir <= bound_y1 and y+ydir >= bound_y0:
                line_seed = check_scanline(line_seed, x_left, x_right, y+ydir, c, border, ydir)
            # check extensions in counter direction
            if y-ydir <= bound_y1 and y-ydir >= bound_y0:
                
                line_seed = check_scanline(line_seed, x_left, x_start-1, y-ydir, c, border, -ydir)
                line_seed = check_scanline(line_seed, x_stop+1, x_right, y-ydir, c, border, -ydir)
        
        # draw the pixels    
        fill_scanline(x_left, x_right, y, pattern)
        
        # show progress
        check_events()



def operation_set(pix0, pix1):
    return pix1

def operation_not(pix0, pix1):
    global bitsperpixel
    return pix1^((1<<bitsperpixel)-1)

def operation_and(pix0, pix1):
    return pix0 & pix1

def operation_or(pix0, pix1):
    return pix0 | pix1

def operation_xor(pix0, pix1):
    return pix0 ^ pix1
       
   
   
def set_area(x0,y0, array, operation):
    global bitsperpixel
    
    byte_array = []
    for i in range(4):
        byte_array.append( var.get_array_byte(array, i) )
    
    dx = util.uint_to_value(byte_array[0:2])
    dy = util.uint_to_value(byte_array[2:4])

    
    # in mode 1, number of x bits is given rather than pixels
    if console.screen_mode==1:
        dx/=2
    
    x1,y1 = x0+dx-1, y0+dy-1
    
    bytesperword=2
    bitsperword = bytesperword*8
    
    
    apply_graph_view()
    x0,y0 = view_coords(x0,y0)
    x1,y1 = view_coords(x1,y1)

    byte = 4
    mask=0x80
    hilo=0
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
    
            pixel = console.apage.surface0.get_at((x,y)).b
           
            index = 0
            
            for b in range(bitsperpixel):
                if ord( var.get_array_byte(array, byte+hilo+b*bytesperword) )&mask !=0:
                    index |= 1<<b  
            mask>>=1
            
            if mask==0: 
                mask=0x80
                
                if hilo==bytesperword-1:
                    byte+=bitsperpixel*bytesperword
                    hilo=0
                else:
                    hilo+=1
        
            put_pixel(x,y, operation(pixel, index)) 
    
        # left align next row
        if mask !=0x80:
            mask=0x80
            byte+=bitsperpixel*bytesperword
            hilo=0
    
    remove_graph_view()        
                
        
def get_area(x0,y0,x1,y1, array):
    global bitsperpixel
    
    dx = (x1-x0+1)
    dy = (y1-y0+1)
   
    # in mode 1, number of x bits is given rather than pixels
    if console.screen_mode==1:
        byte_array = list(tokenise.value_to_uint(dx*2)) + list(tokenise.value_to_uint(dy)) 
    else:
        byte_array = list(tokenise.value_to_uint(dx)) + list(tokenise.value_to_uint(dy)) 

    for i in range(4):
        var.set_array_byte(array, i, byte_array[i])


    bytesperword=2
    bitsperword=bytesperword*8
    
    
    x0,y0 = view_coords(x0,y0)
    x1,y1 = view_coords(x1,y1)
    
    byte = 4
    
    mask=0x80
    hilo=0
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
            pixel = console.apage.surface0.get_at((x,y)).b
            
            for b in range(bitsperpixel):
                if pixel&(1<<b) != 0:
                    var.set_array_byte(  array, byte+hilo+b*bytesperword,  \
                               chr(ord(var.get_array_byte(array, byte+hilo+b*bytesperword)) | mask)  )

            mask>>=1
            
            if mask==0: 
                mask=0x80
                
                if hilo==bytesperword-1:
                    byte+=bitsperpixel*bytesperword
                    hilo=0
                else:
                    hilo+=1
        
        # left align next row
        if mask !=0x80:
            mask=0x80
            byte+=bitsperpixel*bytesperword
            hilo=0

    
    
   

####################################
# SOUND
#
# http://stackoverflow.com/questions/7816294/simple-pygame-audio-at-a-frequency



mixer_bits=16
mixer_samplerate= 44100*4
#beepbuf=None

sound_queue = []

def pre_init_sound():
    global mixer_samplerate, mixer_bits
    pygame.mixer.pre_init(mixer_samplerate, -mixer_bits, channels=1, buffer=128) #4096

def init_sound():    
    pygame.mixer.quit()
    
    
def stop_all_sound():
    pygame.mixer.quit()
        
    
def check_init_sound():
    if pygame.mixer.get_init() ==None:
        pygame.mixer.init()

quiet_ticks = 0        
quiet_quit = 100
def check_quit_sound():
    global sound_queue, quiet_ticks, quiet_quit
    
    if pygame.mixer.get_init() == None:
        return
        
    if len(sound_queue)>0 or pygame.mixer.get_busy():
        quiet_ticks=0
    else:
        quiet_ticks+=1    
        if quiet_ticks > quiet_quit:
            # this is to avoid high pulseaudio cpu load
            pygame.mixer.quit()
            
     
def play_sound(frequency, duration):
    global sound_queue, mixer_samplerate, mixer_bits
    check_init_sound()
    
    
    amplitude = 2**(mixer_bits - 1) - 1

    # not clear why 4*freq instead of 2* ?
    numf = mixer_samplerate/(4*frequency)
    num = int(numf)
    rest = 0
    
    wave0 = numpy.ones(num, numpy.int16) * amplitude
    wave1 = -wave0
    wave2 = numpy.ones(num+1, numpy.int16) * amplitude    
    wave3 = -wave2
    
    # not clear why sample rate /4 ?
    buf=numpy.array([])
    while len(buf) < duration*mixer_samplerate/4:
        rest += (numf-num)
        if int(rest)>0:
            buf = numpy.concatenate((buf, wave0, wave1))
        else:
            buf = numpy.concatenate((buf, wave2, wave3))
    
        rest-=int(rest)
        
        
    
    sound = pygame.sndarray.make_sound(buf)
    sound_queue.append(sound)
        
    
def play_pause(duration):
    global sound_queue
    check_init_sound()
    
    buf = numpy.zeros(duration*mixer_samplerate/4)
    sound = pygame.sndarray.make_sound(buf)
    
    sound_queue.append(sound)
    

# process qound queue in event loop
def check_sound():
    global sound_queue
    
    if len(sound_queue)>0:
        check_init_sound()
    
        if pygame.mixer.Channel(0).get_queue() == None:
            pygame.mixer.Channel(0).queue(sound_queue.pop(0))
    else:
        check_quit_sound()
    

    
def wait_music():
    while len(sound_queue)>0 or pygame.mixer.get_busy():
        idle()
        check_events()
    
def beep():
    play_sound(800, 0.25)
    
def music_queue_length():
    global sound_queue
    return len(sound_queue)       
    
