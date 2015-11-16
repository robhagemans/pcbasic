"""
PC-BASIC - audio_sdl2.py
Sound interface based on SDL2

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

# see e.g. http://toomanyideas.net/2014/pysdl2-playing-a-sound-from-a-wav-file.html

from math import ceil
import logging
import Queue
import ctypes
from collections import deque

try:
    import sdl2
except ImportError:
    sdl2 = None

try:
    import numpy
except ImportError:
    numpy = None

import backend
import audio

tick_ms = 24

# mixer settings
mixer_bits = 16
sample_rate = 44100

# approximate generator chunk length
# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4

callback_chunk_length = 2048
min_samples_buffer = 2*callback_chunk_length

def prepare():
    """ Initialise sound module. """
    audio.plugin_dict['sdl2'] = AudioSDL2


##############################################################################
# plugin

class AudioSDL2(audio.AudioPlugin):
    """ SDL2-based audio plugin. """

    def __init__(self):
        """ Initialise sound system. """
        if not sdl2:
            logging.warning('SDL2 module not found. Failed to initialise SDL2 audio plugin.')
            raise audio.InitFailed()
        if not numpy:
            logging.warning('NumPy module not found. Failed to initialise SDL2 audio plugin.')
            raise audio.InitFailed()
        # sound generators for each tone
        self.generators = [deque(), deque(), deque(), deque()]
        # buffer of samples; drained by callback, replenished by _play_sound
        self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
        # SDL AudioDevice and specifications
        self.audiospec = sdl2.SDL_AudioSpec(0, 0, 0, 0)
        self.audiospec.freq = sample_rate
        # samples are 16-bit signed ints
        self.audiospec.format = sdl2.AUDIO_S16SYS
        self.audiospec.channels = 1
        self.audiospec.samples = callback_chunk_length
        self.audiospec.callback = sdl2.SDL_AudioCallback(self._get_next_chunk)
        self.dev = None
        # start audio thread
        audio.AudioPlugin.__init__(self)

    def _init_sound(self):
        """ Perform any necessary initialisations. """
        self.dev = sdl2.SDL_OpenAudioDevice(None, 0, self.audiospec, None, 0)
        if self.dev == 0:
            logging.warning('Could not open audio device: %s', sdl2.SDL_GetError())
        # unpause the audio device
        sdl2.SDL_PauseAudioDevice(self.dev, 0)

    def _sleep(self):
        """ Sleep a tick to avoid hogging the cpu. """
        sdl2.SDL_Delay(tick_ms)

    def _drain_message_queue(self):
        """ Drain signal queue. """
        while True:
            try:
                signal = backend.message_queue.get(False)
            except Queue.Empty:
                return True
            backend.message_queue.task_done()
            if signal.event_type == backend.AUDIO_STOP:
                self.next_tone = [None, None, None, None]
                self.generators = [deque(), deque(), deque(), deque()]
                sdl2.SDL_LockAudioDevice(self.dev)
                self.samples = [numpy.array([], numpy.int16) for _ in range(4)]
                sdl2.SDL_UnlockAudioDevice(self.dev)
            elif signal.event_type == backend.AUDIO_QUIT:
                # close thread
                return False

    def _drain_tone_queue(self):
        """ Drain signal queue. """
        empty = False
        while not empty:
            empty = True
            for voice, q in enumerate(backend.tone_queue):
                try:
                    signal = q.get(False)
                    empty = False
                except Queue.Empty:
                    continue
                if signal.event_type == backend.AUDIO_TONE:
                    # enqueue a tone
                    self.generators[voice].append(SoundGenerator(
                        signal_sources[voice], feedback_tone, *signal.params))
                elif signal.event_type == backend.AUDIO_NOISE:
                    # enqueue a noise
                    feedback = feedback_noise if signal.params[0] else feedback_periodic
                    self.generators[voice].append(SoundGenerator(
                        signal_sources[3], feedback, *signal.params[1:]))
        return empty

    def _play_sound(self):
        """ Replenish sample buffer. """
        for voice in range(4):
            if len(self.samples[voice]) > min_samples_buffer:
                # nothing to do
                continue
            while True:
                if self.next_tone[voice] is None:
                    try:
                        self.next_tone[voice] = self.generators[voice].popleft()
                    except IndexError:
                        # FIXME: loop last tone if loop property was set?
                        current_chunk = None
                        break
                current_chunk = self.next_tone[voice].build_chunk(chunk_length)
                if current_chunk is not None:
                    break
                backend.tone_queue[voice].task_done()
                self.next_tone[voice] = None
            if current_chunk is not None:
                # append chunk to samples list
                # lock to ensure callback doesn't try to access the list too
                sdl2.SDL_LockAudioDevice(self.dev)
                self.samples[voice] = numpy.concatenate(
                        (self.samples[voice], current_chunk))
                sdl2.SDL_UnlockAudioDevice(self.dev)

    def _get_next_chunk(self, notused, stream, length_bytes):
        """ Callback function to generate the next chunk to be played. """
        # this is for 16-bit samples
        length = length_bytes/2
        samples = [self.samples[voice][:length] for voice in range(4)]
        self.samples = [self.samples[voice][length:] for voice in range(4)]
        # if samples have run out, add silence
        # FIXME: loop sounds
        for voice in range(4):
            if len(samples[voice]) < length:
                silence = numpy.zeros(length-len(samples[voice]), numpy.int16)
                samples[voice] = numpy.concatenate((samples[voice], silence))
        # mix the samples by averaging
        self.mixed = numpy.mean(samples, axis=0, dtype=numpy.int16)
        # copy into byte array (is there a better way?)
        for i in xrange(length_bytes):
            stream[i] = ord(self.mixed.data[i])

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

    def build_chunk(self, length):
        """ Build a sound chunk. """
        self.signal_source.feedback = self.feedback
        if self.count_samples >= self.num_samples:
            # done already
            return None
        # work on last element of sound queue
        if self.frequency == 0 or self.frequency == 32767:
            chunk = numpy.zeros(length, numpy.int16)
        else:
            half_wavelength = sample_rate / (2.*self.frequency)
            num_half_waves = int(ceil(length / half_wavelength))
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
            chunk = numpy.int16(numpy.mean(matrix, axis=1))
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
