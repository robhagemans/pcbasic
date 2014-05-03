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

try:
    import cPickle as pickle
except ImportError:
    import pickle
import os
import zlib
import copy
import logging

        
class State(object):
    pass

# display backends can extend this for their pickling needs
class DisplayState(State):
    def pickle(self):
        pass
    
    def unpickle(self):
        pass
        
basic_state = State()        
io_state = State()
console_state = State()
display = DisplayState()

# a state has been loaded
loaded = False

pcbasic_dir = os.path.dirname(os.path.realpath(__file__))
state_file = os.path.join(pcbasic_dir, 'info', 'STATE.SAV')

# backend implementations
video = None
sound = None 
penstick = None 

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
    to_pickle.basic.direct_line = cStringIO_Pickler(basic_state.direct_line)
    # I/O
    to_pickle.io = copy.copy(io_state)
    to_pickle.io.files = {}
    to_pickle.io.devices = {}
    
    # Console
    to_pickle.console = copy.copy(console_state)
    # Display 
    to_pickle.display = display
    to_pickle.display.pickle()
    # pickle and compress
    s = zlib.compress(pickle.dumps(to_pickle, 2))
    try:
        f = open(state_file, 'wb')
        f.write(str(len(s)) + '\n' + s)
        f.close()
    except IOError:
        logging.warning("Could not write to state file. Emulator state not saved.")
    
def load():
    global console_state, io_state, basic_state, display, loaded
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
    io_state, basic_state, console_state = from_pickle.io, from_pickle.basic, from_pickle.console
    basic_state.bytecode = basic_state.bytecode.unpickle()
    basic_state.direct_line = basic_state.direct_line.unpickle()
    from_pickle.display.unpickle()
    loaded = True
    return True
    
def delete():
    os.remove(state_file)

    
