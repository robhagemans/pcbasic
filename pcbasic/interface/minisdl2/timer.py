from ctypes import CFUNCTYPE, c_void_p, c_int
from .dll import _bind
from .stdinc import Uint32, Uint64, SDL_bool


SDL_GetTicks = _bind("SDL_GetTicks", None, Uint32)
SDL_Delay = _bind("SDL_Delay", [Uint32])


