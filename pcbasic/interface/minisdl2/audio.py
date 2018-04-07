from ctypes import Structure, c_int, c_char_p, c_double, c_void_p, CFUNCTYPE, \
    POINTER
from .dll import _bind, nullfunc
from .minisdl2 import SDL_BYTEORDER, SDL_LIL_ENDIAN
from .minisdl2 import Uint8, Uint16, Uint32


SDL_AudioFormat = Uint16

AUDIO_U16LSB = 0x0010
AUDIO_S16LSB = 0x8010
AUDIO_U16MSB = 0x1010
AUDIO_S16MSB = 0x9010
AUDIO_S32LSB = 0x8020
AUDIO_S32MSB = 0x9020
AUDIO_F32LSB = 0x8120
AUDIO_F32MSB = 0x9120


if SDL_BYTEORDER == SDL_LIL_ENDIAN:
    AUDIO_U16SYS = AUDIO_U16LSB
    AUDIO_S16SYS = AUDIO_S16LSB
    AUDIO_S32SYS = AUDIO_S32LSB
    AUDIO_F32SYS = AUDIO_F32LSB
else:
    AUDIO_U16SYS = AUDIO_U16MSB
    AUDIO_S16SYS = AUDIO_S16MSB
    AUDIO_S32SYS = AUDIO_S32MSB
    AUDIO_F32SYS = AUDIO_F32MSB


SDL_AudioCallback = CFUNCTYPE(None, c_void_p, POINTER(Uint8), c_int)

class SDL_AudioSpec(Structure):
    _fields_ = [("freq", c_int),
                ("format", SDL_AudioFormat),
                ("channels", Uint8),
                ("silence", Uint8),
                ("samples", Uint16),
                ("padding", Uint16),
                ("size", Uint32),
                ("callback", SDL_AudioCallback),
                ("userdata", c_void_p)
                ]
    def __init__(self, freq, aformat, channels, samples,
                 callback=SDL_AudioCallback(), userdata=c_void_p(0)):
        super(SDL_AudioSpec, self).__init__()
        self.freq = freq
        self.format = aformat
        self.channels = channels
        self.samples = samples
        self.callback = callback
        self.userdata = userdata

SDL_AudioInit = _bind("SDL_AudioInit", [c_char_p], c_int)
SDL_AudioQuit = _bind("SDL_AudioQuit")
SDL_OpenAudio = _bind("SDL_OpenAudio", [POINTER(SDL_AudioSpec), POINTER(SDL_AudioSpec)], c_int)
SDL_AudioDeviceID = Uint32
SDL_OpenAudioDevice = _bind("SDL_OpenAudioDevice", [c_char_p, c_int, POINTER(SDL_AudioSpec), POINTER(SDL_AudioSpec), c_int], SDL_AudioDeviceID)
SDL_AudioStatus = c_int
SDL_PauseAudio = _bind("SDL_PauseAudio", [c_int])
SDL_PauseAudioDevice = _bind("SDL_PauseAudioDevice", [SDL_AudioDeviceID, c_int])
SDL_LockAudio = _bind("SDL_LockAudio")
SDL_LockAudioDevice = _bind("SDL_LockAudioDevice", [SDL_AudioDeviceID])
SDL_UnlockAudio = _bind("SDL_UnlockAudio")
SDL_UnlockAudioDevice = _bind("SDL_UnlockAudioDevice", [SDL_AudioDeviceID])
SDL_CloseAudio = _bind("SDL_CloseAudio")
SDL_CloseAudioDevice = _bind("SDL_CloseAudioDevice", [SDL_AudioDeviceID])

