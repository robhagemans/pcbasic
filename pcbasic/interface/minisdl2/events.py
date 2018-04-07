from ctypes import c_char, c_char_p, c_float, c_void_p, c_int, Structure, \
    Union, CFUNCTYPE, POINTER
from .dll import _bind
from .minisdl2 import Sint16, Sint32, Uint8, Uint16, Uint32, SDL_bool
from .minisdl2 import SDL_JoystickID
from .keyboard import SDL_Keysym


SDL_FIRSTEVENT = 0
SDL_QUIT = 0x100
SDL_APP_TERMINATING = 0x101
SDL_APP_LOWMEMORY = 0x102
SDL_APP_WILLENTERBACKGROUND = 0x103
SDL_APP_DIDENTERBACKGROUND = 0x104
SDL_APP_WILLENTERFOREGROUND = 0x105
SDL_APP_DIDENTERFOREGROUND = 0x106
SDL_WINDOWEVENT = 0x200
SDL_SYSWMEVENT = 0x201
SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301
SDL_TEXTEDITING = 0x302
SDL_TEXTINPUT = 0x303
SDL_KEYMAPCHANGED = 0x304
SDL_MOUSEMOTION = 0x400
SDL_MOUSEBUTTONDOWN = 0x401
SDL_MOUSEBUTTONUP = 0x402
SDL_MOUSEWHEEL = 0x403
SDL_JOYAXISMOTION = 0x600
SDL_JOYBALLMOTION = 0x601
SDL_JOYHATMOTION = 0x602
SDL_JOYBUTTONDOWN = 0x603
SDL_JOYBUTTONUP = 0x604
SDL_JOYDEVICEADDED = 0x605
SDL_JOYDEVICEREMOVED = 0x606
SDL_CONTROLLERAXISMOTION = 0x650
SDL_CONTROLLERBUTTONDOWN = 0x651
SDL_CONTROLLERBUTTONUP = 0x652
SDL_CONTROLLERDEVICEADDED = 0x653
SDL_CONTROLLERDEVICEREMOVED = 0x654
SDL_CONTROLLERDEVICEREMAPPED = 0x655
SDL_FINGERDOWN = 0x700
SDL_FINGERUP = 0x701
SDL_FINGERMOTION = 0x702
SDL_DOLLARGESTURE = 0x800
SDL_DOLLARRECORD = 0x801
SDL_MULTIGESTURE = 0x802
SDL_CLIPBOARDUPDATE = 0x900
SDL_DROPFILE = 0x1000
SDL_DROPTEXT = 0x1001
SDL_DROPBEGIN = 0x1002
SDL_DROPCOMPLETE = 0x1003
SDL_AUDIODEVICEADDED = 0x1100
SDL_AUDIODEVICEREMOVED = 0x1101
SDL_RENDER_TARGETS_RESET = 0x2000
SDL_RENDER_DEVICE_RESET = 0x2001
SDL_USEREVENT = 0x8000
SDL_LASTEVENT = 0xFFFF
SDL_EventType = c_int

SDL_RELEASED = 0
SDL_PRESSED = 1


class SDL_CommonEvent(Structure):
    _fields_ = [("type", Uint32), ("timestamp", Uint32)]

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

class SDL_MouseWheelEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("which", Uint32),
                ("x", Sint32),
                ("y", Sint32),
                ("direction", Uint32)
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

class SDL_JoyBallEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("ball", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8),
                ("xrel", Sint16),
                ("yrel", Sint16)
                ]

class SDL_JoyHatEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", SDL_JoystickID),
                ("hat", Uint8),
                ("value", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8)
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

class SDL_JoyDeviceEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", Sint32)
                ]

class SDL_AudioDeviceEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("which", Uint32),
                ("iscapture", Uint8),
                ("padding1", Uint8),
                ("padding2", Uint8),
                ("padding3", Uint8)
            ]

class SDL_DropEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("file", c_char_p),
                ("windowID", Uint32)
                ]

class SDL_QuitEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32)
                ]

class SDL_OSEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32)
                ]

class SDL_UserEvent(Structure):
    _fields_ = [("type", Uint32),
                ("timestamp", Uint32),
                ("windowID", Uint32),
                ("code", Sint32),
                ("data1", c_void_p),
                ("data2", c_void_p)
                ]


class SDL_Event(Union):
    _fields_ = [("type", Uint32),
                ("common", SDL_CommonEvent),
                ("window", SDL_WindowEvent),
                ("key", SDL_KeyboardEvent),
                ("edit", SDL_TextEditingEvent),
                ("text", SDL_TextInputEvent),
                ("motion", SDL_MouseMotionEvent),
                ("button", SDL_MouseButtonEvent),
                ("wheel", SDL_MouseWheelEvent),
                ("jaxis", SDL_JoyAxisEvent),
                ("jball", SDL_JoyBallEvent),
                ("jhat", SDL_JoyHatEvent),
                ("jbutton", SDL_JoyButtonEvent),
                ("jdevice", SDL_JoyDeviceEvent),
                #("caxis", SDL_ControllerAxisEvent),
                #("cbutton", SDL_ControllerButtonEvent),
                #("cdevice", SDL_ControllerDeviceEvent),
                ("adevice", SDL_AudioDeviceEvent),
                ("quit", SDL_QuitEvent),
                ("user", SDL_UserEvent),
                #("syswm", SDL_SysWMEvent),
                #("tfinger", SDL_TouchFingerEvent),
                #("mgesture", SDL_MultiGestureEvent),
                #("dgesture", SDL_DollarGestureEvent),
                ("drop", SDL_DropEvent),
                ("padding", (Uint8 * 56)),
                ]

SDL_PumpEvents = _bind("SDL_PumpEvents")
SDL_ADDEVENT = 0
SDL_PEEKEVENT = 1
SDL_GETEVENT = 2
SDL_eventaction = c_int
SDL_PeepEvents = _bind("SDL_PeepEvents", [POINTER(SDL_Event), c_int, SDL_eventaction, Uint32, Uint32], c_int)
SDL_HasEvent = _bind("SDL_HasEvent", [Uint32], SDL_bool)
SDL_HasEvents = _bind("SDL_HasEvents", [Uint32, Uint32], SDL_bool)
SDL_FlushEvent = _bind("SDL_FlushEvent", [Uint32])
SDL_FlushEvents = _bind("SDL_FlushEvents", [Uint32, Uint32])
SDL_PollEvent = _bind("SDL_PollEvent", [POINTER(SDL_Event)], c_int)
SDL_WaitEvent = _bind("SDL_WaitEvent", [POINTER(SDL_Event)], c_int)
SDL_WaitEventTimeout = _bind("SDL_WaitEventTimeout", [POINTER(SDL_Event), c_int], c_int)
SDL_PushEvent = _bind("SDL_PushEvent", [POINTER(SDL_Event)], c_int)
SDL_EventFilter = CFUNCTYPE(c_int, c_void_p, POINTER(SDL_Event))
SDL_SetEventFilter = _bind("SDL_SetEventFilter", [SDL_EventFilter, c_void_p])
SDL_GetEventFilter = _bind("SDL_GetEventFilter", [POINTER(SDL_EventFilter), POINTER(c_void_p)], SDL_bool)
SDL_AddEventWatch = _bind("SDL_AddEventWatch", [SDL_EventFilter, c_void_p])
SDL_DelEventWatch = _bind("SDL_DelEventWatch", [SDL_EventFilter, c_void_p])
SDL_FilterEvents = _bind("SDL_FilterEvents", [SDL_EventFilter, c_void_p])
SDL_QUERY = -1
SDL_IGNORE = 0
SDL_DISABLE = 0
SDL_ENABLE = 1
SDL_EventState = _bind("SDL_EventState", [Uint32, c_int], Uint8)
SDL_GetEventState = lambda t: SDL_EventState(t, SDL_QUERY)
SDL_RegisterEvents = _bind("SDL_RegisterEvents", [c_int], Uint32)


# SDL_quit.h
def SDL_QuitRequested():
    SDL_PumpEvents()
    return SDL_PeepEvents(None, 0, SDL_PEEKEVENT, SDL_QUIT, SDL_QUIT) > 0
