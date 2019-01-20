"""
PC-BASIC - synthesiser.py
Tone and noise sample generator

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from math import ceil

from ..compat import xrange


# initial condition - see dosbox source
INIT_NOISE = 0x0f35
# white noise feedback
FEEDBACK_NOISE = 0x4400
# 'periodic' feedback mask (15-bit rotation)
FEEDBACK_PERIODIC = 0x4000
# square wave feedback mask
FEEDBACK_TONE = 0x2

# bit depth
SAMPLE_BITS = 8
# sample rate
SAMPLE_RATE = 44100

# The SN76489 attenuates the volume by 2dB for each step in the volume register.
# see http://www.smspower.org/Development/SN76489
# bits -2 (i.e. max div 4) so we can sum 4 voices
_MAX_AMPLITUDE = (1 << (SAMPLE_BITS-2)) - 1
# geometric list of amplitudes for volume values
# 2 dB steps correspond to a voltage factor of 10**(-2./20.) as power ~ voltage**2
_STEP_FACTOR = 10 ** (-2./20.)
# zero volume means silent
_AMPLITUDE = [0] + [int(_MAX_AMPLITUDE * _STEP_FACTOR**_power) for _power in range(14, -1, -1)]

# resolution for averaging
_RESOLUTION = 20


class SignalSource(object):
    """Linear Feedback Shift Register to generate noise or tone."""

    def __init__(self, feedback, init=0x01):
        """Initialise the signal source."""
        self.lfsr = init
        self.feedback = feedback
        # "remaining phase"/pi, i.e. runs 0 to 1 or 0 to -1 on half wavelength
        self.phase = 0.
        self.bit = 0

    def next(self):
        """Get a sample bit."""
        bit = self.lfsr & 1
        self.lfsr >>= 1
        if bit:
            self.lfsr ^= self.feedback
        self.bit = bit
        return bit


class SoundGenerator(object):
    """Sound sample chunk generator."""

    def __init__(self, signal_source, feedback, frequency, duration, loop, volume):
        """Initialise the generator."""
        # noise generator
        self.signal_source = signal_source
        self.feedback = feedback
        # actual duration and gap length
        self.duration = duration
        self.amplitude = _AMPLITUDE[volume]
        self.frequency = frequency
        self.loop = loop
        self.count_samples = 0
        self.num_samples = int(self.duration * SAMPLE_RATE)

    def build_chunk(self, length):
        """Build a sound chunk."""
        self.signal_source.feedback = self.feedback
        if self.count_samples >= self.num_samples:
            # done already
            return None
        # don't generate too many samples
        if length + self.count_samples > self.num_samples and not self.loop:
            length = (self.num_samples - self.count_samples)
        if self.frequency == 32767:
            self.frequency = 0
        # work on last element of sound queue
        if self.frequency == 0:
            chunk = bytearray(length)
        else:
            half_wavelength = SAMPLE_RATE / (2.*self.frequency)
            # generate first half-wave so as to complete the last one played
            if self.signal_source.phase:
                first_length = int(half_wavelength * self.signal_source.phase)
                first_half_wave = bytearray([self.signal_source.bit]) * first_length * _RESOLUTION
                length -= first_length
                self.signal_source.phase = 0.
            else:
                first_half_wave = bytearray()
            num_half_waves = int(ceil(length / half_wavelength))
            # generate bits
            bits = (
                self.signal_source.next()
                for _ in range(num_half_waves)
            )
            # do sampling by averaging the signal over bins of given resolution
            # this allows to use vectors all the way
            # which is *much* faster than looping over an array
            # stretch array by half_wavelength * _RESOLUTION
            stretch = int(half_wavelength * _RESOLUTION)
            waves = bytearray().join(bytearray([_b]) * stretch for _b in bits)
            matrix = bytearray().join((first_half_wave, waves))
            # cut off on round number of resolution blocks
            use_length = len(matrix) - (len(matrix) % _RESOLUTION)
            # average over blocks
            chunk = bytearray(
                self.amplitude * sum(matrix[_i:_i+_RESOLUTION]) // _RESOLUTION
                for _i in xrange(0, use_length, _RESOLUTION)
            )
        if not self.loop:
            # last chunk is shorter
            if self.count_samples + len(chunk) < self.num_samples:
                self.count_samples += len(chunk)
            else:
                # append final chunk
                rest_length = self.num_samples - self.count_samples
                # keep track of remaining phase to avoid ticks
                if self.frequency:
                    self.signal_source.phase = float(len(chunk) - rest_length) / half_wavelength
                else:
                    self.signal_source.phase = 0.
                chunk = chunk[:rest_length]
                # done
                self.count_samples = self.num_samples
        # if loop, attach one chunk to loop, do not increment count
        return chunk


def get_signal_sources():
    """Return three tone voices plus a noise source."""
    return [
        SignalSource(FEEDBACK_TONE),
        SignalSource(FEEDBACK_TONE),
        SignalSource(FEEDBACK_TONE),
        SignalSource(FEEDBACK_NOISE, INIT_NOISE)
    ]
