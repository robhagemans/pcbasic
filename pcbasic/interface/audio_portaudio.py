"""
PC-BASIC - interface.audio_portaudio
Sound interface based on PortAudio

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
from collections import deque
from contextlib import contextmanager

try:
    import pyaudio
except ImportError:
    pyaudio = None

from ..compat import muffle, zip
from .audio import AudioPlugin
from .base import audio_plugins, InitFailed
from . import synthesiser


# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
CHUNK_LENGTH = 1192 * 4
# buffer size in sample frames
BUFSIZE = 1024


@audio_plugins.register('portaudio')
class AudioPortAudio(AudioPlugin):
    """SDL2-based audio plugin."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        if not pyaudio:
            raise InitFailed('Module `pyaudio` not found')
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        # buffer of samples; drained by callback, replenished by _play_sound
        self._samples = [bytearray() for _ in range(4)]
        self._dev = None
        AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        with muffle(sys.stderr):
            self._dev = pyaudio.PyAudio()
            sample_format = self._dev.get_format_from_width(1)
            self._min_samples_buffer = 2 * BUFSIZE
            self._stream = self._dev.open(
                format=sample_format, channels=1, rate=synthesiser.SAMPLE_RATE, output=True,
                frames_per_buffer=BUFSIZE, stream_callback=self._get_next_chunk
            )
            self._stream.start_stream()
            AudioPlugin.__enter__(self)

    def __exit__(self, type, value, traceback):
        """Close down PortAudio."""
        self._stream.stop_stream()
        self._stream.close()
        self._dev.terminate()
        return AudioPlugin.__exit__(self, type, value, traceback)

    def tone(self, voice, frequency, duration, loop, volume):
        """Enqueue a tone."""
        self.generators[voice].append(synthesiser.SoundGenerator(
                    self.signal_sources[voice], synthesiser.FEEDBACK_TONE,
                    frequency, duration, loop, volume))

    def noise(self, source, frequency, duration, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.FEEDBACK_NOISE if source else synthesiser.FEEDBACK_PERIODIC
        self.generators[3].append(synthesiser.SoundGenerator(
                    self.signal_sources[3], feedback,
                    frequency, duration, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self._next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()
        self._samples = [bytearray() for _ in range(4)]

    def _work(self):
        """Replenish sample buffer."""
        for voice in range(4):
            if len(self._samples[voice]) > self._min_samples_buffer:
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
                # should lock to ensure callback doesn't try to access the list too?
                self._samples[voice] = bytearray().join((self._samples[voice], current_chunk))

    def _get_next_chunk(self, in_data, length, time_info, status):
        """Callback function to generate the next chunk to be played."""
        # this assumes 8-bit samples
        # if samples have run out, add silence
        samples = (
            _samp.rjust(length, b'\0') if len(_samp) < length else _samp[:length]
            for _samp in self._samples
        )
        # mix the samples
        mixed = bytearray(sum(_b) for _b in zip(*samples))
        self._samples = [_samp[length:] for _samp in self._samples]
        return bytes(mixed), pyaudio.paContinue
