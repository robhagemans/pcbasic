from ctypes import c_char, c_char_p, c_float, c_void_p, c_int, Structure, \
    Union, CFUNCTYPE, POINTER
from .minisdl2 import _bind
from .minisdl2 import Sint16, Sint32, Uint8, Uint16, Uint32, SDL_bool
from .minisdl2 import SDL_JoystickID
from .minisdl2 import SDL_Keysym


SDL_QUIT = 0x100
SDL_WINDOWEVENT = 0x200
SDL_SYSWMEVENT = 0x201
SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301
SDL_TEXTEDITING = 0x302
SDL_TEXTINPUT = 0x303
SDL_MOUSEMOTION = 0x400
SDL_MOUSEBUTTONDOWN = 0x401
SDL_MOUSEBUTTONUP = 0x402
SDL_JOYAXISMOTION = 0x600
SDL_JOYBUTTONDOWN = 0x603
SDL_JOYBUTTONUP = 0x604

class SDL_WindowEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("event", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("data1", Sint32),
                ("data2", Sint32)
                ]

class SDL_KeyboardEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("state", Uint8),
                ("repeat", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("keysym", SDL_Keysym)
                ]

SDL_TEXTEDITINGEVENT_TEXT_SIZE = 32

class SDL_TextEditingEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("text", (c_char * SDL_TEXTEDITINGEVENT_TEXT_SIZE)),
                ("start", Sint32),
                ("length", Sint32)
                ]

SDL_TEXTINPUTEVENT_TEXT_SIZE = 32
class SDL_TextInputEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("text", (c_char * SDL_TEXTINPUTEVENT_TEXT_SIZE))
                ]

class SDL_MouseMotionEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("which", Uint32),
                ("state", Uint32),
                ("x", Sint32),
                ("y", Sint32),
                ("xrel", Sint32),
                ("yrel", Sint32)
                ]

class SDL_MouseButtonEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("which", Uint32),
                ("button", Uint8),
                ("state", Uint8),
                ("clicks", Uint8),
                ("padding1", Uint8),
                ("x", Sint32),
                ("y", Sint32)
                ]

class SDL_JoyAxisEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("axis", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("value", Sint16),
                ("padding4", Uint16)
                ]

class SDL_JoyButtonEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("button", Uint8),
                ("state", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8)
                ]

class SDL_QuitEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32)
                ]

class SDL_Event(Union):
    _fields_ = [("type", Uint32),
                ("window", SDL_WindowEvent),
                ("key", SDL_KeyboardEvent),
                ("edit", SDL_TextEditingEvent),
                ("text", SDL_TextInputEvent),
                ("motion", SDL_MouseMotionEvent),
                ("button", SDL_MouseButtonEvent),
                ("jaxis", SDL_JoyAxisEvent),
                ("jbutton", SDL_JoyButtonEvent),
                ("quit", SDL_QuitEvent),
                ("padding", (Uint8 * 56)),
                ]

SDL_PollEvent = _bind("SDL_PollEvent", [POINTER(SDL_Event)], c_int)
