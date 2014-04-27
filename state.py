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
import copy
import logging
        
class State(object):
    pass

basic_state = State()        
console_state = State()
display_state = State()

pcbasic_dir = os.path.dirname(os.path.realpath(__file__))
state_file = os.path.join(pcbasic_dir, 'info', 'STATE.SAV')

###############################################

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class cStringIO_Pickler(object):
    def __init__(self, csio):
        self.value = csio.getvalue()
        self.pos = csio.tell()

    def unpickle(self):
        # needs to be called without arguments or it's a StringI object without write()
        csio = StringIO()
        csio.write(self.value)
        csio.seek(self.pos)
        return csio             

###############################################

def save():
    # prepare pickling object
    to_pickle = State()
    # BASIC state
    to_pickle.basic = copy.copy(basic_state)
    to_pickle.basic.bytecode = cStringIO_Pickler(basic_state.bytecode)
    # Console
    to_pickle.console = copy.copy(console_state)
    # Display
    to_pickle.display = copy.copy(display_state)
    # pickle and compress
    s = zlib.compress(pickle.dumps(to_pickle, 2))
    try:
        f = open(state_file, 'wb')
        f.write(str(len(s)) + '\n' + s)
        f.close()
    except IOError:
        logging.warning("Could not write to state file. Emulator state not saved.")
        pass
    
def load():
    global console_state, display_state, basic_state
    # decompress and unpickle
    try:
        f = open(state_file, 'rb')
        length = int(f.readline())
        from_pickle = pickle.loads(zlib.decompress(f.read(length)))
        f.close()
    except IOError:
        logging.warning("Could not load from state file.")
        return False
    # unpack pickling object
    basic_state, console_state, display_state = from_pickle.basic, from_pickle.console, from_pickle.display
    basic_state.bytecode = basic_state.bytecode.unpickle()
    return True
    
def delete():
    os.remove(state_file)

    
