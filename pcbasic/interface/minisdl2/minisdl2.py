from .dll import _bind
from ctypes import CFUNCTYPE, c_int, c_int8, c_uint8, c_int16, c_uint16, c_int32, \
    c_uint32, c_int64, c_uint64, c_size_t, c_void_p, c_char_p


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


