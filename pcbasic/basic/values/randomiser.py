"""
PC-BASIC - randomiser.py
Random number generator

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
from . import values

from ...compat import int2byte


class Randomiser(object):
    """Linear Congruential Generator """

    _step = 4455680 # 0x43fd00
    _period = 2**24
    _multiplier = 214013
    _increment = 2531011

    def __init__(self, values):
        """Initialise the random number generator."""
        self.clear()
        self._values = values

    def clear(self):
        """Reset the random number generator."""
        self._seed = 5228370 # 0x4fc752

    def reseed(self, val):
        """Reseed the random number generator."""
        # RANDOMIZE converts to int in a non-standard way -
        # looking at the first two bytes in the internal representation
        # on a program line, if a number outside the signed int range (or -32768) is entered,
        # the number is stored as a MBF double or float. Randomize then:
        #   - ignores the first 4 bytes (if it's a double)
        #   - reads the next two
        #   - xors them with the final two (most significant including sign bit, and exponent)
        # and interprets them as a signed int
        # e.g. 1#    = /x00/x00/x00/x00 /x00/x00/x00/x81 gets read as /x00/x00 ^ /x00/x81
        #            = /x00/x81 -> 0x10000-0x8100 = -32512 (sign bit set)
        #      0.25# = /x00/x00/x00/x00 /x00/x00/x00/x7f gets read as /x00/x00 ^ /x00/x7f
        #            = /x00/x7F -> 0x7F00 = 32512 (sign bit not set)
        #              /xDE/xAD/xBE/xEF /xFF/x80/x00/x80 gets read as /xFF/x80 ^ /x00/x80
        #            = /xFF/x00 -> 0x00FF = 255
        s = val.to_bytes()
        final_two = s[-2:]
        mask = bytearray(2)
        if len(s) >= 4:
            mask = s[-4:-2]
        final_two = int2byte(final_two[0]^mask[0]) + int2byte(final_two[1]^mask[1])
        # unpack to signed integer
        n, = struct.unpack('<h', final_two)
        self._seed &= 0xff
        self._cycle()
        self._seed += n * self._step
        self._seed %= self._period

    def rnd_(self, args):
        """Get a value from the random number generator."""
        f, = args
        if f is None:
            # RND
            self._cycle()
        else:
            f = values.to_single(f)
            if f.is_zero():
                # RND(0) returns last value
                pass
            else:
                if f.is_negative():
                    # re-seed with integer value of mantissa
                    # so RND(-1) does not mean n==-1 but n==-2**23
                    self._seed = -f.mantissa()
                self._cycle()
        # seed/period
        return self._values.new_single().from_int(self._seed).idiv(
            self._values.new_single().from_int(self._period)
        )

    def _cycle(self):
        """Move the random number generator to the next state."""
        self._seed = (self._seed*self._multiplier + self._increment) % self._period
