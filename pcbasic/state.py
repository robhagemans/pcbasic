"""
PC-BASIC - state.py
Support for pickling emulator state

(c) 2014--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle

import copy_reg
import os
import io
import logging
import zlib
import sys
from contextlib import contextmanager


@contextmanager
def manage_state(session, state_file, do_resume):
    """Resume a session if requested; save upon exit"""
    if do_resume:
        session = zunpickle(state_file).attach(session.interface)
    try:
        yield session
    finally:
        zpickle(session, state_file)


def unpickle_file(name, mode, pos):
    """Unpickle a file object."""
    if name is None:
        if mode in ('r', 'rb'):
            return sys.stdin
        else:
            return sys.stdout
    try:
        if 'w' in mode and pos > 0:
            # preserve existing contents of writable file
            with io.open(name, 'rb') as f:
                buf = f.read(pos)
            f = io.open(name, mode)
            f.write(buf)
        else:
            f = io.open(name, mode)
            if pos > 0:
                f.seek(pos)
    except IOError:
        logging.warning('Could not re-open file %s. Replacing with null file.', name)
        f = io.open(os.devnull, mode)
    return f

def pickle_file(f):
    """Pickle a file object."""
    if f in (sys.stdout, sys.stdin):
        return unpickle_file, (None, f.mode, -1)
    try:
        return unpickle_file, (f.name, f.mode, f.tell())
    except IOError:
        # not seekable
        return unpickle_file, (f.name, f.mode, -1)

# register the picklers for file and cStringIO
copy_reg.pickle(file, pickle_file)
copy_reg.pickle(io.BufferedReader, pickle_file)
copy_reg.pickle(io.BufferedWriter, pickle_file)


def zunpickle(state_file):
    """Read a compressed pickle string."""
    if state_file:
        try:
            with open(state_file, 'rb') as f:
                s = zlib.decompress(f.read())
                return pickle.loads(s)
        except EnvironmentError:
            logging.error('Could not read from %s', state_file)

def zpickle(obj, state_file):
    """Retuen a compressed pickle string."""
    if state_file:
        try:
            with open(state_file, 'wb') as f:
                f.write(zlib.compress(pickle.dumps(obj, 2)))
        except EnvironmentError:
            logging.error('Could not write to %s', state_file)
