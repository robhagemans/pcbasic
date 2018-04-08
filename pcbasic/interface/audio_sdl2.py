"""
PC-BASIC - audio_sdl2.py
Sound interface based on SDL2

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# see e.g. http://toomanyideas.net/2014/pysdl2-playing-a-sound-from-a-wav-file.html

import logging
from collections import deque

try:
    from . import sdl2
except ImportError:
    sdl2 = None

try:
    import numpy
except ImportError:
    numpy = None

from .audio import AudioPlugin
from .base import audio_plugins, InitFailed
from . import synthesiser


# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
CHUNK_LENGTH = 1192 * 4
# length of chunks to be consumed by callback
CALLBACK_CHUNK_LENGTH = 2048
# number of samples below which to replenish the buffer
MIN_SAMPLES_BUFFER = 2*CALLBACK_CHUNK_LENGTH


##############################################################################
# plugin

@audio_plugins.register('sdl2')
class AudioSDL2(AudioPlugin):
    """SDL2-based audio plugin."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        if not sdl2:
            raise InitFailed('Module `sdl2` not found')
        if not numpy:
            raise InitFailed('Module `numpy` module not found')
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        # buffer of samples; drained by callback, replenished by _play_sound
        self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
        # SDL AudioDevice and specifications
        self.audiospec = sdl2.SDL_AudioSpec(0, 0, 0, 0)
        self.audiospec.freq = synthesiser.SAMPLE_RATE
        # samples are 16-bit signed ints
        self.audiospec.format = sdl2.AUDIO_S16SYS
        self.audiospec.channels = 1
        self.audiospec.samples = CALLBACK_CHUNK_LENGTH
        self.audiospec.callback = sdl2.SDL_AudioCallback(self._get_next_chunk)
        self.dev = None
        AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # init sdl audio in this thread separately
        sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
        self.dev = sdl2.SDL_OpenAudioDevice(None, 0, self.audiospec, None, 0)
        if self.dev == 0:
            logging.warning('Could not open audio device: %s', sdl2.SDL_GetError())
        # unpause the audio device
        sdl2.SDL_PauseAudioDevice(self.dev, 0)
        return AudioPlugin.__enter__(self)

    def tone(self, voice, frequency, duration, fill, loop, volume):
        """Enqueue a tone."""
        self.generators[voice].append(synthesiser.SoundGenerator(
                    self.signal_sources[voice], synthesiser.FEEDBACK_TONE,
                    frequency, duration, fill, loop, volume))

    def noise(self, source, frequency, duration, fill, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.FEEDBACK_NOISE if source else synthesiser.FEEDBACK_PERIODIC
        self.generators[3].append(synthesiser.SoundGenerator(
                    self.signal_sources[3], feedback,
                    frequency, duration, fill, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self._next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()
        sdl2.SDL_LockAudioDevice(self.dev)
        self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
        sdl2.SDL_UnlockAudioDevice(self.dev)

    def _work(self):
        """Replenish sample buffer."""
        for voice in range(4):
            if len(self.samples[voice]) > MIN_SAMPLES_BUFFER:
                # nothing to do
                continue
            while True:
                if self._next_tone[voice] is None or self._next_tone[voice].loop:
                    try:
                        # looping tone will be interrupted
                        # by any new tone appearing in the generator queue
                        self._next_tone[voice] = self.generators[voice].popleft()
                    except IndexError:
                        if self._next_tone[voice] is None:
                            current_chunk = None
                            break
                current_chunk = self._next_tone[voice].build_chunk(CHUNK_LENGTH)
                if current_chunk is not None:
                    break
                self._next_tone[voice] = None
            if current_chunk is not None:
                # append chunk to samples list
                # lock to ensure callback doesn't try to access the list too
                sdl2.SDL_LockAudioDevice(self.dev)
                self.samples[voice] = numpy.concatenate(
                        (self.samples[voice], current_chunk))
                sdl2.SDL_UnlockAudioDevice(self.dev)

    def _get_next_chunk(self, notused, stream, length_bytes):
        """Callback function to generate the next chunk to be played."""
        # this is for 16-bit samples
        length = length_bytes/2
        samples = [self.samples[voice][:length] for voice in range(4)]
        self.samples = [self.samples[voice][length:] for voice in range(4)]
        # if samples have run out, add silence
        for voice in range(4):
            if len(samples[voice]) < length:
                silence = numpy.zeros(length-len(samples[voice]), numpy.int16)
                samples[voice] = numpy.concatenate((samples[voice], silence))
        # mix the samples by averaging
        # we need the int32 intermediate step, for int16 numpy will average [32767, 32767] to -1
        mixed = numpy.array(numpy.mean(samples, axis=0, dtype=numpy.int32), dtype=numpy.int16)
        # copy into byte array (is there a better way?)
        for i in xrange(length_bytes):
            stream[i] = ord(mixed.data[i])
