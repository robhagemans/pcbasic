"""
PC-BASIC - rnd.py
Random number generator

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import fp
import vartypes
import state

rnd_step = 4455680 # 0x43fd00
rnd_period = 2**24
rnd_a = 214013
rnd_c = 2531011

def prepare():
    """ Initialise the rnd module. """
    clear()

def clear():
    """ Reset the random number generator. """
    state.basic_state.rnd_seed = 5228370 # 0x4fc752

def randomize(val):
    """ Reseed the random number generator. """
    # RANDOMIZE converts to int in a non-standard way - looking at the first two bytes in the internal representation
    # on a program line, if a number outside the signed int range (or -32768) is entered,
    # the number is stored as a MBF double or float. Randomize then:
    #   - ignores the first 4 bytes (if it's a double)
    #   - reads the next two
    #   - xors them with the final two (most signifant including sign bit, and exponent)
    # and interprets them as a signed int
    # e.g. 1#    = /x00/x00/x00/x00 /x00/x00/x00/x81 gets read as /x00/x00 ^ /x00/x81 = /x00/x81 -> 0x10000-0x8100 = -32512 (sign bit set)
    #      0.25# = /x00/x00/x00/x00 /x00/x00/x00/x7f gets read as /x00/x00 ^ /x00/x7f = /x00/x7F -> 0x7F00 = 32512 (sign bit not set)
    #              /xDE/xAD/xBE/xEF /xFF/x80/x00/x80 gets read as /xFF/x80 ^ /x00/x80 = /xFF/x00 -> 0x00FF = 255
    s = val[1]
    final_two = s[-2:]
    mask = bytearray('\x00\x00')
    if len(s) >= 4:
        mask = s[-4:-2]
    final_two = bytearray(chr(final_two[0]^mask[0]) + chr(final_two[1]^mask[1]))
    n = vartypes.sint_to_value(final_two)
    state.basic_state.rnd_seed &= 0xff
    get_random_int(1) # RND(1)
    state.basic_state.rnd_seed += n * rnd_step
    state.basic_state.rnd_seed %= rnd_period

def get_random_int(n):
    """ Get a value from the random number generator (int argument). """
    if n < 0:
        n = -n
        while n < 2**23:
            n *= 2
        state.basic_state.rnd_seed = n
    if n != 0:
        state.basic_state.rnd_seed = (state.basic_state.rnd_seed*rnd_a + rnd_c) % rnd_period
    # rnd_seed/rnd_period
    return fp.pack(fp.div(fp.Single.from_int(state.basic_state.rnd_seed), fp.Single.from_int(rnd_period)))

def get_random(mbf):
    """ Get a value from the random number generator (MBF single argument). """
    return get_random_int(-(mbf.man>>8) if mbf.neg else mbf.man>>8)

prepare()
