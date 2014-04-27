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
import oslayer

class State(object):
    pass

basic_state = State()        
console_state = State()
display_state = State()
display_state.display_strings = []

pcbasic_dir = os.path.dirname(os.path.realpath(__file__))
state_file = os.path.join(pcbasic_dir, 'info', 'STATE.SAV')

def save():
    state_to_keep = (console_state, display_state)
    s = zlib.compress(pickle.dumps(state_to_keep, 2))
    f = oslayer.safe_open(state_file, 'S', 'W')
    f.write(str(len(s)) + '\n' + s)
    f.close()
    
def load():
    global console_state, display_state
    f = oslayer.safe_open(state_file, 'L', 'R')
    length = int(f.readline())
    console_state, display_state = pickle.loads(zlib.decompress(f.read(length)))

def delete():
    os.remove(state_file)


