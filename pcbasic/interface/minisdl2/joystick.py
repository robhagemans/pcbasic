from ctypes import Structure, c_int, c_char_p, POINTER
from .dll import _bind, nullfunc
from .stdinc import Sint16, Sint32, Uint8, SDL_bool



class SDL_Joystick(Structure):
    pass


SDL_JoystickID = Sint32

SDL_NumJoysticks = _bind("SDL_NumJoysticks", None, c_int)
SDL_JoystickOpen = _bind("SDL_JoystickOpen", [c_int], POINTER(SDL_Joystick))

