from ctypes import Structure, c_int, c_char_p, POINTER
from .dll import _bind
from .minisdl2 import Uint8, Uint16, Uint32, SDL_bool
from .keycode import SDL_Keycode, SDL_Keymod
from .scancode import SDL_Scancode
from .rect import SDL_Rect
from .video import SDL_Window


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
