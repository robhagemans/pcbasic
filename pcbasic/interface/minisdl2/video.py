from ctypes import Structure, POINTER, c_int, c_void_p, c_char_p, c_float, \
    py_object, CFUNCTYPE
from .dll import _bind, nullfunc
from .stdinc import Uint16, Uint32, SDL_bool
from .rect import SDL_Rect #, SDL_Point
from .surface import SDL_Surface


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

