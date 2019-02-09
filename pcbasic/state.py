"""
PC-BASIC - state.py
Support for pickling emulator state

(c) 2014--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    import cPickle as pickle
except ImportError:
    import pickle

import os
import io
import sys
import zlib
import struct
import logging
from contextlib import contextmanager

from .metadata import VERSION
from .compat import PY2, copyreg, stdout, stdin

# session file header
HEADER_FORMAT = '<LIIIII'
HEADER_KEYS = [
    'checksum', 'format_version', 'python_major', 'python_minor', 'pcbasic_major', 'pcbasic_minor'
]
HEADER = {
    # increment this if we change the format of the session file
    'format_version': 2,
    'python_major': sys.version_info.major,
    'python_minor': sys.version_info.minor,
    'pcbasic_major': int(VERSION.split(u'.')[0]),
    'pcbasic_minor': int(VERSION.split(u'.')[1]),
}

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
    copyreg.pickle(file, pickle_file)  # pylint: disable=undefined-variable
copyreg.pickle(io.BufferedReader, pickle_file)
copyreg.pickle(io.BufferedWriter, pickle_file)
copyreg.pickle(io.TextIOWrapper, pickle_file)
copyreg.pickle(io.BufferedRandom, pickle_file)


def load_session(state_file):
    """Read state from a compressed pickle."""
    with open(state_file, 'rb') as in_file:
        header = in_file.read(struct.calcsize(HEADER_FORMAT))
        blob = in_file.read()
    # mask checksum to deal with different signs on Py2/Py3
    # see https://docs.python.org/3.5/library/zlib.html#zlib.crc32
    checksum = zlib.crc32(blob) & 0xffffffff
    try:
        header_dict = dict(zip(HEADER_KEYS, struct.unpack(HEADER_FORMAT, header)))
    except struct.error:
        raise ValueError('session file header corrupted')
    # check blob integrity
    if checksum != header_dict['checksum']:
        raise ValueError('session file corrupted')
    if (
            HEADER['python_major'] != header_dict['python_major']
            or HEADER['python_minor'] != header_dict['python_minor']
        ):
        raise ValueError('session file stored with different Python version')
    if (
            HEADER['pcbasic_major'] != header_dict['pcbasic_major']
            or HEADER['pcbasic_minor'] != header_dict['pcbasic_minor']
        ):
        raise ValueError('session file stored with different PC-BASIC version')
    session = pickle.loads(zlib.decompress(blob))
    return session

def save_session(obj, state_file):
    """Write state to a compressed pickle."""
    blob = zlib.compress(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL))
    checksum = zlib.crc32(blob) & 0xffffffff
    header_dict = dict(checksum=checksum, **HEADER)
    header = struct.pack(HEADER_FORMAT, *(header_dict[_key] for _key in HEADER_KEYS))
    with open(state_file, 'wb') as out_file:
        out_file.write(header)
        out_file.write(blob)
