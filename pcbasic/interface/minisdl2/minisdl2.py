import sys
import array
from ctypes import CFUNCTYPE, c_int, c_int8, c_uint8, c_int16, c_uint16, c_int32, \
    c_uint32, c_int64, c_uint64, c_size_t, c_void_p, c_char_p
from ctypes import Structure, c_int, c_char_p, POINTER

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
