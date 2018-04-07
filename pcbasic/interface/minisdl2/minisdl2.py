import sys
import array
from ctypes import CFUNCTYPE, c_int, c_int8, c_uint8, c_int16, c_uint16, c_int32, \
    c_uint32, c_int64, c_uint64, c_size_t, c_void_p, c_char_p
from ctypes import Structure, POINTER, c_float

from .dll import _bind, nullfunc


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
