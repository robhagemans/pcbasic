"""
PC-BASIC - interface.audio_portaudio
Sound interface based on PortAudio

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import logging
from collections import deque
from contextlib import contextmanager

if False:
    # for detection by packagers
    import pyaudio

from ..compat import zip, WIN32
from .audio import AudioPlugin
from .base import audio_plugins, InitFailed
from . import synthesiser


# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
_CHUNK_LENGTH = 1192 * 4
# buffer size in sample frames
_BUFSIZE = 1024


# suppress ALSA debug messages
# https://stackoverflow.com/questions/7088672/pyaudio-working-but-spits-out-error-messages-each-time
if WIN32:
    @contextmanager
    def _quiet_alsa(): yield
else:
    @contextmanager
    def _quiet_alsa():
        """Set the error handler in alsa to avoid debug messages on the screen."""
        from ctypes import CFUNCTYPE, c_char_p, c_int, cdll
        # From alsa-lib Git 3fd4ab9be0db7c7430ebd258f2717a976381715d
        # $ grep -rn snd_lib_error_handler_t
        # include/error.h:59:typedef void (*snd_lib_error_handler_t)(const char *file, int line, const char *function, int err, const char *fmt, ...) /* __attribute__ ((format (printf, 5, 6))) */;
        ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
        def py_error_handler(filename, line, function, err, fmt):
            logging.debug('ALSA: %s:%s: %s', filename, line, fmt)
        c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
        asound = cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        try:
            yield
        finally:
            asound.snd_lib_error_set_handler(None)



@audio_plugins.register('ansi')
@audio_plugins.register('cli')
@audio_plugins.register('portaudio')
class AudioPortAudio(AudioPlugin):
    """SDL2-based audio plugin."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        global pyaudio
        try:
            import pyaudio
        except ImportError:
            raise InitFailed('Module `pyaudio` not found')
        # synthesisers
        self._signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self._generators = [deque() for _ in synthesiser.VOICES]
        # buffer of samples; drained by callback, replenished by _play_sound
        self._samples = [bytearray() for _ in synthesiser.VOICES]
        self._device = None
        self._stream = None
        self._alsa_muffle = None
        self._min_samples_buffer = 2 * _BUFSIZE
        AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        self._alsa_muffle = _quiet_alsa()
        self._alsa_muffle.__enter__()
        self._device = pyaudio.PyAudio()
        self._stream = self._device.open(
            format=pyaudio.paInt8, channels=1, rate=synthesiser.SAMPLE_RATE, output=True,
            frames_per_buffer=_BUFSIZE, stream_callback=self._get_next_chunk
        )
        self._stream.start_stream()
        AudioPlugin.__enter__(self)

    def __exit__(self, type, value, traceback):
        """Close down PortAudio."""
        self._alsa_muffle.__exit__(type, value, traceback)
        self._stream.stop_stream()
        self._stream.close()
        self._device.terminate()
        return AudioPlugin.__exit__(self, type, value, traceback)

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
        self._samples = [bytearray() for _ in synthesiser.VOICES]

    def _work(self):
        """Replenish sample buffer."""
        for voice in synthesiser.VOICES:
            if len(self._samples[voice]) > self._min_samples_buffer:
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
                # should lock to ensure callback doesn't try to access the list too?
                self._samples[voice] = bytearray().join((self._samples[voice], current_chunk))

    def _get_next_chunk(self, in_data, length, time_info, status):
        """Callback function to generate the next chunk to be played."""
        # this assumes 8-bit samples
        # if samples have run out, add silence
        samples = (
            _samp.ljust(length, b'\0') if len(_samp) < length else _samp[:length]
            for _samp in self._samples
        )
        # mix the samples
        mixed = bytearray(sum(_b) & 0xff for _b in zip(*samples))
        self._samples = [_samp[length:] for _samp in self._samples]
        return bytes(mixed), pyaudio.paContinue
