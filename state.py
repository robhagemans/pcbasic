"""
PC-BASIC - state.py
Emulator state

(c) 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    import cStringIO
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import copy_reg
import os
import zlib
import logging
import plat
import config


class State(object):
    """ Base class for state """
    pass

basic_state = State()
io_state = State()
console_state = State()

# a state has been loaded
loaded = False


def prepare():
    """ Initialise the state module. """
    global state_file, loaded
    if config.options['state']:
        state_file = config.options['state']
    elif os.path.exists(plat.state_name):
        state_file = plat.state_name
    else:
        state_file = os.path.join(plat.state_path, plat.state_name)
    # do not load any state file from a package
    if config.package:
        state_file = ''
    # register the picklers for file and cStringIO
    copy_reg.pickle(file, pickle_file)
    copy_reg.pickle(cStringIO.OutputType, pickle_StringIO)

def unpickle_file(name, mode, pos):
    """ Unpickle a file object. """
    try:
        if 'w' in mode and pos > 0:
            # preserve existing contents of writable file
            with open(name, 'rb') as f:
                buf = f.read(pos)
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
    """ Pickle a file object. """
    try:
        return unpickle_file, (f.name, f.mode, f.tell())
    except IOError:
        # not seekable
        return unpickle_file, (f.name, f.mode, -1)

def unpickle_StringIO(value, pos):
    """ Unpickle a cStringIO object. """
    # needs to be called without arguments or it's a StringI object without write()
    csio = StringIO()
    csio.write(value)
    csio.seek(pos)
    return csio

def pickle_StringIO(csio):
    """ Pickle a cStringIO object. """
    value = csio.getvalue()
    pos = csio.tell()
    return unpickle_StringIO, (value, pos)

def save():
    """ Save emulator state to file. """
    if not state_file:
        return
    # prepare pickling object
    to_pickle = State()
    to_pickle.basic, to_pickle.io, to_pickle.console = basic_state, io_state, console_state
    # pickle and compress
    s = zlib.compress(pickle.dumps(to_pickle, 2))
    try:
        with open(state_file, 'wb') as f:
            f.write(str(len(s)) + '\n' + s)
    except IOError:
        logging.warning("Could not write to state file %s. Emulator state not saved.", state_file)

def load():
    """ Load emulator state from file. """
    global console_state, io_state, basic_state, loaded
    if not state_file:
        return False
    # decompress and unpickle
    try:
        with open(state_file, 'rb') as f:
            length = int(f.readline())
            from_pickle = pickle.loads(zlib.decompress(f.read(length)))
    except IOError:
        logging.warning("Could not read state file %s. Emulator state not loaded.", state_file)
        return False
    # unpack pickling object
    io_state, basic_state, console_state = from_pickle.io, from_pickle.basic, from_pickle.console
    loaded = True
    return True

def delete():
    """ Delete emulator state file. """
    try:
        os.remove(state_file)
    except OSError:
        pass

prepare()
