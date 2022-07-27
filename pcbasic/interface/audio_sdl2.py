"""
PC-BASIC - audio_sdl2.py
Sound interface based on SDL2

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# see e.g. http://toomanyideas.net/2014/pysdl2-playing-a-sound-from-a-wav-file.html

import os
import logging
import ctypes
from collections import deque

from ..compat import zip, BASE_DIR
from .audio import AudioPlugin
from .base import audio_plugins, InitFailed
from . import synthesiser


###############################################################################
# locate and load SDL libraries

if False:
    # packagers take note, we need these imports to be bundled
    from . import sdl2loader
    from . import sdl2

# sdl2 module is imported only at plugin initialisation
sdl2 = None

# custom dll location
LIB_DIR = os.path.join(BASE_DIR, 'lib')


def _import_sdl2():
    """Import the sdl2 bindings and define constants."""
    global sdl2

    # look for SDL2.dll / libSDL2.dylib / libSDL2.so:
    # first in LIB_DIR, then in pysdl2dll module, then the standard search path
    # this means that user should not have dll in LIB_DIR if they want to use another one
    from . import sdl2loader
    sdl2loader.load_dlls(LIB_DIR)

    # this raises ImportError if no library has been found
    from . import sdl2

# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
_CHUNK_LENGTH = 1192 * 4
# length of chunks to be consumed by callback
_CALLBACK_CHUNK_LENGTH = 2048
# number of samples below which to replenish the buffer
_MIN_SAMPLES_BUFFER = 2 * _CALLBACK_CHUNK_LENGTH
# pause audio device after given number of ticks without sound
_QUIET_QUIT = 100


@audio_plugins.register('ansi')
@audio_plugins.register('cli')
@audio_plugins.register('sdl2')
class AudioSDL2(AudioPlugin):
    """SDL2-based audio plugin."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        try:
            _import_sdl2()
        except ImportError:
            raise InitFailed('Module `sdl2` not found')
        # synthesisers
        self._signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self._generators = [deque() for _ in synthesiser.VOICES]
        # buffer of samples; drained by callback, replenished by _play_sound
        self._samples = [bytearray() for _ in synthesiser.VOICES]
        self._next_tone = [None for _ in synthesiser.VOICES]
        self._device = None
        self._audiospec = None
        self._quiet_ticks = 0
        AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # init sdl audio in this thread separately
        sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
        # SDL AudioDevice and specifications
        # S8 gives ticks on pausing and unpausing so we use S16
        audiospec = sdl2.SDL_AudioSpec(
            freq=synthesiser.SAMPLE_RATE, aformat=sdl2.AUDIO_S16LSB, channels=1,
            samples=_CALLBACK_CHUNK_LENGTH, callback=sdl2.SDL_AudioCallback(self._get_next_chunk)
        )
        self._device = sdl2.SDL_OpenAudioDevice(None, False, audiospec, None, 0)
        if self._device == 0:
            logging.warning('Could not open audio device: %s', sdl2.SDL_GetError())
        # prevent audiospec from being garbage collected as it goes out of scope
        self._audiospec = audiospec
        return AudioPlugin.__enter__(self)

    def tone(self, voice, frequency, duration, loop, volume):
        """Enqueue a tone."""
        self._generators[voice].append(synthesiser.SoundGenerator(
            self._signal_sources[voice], synthesiser.FEEDBACK_TONE,
            frequency, duration, loop, volume
        ))

    def noise(self, source, frequency, duration, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.FEEDBACK_NOISE if source else synthesiser.FEEDBACK_PERIODIC
        self._generators[synthesiser.NOISE_VOICE].append(synthesiser.SoundGenerator(
            self._signal_sources[synthesiser.NOISE_VOICE], feedback,
            frequency, duration, loop, volume
        ))

    def hush(self):
        """Stop sound."""
        self._next_tone = [None for _ in synthesiser.VOICES]
        for gen in self._generators:
            gen.clear()
        sdl2.SDL_LockAudioDevice(self._device)
        self._samples = [bytearray() for _ in synthesiser.VOICES]
        sdl2.SDL_UnlockAudioDevice(self._device)

    def _work(self):
        """Replenish sample buffer."""
        if not any(self._generators) and not any(self._next_tone):
            if self._quiet_ticks >= _QUIET_QUIT:
                sdl2.SDL_PauseAudioDevice(self._device, 1)
            self._quiet_ticks += 1
            return
        else:
            self._quiet_ticks = 0
            sdl2.SDL_PauseAudioDevice(self._device, 0)
        for voice in synthesiser.VOICES:
            if len(self._samples[voice]) > _MIN_SAMPLES_BUFFER:
                # nothing to do
                continue
            while True:
                if self._next_tone[voice] is None or self._next_tone[voice].loop:
                    try:
                        # looping tone will be interrupted
                        # by any new tone appearing in the generator queue
                        self._next_tone[voice] = self._generators[voice].popleft()
                    except IndexError:
                        if self._next_tone[voice] is None:
                            current_chunk = None
                            break
                current_chunk = self._next_tone[voice].build_chunk(_CHUNK_LENGTH)
                if current_chunk is not None:
                    break
                self._next_tone[voice] = None
            if current_chunk is not None:
                # append chunk to samples list
                # lock to ensure callback doesn't try to access the list too
                sdl2.SDL_LockAudioDevice(self._device)
                self._samples[voice] = bytearray().join((self._samples[voice], current_chunk))
                sdl2.SDL_UnlockAudioDevice(self._device)

    def _get_next_chunk(self, notused, stream, length_bytes):
        """Callback function to generate the next chunk to be played."""
        # this assumes 8-bit samples
        length = length_bytes // 2
        # if samples have run out, add silence
        samples = (
            _samp.ljust(length, b'\0') if len(_samp) < length else _samp[:length]
            for _samp in self._samples
        )
        # mix the samples
        mixed = bytearray(sum(_b) & 0xff for _b in zip(*samples))
        # convert from S8 to S16 (little-endian)
        # interlace with leading zeros to multiply by 256
        mixed_16 = bytearray(length_bytes)
        mixed_16[1::2] = mixed
        self._samples = [_samp[length:] for _samp in self._samples]
        ctypes.memmove(
            stream, (ctypes.c_char * length_bytes).from_buffer(mixed_16), length_bytes
        )
