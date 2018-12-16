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

import os
import io
import logging
import zlib
import sys
from contextlib import contextmanager

from .compat import PY2, copyreg, stdout, stdin


@contextmanager
def manage_state(session, state_file, do_resume):
    """Resume a session if requested; save upon exit"""
    if do_resume and state_file:
        try:
            session = load_session(state_file).attach(session.interface)
        except Exception as e:
            # if we were told to resume but can't, give up
            logging.fatal('Failed to resume session from %s: %s', state_file, e)
            sys.exit(1)
    try:
        yield session
    finally:
        if state_file:
            try:
                save_session(session, state_file)
            except Exception as e:
                logging.error('Failed to save session to %s: %s', state_file, e)


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
    if f in (sys.stdout, sys.stdin, stdout, stdin, stdout.buffer, stdin.buffer):
        return unpickle_file, (None, f.mode, -1)
    try:
        return unpickle_file, (f.name, f.mode, f.tell())
    except IOError:
        # not seekable
        return unpickle_file, (f.name, f.mode, -1)

# register the picklers for file and cStringIO
if PY2:
    copyreg.pickle(file, pickle_file)
copyreg.pickle(io.BufferedReader, pickle_file)
copyreg.pickle(io.BufferedWriter, pickle_file)
copyreg.pickle(io.TextIOWrapper, pickle_file)
copyreg.pickle(io.BufferedRandom, pickle_file)


def load_session(state_file):
    """Read state from a compressed pickle."""
    with open(state_file, 'rb') as f:
        s = zlib.decompress(f.read())
        return pickle.loads(s)

def save_session(obj, state_file):
    """Write state to a compressed pickle."""
    with open(state_file, 'wb') as f:
        f.write(zlib.compress(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)))
