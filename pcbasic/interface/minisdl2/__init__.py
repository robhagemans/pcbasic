"""
minisdl2
========
This is a condensed version of Marcus von Appen's pysdl2,
containing only the functions I need.
The original package is at https://github.com/marcusva/py-sdl2

pysdl2 licence
==============
This software is distributed under the Public Domain. Since it is
not enough anymore to tell people: 'hey, just do with it whatever
you like to do', you can consider this software being distributed
under the CC0 Public Domain Dedication
(http://creativecommons.org/publicdomain/zero/1.0/legalcode.txt).

In cases, where the law prohibits the recognition of Public Domain
software, this software can be licensed under the zlib license as
stated below:

Copyright (C) 2012-2018 Marcus von Appen <marcus@sysfault.org>

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgement in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.

"""

from .dll import get_dll_file, _bind
from ctypes import c_int as _cint

from .minisdl2 import *
from .audio import *
from .events import *
from .keyboard import *
from .pixels import *
from .rect import *
from .surface import *
from .video import *

from .keycode import *
from .scancode import *

# At least Win32 platforms need this now.
_SDL_SetMainReady = _bind("SDL_SetMainReady")
_SDL_SetMainReady()


SDL_INIT_TIMER = 0x00000001
SDL_INIT_AUDIO = 0x00000010
SDL_INIT_VIDEO = 0x00000020
SDL_INIT_JOYSTICK = 0x00000200
SDL_INIT_HAPTIC = 0x00001000
SDL_INIT_GAMECONTROLLER = 0x00002000
SDL_INIT_EVENTS = 0x00004000
SDL_INIT_NOPARACHUTE = 0x00100000
SDL_INIT_EVERYTHING = (SDL_INIT_TIMER | SDL_INIT_AUDIO | SDL_INIT_VIDEO |
                       SDL_INIT_EVENTS | SDL_INIT_JOYSTICK | SDL_INIT_HAPTIC |
                       SDL_INIT_GAMECONTROLLER)

SDL_Init = _bind("SDL_Init", [Uint32], _cint)
SDL_InitSubSystem = _bind("SDL_InitSubSystem", [Uint32], _cint)
SDL_QuitSubSystem = _bind("SDL_QuitSubSystem", [Uint32])
SDL_WasInit = _bind("SDL_WasInit", [Uint32], Uint32)
SDL_Quit = _bind("SDL_Quit")

__version__ = "0.9.5"
version_info = (0, 9, 5, "")
