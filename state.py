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
import logging
import plat
import config        
        
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

def prepare():
    global state_file, loaded
    if config.options['state']:
        state_file = config.options['state']
    elif os.path.exists('PCBASIC.SAV'):
        state_file = 'PCBASIC.SAV'
    else:            
        state_file = os.path.join(plat.info_dir, 'PCBASIC.SAV')


###############################################

try:
    import cStringIO
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import copy_reg


def unpickle_file(name, mode, pos):
    try:
        if 'w' in mode and pos > 0:
            # preserve existing contents of writable file
            f = open(name, 'rb')
            buf = f.read(pos)
            f.close()
            f = open(name, mode)
            f.write(buf)            
        else:    
            f = open(name, mode)
            if pos > 0:
                f.seek(pos)
    except IOError:
        logging.warning('Could not re-open file %s. Replacing with null file.', name)
        f = open(os.devnull, mode)
    return f
        
def pickle_file(f):
    try:
        return unpickle_file, (f.name, f.mode, f.tell())
    except IOError:
        # not seekable
        return unpickle_file, (f.name, f.mode, -1)
        

def unpickle_StringIO(value, pos):
    # needs to be called without arguments or it's a StringI object without write()
    csio = StringIO()
    csio.write(value)
    csio.seek(pos)
    return csio             

def pickle_StringIO(csio):
    value = csio.getvalue()
    pos = csio.tell()
    return unpickle_StringIO, (value, pos)

copy_reg.pickle(file, pickle_file)
copy_reg.pickle(cStringIO.OutputType, pickle_StringIO)
 


###############################################

def save():
    # prepare pickling object
    to_pickle = State()
    to_pickle.basic, to_pickle.io, to_pickle.console = basic_state, io_state, console_state
    # pack display
    to_pickle.display = display
    to_pickle.display.pickle()
    # pickle and compress
    s = zlib.compress(pickle.dumps(to_pickle, 2))
    try:
        f = open(state_file, 'wb')
        f.write(str(len(s)) + '\n' + s)
        f.close()
    except IOError:
        logging.warning("Could not write to state file %s. Emulator state not saved.", state_file)
    
def load():
    global console_state, io_state, basic_state, loaded
    # decompress and unpickle
    try:
        f = open(state_file, 'rb')
        length = int(f.readline())
        from_pickle = pickle.loads(zlib.decompress(f.read(length)))
        f.close()
    except IOError:
        logging.warning("Could not read state file %s. Emulator state not loaded.", state_file)
        return False
    # unpack pickling object
    io_state, basic_state, console_state = from_pickle.io, from_pickle.basic, from_pickle.console
    # unpack display
    from_pickle.display.unpickle()
    loaded = True
    return True
    
def delete():
    os.remove(state_file)

prepare()
    
