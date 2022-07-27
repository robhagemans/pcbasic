"""
This is a condensed version of Marcus von Appen's pysdl2,
containing only the functions I need. It is based on version 0.9.5.
The original package is at https://github.com/marcusva/py-sdl2

pysdl2 licence
==============
This software is distributed under the Public Domain. Since it is
not enough anymore to tell people: 'hey, just do with it whatever
you like to do', you can consider this software being distributed
under the CC0 Public Domain Dedication
(http://creativecommons.org/publicdomain/zero/1.0/legalcode.txt).

In cases, where the law prohibits the recognition of Public Domain
software, this software can be licensed under the zlib license as
stated below:

Copyright (C) 2012-2018 Marcus von Appen <marcus@sysfault.org>

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgement in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import sys
import array
from ctypes import CFUNCTYPE, c_int, c_int8, c_uint8, c_int16, c_uint16, c_int32
from ctypes import c_uint32, c_int64, c_uint64, c_size_t, c_void_p, c_char_p
from ctypes import Union, Structure, POINTER, c_float, c_double, c_char, py_object
from ctypes import c_int as _cint


# note that this module must have been imported and initialised by our caller previously
from .sdl2loader import sdl2_lib, gfx_lib

# code below this will need to use _bind to link to the DLL
if sdl2_lib:
    _bind = sdl2_lib.bind_function
else:
    raise ImportError('Failed to load SDL2 library.')



# stdinc.py

SDL_FALSE = 0
SDL_TRUE = 1

SDL_bool = c_int
Sint8 = c_int8
Uint8 = c_uint8
Sint16 = c_int16
Uint16 = c_uint16
Sint32 = c_int32
Uint32 = c_uint32
Sint64 = c_int64
Uint64 = c_uint64


# endian.py

SDL_LIL_ENDIAN = 1234
SDL_BIG_ENDIAN = 4321
if sys.byteorder == "little":
    SDL_BYTEORDER = SDL_LIL_ENDIAN
else:
    SDL_BYTEORDER = SDL_BIG_ENDIAN

SDL_Swap16 = lambda x: ((x << 8 & 0xFF00) | (x >> 8 & 0x00FF))
SDL_Swap32 = lambda x: (((x << 24) & 0xFF000000) |
                        ((x << 8) & 0x00FF0000) |
                        ((x >> 8) & 0x0000FF00) |
                        ((x >> 24) & 0x000000FF))
SDL_Swap64 = lambda x: ((SDL_Swap32(x & 0xFFFFFFFF) << 32) |
                        (SDL_Swap32(x >> 32 & 0xFFFFFFFF)))
def SDL_SwapFloat(x):
    ar = array.array("d", (x,))
    ar.byteswap()
    return ar[0]

def _nop(x):
    return x
if SDL_BYTEORDER == SDL_LIL_ENDIAN:
    SDL_SwapLE16 = _nop
    SDL_SwapLE32 = _nop
    SDL_SwapLE64 = _nop
    SDL_SwapFloatLE = _nop
    SDL_SwapBE16 = SDL_Swap16
    SDL_SwapBE32 = SDL_Swap32
    SDL_SwapBE64 = SDL_Swap64
    SDL_SwapFloatBE = SDL_SwapFloat
else:
    SDL_SwapLE16 = SDL_Swap16
    SDL_SwapLE32 = SDL_Swap32
    SDL_SwapLE64 = SDL_Swap64
    SDL_SwapFloatLE = SDL_SwapFloat
    SDL_SwapBE16 = _nop
    SDL_SwapBE32 = _nop
    SDL_SwapBE64 = _nop
    SDL_SwapFloatBE = _nop


# dll.py

def nullfunc(*args):
    """A simple no-op function to be used as dll replacement."""
    return

# error.py

SDL_SetError = _bind("SDL_SetError", [c_char_p], c_int)
SDL_GetError = _bind("SDL_GetError", None, c_char_p)
SDL_ClearError = _bind("SDL_ClearError")

SDL_ENOMEM = 0
SDL_EFREAD = 1
SDL_EFWRITE = 2
SDL_EFSEEK = 3
SDL_UNSUPPORTED = 4
SDL_LASTERROR = 5
SDL_errorcode = c_int
SDL_Error = _bind("SDL_Error", [SDL_errorcode], c_int)
SDL_OutOfMemory = SDL_Error(SDL_ENOMEM)
SDL_Unsupported = SDL_Error(SDL_UNSUPPORTED)
SDL_InvalidParamError = lambda x: SDL_SetError("Parameter '%s' is invalid" % (x))


# blendmode.py

SDL_BLENDMODE_ADD = 0x00000002
SDL_BlendMode = c_int


# clipboard.py

SDL_SetClipboardText = _bind("SDL_SetClipboardText", [c_char_p], c_int)
SDL_GetClipboardText = _bind("SDL_GetClipboardText", None, c_char_p)
SDL_HasClipboardText = _bind("SDL_HasClipboardText", None, SDL_bool)


# timer.py

SDL_GetTicks = _bind("SDL_GetTicks", None, Uint32)
SDL_Delay = _bind("SDL_Delay", [Uint32])


# mouse.py

SDL_BUTTON_LEFT = 1
SDL_BUTTON_MIDDLE = 2
SDL_BUTTON_RIGHT = 3


# joystick.py

class SDL_Joystick(Structure):
    pass

SDL_JoystickID = Sint32
SDL_NumJoysticks = _bind("SDL_NumJoysticks", None, c_int)
SDL_JoystickOpen = _bind("SDL_JoystickOpen", [c_int], POINTER(SDL_Joystick))


# rect.py

class SDL_Rect(Structure):
    _fields_ = [("x", c_int), ("y", c_int),
                ("w", c_int), ("h", c_int)]

    def __init__(self, x=0, y=0, w=0, h=0):
        super(SDL_Rect, self).__init__()
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def __repr__(self):
        return "SDL_Rect(x=%d, y=%d, w=%d, h=%d)" % (self.x, self.y, self.w,
                                                     self.h)

    def __copy__(self):
        return SDL_Rect(self.x, self.y, self.w, self.h)

    def __deepcopy__(self, memo):
        return SDL_Rect(self.x, self.y, self.w, self.h)

    def __eq__(self, rt):
        return self.x == rt.x and self.y == rt.y and \
            self.w == rt.w and self.h == rt.h

    def __ne__(self, rt):
        return self.x != rt.x or self.y != rt.y or \
            self.w != rt.w or self.h != rt.h


# pixels.py

class SDL_Color(Structure):
    _fields_ = [("r", Uint8),
                ("g", Uint8),
                ("b", Uint8),
                ("a", Uint8),
                ]

    def __init__(self, r=255, g=255, b=255, a=255):
        super(SDL_Color, self).__init__()
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    def __repr__(self):
        return "SDL_Color(r=%d, g=%d, b=%d, a=%d)" % (self.r, self.g, self.b,
                                                      self.a)

    def __copy__(self):
        return SDL_Color(self.r, self.g, self.b, self.a)

    def __deepcopy__(self, memo):
        return SDL_Color(self.r, self.g, self.b, self.a)

    def __eq__(self, color):
        return self.r == color.r and self.g == color.g and \
            self.b == color.b and self.a == color.a

    def __ne__(self, color):
        return self.r != color.r or self.g != color.g or self.b != color.b or \
            self.a != color.a

SDL_Colour = SDL_Color

class SDL_Palette(Structure):
    _fields_ = [("ncolors", c_int),
                ("colors", POINTER(SDL_Color)),
                ("version", Uint32),
                ("refcount", c_int)]


class SDL_PixelFormat(Structure):
    pass
SDL_PixelFormat._fields_ = \
    [("format", Uint32),
     ("palette", POINTER(SDL_Palette)),
     ("BitsPerPixel", Uint8),
     ("BytesPerPixel", Uint8),
     ("padding", Uint8 * 2),
     ("Rmask", Uint32),
     ("Gmask", Uint32),
     ("Bmask", Uint32),
     ("Amask", Uint32),
     ("Rloss", Uint8),
     ("Gloss", Uint8),
     ("Bloss", Uint8),
     ("Aloss", Uint8),
     ("Rshift", Uint8),
     ("Gshift", Uint8),
     ("Bshift", Uint8),
     ("Ashift", Uint8),
     ("refcount", c_int),
     ("next", POINTER(SDL_PixelFormat))]

SDL_AllocPalette = _bind("SDL_AllocPalette", [c_int], POINTER(SDL_Palette))
SDL_SetPaletteColors = _bind("SDL_SetPaletteColors", [POINTER(SDL_Palette), POINTER(SDL_Color), c_int, c_int], c_int)
SDL_FreePalette = _bind("SDL_FreePalette", [POINTER(SDL_Palette)])
SDL_MapRGB = _bind("SDL_MapRGB", [POINTER(SDL_PixelFormat), Uint8, Uint8, Uint8], Uint32)
SDL_MapRGBA = _bind("SDL_MapRGBA", [POINTER(SDL_PixelFormat), Uint8, Uint8, Uint8, Uint8], Uint32)
SDL_GetRGB = _bind("SDL_GetRGB", [Uint32, POINTER(SDL_PixelFormat), POINTER(Uint8), POINTER(Uint8), POINTER(Uint8)])
SDL_GetRGBA = _bind("SDL_GetRGBA", [Uint32, POINTER(SDL_PixelFormat), POINTER(Uint8), POINTER(Uint8), POINTER(Uint8), POINTER(Uint8)])


# surface.py

SDL_SWSURFACE = 0
SDL_PREALLOC = 0x00000001
SDL_RLEACCEL = 0x00000002
SDL_DONTFREE = 0x00000004

SDL_MUSTLOCK = lambda s: ((s.flags & SDL_RLEACCEL) != 0)

class SDL_BlitMap(Structure):
    pass

class SDL_Surface(Structure):
    _fields_ = [("flags", Uint32),
                ("format", POINTER(SDL_PixelFormat)),
                ("w", c_int), ("h", c_int),
                ("pitch", c_int),
                ("pixels", c_void_p),
                ("userdata", c_void_p),
                ("locked", c_int),
                ("lock_data", c_void_p),
                ("clip_rect", SDL_Rect),
                ("map", POINTER(SDL_BlitMap)),
                ("refcount", c_int)
               ]

SDL_Blit = CFUNCTYPE(c_int, POINTER(SDL_Surface), POINTER(SDL_Rect), POINTER(SDL_Surface), POINTER(SDL_Rect))

SDL_CreateRGBSurface = _bind("SDL_CreateRGBSurface", [Uint32, c_int, c_int, c_int, Uint32, Uint32, Uint32, Uint32], POINTER(SDL_Surface))
SDL_CreateRGBSurfaceFrom = _bind("SDL_CreateRGBSurfaceFrom", [c_void_p, c_int, c_int, c_int, c_int, Uint32, Uint32, Uint32, Uint32], POINTER(SDL_Surface))
SDL_CreateRGBSurfaceWithFormat = _bind("SDL_CreateRGBSurfaceWithFormat", [Uint32, c_int, c_int, c_int, Uint32], POINTER(SDL_Surface), optfunc=nullfunc)
SDL_CreateRGBSurfaceWithFormatFrom = _bind("SDL_CreateRGBSurfaceWithFormatFrom", [c_void_p, c_int, c_int, c_int, c_int, Uint32], POINTER(SDL_Surface), optfunc=nullfunc)
SDL_FreeSurface = _bind("SDL_FreeSurface", [POINTER(SDL_Surface)])
SDL_SetSurfacePalette = _bind("SDL_SetSurfacePalette", [POINTER(SDL_Surface), POINTER(SDL_Palette)], c_int)
SDL_LockSurface = _bind("SDL_LockSurface", [POINTER(SDL_Surface)], c_int)
SDL_UnlockSurface = _bind("SDL_UnlockSurface", [POINTER(SDL_Surface)])

SDL_SetColorKey = _bind("SDL_SetColorKey", [POINTER(SDL_Surface), c_int, Uint32], c_int)
SDL_GetColorKey = _bind("SDL_GetColorKey", [POINTER(SDL_Surface), POINTER(Uint32)], c_int)
SDL_SetSurfaceBlendMode = _bind("SDL_SetSurfaceBlendMode", [POINTER(SDL_Surface), SDL_BlendMode], c_int)
SDL_GetSurfaceBlendMode = _bind("SDL_GetSurfaceBlendMode", [POINTER(SDL_Surface), POINTER(SDL_BlendMode)], c_int)
SDL_SetClipRect = _bind("SDL_SetClipRect", [POINTER(SDL_Surface), POINTER(SDL_Rect)], SDL_bool)
SDL_GetClipRect = _bind("SDL_GetClipRect", [POINTER(SDL_Surface), POINTER(SDL_Rect)])
SDL_ConvertSurface = _bind("SDL_ConvertSurface", [POINTER(SDL_Surface), POINTER(SDL_PixelFormat), Uint32], POINTER(SDL_Surface))
SDL_ConvertSurfaceFormat = _bind("SDL_ConvertSurfaceFormat", [POINTER(SDL_Surface), Uint32, Uint32], POINTER(SDL_Surface))
SDL_ConvertPixels = _bind("SDL_ConvertPixels", [c_int, c_int, Uint32, c_void_p, c_int, Uint32, c_void_p, c_int], c_int)
SDL_FillRect = _bind("SDL_FillRect", [POINTER(SDL_Surface), POINTER(SDL_Rect), Uint32], c_int)
SDL_FillRects = _bind("SDL_FillRects", [POINTER(SDL_Surface), POINTER(SDL_Rect), c_int, Uint32], c_int)

SDL_UpperBlit = _bind("SDL_UpperBlit", [POINTER(SDL_Surface), POINTER(SDL_Rect), POINTER(SDL_Surface), POINTER(SDL_Rect)], c_int)
SDL_BlitSurface = SDL_UpperBlit
SDL_UpperBlitScaled = _bind("SDL_UpperBlitScaled", [POINTER(SDL_Surface), POINTER(SDL_Rect), POINTER(SDL_Surface), POINTER(SDL_Rect)], c_int)
SDL_BlitScaled = SDL_UpperBlitScaled


# audio.py

SDL_AudioFormat = Uint16

AUDIO_U8 = 0x0008
AUDIO_S8 = 0x8008

AUDIO_U16LSB = 0x0010
AUDIO_S16LSB = 0x8010
AUDIO_U16MSB = 0x1010
AUDIO_S16MSB = 0x9010
AUDIO_S32LSB = 0x8020
AUDIO_S32MSB = 0x9020
AUDIO_F32LSB = 0x8120
AUDIO_F32MSB = 0x9120


if SDL_BYTEORDER == SDL_LIL_ENDIAN:
    AUDIO_U16SYS = AUDIO_U16LSB
    AUDIO_S16SYS = AUDIO_S16LSB
    AUDIO_S32SYS = AUDIO_S32LSB
    AUDIO_F32SYS = AUDIO_F32LSB
else:
    AUDIO_U16SYS = AUDIO_U16MSB
    AUDIO_S16SYS = AUDIO_S16MSB
    AUDIO_S32SYS = AUDIO_S32MSB
    AUDIO_F32SYS = AUDIO_F32MSB


SDL_AudioCallback = CFUNCTYPE(None, c_void_p, POINTER(Uint8), c_int)

class SDL_AudioSpec(Structure):
    _fields_ = [("freq", c_int),
                ("format", SDL_AudioFormat),
                ("channels", Uint8),
                ("silence", Uint8),
                ("samples", Uint16),
                ("padding", Uint16),
                ("size", Uint32),
                ("callback", SDL_AudioCallback),
                ("userdata", c_void_p)
                ]
    def __init__(self, freq, aformat, channels, samples,
                 callback=SDL_AudioCallback(), userdata=c_void_p(0)):
        super(SDL_AudioSpec, self).__init__()
        self.freq = freq
        self.format = aformat
        self.channels = channels
        self.samples = samples
        self.callback = callback
        self.userdata = userdata

SDL_AudioInit = _bind("SDL_AudioInit", [c_char_p], c_int)
SDL_AudioQuit = _bind("SDL_AudioQuit")
SDL_OpenAudio = _bind("SDL_OpenAudio", [POINTER(SDL_AudioSpec), POINTER(SDL_AudioSpec)], c_int)
SDL_AudioDeviceID = Uint32
SDL_OpenAudioDevice = _bind("SDL_OpenAudioDevice", [c_char_p, c_int, POINTER(SDL_AudioSpec), POINTER(SDL_AudioSpec), c_int], SDL_AudioDeviceID)
SDL_AudioStatus = c_int
SDL_PauseAudio = _bind("SDL_PauseAudio", [c_int])
SDL_PauseAudioDevice = _bind("SDL_PauseAudioDevice", [SDL_AudioDeviceID, c_int])
SDL_LockAudio = _bind("SDL_LockAudio")
SDL_LockAudioDevice = _bind("SDL_LockAudioDevice", [SDL_AudioDeviceID])
SDL_UnlockAudio = _bind("SDL_UnlockAudio")
SDL_UnlockAudioDevice = _bind("SDL_UnlockAudioDevice", [SDL_AudioDeviceID])
SDL_CloseAudio = _bind("SDL_CloseAudio")
SDL_CloseAudioDevice = _bind("SDL_CloseAudioDevice", [SDL_AudioDeviceID])


# video.py

class SDL_DisplayMode(Structure):
    _fields_ = [("format", Uint32),
                ("w", c_int),
                ("h", c_int),
                ("refresh_rate", c_int),
                ("driverdata", c_void_p)
               ]
    def __init__(self, format_=0, w=0, h=0, refresh_rate=0):
        super(SDL_DisplayMode, self).__init__()
        self.format = format_
        self.w = w
        self.h = h
        self.refresh_rate = refresh_rate

    def __repr__(self):
        return "SDL_DisplayMode(format=%d, w=%d, h=%d, refresh_rate=%d)" % \
            (self.format, self.w, self.h, self.refresh_rate)

    def __eq__(self, mode):
        return self.format == mode.format and self.w == mode.w and \
            self.h == mode.h and self.refresh_rate == mode.refresh_rate

    def __ne__(self, mode):
        return self.format != mode.format or self.w != mode.w or \
            self.h != mode.h or self.refresh_rate != mode.refresh_rate

class SDL_Window(Structure):
    pass

SDL_WindowFlags = c_int
SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_SHOWN = 0x00000004
SDL_WINDOW_BORDERLESS = 0x00000010
SDL_WINDOW_RESIZABLE = 0x00000020
SDL_WINDOW_MAXIMIZED = 0x00000080
SDL_WINDOW_INPUT_FOCUS = 0x00000200
SDL_WINDOW_FULLSCREEN_DESKTOP = (SDL_WINDOW_FULLSCREEN | 0x00001000)
SDL_WINDOW_ALLOW_HIGHDPI = 0x00002000

SDL_WINDOWPOS_CENTERED_MASK = 0x2FFF0000
SDL_WINDOWPOS_CENTERED_DISPLAY = lambda x: (SDL_WINDOWPOS_CENTERED_MASK | x)
SDL_WINDOWPOS_CENTERED = SDL_WINDOWPOS_CENTERED_DISPLAY(0)

SDL_WindowEventID = c_int

SDL_WINDOWEVENT_RESIZED = 5
SDL_WINDOWEVENT_ENTER = 10
SDL_WINDOWEVENT_LEAVE = 11
SDL_WINDOWEVENT_FOCUS_GAINED = 12
SDL_WINDOWEVENT_FOCUS_LOST = 13


SDL_VideoInit = _bind("SDL_VideoInit", [c_char_p], c_int)
SDL_VideoQuit = _bind("SDL_VideoQuit")
SDL_GetCurrentDisplayMode = _bind("SDL_GetCurrentDisplayMode", [c_int, POINTER(SDL_DisplayMode)], c_int)
SDL_CreateWindow = _bind("SDL_CreateWindow", [c_char_p, c_int, c_int, c_int, c_int, Uint32], POINTER(SDL_Window))
SDL_GetWindowFlags = _bind("SDL_GetWindowFlags", [POINTER(SDL_Window)], Uint32)
SDL_SetWindowTitle = _bind("SDL_SetWindowTitle", [POINTER(SDL_Window), c_char_p])
SDL_GetWindowTitle = _bind("SDL_GetWindowTitle", [POINTER(SDL_Window)], c_char_p)
SDL_SetWindowIcon = _bind("SDL_SetWindowIcon", [POINTER(SDL_Window), POINTER(SDL_Surface)])
SDL_SetWindowPosition = _bind("SDL_SetWindowPosition", [POINTER(SDL_Window), c_int, c_int])
SDL_GetWindowPosition = _bind("SDL_GetWindowPosition", [POINTER(SDL_Window), POINTER(c_int), POINTER(c_int)])
SDL_SetWindowSize = _bind("SDL_SetWindowSize", [POINTER(SDL_Window), c_int, c_int])
SDL_GetWindowSize = _bind("SDL_GetWindowSize", [POINTER(SDL_Window), POINTER(c_int), POINTER(c_int)])
SDL_MaximizeWindow = _bind("SDL_MaximizeWindow", [POINTER(SDL_Window)])
SDL_RestoreWindow = _bind("SDL_RestoreWindow", [POINTER(SDL_Window)])
SDL_SetWindowFullscreen = _bind("SDL_SetWindowFullscreen", [POINTER(SDL_Window), Uint32], c_int)
SDL_GetWindowSurface = _bind("SDL_GetWindowSurface", [POINTER(SDL_Window)], POINTER(SDL_Surface))
SDL_UpdateWindowSurface = _bind("SDL_UpdateWindowSurface", [POINTER(SDL_Window)], c_int)
SDL_UpdateWindowSurfaceRects = _bind("SDL_UpdateWindowSurfaceRects", [POINTER(SDL_Window), POINTER(SDL_Rect), c_int], c_int)
SDL_DestroyWindow = _bind("SDL_DestroyWindow", [POINTER(SDL_Window)])
SDL_SetWindowResizable = _bind("SDL_SetWindowResizable", [POINTER(SDL_Window), SDL_bool], optfunc=nullfunc)

# keyboard.py

SDL_Keycode = c_int32
SDL_Keymod = c_int
SDL_Scancode = c_int


class SDL_Keysym(Structure):
    _fields_ = [("scancode", SDL_Scancode),
                ("sym", SDL_Keycode),
                ("mod", Uint16),
                ("unused", Uint32)
                ]

SDL_GetModState = _bind("SDL_GetModState", None, SDL_Keymod)
SDL_SetModState = _bind("SDL_SetModState", [SDL_Keymod])
SDL_StartTextInput = _bind("SDL_StartTextInput")
SDL_IsTextInputActive = _bind("SDL_IsTextInputActive", None, SDL_bool)
SDL_StopTextInput = _bind("SDL_StopTextInput")
SDL_SetTextInputRect = _bind("SDL_SetTextInputRect", [POINTER(SDL_Rect)])


# scancode.py

SDL_SCANCODE_UNKNOWN = 0
SDL_SCANCODE_A = 4
SDL_SCANCODE_B = 5
SDL_SCANCODE_C = 6
SDL_SCANCODE_D = 7
SDL_SCANCODE_E = 8
SDL_SCANCODE_F = 9
SDL_SCANCODE_G = 10
SDL_SCANCODE_H = 11
SDL_SCANCODE_I = 12
SDL_SCANCODE_J = 13
SDL_SCANCODE_K = 14
SDL_SCANCODE_L = 15
SDL_SCANCODE_M = 16
SDL_SCANCODE_N = 17
SDL_SCANCODE_O = 18
SDL_SCANCODE_P = 19
SDL_SCANCODE_Q = 20
SDL_SCANCODE_R = 21
SDL_SCANCODE_S = 22
SDL_SCANCODE_T = 23
SDL_SCANCODE_U = 24
SDL_SCANCODE_V = 25
SDL_SCANCODE_W = 26
SDL_SCANCODE_X = 27
SDL_SCANCODE_Y = 28
SDL_SCANCODE_Z = 29

SDL_SCANCODE_1 = 30
SDL_SCANCODE_2 = 31
SDL_SCANCODE_3 = 32
SDL_SCANCODE_4 = 33
SDL_SCANCODE_5 = 34
SDL_SCANCODE_6 = 35
SDL_SCANCODE_7 = 36
SDL_SCANCODE_8 = 37
SDL_SCANCODE_9 = 38
SDL_SCANCODE_0 = 39

SDL_SCANCODE_RETURN = 40
SDL_SCANCODE_ESCAPE = 41
SDL_SCANCODE_BACKSPACE = 42
SDL_SCANCODE_TAB = 43
SDL_SCANCODE_SPACE = 44

SDL_SCANCODE_MINUS = 45
SDL_SCANCODE_EQUALS = 46
SDL_SCANCODE_LEFTBRACKET = 47
SDL_SCANCODE_RIGHTBRACKET = 48
SDL_SCANCODE_BACKSLASH = 49

SDL_SCANCODE_NONUSHASH = 50

SDL_SCANCODE_SEMICOLON = 51
SDL_SCANCODE_APOSTROPHE = 52
SDL_SCANCODE_GRAVE = 53

SDL_SCANCODE_COMMA = 54
SDL_SCANCODE_PERIOD = 55
SDL_SCANCODE_SLASH = 56

SDL_SCANCODE_CAPSLOCK = 57

SDL_SCANCODE_F1 = 58
SDL_SCANCODE_F2 = 59
SDL_SCANCODE_F3 = 60
SDL_SCANCODE_F4 = 61
SDL_SCANCODE_F5 = 62
SDL_SCANCODE_F6 = 63
SDL_SCANCODE_F7 = 64
SDL_SCANCODE_F8 = 65
SDL_SCANCODE_F9 = 66
SDL_SCANCODE_F10 = 67
SDL_SCANCODE_F11 = 68
SDL_SCANCODE_F12 = 69

SDL_SCANCODE_PRINTSCREEN = 70
SDL_SCANCODE_SCROLLLOCK = 71
SDL_SCANCODE_PAUSE = 72
SDL_SCANCODE_INSERT = 73

SDL_SCANCODE_HOME = 74
SDL_SCANCODE_PAGEUP = 75
SDL_SCANCODE_DELETE = 76
SDL_SCANCODE_END = 77
SDL_SCANCODE_PAGEDOWN = 78
SDL_SCANCODE_RIGHT = 79
SDL_SCANCODE_LEFT = 80
SDL_SCANCODE_DOWN = 81
SDL_SCANCODE_UP = 82

SDL_SCANCODE_NUMLOCKCLEAR = 83
SDL_SCANCODE_KP_DIVIDE = 84
SDL_SCANCODE_KP_MULTIPLY = 85
SDL_SCANCODE_KP_MINUS = 86
SDL_SCANCODE_KP_PLUS = 87
SDL_SCANCODE_KP_ENTER = 88
SDL_SCANCODE_KP_1 = 89
SDL_SCANCODE_KP_2 = 90
SDL_SCANCODE_KP_3 = 91
SDL_SCANCODE_KP_4 = 92
SDL_SCANCODE_KP_5 = 93
SDL_SCANCODE_KP_6 = 94
SDL_SCANCODE_KP_7 = 95
SDL_SCANCODE_KP_8 = 96
SDL_SCANCODE_KP_9 = 97
SDL_SCANCODE_KP_0 = 98
SDL_SCANCODE_KP_PERIOD = 99

SDL_SCANCODE_NONUSBACKSLASH = 100
SDL_SCANCODE_KP_EQUALS = 103
SDL_SCANCODE_MENU = 118

SDL_SCANCODE_INTERNATIONAL1 = 135
SDL_SCANCODE_INTERNATIONAL2 = 136
SDL_SCANCODE_INTERNATIONAL3 = 137

SDL_SCANCODE_LANG1 = 144
SDL_SCANCODE_LANG2 = 145
SDL_SCANCODE_LANG3 = 146
SDL_SCANCODE_LANG4 = 147
SDL_SCANCODE_LANG5 = 148

SDL_SCANCODE_SYSREQ = 154

SDL_SCANCODE_LCTRL = 224
SDL_SCANCODE_LSHIFT = 225
SDL_SCANCODE_LALT = 226
SDL_SCANCODE_LGUI = 227
SDL_SCANCODE_RCTRL = 228
SDL_SCANCODE_RSHIFT = 229
SDL_SCANCODE_RALT = 230
SDL_SCANCODE_RGUI = 231

SDL_SCANCODE_MODE = 257


# keycode.py

SDLK_SCANCODE_MASK = 1 << 30
SDL_SCANCODE_TO_KEYCODE = lambda x: (x | SDLK_SCANCODE_MASK)

KMOD_NONE = 0x0000
KMOD_LSHIFT = 0x0001
KMOD_RSHIFT = 0x0002
KMOD_LCTRL = 0x0040
KMOD_RCTRL = 0x0080
KMOD_LALT = 0x0100
KMOD_RALT = 0x0200
KMOD_LGUI = 0x0400
KMOD_RGUI = 0x0800
KMOD_NUM = 0x1000
KMOD_CAPS = 0x2000
KMOD_MODE = 0x4000
KMOD_RESERVED = 0x8000

KMOD_CTRL = KMOD_LCTRL | KMOD_RCTRL
KMOD_SHIFT = KMOD_LSHIFT | KMOD_RSHIFT
KMOD_ALT = KMOD_LALT | KMOD_RALT
KMOD_GUI = KMOD_LGUI | KMOD_RGUI

SDLK_UNKNOWN = 0

SDLK_RETURN = ord('\r')
SDLK_ESCAPE = ord('\033')
SDLK_BACKSPACE = ord('\b')
SDLK_TAB = ord('\t')
SDLK_SPACE = ord(' ')
SDLK_EXCLAIM = ord('!')
SDLK_QUOTEDBL = ord('"')
SDLK_HASH = ord('#')
SDLK_PERCENT = ord('%')
SDLK_DOLLAR = ord('$')
SDLK_AMPERSAND = ord('&')
SDLK_QUOTE = ord('\'')
SDLK_LEFTPAREN = ord('(')
SDLK_RIGHTPAREN = ord(')')
SDLK_ASTERISK = ord('*')
SDLK_PLUS = ord('+')
SDLK_COMMA = ord(',')
SDLK_MINUS = ord('-')
SDLK_PERIOD = ord('.')
SDLK_SLASH = ord('/')

SDLK_0 = ord('0')
SDLK_1 = ord('1')
SDLK_2 = ord('2')
SDLK_3 = ord('3')
SDLK_4 = ord('4')
SDLK_5 = ord('5')
SDLK_6 = ord('6')
SDLK_7 = ord('7')
SDLK_8 = ord('8')
SDLK_9 = ord('9')

SDLK_COLON = ord(':')
SDLK_SEMICOLON = ord(';')
SDLK_LESS = ord('<')
SDLK_EQUALS = ord('=')
SDLK_GREATER = ord('>')
SDLK_QUESTION = ord('?')
SDLK_AT = ord('@')

SDLK_LEFTBRACKET = ord('[')
SDLK_BACKSLASH = ord('\\')
SDLK_RIGHTBRACKET = ord(']')
SDLK_CARET = ord('^')
SDLK_UNDERSCORE = ord('_')
SDLK_BACKQUOTE = ord('`')

SDLK_a = ord('a')
SDLK_b = ord('b')
SDLK_c = ord('c')
SDLK_d = ord('d')
SDLK_e = ord('e')
SDLK_f = ord('f')
SDLK_g = ord('g')
SDLK_h = ord('h')
SDLK_i = ord('i')
SDLK_j = ord('j')
SDLK_k = ord('k')
SDLK_l = ord('l')
SDLK_m = ord('m')
SDLK_n = ord('n')
SDLK_o = ord('o')
SDLK_p = ord('p')
SDLK_q = ord('q')
SDLK_r = ord('r')
SDLK_s = ord('s')
SDLK_t = ord('t')
SDLK_u = ord('u')
SDLK_v = ord('v')
SDLK_w = ord('w')
SDLK_x = ord('x')
SDLK_y = ord('y')
SDLK_z = ord('z')

SDLK_CAPSLOCK = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_CAPSLOCK)

SDLK_F1 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F1)
SDLK_F2 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F2)
SDLK_F3 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F3)
SDLK_F4 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F4)
SDLK_F5 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F5)
SDLK_F6 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F6)
SDLK_F7 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F7)
SDLK_F8 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F8)
SDLK_F9 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F9)
SDLK_F10 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F10)
SDLK_F11 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F11)
SDLK_F12 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_F12)

SDLK_PRINTSCREEN = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_PRINTSCREEN)
SDLK_SCROLLLOCK = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_SCROLLLOCK)
SDLK_PAUSE = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_PAUSE)
SDLK_INSERT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_INSERT)
SDLK_HOME = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_HOME)
SDLK_PAGEUP = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_PAGEUP)
SDLK_DELETE = ord('\177')
SDLK_END = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_END)
SDLK_PAGEDOWN = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_PAGEDOWN)
SDLK_RIGHT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_RIGHT)
SDLK_LEFT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_LEFT)
SDLK_DOWN = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_DOWN)
SDLK_UP = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_UP)

SDLK_NUMLOCKCLEAR = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_NUMLOCKCLEAR)
SDLK_KP_DIVIDE = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_DIVIDE)
SDLK_KP_MULTIPLY = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_MULTIPLY)
SDLK_KP_MINUS = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_MINUS)
SDLK_KP_PLUS = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_PLUS)
SDLK_KP_ENTER = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_ENTER)
SDLK_KP_1 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_1)
SDLK_KP_2 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_2)
SDLK_KP_3 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_3)
SDLK_KP_4 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_4)
SDLK_KP_5 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_5)
SDLK_KP_6 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_6)
SDLK_KP_7 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_7)
SDLK_KP_8 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_8)
SDLK_KP_9 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_9)
SDLK_KP_0 = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_0)
SDLK_KP_PERIOD = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_PERIOD)

SDLK_KP_EQUALS = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_KP_EQUALS)

SDLK_LCTRL = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_LCTRL)
SDLK_LSHIFT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_LSHIFT)
SDLK_LALT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_LALT)
SDLK_LGUI = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_LGUI)
SDLK_RCTRL = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_RCTRL)
SDLK_RSHIFT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_RSHIFT)
SDLK_RALT = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_RALT)
SDLK_RGUI = SDL_SCANCODE_TO_KEYCODE(SDL_SCANCODE_RGUI)


# events.py

SDL_QUIT = 0x100
SDL_WINDOWEVENT = 0x200
SDL_SYSWMEVENT = 0x201
SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301
SDL_TEXTEDITING = 0x302
SDL_TEXTINPUT = 0x303
SDL_MOUSEMOTION = 0x400
SDL_MOUSEBUTTONDOWN = 0x401
SDL_MOUSEBUTTONUP = 0x402
SDL_JOYAXISMOTION = 0x600
SDL_JOYBUTTONDOWN = 0x603
SDL_JOYBUTTONUP = 0x604

class SDL_WindowEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("event", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("data1", Sint32),
                ("data2", Sint32)
                ]

class SDL_KeyboardEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("state", Uint8),
                ("repeat", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("keysym", SDL_Keysym)
                ]

SDL_TEXTEDITINGEVENT_TEXT_SIZE = 32

class SDL_TextEditingEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("text", (c_char * SDL_TEXTEDITINGEVENT_TEXT_SIZE)),
                ("start", Sint32),
                ("length", Sint32)
                ]

SDL_TEXTINPUTEVENT_TEXT_SIZE = 32
class SDL_TextInputEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("text", (c_char * SDL_TEXTINPUTEVENT_TEXT_SIZE))
                ]

class SDL_MouseMotionEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("which", Uint32),
                ("state", Uint32),
                ("x", Sint32),
                ("y", Sint32),
                ("xrel", Sint32),
                ("yrel", Sint32)
                ]

class SDL_MouseButtonEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("which", Uint32),
                ("button", Uint8),
                ("state", Uint8),
                ("clicks", Uint8),
                ("padding1", Uint8),
                ("x", Sint32),
                ("y", Sint32)
                ]

class SDL_JoyAxisEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("axis", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("value", Sint16),
                ("padding4", Uint16)
                ]

class SDL_JoyButtonEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("button", Uint8),
                ("state", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8)
                ]

class SDL_QuitEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32)
                ]

class SDL_Event(Union):
    _fields_ = [("type", Uint32),
                ("window", SDL_WindowEvent),
                ("key", SDL_KeyboardEvent),
                ("edit", SDL_TextEditingEvent),
                ("text", SDL_TextInputEvent),
                ("motion", SDL_MouseMotionEvent),
                ("button", SDL_MouseButtonEvent),
                ("jaxis", SDL_JoyAxisEvent),
                ("jbutton", SDL_JoyButtonEvent),
                ("quit", SDL_QuitEvent),
                ("padding", (Uint8 * 56)),
                ]

SDL_PollEvent = _bind("SDL_PollEvent", [POINTER(SDL_Event)], c_int)


# __init__.py

# At least Win32 platforms need this now.
_SDL_SetMainReady = _bind("SDL_SetMainReady")
_SDL_SetMainReady()


SDL_INIT_TIMER = 0x00000001
SDL_INIT_AUDIO = 0x00000010
SDL_INIT_VIDEO = 0x00000020
SDL_INIT_JOYSTICK = 0x00000200
SDL_INIT_HAPTIC = 0x00001000
SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_INIT_EVENTS = 0x00004000
SDL_INIT_NOPARACHUTE = 0x00100000
SDL_INIT_EVERYTHING = (SDL_INIT_TIMER | SDL_INIT_AUDIO | SDL_INIT_VIDEO |
                       SDL_INIT_EVENTS | SDL_INIT_JOYSTICK | SDL_INIT_HAPTIC |
                       SDL_INIT_GAMECONTROLLER)

SDL_Init = _bind("SDL_Init", [Uint32], _cint)
SDL_InitSubSystem = _bind("SDL_InitSubSystem", [Uint32], _cint)
SDL_QuitSubSystem = _bind("SDL_QuitSubSystem", [Uint32])
SDL_WasInit = _bind("SDL_WasInit", [Uint32], Uint32)
SDL_Quit = _bind("SDL_Quit")


# added RH
SDL_SetWindowGrab = _bind("SDL_SetWindowGrab", [POINTER(SDL_Window), SDL_bool])
SDL_SetHint = _bind("SDL_SetHint", [c_char_p, c_char_p])
SDL_HINT_GRAB_KEYBOARD = b"SDL_GRAB_KEYBOARD"


# gfx smooth zoom

if gfx_lib:
    SDL_gfx_zoomSurface = gfx_lib.bind_function(
        'zoomSurface',
        [POINTER(SDL_Surface), c_double, c_double, c_int],
        POINTER(SDL_Surface)
    )
else:
    SDL_gfx_zoomSurface = None
