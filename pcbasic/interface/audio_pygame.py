"""
PC-BASIC - audio_pygame.py
Sound interface based on PyGame

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""


import Queue
from collections import deque

try:
    import pygame
except ImportError:
    pygame = None

try:
    import numpy
except ImportError:
    numpy = None

if pygame:
    import pygame.mixer as mixer
else:
    mixer = None

from ..basic.base import signals
from . import base
from . import synthesiser

# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4


##############################################################################
# plugin

@base.audio_plugins.register('pygame')
class AudioPygame(base.AudioPlugin):
    """Pygame-based audio plugin."""

    # quit sound server after quiet period of quiet_quit ticks
    # to avoid high-ish cpu load from the sound server.
    quiet_quit = 10000

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        if not pygame:
            raise base.InitFailed('Module `pygame` not found')
        if not numpy:
            raise base.InitFailed('Mdoule `numpy` not found')
        if not mixer:
            raise base.InitFailed('Module `mixer` not found')
        # this must be called before pygame.init() in the video plugin
        mixer.pre_init(synthesiser.sample_rate, -synthesiser.sample_bits, channels=1, buffer=1024) #4096
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        # do not quit mixer if true
        self._persist = False
        # keep track of quiet time to shut down mixer after a while
        self.quiet_ticks = 0
        base.AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # initialise mixer as silent
        # this is necessary to be able to set channels to mono
        mixer.quit()
        return base.AudioPlugin.__enter__(self)

    def persist(self, do_persist):
        """Allow or disallow mixer to quit."""
        self._persist = do_persist

    def tone(self, voice, frequency, duration, fill, loop, volume):
        """Enqueue a tone."""
        self.generators[voice].append(synthesiser.SoundGenerator(
                    self.signal_sources[voice], synthesiser.feedback_tone,
                    frequency, duration, fill, loop, volume))

    def noise(self, source, frequency, duration, fill, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.feedback_noise if source else synthesiser.feedback_periodic
        self.generators[3].append(synthesiser.SoundGenerator(
                    self.signal_sources[3], feedback,
                    frequency, duration, fill, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self._stop_channel(voice)
            self._next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()

    def _work(self):
        """Replenish sample buffer."""
        if (sum(len(q) for q in self.generators) == 0 and self._next_tone == [None, None, None, None]):
            # check if mixer can be quit
            self._check_quit()
            return
        self._check_init_mixer()
        for voice in range(4):
            if mixer.Channel(voice).get_queue() is not None:
                # nothing to do
                continue
            while True:
                if self._next_tone[voice] is None or self._next_tone[voice].loop:
                    try:
                        self._next_tone[voice] = self.generators[voice].popleft()
                    except IndexError:
                        if self._next_tone[voice] is None:
                            current_chunk = None
                            break
                current_chunk = self._next_tone[voice].build_chunk(chunk_length)
                if current_chunk is not None:
                    break
                self._next_tone[voice] = None
            if current_chunk is not None:
                # enqueue chunk in mixer
                snd = pygame.sndarray.make_sound(current_chunk)
                mixer.Channel(voice).queue(snd)

    def _check_quit(self):
        """Quit the mixer if not running a program and sound quiet for a while."""
        if self._next_tone != [None, None, None, None]:
            self.quiet_ticks = 0
        else:
            self.quiet_ticks += 1
            if not self._persist and self.quiet_ticks > self.quiet_quit:
                # mixer is quiet and we're not running a program.
                # quit to reduce pulseaudio cpu load
                # this takes quite a while and leads to missed frames...
                if mixer.get_init() is not None:
                    mixer.quit()
                self.quiet_ticks = 0

    def _stop_channel(self, channel):
        """Stop sound on a channel."""
        if mixer.get_init():
            mixer.Channel(channel).stop()
            # play short silence to avoid blocking the channel
            # otherwise it won't play on queue()
            silence = pygame.sndarray.make_sound(numpy.zeros(1, numpy.int16))
            mixer.Channel(channel).play(silence)

    def _check_init_mixer(self):
        """Initialise the mixer if necessary."""
        if mixer.get_init() is None:
            mixer.init()
