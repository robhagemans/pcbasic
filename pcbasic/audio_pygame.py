"""
PC-BASIC - audio_pygame.py
Sound interface based on PyGame

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

try:
    import pygame
except ImportError:
    pygame = None

try:
    import numpy
except ImportError:
    numpy = None

import plat
if plat.system == 'Android':
    android = True
    # don't do sound for now on Android
    mixer = None
else:
    android = False
    if pygame:
        import pygame.mixer as mixer
    else:
        mixer = None

from math import ceil
import logging
import Queue

import backend
import audio

tick_ms = 24
# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000

# mixer settings
mixer_bits = 16
sample_rate = 44100


def prepare():
    """ Initialise sound module. """
    audio.plugin_dict['pygame'] = AudioPygame
    if pygame:
        # must be called before pygame.init()
        if mixer:
            mixer.pre_init(sample_rate, -mixer_bits, channels=1, buffer=1024) #4096


##############################################################################
# plugin

class AudioPygame(audio.AudioPlugin):
    """ Pygame-based audio plugin. """

    def __init__(self):
        """ Initialise sound system. """
        if not numpy:
            logging.warning('NumPy module not found. Failed to initialise audio.')
            raise audio.InitFailed()
        if not mixer:
            raise audio.InitFailed()
        # currently looping sound
        self.loop_sound = [ None, None, None, None ]
        # do not quit mixer if true
        self.persist = False
        # keep track of quiet time to shut down mixer after a while
        self.quiet_ticks = 0
        audio.AudioPlugin.__init__(self)

    def _init_sound(self):
        """ Perform any necessary initialisations. """
        # initialise mixer as silent
        # this is necessary to be able to set channels to mono
        mixer.quit()

    def _sleep(self):
        """ Sleep a tick to avoid hogging the cpu. """
        pygame.time.wait(tick_ms)

    def _drain_message_queue(self):
        """ Drain signal queue. """
        alive = True
        while alive:
            try:
                signal = backend.message_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == backend.AUDIO_STOP:
                # stop all channels
                for voice in range(4):
                    stop_channel(voice)
                self.loop_sound = [None, None, None, None]
                self.next_tone = [None, None, None, None]
            elif signal.event_type == backend.AUDIO_QUIT:
                # close thread after task_done
                alive = False
            elif signal.event_type == backend.AUDIO_PERSIST:
                # allow/disallow mixer to quit
                self.persist = signal.params
            backend.message_queue.task_done()

    def _drain_tone_queue(self):
        """ Drain signal queue. """
        empty = False
        while not empty:
            empty = True
            for voice, q in enumerate(backend.tone_queue):
                # don't get the next tone if we're still working on one
                if self.next_tone[voice]:
                    continue
                try:
                    signal = q.get(False)
                    empty = False
                except Queue.Empty:
                    continue
                if signal.event_type == backend.AUDIO_TONE:
                    # enqueue a tone
                    self.next_tone[voice] = SoundGenerator(signal_sources[voice],
                                                      feedback_tone, *signal.params)
                elif signal.event_type == backend.AUDIO_NOISE:
                    # enqueue a noise
                    feedback = feedback_noise if signal.params[0] else feedback_periodic
                    self.next_tone[voice] = SoundGenerator(signal_sources[3],
                                                      feedback, *signal.params[1:])
        return empty

    def _play_sound(self):
        """ play sounds. """
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
                        backend.tone_queue[voice].task_done()
                    else:
                        current_chunk[voice] = numpy.array([], dtype=numpy.int16)
                        while (self.next_tone[voice] and
                                        len(current_chunk[voice]) < chunk_length):
                            chunk = self.next_tone[voice].build_chunk()
                            if chunk is None:
                                # tone has finished
                                self.next_tone[voice] = None
                                backend.tone_queue[voice].task_done()
                            else:
                                current_chunk[voice] = numpy.concatenate(
                                                    (current_chunk[voice], chunk))
                if self.loop_sound[voice]:
                    # currently looping sound
                    current_chunk[voice] = self.loop_sound[voice].build_chunk()
        for voice in range(4):
            if current_chunk[voice] is not None and len(current_chunk[voice]) != 0:
                snd = pygame.sndarray.make_sound(current_chunk[voice])
                mixer.Channel(voice).queue(snd)
        # check if mixer can be quit
        self._check_quit()

    def _check_quit(self):
        """ Quit the mixer if not running a program and sound quiet for a while. """
        global quiet_ticks
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
    """ Stop sound on a channel. """
    if mixer.get_init():
        mixer.Channel(channel).stop()
        # play short silence to avoid blocking the channel
        # otherwise it won't play on queue()
        silence = pygame.sndarray.make_sound(numpy.zeros(1, numpy.int16))
        mixer.Channel(channel).play(silence)

def check_init_mixer():
    """ Initialise the mixer if necessary. """
    if mixer.get_init() is None:
        mixer.init()


##############################################################################
# synthesizer

# initial condition - see dosbox source
init_noise = 0x0f35
# white noise feedback
feedback_noise = 0x4400
# 'periodic' feedback mask (15-bit rotation)
feedback_periodic = 0x4000
# square wave feedback mask
feedback_tone = 0x2

# The SN76489 attenuates the volume by 2dB for each step in the volume register.
# see http://www.smspower.org/Development/SN76489
max_amplitude = (1<<(mixer_bits-1)) - 1
# 2 dB steps correspond to a voltage factor of 10**(-2./20.) as power ~ voltage**2
step_factor = 10**(-2./20.)
# geometric list of amplitudes for volume values
if numpy:
    amplitude = numpy.int16(max_amplitude*(step_factor**numpy.arange(15,-1,-1)))
else:
    amplitude = [0]*16
# zero volume means silent
amplitude[0] = 0

# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4


class SignalSource(object):
    """ Linear Feedback Shift Register to generate noise or tone. """

    def __init__(self, feedback, init=0x01):
        """ Initialise the signal source. """
        self.lfsr = init
        self.feedback = feedback

    def next(self):
        """ Get a sample bit. """
        bit = self.lfsr & 1
        self.lfsr >>= 1
        if bit:
            self.lfsr ^= self.feedback
        return bit


class SoundGenerator(object):
    """ Sound sample chunk generator. """

    def __init__(self, signal_source, feedback,
                 frequency, total_duration, fill, loop, volume):
        """ Initialise the generator. """
        # noise generator
        self.signal_source = signal_source
        self.feedback = feedback
        # actual duration and gap length
        self.duration = fill * total_duration
        self.gap = (1-fill) * total_duration
        self.amplitude = amplitude[volume]
        self.frequency = frequency
        self.loop = loop
        self.bit = 0
        self.count_samples = 0
        self.num_samples = int(self.duration * sample_rate)

    def build_chunk(self):
        """ Build a sound chunk. """
        self.signal_source.feedback = self.feedback
        if self.count_samples >= self.num_samples:
            # done already
            return None
        # work on last element of sound queue
        check_init_mixer()
        if self.frequency == 0 or self.frequency == 32767:
            chunk = numpy.zeros(chunk_length, numpy.int16)
        else:
            half_wavelength = sample_rate / (2.*self.frequency)
            num_half_waves = int(ceil(chunk_length / half_wavelength))
            # generate bits
            bits = [ -self.amplitude if self.signal_source.next()
                     else self.amplitude for _ in xrange(num_half_waves) ]
            # do sampling by averaging the signal over bins of given resolution
            # this allows to use numpy all the way
            # which is *much* faster than looping over an array
            # stretch array by half_wavelength * resolution
            resolution = 20
            matrix = numpy.repeat(numpy.array(bits, numpy.int16),
                                  int(half_wavelength*resolution))
            # cut off on round number of resolution blocks
            matrix = matrix[:len(matrix)-(len(matrix)%resolution)]
            # average over blocks
            matrix = matrix.reshape((len(matrix)/resolution, resolution))
            chunk = numpy.int16(numpy.average(matrix, axis=1))
        if not self.loop:
            # last chunk is shorter
            if self.count_samples + len(chunk) < self.num_samples:
                self.count_samples += len(chunk)
            else:
                # append final chunk
                rest_length = self.num_samples - self.count_samples
                chunk = chunk[:rest_length]
                # append quiet gap if requested
                if self.gap:
                    gap_chunk = numpy.zeros(int(self.gap * sample_rate),
                                            numpy.int16)
                    chunk = numpy.concatenate((chunk, gap_chunk))
                # done
                self.count_samples = self.num_samples
        # if loop, attach one chunk to loop, do not increment count
        return chunk


# three tone voices plus a noise source
signal_sources = [  SignalSource(feedback_tone),
                    SignalSource(feedback_tone),
                    SignalSource(feedback_tone),
                    SignalSource(feedback_noise, init_noise) ]


prepare()
