#
# PC-BASIC 3.23  - rnd.py
#
# Random number generator
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import error
import fp
import vartypes

def clear():
    global rnd_seed
    global rnd_step
    global rnd_a
    global rnd_c
    global rnd_period
    rnd_seed = 5228370 # 0x4fc752
    rnd_step = 4455680 # 0x43fd00
    rnd_period = 2**24
    rnd_a = 214013
    rnd_c = 2531011

clear()

def randomize(val):        
    global rnd_seed
    # get the bytes
    s = val[1]
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
    final_two = s[-2:]
    mask = bytearray('\x00\x00')
    if len(s) >= 4:
        mask = s[-4:-2]
    final_two = bytearray(chr(final_two[0]^mask[0]) + chr(final_two[1]^mask[1]))
    n = vartypes.sint_to_value(final_two)
    # this reproduces gwbasic for anything entered on the randomize prompt in the allowed range (-32768..32767)
    # on a program line, the range (-32787..32787) gives the same result reproduced here.
    rnd_seed &= 0xff
    get_random() # RND(1)
    rnd_seed += n * rnd_step
    rnd_seed %= rnd_period
    
def get_random(inp=None):
    global rnd_seed
    n = 1
    if inp:
        if inp[0] == '$':
            raise error.RunError(5)
        else:
            n = vartypes.pass_int_unpack(inp)
    if n < 0:
        n = -n
        while n < 2**23:
            n *= 2
        rnd_seed = n
    if n != 0:
        rnd_seed = (rnd_seed*rnd_a + rnd_c) % rnd_period       
    # rnd_seed/rnd_period
    return fp.pack(fp.div(fp.Single.from_int(rnd_seed), fp.Single.from_int(rnd_period)))

    
