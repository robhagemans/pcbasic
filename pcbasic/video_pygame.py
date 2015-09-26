"""
PC-BASIC - video_pygame.py
Graphical interface based on PyGame

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
import threading
import Queue

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
# for operation tokens for PUT
import basictoken as tk

if plat.system == 'Windows':
    # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
    # see https://bitbucket.org/pygame/pygame/issues/245/wrong-resolution-unless-you-use-ctypes
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        # old versions of Windows don't have this in user32.dll
        pass

# fallback to curses if not working
fallback = 'video_curses'

# Android-specific definitions
android = (plat.system == 'Android')
if android:
    numpy = None
    if pygame:
        import pygame_android


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
    force_display_size = config.get('dimensions')
    aspect = config.get('aspect') or aspect
    border_width = config.get('border')
    force_square_pixel = (config.get('scaling') == 'native')
    fullscreen = config.get('fullscreen')
    smooth = (config.get('scaling') == 'smooth')
    # don't catch Alt+F4
    noquit = config.get('nokill')
    # monitor choice
    mono_monitor =  config.get('monitor') == 'mono'
    # if no composite palette available for this card, ignore.
    composite_monitor = (config.get('monitor') == 'composite' and
                         config.get('video') in composite_640)
    if composite_monitor:
            composite_640_palette = composite_640[config.get('video')]
    # keyboard setting based on video card...
    if config.get('video') == 'tandy':
        # enable tandy F11, F12
        key_to_scan[pygame.K_F11] = scancode.F11
        key_to_scan[pygame.K_F12] = scancode.F12
    # fonts
    font_families = config.get('font')
    # mouse setups
    buttons = { 'left': 1, 'middle': 2, 'right': 3, 'none': -1 }
    mousebutton_copy = buttons[config.get('copy-paste')[0]]
    mousebutton_paste = buttons[config.get('copy-paste')[1]]
    mousebutton_pen = buttons[config.get('pen')]
    if not config.get('altgr'):
        # on Windows, AltGr key is reported as right-alt
        key_to_scan[pygame.K_RALT] = scancode.ALT
        # on Linux, AltGr is reported as mode key
        key_to_scan[pygame.K_MODE] = scancode.ALT
    # window caption/title
    caption = config.get('caption')


###############################################################################


def init():
    """ Initialise pygame interface. """
    global joysticks, physical_size, display_size
    global text_mode, fonts, state_loaded
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
        state_loaded = False
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]
    for j in joysticks:
        j.init()
    # if a joystick is present, its axes report 128 for mid, not 0
    for joy in range(len(joysticks)):
        for axis in (0, 1):
            backend.input_queue.put(backend.Event(backend.STICK_MOVED,
                                                  (joy, axis, 128)))
    # retrieve 8-pixel font from backend
    # also link as 9-pixel font for tandy
    fonts = { 8: backend.font_8, 9: backend.font_8 }
    if not load_fonts(backend.heights_needed):
        return False
    text_mode = True
    set_page(0, 0)
    launch_thread()
    return True

def close():
    """ Close the pygame interface. """
    if backend.video_queue:
        backend.video_queue.put(backend.Event(backend.VIDEO_QUIT))
        backend.video_queue.join()
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()
    # all messages are processed; shut down
    if android:
        pygame_android.close()
    # if pygame import failed, close() is called while pygame is None
    if pygame:
        pygame.joystick.quit()
        pygame.display.quit()


###############################################################################
# implementation

thread = None
tick_s = 0.024

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.start()

def consumer_thread():
    """ Video signal queue consumer thread. """
    while drain_video_queue():
        check_events()
        pygame.time.wait(cycle_time/blink_cycles/8)

def drain_video_queue():
    """ Drain signal queue. """
    alive = True
    while alive:
        try:
            signal = backend.video_queue.get(False)
        except Queue.Empty:
            return True
        if signal.event_type == backend.VIDEO_QUIT:
            # close thread after task_done
            alive = False
        elif signal.event_type == backend.VIDEO_MODE:
            init_screen_mode(signal.params)
        elif signal.event_type == backend.VIDEO_PUT_GLYPH:
            put_glyph(*signal.params)
        elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
            move_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_CLEAR_ROWS:
            clear_rows(*signal.params)
        elif signal.event_type == backend.VIDEO_SCROLL_UP:
            scroll(*signal.params)
        elif signal.event_type == backend.VIDEO_SCROLL_DOWN:
            scroll_down(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_PALETTE:
            update_palette(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CURSOR_SHAPE:
            build_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CURSOR_ATTR:
            update_cursor_attr(signal.params)
        elif signal.event_type == backend.VIDEO_SHOW_CURSOR:
            show_cursor(signal.params)
        elif signal.event_type == backend.VIDEO_MOVE_CURSOR:
            move_cursor(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_PAGE:
            set_page(*signal.params)
        elif signal.event_type == backend.VIDEO_COPY_PAGE:
            copy_page(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_BORDER_ATTR:
            set_border(signal.params)
        elif signal.event_type == backend.VIDEO_SET_COLORBURST:
            set_colorburst(*signal.params)
        elif signal.event_type == backend.VIDEO_BUILD_GLYPH:
            rebuild_glyph(signal.params)
        elif signal.event_type == backend.VIDEO_PUT_PIXEL:
            put_pixel(*signal.params)
        elif signal.event_type == backend.VIDEO_PUT_INTERVAL:
            put_interval(*signal.params)
        elif signal.event_type == backend.VIDEO_FILL_INTERVAL:
            fill_interval(*signal.params)
        elif signal.event_type == backend.VIDEO_PUT_RECT:
            put_rect(*signal.params)
        elif signal.event_type == backend.VIDEO_FILL_RECT:
            fill_rect(*signal.params)
        elif signal.event_type == backend.VIDEO_SET_CAPTION:
            set_caption_message(signal.params)
        backend.video_queue.task_done()


###############################################################################
# event queue

pause = False

def check_events():
    """ Handle screen and interface events. """
    global screen_changed, fullscreen, pause
    # wait for initialisation
    if not init_complete:
        return
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
                pause = False
                backend.input_queue.put(backend.Event(backend.KEYB_PAUSE, False))
        if event.type == pygame.KEYUP:
            if not pause:
                handle_key_up(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # copy, paste and pen may be on the same button, so no elifs
            if event.button == mousebutton_copy:
                # LEFT button: copy
                pos = normalise_pos(*event.pos)
                clipboard.start(1 + pos[1] // font_height,
                            1 + (pos[0]+font_width//2) // font_width)
            if event.button == mousebutton_paste:
                # MIDDLE button: paste
                clipboard.paste(mouse=True)
            if event.button == mousebutton_pen:
                # right mouse button is a pen press
                backend.input_queue.put(backend.Event(backend.PEN_DOWN,
                                                normalise_pos(*event.pos)))
        elif event.type == pygame.MOUSEBUTTONUP:
            backend.input_queue.put(backend.Event(backend.PEN_UP))
            if event.button == mousebutton_copy:
                clipboard.copy(mouse=True)
                clipboard.stop()
        elif event.type == pygame.MOUSEMOTION:
            pos = normalise_pos(*event.pos)
            backend.input_queue.put(backend.Event(backend.PEN_MOVED, pos))
            if clipboard.active():
                clipboard.move(1 + pos[1] // font_height,
                           1 + (pos[0]+font_width//2) // font_width)
        elif event.type == pygame.JOYBUTTONDOWN:
            backend.input_queue.put(backend.Event(backend.STICK_DOWN,
                                                  (event.joy, event.button)))
        elif event.type == pygame.JOYBUTTONUP:
            backend.input_queue.put(backend.Event(backend.STICK_UP,
                                                  (event.joy, event.button)))
        elif event.type == pygame.JOYAXISMOTION:
            backend.input_queue.put(backend.Event(backend.STICK_MOVED,
                                                  (event.joy, event.axis,
                                                  int(event.value*127 + 128))))
        elif event.type == pygame.VIDEORESIZE:
            fullscreen = False
            resize_display(event.w, event.h)
        elif event.type == pygame.QUIT:
            if noquit:
                set_caption_message('to exit type <CTRL+BREAK> <ESC> SYSTEM')
            else:
                backend.input_queue.put(backend.Event(backend.KEYB_QUIT))
    check_screen()

f12_active = False
f11_active = False

def handle_key_down(e):
    """ Handle key-down event. """
    global screen_changed, f12_active, f11_active, fullscreen, pause
    c = ''
    mods = pygame.key.get_mods()
    if ((e.key == pygame.K_NUMLOCK and mods & pygame.KMOD_CTRL) or
            (e.key in (pygame.K_PAUSE, pygame.K_BREAK) and
             not mods & pygame.KMOD_CTRL)):
        # pause until keypress
        backend.input_queue.put(backend.Event(backend.KEYB_PAUSE, True))
    elif e.key == pygame.K_MENU and android:
        # Android: toggle keyboard on menu key
        pygame_android.toggle_keyboard()
        screen_changed = True
    elif e.key == pygame.K_F11:
        f11_active = True
        clipboard.start()
    elif e.key == pygame.K_F12:
        f12_active = True
    elif f11_active:
        # F11+f to toggle fullscreen mode
        if e.key == pygame.K_f:
            fullscreen = not fullscreen
            resize_display(*find_display_size(size[0], size[1], border_width))
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
        if f12_active:
            # F12+P should just send Pause, but pause is still implemented directly
            if e.key == pygame.K_p:
                backend.input_queue.put(backend.Event(backend.KEYB_PAUSE, True))
            else:
                try:
                    scan, c = key_to_scan_f12[e.key]
                except KeyError:
                    scan = None
                backend.input_queue.put(backend.Event(backend.KEYB_DOWN, (scan, c)))
        else:
            try:
                scan = key_to_scan[e.key]
            except KeyError:
                scan = None
                if android:
                    # android hacks - send keystroke sequences
                    if e.key == pygame.K_ASTERISK:
                        backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                (scancode.RSHIFT, '')))
                        backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                (scancode.N8, '*')))
                        backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                scancode.RSHIFT))
                    elif e.key == pygame.K_AT:
                        backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                (scancode.RSHIFT, '')))
                        backend.input_queue.put(backend.Event(backend.KEYB_DOWN,
                                (scancode.N2, '@')))
                        backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                scancode.RSHIFT))
                if plat.system == 'Windows':
                    # Windows 7 and above send AltGr as Ctrl+RAlt
                    # if 'altgr' option is off, Ctrl+RAlt is sent.
                    # if 'altgr' is on, the RAlt key is being ignored
                    # but a Ctrl keydown event has already been sent
                    # so send keyup event to tell backend to release Ctrl modifier
                    if e.key == pygame.K_RALT:
                        backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                                              scancode.CTRL))
            # insert into keyboard queue
            backend.input_queue.put(backend.Event(backend.KEYB_DOWN, (scan, c)))

def handle_key_up(e):
    """ Handle key-up event. """
    global f12_active, f11_active
    if e.key == pygame.K_F11:
        clipboard.stop()
        f11_active = False
    elif e.key == pygame.K_F12:
        f12_active = False
    if not (f12_active and e.key in key_to_scan_f12):
        # last key released gets remembered
        try:
            backend.input_queue.put(backend.Event(backend.KEYB_UP,
                                                  key_to_scan[e.key]))
        except KeyError:
            pass


###############################################################################

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
display_slack = 15
# screen width and height in pixels
display_size = (640, 480)

fullscreen = False
smooth = False
# ignore ALT+F4 (and consequently window X button)
noquit = False

# letter shapes
glyphs = []

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
        pygame.K_LALT: scancode.ALT,
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

    key_to_scan_kplock = {
        pygame.K_0: (scancode.KP0, '0'),
        pygame.K_1: (scancode.KP1, '1'),
        pygame.K_2: (scancode.KP2, '2'),
        pygame.K_3: (scancode.KP3, '3'),
        pygame.K_4: (scancode.KP4, '4'),
        pygame.K_5: (scancode.KP5, '5'),
        pygame.K_6: (scancode.KP6, '6'),
        pygame.K_7: (scancode.KP7, '7'),
        pygame.K_8: (scancode.KP8, '8'),
        pygame.K_9: (scancode.KP9, '9'),
        pygame.K_PLUS: (scancode.KPPLUS, '+'),
        pygame.K_MINUS: (scancode.KPMINUS, '-'),
        pygame.K_LEFT: (scancode.KP4, '4'),
        pygame.K_RIGHT: (scancode.KP6, '6'),
        pygame.K_UP: (scancode.KP8, '8'),
        pygame.K_DOWN: (scancode.KP2, '2'),
    }

    key_to_scan_f12 = {
        pygame.K_b: (scancode.BREAK, ''),
        pygame.K_p: (scancode.BREAK, ''),
        pygame.K_n: (scancode.NUMLOCK, ''),
        pygame.K_s: (scancode.SCROLLOCK, ''),
        pygame.K_c: (scancode.CAPSLOCK, ''),
    }
    key_to_scan_f12.update(key_to_scan_kplock)


# cursor is visible
cursor_visible = True

# mouse button functions
mousebutton_copy = 1
mousebutton_paste = 2
mousebutton_pen = 3

# initialisation complete
init_complete = False

####################################
# initialisation


def load_fonts(heights_needed):
    """ Load font typefaces. """
    for height in reversed(sorted(heights_needed)):
        if height in fonts:
            # already force loaded
            continue
        # load a Unifont .hex font and take the codepage subset
        fonts[height] = typeface.load(font_families, height,
                                      unicodepage.cp_to_unicodepoint)
        # fix missing code points font based on 16-line font
        if 16 not in fonts:
            # if available, load the 16-pixel font unrequested
            font_16 = typeface.load(font_families, 16,
                                    unicodepage.cp_to_unicodepoint, nowarn=True)
            if font_16:
                fonts[16] = font_16
        if 16 in fonts and fonts[16]:
            typeface.fixfont(height, fonts[height],
                             unicodepage.cp_to_unicodepoint, fonts[16])
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
    global init_complete
    if mode_info.font_height not in fonts or not fonts[mode_info.font_height]:
        logging.warning(
            'No %d-pixel font available. Could not enter video mode %s.',
            mode_info.font_height, mode_info.name)
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
    resize_display(*find_display_size(size[0], size[1], border_width))
    # set standard cursor
    build_cursor(font_width, font_height, 0, font_height)
    # whole screen (blink on & off)
    canvas = [ pygame.Surface(size, depth=8) for _ in range(num_pages)]
    for i in range(num_pages):
        canvas[i].set_palette(workpalette)
    # initialise clipboard
    clipboard = ClipboardInterface(mode_info.width, mode_info.height)
    screen_changed = True
    # signal that initialisation is complete
    init_complete = True
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
        # leave part of the screen either direction unused
        # to account for task bars, window decorations, etc.
        xmult = max(1, int((100.-display_slack) * physical_size[0] / (100.*pixel_x)))
        ymult = max(1, int((100.-display_slack) * physical_size[1] / (100.*pixel_y)))
        # find the multipliers mx <= xmult, my <= ymult
        # such that mx * pixel_x / my * pixel_y
        # is multiplicatively closest to aspect[0] / aspect[1]
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
    if fullscreen:
        flags |= pygame.FULLSCREEN | pygame.NOFRAME
        if (not initial and not text_mode):
            width, height = display_size
        # scale suggested dimensions to largest integer times pixel size that fits
        scale = min( physical_size[0]//width, physical_size[1]//height )
        width, height = width * scale, height * scale
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
    okfont = { 'O': '\x00\x7C\xC6\xC6\xC6\xC6\xC6\x7C', 'k': '\x00\xE0\x60\x66\x6C\x78\x6C\xE6' }
    O = build_glyph('O', okfont, 8, 8)
    k = build_glyph('k', okfont, 8, 8)
    icon.blit(O, (1, 0, 8, 8))
    icon.blit(k, (9, 0, 8, 8))
    icon.set_palette_at(255, (0, 0, 0))
    icon.set_palette_at(254, (0xff, 0xff, 0xff))
    pygame.transform.scale2x(icon)
    pygame.transform.scale2x(icon)
    return icon

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

def clear_rows(back_attr, start, stop):
    """ Clear a range of screen rows. """
    global screen_changed
    bg = (0, 0, back_attr)
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

def show_cursor(cursor_on):
    """ Change visibility of cursor. """
    global screen_changed, cursor_visible
    cursor_visible = cursor_on
    screen_changed = True

def move_cursor(crow, ccol):
    """ Move the cursor to a new position. """
    global cursor_row, cursor_col
    cursor_row, cursor_col = crow, ccol

def update_cursor_attr(attr):
    global cursor_attr
    """ Change attribute of cursor. """
    cursor_attr = canvas[vpagenum].get_palette_at(attr).b
    cursor.set_palette_at(254, pygame.Color(0, cursor_attr, cursor_attr))

def scroll(from_line, scroll_height, back_attr):
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
    bg = (0, 0, back_attr)
    canvas[apagenum].fill(bg, (0, (scroll_height-1) * font_height,
                               size[0], font_height))
    canvas[apagenum].set_clip(None)
    screen_changed = True

def scroll_down(from_line, scroll_height, back_attr):
    """ Scroll the screen down between from_line and scroll_height. """
    global screen_changed
    temp_scroll_area = pygame.Rect(0, (from_line-1) * font_height, size[0],
                                   (scroll_height-from_line+1) * font_height)
    canvas[apagenum].set_clip(temp_scroll_area)
    canvas[apagenum].scroll(0, font_height)
    # empty new line
    bg = (0, 0, back_attr)
    canvas[apagenum].fill(bg, (0, (from_line-1) * font_height,
                                  size[0], font_height))
    canvas[apagenum].set_clip(None)
    screen_changed = True

def put_glyph(pagenum, row, col, c, fore, back, blink, underline, for_keys):
    """ Put a single-byte character at a given position. """
    global screen_changed
    color, bg = (0, 0, fore + 16*back + 128*blink), (0, 0, back)
    x0, y0 = (col-1)*font_width, (row-1)*font_height
    if c == '\0':
        # guaranteed to be blank, saves time on some BLOADs
        canvas[pagenum].fill(bg, (x0, y0, font_width, font_height))
    else:
        if len(c) == 1:
            glyph = glyphs[ord(c)]
        else:
            glyph = build_glyph(c, font, 2*font_width, font_height)
        if glyph.get_palette_at(255) != bg:
            glyph.set_palette_at(255, bg)
        if glyph.get_palette_at(254) != color:
            glyph.set_palette_at(254, color)
        canvas[pagenum].blit(glyph, (x0, y0))
    if mode_has_underline and underline:
        for xx in range(font_width):
            canvas[pagenum].set_at((x0 + xx, y0 + font_height - 1), color)
    screen_changed = True

# ascii codepoints for which to repeat column 8 in column 9 (box drawing)
# Many internet sources say this should be 0xC0--0xDF. However, that would
# exclude the shading characters. It appears to be traced back to a mistake in
# IBM's VGA docs. See https://01.org/linuxgraphics/sites/default/files/documentation/ilk_ihd_os_vol3_part1r2.pdf
carry_col_9 = [chr(c) for c in range(0xb0, 0xdf+1)]
# ascii codepoints for which to repeat row 8 in row 9 (box drawing)
carry_row_9 = [chr(c) for c in range(0xb0, 0xdf+1)]

def rebuild_glyph(ordval):
    """ Rebuild a glyph after POKE. """
    if font_height == 8:
        glyphs[ordval] = build_glyph(chr(ordval), font, font_width, 8)


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

def set_caption_message(msg):
    """ Add a message to the window caption. """
    if msg:
        pygame.display.set_caption(caption + ' - ' + msg)
    else:
        pygame.display.set_caption(caption)


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
        if cursor_fixed_attr is not None:
            index = cursor_fixed_attr
        else:
            index = cursor_attr & 0xf
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
                    pixel = canvas[vpagenum].get_at((x,y)).b
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
# clipboard handling

class ClipboardInterface(object):
    """ Clipboard user interface. """

    def __init__(self, width, height):
        """ Initialise clipboard feedback handler. """
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        self.width = width
        self.height = height

    def active(self):
        """ True if clipboard mode is active. """
        return self._active

    def start(self, r=None, c=None):
        """ Enter clipboard mode (clipboard key pressed). """
        self._active = True
        if r is None or c is None:
            self.select_start = [cursor_row, cursor_col]
            self.select_stop = [cursor_row, cursor_col]
        else:
            self.select_start = [r, c]
            self.select_stop = [r, c]
        self.selection_rect = []

    def stop(self):
        """ Leave clipboard mode (clipboard key released). """
        global screen_changed
        self._active = False
        self.select_start = None
        self.select_stop = None
        self.selection_rect = None
        screen_changed = True

    def copy(self, mouse=False):
        """ Copy screen characters from selection into clipboard. """
        start, stop = self.select_start, self.select_stop
        if not start or not stop:
            return
        if start[0] == stop[0] and start[1] == stop[1]:
            return
        if start[0] > stop[0] or (start[0] == stop[0] and start[1] > stop[1]):
            start, stop = stop, start
        backend.input_queue.put(backend.Event(backend.CLIP_COPY,
                            (start[0], start[1], stop[0], stop[1]-1, mouse)))

    def paste(self, mouse=False):
        """ Paste from clipboard into keyboard buffer. """
        backend.input_queue.put(backend.Event(backend.CLIP_PASTE, mouse))

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
        """ Handle keyboard clipboard commands. """
        global screen_changed
        if not self._active:
            return
        if e.unicode.upper() ==  u'C':
            self.copy()
        elif e.unicode.upper() == u'V':
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

def fill_rect(x0, y0, x1, y1, index):
    """ Fill a rectangle in a solid attribute. """
    global screen_changed
    rect = pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)
    canvas[apagenum].fill(index, rect)
    screen_changed = True

def fill_interval(x0, x1, y, index):
    """ Fill a scanline interval in a solid attribute. """
    global screen_changed
    dx = x1 - x0 + 1
    canvas[apagenum].fill(index, (x0, y, dx, 1))
    screen_changed = True

if numpy:
    def put_interval(pagenum, x, y, colours):
        """ Write a list of attributes to a scanline interval. """
        global screen_changed
        # reference the interval on the canvas
        pygame.surfarray.pixels2d(canvas[pagenum])[x:x+len(colours), y] = numpy.array(colours).astype(int)
        screen_changed = True

    def put_rect(x0, y0, x1, y1, array):
        """ Apply numpy array [y][x] of attribytes to an area. """
        global screen_changed
        if (x1 < x0) or (y1 < y0):
            return
        # reference the destination area
        pygame.surfarray.pixels2d(
            canvas[apagenum].subsurface(pygame.Rect(x0, y0, x1-x0+1, y1-y0+1)))[:] = numpy.array(array).T
        screen_changed = True

else:
    def put_interval(pagenum, x, y, colours, mask=0xff):
        """ Write a list of attributes to a scanline interval. """
        global screen_changed
        # list comprehension and ignoring result seems faster than loop
        [canvas[pagenum].set_at((x+i, y), index)
                         for i, index in enumerate(colours)]
        screen_changed = True

    def put_rect(x0, y0, x1, y1, array):
        """ Apply a 2D list [y][x] of attributes to an area. """
        global screen_changed
        [[ canvas[apagenum].set_at((x0+i, y0+j), index)
                            for i, index in enumerate(array[j]) ]
                            for j in xrange(y1-y0+1) ]
        screen_changed = True


prepare()
