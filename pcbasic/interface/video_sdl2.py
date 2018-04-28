"""
PC-BASIC - video_sdl2.py
Graphical interface based on PySDL2

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import ctypes
import os
import sys
from collections import Counter
from ctypes import POINTER, c_int, c_double

try:
    import numpy
except ImportError:
    numpy = None

from ..compat import WIN32, BASE_DIR, PLATFORM
from .base import EnvironmentCache

# platform-specific dll location
LIB_DIR = os.path.join(BASE_DIR, 'lib', PLATFORM)

# look for SDL2.dll / libSDL2.dylib / libSDL2.so:
# first in LIB_DIR, then in the standard search path
# if not found, in LIB_DIR

# look in LIB_DIR first, user can remove if they want to use standard one
_sdl_env = EnvironmentCache()
_sdl_env.set('PYSDL2_DLL_PATH', LIB_DIR)
try:
    from . import sdl2
except ImportError:
    _sdl_env.set('PYSDL2_DLL_PATH', '')
    try:
        from . import sdl2
    except ImportError:
        sdl2 = None

# look for SDL2_gfx.dll:
# first in SDL2.dll location
# if not found, in LIB_DIR; then in standard search path
GFX_NAMES = ['SDL2_gfx', 'SDL2_gfx-1.0']
try:
    sdlgfx = sdl2.DLL('SDL2_gfx', GFX_NAMES, os.path.dirname(sdl2.dll.libfile))
except Exception:
    try:
        sdlgfx = sdl2.DLL('SDL2_gfx', GFX_NAMES, LIB_DIR)
    except Exception:
        try:
            sdlgfx = sdl2.DLL('SDL2_gfx', GFX_NAMES)
        except Exception:
            sdlgfx = None

if sdlgfx:
    SMOOTHING_ON = 1
    zoomSurface = sdlgfx.bind_function(
            'zoomSurface',
            [POINTER(sdl2.SDL_Surface), c_double, c_double, c_int], POINTER(sdl2.SDL_Surface)
        )

from .base import video_plugins, InitFailed, NOKILL_MESSAGE
from ..basic.base import signals
from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea
from ..data.resources import ICON
from .video import VideoPlugin
from . import window
from . import clipboard


###############################################################################
# video settings

# refresh cycle parameters
# number of cycles to change blink state
BLINK_CYCLES = 5
# ms duration of a blink
BLINK_TIME = 120
CYCLE_TIME = BLINK_TIME // BLINK_CYCLES


###############################################################################
# keyboard codes

if sdl2:
    # these are PC keyboard scancodes
    SCAN_TO_SCAN = {
        # top row
        sdl2.SDL_SCANCODE_ESCAPE: scancode.ESCAPE, sdl2.SDL_SCANCODE_1: scancode.N1,
        sdl2.SDL_SCANCODE_2: scancode.N2, sdl2.SDL_SCANCODE_3: scancode.N3,
        sdl2.SDL_SCANCODE_4: scancode.N4, sdl2.SDL_SCANCODE_5: scancode.N5,
        sdl2.SDL_SCANCODE_6: scancode.N6, sdl2.SDL_SCANCODE_7: scancode.N7,
        sdl2.SDL_SCANCODE_8: scancode.N8, sdl2.SDL_SCANCODE_9: scancode.N9,
        sdl2.SDL_SCANCODE_0: scancode.N0, sdl2.SDL_SCANCODE_MINUS: scancode.MINUS,
        sdl2.SDL_SCANCODE_EQUALS: scancode.EQUALS,
        sdl2.SDL_SCANCODE_BACKSPACE: scancode.BACKSPACE,
        # row 1
        sdl2.SDL_SCANCODE_TAB: scancode.TAB, sdl2.SDL_SCANCODE_Q: scancode.q,
        sdl2.SDL_SCANCODE_W: scancode.w, sdl2.SDL_SCANCODE_E: scancode.e, sdl2.SDL_SCANCODE_R: scancode.r,
        sdl2.SDL_SCANCODE_T: scancode.t, sdl2.SDL_SCANCODE_Y: scancode.y, sdl2.SDL_SCANCODE_U: scancode.u,
        sdl2.SDL_SCANCODE_I: scancode.i, sdl2.SDL_SCANCODE_O: scancode.o, sdl2.SDL_SCANCODE_P: scancode.p,
        sdl2.SDL_SCANCODE_LEFTBRACKET: scancode.LEFTBRACKET,
        sdl2.SDL_SCANCODE_RIGHTBRACKET: scancode.RIGHTBRACKET,
        sdl2.SDL_SCANCODE_RETURN: scancode.RETURN, sdl2.SDL_SCANCODE_KP_ENTER: scancode.RETURN,
        # row 2
        sdl2.SDL_SCANCODE_RCTRL: scancode.CTRL, sdl2.SDL_SCANCODE_LCTRL: scancode.CTRL,
        sdl2.SDL_SCANCODE_A: scancode.a, sdl2.SDL_SCANCODE_S: scancode.s, sdl2.SDL_SCANCODE_D: scancode.d,
        sdl2.SDL_SCANCODE_F: scancode.f, sdl2.SDL_SCANCODE_G: scancode.g, sdl2.SDL_SCANCODE_H: scancode.h,
        sdl2.SDL_SCANCODE_J: scancode.j, sdl2.SDL_SCANCODE_K: scancode.k, sdl2.SDL_SCANCODE_L: scancode.l,
        sdl2.SDL_SCANCODE_SEMICOLON: scancode.SEMICOLON, sdl2.SDL_SCANCODE_APOSTROPHE: scancode.QUOTE,
        sdl2.SDL_SCANCODE_GRAVE: scancode.BACKQUOTE,
        # row 3
        sdl2.SDL_SCANCODE_LSHIFT: scancode.LSHIFT,
        sdl2.SDL_SCANCODE_BACKSLASH: scancode.BACKSLASH,
        sdl2.SDL_SCANCODE_Z: scancode.z, sdl2.SDL_SCANCODE_X: scancode.x, sdl2.SDL_SCANCODE_C: scancode.c,
        sdl2.SDL_SCANCODE_V: scancode.v, sdl2.SDL_SCANCODE_B: scancode.b, sdl2.SDL_SCANCODE_N: scancode.n,
        sdl2.SDL_SCANCODE_M: scancode.m, sdl2.SDL_SCANCODE_COMMA: scancode.COMMA,
        sdl2.SDL_SCANCODE_PERIOD: scancode.PERIOD, sdl2.SDL_SCANCODE_SLASH: scancode.SLASH,
        sdl2.SDL_SCANCODE_RSHIFT: scancode.RSHIFT,
        sdl2.SDL_SCANCODE_SYSREQ: scancode.SYSREQ,
        sdl2.SDL_SCANCODE_LALT: scancode.ALT,
        # don't catch right-Alt as it may inhibit AltGr on Windows
        # sdl2.SDL_SCANCODE_RALT: scancode.ALT,
        sdl2.SDL_SCANCODE_SPACE: scancode.SPACE, sdl2.SDL_SCANCODE_CAPSLOCK: scancode.CAPSLOCK,
        # function keys
        sdl2.SDL_SCANCODE_F1: scancode.F1, sdl2.SDL_SCANCODE_F2: scancode.F2,
        sdl2.SDL_SCANCODE_F3: scancode.F3, sdl2.SDL_SCANCODE_F4: scancode.F4,
        sdl2.SDL_SCANCODE_F5: scancode.F5, sdl2.SDL_SCANCODE_F6: scancode.F6,
        sdl2.SDL_SCANCODE_F7: scancode.F7, sdl2.SDL_SCANCODE_F8: scancode.F8,
        sdl2.SDL_SCANCODE_F9: scancode.F9, sdl2.SDL_SCANCODE_F10: scancode.F10,
        sdl2.SDL_SCANCODE_F11: scancode.F11, sdl2.SDL_SCANCODE_F12: scancode.F12,
        # top of keypad
        sdl2.SDL_SCANCODE_NUMLOCKCLEAR: scancode.NUMLOCK,
        sdl2.SDL_SCANCODE_SCROLLLOCK: scancode.SCROLLOCK,
        sdl2.SDL_SCANCODE_PAUSE: scancode.BREAK,
        # keypad
        sdl2.SDL_SCANCODE_KP_MULTIPLY: scancode.KPTIMES,
        sdl2.SDL_SCANCODE_PRINTSCREEN: scancode.PRINT,
        sdl2.SDL_SCANCODE_KP_7: scancode.KP7,
        sdl2.SDL_SCANCODE_HOME: scancode.HOME,
        sdl2.SDL_SCANCODE_KP_8: scancode.KP8,
        sdl2.SDL_SCANCODE_UP: scancode.UP,
        sdl2.SDL_SCANCODE_KP_9: scancode.KP9,
        sdl2.SDL_SCANCODE_PAGEUP: scancode.PAGEUP,
        sdl2.SDL_SCANCODE_KP_MINUS: scancode.KPMINUS,
        sdl2.SDL_SCANCODE_KP_4: scancode.KP4,
        sdl2.SDL_SCANCODE_LEFT: scancode.LEFT,
        sdl2.SDL_SCANCODE_KP_5: scancode.KP5,
        sdl2.SDL_SCANCODE_KP_6: scancode.KP6,
        sdl2.SDL_SCANCODE_RIGHT: scancode.RIGHT,
        sdl2.SDL_SCANCODE_KP_PLUS: scancode.KPPLUS,
        sdl2.SDL_SCANCODE_KP_1: scancode.KP1,
        sdl2.SDL_SCANCODE_END: scancode.END,
        sdl2.SDL_SCANCODE_KP_2: scancode.KP2,
        sdl2.SDL_SCANCODE_DOWN: scancode.DOWN,
        sdl2.SDL_SCANCODE_KP_3: scancode.KP3,
        sdl2.SDL_SCANCODE_PAGEDOWN: scancode.PAGEDOWN,
        sdl2.SDL_SCANCODE_KP_0: scancode.KP0,
        sdl2.SDL_SCANCODE_INSERT: scancode.INSERT,
        sdl2.SDL_SCANCODE_KP_PERIOD: scancode.KPPOINT,
        sdl2.SDL_SCANCODE_DELETE: scancode.DELETE,
        # extensions
        sdl2.SDL_SCANCODE_NONUSBACKSLASH: scancode.INT1,
        # windows keys
        sdl2.SDL_SCANCODE_LGUI: scancode.LSUPER,
        sdl2.SDL_SCANCODE_RGUI: scancode.RSUPER,
        sdl2.SDL_SCANCODE_MENU: scancode.MENU,
        # Japanese keyboards
        # mapping to SDL scancodes unknown
        #HIRAGANA_KATAKANA = 0x70
        # backslash/underscore on Japanese keyboard
        #INT3 = 0x73
        #HENKAN = 0x79
        # this is a guess based on https://wiki.libsdl.org/SDL_Scancode
        # and http://www.quadibloc.com/comp/scan.htm
        sdl2.SDL_SCANCODE_LANG4: scancode.MUHENKAN,
        sdl2.SDL_SCANCODE_LANG5: scancode.ZENKAKU_HANKAKU,
        sdl2.SDL_SCANCODE_INTERNATIONAL3: scancode.INT4,
        # Korean keyboards
        sdl2.SDL_SCANCODE_LANG2: scancode.HANJA,
        sdl2.SDL_SCANCODE_LANG1: scancode.HAN_YEONG,
    }

    KEY_TO_EASCII = {
        sdl2.SDLK_F1: uea.F1,
        sdl2.SDLK_F2: uea.F2,
        sdl2.SDLK_F3: uea.F3,
        sdl2.SDLK_F4: uea.F4,
        sdl2.SDLK_F5: uea.F5,
        sdl2.SDLK_F6: uea.F6,
        sdl2.SDLK_F7: uea.F7,
        sdl2.SDLK_F8: uea.F8,
        sdl2.SDLK_F9: uea.F9,
        sdl2.SDLK_F10: uea.F10,
        sdl2.SDLK_F11: uea.F11,
        sdl2.SDLK_F12: uea.F12,
        sdl2.SDLK_HOME: uea.HOME,
        sdl2.SDLK_UP: uea.UP,
        sdl2.SDLK_PAGEUP: uea.PAGEUP,
        sdl2.SDLK_LEFT: uea.LEFT,
        sdl2.SDLK_RIGHT: uea.RIGHT,
        sdl2.SDLK_END: uea.END,
        sdl2.SDLK_DOWN: uea.DOWN,
        sdl2.SDLK_PAGEDOWN: uea.PAGEDOWN,
        sdl2.SDLK_ESCAPE: uea.ESCAPE,
        sdl2.SDLK_BACKSPACE: uea.BACKSPACE,
        sdl2.SDLK_TAB: uea.TAB,
        sdl2.SDLK_RETURN: uea.RETURN,
        sdl2.SDLK_KP_ENTER: uea.RETURN,
        sdl2.SDLK_SPACE: uea.SPACE,
        sdl2.SDLK_INSERT: uea.INSERT,
        sdl2.SDLK_DELETE: uea.DELETE,
    }

    SHIFT_KEY_TO_EASCII = {
        sdl2.SDLK_F1: uea.SHIFT_F1,
        sdl2.SDLK_F2: uea.SHIFT_F2,
        sdl2.SDLK_F3: uea.SHIFT_F3,
        sdl2.SDLK_F4: uea.SHIFT_F4,
        sdl2.SDLK_F5: uea.SHIFT_F5,
        sdl2.SDLK_F6: uea.SHIFT_F6,
        sdl2.SDLK_F7: uea.SHIFT_F7,
        sdl2.SDLK_F8: uea.SHIFT_F8,
        sdl2.SDLK_F9: uea.SHIFT_F9,
        sdl2.SDLK_F10: uea.SHIFT_F10,
        sdl2.SDLK_F11: uea.SHIFT_F11,
        sdl2.SDLK_F12: uea.SHIFT_F12,
        sdl2.SDLK_HOME: uea.SHIFT_HOME,
        sdl2.SDLK_UP: uea.SHIFT_UP,
        sdl2.SDLK_PAGEUP: uea.SHIFT_PAGEUP,
        sdl2.SDLK_LEFT: uea.SHIFT_LEFT,
        sdl2.SDLK_RIGHT: uea.SHIFT_RIGHT,
        sdl2.SDLK_END: uea.SHIFT_END,
        sdl2.SDLK_DOWN: uea.SHIFT_DOWN,
        sdl2.SDLK_PAGEDOWN: uea.SHIFT_PAGEDOWN,
        sdl2.SDLK_ESCAPE: uea.SHIFT_ESCAPE,
        sdl2.SDLK_BACKSPACE: uea.SHIFT_BACKSPACE,
        sdl2.SDLK_TAB: uea.SHIFT_TAB,
        sdl2.SDLK_RETURN: uea.SHIFT_RETURN,
        sdl2.SDLK_KP_ENTER: uea.SHIFT_RETURN,
        sdl2.SDLK_SPACE: uea.SHIFT_SPACE,
        sdl2.SDLK_INSERT: uea.SHIFT_INSERT,
        sdl2.SDLK_DELETE: uea.SHIFT_DELETE,
        sdl2.SDLK_KP_5: uea.SHIFT_KP5,
    }

    CTRL_KEY_TO_EASCII = {
        sdl2.SDLK_F1: uea.CTRL_F1,
        sdl2.SDLK_F2: uea.CTRL_F2,
        sdl2.SDLK_F3: uea.CTRL_F3,
        sdl2.SDLK_F4: uea.CTRL_F4,
        sdl2.SDLK_F5: uea.CTRL_F5,
        sdl2.SDLK_F6: uea.CTRL_F6,
        sdl2.SDLK_F7: uea.CTRL_F7,
        sdl2.SDLK_F8: uea.CTRL_F8,
        sdl2.SDLK_F9: uea.CTRL_F9,
        sdl2.SDLK_F10: uea.CTRL_F10,
        sdl2.SDLK_F11: uea.CTRL_F11,
        sdl2.SDLK_F12: uea.CTRL_F12,
        sdl2.SDLK_HOME: uea.CTRL_HOME,
        sdl2.SDLK_PAGEUP: uea.CTRL_PAGEUP,
        sdl2.SDLK_LEFT: uea.CTRL_LEFT,
        sdl2.SDLK_RIGHT: uea.CTRL_RIGHT,
        sdl2.SDLK_END: uea.CTRL_END,
        sdl2.SDLK_PAGEDOWN: uea.CTRL_PAGEDOWN,
        sdl2.SDLK_ESCAPE: uea.CTRL_ESCAPE,
        sdl2.SDLK_BACKSPACE: uea.CTRL_BACKSPACE,
        sdl2.SDLK_TAB: uea.CTRL_TAB,
        sdl2.SDLK_RETURN: uea.CTRL_RETURN,
        sdl2.SDLK_KP_ENTER: uea.CTRL_RETURN,
        sdl2.SDLK_SPACE: uea.CTRL_SPACE,
        sdl2.SDLK_PRINTSCREEN: uea.CTRL_PRINT,
        sdl2.SDLK_2: uea.CTRL_2,
        sdl2.SDLK_6: uea.CTRL_6,
        sdl2.SDLK_MINUS: uea.CTRL_MINUS,
    }

    ALT_SCAN_TO_EASCII = {
        sdl2.SDL_SCANCODE_1: uea.ALT_1,
        sdl2.SDL_SCANCODE_2: uea.ALT_2,
        sdl2.SDL_SCANCODE_3: uea.ALT_3,
        sdl2.SDL_SCANCODE_4: uea.ALT_4,
        sdl2.SDL_SCANCODE_5: uea.ALT_5,
        sdl2.SDL_SCANCODE_6: uea.ALT_6,
        sdl2.SDL_SCANCODE_7: uea.ALT_7,
        sdl2.SDL_SCANCODE_8: uea.ALT_8,
        sdl2.SDL_SCANCODE_9: uea.ALT_9,
        sdl2.SDL_SCANCODE_0: uea.ALT_0,
        sdl2.SDL_SCANCODE_MINUS: uea.ALT_MINUS,
        sdl2.SDL_SCANCODE_EQUALS: uea.ALT_EQUALS,
        sdl2.SDL_SCANCODE_Q: uea.ALT_q,
        sdl2.SDL_SCANCODE_W: uea.ALT_w,
        sdl2.SDL_SCANCODE_E: uea.ALT_e,
        sdl2.SDL_SCANCODE_R: uea.ALT_r,
        sdl2.SDL_SCANCODE_T: uea.ALT_t,
        sdl2.SDL_SCANCODE_Y: uea.ALT_y,
        sdl2.SDL_SCANCODE_U: uea.ALT_u,
        sdl2.SDL_SCANCODE_I: uea.ALT_i,
        sdl2.SDL_SCANCODE_O: uea.ALT_o,
        sdl2.SDL_SCANCODE_P: uea.ALT_p,
        sdl2.SDL_SCANCODE_A: uea.ALT_a,
        sdl2.SDL_SCANCODE_S: uea.ALT_s,
        sdl2.SDL_SCANCODE_D: uea.ALT_d,
        sdl2.SDL_SCANCODE_F: uea.ALT_f,
        sdl2.SDL_SCANCODE_G: uea.ALT_g,
        sdl2.SDL_SCANCODE_H: uea.ALT_h,
        sdl2.SDL_SCANCODE_J: uea.ALT_j,
        sdl2.SDL_SCANCODE_K: uea.ALT_k,
        sdl2.SDL_SCANCODE_L: uea.ALT_l,
        sdl2.SDL_SCANCODE_Z: uea.ALT_z,
        sdl2.SDL_SCANCODE_X: uea.ALT_x,
        sdl2.SDL_SCANCODE_C: uea.ALT_c,
        sdl2.SDL_SCANCODE_V: uea.ALT_v,
        sdl2.SDL_SCANCODE_B: uea.ALT_b,
        sdl2.SDL_SCANCODE_N: uea.ALT_n,
        sdl2.SDL_SCANCODE_M: uea.ALT_m,
        sdl2.SDL_SCANCODE_F1: uea.ALT_F1,
        sdl2.SDL_SCANCODE_F2: uea.ALT_F2,
        sdl2.SDL_SCANCODE_F3: uea.ALT_F3,
        sdl2.SDL_SCANCODE_F4: uea.ALT_F4,
        sdl2.SDL_SCANCODE_F5: uea.ALT_F5,
        sdl2.SDL_SCANCODE_F6: uea.ALT_F6,
        sdl2.SDL_SCANCODE_F7: uea.ALT_F7,
        sdl2.SDL_SCANCODE_F8: uea.ALT_F8,
        sdl2.SDL_SCANCODE_F9: uea.ALT_F9,
        sdl2.SDL_SCANCODE_F10: uea.ALT_F10,
        sdl2.SDL_SCANCODE_F11: uea.ALT_F11,
        sdl2.SDL_SCANCODE_F12: uea.ALT_F12,
        sdl2.SDL_SCANCODE_BACKSPACE: uea.ALT_BACKSPACE,
        sdl2.SDL_SCANCODE_TAB: uea.ALT_TAB,
        sdl2.SDL_SCANCODE_RETURN: uea.ALT_RETURN,
        sdl2.SDL_SCANCODE_KP_ENTER: uea.ALT_RETURN,
        sdl2.SDL_SCANCODE_SPACE: uea.ALT_SPACE,
        sdl2.SDL_SCANCODE_PRINTSCREEN: uea.ALT_PRINT,
        sdl2.SDL_SCANCODE_KP_5: uea.ALT_KP5,
    }

    MOD_TO_SCAN = {
        sdl2.KMOD_LSHIFT: scancode.LSHIFT,
        sdl2.KMOD_RSHIFT: scancode.RSHIFT,
        sdl2.KMOD_LCTRL: scancode.CTRL,
        sdl2.KMOD_RCTRL: scancode.CTRL,
        sdl2.KMOD_LALT: scancode.ALT,
        # don't catch right-Alt as it may inhibit AltGr on Windows
        #sdl2.KMOD_RALT: scancode.ALT,
    }


###############################################################################
# clipboard handling


class SDL2Clipboard(clipboard.Clipboard):
    """Clipboard handling interface using SDL2."""

    def __init__(self):
        """Initialise the clipboard handler."""
        self.ok = (sdl2 is not None)

    def copy(self, text, mouse=False):
        """Put unicode text on clipboard."""
        sdl2.SDL_SetClipboardText(text.encode('utf-8', errors='replace'))

    def paste(self, mouse=False):
        """Return unicode text from clipboard."""
        text = sdl2.SDL_GetClipboardText()
        if text is None:
            return u''
        return text.decode('utf-8', 'replace').replace(u'\r\n', u'\n').replace(u'\n', u'\r')


###############################################################################

def _pixels2d(psurface):
    """Creates a 2D pixel array view of the passed 8-bit surface."""
    # limited, specialised version of pysdl2.ext.pixels2d by Marcus von Appen
    # original is CC0 public domain with zlib fallback licence
    # https://bitbucket.org/marcusva/py-sdl2
    strides = (psurface.pitch, 1)
    srcsize = psurface.h * psurface.pitch
    shape = psurface.h, psurface.w
    pxbuf = ctypes.cast(psurface.pixels, ctypes.POINTER(ctypes.c_ubyte * srcsize)).contents
    # NOTE: transpose() brings it on [x][y] form - we may prefer [y][x] instead
    return numpy.ndarray(shape, numpy.uint8, pxbuf, 0, strides, "C").transpose()


###############################################################################
# video plugin

@video_plugins.register('sdl2')
class VideoSDL2(VideoPlugin):
    """SDL2-based graphical interface."""

    def __init__(
            self, input_queue, video_queue,
            caption=u'', icon=ICON,
            scaling=None, dimensions=None, aspect_ratio=(4, 3), border_width=0, fullscreen=False,
            alt_f4_quits=True, mouse_clipboard=True,
            **kwargs):
        """Initialise SDL2 interface."""
        if not sdl2:
            raise InitFailed('Module `sdl2` not found')
        if not numpy:
            raise InitFailed('Module `numpy` not found')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # request smooth scaling
        self._smooth = scaling == 'smooth'
        # ignore ALT+F4 and window X button
        self._nokill = not alt_f4_quits
        # window caption/title
        self._caption = caption
        # start in fullscreen mode if True
        self._fullscreen = fullscreen
        # display & border
        # border attribute
        self._border_attr = 0
        # palette and colours
        # composite colour artifacts are active
        self._composite = False
        # update cycle
        self._cycle = 0
        self._last_tick = 0
        # cursor
        # current cursor location
        self._last_row, self._last_col = 1, 1
        # cursor is visible
        self._cursor_visible = True
        # load the icon
        self._icon = icon
        # mouse setups
        self._mouse_clip = mouse_clipboard
        # keyboard setup
        self._f11_active = False
        # we need a set_mode call to be really up and running
        self._has_window = False
        # ensure the correct SDL2 video driver is chosen for Windows
        # since this gets messed up if we also import pygame
        self._env = EnvironmentCache()
        if WIN32:
            self._env.set('SDL_VIDEODRIVER', 'windows')
        # initialise SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_EVERYTHING):
            # SDL not initialised correctly
            # reset the environment variable
            # to not throw PyGame off if we try that later
            self._env.close()
            raise InitFailed('Could not initialise SDL2: %s' % sdl2.SDL_GetError())
        display_mode = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetCurrentDisplayMode(0, ctypes.byref(display_mode))
        self._window_sizer = window.WindowSizer(
                display_mode.w, display_mode.h,
                scaling, dimensions, aspect_ratio, border_width, fullscreen)
        # create the window initially as 640*400 black
        # "NOTE: You should not expect to be able to create a window, render,
        #        or receive events on any thread other than the main one"
        # https://wiki.libsdl.org/CategoryThread
        # http://stackoverflow.com/questions/27751533/sdl2-threading-seg-fault
        self._display = None
        self._work_surface = None
        self._do_create_window(*self._window_sizer.find_display_size(720, 400))
        # pop up as black rather than background, looks nicer
        sdl2.SDL_UpdateWindowSurface(self._display)
        # workaround for duplicated keypresses after Alt (at least on Ubuntu Unity)
        self._alt_counter = Counter()
        self._clipboard_handler = None

    def __enter__(self):
        """Complete SDL2 interface initialisation."""
        # set clipboard handler to SDL2
        self._clipboard_handler = SDL2Clipboard()
        # display palettes for blink states 0, 1
        self._palette = [sdl2.SDL_AllocPalette(256), sdl2.SDL_AllocPalette(256)]
        self._saved_palette = [sdl2.SDL_AllocPalette(256), sdl2.SDL_AllocPalette(256)]
        # get physical screen dimensions (needs to be called before set_mode)
        # load an all-black 16-colour game palette to get started
        self.set_palette([(0, 0, 0)] * 16, None)
        self.move_cursor(1, 1)
        self.set_page(0, 0)
        # set_mode should be first event on queue
        # check if we can honour scaling=smooth
        if self._smooth:
            # pointer to the zoomed surface
            self.zoomed = None
            pixelformat = self._display_surface.contents.format
            if pixelformat.contents.BitsPerPixel != 32:
                logging.warning('Smooth scaling not available: need 32-bit colour, have %d-bit.',
                        self._display_surface.format.contents.BitsPerPixel)
                self._smooth = False
            if not sdlgfx:
                logging.warning('Smooth scaling not available: `sdlgfx` extension not found.')
                self._smooth = False
        # available joysticks
        num_joysticks = sdl2.SDL_NumJoysticks()
        for j in range(num_joysticks):
            sdl2.SDL_JoystickOpen(j)
            # if a joystick is present, its axes report 128 for mid, not 0
            for axis in (0, 1):
                self._input_queue.put(signals.Event(signals.STICK_MOVED, (j, axis, 128)))
        # enable IME
        sdl2.SDL_StartTextInput()
        return VideoPlugin.__enter__(self)

    def __exit__(self, type, value, traceback):
        """Close the SDL2 interface."""
        VideoPlugin.__exit__(self, type, value, traceback)
        if sdl2 and numpy and self._has_window:
            # free windows
            sdl2.SDL_DestroyWindow(self._display)
            # free surfaces
            for s in self.canvas:
                sdl2.SDL_FreeSurface(s)
            sdl2.SDL_FreeSurface(self._work_surface)
            sdl2.SDL_FreeSurface(self.overlay)
            # free palettes
            for p in self._palette + self._saved_palette:
                sdl2.SDL_FreePalette(p)
            # close IME
            sdl2.SDL_StopTextInput()
            # close SDL2
            sdl2.SDL_Quit()

    def _set_icon(self):
        """Set the icon on the SDL window."""
        mask = numpy.array(self._icon).T.repeat(2, 0).repeat(2, 1)
        icon = sdl2.SDL_CreateRGBSurface(0, mask.shape[0], mask.shape[1], 8, 0, 0, 0, 0)
        _pixels2d(icon.contents)[:] = mask
        # icon palette (black & white)
        icon_palette = sdl2.SDL_AllocPalette(256)
        icon_colors = [ sdl2.SDL_Color(x, x, x, 255) for x in [0, 255] + [255]*254 ]
        sdl2.SDL_SetPaletteColors(icon_palette, (sdl2.SDL_Color * 256)(*icon_colors), 0, 2)
        sdl2.SDL_SetSurfacePalette(icon, icon_palette)
        sdl2.SDL_SetWindowIcon(self._display, icon)
        sdl2.SDL_FreeSurface(icon)
        sdl2.SDL_FreePalette(icon_palette)

    def _do_create_window(self, width, height):
        """Create a new SDL window """
        flags = sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_SHOWN
        if self._fullscreen:
             flags |= sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_BORDERLESS
        sdl2.SDL_DestroyWindow(self._display)
        self._display = sdl2.SDL_CreateWindow(self._caption.encode('utf-8', errors='replace'),
                    sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
                    width, height, flags)
        self._set_icon()
        self._display_surface = sdl2.SDL_GetWindowSurface(self._display)
        self._window_sizer.window_size = width, height
        self.busy = True


    ###########################################################################
    # input cycle

    def _check_input(self):
        """Handle screen and interface events."""
        # don't try to handle events before set_mode
        if not self._has_window:
            return
        # check and handle input events
        self._last_down = None
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_KEYDOWN:
                self._handle_key_down(event)
            elif event.type == sdl2.SDL_KEYUP:
                self._handle_key_up(event)
            elif event.type == sdl2.SDL_TEXTINPUT:
                self._handle_text_input(event)
            elif event.type == sdl2.SDL_TEXTEDITING:
                self.set_caption_message(event.text.text.decode('utf-8'))
            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                pos = self._window_sizer.normalise_pos(event.button.x, event.button.y)
                if self._mouse_clip:
                    if event.button.button == sdl2.SDL_BUTTON_LEFT:
                        # LEFT button: copy
                        self._clipboard_interface.start(1 + pos[1] // self.font_height,
                                1 + (pos[0]+self.font_width//2) // self.font_width)
                    elif event.button.button == sdl2.SDL_BUTTON_MIDDLE:
                        # MIDDLE button: paste
                        text = self._clipboard_handler.paste(mouse=True)
                        self._clipboard_interface.paste(text)
                if event.button.button == sdl2.SDL_BUTTON_LEFT:
                    # right mouse button is a pen press
                    self._input_queue.put(signals.Event(signals.PEN_DOWN, pos))
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                self._input_queue.put(signals.Event(signals.PEN_UP))
                if self._mouse_clip and event.button.button == sdl2.SDL_BUTTON_LEFT:
                    self._clipboard_interface.copy(mouse=True)
                    self._clipboard_interface.stop()
            elif event.type == sdl2.SDL_MOUSEMOTION:
                pos = self._window_sizer.normalise_pos(event.motion.x, event.motion.y)
                self._input_queue.put(signals.Event(signals.PEN_MOVED, pos))
                if self._clipboard_interface.active():
                    self._clipboard_interface.move(1 + pos[1] // self.font_height,
                            1 + (pos[0]+self.font_width//2) // self.font_width)
                    self.busy = True
            elif event.type == sdl2.SDL_JOYBUTTONDOWN:
                self._input_queue.put(signals.Event(signals.STICK_DOWN,
                                    (event.jbutton.which, event.jbutton.button)))
            elif event.type == sdl2.SDL_JOYBUTTONUP:
                self._input_queue.put(signals.Event(signals.STICK_UP,
                                    (event.jbutton.which, event.jbutton.button)))
            elif event.type == sdl2.SDL_JOYAXISMOTION:
                self._input_queue.put(signals.Event(signals.STICK_MOVED,
                                    (event.jaxis.which, event.jaxis.axis,
                                    int((event.jaxis.value/32768.)*127 + 128))))
            elif event.type == sdl2.SDL_WINDOWEVENT:
                if event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
                    self._resize_display(event.window.data1, event.window.data2)
                # unset Alt modifiers on entering/leaving the window
                # workaround for what seems to be an SDL2 bug
                # where the ALT modifier sticks on the first Alt-Tab out
                # of the window
                elif event.window.event in (sdl2.SDL_WINDOWEVENT_LEAVE,
                        sdl2.SDL_WINDOWEVENT_ENTER,
                        sdl2.SDL_WINDOWEVENT_FOCUS_LOST,
                        sdl2.SDL_WINDOWEVENT_FOCUS_GAINED):
                    sdl2.SDL_SetModState(sdl2.SDL_GetModState() & ~sdl2.KMOD_ALT)
            elif event.type == sdl2.SDL_QUIT:
                if self._nokill:
                    self.set_caption_message(NOKILL_MESSAGE)
                else:
                    self._input_queue.put(signals.Event(signals.KEYB_QUIT))
        self._flush_keypress()

    def _handle_key_down(self, e):
        """Handle key-down event."""
        # get scancode
        scan = SCAN_TO_SCAN.get(e.key.keysym.scancode, None)
        # workaround: on some Ubuntu systems with Unity, the Alt key activates the HUD
        # after that, every alt keypress is reported twice (down-ALT down-ALT ... up-ALT)
        # and every alt+X keypress becomes down-ALT down-X down-X ... up-X ... up-ALT
        if self._alt_counter[scancode.ALT] or scan == scancode.ALT:
            self._alt_counter[scan] += 1
            # after double-ALT, ignore every second keypress
            if self._alt_counter[scan] > 1 and (
                    not(self._alt_counter[scan] % 2) or scan == scancode.ALT):
                return
        # get modifiers
        mod = [s for m, s in MOD_TO_SCAN.iteritems() if e.key.keysym.mod & m]
        # get eascii
        try:
            if scancode.ALT in mod:
                c = ALT_SCAN_TO_EASCII[e.key.keysym.scancode]
            elif scancode.CTRL in mod:
                c = CTRL_KEY_TO_EASCII[e.key.keysym.sym]
            elif scancode.LSHIFT in mod or scancode.RSHIFT in mod:
                c = SHIFT_KEY_TO_EASCII[e.key.keysym.sym]
            else:
                c = KEY_TO_EASCII[e.key.keysym.sym]
        except KeyError:
            # try control+letter -> control codes
            key = e.key.keysym.sym
            if scancode.CTRL in mod and key >= ord('a') and key <= ord('z'):
                c = unichr(key - ord('a') + 1)
            elif scancode.CTRL in mod and key >= ord('[') and key <= ord('_'):
                c = unichr(key - ord('A') + 1)
            else:
                c = u''
        if c == u'\0':
            c = uea.NUL
        # handle F11 home-key combinations
        if e.key.keysym.sym == sdl2.SDLK_F11:
            self._f11_active = True
            self._clipboard_interface.start(self.cursor_row, self.cursor_col)
        elif self._f11_active:
            self._clipboard_interface.handle_key(scan, c)
            self.busy = True
        else:
            # keep scancode in buffer
            # to combine with text event
            # flush buffer on next key down, text event or end of loop
            if scan is not None:
                self._flush_keypress()
                self._last_down = c, scan, mod, e.key.timestamp

    def _flush_keypress(self):
        """Flush last keypress from buffer."""
        if self._last_down is not None:
            # insert into keyboard queue; no text event
            c, scan, mod, _ = self._last_down
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, scan, mod)))
            self._last_down = None

    def _handle_key_up(self, e):
        """Handle key-up event."""
        try:
            scan = SCAN_TO_SCAN[e.key.keysym.scancode]
        except KeyError:
            return
        # reset ALT workaround counter
        if scan == scancode.ALT:
            self._alt_counter = Counter()
        # check for emulator key
        if e.key.keysym.sym == sdl2.SDLK_F11:
            self._clipboard_interface.stop()
            self.busy = True
            self._f11_active = False
        # last key released gets remembered
        try:
            self._input_queue.put(signals.Event(signals.KEYB_UP, (scan,)))
        except KeyError:
            pass

    def _handle_text_input(self, event):
        """Handle text-input event."""
        c = event.text.text.decode('utf-8', errors='replace')
        if self._f11_active:
            # F11+f to toggle fullscreen mode
            if c.upper() == u'F':
                self._fullscreen = not self._fullscreen
                self._do_create_window(*self._window_sizer.find_display_size(*self.size))
            self._clipboard_interface.handle_key(None, c)
        # the text input event follows the key down event immediately
        elif self._last_down is None:
            # no key down event waiting: other input method
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, None, None)))
        else:
            eascii, scan, mod, ts = self._last_down
            # timestamps for kepdown and textinput may differ by one on mac
            if ts + 1 >= event.text.timestamp:
                # combine if same time stamp
                if eascii and c != eascii:
                    # filter out chars being sent with alt+key on Linux
                    if scancode.ALT not in mod:
                        # with IME, the text is sent together with the final Enter keypress.
                        self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, None, None)))
                    else:
                        # final keypress such as space, CR have IME meaning, we should ignore them
                        self._input_queue.put(signals.Event(signals.KEYB_DOWN, (eascii, scan, mod)))
                else:
                    self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, scan, mod)))
            else:
                # two separate events
                # previous keypress has no corresponding textinput
                self._flush_keypress()
                # current textinput has no corresponding keypress
                self._input_queue.put(signals.Event(signals.KEYB_DOWN, (c, None, None)))
            self._last_down = None


    ###########################################################################
    # screen drawing cycle

    def sleep(self, ms):
        """Sleep a tick to avoid hogging the cpu."""
        sdl2.SDL_Delay(ms)

    def _work(self):
        """Check screen and blink events; update screen if necessary."""
        if not self._has_window:
            return
        self.blink_state = 0
        if self.mode_has_blink:
            self.blink_state = 0 if self._cycle < BLINK_CYCLES * 2 else 1
            if self._cycle % BLINK_CYCLES == 0:
                self.busy = True
        if self._cursor_visible and (
                (self.cursor_row != self._last_row) or (self.cursor_col != self._last_col)):
            self.busy = True
        tock = sdl2.SDL_GetTicks()
        if tock - self._last_tick >= CYCLE_TIME:
            self._last_tick = tock
            self._cycle += 1
            if self._cycle == BLINK_CYCLES * 4:
                self._cycle = 0
            if self.busy:
                self._do_flip()
                self.busy = False

    def _do_flip(self):
        """Draw the canvas to the screen."""
        sdl2.SDL_FillRect(self._work_surface, None, self._border_attr)
        if self._composite:
            self._work_pixels[:] = window.apply_composite_artifacts(
                            self.pixels[self.vpagenum], 4//self.bitsperpixel)
        else:
            self._work_pixels[:] = self.pixels[self.vpagenum]
        sdl2.SDL_SetSurfacePalette(self._work_surface, self._palette[self.blink_state])
        # apply cursor to work surface
        self._show_cursor(True)
        # convert 8-bit work surface to (usually) 32-bit display surface format
        pixelformat = self._display_surface.contents.format
        conv = sdl2.SDL_ConvertSurface(self._work_surface, pixelformat, 0)
        # scale converted surface and blit onto display
        if not self._smooth:
            sdl2.SDL_BlitScaled(conv, None, self._display_surface, None)
        else:
            # smooth-scale converted surface
            scalex, scaley = self._window_sizer.scale()
            zoomx, zoomy = ctypes.c_double(scalex), ctypes.c_double(scaley)
            # only free the surface just before zoomSurface needs to re-allocate
            # so that the memory block is highly likely to be easily available
            # this seems to avoid unpredictable delays
            sdl2.SDL_FreeSurface(self.zoomed)
            self.zoomed = zoomSurface(conv, zoomx, zoomy, SMOOTHING_ON)
            # blit onto display
            sdl2.SDL_BlitSurface(self.zoomed, None, self._display_surface, None)
        # create clipboard feedback
        if self._clipboard_interface.active():
            rects = (sdl2.SDL_Rect(
                        r[0]+self.border_x, r[1]+self.border_y, r[2], r[3])
                        for r in self._clipboard_interface.selection_rect)
            sdl_rects = (sdl2.SDL_Rect*len(self._clipboard_interface.selection_rect))(*rects)
            sdl2.SDL_FillRect(self.overlay, None,
                sdl2.SDL_MapRGBA(self.overlay.contents.format, 0, 0, 0, 0))
            sdl2.SDL_FillRects(self.overlay, sdl_rects, len(sdl_rects),
                sdl2.SDL_MapRGBA(self.overlay.contents.format, 128, 0, 128, 0))
            sdl2.SDL_BlitScaled(self.overlay, None, self._display_surface, None)
        # flip the display
        sdl2.SDL_UpdateWindowSurface(self._display)
        # destroy the temporary surface
        sdl2.SDL_FreeSurface(conv)

    def _show_cursor(self, do_show):
        """Draw or remove the cursor on the visible page."""
        if not self._cursor_visible or self.vpagenum != self.apagenum:
            return
        screen = self._work_surface
        pixels = self._work_pixels
        top = (self.cursor_row-1) * self.font_height
        left = (self.cursor_col-1) * self.font_width
        if not do_show:
            pixels[left:left+self.font_width, top:top+self.font_height] = self.under_cursor
            return
        # copy area under cursor
        self.under_cursor = numpy.copy(
                pixels[left : left+self.font_width, top : top+self.font_height])
        if self.text_mode:
            # cursor is visible - to be done every cycle between 5 and 10, 15 and 20
            if self._cycle/BLINK_CYCLES in (1, 3):
                curs_height = min(
                        self.cursor_to - self.cursor_from+1, self.font_height - self.cursor_from)
                curs_rect = sdl2.SDL_Rect(
                        self.border_x + left, self.border_y + top + self.cursor_from,
                        self.cursor_width, curs_height)
                sdl2.SDL_FillRect(screen, curs_rect, self.cursor_attr)
        else:
            pixels[left:left+self.cursor_width,
                    top+self.cursor_from:top+self.cursor_to+1] ^= self.cursor_attr
        self._last_row = self.cursor_row
        self._last_col = self.cursor_col

    def _resize_display(self, width, height):
        """Change the display size."""
        maximised = sdl2.SDL_GetWindowFlags(self._display) & sdl2.SDL_WINDOW_MAXIMIZED
        # workaround for maximised state not reporting correctly (at least on Ubuntu Unity)
        # detect if window is very large compared to screen; force maximise if so.
        to_maximised = self._window_sizer.is_maximal(width, height)
        if not maximised:
            if to_maximised:
                # force maximise for large windows
                sdl2.SDL_MaximizeWindow(self._display)
            else:
                # regular resize on non-maximised windows
                sdl2.SDL_SetWindowSize(self._display, width, height)
        else:
            # resizing throws us out of maximised mode
            if not to_maximised:
                sdl2.SDL_RestoreWindow(self._display)
        # get window size
        w, h = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetWindowSize(self._display, ctypes.byref(w), ctypes.byref(h))
        self._window_sizer.window_size = w.value, h.value
        self._display_surface = sdl2.SDL_GetWindowSurface(self._display)
        self.busy = True


    ###########################################################################
    # signal handlers

    def set_mode(self, mode_info):
        """Initialise a given text or graphics mode."""
        self.text_mode = mode_info.is_text_mode
        # unpack mode info struct
        self.font_height = mode_info.font_height
        self.font_width = mode_info.font_width
        # prebuilt glyphs
        # NOTE: [x][y] format - change this if we change _pixels2d
        self.glyph_dict = {u'\0': numpy.zeros((self.font_width, self.font_height))}
        self.num_pages = mode_info.num_pages
        self.mode_has_blink = mode_info.has_blink
        if not self.text_mode:
            self.bitsperpixel = mode_info.bitsperpixel
        # logical size
        self.size = (mode_info.pixel_width, mode_info.pixel_height)
        self._window_sizer.size = self.size
        self._resize_display(*self._window_sizer.find_display_size(*self.size))
        # set standard cursor
        self.set_cursor_shape(self.font_width, self.font_height, 0, self.font_height)
        # screen pages
        canvas_width, canvas_height = self.size
        self.canvas = [
                sdl2.SDL_CreateRGBSurface(0, canvas_width, canvas_height, 8, 0, 0, 0, 0)
                for _ in range(self.num_pages)]
        self.pixels = [_pixels2d(canvas.contents) for canvas in self.canvas]
        # create work surface for border and composite
        self.border_x, self.border_y = self._window_sizer.border_start()
        work_width = canvas_width + 2 * self.border_x
        work_height = canvas_height + 2 * self.border_y
        sdl2.SDL_FreeSurface(self._work_surface)
        self._work_surface = sdl2.SDL_CreateRGBSurface(0, work_width, work_height, 8, 0, 0, 0, 0)
        self._work_pixels = _pixels2d(self._work_surface.contents)[
                self.border_x:work_width-self.border_x, self.border_y:work_height-self.border_y]
        # create overlay for clipboard selection feedback
        # use convertsurface to create a copy of the display surface format
        pixelformat = self._display_surface.contents.format
        self.overlay = sdl2.SDL_ConvertSurface(self._work_surface, pixelformat, 0)
        sdl2.SDL_SetSurfaceBlendMode(self.overlay, sdl2.SDL_BLENDMODE_ADD)
        # initialise clipboard
        self._clipboard_interface = clipboard.ClipboardInterface(
                self._clipboard_handler, self._input_queue,
                mode_info.width, mode_info.height, self.font_width, self.font_height, self.size)
        self.busy = True
        self._has_window = True

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        title = self._caption + (u' - ' + msg if msg else u'')
        sdl2.SDL_SetWindowTitle(self._display, title.encode('utf-8', errors='replace'))

    def set_clipboard_text(self, text, mouse):
        """Put text on the clipboard."""
        self._clipboard_handler.copy(text, mouse)

    def set_palette(self, rgb_palette_0, rgb_palette_1):
        """Build the palette."""
        self.num_fore_attrs = min(16, len(rgb_palette_0))
        self.num_back_attrs = min(8, self.num_fore_attrs)
        rgb_palette_1 = rgb_palette_1 or rgb_palette_0
        # fill up the 8-bit palette with all combinations we need
        # blink states: 0 light up, 1 light down
        # bottom 128 are non-blink, top 128 blink to background
        show_palette_0 = rgb_palette_0[:self.num_fore_attrs] * (256//self.num_fore_attrs)
        show_palette_1 = rgb_palette_1[:self.num_fore_attrs] * (128//self.num_fore_attrs)
        for b in rgb_palette_1[:self.num_back_attrs] * (
                128 // self.num_fore_attrs // self.num_back_attrs):
            show_palette_1 += [b]*self.num_fore_attrs
        colors_0 = (sdl2.SDL_Color * 256)(*(
                sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in show_palette_0))
        colors_1 = (sdl2.SDL_Color * 256)(*(
                sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in show_palette_1))
        sdl2.SDL_SetPaletteColors(self._palette[0], colors_0, 0, 256)
        sdl2.SDL_SetPaletteColors(self._palette[1], colors_1, 0, 256)
        self.busy = True

    def set_border_attr(self, attr):
        """Change the border attribute."""
        self._border_attr = attr
        self.busy = True

    def set_composite(self, on, composite_colors):
        """Enable/disable composite artifacts."""
        if on != self._composite:
            self._palette, self._saved_palette = self._saved_palette, self._palette
        if on:
            colors = (sdl2.SDL_Color * 256)(*(
                    sdl2.SDL_Color(r, g, b, 255) for (r, g, b) in composite_colors))
            sdl2.SDL_SetPaletteColors(self._palette[0], colors, 0, 256)
            sdl2.SDL_SetPaletteColors(self._palette[1], colors, 0, 256)
        self._composite = on
        self.busy = True

    def clear_rows(self, back_attr, start, stop):
        """Clear a range of screen rows."""
        scroll_area = sdl2.SDL_Rect(
                0, (start-1)*self.font_height, self.size[0], (stop-start+1)*self.font_height)
        sdl2.SDL_FillRect(self.canvas[self.apagenum], scroll_area, back_attr)
        self.busy = True

    def set_page(self, vpage, apage):
        """Set the visible and active page."""
        self.vpagenum, self.apagenum = vpage, apage
        self.busy = True

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        self.pixels[dst][:] = self.pixels[src][:]
        # alternative:
        # sdl2.SDL_BlitSurface(self.canvas[src], None, self.canvas[dst], None)
        self.busy = True

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self._cursor_visible = cursor_on
        self.busy = True

    def move_cursor(self, crow, ccol):
        """Move the cursor to a new position."""
        self.cursor_row, self.cursor_col = crow, ccol

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        self.cursor_attr = attr % self.num_fore_attrs

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        pixels = self.pixels[self.apagenum]
        # these are exclusive ranges [x0, x1) etc
        x0, x1 = 0, self.size[0]
        new_y0, new_y1 = (from_line-1)*self.font_height, (scroll_height-1)*self.font_height
        old_y0, old_y1 = from_line*self.font_height, scroll_height*self.font_height
        pixels[x0:x1, new_y0:new_y1] = pixels[x0:x1, old_y0:old_y1]
        pixels[x0:x1, new_y1:old_y1] = numpy.full((x1-x0, old_y1-new_y1), back_attr, dtype=int)
        self.busy = True

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        pixels = self.pixels[self.apagenum]
        # these are exclusive ranges [x0, x1) etc
        x0, x1 = 0, self.size[0]
        old_y0, old_y1 = (from_line-1)*self.font_height, (scroll_height-1)*self.font_height
        new_y0, new_y1 = from_line*self.font_height, scroll_height*self.font_height
        pixels[x0:x1, new_y0:new_y1] = pixels[x0:x1, old_y0:old_y1]
        pixels[x0:x1, old_y0:new_y0] = numpy.full((x1-x0, new_y0-old_y0), back_attr, dtype=int)
        self.busy = True

    def put_glyph(self, pagenum, row, col, cp, is_fullwidth, fore, back, blink, underline):
        """Put a character at a given position."""
        if not self.text_mode:
            # in graphics mode, a put_rect call does the actual drawing
            return
        attr = fore + self.num_fore_attrs*back + 128*blink
        x0, y0 = (col-1)*self.font_width, (row-1)*self.font_height
        # NOTE: in pygame plugin we used a surface fill for the NUL character
        # which was an optimisation early on -- consider if we need speedup.
        try:
            glyph = self.glyph_dict[cp]
        except KeyError:
            logging.warning('No glyph received for code point %s', hex(ord(cp)))
            try:
                glyph = self.glyph_dict['\0']
            except KeyError:
                logging.error('No glyph received for code point 0')
                return
        # _pixels2d uses column-major mode and hence [x][y] indexing (we can change this)
        glyph_width = glyph.shape[0]
        # changle glyph color by numpy scalar mult (is there a better way?)
        self.pixels[pagenum][
            x0:x0+glyph_width, y0:y0+self.font_height] = (
                                                    glyph*(attr-back) + back)
        if underline:
            sdl2.SDL_FillRect(
                self.canvas[self.apagenum],
                sdl2.SDL_Rect(x0, y0 + self.font_height - 1, glyph_width, 1),
                attr)
        self.busy = True

    def build_glyphs(self, new_dict):
        """Build a dict of glyphs for use in text mode."""
        for char, glyph in new_dict.iteritems():
            # transpose because _pixels2d uses column-major mode and hence [x][y] indexing
            # (we can change this)
            self.glyph_dict[char] = numpy.asarray(glyph).T

    def set_cursor_shape(self, width, height, from_line, to_line):
        """Build a sprite for the cursor."""
        self.cursor_width = width
        self.cursor_from, self.cursor_to = from_line, to_line
        self.under_cursor = numpy.zeros((width, height))

    def put_pixel(self, pagenum, x, y, index):
        """Put a pixel on the screen; callback to empty character buffer."""
        self.pixels[pagenum][x, y] = index
        self.busy = True

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""
        rect = sdl2.SDL_Rect(x0, y0, x1-x0+1, y1-y0+1)
        sdl2.SDL_FillRect(self.canvas[pagenum], rect, index)
        self.busy = True

    def fill_interval(self, pagenum, x0, x1, y, index):
        """Fill a scanline interval in a solid attribute."""
        rect = sdl2.SDL_Rect(x0, y, x1-x0+1, 1)
        sdl2.SDL_FillRect(self.canvas[pagenum], rect, index)
        self.busy = True

    def put_interval(self, pagenum, x, y, colours):
        """Write a list of attributes to a scanline interval."""
        # reference the interval on the canvas
        self.pixels[pagenum][x:x+len(colours), y] = numpy.array(colours).astype(int)
        self.busy = True

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """Apply numpy array [y][x] of attribytes to an area."""
        if (x1 < x0) or (y1 < y0):
            return
        # reference the destination area
        self.pixels[pagenum][x0:x1+1, y0:y1+1] = numpy.array(array).T
        self.busy = True
