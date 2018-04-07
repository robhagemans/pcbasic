import os
from ctypes import POINTER, c_int, c_double
from .dll import DLL
from .surface import SDL_Surface


try:
    dll = DLL("SDL2_gfx", ["SDL2_gfx", "SDL2_gfx-1.0"],
              os.getenv("PYSDL2_DLL_PATH"))
except RuntimeError as exc:
    raise ImportError(exc)


def get_dll_file():
    """Gets the file name of the loaded SDL2_gfx library."""
    return dll.libfile

_bind = dll.bind_function


SMOOTHING_OFF = 0
SMOOTHING_ON = 1
zoomSurface = _bind("zoomSurface", [POINTER(SDL_Surface), c_double, c_double, c_int], POINTER(SDL_Surface))
