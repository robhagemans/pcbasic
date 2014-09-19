"""
PC-BASIC 3.23 - backend.py

Event loop; video, audio, keyboard, pen and joystick handling

(c) 2013, 2014 Rob Hagemans 

This file is released under the GNU GPL version 3. 
please see text file COPYING for licence terms.
"""

import logging
from copy import copy

import config
import state 
import timedate
import unicodepage
import scancode
import error
    
# backend implementations
video = None
audio = None 

#############################################
# sound queue

# sound queue
state.console_state.music_queue = [[], [], [], []]
# sound capabilities - '', 'pcjr' or 'tandy'
pcjr_sound = ''

#############################################
# keyboard queue

# let OS handle capslock effects
ignore_caps = True

# default function key scancodes for KEY autotext. F1-F10
# F11 and F12 here are TANDY scancodes only!
function_key = {
    scancode.F1: 0, scancode.F2: 1, scancode.F3: 2, scancode.F4: 3, 
    scancode.F5: 4, scancode.F6: 5, scancode.F7: 6, scancode.F8: 7,
    scancode.F9: 8, scancode.F10: 9, scancode.F11: 10, scancode.F12: 11}
# user definable key list
state.console_state.key_replace = [ 
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r',
    'TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '' ]
# switch off macro repacements
state.basic_state.key_macros_off = False    
# keyboard queue
state.console_state.keybuf = ''
# key buffer
# INP(&H60) scancode
state.console_state.inp_key = 0
# active status of caps, num, scroll, alt, ctrl, shift modifiers
state.console_state.mod = 0
# input has closed
input_closed = False
# bit flags for modifier keys
toggle = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,  
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10}
modifier = {    
    scancode.ALT: 0x8, scancode.CTRL: 0x4, 
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1}
# store for alt+keypad ascii insertion    
keypad_ascii = ''

#############################################
# screen buffer

class ScreenRow(object):
    """ Buffer for a single row of the screen. """
    
    def __init__(self, battr, bwidth):
        """ Set up screen row empty and unwrapped. """
        # screen buffer, initialised to spaces, dim white on black
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0    
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self, battr):
        """ Clear the screen row buffer. Leave wrap untouched. """
        bwidth = len(self.buf)
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0    


class ScreenBuffer(object):
    """ Buffer for a screen page. """
    
    def __init__(self, battr, bwidth, bheight):
        """ Initialise the screen buffer to given dimensions. """
        self.row = [ScreenRow(battr, bwidth) for _ in xrange(bheight)]


# redirect i/o to file or printer
input_echos = []
output_echos = []

#############################################
# cursor

# cursor visible in execute mode?
state.console_state.cursor = False
# cursor shape
state.console_state.cursor_from = 0
state.console_state.cursor_to = 0    

# pen and stick
state.console_state.pen_is_on = False
state.console_state.stick_is_on = False

#############################################
# palettes

# CGA colours
colours16_colour = [    
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0x55,0x00), (0xaa,0xaa,0xaa), 
    (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) ]
# EGA colours
colours64 = [ 
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0xaa,0x00), (0xaa,0xaa,0xaa), 
    (0x00,0x00,0x55), (0x00,0x00,0xff), (0x00,0xaa,0x55), (0x00,0xaa,0xff),
    (0xaa,0x00,0x55), (0xaa,0x00,0xff), (0xaa,0xaa,0x55), (0xaa,0xaa,0xff),
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
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) ]

# mono intensities
# CGA mono
intensity16_mono = range(0x00, 0x100, 0x11) 
# SCREEN 10 EGA pseudocolours, blink state 0 and 1
intensity_ega_mono_0 = [0x00, 0x00, 0x00, 0xaa, 0xaa, 0xaa, 0xff, 0xff, 0xff]
intensity_ega_mono_1 = [0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff]
# MDA/EGA mono text intensity (blink is attr bit 7, like in colour mode)
intensity_mda_mono = [0x00, 0xaa, 0xff] 
# colour of monochrome monitor
mono_tint = (0xff, 0xff, 0xff)
# mono colours
colours16_mono = [ [tint*i//255 for tint in mono_tint] 
                   for i in intensity16_mono ]            
colours_ega_mono_0 = [ [tint*i//255 for tint in mono_tint]
                   for i in intensity_ega_mono_0 ]            
colours_ega_mono_1 = [ [tint*i//255 for tint in mono_tint]
                   for i in intensity_ega_mono_1 ]        
colours_mda_mono = [ [tint*i//255 for tint in mono_tint]
                   for i in intensity_mda_mono ]
colours16 = copy(colours16_colour)

# default cga 4-color palette can change with mode, so is a list
cga_mode_5 = False
cga4_palette = [0, 11, 13, 15]
# default 16-color and ega palettes
cga16_palette = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
ega_palette = (0, 1, 2, 3, 4, 5, 20, 7, 56, 57, 58, 59, 60, 61, 62, 63)
ega_mono_palette = (0, 4, 1, 8)
# http://qbhlp.uebergeord.net/screen-statement-details-colors.html
# http://www.seasip.info/VintagePC/mda.html
# underline/intensity/reverse video attributes are slightly different from mda
# attributes 1, 9 should have underlining. 
ega_mono_text_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 0)
mda_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 2)
# use ega palette by default

#############################################
# video modes

# ega, tandy, pcjr
video_capabilities = 'ega'
# video memory size - currently only used by tandy/pcjr
state.console_state.pcjr_video_mem_size = 16384
# default is EGA 64K
#state.console_state.video_mem_size = 65536
# SCREEN mode (0 is textmode)
state.console_state.screen_mode = 0
# number of active page
state.console_state.apagenum = 0
# number of visible page
state.console_state.vpagenum = 0
# number of columns, counting 1..width
state.console_state.width = 80
# number of rows, counting 1..height
state.console_state.height = 25
# the available colours
state.console_state.colours = colours64
# blinking *colours* - only SCREEN 10, otherwise blink is an *attribute*
state.console_state.colours1 = None
# the palette defines the colour for each attribute
state.console_state.palette = list(ega_palette)


class ModeData(object):
    """ Holds settings for video modes. """
    
    def __init__(self, font_height, attr, num_attr, 
                 width, num_pages, bitsperpixel, 
                 palette, colours, colours1=None, 
                 font_width=8, 
                 supports_artifacts=False, cursor_index=None, has_blink=False,
                 pixel_aspect=None, has_underline=False):
        """ Settings for one video mode. """         
        self.font_height = font_height
        self.attr = attr
        self.num_attr = num_attr
        self.colours = colours
        self.colours1 = colours1
        self.palette = palette
        self.width = width
        self.num_pages = num_pages
        self.bitsperpixel = bitsperpixel
        self.font_width = font_width
        self.supports_artifacts = supports_artifacts
        self.cursor_index = cursor_index
        self.has_blink = has_blink
        self.has_underline = has_underline
        self.pixel_aspect = pixel_aspect
            
# video modes
text_mode = {
    'vga': ModeData(
                font_height = 16,
                font_width = 9,
                attr = 7,
                num_attr = 32,
                colours = colours64,
                palette = ega_palette,
                width = 80,
                num_pages = 4,
                bitsperpixel = 4,
                has_blink = True),
    'ega': ModeData(
                font_height = 14,
                attr = 7,
                num_attr = 32,
                colours = colours64,
                palette = ega_palette,
                width = 80,
                num_pages = 4,
                bitsperpixel = 4,
                has_blink = True),
    'ega_mono': ModeData(
                font_height = 14, 
                font_width = 8,
                attr = 7,
                num_attr = 32,
                colours = colours_mda_mono,
                palette = mda_palette,
                width = 80,
                num_pages = 4,
                bitsperpixel = 4,
                has_blink = True,
                has_underline = True),
    'mda':  ModeData(
                font_height = 14, 
                font_width = 9,
                attr = 7,
                num_attr = 32,
                colours = colours_mda_mono,
                palette = mda_palette,
                width = 80,
                num_pages = 4,
                bitsperpixel = 4,
                has_blink = True,
                has_underline = True),
    'cga':  ModeData(
                font_height = 8, 
                attr = 7,
                num_attr = 32,
                colours = colours16,
                palette = cga16_palette,
                width = 80,
                num_pages = 4, # do we have 4 pages on CGA/Tandy text?
                bitsperpixel = 4,
                has_blink = True),
    'tandy':  ModeData(
                font_height = 9, 
                attr = 7,
                num_attr = 32,
                colours = colours16,
                palette = cga16_palette,
                width = 80,
                num_pages = 4, # do we have 4 pages on CGA/Tandy text?
                bitsperpixel = 4,
                has_blink = True),
    }

# Tandy/PCjr pixel aspect ratio is different from normal
# suggesting screen aspect ratio is not 4/3.
# Tandy pixel aspect ratios, experimentally found with CIRCLE:
# screen 2, 6:     48/100   normal if aspect = 3072, 2000
# screen 1, 4, 5:  96/100   normal if aspect = 3072, 2000
# screen 3:      1968/1000 
# screen 3 is strange, slighly off the 192/100 you'd expect

graphics_mode = {
    # 04h 320x200x4  16384B 2bpp 0xb8000 
    # tandy:2 pages if 32k memory; ega: 1 page only 
    # TODO: tandy/pcjr - determine the number of pages based on video memory
    '320x200x4': ModeData(
            font_height = 8, 
            attr = 3,
            num_attr = 4,
            colours = colours16,
            palette = cga4_palette,
            width = 40,
            num_pages = 1,
            bitsperpixel = 2),
    # 06h 640x200x2  16384B 1bpp 0xb8000 
    '640x200x2': ModeData(
            font_height = 8, 
            attr = 1,
            num_attr = 2,
            colours = colours16,
            palette = [0, 15],
            width = 80,
            num_pages = 1,
            bitsperpixel = 1,
            supports_artifacts = True),
    # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy
    '160x200x16': ModeData(
            font_height = 8, 
            attr = 15,
            num_attr = 16,
            colours = colours16,
            palette = cga16_palette,
            width = 20,
            num_pages = 2,
            bitsperpixel = 4,
            cursor_index = 3,
            pixel_aspect = (1968, 1000) # you'd expect 192, 100
            ),
    #     320x200x4  16384B 2bpp 0xb8000   
    '320x200x4': ModeData(
            font_height = 8, 
            attr = 3,
            num_attr = 4,
            colours = colours16,
            palette = cga4_palette,
            width = 40,
            num_pages = 2,
            bitsperpixel = 2,
            cursor_index = 3),
    # 09h 320x200x16 32768B 4bpp 0xb8000    
    '320x200x16': ModeData(
            font_height = 8, 
            attr = 15,
            num_attr = 16,
            colours = colours16,
            palette = cga16_palette,
            width = 40,
            num_pages = 1,
            bitsperpixel = 4,
            cursor_index = 3),
    # 0Ah 640x200x4  32768B 2bpp 0xb8000   
    '640x200x4': ModeData(
            font_height = 8, 
            attr = 3,
            num_attr = 4,
            colours = colours16,
            palette = cga4_palette,
            width = 80,
            num_pages = 1,
            bitsperpixel = 2,
            cursor_index = 3),
    # 0Dh 320x200x16 32768B 4bpp 0xa0000
    '320x200x16': ModeData(
            font_height = 8, 
            attr = 15,
            num_attr = 16,
            colours = colours16,
            palette = cga16_palette,
            width = 40,
            num_pages = 8,
            bitsperpixel = 4),
    # 0Eh 640x200x16 
    '640x200x16': ModeData(
            font_height = 8, 
            attr = 15,
            num_attr = 16,
            colours = colours16,
            palette = cga16_palette,
            width = 80,
            num_pages = 4,
            bitsperpixel = 4),
    # 10h 640x350x16 
    '640x350x16': ModeData(
            font_height = 14, 
            attr = 15,
            num_attr = 16,
            colours = colours64,
            palette = ega_palette,
            width = 80,
            num_pages = 2,
            bitsperpixel = 4),
    # 0Fh 640x350x4 monochrome 
    '640x350x4': ModeData(
            font_height = 14, 
            attr = 1,
            num_attr = 4,
            colours = colours_ega_mono_0,
            colours1 = colours_ega_mono_1,
            palette = ega_mono_palette,
            width = 80,
            num_pages = 2,
            bitsperpixel = 2,
            has_blink = True),
    }

# mode numbers by video card
available_modes = {
    'mda': {
        0: text_mode['mda']},
    'cga': {
        0: text_mode['cga'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2']},
    'cga_old': {
        0: text_mode['cga'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2']},
    'pcjr': {
        0: text_mode['cga'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2'],
        3: graphics_mode['160x200x16'],
        4: graphics_mode['320x200x4'],
        5: graphics_mode['320x200x16'],
        6: graphics_mode['640x200x4']},
    'tandy': {
        0: text_mode['tandy'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2'],
        3: graphics_mode['160x200x16'],
        4: graphics_mode['320x200x4'],
        5: graphics_mode['320x200x16'],
        6: graphics_mode['640x200x4']},
    'ega': {
        0: text_mode['ega'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2'],
        7: graphics_mode['320x200x16'],
        8: graphics_mode['640x200x16'],
        9: graphics_mode['640x350x16']},
    'ega_mono': {
        0: text_mode['ega_mono'],
        10: graphics_mode['640x350x4']},
    'vga': {
        0: text_mode['vga'],
        1: graphics_mode['320x200x4'],
        2: graphics_mode['640x200x2'],
        7: graphics_mode['320x200x16'],
        8: graphics_mode['640x200x16'],
        9: graphics_mode['640x350x16']},
}

# to be filled with the modes available to our video card    
mode_data = {}

# border colour
state.console_state.border_attr = 0
# colorburst value
state.console_state.colorswitch = 1

#############################################
# initialisation

def prepare():
    """ Initialise backend module. """
    prepare_keyboard()
    prepare_audio()
    prepare_video()
    # initialise event triggers
    reset_events()    

def prepare_keyboard():
    """ Prepare keyboard handling. """
    global ignore_caps
    global num_fn_keys
    # inserted keystrokes
    for u in config.options['keys'].decode('string_escape').decode('utf-8'):
        c = u.encode('utf-8')
        try:
            state.console_state.keybuf += unicodepage.from_utf8(c)
        except KeyError:
            state.console_state.keybuf += c
    # handle caps lock only if requested
    if config.options['capture_caps']:
        ignore_caps = False
    # function keys: F1-F12 for tandy, F1-F10 for gwbasic and pcjr
    if config.options['pcjr_syntax'] == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10

def prepare_audio():
    """ Prepare the audio subsystem. """
    global pcjr_sound
    # pcjr/tandy sound
    pcjr_sound = config.options['pcjr_syntax']
    # tandy has SOUND ON by default, pcjr has it OFF
    state.console_state.sound_on = (pcjr_sound == 'tandy')

def init_audio():
    """ Initialise the audio backend. """
    global audio
    if not audio or not audio.init_sound():
        return False
    # rebuild sound queue
    for voice in range(4):    
        for note in state.console_state.music_queue[voice]:
            audio.play_sound(*note)
    return True

def prepare_video():
    """ Prepare the video subsystem. """
    global egacursor
    global video_capabilities, composite_monitor, mono_monitor, mono_tint
    global colours16_mono, colours_ega_mono_0, colours_ega_mono_1, cga_low
    global colours_ega_mono_text
    global mode_data, circle_aspect
    video_capabilities = config.options['video']
    if video_capabilities in ('pcjr', 'tandy'):
        circle_aspect = (3072, 2000)
    else:
        circle_aspect = (4, 3)
    egacursor = config.options['video'] in ('ega', 'mda', 'ega_mono', 'vga')
    composite_monitor = config.options['monitor'] == 'composite'
    mono_monitor = config.options['monitor'] == 'mono'
    if video_capabilities == 'ega' and mono_monitor:
        video_capabilities = 'ega_mono'
    if video_capabilities not in ('ega', 'vga'):
        state.console_state.colours = colours16
        state.console_state.palette = cga16_palette[:]
    cga_low = config.options['cga_low']
    set_cga4_palette(1)    
    # set monochrome tint and build mono palettes
    if config.options['mono_tint']:
        mono_tint = [int(s) for s in config.options['mono_tint'].split(',')]
    colours16_mono[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity16_mono ]            
    colours_ega_mono_0[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_ega_mono_0 ]            
    colours_ega_mono_1[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_ega_mono_1 ]        
    colours_mda_mono[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_mda_mono ]
    if mono_monitor:
        # copy to replace 16-colours with 16-mono
        colours16[:] = colours16_mono
    # prepare video mode list
    # only allow the screen modes that the given machine supports
    mode_data = available_modes[video_capabilities]
           
def init_video():
    """ Initialise the video backend. """
    if not video or not video.init():
        return False
    if state.loaded:
        # reload the screen in resumed state
        return resume_screen()
    else:        
        # initialise a fresh textmode screen
        screen(None, None, None, None)
        return True

def resume_screen():
    """ Load a video mode from storage and initialise. """
    if state.console_state.screen_mode not in mode_data:
        # mode not supported by backend
        logging.warning(
            "Resumed screen mode %d not supported by this setup",
            state.console_state.screen_mode)
        return False
    mode_info = copy(mode_data[state.console_state.screen_mode])
    mode_info.width = state.console_state.width    
    mode_info.attr = state.console_state.attr
    # set up the appropriate screen resolution
    if (state.console_state.screen_mode == 0 or 
            video.supports_graphics_mode(mode_info)):
        # set the visible and active pages
        video.set_page(state.console_state.vpagenum, 
                       state.console_state.apagenum)
        # set the screen mde
        video.init_screen_mode(mode_info, 
                               state.console_state.screen_mode==0)
        video.update_palette(state.console_state.palette,
                             state.console_state.colours,
                             state.console_state.colours1)
        # fix the cursor
        video.build_cursor(
            state.console_state.cursor_width, 
            state.console_state.font_height, 
            state.console_state.cursor_from, state.console_state.cursor_to)    
        video.move_cursor(state.console_state.row, state.console_state.col)
        video.update_cursor_attr(
                state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
        update_cursor_visibility()
        video.set_border(state.console_state.border_attr)
    else:
        # fix the terminal
        video.close()
        # mode not supported by backend
        logging.warning(
            "Resumed screen mode %d not supported by this interface.", 
            state.console_state.screen_mode)
        return False
    # load the screen contents from storage
    video.load_state()
    return True
    
#############################################
# main event checker
    
def wait():
    """ Wait and check events. """
    video.idle()
    check_events()    

def idle():
    """ Wait a tick. """
    video.idle()

def check_events():
    """ Main event cycle. """
    # manage sound queue
    audio.check_sound()
    check_quit_sound()
    # check video, keyboard, pen and joystick events
    video.check_events()   
    # trigger & handle BASIC events
    if state.basic_state.run_mode:
        # trigger TIMER, PLAY and COM events
        check_timer_event()
        check_play_event()
        check_com_events()
        # KEY, PEN and STRIG are triggered on handling the queue

##############################
# video mode

def screen(new_mode, new_colorswitch, new_apagenum, new_vpagenum, 
           erase=1, new_width=None):
    """ Change the video mode, colourburst, visible or active page. """
    # set default arguments
    if new_mode == None:
        new_mode = state.console_state.screen_mode
    if new_colorswitch == None:    
        new_colorswitch = state.console_state.colorswitch 
    else:
        new_colorswitch = (new_colorswitch != 0)
    if new_vpagenum == None:    
        new_vpagenum = state.console_state.vpagenum 
    if new_apagenum == None:
        new_apagenum = state.console_state.apagenum
    # TODO: implement erase level (Tandy/pcjr)
    # Erase tells basic how much video memory to erase
    # 0: do not erase video memory
    # 1: (default) erase old and new page if screen or bust changes
    # 2: erase all video memory if screen or bust changes 
    try:
        info = copy(mode_data[new_mode])
    except KeyError:
        # no such mode
        info = None
    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, 
    # illegal fn call before anything happens.
    if (not info or new_apagenum >= info.num_pages or 
            new_vpagenum >= info.num_pages or 
            (new_mode != 0 and not video.supports_graphics_mode(info))):
        # reset palette happens 
        # even if the function fails with Illegal Function Call
        set_palette()
        return False
    # width persists on change to screen 0
    if new_mode == 0 and new_width == None:
        new_width = state.console_state.width 
        if new_width == 20:
            new_width = 40
    if new_width != None:
        info.width = new_width
    state.console_state.width = info.width
    # attribute persists on width-only change
    if (state.console_state.screen_mode == 0 and new_mode == 0 
            and state.console_state.apagenum == new_apagenum 
            and state.console_state.vpagenum == new_vpagenum):
        info.attr = state.console_state.attr
    state.console_state.attr = info.attr
    # start with black border 
    if new_mode != state.console_state.screen_mode:
        set_border(0)
    # set all state vars
    state.console_state.screen_mode = new_mode
    state.console_state.colorswitch = new_colorswitch 
    state.console_state.font_height = info.font_height 
    state.console_state.num_attr = info.num_attr
    state.console_state.colours = info.colours
    state.console_state.colours1 = info.colours1
    state.console_state.default_palette = info.palette
    state.console_state.height = 25
    state.console_state.width = info.width
    state.console_state.num_pages = info.num_pages
    state.console_state.bitsperpixel = info.bitsperpixel
    state.console_state.font_width = info.font_width
    # build the screen buffer    
    state.console_state.pages = []
    for _ in range(state.console_state.num_pages):
        state.console_state.pages.append(
                ScreenBuffer(state.console_state.attr, 
                    state.console_state.width, state.console_state.height))
    # set active page & visible page, counting from 0. 
    set_page(new_vpagenum, new_apagenum)
    # set graphics characteristics
    init_graphics(info)
    # cursor width starts out as single char
    state.console_state.cursor_width = state.console_state.font_width        
    # signal the backend to change the screen resolution
    video.init_screen_mode(info, state.console_state.screen_mode == 0)
    # set the palette (essential on first run, or not all globals defined)
    set_palette()
    # in screen 0, 1, set colorburst (not in SCREEN 2!)
    if new_mode in (0, 1):
        set_colorburst(new_colorswitch)
    elif new_mode == 2:
        set_colorburst(False)    
    return True

def init_graphics(mode_info):
    """ Set the graphical characteristics of a new mode. """
    # resolution
    state.console_state.size = (
        state.console_state.width * state.console_state.font_width,          
        state.console_state.height * state.console_state.font_height)
    # centre of new graphics screen
    state.console_state.last_point = (
        state.console_state.size[0]/2, state.console_state.size[1]/2)
    # assumed aspect ratio for CIRCLE    
    # pixels e.g. 80*8 x 25*14, screen ratio 4x3 
    # makes for pixel width/height (4/3)*(25*14/8*80)
    if mode_info.pixel_aspect:
        state.console_state.pixel_aspect_ratio = mode_info.pixel_aspect
    else:      
        state.console_state.pixel_aspect_ratio = (
             25 * mode_info.font_height * circle_aspect[0], 
             mode_info.width * mode_info.font_width * circle_aspect[1])

def set_page(new_vpagenum, new_apagenum):
    """ Set active page & visible page, counting from 0. """
    state.console_state.vpagenum = new_vpagenum
    state.console_state.apagenum = new_apagenum
    state.console_state.vpage = state.console_state.pages[new_vpagenum]
    state.console_state.apage = state.console_state.pages[new_apagenum]
    video.set_page(new_vpagenum, new_apagenum)

def set_width(to_width):
    """ Set the character width of the screen. """
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

def check_video_memory():
    """ Raise an error if not enough video memory for this state. """
    # video memory size check for SCREENs 5 and 6: 
    # (pcjr/tandy only; this is a bit of a hack as is) 
    # (32753 determined experimentally on DOSBox)
    if (state.console_state.screen_mode in (5, 6) and 
            state.console_state.pcjr_video_mem_size < 32753):
        screen (0, None, None, None)

#############################################
# palette and colours

def set_palette_entry(index, colour):
    """ Set a new colour for a given attribute. """
    state.console_state.palette[index] = colour
    video.update_palette(state.console_state.palette,
                         state.console_state.colours,
                         state.console_state.colours1)

def get_palette_entry(index):
    """ Retrieve the colour for a given attribute. """
    return state.console_state.palette[index]

def set_palette(new_palette=None):
    """ Set the colours for all attributes. """
    if new_palette:
        state.console_state.palette = new_palette[:]
    else:    
        state.console_state.palette = list(state.console_state.default_palette)
    video.update_palette(state.console_state.palette,
                         state.console_state.colours,
                         state.console_state.colours1)

def set_cga4_palette(num):
    """ Change the default CGA palette according to palette number & mode. """
    # palette 1: Black, Ugh, Yuck, Bleah, choice of low & high intensity
    # palette 0: Black, Green, Red, Brown/Yellow, low & high intensity
    # tandy/pcjr have high-intensity white, but low-intensity colours
    # mode 5 (SCREEN 1 + colorburst on RGB) has red instead of magenta
    if video_capabilities in ('pcjr', 'tandy'):
        # pcjr does not have mode 5
        if num == 0:
            cga4_palette[:] = (0, 2, 4, 6)
        else:    
            cga4_palette[:] = (0, 3, 5, 15)
    elif cga_low:
        if cga_mode_5:
            cga4_palette[:] = (0, 3, 4, 7)
        elif num == 0:
            cga4_palette[:] = (0, 2, 4, 6)
        else:    
            cga4_palette[:] = (0, 3, 5, 7)
    else:
        if cga_mode_5:
            cga4_palette[:] = (0, 11, 12, 15)
        elif num == 0:
            cga4_palette[:] = (0, 10, 12, 14)
        else:    
            cga4_palette[:] = (0, 11, 13, 15)

def set_colorburst(on=True):
    """ Set the composite colorburst bit. """
    # On a composite monitor:
    # - on SCREEN 2 this enables artifacting
    # - on SCREEN 1 and 0 this switches between colour and greyscale
    # On an RGB monitor:
    # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
    # - ignored on other screens
    global cga_mode_5
    colorburst_capable = video_capabilities in (
                                'cga', 'cga_old', 'tandy', 'pcjr')
    if state.console_state.screen_mode == 1 and not composite_monitor:
        # ega ignores colorburst; tandy and pcjr have no mode 5
        cga_mode_5 = not (on or video_capabilities not in ('cga', 'cga_old'))
        set_cga4_palette(1)
        set_palette()    
    elif (on or not composite_monitor and not mono_monitor):
        # take modulo in case we're e.g. resuming ega text into a cga machine
        colours16[:] = colours16_colour
    else:
        colours16[:] = colours16_mono
    video.set_colorburst(on and colorburst_capable, state.console_state.palette, 
            state.console_state.colours, state.console_state.colours1)

def set_border(attr):
    """ Set the border attribute. """
    state.console_state.border_attr = attr
    video.set_border(attr)

##############################
# screen buffer read/write

def put_screen_char_attr(cpage, crow, ccol, c, cattr, 
                         one_only=False, for_keys=False):
    """ Put a byte to the screen, redrawing SBCS and DBCS as necessary. """
    cattr = cattr & 0xf if state.console_state.screen_mode else cattr
    # update the screen buffer
    cpage.row[crow-1].buf[ccol-1] = (c, cattr)
    # mark the replaced char for refreshing
    start, stop = ccol, ccol+1
    cpage.row[crow-1].double[ccol-1] = 0
    # mark out sbcs and dbcs characters
    # only do dbcs in 80-character modes
    if unicodepage.dbcs and state.console_state.width == 80:
        orig_col = ccol
        # replace chars from here until necessary to update double-width chars
        therow = cpage.row[crow-1]    
        # replacing a trail byte? take one step back
        # previous char could be a lead byte? take a step back
        if (ccol > 1 and therow.double[ccol-2] != 2 and 
                (therow.buf[ccol-1][0] in unicodepage.trail or 
                 therow.buf[ccol-2][0] in unicodepage.lead)):
            ccol -= 1
            start -= 1
        # check all dbcs characters between here until it doesn't matter anymore
        while ccol < state.console_state.width:
            c = therow.buf[ccol-1][0]
            d = therow.buf[ccol][0]  
            if (c in unicodepage.lead and d in unicodepage.trail):
                if (therow.double[ccol-1] == 1 and 
                        therow.double[ccol] == 2 and ccol > orig_col):
                    break
                therow.double[ccol-1] = 1
                therow.double[ccol] = 2
                start, stop = min(start, ccol), max(stop, ccol+2)
                ccol += 2
            else:
                if therow.double[ccol-1] == 0 and ccol > orig_col:
                    break
                therow.double[ccol-1] = 0
                start, stop = min(start, ccol), max(stop, ccol+1)
                ccol += 1
            if (ccol >= state.console_state.width or 
                    (one_only and ccol > orig_col)):
                break  
        # check for box drawing
        if unicodepage.box_protect:
            ccol = start-2
            connecting = 0
            bset = -1
            while ccol < stop+2 and ccol < state.console_state.width:
                c = therow.buf[ccol-1][0]
                d = therow.buf[ccol][0]  
                if bset > -1 and unicodepage.connects(c, d, bset): 
                    connecting += 1
                else:
                    connecting = 0
                    bset = -1
                if bset == -1:
                    for b in (0, 1):
                        if unicodepage.connects(c, d, b):
                            bset = b
                            connecting = 1
                if connecting >= 2:
                    therow.double[ccol] = 0
                    therow.double[ccol-1] = 0
                    therow.double[ccol-2] = 0
                    start = min(start, ccol-1)
                    if ccol > 2 and therow.double[ccol-3] == 1:
                        therow.double[ccol-3] = 0
                        start = min(start, ccol-2)
                    if (ccol < state.console_state.width-1 and 
                            therow.double[ccol+1] == 2):
                        therow.double[ccol+1] = 0
                        stop = max(stop, ccol+2)
                ccol += 1        
    # update the screen            
    refresh_screen_range(cpage, crow, start, stop, for_keys)

def get_screen_char_attr(crow, ccol, want_attr):
    """ Retrieve a byte from the screen (SBCS or DBCS half-char). """
    ca = state.console_state.apage.row[crow-1].buf[ccol-1][want_attr]
    return ca if want_attr else ord(ca)

def get_text(start_row, start_col, stop_row, stop_col):   
    """ Retrieve a clip of the text between start and stop. """     
    r, c = start_row, start_col
    full = ''
    clip = ''
    while r < stop_row or (r == stop_row and c <= stop_col):
        clip += state.console_state.vpage.row[r-1].buf[c-1][0]    
        c += 1
        if c > state.console_state.width:
            if not state.console_state.vpage.row[r-1].wrap:
                full += unicodepage.UTF8Converter().to_utf8(clip) + '\r\n'
                clip = ''
            r += 1
            c = 1
    full += unicodepage.UTF8Converter().to_utf8(clip)        
    return full

def redraw_row(start, crow, wrap=True):
    """ Draw the screen row, wrapping around and reconstructing DBCS buffer. """
    while True:
        therow = state.console_state.apage.row[crow-1]  
        for i in range(start, therow.end): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            # don't update all dbcs chars behind at each put
            put_screen_char_attr(state.console_state.apage, crow, i+1, 
                    therow.buf[i][0], state.console_state.attr, one_only=True)
        if (wrap and therow.wrap and 
                crow >= 0 and crow < state.console_state.height-1):
            crow += 1
            start = 0
        else:
            break    

def refresh_screen_range(cpage, crow, start, stop, for_keys=False):
    """ Redraw a section of a screen row, assuming DBCS buffer has been set. """
    therow = cpage.row[crow-1]
    ccol = start
    while ccol < stop:
        double = therow.double[ccol-1]
        if double == 1:
            ca = therow.buf[ccol-1]
            da = therow.buf[ccol]
            video.set_attr(da[1]) 
            video.putwc_at(crow, ccol, ca[0], da[0], for_keys)
            therow.double[ccol-1] = 1
            therow.double[ccol] = 2
            ccol += 2
        else:
            if double != 0:
                logging.debug('DBCS buffer corrupted at %d, %d', crow, ccol)
            ca = therow.buf[ccol-1]        
            video.set_attr(ca[1]) 
            video.putc_at(crow, ccol, ca[0], for_keys)
            ccol += 1


def redraw_text_screen():
    """ Redraw the active screen page, reconstructing DBCS buffers. """
    # force cursor invisible during redraw
    show_cursor(False)
    # this makes it feel faster
    video.clear_rows(state.console_state.attr, 1, 25)
    # redraw every character
    for crow in range(state.console_state.height):
        thepage = state.console_state.apage
        therow = thepage.row[crow]  
        for i in range(state.console_state.width): 
            put_screen_char_attr(thepage, crow+1, i+1, 
                                 therow.buf[i][0], therow.buf[i][1])
    # set cursor back to previous state                             
    update_cursor_visibility()

def print_screen():
    """ Output the visible page to LPT1. """
    for crow in range(1, state.console_state.height+1):
        line = ''
        for c, _ in state.console_state.vpage.row[crow-1].buf:
            line += c
        state.io_state.devices['LPT1:'].write_line(line)

def copy_page(src, dst):
    """ Copy source to destination page. """
    for x in range(state.console_state.height):
        dstrow = state.console_state.pages[dst].row[x]
        srcrow = state.console_state.pages[src].row[x]
        dstrow.buf[:] = srcrow.buf[:]
        dstrow.end = srcrow.end
        dstrow.wrap = srcrow.wrap            
    video.copy_page(src, dst)

def clear_screen_buffer_at(x, y):
    """ Remove the character covering a single pixel. """
    fx, fy = state.console_state.font_width, state.console_state.font_height
    cymax, cxmax = state.console_state.height-1, state.console_state.width-1
    cx, cy = x // fx, y // fy
    if cx >= 0 and cy >= 0 and cx <= cxmax and cy <= cymax:
        state.console_state.apage.row[cy].buf[cx] = (
                ' ', state.console_state.attr)

def clear_screen_buffer_area(x0, y0, x1, y1):
    """ Remove all characters from a rectangle of the graphics screen. """
    fx, fy = state.console_state.font_width, state.console_state.font_height
    cymax, cxmax = state.console_state.height-1, state.console_state.width-1 
    cx0 = min(cxmax, max(0, x0 // fx)) 
    cy0 = min(cymax, max(0, y0 // fy))
    cx1 = min(cxmax, max(0, x1 // fx)) 
    cy1 = min(cymax, max(0, y1 // fy))
    for r in range(cy0, cy1+1):
        state.console_state.apage.row[r].buf[cx0:cx1+1] = [
            (' ', state.console_state.attr)] * (cx1 - cx0 + 1)
    
##############################
# keyboard buffer read/write

def read_chars(num):
    """ Read num keystrokes, blocking. """
    word = []
    for _ in range(num):
        wait_char()
        word.append(get_char())
    return word

def get_char():
    """ Read any keystroke, nonblocking. """
    wait()    
    return pass_char(peek_char())

def wait_char():
    """ Wait for character, then return it but don't drop from queue. """
    while len(state.console_state.keybuf) == 0 and not input_closed:
        wait()
    return peek_char()

def pass_char(ch):
    """ Drop characters from keyboard buffer. """
    state.console_state.keybuf = state.console_state.keybuf[len(ch):]        
    return ch

def peek_char():
    """ Peek character or scancode from keyboard buffer. """
    ch = ''
    if len(state.console_state.keybuf)>0:
        ch = state.console_state.keybuf[0]
        if ch == '\x00' and len(state.console_state.keybuf) > 1:
            ch += state.console_state.keybuf[1]
    return ch 
    
def key_down(scan, eascii=''):
    """ Insert a key-down event. Keycode is extended ascii, including DBCS. """
    global keypad_ascii
    # set port and low memory address regardless of event triggers
    if scan != None:
        state.console_state.inp_key = scan
    # set modifier status    
    try:
        state.console_state.mod |= modifier[scan]
    except KeyError:
       pass 
    # set toggle-key modifier status    
    try:
        state.console_state.mod ^= toggle[scan]
    except KeyError:
       pass 
    # handle BIOS events
    if (scan == scancode.DELETE and 
            state.console_state.mod & 
                (modifier[scancode.CTRL] & modifier[scancode.ALT])):
            # ctrl-alt-del: if not captured by the OS, reset the emulator
            # meaning exit and delete state. This is useful on android.
            raise error.Reset()
    if (scan in (scancode.BREAK, scancode.SCROLLOCK) and
            state.console_state.mod & modifier[scancode.CTRL]):
            raise error.Break()
    if scan == scancode.PRINT:
        if (state.console_state.mod & 
                (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT])):
            # shift + printscreen
            print_screen()
        if state.console_state.mod & modifier[scancode.CTRL]:
            # ctrl + printscreen
            toggle_echo_lpt1()
    # alt+keypad ascii replacement        
    # we can't depend on internal NUM LOCK state as it doesn't get updated
    if (state.console_state.mod & modifier[scancode.ALT] and 
            len(eascii) == 1 and eascii >= '0' and eascii <= '9'):
        try:
            keypad_ascii += scancode.keypad[scan]
            return
        except KeyError:    
            pass
    # trigger events
    if check_key_event(scan, state.console_state.mod):
        # this key is being trapped, don't replace
        return
    # function key macros
    try:
        # only check function keys
        # can't be redefined in events - so must be fn 1-10 (1-12 on Tandy).
        keynum = function_key[scan]
        if (state.basic_state.key_macros_off or state.basic_state.run_mode 
                and state.basic_state.key_handlers[keynum].enabled):
            # this key is paused from being trapped, don't replace
            state.console_state.keybuf += scan_to_eascii(scan, 
                                              state.console_state.mod)
            return
        else:
            macro = state.console_state.key_replace[keynum]
            # insert directly, avoid caps handling
            state.console_state.keybuf += macro
            return
    except KeyError:
        pass
    if not eascii or (scan != None and state.console_state.mod & 
                (modifier[scancode.ALT] | modifier[scancode.CTRL])):
        # any provided e-ASCII value overrides when CTRL & ALT are off
        # this helps make keyboards do what's expected 
        # independent of language setting
        try:
            eascii = scan_to_eascii(scan, state.console_state.mod)
        except KeyError:            
            # no eascii found
            return
    if (state.console_state.mod & toggle[scancode.CAPSLOCK]
            and not ignore_caps and len(eascii) == 1):
        if eascii >= 'a' and eascii <= 'z':
            eascii = chr(ord(eascii)-32)
        elif eascii >= 'A' and eascii <= 'z':
            eascii = chr(ord(eascii)+32)
    insert_chars(eascii)        
    
def key_up(scan):
    """ Insert a key-up event. """
    global keypad_ascii
    if scan != None:
        state.console_state.inp_key = 0x80 + scan
    try:
        # switch off ephemeral modifiers
        state.console_state.mod &= ~modifier[scan]
        # ALT+keycode    
        if scan == scancode.ALT and keypad_ascii:
            char = chr(int(keypad_ascii)%256)
            if char == '\0':
                char = '\0\0'
            insert_chars(char)
            keypad_ascii = ''
    except KeyError:
       pass 
    
def insert_special_key(name):
    """ Insert break, reset or quit events. """
    if name == 'quit':
        raise error.Exit()
    elif name == 'reset':
        raise error.Reset()
    elif name == 'break':
        raise error.Break()
    else:
        logging.debug('Unknown special key: %s', name)
        
def insert_chars(s):
    """ Insert characters into keyboard buffer. """
    state.console_state.keybuf += s

def scan_to_eascii(scan, mod):
    """ Translate scancode and modifier state to e-ASCII. """
    if mod & modifier[scancode.ALT]:
        return scancode.eascii_table[scan][3]
    elif mod & modifier[scancode.CTRL]:
        return scancode.eascii_table[scan][2]
    elif mod & (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT]):
        return scancode.eascii_table[scan][1]
    else:
        return scancode.eascii_table[scan][0]

#############################################
# cursor

def show_cursor(do_show):
    """ Force cursor to be visible/invisible. """
    video.update_cursor_visibility(do_show)

def update_cursor_visibility():
    """ Set cursor visibility to its default state. """
    # visible if in interactive mode, unless forced visible in text mode.
    visible = (not state.basic_state.execute_mode)
    if state.console_state.screen_mode == 0:
        visible = visible or state.console_state.cursor
    video.update_cursor_visibility(visible)

def set_cursor_shape(from_line, to_line):
    """ Set the cursor shape. """
    # A block from from_line to to_line in 8-line modes.
    # Use compatibility algo in higher resolutions
    if egacursor:
        # odd treatment of cursors on EGA machines, 
        # presumably for backward compatibility
        # the following algorithm is based on DOSBox source int10_char.cpp 
        #     INT10_SetCursorShape(Bit8u first,Bit8u last)    
        max_line = state.console_state.font_height-1
        if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
            if (to_line < from_line):
                # invisible only if to_line is zero and to_line < from_line
                if to_line != 0: 
                    # block shape from *to_line* to end
                    from_line = to_line
                    to_line = max_line
            elif ((from_line | to_line) >= max_line or 
                        to_line != max_line-1 or from_line != max_line):
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
    state.console_state.cursor_from = max(0, min(from_line, 
                                      state.console_state.font_height-1))
    state.console_state.cursor_to = max(0, min(to_line, 
                                    state.console_state.font_height-1))
    video.build_cursor(state.console_state.cursor_width, 
                       state.console_state.font_height, 
                       state.console_state.cursor_from, 
                       state.console_state.cursor_to)
    video.update_cursor_attr(state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)

#############################################
# I/O redirection

def toggle_echo_lpt1():
    """ Toggle copying of all screen I/O to LPT1. """
    lpt1 = state.io_state.devices['LPT1:']
    if lpt1.write in input_echos:
        input_echos.remove(lpt1.write)
        output_echos.remove(lpt1.write)
    else:    
        input_echos.append(lpt1.write)
        output_echos.append(lpt1.write)

##############################################
# light pen

state.console_state.pen_was_down = False
pen_is_down = False
state.console_state.pen_down_pos = (0, 0)
pen_pos = (0, 0)

def pen_down(x, y):
    """ Report a pen-down event at graphical x,y """
    global pen_is_down
    state.basic_state.pen_handler.triggered = True
    state.console_state.pen_was_down = True # TRUE until polled
    pen_is_down = True # TRUE until pen up
    state.console_state.pen_down_pos = x, y

def pen_up():
    """ Report a pen-up event at graphical x,y """
    global pen_is_down
    pen_is_down = False
    
def pen_moved(x, y):
    """ Report a pen-move event at graphical x,y """
    state.console_state.pen_pos = x, y
    
def get_pen(fn):
    """ Poll the pen. """
    posx, posy = pen_pos
    fw = state.console_state.font_width
    fh = state.console_state.font_height
    if fn == 0:
        pen_down_old, state.console_state.pen_was_down = (
                state.console_state.pen_was_down, False)
        return -1 if pen_down_old else 0
    elif fn == 1:
        return state.console_state.pen_down_pos[0]
    elif fn == 2:
        return state.console_state.pen_down_pos[1]
    elif fn == 3:
        return -1 if pen_is_down else 0 
    elif fn == 4:
        return posx
    elif fn == 5:
        return posy
    elif fn == 6:
        return 1 + state.console_state.pen_down_pos[1]//fh
    elif fn == 7:
        return 1 + state.console_state.pen_down_pos[0]//fw
    elif fn == 8:
        return 1 + posy//fh
    elif fn == 9:
        return 1 + posx//fw
 
##############################################
# joysticks

state.console_state.stick_was_fired = [[False, False], [False, False]]
stick_is_firing = [[False, False], [False, False]]
# axis 0--255; 128 is mid but reports 0, not 128 if no joysticks present
stick_axis = [[0, 0], [0, 0]]

def stick_down(joy, button):
    """ Report a joystick button down event. """
    state.console_state.stick_was_fired[joy][button] = True
    stick_is_firing[joy][button] = True
    state.basic_state.strig_handlers[joy*2 + button].triggered = True

def stick_up(joy, button):
    """ Report a joystick button up event. """
    stick_is_firing[joy][button] = False

def stick_moved(joy, axis, value):
    """ Report a joystick axis move. """
    stick_axis[joy][axis] = value

def get_stick(fn):
    """ Poll the joystick axes. """    
    joy, axis = fn // 2, fn % 2
    return stick_axis[joy][axis]
    
def get_strig(fn):       
    """ Poll the joystick buttons. """    
    joy, trig = fn // 4, (fn//2) % 2
    if fn % 2 == 0:
        # has been fired
        stick_was_trig = state.console_state.stick_was_fired[joy][trig]
        state.console_state.stick_was_fired[joy][trig] = False
        return stick_was_trig
    else:
        # is currently firing
        return stick_is_firing[joy][trig]

##############################
# sound queue read/write

state.console_state.music_foreground = True

base_freq = 3579545./1024.
state.console_state.noise_freq = [base_freq / v 
                                  for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
state.console_state.noise_freq[3] = 0.
state.console_state.noise_freq[7] = 0.

# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000
quiet_ticks = 0

def beep():
    """ Play the BEEP sound. """
    play_sound(800, 0.25)

def play_sound(frequency, duration, fill=1, loop=False, voice=0, volume=15):
    """ Play a sound on the tone generator. """
    if frequency < 0:
        frequency = 0
    if ((pcjr_sound == 'tandy' or 
            (pcjr_sound == 'pcjr' and state.console_state.sound_on)) and
            frequency < 110. and frequency != 0):
        # pcjr, tandy play low frequencies as 110Hz
        frequency = 110.
    state.console_state.music_queue[voice].append(
            (frequency, duration, fill, loop, volume))
    audio.play_sound(frequency, duration, fill, loop, voice, volume) 
    if voice == 2:
        # reset linked noise frequencies
        # /2 because we're using a 0x4000 rotation rather than 0x8000
        state.console_state.noise_freq[3] = frequency/2.
        state.console_state.noise_freq[7] = frequency/2.
    # at most 16 notes in the sound queue (not 32 as the guide says!)
    wait_music(15, wait_last=False)    

def play_noise(source, volume, duration, loop=False):
    """ Play a sound on the noise generator. """
    audio.set_noise(source > 3)
    frequency = state.console_state.noise_freq[source]
    state.console_state.music_queue[3].append(
            (frequency, duration, 1, loop, volume))
    audio.play_sound(frequency, duration, 1, loop, 3, volume) 
    # don't wait for noise

def stop_all_sound():
    """ Terminate all sounds immediately. """
    state.console_state.music_queue = [ [], [], [], [] ]
    audio.stop_all_sound()
        
def wait_music(wait_length=0, wait_last=True):
    """ Wait until the music has finished playing. """
    while ((wait_last and audio.busy()) or
            len(state.console_state.music_queue[0])+wait_last-1 > wait_length or
            len(state.console_state.music_queue[1])+wait_last-1 > wait_length or
            len(state.console_state.music_queue[2])+wait_last-1 > wait_length ):
        wait()
    
def music_queue_length(voice=0):
    """ Return the number of notes in the queue. """
    # top of sound_queue is currently playing
    return max(0, len(state.console_state.music_queue[voice])-1)
        
def sound_done(voice, number_left):
    """ Report a sound has finished playing, remove from queue. """ 
    # remove the notes that have been played
    while len(state.console_state.music_queue[voice]) > number_left:
        state.console_state.music_queue[voice].pop(0)

def check_quit_sound():
    """ Quit the mixer if not running a program and sound quiet for a while. """
    global quiet_ticks
    if state.console_state.music_queue == [[], [], [], []] and not audio.busy():
        # could leave out the is_quiet call but for looping sounds 
        quiet_ticks = 0
    else:
        quiet_ticks += 1    
        if quiet_ticks > quiet_quit:
            # mixer is quiet and we're not running a program. 
            # quit to reduce pulseaudio cpu load
            if not state.basic_state.run_mode:
                # this takes quite a while and leads to missed frames...
                audio.quit_sound()
                quiet_ticks = 0
            
#############################################
# BASIC event triggers        
        
class EventHandler(object):
    """ Keeps track of event triggers. """
    
    def __init__(self):
        """ Initialise untriggered and disabled. """
        self.reset()
        
    def reset(self):
        """ Reet to untriggered and disabled initial state. """
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def command(self, command_char):
        """ Turn the event ON, OFF and STOP. """
        if command_char == '\x95': 
            # ON
            self.enabled = True
            self.stopped = False
        elif command_char == '\xDD': 
            # OFF
            self.enabled = False
        elif command_char == '\x90': 
            # STOP
            self.stopped = True
        else:
            return False
        return True

def reset_events():
    """ Initialise or reset event triggers. """
    # TIMER
    state.basic_state.timer_period, state.basic_state.timer_start = 0, 0
    state.basic_state.timer_handler = EventHandler()
    # KEY
    state.basic_state.event_keys = [''] * 20
    # F1-F10
    state.basic_state.event_keys[0:10] = [
        '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',
        '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44']
    # Tandy F11, F12
    if num_fn_keys == 12:
        state.basic_state.event_keys[10:12] = ['\x00\x98', '\x00\x99']
    # up, left, right, down
    state.basic_state.event_keys[num_fn_keys:num_fn_keys+4] = [   
        '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50']
    # the remaining keys are user definable        
    state.basic_state.key_handlers = [EventHandler() for _ in xrange(20)]
    # PLAY
    state.basic_state.play_last = [0, 0, 0]
    state.basic_state.play_trig = 1
    state.basic_state.play_handler = EventHandler()
    # COM
    state.basic_state.com_handlers = [EventHandler(), EventHandler()]  
    # PEN
    state.basic_state.pen_handler = EventHandler()
    # STRIG
    state.basic_state.strig_handlers = [EventHandler() for _ in xrange(4)]
    # all handlers in order of handling; TIMER first
    state.basic_state.all_handlers = [state.basic_state.timer_handler]  
    # key events are not handled FIFO but first 11-20 in that order, then 1-10
    state.basic_state.all_handlers += [state.basic_state.key_handlers[num] 
                                       for num in (range(10, 20) + range(10))]
    # this determined handling order
    state.basic_state.all_handlers += (
            [state.basic_state.play_handler] + state.basic_state.com_handlers + 
            [state.basic_state.pen_handler] + state.basic_state.strig_handlers)
    # set suspension off
    state.basic_state.suspend_all_events = False

def check_timer_event():
    """ Trigger TIMER events. """
    mutimer = timedate.timer_milliseconds() 
    if mutimer >= state.basic_state.timer_start+state.basic_state.timer_period:
        state.basic_state.timer_start = mutimer
        state.basic_state.timer_handler.triggered = True

def check_play_event():
    """ Trigger PLAY (music queue) events. """
    play_now = [music_queue_length(voice) for voice in range(3)]
    if pcjr_sound: 
        for voice in range(3):
            if (play_now[voice] <= state.basic_state.play_trig and 
                    play_now[voice] > 0 and 
                    play_now[voice] != state.basic_state.play_last[voice] ):
                state.basic_state.play_handler.triggered = True 
    else:    
        if (state.basic_state.play_last[0] >= state.basic_state.play_trig and 
                play_now[0] < state.basic_state.play_trig):    
            state.basic_state.play_handler.triggered = True     
    state.basic_state.play_last = play_now

def check_com_events():
    """ Trigger COM-port events. """
    ports = (state.io_state.devices['COM1:'], state.io_state.devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports[comport].peek_char():
            state.basic_state.com_handlers[comport].triggered = True

def check_key_event(scancode, modifiers):
    """ Trigger KEYboard events. """
    # "Extended ascii": ascii 1-255 or NUL+code where code is often but not
    # always the keyboard scancode. See e.g. Tandy 1000 BASIC manual for a good
    # overview. DBCS is simply entered as a string of ascii codes.
    # check for scancode (inp_code) events
    if not scancode:
        return False
    try:
        keynum = state.basic_state.event_keys.index('\0' + chr(scancode))
        # for pre-defined KEYs 1-14 (and 1-16 on Tandy) the modifier status 
        # is ignored.
        if (keynum >= 0 and keynum < num_fn_keys + 4 and 
                    state.basic_state.key_handlers[keynum].enabled):
                # trigger function or arrow key event
                state.basic_state.key_handlers[keynum].triggered = True
                # don't enter into key buffer
                return True
    except ValueError:
        pass
    # build KEY trigger code
    # see http://www.petesqbsite.com/sections/tutorials/tuts/keysdet.txt                
    # second byte is scan code; first byte
    #  0       if the key is pressed alone
    #  1 to 3    if any Shift and the key are combined
    #    4       if Ctrl and the key are combined
    #    8       if Alt and the key are combined
    #   32       if NumLock is activated
    #   64       if CapsLock is activated
    #  128       if we are defining some extended key
    # extended keys are for example the arrow keys on the non-numerical keyboard
    # presumably all the keys in the middle region of a standard PC keyboard?
    # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
    trigger_code = chr(modifiers & 0x6f) + chr(scancode)
    try:
        keynum = state.basic_state.event_keys.index(trigger_code)
        if (keynum >= num_fn_keys + 4 and keynum < 20 and
                    state.basic_state.key_handlers[keynum].enabled):
                # trigger user-defined key
                state.basic_state.key_handlers[keynum].triggered = True
                # don't enter into key buffer
                return True
    except ValueError:
        pass
    return False



prepare()
