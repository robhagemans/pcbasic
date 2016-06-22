"""
PC-BASIC - audio_sdl2.py
Sound interface based on SDL2

(c) 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# see e.g. http://toomanyideas.net/2014/pysdl2-playing-a-sound-from-a-wav-file.html

import logging
import Queue
from collections import deque

try:
    import sdl2
except ImportError:
    sdl2 = None

try:
    import numpy
except ImportError:
    numpy = None

from ..basic import signals
from . import base
from . import synthesiser


# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4

callback_chunk_length = 2048
min_samples_buffer = 2*callback_chunk_length


##############################################################################
# plugin

class AudioSDL2(base.AudioPlugin):
    """SDL2-based audio plugin."""

    def __init__(self, tone_queue, message_queue):
        """Initialise sound system."""
        if not sdl2:
            logging.warning('SDL2 module not found. Failed to initialise SDL2 audio plugin.')
            raise base.InitFailed()
        if not numpy:
            logging.warning('NumPy module not found. Failed to initialise SDL2 audio plugin.')
            raise base.InitFailed()
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # sound generators for each tone
        self.generators = [deque(), deque(), deque(), deque()]
        # buffer of samples; drained by callback, replenished by _play_sound
        self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
        # SDL AudioDevice and specifications
        self.audiospec = sdl2.SDL_AudioSpec(0, 0, 0, 0)
        self.audiospec.freq = synthesiser.sample_rate
        # samples are 16-bit signed ints
        self.audiospec.format = sdl2.AUDIO_S16SYS
        self.audiospec.channels = 1
        self.audiospec.samples = callback_chunk_length
        self.audiospec.callback = sdl2.SDL_AudioCallback(self._get_next_chunk)
        self.dev = None
        # start audio thread
        base.AudioPlugin.__init__(self, tone_queue, message_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # init sdl audio in this thread separately
        sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
        self.dev = sdl2.SDL_OpenAudioDevice(None, 0, self.audiospec, None, 0)
        if self.dev == 0:
            logging.warning('Could not open audio device: %s', sdl2.SDL_GetError())
        # unpause the audio device
        sdl2.SDL_PauseAudioDevice(self.dev, 0)
        return base.AudioPlugin.__enter__(self)

    def tone(self, voice, frequency, duration, fill, loop, volume):
        """Enqueue a tone."""
        self.generators[voice].append(synthesiser.SoundGenerator(
                    self.signal_sources[voice], synthesiser.feedback_tone,
                    frequency, duration, fill, loop, volume))

    def noise(self, source, frequency, duration, fill, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.feedback_noise if source else synthesiser.feedback_periodic
        self.generators[voice].append(synthesiser.SoundGenerator(
                    self.signal_sources[3], feedback,
                    frequency, duration, fill, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self.next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()
        sdl2.SDL_LockAudioDevice(self.dev)
        self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
        sdl2.SDL_UnlockAudioDevice(self.dev)

    def work(self):
        """Replenish sample buffer."""
        for voice in range(4):
            if len(self.samples[voice]) > min_samples_buffer:
                # nothing to do
                continue
            while True:
                if self.next_tone[voice] is None or self.next_tone[voice].loop:
                    try:
                        self.next_tone[voice] = self.generators[voice].popleft()
                    except IndexError:
                        if self.next_tone[voice] is None:
                            current_chunk = None
                            break
                current_chunk = self.next_tone[voice].build_chunk(chunk_length)
                if current_chunk is not None:
                    break
                self.next_tone[voice] = None
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
