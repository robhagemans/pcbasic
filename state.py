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
import copy

import oslayer

class State(object):
    pass
        
console_state = State()
display_state = State()

state_file = os.path.join(oslayer.drives['@'], 'STATE.PKL')

display_state.do_load = ''

def save():
    f = oslayer.safe_open(state_file, 'S', 'W')
    state_to_keep = (console_state, display_state)
    pickle.dump(state_to_keep, f)
    f.close()

def load(displaysave):
    global console_state, display_state
    f = oslayer.safe_open(state_file, 'L', 'R')
    console_state, display_state = pickle.load(f)
    f.close()
    #ensure the display gets loaded
    display_state.do_load = displaysave

