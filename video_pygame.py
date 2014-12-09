"""
PC-BASIC 3.23 - video_pygame.py
Graphical interface based on PyGame

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import logging

try:
    import pygame
except ImportError:
    pygame = None

try:
    import numpy
except ImportError:
    numpy = None

import plat
import config
import unicodepage 
import backend
import typeface
import scancode
import state

# Workaround for broken pygame.scrap on Mac
if pygame:
    if plat.system == 'OSX':
        import pygame_mac_scrap as scrap
    else:
        scrap = pygame.scrap

# Android-specific definitions
android = (plat.system == 'Android')
if android:
    numpy = None
    if pygame:
        import pygame_android


# default font family
font_families = ['unifont', 'univga', 'freedos']
fonts = {}

# screen aspect ratio x, y
aspect = (4, 3)

# composite palettes, see http://nerdlypleasures.blogspot.co.uk/2013_11_01_archive.html
composite_640 = {
    'cga_old': [
        (0x00, 0x00, 0x00),        (0x00, 0x71, 0x00),        (0x00, 0x3f, 0xff),        (0x00, 0xab, 0xff),
        (0xc3, 0x00, 0x67),        (0x73, 0x73, 0x73),        (0xe6, 0x39, 0xff),        (0x8c, 0xa8, 0xff),
        (0x53, 0x44, 0x00),        (0x00, 0xcd, 0x00),        (0x73, 0x73, 0x73),        (0x00, 0xfc, 0x7e),
        (0xff, 0x39, 0x00),        (0xe2, 0xca, 0x00),        (0xff, 0x7c, 0xf4),        (0xff, 0xff, 0xff)    ],
    'cga': [
        (0x00, 0x00, 0x00),        (0x00, 0x6a, 0x2c),        (0x00, 0x39, 0xff),        (0x00, 0x94, 0xff),        
        (0xca, 0x00, 0x2c),        (0x77, 0x77, 0x77),        (0xff, 0x31, 0xff),        (0xc0, 0x98, 0xff),
        (0x1a, 0x57, 0x00),        (0x00, 0xd6, 0x00),        (0x77, 0x77, 0x77),        (0x00, 0xf4, 0xb8),
        (0xff, 0x57, 0x00),        (0xb0, 0xdd, 0x00),        (0xff, 0x7c, 0xb8),        (0xff, 0xff, 0xff)    ],
    'tandy': [
        (0x00, 0x00, 0x00),        (0x7c, 0x30, 0x00),        (0x00, 0x75, 0x00),        (0x00, 0xbe, 0x00),        
        (0x00, 0x47, 0xee),        (0x77, 0x77, 0x77),        (0x00, 0xbb, 0xc4),        (0x00, 0xfb, 0x3f),        
        (0xb2, 0x0f, 0x9d),        (0xff, 0x1e, 0x0f),        (0x77, 0x77, 0x77),        (0xff, 0xb8, 0x00),        
        (0xb2, 0x44, 0xff),        (0xff, 0x78, 0xff),        (0x4b, 0xba, 0xff),        (0xff, 0xff, 0xff)    ],      
    'pcjr': [
        (0x00, 0x00, 0x00),
        (0x98, 0x20, 0xcb),        (0x9f, 0x1c, 0x00),        (0xff, 0x11, 0x71),        (0x00, 0x76, 0x00),
        (0x77, 0x77, 0x77),        (0x5b, 0xaa, 0x00),        (0xff, 0xa5, 0x00),        (0x00, 0x4e, 0xcb),
        (0x74, 0x53, 0xff),        (0x77, 0x77, 0x77),        (0xff, 0x79, 0xff),        (0x00, 0xc8, 0x71),
        (0x00, 0xcc, 0xff),        (0x00, 0xfa, 0x00),        (0xff, 0xff, 0xff) ]        }
                    
composite_artifacts = False
composite_monitor = False
mode_has_artifacts = False
mono_monitor = False
    
# working palette - attribute index in blue channel
workpalette = [(0, 0, b * 16 + f) for b in range(16) for f in range(16)]
# display palettes for blink states 0, 1
gamepalette = [None, None]
# text attributes supported
mode_has_blink = True
mode_has_underline = False

# border attribute
border_attr = 0
# border widh in pixels
border_width = 5
# percentage of the screen to leave unused for indow decorations etc.
display_slack = 10
# screen width and height in pixels
display_size = (640, 480)

fullscreen = False
smooth = False
# ignore ALT+F4 (and consequently window X button)
noquit = False

# letter shapes
glyphs = []
font = None
# the current attribute of the stored sbcs glyphs
current_attr = None
current_attr_context = None

# cursor shape
cursor = None
# screen & updating 
canvas = []
    
screen_changed = True
cycle = 0
last_cycle = 0
cycle_time = 120 
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

if pygame:
    # these are PC keyboard scancodes
    key_to_scan = {
        # top row
        pygame.K_ESCAPE: scancode.ESCAPE, pygame.K_1: scancode.N1, 
        pygame.K_2: scancode.N2, pygame.K_3: scancode.N3, 
        pygame.K_4: scancode.N4, pygame.K_5: scancode.N5,
        pygame.K_6: scancode.N6, pygame.K_7: scancode.N7, 
        pygame.K_8: scancode.N8, pygame.K_9: scancode.N9,
        pygame.K_0: scancode.N0, pygame.K_MINUS: scancode.MINUS,
        pygame.K_EQUALS: scancode.EQUALS, 
        pygame.K_BACKSPACE: scancode.BACKSPACE,
        # row 1
        pygame.K_TAB: scancode.TAB, pygame.K_q: scancode.q, 
        pygame.K_w: scancode.w, pygame.K_e: scancode.e, pygame.K_r: scancode.r, 
        pygame.K_t: scancode.t, pygame.K_y: scancode.y, pygame.K_u: scancode.u,
        pygame.K_i: scancode.i, pygame.K_o: scancode.o, pygame.K_p: scancode.p, 
        pygame.K_LEFTBRACKET: scancode.LEFTBRACKET, 
        pygame.K_RIGHTBRACKET: scancode.RIGHTBRACKET, 
        pygame.K_RETURN: scancode.RETURN, pygame.K_KP_ENTER: scancode.RETURN,
        # row 2
        pygame.K_RCTRL: scancode.CTRL, pygame.K_LCTRL: scancode.CTRL, 
        pygame.K_a: scancode.a, pygame.K_s: scancode.s, pygame.K_d: scancode.d,
        pygame.K_f: scancode.f, pygame.K_g: scancode.g, pygame.K_h: scancode.h, 
        pygame.K_j: scancode.j, pygame.K_k: scancode.k, pygame.K_l: scancode.l, 
        pygame.K_SEMICOLON: scancode.SEMICOLON, pygame.K_QUOTE: scancode.QUOTE,
        pygame.K_BACKQUOTE: scancode.BACKQUOTE,
        # row 3        
        pygame.K_LSHIFT: scancode.LSHIFT, 
        pygame.K_BACKSLASH: scancode.BACKSLASH,
        pygame.K_z: scancode.z, pygame.K_x: scancode.x, pygame.K_c: scancode.c,
        pygame.K_v: scancode.v, pygame.K_b: scancode.b, pygame.K_n: scancode.n,
        pygame.K_m: scancode.m, pygame.K_COMMA: scancode.COMMA, 
        pygame.K_PERIOD: scancode.PERIOD, pygame.K_SLASH: scancode.SLASH,
        pygame.K_RSHIFT: scancode.RSHIFT, pygame.K_PRINT: scancode.PRINT,
        pygame.K_SYSREQ: scancode.SYSREQ,
        pygame.K_RALT: scancode.ALT, pygame.K_LALT: scancode.ALT, 
        #pygame.K_MODE: scancode.ALT,    # ALT GR sends MODE
        pygame.K_SPACE: scancode.SPACE, pygame.K_CAPSLOCK: scancode.CAPSLOCK,
        # function key row    
        pygame.K_F1: scancode.F1, pygame.K_F2: scancode.F2, 
        pygame.K_F3: scancode.F3, pygame.K_F4: scancode.F4,
        pygame.K_F5: scancode.F5, pygame.K_F6: scancode.F6,
        pygame.K_F7: scancode.F7, pygame.K_F8: scancode.F8,
        pygame.K_F9: scancode.F9, pygame.K_F10: scancode.F10,
        # top middle
        pygame.K_NUMLOCK: scancode.NUMLOCK, 
        pygame.K_SCROLLOCK: scancode.SCROLLOCK,
        # keypad
        pygame.K_KP7: scancode.KP7, pygame.K_HOME: scancode.HOME,
        pygame.K_KP8: scancode.KP8, pygame.K_UP: scancode.UP,        
        pygame.K_KP9: scancode.KP9, pygame.K_PAGEUP: scancode.PAGEUP,
        pygame.K_KP_MINUS: scancode.KPMINUS,
        pygame.K_KP4: scancode.KP4, pygame.K_LEFT: scancode.LEFT,
        pygame.K_KP5: scancode.KP5,
        pygame.K_KP6: scancode.KP6, pygame.K_RIGHT: scancode.RIGHT,
        pygame.K_KP_PLUS: scancode.KPPLUS,
        pygame.K_KP1: scancode.KP1, pygame.K_END: scancode.END,
        pygame.K_KP2: scancode.KP2, pygame.K_DOWN: scancode.DOWN,
        pygame.K_KP3: scancode.KP3, pygame.K_PAGEDOWN: scancode.PAGEDOWN,
        pygame.K_KP0: scancode.KP0, pygame.K_INSERT: scancode.INSERT,
        # keypad dot, times, div, enter ?
        # various
        pygame.K_DELETE: scancode.DELETE, 
        pygame.K_PAUSE: scancode.BREAK,
        pygame.K_BREAK: scancode.BREAK,
    }
    
# cursor is visible
cursor_visible = True

# mouse button functions
mousebutton_copy = 1
mousebutton_paste = 2
mousebutton_pen = 3

###############################################################################
    
def prepare():
    """ Initialise video_pygame module. """
    global fullscreen, smooth, noquit, force_display_size
    global composite_monitor, heights_needed
    global composite_640_palette, border_width
    global mousebutton_copy, mousebutton_paste, mousebutton_pen
    global mono_monitor, font_families, aspect, force_square_pixel
    global caption
    # display dimensions
    force_display_size = config.options['dimensions']
    aspect = config.options['aspect'] or aspect
    border_width = config.options['border']
    force_square_pixel = config.options['blocky']
    fullscreen = config.options['fullscreen']
    smooth = not config.options['blocky']
    # don't catch Alt+F4    
    noquit = config.options['nokill']
    # monitor choice
    mono_monitor =  config.options['monitor'] == 'mono'
    # if no composite palette available for this card, ignore.
    composite_monitor = (config.options['monitor'] == 'composite' and
                         config.options['video'] in composite_640)
    if composite_monitor:
            composite_640_palette = composite_640[config.options['video']]
    # keyboard setting based on video card...
    if config.options['video'] == 'tandy':
        # enable tandy F11, F12
        key_to_scan[pygame.K_F11] = scancode.F11
        key_to_scan[pygame.K_F12] = scancode.F12
    # fonts
    if config.options['video'] in ('cga', 'cga_old', 'tandy', 'pcjr'):
        heights_needed = (8, )
    elif config.options['video'] == 'mda':
        heights_needed = (14, )
    elif config.options['video'] == 'ega':
        heights_needed = (14, 8)
    else:
        heights_needed = (16, 14, 8)
    if config.options['font']:
        font_families = config.options['font']
    # mouse setups
    if config.options['mouse']:
        mousebutton_copy = -1
        mousebutton_paste = -1
        mousebutton_pen = -1
        for i, s in enumerate(config.options['mouse']):    
            if s == 'copy':
                mousebutton_copy = i+1
            elif s == 'paste':
                mousebutton_paste = i+1
            elif s == 'pen':
                mousebutton_pen = i+1
    # window caption/title
    caption = config.options['caption'] or 'PC-BASIC 3.23'
    
###############################################################################
# state saving and loading

# picklable store for surfaces
display_strings = ([], [])
display_strings_loaded = False

class PygameDisplayState(state.DisplayState):
    """ Display state saving and restoring. """
    
    def pickle(self):
        """ Convert display state to string. """
        self.display_strings = ([], [])
        for s in canvas:    
            self.display_strings[0].append(pygame.image.tostring(s, 'P'))
        
    def unpickle(self):
        """ Convert string to display state. """
        global display_strings, display_strings_loaded
        display_strings_loaded = True
        display_strings = self.display_strings
        del self.display_strings


def load_state():        
    """ Restore display state from file. """
    global screen_changed
    if display_strings_loaded:
        try:
            for i in range(len(canvas)):    
                canvas[i] = pygame.image.fromstring(display_strings[0][i], size, 'P')
                canvas[i].set_palette(workpalette)
            screen_changed = True    
        except (IndexError, ValueError):
            # couldn't load the state correctly; most likely a text screen saved from -t. just redraw what's unpickled.
            # this also happens if the screen resolution has changed 
            state.console_state.screen.redraw_text_screen()
    else:
        state.console_state.screen.redraw_text_screen()
        
####################################
# initialisation

def init():
    """ Initialise pygame interface. """
    global joysticks, physical_size, display_size
    global text_mode
    # set state objects to whatever is now in state (may have been unpickled)
    if not pygame:
        logging.warning('PyGame module not found. Failed to initialise graphical interface.')
        return False     
    pygame.init()
    # exclude some backend drivers as they give unusable results
    if pygame.display.get_driver() == 'caca':
        pygame.display.quit()
        logging.warning('Refusing to use libcaca. Failed to initialise graphical interface.')
        return False
    # get physical screen dimensions (needs to be called before set_mode)
    display_info = pygame.display.Info()
    physical_size = display_info.current_w, display_info.current_h
    # draw the icon
    pygame.display.set_icon(build_icon())
    # determine initial display size
    display_size = find_display_size(640, 480, border_width)   
    # first set the screen non-resizeable, to trick things like maximus into not full-screening
    # I hate it when applications do this ;)
    if not fullscreen:
        pygame.display.set_mode(display_size, 0)
    resize_display(*display_size, initial=True)
    pygame.display.set_caption(caption)
    pygame.key.set_repeat(500, 24)
    # load an all-black 16-colour game palette to get started
    update_palette([(0,0,0)]*16, None)
    if android:
        pygame_android.init()
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
    for j in joysticks:
        j.init()
    # if a joystick is present, its axes report 128 for mid, not 0
    for joy in range(len(joysticks)):
        for axis in (0, 1):
            backend.stick_moved(joy, axis, 128)
    if not load_fonts(heights_needed):
        return False
    text_mode = True    
    state.display = PygameDisplayState()
    return True

def load_fonts(heights_needed):
    """ Load font typefaces. """
    for height in heights_needed:
        if height in fonts:
            # already force loaded
            continue
        # load a Unifont .hex font and take the codepage subset
        fonts[height] = typeface.load(font_families, height, 
                                      unicodepage.cp_to_utf8)
        if height == 8:
            # also link as 9-pixel font for tandy
            fonts[9] = fonts[8]                              
        # fix missing code points font based on 16-line font
        if 16 not in fonts:
            # if available, load the 16-pixel font unrequested
            font_16 = typeface.load(font_families, 16, 
                                          unicodepage.cp_to_utf8, nowarn=True)
            if font_16:
                fonts[16] = font_16 
        if 16 in fonts and fonts[16]:
            typeface.fixfont(height, fonts[height], 
                             unicodepage.cp_to_utf8, fonts[16])
    if 16 in heights_needed and not fonts[16]:
        logging.error('No 16-pixel font specified')
        return False
    return True    
        
def supports_graphics_mode(mode_info):
    """ Return whether we support a given graphics mode. """
    # unpack mode info struct
    font_height = mode_info.font_height
    if not font_height in fonts:
        return False
    return True

def init_screen_mode(mode_info):
    """ Initialise a given text or graphics mode. """
    global glyphs, cursor
    global screen_changed, canvas
    global font, under_cursor, size, text_mode
    global font_height
    global clipboard, num_pages, bitsperpixel, font_width
    global mode_has_artifacts, cursor_fixed_attr, mode_has_blink
    global mode_has_underline
    global get_put_store
    if not fonts[mode_info.font_height]:
        return False
    text_mode = mode_info.is_text_mode
    # unpack mode info struct
    font_height = mode_info.font_height
    font_width = mode_info.font_width
    num_pages = mode_info.num_pages
    mode_has_blink = mode_info.has_blink
    mode_has_underline = mode_info.has_underline
    if not text_mode:
        bitsperpixel = mode_info.bitsperpixel
        mode_has_artifacts = mode_info.supports_artifacts
        cursor_fixed_attr = mode_info.cursor_index
    # logical size    
    size = (mode_info.pixel_width, mode_info.pixel_height)    
    font = fonts[font_height]
    glyphs = [build_glyph(chr(c), font, font_width, font_height) 
              for c in range(256)]
    # initialise glyph colour
    set_attr(mode_info.attr, force_rebuild=True)
    resize_display(*find_display_size(size[0], size[1], border_width))
    # set standard cursor
    build_cursor(font_width, font_height, 0, font_height)
    # whole screen (blink on & off)
    canvas = [ pygame.Surface(size, depth=8) for _ in range(num_pages)]
    for i in range(num_pages):
        canvas[i].set_palette(workpalette)
    # remove cached sprites
    get_put_store = {}    
    # initialise clipboard
    clipboard = Clipboard(mode_info.width, mode_info.height)
    screen_changed = True
    return True

def find_display_size(canvas_x, canvas_y, border_width): 
    """ Determine the optimal size for the display. """
    if force_display_size:
        return force_display_size
    if not force_square_pixel:
        # this assumes actual display aspect ratio is wider than 4:3
        # scale y to fit screen
        canvas_y = (1 - display_slack/100.) * physical_size[1] // int(1 + border_width/100.)
        # scale x to match aspect ratio
        canvas_x = (canvas_y * aspect[0]) / aspect[1]
        # add back border
        pixel_x = int(canvas_x * (1 + border_width/100.))
        pixel_y = int(canvas_y * (1 + border_width/100.))
        return pixel_x, pixel_y
    else:
        pixel_x = int(canvas_x * (1 + border_width/100.))
        pixel_y = int(canvas_y * (1 + border_width/100.))
        # leave 5% of the screen either direction unused
        # to account for task bars, window decorations, etc.    
        xmult = max(1, int((100.-display_slack) * physical_size[0] / (100.*pixel_x)))
        ymult = max(1, int((100.-display_slack) * physical_size[1] / (100.*pixel_y)))
        # find the multipliers mx <= xmult, my <= ymult
        # such that mx * pixel_x / my * pixel_y 
        # is multiplicaively closest to aspect[0] / aspect[1] 
        target = aspect[0]/(1.0*aspect[1])
        current = xmult*canvas_x / (1.0*ymult*canvas_y) 
        # find the absolute multiplicative distance (always > 1)
        best = max(current, target) / min(current, target)
        apx = xmult, ymult
        for mx in range(1, xmult+1):
            my = min(ymult, 
                     int(round(mx*canvas_x*aspect[1] / (1.0*canvas_y*aspect[0]))))
            current = mx*pixel_x / (1.0*my*pixel_y)         
            dist = max(current, target) / min(current, target)
            # prefer larger multipliers if distance is equal
            if dist <= best:
                best = dist
                apx = mx, my
        return apx[0] * pixel_x, apx[1] * pixel_y
    
def resize_display(width, height, initial=False): 
    """ Change the display size. """
    global display, screen_changed
    global fullscreen, smooth
    display_info = pygame.display.Info()
    flags = pygame.RESIZABLE
    if fullscreen or (width, height) == physical_size:
        fullscreen = True
        flags |= pygame.FULLSCREEN | pygame.NOFRAME
        if (not initial and not text_mode):
            width, height = display_size 
        # scale suggested dimensions to largest integer times pixel size that fits
        scale = min( physical_size[0]//width, physical_size[1]//height )
        width, height = width * scale, height * scale
    if (width, height) == (display_info.current_w, display_info.current_h) and not initial:
        return
    display = pygame.display.set_mode((width, height), flags)
    if initial and smooth and display.get_bitsize() < 24:
        logging.warning("Smooth scaling not available on this display (depth %d < 24)", display.get_bitsize())
        smooth = False
    # load display if requested    
    screen_changed = True    
    
def build_icon():
    """ Build the ok icon. """
    icon = pygame.Surface((17, 17), depth=8)
    icon.fill(255)
    icon.fill(254, (1, 8, 8, 8))
    # hardcoded O and k from freedos cga font
    okfont = { ord('O'): '\x00\x7C\xC6\xC6\xC6\xC6\xC6\x7C', ord('k'): '\x00\xE0\x60\x66\x6C\x78\x6C\xE6' }
    O = build_glyph(ord('O'), okfont, 8, 8)
    k = build_glyph(ord('k'), okfont, 8, 8)
    icon.blit(O, (1, 0, 8, 8))
    icon.blit(k, (9, 0, 8, 8))
    icon.set_palette_at(255, (0, 0, 0))
    icon.set_palette_at(254, (0xff, 0xff, 0xff))
    pygame.transform.scale2x(icon)
    pygame.transform.scale2x(icon)
    return icon

def close():
    """ Close the pygame interface. """
    if android:
        pygame_android.close()
    pygame.joystick.quit()
    pygame.display.quit()    

def get_palette_index(cattr):
    """ Find the index in the game palette for this attribute. """
    # NOTE: we're using mode_has_underline as a proxy to "it's an MDA" here
    # we're also counting on graphics modes not using colours beyond point 16
    # where blink is for text mode. 
    if not mode_has_underline:
        color = (0, 0, cattr)
        bg = (0, 0, (cattr>>4) & 7)
    else:
        # MDA palette, see http://www.seasip.info/VintagePC/mda.html
        # don't try to change this with PALETTE, it won't work correctly
        if cattr in (0x00, 0x08, 0x80, 0x88, 0x70):
            color = (0, 0, 0)
        elif cattr == 0x78:
            # dim foreground on bright background
            color = (0, 0, 1)    
        elif cattr == 0xf8:
            # dim foreground on bright background, blinking
            color = (0, 0, 0xa2)    
        elif cattr == 0xf0:
            # black on bright background, blinking
            color = (0, 0, 0xa0)    
        elif cattr % 8 == 0:
            color = (0, 0, (cattr&0x80) + 1)
        elif cattr < 0x80:    
            # most % 8 == 0 points aren't actually black; blink goes to black bg
            color = (0, 0, cattr)
        else:    
            # most % 8 == 0 points aren't actually black; blink goes to black bg
            color = (0, 0, 0x80 + cattr % 16)
        if cattr in (0x70, 0x78, 0xF0, 0xF8):
            # bright green background for these points
            bg = (0, 0, 15)    
        else:
            # background is almost always black
            bg = (0, 0, 0)
    return color, bg    

def update_palette(rgb_palette, rgb_palette1):
    """ Build the game palette. """
    global screen_changed, gamepalette
    basepalette0 = [pygame.Color(*c) for c in rgb_palette]
    if rgb_palette1:    
        basepalette1 = [pygame.Color(*c) for c in rgb_palette1]
    else:    
        basepalette1 = basepalette0
    while len(basepalette0) < 16:
        basepalette0.append(pygame.Color(0, 0, 0))
    while len(basepalette1) < 16:
        basepalette1.append(pygame.Color(0, 0, 0))
    # combining into all 256 attribute combinations for screen 0:   
    # NOTE: we're using mode_has_underline as a proxy to "it's an MDA" here
    if not mode_has_underline:
        gamepalette[0] = [basepalette0[f] for b in range(16) for f in range(16)]
        gamepalette[1] = ([basepalette1[f] for b in range(8) for f in range(16)] + 
                          [basepalette1[b] for b in range(8) for f in range(16)])
    else:
        # MDA has bright backgrounds
        gamepalette[0] = [basepalette0[f] for b in range(16) for f in range(16)]
        gamepalette[1] = ([basepalette1[f] for b in range(8) for f in range(16)] + 
                          [basepalette1[b+8] for b in range(8) for f in range(16)])
    screen_changed = True

def set_border(attr):
    """ Change the border attribute. """
    global border_attr, screen_changed
    border_attr = attr
    screen_changed = True
    
def set_colorburst(on, rgb_palette, rgb_palette1):
    """ Change the NTSC colorburst setting. """
    global composite_artifacts
    update_palette(rgb_palette, rgb_palette1)
    composite_artifacts = on and mode_has_artifacts and composite_monitor
    
def clear_rows(cattr, start, stop):
    """ Clear a range of screen rows. """
    global screen_changed
    _, bg = get_palette_index(cattr)
    scroll_area = pygame.Rect(0, (start-1)*font_height, 
                              size[0], (stop-start+1)*font_height) 
    canvas[apagenum].fill(bg, scroll_area)
    screen_changed = True
    
def set_page(vpage, apage):
    """ Set the visible and active page. """
    global vpagenum, apagenum, screen_changed
    vpagenum, apagenum = vpage, apage
    screen_changed = True

def copy_page(src, dst):
    """ Copy source to destination page. """
    global screen_changed
    canvas[dst].blit(canvas[src], (0,0))
    screen_changed = True
    
def update_cursor_visibility(cursor_on):
    """ Change visibility of cursor. """
    global screen_changed, cursor_visible
    cursor_visible = cursor_on
    screen_changed = True

def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
    """ Change attribute of cursor. """
    color = canvas[vpagenum].get_palette_at(attr).b
    cursor.set_palette_at(254, pygame.Color(0, color, color))

def scroll(from_line, scroll_height, attr):
    """ Scroll the screen up between from_line and scroll_height. """
    global screen_changed
    temp_scroll_area = pygame.Rect(
                    0, (from_line-1)*font_height,
                    size[0], 
                    (scroll_height-from_line+1) * font_height)
    # scroll
    canvas[apagenum].set_clip(temp_scroll_area)
    canvas[apagenum].scroll(0, -font_height)
    # empty new line
    blank = pygame.Surface( (size[0], font_height) , depth=8)
    _, bg = get_palette_index(attr)
    blank.set_palette(workpalette)
    blank.fill(bg)
    canvas[apagenum].blit(blank, (0, (scroll_height-1) * font_height))
    canvas[apagenum].set_clip(None)
    screen_changed = True
   
def scroll_down(from_line, scroll_height, attr):
    """ Scroll the screen down between from_line and scroll_height. """
    global screen_changed
    temp_scroll_area = pygame.Rect(0, (from_line-1) * font_height, size[0], 
                                   (scroll_height-from_line+1) * font_height)
    canvas[apagenum].set_clip(temp_scroll_area)
    canvas[apagenum].scroll(0, font_height)
    # empty new line
    blank = pygame.Surface( (size[0], font_height), depth=8 )
    _, bg = get_palette_index(attr)
    blank.set_palette(workpalette)
    blank.fill(bg)
    canvas[apagenum].blit(blank, (0, (from_line-1) * font_height))
    canvas[apagenum].set_clip(None)
    screen_changed = True

def set_attr(cattr, force_rebuild=False):
    """ Set the current attribuite. """
    global current_attr, current_attr_context
    if (not force_rebuild and cattr == current_attr and apagenum == current_attr_context):
        return  
    color, bg = get_palette_index(cattr)    
    for glyph in glyphs:
        glyph.set_palette_at(255, bg)
        glyph.set_palette_at(254, color)
    current_attr = cattr    
    current_attr_context = apagenum

def putc_at(pagenum, row, col, c, for_keys=False):
    """ Put a single-byte character at a given position. """
    global screen_changed
    glyph = glyphs[ord(c)]
    blank = glyphs[0] # using \0 for blank (tyoeface.py guarantees it's empty)
    top_left = ((col-1) * font_width, (row-1) * font_height)
    canvas[pagenum].blit(glyph, top_left)
    if mode_has_underline and (current_attr % 8 == 1):
        color, _ = get_palette_index(current_attr)    
        for xx in range(font_width):
            canvas[pagenum].set_at(((col-1) * font_width + xx, 
                                       row*font_height - 1), color)
    screen_changed = True

def putwc_at(pagenum, row, col, c, d, for_keys=False):
    """ Put a double-byte character at a given position. """
    global screen_changed
    glyph = build_glyph(c+d, font, 2*font_width, font_height)
    color, bg = get_palette_index(current_attr)    
    glyph.set_palette_at(255, bg)
    glyph.set_palette_at(254, color)
    blank = pygame.Surface((2*font_width, font_height), depth=8)
    blank.fill(255)
    blank.set_palette_at(255, bg)
    top_left = ((col-1) * font_width, (row-1) * font_height)
    canvas[pagenum].blit(glyph, top_left)
    screen_changed = True
    
# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in 
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
carry_col_9 = [chr(c) for c in range(0xb0, 0xdf+1)]
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
carry_row_9 = [chr(c) for c in range(0xb0, 0xdf+1)]

def build_glyph(c, font_face, req_width, req_height):
    """ Build a sprite for the given character glyph. """
    color, bg = 254, 255
    try:
        face = font_face[c]
    except KeyError:
        logging.debug('Byte sequence %s not represented in codepage, replace with blank glyph.', repr(c))
        # codepoint 0 must be blank by our definitions
        face = font_face['\0']
        c = '\0'
    code_height = 8 if req_height == 9 else req_height    
    glyph_width, glyph_height = 8*len(face)//code_height, req_height
    if req_width <= glyph_width + 2:
        # allow for 9-pixel widths (18-pixel dwidths) without scaling
        glyph_width = req_width
    elif glyph_width < req_width:
        u = unicodepage.cp_to_utf8[c]
        logging.debug('Incorrect glyph width for %s [%s, code point %x].', repr(c), u, ord(u.decode('utf-8')))
    glyph = pygame.Surface((glyph_width, glyph_height), depth=8)
    glyph.fill(bg)
    for yy in range(code_height):
        for half in range(glyph_width//8):    
            line = ord(face[yy*(glyph_width//8)+half])
            for xx in range(8):
                if (line >> (7-xx)) & 1 == 1:
                    glyph.set_at((half*8 + xx, yy), color)
        # MDA/VGA 9-bit characters        
        if c in carry_col_9 and glyph_width == 9:
            if line & 1 == 1:
                glyph.set_at((8, yy), color)
    # tandy 9-bit high characters            
    if c in carry_row_9 and glyph_height == 9:
        line = ord(face[7*(glyph_width//8)])
        for xx in range(8):
            if (line >> (7-xx)) & 1 == 1:
                glyph.set_at((xx, 8), color)
    if req_width > glyph_width:
        glyph = pygame.transform.scale(glyph, (req_width, req_height))    
    return glyph        
        
def build_cursor(width, height, from_line, to_line):
    """ Build a sprite for the cursor. """
    global screen_changed, cursor, under_cursor
    global cursor_width, cursor_from, cursor_to
    cursor_width, cursor_from, cursor_to = width, from_line, to_line
    under_cursor = pygame.Surface((width, height), depth=8)
    under_cursor.set_palette(workpalette)
    cursor = pygame.Surface((width, height), depth=8)
    color, bg = 254, 255
    cursor.set_colorkey(bg)
    cursor.fill(bg)
    for yy in range(height):
        for xx in range(width):
            if yy < from_line or yy > to_line:
                pass
            else:
                cursor.set_at((xx, yy), color)
    screen_changed = True            

###############################################################################
# event loop

def check_screen():
    """ Check screen and blink events; update screen if necessary. """
    global cycle, last_cycle
    global screen_changed
    blink_state = 0
    if mode_has_blink:
        blink_state = 0 if cycle < blink_cycles * 2 else 1
        if cycle%blink_cycles == 0:    
            screen_changed = True
    if cursor_visible and ((cursor_row != last_row) or (cursor_col != last_col)):
        screen_changed = True
    tock = pygame.time.get_ticks() 
    if (tock - last_cycle) >= (cycle_time/blink_cycles):
        last_cycle = tock
        cycle += 1
        if cycle == blink_cycles*4: 
            cycle = 0
        if screen_changed:
            do_flip(blink_state)
            screen_changed = False
    
def draw_cursor(screen):
    """ Draw the cursor on the screen. """
    global under_top_left, last_row, last_col
    if not cursor_visible or vpagenum != apagenum:
        return
    # copy screen under cursor
    under_top_left = (  (cursor_col-1) * font_width,
                        (cursor_row-1) * font_height)
    under_char_area = pygame.Rect(
            (cursor_col-1) * font_width, 
            (cursor_row-1) * font_height, 
            (cursor_col-1) * font_width + cursor_width,
            cursor_row * font_height)
    under_cursor.blit(screen, (0,0), area=under_char_area)
    if text_mode:
        # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
        if (cycle/blink_cycles==1 or cycle/blink_cycles==3): 
            screen.blit(cursor, (  (cursor_col-1) * font_width,
                                    (cursor_row-1) * font_height) )
    else:
        if cursor_fixed_attr != None:
            index = cursor_fixed_attr
        else:
            index = current_attr & 0xf
        if numpy:
            # reference the destination area
            dest_array = pygame.surfarray.pixels2d(screen.subsurface(pygame.Rect(
                                (cursor_col-1) * font_width, 
                                (cursor_row-1) * font_height + cursor_from, 
                                cursor_width, 
                                cursor_to - cursor_from + 1))) 
            dest_array ^= index
        else:
            # no surfarray if no numpy    
            for x in range(     (cursor_col-1) * font_width, 
                                  (cursor_col-1) * font_width + cursor_width):
                for y in range((cursor_row-1) * font_height + cursor_from, 
                                (cursor_row-1) * font_height + cursor_to + 1):
                    pixel = get_pixel(x, y, apagenum)
                    screen.set_at((x,y), pixel^index)
    last_row = cursor_row
    last_col = cursor_col

def apply_composite_artifacts(screen, pixels=4):
    """ Process the canvas to apply composite colour artifacts. """
    src_array = pygame.surfarray.array2d(screen)
    width, height = src_array.shape
    s = [None]*pixels
    for p in range(pixels):
        s[p] = src_array[p:width:pixels]&(4//pixels)
    for p in range(1,pixels):
        s[0] = s[0]*2 + s[p]
    return pygame.surfarray.make_surface(numpy.repeat(s[0], pixels, axis=0))
    
def do_flip(blink_state):
    """ Draw the canvas to the screen. """
    # create the screen that will be stretched onto the display
    border_x = int(size[0] * border_width / 200.)
    border_y = int(size[1] * border_width / 200.)
    screen = pygame.Surface((size[0] + 2*border_x, size[1] + 2*border_y),
                             0, canvas[vpagenum])
    screen.set_palette(workpalette)
    # border colour
    border_colour = pygame.Color(0, border_attr, border_attr)
    screen.fill(border_colour)
    screen.blit(canvas[vpagenum], (border_x, border_y))
    # subsurface referencing the canvas area
    workscreen = screen.subsurface((border_x, border_y, size[0], size[1]))
    draw_cursor(workscreen)
    if clipboard.active():
        clipboard.create_feedback(workscreen)
    # android: shift screen if keyboard is on so that cursor remains visible
    if android:
        pygame_android.shift_screen(screen, border_x, border_y, size, cursor_row, font_height)
    if composite_artifacts and numpy:
        screen = apply_composite_artifacts(screen, 4//bitsperpixel)
        screen.set_palette(composite_640_palette)    
    else:
        screen.set_palette(gamepalette[blink_state])
    if smooth:
        pygame.transform.smoothscale(screen.convert(display), display.get_size(), display)
    else:
        pygame.transform.scale(screen.convert(display), display.get_size(), display)  
    pygame.display.flip()

###############################################################################
# event queue

def pause_key():
    """ Wait for key in pause state. """
    # pause key press waits for any key down. 
    # continues to process screen events (blink) but not user events.
    while not check_events(pause=True):
        # continue playing background music
        backend.audio.check_sound()
        idle()
        
def idle():
    """ Video idle process. """
    pygame.time.wait(cycle_time/blink_cycles/8)  

def check_events(pause=False):
    """ Handle screen and interface events. """
    global screen_changed, fullscreen
    # handle Android pause/resume
    if android and pygame_android.check_events():
        # force immediate redraw of screen
        do_flip(0)
        # force redraw on next tick  
        # we seem to have to redraw twice to see anything
        screen_changed = True
    # check and handle pygame events    
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if not pause:
                handle_key_down(event)
            else:
                return True    
        if event.type == pygame.KEYUP:
            if not pause:
                handle_key_up(event)
        elif event.type == pygame.MOUSEBUTTONDOWN: 
            if event.button == mousebutton_copy:
                # LEFT button: copy
                pos = normalise_pos(*event.pos)
                clipboard.start(1 + pos[1] // font_height, 
                            1 + (pos[0]+font_width//2) // font_width)
            elif event.button == mousebutton_paste:
                # MIDDLE button: paste
                clipboard.paste(mouse=True)    
            elif event.button == mousebutton_pen:
                # right mouse button is a pen press
                backend.pen_down(*normalise_pos(*event.pos))
        elif event.type == pygame.MOUSEBUTTONUP: 
            backend.pen_up()
            if event.button == mousebutton_copy:
                clipboard.copy(mouse=True)
                clipboard.stop()
        elif event.type == pygame.MOUSEMOTION: 
            pos = normalise_pos(*event.pos) 
            backend.pen_moved(*pos)
            if clipboard.active():
                clipboard.move(1 + pos[1] // font_height,
                           1 + (pos[0]+font_width//2) // font_width)
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.joy < 2 and event.button < 2:
                backend.stick_down(event.joy, event.button)
        elif event.type == pygame.JOYBUTTONUP:
            if event.joy < 2 and event.button < 2:
                backend.stick_up(event.joy, event.button)
        elif event.type == pygame.JOYAXISMOTION:
            if event.joy < 2 and event.axis < 2:
                backend.stick_moved(event.joy, event.axis, 
                                    int(event.value*127 + 128))
        elif event.type == pygame.VIDEORESIZE:
            fullscreen = False
            resize_display(event.w, event.h)
        elif event.type == pygame.QUIT:
            if noquit:
                pygame.display.set_caption('%s - to exit type <CTRL+BREAK> <ESC> SYSTEM' % caption)
            else:
                backend.insert_special_key('quit')
    check_screen()
    return False

def handle_key_down(e):
    """ Handle key-down event. """
    global screen_changed
    c = ''
    mods = pygame.key.get_mods()
    if ((e.key == pygame.K_NUMLOCK and mods & pygame.KMOD_CTRL) or
            (e.key in (pygame.K_PAUSE, pygame.K_BREAK) and 
             not mods & pygame.KMOD_CTRL)):
        # pause until keypress
        pause_key()    
    elif e.key == pygame.K_MENU and android:
        # Android: toggle keyboard on menu key
        pygame_android.toggle_keyboard()
        screen_changed = True
    elif e.key == pygame.K_LSUPER: # logo key, doesn't set a modifier
        clipboard.start()
    elif clipboard.active():
        clipboard.handle_key(e)
    else:
        if not android:
            # android unicode values are wrong, use the scancode only
            utf8 = e.unicode.encode('utf-8')
            try:
                c = unicodepage.from_utf8(utf8)
            except KeyError:
                # no codepage encoding found, ignore unless ascii
                # this happens for control codes like '\r' since
                # unicodepage defines the special graphic characters for those.
                #if len(utf8) == 1 and ord(utf8) < 128:
                #    c = utf8
                # don't do this, let control codes be handled by scancode
                # e.g. ctrl+enter should be '\n' but has e.unicode=='\r'
                pass 
        # double NUL characters, as single NUL signals scan code
        if len(c) == 1 and ord(c) == 0:
            c = '\0\0'
        # current key pressed; modifiers handled by backend interface
        try:
            scan = key_to_scan[e.key]
        except KeyError:
            scan = None    
            if android:
                # android hacks - send keystroke sequences 
                if e.key == pygame.K_ASTERISK:
                    backend.key_down(scancode.RSHIFT, '')            
                    backend.key_down(scancode.N8, '*')            
                    backend.key_up(scancode.RSHIFT)            
                elif e.key == pygame.K_AT:
                    backend.key_down(scancode.RSHIFT, '')            
                    backend.key_down(scancode.N2, '@')            
                    backend.key_up(scancode.RSHIFT)            
        # insert into keyboard queue
        backend.key_down(scan, c) 

def handle_key_up(e):
    """ Handle key-up event. """
    if e.key == pygame.K_LSUPER: # logo key, doesn't set a modifier
        clipboard.stop()
    # last key released gets remembered
    try:
        backend.key_up(key_to_scan[e.key])
    except KeyError:
        pass

def normalise_pos(x, y):
    """ Convert physical to logical coordinates within screen bounds. """
    border_x = int(size[0] * border_width / 200.)
    border_y = int(size[1] * border_width / 200.)
    display_info = pygame.display.Info()
    xscale = display_info.current_w / (1.*(size[0]+2*border_x)) 
    yscale = display_info.current_h / (1.*(size[1]+2*border_y))
    xpos = min(size[0]-1, max(0, int(x//xscale - border_x)))
    ypos = min(size[1]-1, max(0, int(y//yscale - border_y))) 
    return xpos, ypos
    
###############################################################################
# clipboard handling

class Clipboard(object):
    """ Clipboard handling """    
    
    # text type we look for in the clipboard
    text = ('UTF8_STRING', 'text/plain;charset=utf-8', 'text/plain',
            'TEXT', 'STRING')
        
    def __init__(self, width, height):
        """ Initialise pygame scrapboard. """
        self.logo_pressed = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.width = width
        self.height = height
        try:
            scrap.init()
            scrap.set_mode(pygame.SCRAP_CLIPBOARD)
            self.ok = True
        except NotImplementedError:
            logging.warning('PyGame.Scrap module not found. Clipboard functions not available.')    
            self.ok = False

    def available(self):
        if not self.ok:
            return False
        """ True if pasteable text is available on clipboard. """
        types = scrap.get_types()
        for t in types:
            if t in self.text:
                return True
        return False        

    def active(self):
        if not self.ok:
            return False
        """ True if clipboard mode is active. """
        return self.logo_pressed
        
    def start(self, r=None, c=None):
        if not self.ok:
            return 
        """ Enter clipboard mode (Logo key pressed). """
        self.logo_pressed = True
        if r == None or c == None:
            self.select_start = [cursor_row, cursor_col]
            self.select_stop = [cursor_row, cursor_col]
        else:
            self.select_start = [r, c]
            self.select_stop = [r, c]
        self.selection_rect = []
        
    def stop(self):
        """ Leave clipboard mode (Logo key released). """
        global screen_changed
        if not self.ok:
            return 
        self.logo_pressed = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        screen_changed = True

    def copy(self, mouse=False):
        """ Copy screen characters from selection into clipboard. """
        if not self.ok:
            return 
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        full = state.console_state.screen.get_text(start[0], start[1], stop[0], stop[1]-1)
        if mouse:
            scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        try: 
            if plat.system == 'Windows':
                # on Windows, encode as utf-16 without FF FE byte order mark and null-terminate
                scrap.put('text/plain;charset=utf-8', full.decode('utf-8').encode('utf-16le') + '\0\0')
            else:    
                scrap.put(pygame.SCRAP_TEXT, full)
        except KeyError:
            logging.debug('Clipboard copy failed for clip %s', repr(full))    
        
    def paste(self, mouse=False):
        """ Paste from clipboard into keyboard buffer. """
        if not self.ok:
            return 
        if mouse:
            scrap.set_mode(pygame.SCRAP_SELECTION)
        else:
            scrap.set_mode(pygame.SCRAP_CLIPBOARD)
        us = None
        available = scrap.get_types()
        for text_type in self.text:
            if text_type not in available:
                continue
            us = scrap.get(text_type)
            if us:
                break            
        if plat.system == 'Windows':
            if text_type == 'text/plain;charset=utf-8':
                # it's lying, it's giving us UTF16 little-endian
                # ignore any bad UTF16 characters from outside
                us = us.decode('utf-16le', 'ignore')
            # null-terminated strings
            us = us[:us.find('\0')] 
            us = us.encode('utf-8')
        if not us:
            return
        # ignore any bad UTF8 characters from outside
        for u in us.decode('utf-8', 'ignore'):
            c = u.encode('utf-8')
            last = ''
            if c == '\n':
                if last != '\r':
                    backend.insert_chars('\r')
            else:
                try:
                    backend.insert_chars(unicodepage.from_utf8(c))
                except KeyError:
                    backend.insert_chars(c)
            last = c
                        
    def move(self, r, c):
        """ Move the head of the selection and update feedback. """
        global screen_changed
        self.select_stop = [r, c]
        start, stop = self.select_start, self.select_stop
        if stop[1] < 1: 
            stop[0] -= 1
            stop[1] = self.width+1
        if stop[1] > self.width+1:        
            stop[0] += 1
            stop[1] = 1
        if stop[0] > self.height:
            stop[:] = [self.height, self.width+1]
        if stop[0] < 1:
            stop[:] = [1, 1]            
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        rect_left = (start[1] - 1) * font_width
        rect_top = (start[0] - 1) * font_height
        rect_right = (stop[1] - 1) * font_width
        rect_bot = stop[0] * font_height
        if start[0] == stop[0]:
            # single row selection
            self.selection_rect = [pygame.Rect(rect_left, rect_top, 
                                    rect_right-rect_left, rect_bot-rect_top)]
        else:
            # multi-row selection
            self.selection_rect = [
              pygame.Rect(rect_left, rect_top, size[0]-rect_left, font_height),
              pygame.Rect(0, rect_top + font_height, 
                          size[0], rect_bot - rect_top - 2*font_height),
              pygame.Rect(0, rect_bot - font_height, 
                          rect_right, font_height)]
        screen_changed = True
    
    
    def handle_key(self, e):
        """ Handle logo+key clipboard commands. """
        global screen_changed
        if not self.ok or not self.logo_pressed:
            return
        if e.unicode.upper() ==  u'C':
            self.copy()
        elif e.unicode.upper() == u'V' and self.available():
            self.paste()
        elif e.unicode.upper() == u'A':
            # select all
            self.select_start = [1, 1]
            self.move(self.height, self.width+1)
        elif e.key == pygame.K_LEFT:
            # move selection head left
            self.move(self.select_stop[0], self.select_stop[1]-1)
        elif e.key == pygame.K_RIGHT:
            # move selection head right
            self.move(self.select_stop[0], self.select_stop[1]+1)
        elif e.key == pygame.K_UP:
            # move selection head up
            self.move(self.select_stop[0]-1, self.select_stop[1])
        elif e.key == pygame.K_DOWN:
            # move selection head down
            self.move(self.select_stop[0]+1, self.select_stop[1])

    def create_feedback(self, surface):
        """ Create visual feedback for selection onto a surface. """
        for r in self.selection_rect:
            work_area = surface.subsurface(r)
            orig = work_area.copy()
            # add 1 to the color as a highlight
            orig.fill(pygame.Color(0, 0, 1))
            work_area.blit(orig, (0, 0), special_flags=pygame.BLEND_ADD)
        
###############################################################################
# graphics backend interface
# low-level methods (pygame implementation)

def put_pixel(x, y, index, pagenum):
    """ Put a pixel on the screen; callback to empty character buffer. """
    global screen_changed
    canvas[pagenum].set_at((x,y), index)
    screen_changed = True

def get_pixel(x, y, pagenum):    
    """ Return the attribute a pixel on the screen. """
    return canvas[pagenum].get_at((x,y)).b

# graphics view area (pygame clip)

def remove_graph_clip():
    """ Un-apply the graphics clip. """
    canvas[apagenum].set_clip(None)

def apply_graph_clip(x0, y0, x1, y1):
    """ Apply the graphics clip. """
    canvas[apagenum].set_clip(pygame.Rect(x0, y0, x1-x0+1, y1-y0+1))

# fill functions

def fill_rect(x0, y0, x1, y1, index):
    """ Fill a rectangle in a solid attribute. """
    global screen_changed
    rect = pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)
    canvas[apagenum].fill(index, rect)
    screen_changed = True

def fill_interval(x0, x1, y, tile, solid):
    """ Fill a scanline interval in a tile pattern or solid attribute. """
    global screen_changed
    dx = x1 - x0 + 1
    h = len(tile)
    w = len(tile[0])
    if solid:
        canvas[apagenum].fill(tile[0][0], (x0, y, dx, 1))
    elif numpy:
        # fast method using numpy instead of loop
        ntile = numpy.roll(numpy.array(tile).astype(int)[y % h], int(-x0 % 8))
        bar = numpy.tile(ntile, (dx+w-1) / w)
        pygame.surfarray.pixels2d(canvas[apagenum])[x0:x1+1, y] = bar[:dx]
    else:
        # slow loop
        for x in range(x0, x1+1):
            canvas[apagenum].set_at((x,y), tile[y % h][x % 8])
    screen_changed = True

def put_interval(pagenum, x, y, colours):
    """ Write a list of attributes to a scanline interval. """
    global screen_changed
    if numpy:
        colours = numpy.array(colours).astype(int)
        pygame.surfarray.pixels2d(canvas[pagenum])[x:x+len(colours), y] = colours
    else:
        for i, index in enumerate(colours):
            canvas[pagenum].set_at((x+i, y), index)
    screen_changed = True

def put_interval_packed(pagenum, x, y, bytes, plane_mask):
    """ Write a list of attributes to a scanline interval. """
    global screen_changed
    inv_mask = 0xff ^ plane_mask
    if numpy:
        bits = (numpy.repeat(numpy.array(bytes).astype(int), 8) &
               numpy.tile(numpy.array([128, 64, 32, 16, 8, 4, 2, 1]), len(bytes))) != 0
        colours = numpy.multiply(numpy.array(bits).astype(int), plane_mask)
        pygame.surfarray.pixels2d(canvas[pagenum])[x:x+len(colours), y] &= inv_mask
        pygame.surfarray.pixels2d(canvas[pagenum])[x:x+len(colours), y] |= colours
    else:
        bits = []
        for byte in bytes:
            for shift in range(8):
                bits.append((byte >> (7-shift)) & 1)
        for i, index in enumerate(bits):
            c = canvas[pagenum].get_at((x+i, y)).b & inv_mask
            canvas[pagenum].set_at((x+i, y), c | index * plane_mask)
    screen_changed = True
    
def get_until(x0, x1, y, c):
    """ Get the attribute values of a scanline interval. """
    if x0 == x1:
        return []
    if numpy:     
        toright = x1 > x0
        if not toright:
            x0, x1 = x1+1, x0+1
        arr = pygame.surfarray.array2d(canvas[apagenum].subsurface((x0, y, x1-x0, 1)))
        found = numpy.where(arr == c)
        if len(found[0]) > 0:
            if toright:
                arr = arr[:found[0][0]]
            else:
                arr = arr[found[0][-1]+1:]    
        return list(arr.flatten())
    else:
        interval = []
        for x in range(x0, x1):
            index = canvas[apagenum].get_at((x,y)).b
            if index == c:
                break
            interval.append(index)
        return interval    

###############################################################################
# Numpy-optimised sprite operations (PUT and GET)
    
def numpy_set(left, right):
    """ Fast PUT: PSET operation. """
    left[:] = right

def numpy_not(left, right):
    """ Fast PUT: PRESET operation. """
    left[:] = right
    left ^= (1<<bitsperpixel) - 1

def numpy_iand(left, right):
    """ Fast PUT: AND operation. """
    left &= right

def numpy_ior(left, right):
    """ Fast PUT: OR operation. """
    left |= right

def numpy_ixor(left, right):
    """ Fast PUT: XOR operation. """
    left ^= right
        
fast_operations = {
    '\xC6': numpy_set, #PSET
    '\xC7': numpy_not, #PRESET
    '\xEE': numpy_iand,
    '\xEF': numpy_ior,
    '\xF0': numpy_ixor,
    }

def fast_get(x0, y0, x1, y1, varname, version):
    """ Store sprite in numpy array for fast operations. """
    if not numpy:
        return
    # copy a numpy array of the target area
    clip = pygame.surfarray.array2d(canvas[apagenum].subsurface(pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)))
    get_put_store[varname] = ( x1-x0+1, y1-y0+1, clip, version )

def fast_put(x0, y0, varname, new_version, operation_char):
    """ Write sprite to screen; use numpy array if available. """
    global screen_changed
    try:
        width, height, clip, version = get_put_store[varname]
    except KeyError:
        # not yet stored, do it the slow way
        return None
    if x0 < 0 or x0+width-1 > size[0] or y0 < 0 or y0+height-1 > size[1]:
        # let the normal version handle errors
        return None    
    # if the versions are not the same, use the slow method 
    # (array has changed since clip was stored)
    if version != new_version:
        return None
    # reference the destination area
    dest_array = pygame.surfarray.pixels2d(
            canvas[apagenum].subsurface(pygame.Rect(x0, y0, width, height))) 
    # apply the operation
    operation = fast_operations[operation_char]
    operation(dest_array, clip)
    screen_changed = True
    return x0, y0, x0+width-1, y0+height-1
                
prepare()

