"""
PC-BASIC - synthesiser.py
Tone and noise sample generator

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from math import ceil

try:
    import numpy
except ImportError:
    numpy = None


# sample rate and bit depth
sample_bits = 16
sample_rate = 44100

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
max_amplitude = (1<<(sample_bits-1)) - 1
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
    """Linear Feedback Shift Register to generate noise or tone."""

    def __init__(self, feedback, init=0x01):
        """Initialise the signal source."""
        self.lfsr = init
        self.feedback = feedback

    def next(self):
        """Get a sample bit."""
        bit = self.lfsr & 1
        self.lfsr >>= 1
        if bit:
            self.lfsr ^= self.feedback
        return bit


class SoundGenerator(object):
    """Sound sample chunk generator."""

    def __init__(self, signal_source, feedback,
                 frequency, total_duration, fill, loop, volume):
        """Initialise the generator."""
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
        """Build a sound chunk."""
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


def get_signal_sources():
    """Return three tone voices plus a noise source."""
    return [SignalSource(feedback_tone),
            SignalSource(feedback_tone),
            SignalSource(feedback_tone),
            SignalSource(feedback_noise, init_noise)]
