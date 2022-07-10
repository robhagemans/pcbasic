"""
PC-BASIC - audio_pygame.py
Sound interface based on PyGame

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
from collections import deque


if False:
    # keep the import for detection by packagers
    import pygame
    import pygame.mixer as mixer

from ..basic.base import signals
from .audio import AudioPlugin
from .base import audio_plugins, InitFailed
from . import synthesiser


# one wavelength at 37 Hz is 1192 samples at 44100 Hz
CHUNK_LENGTH = 1192 * 4
# quit sound server after quiet period of QUIET_QUIT ticks
# to avoid high-ish cpu load from the sound server.
QUIET_QUIT = 10000
# buffer size in sample frames
BUFSIZE = 1024 #4096


##############################################################################
# plugin

@audio_plugins.register('pygame')
class AudioPygame(AudioPlugin):
    """Pygame-based audio plugin."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        global pygame, mixer
        try:
            import pygame
        except ImportError:
            raise InitFailed('Module `pygame` not found')
        try:
            from pygame import mixer
        except ImportError:
            raise InitFailed('Module `mixer` not found')
        # this must be called before pygame.init() in the video plugin
        # if sample_bits != 16 or -16 I get no sound. seems to ave no effect though
        mixer.pre_init(
            synthesiser.SAMPLE_RATE, -16, channels=1, buffer=BUFSIZE
        )
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        # do not quit mixer if true
        self._persist = False
        # keep track of quiet time to shut down mixer after a while
        self.quiet_ticks = 0
        AudioPlugin.__init__(self, audio_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # initialise mixer as silent
        # this is necessary to be able to set channels to mono
        mixer.quit()
        return AudioPlugin.__enter__(self)

    def persist(self, do_persist):
        """Allow or disallow mixer to quit."""
        self._persist = do_persist

    def tone(self, voice, frequency, duration, loop, volume):
        """Enqueue a tone."""
        self.generators[voice].append(synthesiser.SoundGenerator(
            self.signal_sources[voice], synthesiser.FEEDBACK_TONE,
            frequency, duration, loop, volume
        ))

    def noise(self, source, frequency, duration, loop, volume):
        """Enqueue a noise."""
        feedback = synthesiser.FEEDBACK_NOISE if source else synthesiser.FEEDBACK_PERIODIC
        self.generators[3].append(synthesiser.SoundGenerator(
            self.signal_sources[3], feedback,
            frequency, duration, loop, volume
        ))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self._stop_channel(voice)
            self._next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()

    def _work(self):
        """Replenish sample buffer."""
        if (
                sum(len(q) for q in self.generators) == 0 and
                self._next_tone == [None, None, None, None]
            ):
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
                current_chunk = self._next_tone[voice].build_chunk(CHUNK_LENGTH)
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
            if not self._persist and self.quiet_ticks > QUIET_QUIT:
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
            silence = pygame.sndarray.make_sound(bytearray(1))
            mixer.Channel(channel).play(silence)

    def _check_init_mixer(self):
        """Initialise the mixer if necessary."""
        if mixer.get_init() is None:
            mixer.init()
