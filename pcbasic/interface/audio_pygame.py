"""
PC-BASIC - audio_pygame.py
Sound interface based on PyGame

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

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


import logging
import Queue

from ..basic import signals
from . import base
from . import synthesiser

# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000

# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4


##############################################################################
# plugin

class AudioPygame(base.AudioPlugin):
    """Pygame-based audio plugin."""

    def __init__(self, tone_queue, message_queue):
        """Initialise sound system."""
        if not pygame:
            logging.warning('PyGame module not found. Failed to initialise PyGame audio plugin.')
            raise base.InitFailed()
        if not numpy:
            logging.warning('NumPy module not found. Failed to initialise PyGame audio plugin.')
            raise base.InitFailed()
        if not mixer:
            logging.warning('PyGame mixer module not found. Failed to initialise PyGame audio plugin.')
            raise base.InitFailed()
        # this must be called before pygame.init() in the video plugin
        mixer.pre_init(synthesiser.sample_rate, -synthesiser.sample_bits, channels=1, buffer=1024) #4096
        # synthesisers
        self.signal_sources = synthesiser.get_signal_sources()
        # currently looping sound
        self.loop_sound = [ None, None, None, None ]
        # do not quit mixer if true
        self.persist = False
        # keep track of quiet time to shut down mixer after a while
        self.quiet_ticks = 0
        base.AudioPlugin.__init__(self, tone_queue, message_queue)

    def __enter__(self):
        """Perform any necessary initialisations."""
        # initialise mixer as silent
        # this is necessary to be able to set channels to mono
        mixer.quit()
        return base.AudioPlugin.__enter__(self)

    def _drain_message_queue(self):
        """Drain signal queue."""
        alive = True
        while alive:
            try:
                signal = self.message_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == signals.AUDIO_STOP:
                # stop all channels
                for voice in range(4):
                    stop_channel(voice)
                    if self.next_tone[voice] is not None:
                        # ensure sender knows the tone has been dropped
                        self.tone_queue[voice].task_done()
                        self.next_tone[voice] = None
                self.loop_sound = [None, None, None, None]
                self.next_tone = [None, None, None, None]
            elif signal.event_type == signals.AUDIO_QUIT:
                # close thread after task_done
                alive = False
            elif signal.event_type == signals.AUDIO_PERSIST:
                # allow/disallow mixer to quit
                self.persist = signal.params
            self.message_queue.task_done()

    def _drain_tone_queue(self):
        """Drain signal queue."""
        empty = False
        while not empty:
            empty = True
            for voice, q in enumerate(self.tone_queue):
                # don't get the next tone if we're still working on one
                if self.next_tone[voice]:
                    continue
                try:
                    signal = q.get(False)
                    empty = False
                except Queue.Empty:
                    continue
                if signal.event_type == signals.AUDIO_TONE:
                    # enqueue a tone
                    self.next_tone[voice] = synthesiser.SoundGenerator(
                        self.signal_sources[voice], synthesiser.feedback_tone, *signal.params)
                elif signal.event_type == signals.AUDIO_NOISE:
                    # enqueue a noise
                    feedback = synthesiser.feedback_noise if signal.params[0] else synthesiser.feedback_periodic
                    self.next_tone[voice] = synthesiser.SoundGenerator(
                        self.signal_sources[3], feedback, *signal.params[1:])
        return empty

    def _play_sound(self):
        """play sounds."""
        current_chunk = [ None, None, None, None ]
        if (self.next_tone == [ None, None, None, None ]
                and self.loop_sound == [ None, None, None, None ]):
            return
        check_init_mixer()
        for voice in range(4):
            # if there is a sound queue, stop looping sound
            if self.next_tone[voice] and self.loop_sound[voice]:
                stop_channel(voice)
                self.loop_sound[voice] = None
            if mixer.Channel(voice).get_queue() is None:
                if self.next_tone[voice]:
                    if self.next_tone[voice].loop:
                        # it's a looping tone, handle there
                        self.loop_sound[voice] = self.next_tone[voice]
                        self.next_tone[voice] = None
                        self.tone_queue[voice].task_done()
                    else:
                        current_chunk[voice] = numpy.array([], dtype=numpy.int16)
                        while (self.next_tone[voice] and
                                        len(current_chunk[voice]) < chunk_length):
                            chunk = self.next_tone[voice].build_chunk(chunk_length)
                            if chunk is None:
                                # tone has finished
                                self.next_tone[voice] = None
                                self.tone_queue[voice].task_done()
                            else:
                                current_chunk[voice] = numpy.concatenate(
                                                    (current_chunk[voice], chunk))
                if self.loop_sound[voice]:
                    # currently looping sound
                    current_chunk[voice] = self.loop_sound[voice].build_chunk(chunk_length)
        for voice in range(4):
            if current_chunk[voice] is not None and len(current_chunk[voice]) != 0:
                snd = pygame.sndarray.make_sound(current_chunk[voice])
                mixer.Channel(voice).queue(snd)
        # check if mixer can be quit
        self._check_quit()

    def _check_quit(self):
        """Quit the mixer if not running a program and sound quiet for a while."""
        if self.next_tone != [None, None, None, None]:
            self.quiet_ticks = 0
        else:
            self.quiet_ticks += 1
            if not self.persist and self.quiet_ticks > quiet_quit:
                # mixer is quiet and we're not running a program.
                # quit to reduce pulseaudio cpu load
                # this takes quite a while and leads to missed frames...
                if mixer.get_init() is not None:
                    mixer.quit()
                self.quiet_ticks = 0


def stop_channel(channel):
    """Stop sound on a channel."""
    if mixer.get_init():
        mixer.Channel(channel).stop()
        # play short silence to avoid blocking the channel
        # otherwise it won't play on queue()
        silence = pygame.sndarray.make_sound(numpy.zeros(1, numpy.int16))
        mixer.Channel(channel).play(silence)

def check_init_mixer():
    """Initialise the mixer if necessary."""
    if mixer.get_init() is None:
        mixer.init()
