import sys
import array
import os
import warnings
from ctypes import CFUNCTYPE, c_int, c_int8, c_uint8, c_int16, c_uint16, c_int32, \
    c_uint32, c_int64, c_uint64, c_size_t, c_void_p, c_char_p
from ctypes import Structure, POINTER, c_float, c_double, py_object
from ctypes import CDLL
from ctypes.util import find_library


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

def _findlib(libnames, path=None):
    """."""
    platform = sys.platform
    if platform in ("win32",):
        pattern = "%s.dll"
    elif platform == "darwin":
        pattern = "lib%s.dylib"
    else:
        pattern = "lib%s.so"
    searchfor = libnames
    if type(libnames) is dict:
        # different library names for the platforms
        if platform not in libnames:
            platform = "DEFAULT"
        searchfor = libnames[platform]
    results = []
    if path:
        for libname in searchfor:
            for subpath in str.split(path, os.pathsep):
                dllfile = os.path.join(subpath, pattern % libname)
                if os.path.exists(dllfile):
                    results.append(dllfile)
    for libname in searchfor:
        dllfile = find_library(libname)
        if dllfile:
            results.append(dllfile)
    return results


class DLLWarning(Warning):
    pass


class DLL(object):
    """Function wrapper around the different DLL functions. Do not use or
    instantiate this one directly from your user code.
    """
    def __init__(self, libinfo, libnames, path=None):
        self._dll = None
        foundlibs = _findlib(libnames, path)
        dllmsg = "PYSDL2_DLL_PATH: %s" % (os.getenv("PYSDL2_DLL_PATH") or "unset")
        if len(foundlibs) == 0:
            raise RuntimeError("could not find any library for %s (%s)" %
                               (libinfo, dllmsg))
        for libfile in foundlibs:
            try:
                self._dll = CDLL(libfile)
                self._libfile = libfile
                break
            except Exception as exc:
                # Could not load the DLL, move to the next, but inform the user
                # about something weird going on - this may become noisy, but
                # is better than confusing the users with the RuntimeError below
                warnings.warn(repr(exc), DLLWarning)
        if self._dll is None:
            raise RuntimeError("found %s, but it's not usable for the library %s" %
                               (foundlibs, libinfo))
        if path is not None and sys.platform in ("win32",) and \
            path in self._libfile:
            os.environ["PATH"] = "%s;%s" % (path, os.environ["PATH"])

    def bind_function(self, funcname, args=None, returns=None, optfunc=None):
        """Binds the passed argument and return value types to the specified
        function."""
        func = getattr(self._dll, funcname, None)
        warnings.warn\
            ("function '%s' not found in %r, using replacement" %
             (funcname, self._dll), ImportWarning)
        if not func:
            if optfunc:
                warnings.warn\
                    ("function '%s' not found in %r, using replacement" %
                     (funcname, self._dll), ImportWarning)
                func = _nonexistent(funcname, optfunc)
            else:
                raise ValueError("could not find function '%s' in %r" %
                                 (funcname, self._dll))
        func.argtypes = args
        func.restype = returns
        return func

    @property
    def libfile(self):
        """Gets the filename of the loaded library."""
        return self._libfile


def _nonexistent(funcname, func):
    """A simple wrapper to mark functions and methods as nonexistent."""
    def wrapper(*fargs, **kw):
        warnings.warn("%s does not exist" % funcname,
                      category=RuntimeWarning, stacklevel=2)
        return func(*fargs, **kw)
    wrapper.__name__ = func.__name__
    return wrapper


def nullfunc(*args):
    """A simple no-op function to be used as dll replacement."""
    return

try:
    dll = DLL("SDL2", ["SDL2", "SDL2-2.0"], os.getenv("PYSDL2_DLL_PATH"))
except RuntimeError as exc:
    raise ImportError(exc)

def get_dll_file():
    """Gets the file name of the loaded SDL2 library."""
    return dll.libfile

_bind = dll.bind_function


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
