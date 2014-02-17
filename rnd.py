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


def randomize_int(n):
    global rnd_seed
    # this reproduces gwbasic for anything entered on the randomize prompt in the allowed range (-32768..32767)
    # on a program line, the range (-32787..32787) gives the same result reproduced here.
    rnd_seed &= 0xff
    # vrnd(('',''))
    get_random() # RND(1)
    rnd_seed += n*rnd_step
    rnd_seed %= rnd_period
    
    
    
def get_random(inp=None):
    global rnd_seed
    n = 1
    if inp==None or inp[0]=='':
        pass
    elif inp[0]=='$':
        raise error.RunError(5)
    else:
        n = vartypes.pass_int_unpack(inp)
    if n==0:
        pass
    else:
        if n<0:
            n=-n
            while n < 2**23:
                n *= 2
            rnd_seed = n
        rnd_seed = (rnd_seed*rnd_a + rnd_c) % rnd_period       
    # rnd_seed/rnd_period
    return fp.pack(fp.div(fp.Single.from_int(rnd_seed), fp.Single.from_int(rnd_period)))

    
