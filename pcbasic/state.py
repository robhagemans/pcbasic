"""
PC-BASIC - state.py
Emulator state

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
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


session = None

# name of state file
state_name = 'PCBASIC.SAV'


def prepare():
    """ Initialise the state module. """
    global state_file
    state_file = config.get('state')
    if os.path.exists(state_name):
        state_file = state_name
    else:
        state_file = os.path.join(plat.state_path, state_name)
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
    # pickle and compress
    try:
        with open(state_file, 'wb') as f:
            f.write(zlib.compress(pickle.dumps(session, 2)))
    except IOError:
        logging.warning("Could not write to state file %s. Emulator state not saved.", state_file)

def load():
    """ Load emulator state from file. """
    global session
    if not state_file:
        return False
    # decompress and unpickle
    try:
        with open(state_file, 'rb') as f:
            session = pickle.loads(zlib.decompress(f.read()))
    except IOError:
        logging.warning("Could not read state file %s. Emulator state not loaded.", state_file)
        return False
    return True

def delete():
    """ Delete emulator state file. """
    try:
        os.remove(state_file)
    except OSError:
        pass

prepare()
