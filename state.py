#
# PC-BASIC 3.23 - state.py
#
# Emulator state
# 
# (c) 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import pickle
import os
import zlib

class State(object):
    pass

basic_state = State()        
console_state = State()
display_state = State()

display_state.do_load = None

def save(f):
    state_to_keep = (console_state, display_state)
    s = zlib.compress(pickle.dumps(state_to_keep, 2))
    f.write(str(len(s)) + '\n' + s + '\n')

def load(f):
    global console_state, display_state
    length = int(f.readline())
    console_state, display_state = pickle.loads(zlib.decompress(f.read(length)))
    f.read(1)
    # ensure the display gets loaded
    display_state.do_load = f

