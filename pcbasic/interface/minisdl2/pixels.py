from ctypes import Structure, POINTER, c_int, c_char_p, c_float
from .dll import _bind
from .endian import SDL_BYTEORDER, SDL_BIG_ENDIAN, SDL_LIL_ENDIAN
from .minisdl2 import Uint8, Uint16, Uint32, SDL_bool


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
