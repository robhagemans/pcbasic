"""
PC-BASIC - video_sdl2.py
Graphical interface based on PySDL2

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
import ctypes
import os
from contextlib import contextmanager

try:
    import numpy
except ImportError:
    numpy = None

from ..compat import iteritems, unichr
from ..compat import WIN32, BASE_DIR, PLATFORM
from ..compat import set_dpi_aware

from .base import EnvironmentCache
from .base import video_plugins, InitFailed, NOKILL_MESSAGE
from ..basic.base import signals
from ..basic.base import scancode
from ..basic.base.eascii import as_unicode as uea
from ..data.resources import ICON
from .video import VideoPlugin
from . import window
from . import clipboard


###############################################################################
# locate and load SDL libraries

# platform-specific dll location
LIB_DIR = os.path.join(BASE_DIR, 'lib', PLATFORM)
# possible names of sdl_gfx library
GFX_NAMES = ('SDL2_gfx', 'SDL2_gfx-1.0')


def _bind_gfx_zoomsurface():
    """Bind smooth-zoom function."""
    global sdlgfx
    # look for SDL2_gfx.dll:
    # first in SDL2.dll location
    # if not found, in LIB_DIR; then in standard search path
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
        return sdlgfx.bind_function(
            'zoomSurface',
            [ctypes.POINTER(sdl2.SDL_Surface), ctypes.c_double, ctypes.c_double, ctypes.c_int],
            ctypes.POINTER(sdl2.SDL_Surface)
        )
    return None


with EnvironmentCache() as _sdl_env:
    # look for SDL2.dll / libSDL2.dylib / libSDL2.so:
    # first in LIB_DIR, then in the standard search path
    # user should remove dll from LIB_DIR they want to use another one
    _sdl_env.set('PYSDL2_DLL_PATH', LIB_DIR)
    try:
        from . import sdl2
    except ImportError:
        _sdl_env.set('PYSDL2_DLL_PATH', '')
        try:
            from . import sdl2
        except ImportError:
            sdl2 = None
    sdlgfx = None
    _smooth_zoom = _bind_gfx_zoomsurface()


###############################################################################
# video settings

# refresh cycle parameters
# number of cycles to change blink state
BLINK_CYCLES = 5
# number of distinct blink states
N_BLINK_STATES = 4
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
        sdl2.SDL_SCANCODE_EQUALS: scancode.EQUALS, sdl2.SDL_SCANCODE_BACKSPACE: scancode.BACKSPACE,
        # row 1
        sdl2.SDL_SCANCODE_TAB: scancode.TAB, sdl2.SDL_SCANCODE_Q: scancode.q,
        sdl2.SDL_SCANCODE_W: scancode.w, sdl2.SDL_SCANCODE_E: scancode.e,
        sdl2.SDL_SCANCODE_R: scancode.r, sdl2.SDL_SCANCODE_T: scancode.t,
        sdl2.SDL_SCANCODE_Y: scancode.y, sdl2.SDL_SCANCODE_U: scancode.u,
        sdl2.SDL_SCANCODE_I: scancode.i, sdl2.SDL_SCANCODE_O: scancode.o,
        sdl2.SDL_SCANCODE_P: scancode.p, sdl2.SDL_SCANCODE_LEFTBRACKET: scancode.LEFTBRACKET,
        sdl2.SDL_SCANCODE_RIGHTBRACKET: scancode.RIGHTBRACKET,
        sdl2.SDL_SCANCODE_RETURN: scancode.RETURN, sdl2.SDL_SCANCODE_KP_ENTER: scancode.RETURN,
        # row 2
        sdl2.SDL_SCANCODE_RCTRL: scancode.CTRL, sdl2.SDL_SCANCODE_LCTRL: scancode.CTRL,
        sdl2.SDL_SCANCODE_A: scancode.a, sdl2.SDL_SCANCODE_S: scancode.s,
        sdl2.SDL_SCANCODE_D: scancode.d, sdl2.SDL_SCANCODE_F: scancode.f,
        sdl2.SDL_SCANCODE_G: scancode.g, sdl2.SDL_SCANCODE_H: scancode.h,
        sdl2.SDL_SCANCODE_J: scancode.j, sdl2.SDL_SCANCODE_K: scancode.k,
        sdl2.SDL_SCANCODE_L: scancode.l, sdl2.SDL_SCANCODE_SEMICOLON: scancode.SEMICOLON,
        sdl2.SDL_SCANCODE_APOSTROPHE: scancode.QUOTE, sdl2.SDL_SCANCODE_GRAVE: scancode.BACKQUOTE,
        # row 3
        sdl2.SDL_SCANCODE_LSHIFT: scancode.LSHIFT, sdl2.SDL_SCANCODE_BACKSLASH: scancode.BACKSLASH,
        sdl2.SDL_SCANCODE_Z: scancode.z, sdl2.SDL_SCANCODE_X: scancode.x,
        sdl2.SDL_SCANCODE_C: scancode.c, sdl2.SDL_SCANCODE_V: scancode.v,
        sdl2.SDL_SCANCODE_B: scancode.b, sdl2.SDL_SCANCODE_N: scancode.n,
        sdl2.SDL_SCANCODE_M: scancode.m, sdl2.SDL_SCANCODE_COMMA: scancode.COMMA,
        sdl2.SDL_SCANCODE_PERIOD: scancode.PERIOD, sdl2.SDL_SCANCODE_SLASH: scancode.SLASH,
        sdl2.SDL_SCANCODE_RSHIFT: scancode.RSHIFT, sdl2.SDL_SCANCODE_SYSREQ: scancode.SYSREQ,
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
        sdl2.SDL_SCANCODE_SCROLLLOCK: scancode.SCROLLOCK, sdl2.SDL_SCANCODE_PAUSE: scancode.BREAK,
        # keypad
        sdl2.SDL_SCANCODE_KP_MULTIPLY: scancode.KPTIMES,
        sdl2.SDL_SCANCODE_PRINTSCREEN: scancode.PRINT,
        sdl2.SDL_SCANCODE_KP_7: scancode.KP7, sdl2.SDL_SCANCODE_HOME: scancode.HOME,
        sdl2.SDL_SCANCODE_KP_8: scancode.KP8, sdl2.SDL_SCANCODE_UP: scancode.UP,
        sdl2.SDL_SCANCODE_KP_9: scancode.KP9, sdl2.SDL_SCANCODE_PAGEUP: scancode.PAGEUP,
        sdl2.SDL_SCANCODE_KP_MINUS: scancode.KPMINUS, sdl2.SDL_SCANCODE_KP_4: scancode.KP4,
        sdl2.SDL_SCANCODE_LEFT: scancode.LEFT, sdl2.SDL_SCANCODE_KP_5: scancode.KP5,
        sdl2.SDL_SCANCODE_KP_6: scancode.KP6, sdl2.SDL_SCANCODE_RIGHT: scancode.RIGHT,
        sdl2.SDL_SCANCODE_KP_PLUS: scancode.KPPLUS, sdl2.SDL_SCANCODE_KP_1: scancode.KP1,
        sdl2.SDL_SCANCODE_END: scancode.END, sdl2.SDL_SCANCODE_KP_2: scancode.KP2,
        sdl2.SDL_SCANCODE_DOWN: scancode.DOWN, sdl2.SDL_SCANCODE_KP_3: scancode.KP3,
        sdl2.SDL_SCANCODE_PAGEDOWN: scancode.PAGEDOWN,
        sdl2.SDL_SCANCODE_KP_0: scancode.KP0, sdl2.SDL_SCANCODE_INSERT: scancode.INSERT,
        sdl2.SDL_SCANCODE_KP_PERIOD: scancode.KPPOINT, sdl2.SDL_SCANCODE_DELETE: scancode.DELETE,
        # extensions
        sdl2.SDL_SCANCODE_NONUSBACKSLASH: scancode.INT1,
        # windows keys
        sdl2.SDL_SCANCODE_LGUI: scancode.LSUPER, sdl2.SDL_SCANCODE_RGUI: scancode.RSUPER,
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
        sdl2.SDLK_F1: uea.F1, sdl2.SDLK_F2: uea.F2, sdl2.SDLK_F3: uea.F3, sdl2.SDLK_F4: uea.F4,
        sdl2.SDLK_F5: uea.F5, sdl2.SDLK_F6: uea.F6, sdl2.SDLK_F7: uea.F7, sdl2.SDLK_F8: uea.F8,
        sdl2.SDLK_F9: uea.F9, sdl2.SDLK_F10: uea.F10, sdl2.SDLK_F11: uea.F11,
        sdl2.SDLK_F12: uea.F12, sdl2.SDLK_HOME: uea.HOME, sdl2.SDLK_UP: uea.UP,
        sdl2.SDLK_PAGEUP: uea.PAGEUP, sdl2.SDLK_LEFT: uea.LEFT, sdl2.SDLK_RIGHT: uea.RIGHT,
        sdl2.SDLK_END: uea.END, sdl2.SDLK_DOWN: uea.DOWN, sdl2.SDLK_PAGEDOWN: uea.PAGEDOWN,
        sdl2.SDLK_ESCAPE: uea.ESCAPE, sdl2.SDLK_BACKSPACE: uea.BACKSPACE, sdl2.SDLK_TAB: uea.TAB,
        sdl2.SDLK_RETURN: uea.RETURN, sdl2.SDLK_KP_ENTER: uea.RETURN, sdl2.SDLK_SPACE: uea.SPACE,
        sdl2.SDLK_INSERT: uea.INSERT, sdl2.SDLK_DELETE: uea.DELETE,
    }

    SHIFT_KEY_TO_EASCII = {
        sdl2.SDLK_F1: uea.SHIFT_F1, sdl2.SDLK_F2: uea.SHIFT_F2, sdl2.SDLK_F3: uea.SHIFT_F3,
        sdl2.SDLK_F4: uea.SHIFT_F4, sdl2.SDLK_F5: uea.SHIFT_F5, sdl2.SDLK_F6: uea.SHIFT_F6,
        sdl2.SDLK_F7: uea.SHIFT_F7, sdl2.SDLK_F8: uea.SHIFT_F8, sdl2.SDLK_F9: uea.SHIFT_F9,
        sdl2.SDLK_F10: uea.SHIFT_F10, sdl2.SDLK_F11: uea.SHIFT_F11, sdl2.SDLK_F12: uea.SHIFT_F12,
        sdl2.SDLK_HOME: uea.SHIFT_HOME, sdl2.SDLK_UP: uea.SHIFT_UP,
        sdl2.SDLK_PAGEUP: uea.SHIFT_PAGEUP, sdl2.SDLK_LEFT: uea.SHIFT_LEFT,
        sdl2.SDLK_RIGHT: uea.SHIFT_RIGHT, sdl2.SDLK_END: uea.SHIFT_END,
        sdl2.SDLK_DOWN: uea.SHIFT_DOWN, sdl2.SDLK_PAGEDOWN: uea.SHIFT_PAGEDOWN,
        sdl2.SDLK_ESCAPE: uea.SHIFT_ESCAPE, sdl2.SDLK_BACKSPACE: uea.SHIFT_BACKSPACE,
        sdl2.SDLK_TAB: uea.SHIFT_TAB, sdl2.SDLK_RETURN: uea.SHIFT_RETURN,
        sdl2.SDLK_KP_ENTER: uea.SHIFT_RETURN, sdl2.SDLK_SPACE: uea.SHIFT_SPACE,
        sdl2.SDLK_INSERT: uea.SHIFT_INSERT, sdl2.SDLK_DELETE: uea.SHIFT_DELETE,
        sdl2.SDLK_KP_5: uea.SHIFT_KP5,
    }

    CTRL_KEY_TO_EASCII = {
        sdl2.SDLK_F1: uea.CTRL_F1, sdl2.SDLK_F2: uea.CTRL_F2, sdl2.SDLK_F3: uea.CTRL_F3,
        sdl2.SDLK_F4: uea.CTRL_F4, sdl2.SDLK_F5: uea.CTRL_F5, sdl2.SDLK_F6: uea.CTRL_F6,
        sdl2.SDLK_F7: uea.CTRL_F7, sdl2.SDLK_F8: uea.CTRL_F8, sdl2.SDLK_F9: uea.CTRL_F9,
        sdl2.SDLK_F10: uea.CTRL_F10, sdl2.SDLK_F11: uea.CTRL_F11, sdl2.SDLK_F12: uea.CTRL_F12,
        sdl2.SDLK_HOME: uea.CTRL_HOME, sdl2.SDLK_PAGEUP: uea.CTRL_PAGEUP,
        sdl2.SDLK_LEFT: uea.CTRL_LEFT, sdl2.SDLK_RIGHT: uea.CTRL_RIGHT, sdl2.SDLK_END: uea.CTRL_END,
        sdl2.SDLK_PAGEDOWN: uea.CTRL_PAGEDOWN, sdl2.SDLK_ESCAPE: uea.CTRL_ESCAPE,
        sdl2.SDLK_BACKSPACE: uea.CTRL_BACKSPACE, sdl2.SDLK_TAB: uea.CTRL_TAB,
        sdl2.SDLK_RETURN: uea.CTRL_RETURN, sdl2.SDLK_KP_ENTER: uea.CTRL_RETURN,
        sdl2.SDLK_SPACE: uea.CTRL_SPACE, sdl2.SDLK_PRINTSCREEN: uea.CTRL_PRINT,
        sdl2.SDLK_2: uea.CTRL_2, sdl2.SDLK_6: uea.CTRL_6, sdl2.SDLK_MINUS: uea.CTRL_MINUS,
    }

    ALT_SCAN_TO_EASCII = {
        sdl2.SDL_SCANCODE_1: uea.ALT_1, sdl2.SDL_SCANCODE_2: uea.ALT_2,
        sdl2.SDL_SCANCODE_3: uea.ALT_3, sdl2.SDL_SCANCODE_4: uea.ALT_4,
        sdl2.SDL_SCANCODE_5: uea.ALT_5, sdl2.SDL_SCANCODE_6: uea.ALT_6,
        sdl2.SDL_SCANCODE_7: uea.ALT_7, sdl2.SDL_SCANCODE_8: uea.ALT_8,
        sdl2.SDL_SCANCODE_9: uea.ALT_9, sdl2.SDL_SCANCODE_0: uea.ALT_0,
        sdl2.SDL_SCANCODE_MINUS: uea.ALT_MINUS, sdl2.SDL_SCANCODE_EQUALS: uea.ALT_EQUALS,
        sdl2.SDL_SCANCODE_Q: uea.ALT_q, sdl2.SDL_SCANCODE_W: uea.ALT_w,
        sdl2.SDL_SCANCODE_E: uea.ALT_e, sdl2.SDL_SCANCODE_R: uea.ALT_r,
        sdl2.SDL_SCANCODE_T: uea.ALT_t, sdl2.SDL_SCANCODE_Y: uea.ALT_y,
        sdl2.SDL_SCANCODE_U: uea.ALT_u, sdl2.SDL_SCANCODE_I: uea.ALT_i,
        sdl2.SDL_SCANCODE_O: uea.ALT_o, sdl2.SDL_SCANCODE_P: uea.ALT_p,
        sdl2.SDL_SCANCODE_A: uea.ALT_a, sdl2.SDL_SCANCODE_S: uea.ALT_s,
        sdl2.SDL_SCANCODE_D: uea.ALT_d, sdl2.SDL_SCANCODE_F: uea.ALT_f,
        sdl2.SDL_SCANCODE_G: uea.ALT_g, sdl2.SDL_SCANCODE_H: uea.ALT_h,
        sdl2.SDL_SCANCODE_J: uea.ALT_j, sdl2.SDL_SCANCODE_K: uea.ALT_k,
        sdl2.SDL_SCANCODE_L: uea.ALT_l, sdl2.SDL_SCANCODE_Z: uea.ALT_z,
        sdl2.SDL_SCANCODE_X: uea.ALT_x, sdl2.SDL_SCANCODE_C: uea.ALT_c,
        sdl2.SDL_SCANCODE_V: uea.ALT_v, sdl2.SDL_SCANCODE_B: uea.ALT_b,
        sdl2.SDL_SCANCODE_N: uea.ALT_n, sdl2.SDL_SCANCODE_M: uea.ALT_m,
        sdl2.SDL_SCANCODE_F1: uea.ALT_F1, sdl2.SDL_SCANCODE_F2: uea.ALT_F2,
        sdl2.SDL_SCANCODE_F3: uea.ALT_F3, sdl2.SDL_SCANCODE_F4: uea.ALT_F4,
        sdl2.SDL_SCANCODE_F5: uea.ALT_F5, sdl2.SDL_SCANCODE_F6: uea.ALT_F6,
        sdl2.SDL_SCANCODE_F7: uea.ALT_F7, sdl2.SDL_SCANCODE_F8: uea.ALT_F8,
        sdl2.SDL_SCANCODE_F9: uea.ALT_F9, sdl2.SDL_SCANCODE_F10: uea.ALT_F10,
        sdl2.SDL_SCANCODE_F11: uea.ALT_F11, sdl2.SDL_SCANCODE_F12: uea.ALT_F12,
        sdl2.SDL_SCANCODE_BACKSPACE: uea.ALT_BACKSPACE, sdl2.SDL_SCANCODE_TAB: uea.ALT_TAB,
        sdl2.SDL_SCANCODE_RETURN: uea.ALT_RETURN, sdl2.SDL_SCANCODE_KP_ENTER: uea.ALT_RETURN,
        sdl2.SDL_SCANCODE_SPACE: uea.ALT_SPACE, sdl2.SDL_SCANCODE_PRINTSCREEN: uea.ALT_PRINT,
        sdl2.SDL_SCANCODE_KP_5: uea.ALT_KP5,
    }

    MOD_TO_SCAN = {
        sdl2.KMOD_LSHIFT: scancode.LSHIFT, sdl2.KMOD_RSHIFT: scancode.RSHIFT,
        sdl2.KMOD_LCTRL: scancode.CTRL, sdl2.KMOD_RCTRL: scancode.CTRL,
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
        clipboard.Clipboard.__init__(self)
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
    return numpy.ndarray(shape, numpy.uint8, pxbuf, 0, strides, 'C').transpose()


###############################################################################
# video plugin

@video_plugins.register('sdl2')
class VideoSDL2(VideoPlugin):
    """SDL2-based graphical interface."""

    def __init__(
            self, input_queue, video_queue,
            caption=u'', icon=ICON,
            scaling=None, dimensions=None, aspect_ratio=(4, 3), border_width=0, fullscreen=False,
            prevent_close=False, mouse_clipboard=True,
            **kwargs
        ):
        """Initialise SDL2 interface."""
        if not sdl2:
            raise InitFailed('Module `sdl2` not found')
        if not numpy:
            raise InitFailed('Module `numpy` not found')
        VideoPlugin.__init__(self, input_queue, video_queue)
        # Windows 10 - set to DPI aware to avoid scaling twice on HiDPI screens
        set_dpi_aware()
        # request smooth scaling
        self._smooth = scaling == 'smooth'
        # ignore ALT+F4 and window X button
        self._nokill = prevent_close
        # window caption/title
        self._caption = caption
        # start in fullscreen mode if True
        self._fullscreen = fullscreen
        # don't resize native windows
        self._resizable = scaling != 'native'
        # display & border
        # border attribute
        self._border_attr = 0
        # update cycle
        self._cycle = 0
        self._last_tick = 0
        # blink is enabled, should be True in text modes with blink and ega mono
        # cursor blinks if _is_text_mode and _blink_enabled
        self._blink_enabled = True
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
        # get physical screen dimensions (needs to be called before set_mode)
        display_mode = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetCurrentDisplayMode(0, ctypes.byref(display_mode))
        self._window_sizer = window.WindowSizer(
            display_mode.w, display_mode.h,
            scaling, dimensions, aspect_ratio, border_width,
        )
        # create the window initially as 720*400 black
        self._window_sizer.set_canvas_size(720, 400, fullscreen=self._fullscreen)
        # canvas surfaces
        self._window_surface = []
        # pixel views of canvases
        self._canvas_pixels = []
        # main window object
        self._display = None
        self._display_surface = None
        # one cache per blink state
        self._display_cache = [None] * N_BLINK_STATES
        self._has_display_cache = [False] * N_BLINK_STATES
        # pointer to the zoomed surface
        self._zoomed_surface = None
        # clipboard handler
        self._clipboard_handler = None
        # clipboard visual feedback
        self._clipboard_interface = None
        # event handlers
        self._event_handlers = self._register_handlers()
        # video mode settings
        self._is_text_mode = True
        self._font_height = None
        self._font_width = None
        self._num_pages = None
        # cursor
        # cursor is visible
        self._cursor_visible = True
        # cursor position
        self._cursor_row, self._cursor_col = 1, 1
        # cursor shape
        self._cursor_from = None
        self._cursor_to = None
        self._cursor_width = None
        self._cursor_attr = None
        self._cursor_cache = [None, None]
        # display pages
        self._vpagenum, self._apagenum = 0, 0
        # palette
        # display palettes for blink states 0, 1
        self._palette = [sdl2.SDL_AllocPalette(256), sdl2.SDL_AllocPalette(256)]
        self._num_fore_attrs = 16
        self._num_back_attrs = 8
        # pixel packing is active (composite artifacts)
        self._pixel_packing = False
        # last keypress
        self._last_keypress = None
        # set clipboard handler to SDL2
        self._clipboard_handler = SDL2Clipboard()
        # available joysticks
        num_joysticks = sdl2.SDL_NumJoysticks()
        for stick in range(num_joysticks):
            sdl2.SDL_JoystickOpen(stick)
            # if a joystick is present, its axes report 128 for mid, not 0
            for axis in (0, 1):
                self._input_queue.put(signals.Event(signals.STICK_MOVED, (stick, axis, 128)))

    def __enter__(self):
        """Complete SDL2 interface initialisation."""
        # "NOTE: You should not expect to be able to create a window, render,
        #        or receive events on any thread other than the main one"
        # https://wiki.libsdl.org/CategoryThread
        # http://stackoverflow.com/questions/27751533/sdl2-threading-seg-fault
        self._do_create_window()
        # pop up as black rather than background, looks nicer
        sdl2.SDL_UpdateWindowSurface(self._display)
        # check if we can honour scaling=smooth
        if self._smooth:
            bpp = self._display_surface.contents.format.contents.BitsPerPixel
            if bpp != 32:
                logging.warning(
                    'Smooth scaling not available: need 32-bit colour, have %d-bit.', bpp
                )
                self._smooth = False
            if not _smooth_zoom:
                logging.warning('Smooth scaling not available: `sdlgfx` extension not found.')
                self._smooth = False
        # enable IME
        sdl2.SDL_StartTextInput()
        return VideoPlugin.__enter__(self)
        # set_mode should be first event on queue

    def __exit__(self, exc_type, value, traceback):
        """Close the SDL2 interface."""
        VideoPlugin.__exit__(self, exc_type, value, traceback)
        if sdl2 and numpy and self._has_window:
            # free windows
            sdl2.SDL_DestroyWindow(self._display)
            # free caches
            for surface in self._display_cache:
                sdl2.SDL_FreeSurface(surface)
            # free surfaces
            for surface in self._window_surface:
                sdl2.SDL_FreeSurface(surface)
            # free palettes
            for palette in self._palette:
                sdl2.SDL_FreePalette(palette)
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
        icon_colors = [sdl2.SDL_Color(_c, _c, _c, 255) for _c in [0, 255] + [255]*254]
        sdl2.SDL_SetPaletteColors(icon_palette, (sdl2.SDL_Color * 256)(*icon_colors), 0, 2)
        sdl2.SDL_SetSurfacePalette(icon, icon_palette)
        sdl2.SDL_SetWindowIcon(self._display, icon)
        sdl2.SDL_FreeSurface(icon)
        sdl2.SDL_FreePalette(icon_palette)

    def _do_create_window(self):
        """Create a new SDL window """
        flags = sdl2.SDL_WINDOW_SHOWN
        if self._resizable:
            flags |= sdl2.SDL_WINDOW_RESIZABLE
        if self._fullscreen:
            flags |= sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_BORDERLESS
        width, height = self._window_sizer.display_size
        sdl2.SDL_DestroyWindow(self._display)
        self._display = sdl2.SDL_CreateWindow(
            self._caption.encode('utf-8', errors='replace'),
            sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
            width, height, flags
        )
        # on fullscreen, grab keyboard exclusively
        # this allows BASIC to capture Alt-F4, Alt-TAB etc.
        if self._fullscreen:
            sdl2.SDL_SetHint(sdl2.SDL_HINT_GRAB_KEYBOARD, b'1')
            sdl2.SDL_SetWindowGrab(self._display, sdl2.SDL_TRUE)
        self._set_icon()
        self._reset_display_caches()
        self.busy = True

    def _reset_display_caches(self):
        """Reset caches and references to display object."""
        self._display_surface = sdl2.SDL_GetWindowSurface(self._display)
        # reset cache sizes
        for surface in self._display_cache:
            sdl2.SDL_FreeSurface(surface)
        # clone the surface four times for blink caches
        self._display_cache = [
            sdl2.SDL_ConvertSurface(self._display_surface, self._display_surface.contents.format, 0)
            for _ in range(N_BLINK_STATES)
        ]
        self._has_display_cache = [False] * N_BLINK_STATES


    ###########################################################################
    # input cycle

    def _check_input(self):
        """Handle screen and interface events."""
        # don't try to handle events before set_mode
        if not self._has_window:
            return
        # check and handle input events
        self._last_keypress = None
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            try:
                self._event_handlers[event.type](event)
            except KeyError:
                pass
        self._flush_keypress()

    def _register_handlers(self):
        """Create table of event handlers."""
        return {
            sdl2.SDL_KEYDOWN: self._handle_key_down,
            sdl2.SDL_KEYUP: self._handle_key_up,
            sdl2.SDL_TEXTINPUT: self._handle_text_input,
            sdl2.SDL_TEXTEDITING: self._handle_text_editing,
            sdl2.SDL_MOUSEBUTTONDOWN: self._handle_mouse_down,
            sdl2.SDL_MOUSEBUTTONUP: self._handle_mouse_up,
            sdl2.SDL_MOUSEMOTION: self._handle_mouse_motion,
            sdl2.SDL_JOYBUTTONDOWN: self._handle_stick_down,
            sdl2.SDL_JOYBUTTONUP: self._handle_stick_up,
            sdl2.SDL_JOYAXISMOTION: self._handle_stick_motion,
            sdl2.SDL_WINDOWEVENT: self._handle_window_event,
            sdl2.SDL_QUIT: self._handle_quit,
        }

    # quit events

    def _handle_quit(self, event):
        """Handle quit event."""
        if self._nokill:
            self.set_caption_message(NOKILL_MESSAGE)
        else:
            self._input_queue.put(signals.Event(signals.KEYB_QUIT))

    # window events

    def _handle_window_event(self, event):
        """Handle window event."""
        if event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
            self._handle_resize_event(event)
        # unset Alt modifiers on entering/leaving the window
        # workaround for what seems to be an SDL2 bug
        # where the ALT modifier sticks on the first Alt-Tab out
        # of the window
        elif event.window.event in (
                sdl2.SDL_WINDOWEVENT_LEAVE,
                sdl2.SDL_WINDOWEVENT_ENTER,
                sdl2.SDL_WINDOWEVENT_FOCUS_LOST,
                sdl2.SDL_WINDOWEVENT_FOCUS_GAINED
            ):
            sdl2.SDL_SetModState(sdl2.SDL_GetModState() & ~sdl2.KMOD_ALT)

    def _handle_resize_event(self, event):
        """Respond to change of display size."""
        if not self._fullscreen:
            # width, height = event.window.data1, event.window.data2
            # get actual window size
            width, height = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_GetWindowSize(self._display, ctypes.byref(width), ctypes.byref(height))
            # update the size calculator
            self._window_sizer.set_display_size(width.value, height.value)
        # we need to update the surface pointer
        self._reset_display_caches()
        self.busy = True

    # mouse events

    def _handle_mouse_down(self, event):
        """Handle mouse-down event."""
        pos = self._window_sizer.normalise_pos(event.button.x, event.button.y)
        if self._mouse_clip:
            if event.button.button == sdl2.SDL_BUTTON_LEFT:
                # LEFT button: copy
                self._clipboard_interface.start(
                    1 + pos[1] // self._font_height,
                    1 + (pos[0]+self._font_width//2) // self._font_width
                )
            elif event.button.button == sdl2.SDL_BUTTON_MIDDLE:
                # MIDDLE button: paste
                text = self._clipboard_handler.paste(mouse=True)
                self._clipboard_interface.paste(text)
            self.busy = True
        if event.button.button == sdl2.SDL_BUTTON_LEFT:
            # pen press
            self._input_queue.put(signals.Event(signals.PEN_DOWN, pos))

    def _handle_mouse_up(self, event):
        """Handle mouse-up event."""
        self._input_queue.put(signals.Event(signals.PEN_UP))
        if self._mouse_clip and event.button.button == sdl2.SDL_BUTTON_LEFT:
            self._clipboard_interface.copy(mouse=True)
            self._clipboard_interface.stop()
            self.busy = True

    def _handle_mouse_motion(self, event):
        """Handle mouse-motion event."""
        pos = self._window_sizer.normalise_pos(event.motion.x, event.motion.y)
        self._input_queue.put(signals.Event(signals.PEN_MOVED, pos))
        if self._clipboard_interface.active():
            self._clipboard_interface.move(
                1 + pos[1] // self._font_height,
                1 + (pos[0]+self._font_width//2) // self._font_width
            )
            self.busy = True

    # joystick events

    def _handle_stick_down(self, event):
        """Handle joystick button-down event."""
        self._input_queue.put(signals.Event(
            signals.STICK_DOWN,
            (event.jbutton.which, event.jbutton.button)
        ))

    def _handle_stick_up(self, event):
        """Handle joystick button-up event."""
        self._input_queue.put(signals.Event(
            signals.STICK_UP,
            (event.jbutton.which, event.jbutton.button)
        ))

    def _handle_stick_motion(self, event):
        """Handle joystick axis-motion event."""
        self._input_queue.put(signals.Event(
            signals.STICK_MOVED,
            (event.jaxis.which, event.jaxis.axis, int((event.jaxis.value/32768.)*127 + 128))
        ))

    # keyboard events

    def _handle_key_down(self, event):
        """Handle key-down event."""
        # get scancode
        scan = SCAN_TO_SCAN.get(event.key.keysym.scancode, None)
        # get modifiers
        mod = [_s for _m, _s in iteritems(MOD_TO_SCAN) if event.key.keysym.mod & _m]
        # get eascii
        try:
            if scancode.ALT in mod:
                char = ALT_SCAN_TO_EASCII[event.key.keysym.scancode]
            elif scancode.CTRL in mod:
                char = CTRL_KEY_TO_EASCII[event.key.keysym.sym]
            elif scancode.LSHIFT in mod or scancode.RSHIFT in mod:
                char = SHIFT_KEY_TO_EASCII[event.key.keysym.sym]
            else:
                char = KEY_TO_EASCII[event.key.keysym.sym]
        except KeyError:
            # try control+letter -> control codes
            key = event.key.keysym.sym
            if scancode.CTRL in mod and key >= ord(u'a') and key <= ord(u'z'):
                char = unichr(key - ord(u'a') + 1)
            elif scancode.CTRL in mod and key >= ord(u'[') and key <= ord(u'_'):
                char = unichr(key - ord(u'A') + 1)
            else:
                char = u''
        if char == u'\0':
            char = uea.NUL
        # handle F11 home-key combinations
        if event.key.keysym.sym == sdl2.SDLK_F11:
            self._f11_active = True
            self._clipboard_interface.start(self._cursor_row, self._cursor_col)
        elif self._f11_active:
            self._clipboard_interface.handle_key(scan, char)
            self.busy = True
        else:
            # keep scancode in last-down buffer to combine with text event
            # flush buffer on next key down, text event or end of loop
            # if the same key is reported twice with the same timestamp, ignore
            # (this deals with the Unity double-ALT-bug and maybe others)
            if scan is not None and (char, scan, mod, event.key.timestamp) != self._last_keypress:
                self._flush_keypress()
                self._last_keypress = char, scan, mod, event.key.timestamp

    def _flush_keypress(self):
        """Flush last keypress from buffer."""
        if self._last_keypress is not None:
            # insert into keyboard queue; no text event
            char, scan, mod, _ = self._last_keypress
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, scan, mod)))
            self._last_keypress = None

    def _handle_key_up(self, event):
        """Handle key-up event."""
        try:
            scan = SCAN_TO_SCAN[event.key.keysym.scancode]
        except KeyError:
            return
        # check for emulator key
        if event.key.keysym.sym == sdl2.SDLK_F11:
            self._clipboard_interface.stop()
            self.busy = True
            self._f11_active = False
        # last key released gets remembered
        try:
            self._input_queue.put(signals.Event(signals.KEYB_UP, (scan,)))
        except KeyError:
            pass

    # text input method events

    def _handle_text_editing(self, event):
        """Handle text-editing event."""
        self.set_caption_message(event.text.text.decode('utf-8'))

    def _handle_text_input(self, event):
        """Handle text-input event."""
        char = event.text.text.decode('utf-8', errors='replace')
        if self._f11_active:
            # F11+f to toggle fullscreen mode
            if char.upper() == u'F':
                self._toggle_fullscreen()
            self._clipboard_interface.handle_key(None, char)
        # the text input event follows the key down event immediately
        elif self._last_keypress is None:
            # no key down event waiting: other input method
            self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, None, None)))
        else:
            eascii, scan, mod, timestamp = self._last_keypress
            # timestamps for kepdown and textinput may differ by one on mac
            if timestamp + 1 >= event.text.timestamp:
                # combine if same time stamp
                if eascii and char != eascii:
                    # filter out chars being sent with alt+key on Linux
                    if scancode.ALT not in mod:
                        # with IME, the text is sent together with the final Enter keypress.
                        self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, None, None)))
                    else:
                        # final keypress such as space, CR have IME meaning, we should ignore them
                        self._input_queue.put(signals.Event(signals.KEYB_DOWN, (eascii, scan, mod)))
                else:
                    self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, scan, mod)))
            else:
                # two separate events
                # previous keypress has no corresponding textinput
                self._flush_keypress()
                # current textinput has no corresponding keypress
                self._input_queue.put(signals.Event(signals.KEYB_DOWN, (char, None, None)))
            self._last_keypress = None

    def _toggle_fullscreen(self):
        """Togggle fullscreen mode."""
        self._fullscreen = not self._fullscreen
        self._window_sizer.set_canvas_size(fullscreen=self._fullscreen)
        self._do_create_window()
        self.busy = True


    ###########################################################################
    # screen drawing cycle

    def sleep(self, ms):
        """Sleep a tick to avoid hogging the cpu."""
        sdl2.SDL_Delay(ms)

    def _work(self):
        """Check screen and blink events; update screen if necessary."""
        if not self._has_window:
            return
        #               0      0      1      1
        # cycle         0 1234 5 6789 0 1234 5 6789 (0)
        # blink state   0 ---- 1 ---- 2 ---- 3 ---- (0)
        # cursor        off    on     off    on
        # blink         on     on     off    off
        #
        # blink state remains constant if blink not enabled
        # cursor blinks only if _is_text_mode and _blink_enabled
        # cursor visible every cycle between 5 and 10, 15 and 20
        tick = sdl2.SDL_GetTicks()
        if tick - self._last_tick >= CYCLE_TIME:
            self._last_tick = tick
            self._cycle += 1
            if self._cycle == BLINK_CYCLES * N_BLINK_STATES:
                self._cycle = 0
            # blink state
            blink_state, blink_tock = divmod(self._cycle, BLINK_CYCLES)
            if not self._blink_enabled:
                blink_state = 1
            # flip display fully if changed, use cache if just blinking
            if self.busy:
                self._clear_display_cache()
                self._flip_busy(blink_state)
                self.busy = False
            elif self._blink_enabled and blink_tock == 0:
                self._flip_lazy(blink_state)

    def _clear_display_cache(self):
        """Clear cursor cache on busy flip."""
        # one cache per blink state
        self._has_display_cache = [False] * N_BLINK_STATES

    def _flip_lazy(self, blink_state):
        """Blink the cursor only, to avoid doing all the scaling and converting work."""
        if self._has_display_cache[blink_state]:
            sdl2.SDL_BlitSurface(
                self._display_cache[blink_state], None, self._display_surface, None
            )
            sdl2.SDL_UpdateWindowSurface(self._display)
        else:
            # if we don't have a cache for this state, build it
            self._flip_busy(blink_state)

    def _flip_busy(self, blink_state):
        """Draw the canvas to the screen."""
        if self._pixel_packing:
            work_surface = self._create_composite_surface()
        else:
            work_surface = self._window_surface[self._vpagenum]
        pixelformat = self._display_surface.contents.format
        # apply cursor to work surface
        with self._show_cursor(blink_state % 2):
            # convert 8-bit work surface to (usually) 32-bit display surface format
            sdl2.SDL_SetSurfacePalette(work_surface, self._palette[blink_state // 2])
            conv = sdl2.SDL_ConvertSurface(work_surface, pixelformat, 0)
        if self._pixel_packing:
            sdl2.SDL_FreeSurface(work_surface)
        # create clipboard feedback
        if self._clipboard_interface.active():
            self._show_clipboard(conv)
        # scale surface to final dimensions and flip
        self._scale_and_flip(conv, blink_state)
        # destroy the temporary surface
        sdl2.SDL_FreeSurface(conv)

    def _scale_and_flip(self, conv, blink_state):
        """Scale converted surface and flip onto display."""
        # determine letterbox dimensions
        xshift, yshift = self._window_sizer.letterbox_shift
        window_w, window_h = self._window_sizer.window_size
        target_rect = sdl2.SDL_Rect(xshift, yshift, window_w, window_h)
        if not self._smooth:
            sdl2.SDL_BlitScaled(conv, None, self._display_surface, target_rect)
        else:
            # smooth-scale converted surface
            scalex, scaley = self._window_sizer.scale
            # only free the surface just before zoomSurface needs to re-allocate
            # so that the memory block is highly likely to be easily available
            # this seems to avoid unpredictable delays
            sdl2.SDL_FreeSurface(self._zoomed_surface)
            # SMOOTHING_ON = 1
            self._zoomed_surface = _smooth_zoom(conv, scalex, scaley, 1)
            # blit onto display
            sdl2.SDL_BlitSurface(self._zoomed_surface, None, self._display_surface, target_rect)
        # save in display cache for this blink state
        sdl2.SDL_BlitSurface(self._display_surface, None, self._display_cache[blink_state], None)
        self._has_display_cache[blink_state] = True
        # flip the display
        sdl2.SDL_UpdateWindowSurface(self._display)

    @contextmanager
    def _show_cursor(self, cursor_state):
        """Draw or remove the cursor on the visible page."""
        if not self._cursor_visible or self._vpagenum != self._apagenum or not cursor_state:
            yield
        else:
            pixels = self._canvas_pixels[self._apagenum]
            height = self._cursor_to + 1 - self._cursor_from
            top = (self._cursor_row-1) * self._font_height + self._cursor_from
            left = (self._cursor_col-1) * self._font_width
            cursor_area = pixels[left:left+self._cursor_width, top:top+height]
            # copy area under cursor
            under_cursor = numpy.copy(cursor_area)
            if self._is_text_mode:
                cursor_area[:] = self._cursor_attr
            else:
                cursor_area[:] ^= self._cursor_attr
            yield
            cursor_area[:] = under_cursor

    def _show_clipboard(self, conv):
        """Show clipboard feedback overlay."""
        n_rects = len(self._clipboard_interface.selection_rect)
        if not n_rects:
            return
        border_x, border_y = self._window_sizer.border_shift
        lcanvas_w, lcanvas_h = self._window_sizer.canvas_size_logical
        # create overlay for clipboard selection feedback
        overlay = sdl2.SDL_CreateRGBSurface(0, lcanvas_w, lcanvas_h, 32, 0, 0, 0, 0)
        sdl2.SDL_SetSurfaceBlendMode(overlay, sdl2.SDL_BLENDMODE_ADD)
        overlay_target = sdl2.SDL_Rect(border_x, border_y, lcanvas_w, lcanvas_h)
        rects = (sdl2.SDL_Rect * n_rects)(*(
            sdl2.SDL_Rect(*r) for r in self._clipboard_interface.selection_rect
        ))
        sdl2.SDL_FillRects(
            overlay, rects, n_rects,
            sdl2.SDL_MapRGBA(overlay.contents.format, 128, 0, 128, 0)
        )
        sdl2.SDL_BlitSurface(overlay, None, conv, overlay_target)
        sdl2.SDL_FreeSurface(overlay)

    def _create_composite_surface(self):
        """Pack multiple pixels into one for composite artifacts."""
        lwindow_w, lwindow_h = self._window_sizer.window_size_logical
        border_x, border_y = self._window_sizer.border_shift
        work_surface = sdl2.SDL_CreateRGBSurface(0, lwindow_w, lwindow_h, 8, 0, 0, 0, 0)
        # pack pixels into higher bpp
        bpp_out, bpp_in = self._pixel_packing
        src_array = self._canvas_pixels[self._vpagenum]
        width, _ = src_array.shape
        mask = 1<<bpp_in - 1
        step = bpp_out // bpp_in
        s = [(src_array[_p:width:step] & mask) << _p for _p in range(step)]
        packed = numpy.repeat(numpy.array(s).sum(axis=0), step, axis=0)
        # apply packed array onto work surface
        _pixels2d(work_surface.contents)[
            border_x : (lwindow_w - border_x),
            border_y : lwindow_h - border_y
        ] = packed
        return work_surface


    ###########################################################################
    # signal handlers

    def set_mode(self, mode_info):
        """Initialise a given text or graphics mode."""
        # unpack mode info struct
        self._is_text_mode = mode_info.is_text_mode
        self._font_height = mode_info.font_height
        self._font_width = mode_info.font_width
        self._num_pages = mode_info.num_pages
        self._blink_enabled = mode_info.has_blink
        # prebuilt glyphs
        # logical size
        canvas_width, canvas_height = mode_info.pixel_width, mode_info.pixel_height
        size_changed = self._window_sizer.set_canvas_size(
            canvas_width, canvas_height, fullscreen=self._fullscreen, resize_window=False
        )
        # only ever adjust window size if we're in native pixel mode
        if size_changed:
            if self._fullscreen:
                # clear any areas now outside the window
                sdl2.SDL_FillRect(self._display_surface, None, 0)
            else:
                # resize and recentre
                sdl2.SDL_SetWindowSize(self._display, *self._window_sizer.display_size)
                sdl2.SDL_SetWindowPosition(
                    self._display, sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED
                )
                # need to update surface pointer after a change in window size
                self._reset_display_caches()
        # set standard cursor
        self.set_cursor_shape(self._font_width, 0, self._font_height)
        # screen pages
        for surface in self._window_surface:
            sdl2.SDL_FreeSurface(surface)
        work_width, work_height = self._window_sizer.window_size_logical
        self._window_surface = [
            sdl2.SDL_CreateRGBSurface(0, work_width, work_height, 8, 0, 0, 0, 0)
            for _ in range(self._num_pages)
        ]
        border_x, border_y = self._window_sizer.border_shift
        self._canvas_pixels = [
            _pixels2d(canvas.contents)[
                border_x : work_width - border_x,
                border_y : work_height - border_y
            ] for canvas in self._window_surface
        ]
        # initialise clipboard
        self._clipboard_interface = clipboard.ClipboardInterface(
            self._clipboard_handler, self._input_queue,
            mode_info.width, mode_info.height, self._font_width, self._font_height,
            (canvas_width, canvas_height)
        )
        self.busy = True
        self._has_window = True

    def set_caption_message(self, msg):
        """Add a message to the window caption."""
        title = self._caption + (u' - ' + msg if msg else u'')
        sdl2.SDL_SetWindowTitle(self._display, title.encode('utf-8', errors='replace'))

    def set_clipboard_text(self, text, mouse):
        """Put text on the clipboard."""
        self._clipboard_handler.copy(text, mouse)

    def set_palette(self, rgb_palette_0, rgb_palette_1, pack_pixels):
        """Build the palette."""
        self._num_fore_attrs = min(16, len(rgb_palette_0))
        self._num_back_attrs = min(8, self._num_fore_attrs)
        rgb_palette_1 = rgb_palette_1 or rgb_palette_0
        # fill up the 8-bit palette with all combinations we need
        # blink states: 0 light up, 1 light down
        # bottom 128 are non-blink, top 128 blink to background
        show_palette_0 = rgb_palette_0[:self._num_fore_attrs] * (256//self._num_fore_attrs)
        show_palette_1 = rgb_palette_1[:self._num_fore_attrs] * (128//self._num_fore_attrs)
        for attr in (
                rgb_palette_1[:self._num_back_attrs] *
                (128 // self._num_fore_attrs // self._num_back_attrs)
            ):
            show_palette_1 += [attr]*self._num_fore_attrs
        colors_0 = (sdl2.SDL_Color * 256)(*(
            sdl2.SDL_Color(_r, _g, _b, 255)
            for (_r, _g, _b) in show_palette_0
        ))
        colors_1 = (sdl2.SDL_Color * 256)(*(
            sdl2.SDL_Color(_r, _g, _b, 255)
            for (_r, _g, _b) in show_palette_1
        ))
        sdl2.SDL_SetPaletteColors(self._palette[0], colors_0, 0, 256)
        sdl2.SDL_SetPaletteColors(self._palette[1], colors_1, 0, 256)
        self._pixel_packing = pack_pixels
        self.busy = True

    def set_border_attr(self, attr):
        """Change the border attribute."""
        window_w, window_h = self._window_sizer.window_size_logical
        border_x, border_y = self._window_sizer.border_shift
        border_rects = (sdl2.SDL_Rect*4)(
            sdl2.SDL_Rect(0, 0, window_w, border_y),
            sdl2.SDL_Rect(0, 0, border_x, window_h),
            sdl2.SDL_Rect(window_w-border_x, 0, border_x, window_h),
            sdl2.SDL_Rect(0, window_h-border_y, window_w, border_y),
        )
        for canvas in self._window_surface:
            sdl2.SDL_FillRects(canvas, border_rects, 4, attr)
        self._border_attr = attr
        self.busy = True

    def clear_rows(self, back_attr, start, stop):
        """Clear a range of screen rows."""
        self._canvas_pixels[self._apagenum][
            0 : self._window_sizer.width,
            (start-1)*self._font_height : stop*self._font_height
        ] = back_attr
        self.busy = True

    def set_page(self, vpage, apage):
        """Set the visible and active page."""
        self._vpagenum, self._apagenum = vpage, apage
        self.busy = True

    def copy_page(self, src, dst):
        """Copy source to destination page."""
        self._canvas_pixels[dst][:] = self._canvas_pixels[src][:]
        self.busy = True

    def show_cursor(self, cursor_on):
        """Change visibility of cursor."""
        self._cursor_visible = cursor_on
        self.busy = True

    def move_cursor(self, new_row, new_col):
        """Move the cursor to a new position."""
        if self._cursor_visible and (self._cursor_row, self._cursor_col) != (new_row, new_col):
            self.busy = True
        self._cursor_row, self._cursor_col = new_row, new_col

    def set_cursor_attr(self, attr):
        """Change attribute of cursor."""
        new_attr = attr % self._num_fore_attrs
        if self._cursor_visible and self._cursor_attr != new_attr:
            self.busy = True
        self._cursor_attr = new_attr

    def scroll_up(self, from_line, scroll_height, back_attr):
        """Scroll the screen up between from_line and scroll_height."""
        pixels = self._canvas_pixels[self._apagenum]
        # these are exclusive ranges [x0, x1) etc
        width = self._window_sizer.width
        new_y0, new_y1 = (from_line-1)*self._font_height, (scroll_height-1)*self._font_height
        old_y0, old_y1 = from_line*self._font_height, scroll_height*self._font_height
        pixels[0:width, new_y0:new_y1] = pixels[0:width, old_y0:old_y1]
        pixels[0:width, new_y1:old_y1] = numpy.full((width, old_y1-new_y1), back_attr, dtype=int)
        self.busy = True

    def scroll_down(self, from_line, scroll_height, back_attr):
        """Scroll the screen down between from_line and scroll_height."""
        pixels = self._canvas_pixels[self._apagenum]
        # these are exclusive ranges [x0, x1) etc
        width = self._window_sizer.width
        old_y0, old_y1 = (from_line-1)*self._font_height, (scroll_height-1)*self._font_height
        new_y0, new_y1 = from_line*self._font_height, scroll_height*self._font_height
        pixels[0:width, new_y0:new_y1] = pixels[0:width, old_y0:old_y1]
        pixels[0:width, old_y0:new_y0] = numpy.full((width, new_y0-old_y0), back_attr, dtype=int)
        self.busy = True

    def put_glyph(self, pagenum, row, col, char, is_fullwidth, fore, back, blink, underline, glyph):
        """Put a character at a given position."""
        if not self._is_text_mode:
            # in graphics mode, a put_rect call does the actual drawing
            return
        glyph = numpy.array(glyph).T
        # NOTE: in pygame plugin we used a surface fill for the NUL character
        #       which was an optimisation early on -- consider if we need speedup.
        ##if char == u'\0':
        ##    glyph = numpy.zeros((self._font_width, self._font_height))
        # _pixels2d uses column-major mode and hence [x][y] indexing (we can change this)
        glyph_width = glyph.shape[0]
        left, top = (col-1)*self._font_width, (row-1)*self._font_height
        attr = fore + self._num_fore_attrs*back + 128*blink
        # changle glyph color by numpy scalar mult (is there a better way?)
        self._canvas_pixels[pagenum][
            left : left+glyph_width,
            top : top+self._font_height
        ] = glyph*(attr-back) + back
        if underline:
            self._canvas_pixels[pagenum][
            left : left+glyph_width,
            top + self._font_height - 1 : top + self._font_height
        ] = attr
        self.busy = True

    def set_cursor_shape(self, width, from_line, to_line):
        """Build a sprite for the cursor."""
        self._cursor_width = width
        self._cursor_from, self._cursor_to = from_line, to_line
        if self._cursor_visible:
            self.busy = True

    def fill_rect(self, pagenum, x0, y0, x1, y1, index):
        """Fill a rectangle in a solid attribute."""
        self._canvas_pixels[pagenum][x0:x1+1, y0:y1+1] = index
        self.busy = True

    def put_rect(self, pagenum, x0, y0, x1, y1, array):
        """Apply numpy array [y][x] of attributes to an area."""
        # reference the destination area
        self._canvas_pixels[pagenum][x0:x1+1, y0:y1+1] = numpy.array(array).T
        self.busy = True
