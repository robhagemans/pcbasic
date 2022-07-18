"""
PC-BASIC - state.py
Support for pickling emulator state

(c) 2014--2022 Rob Hagemans
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
import codecs
import logging
from contextlib import contextmanager

from .basic import VERSION
from .compat import PY2, copyreg, stdio

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

def unpickle_bytesio(value, pos):
    """Unpickle a file object."""
    stream = io.BytesIO(value)
    stream.seek(pos)
    return stream

def pickle_bytesio(f):
    """Pickle a BytesIO object."""
    return unpickle_bytesio, (f.getvalue(), f.tell())

def unpickle_file(name, mode, pos):
    """Unpickle a file object."""
    if name is None:
        if mode == 'rb' or (PY2 and mode == 'r'):
            return stdio.stdin.buffer
        elif mode == 'r':
            return stdio.stdin
        elif mode == 'wb' or (PY2 and mode == 'w'):
            return stdio.stdout.buffer
        elif mode == 'w':
            return stdio.stdout
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
        pass
    else:
        return f
    logging.warning('Could not re-open file %s. Replacing with null file.', name)
    return io.open(os.devnull, mode)

def pickle_file(f):
    """Pickle a file object."""
    if f in (
            sys.stdout, sys.stdin,
            stdio.stdout, stdio.stdin,
            stdio.stdout.buffer, stdio.stdin.buffer
        ):
        return unpickle_file, (None, f.mode, -1)
    try:
        return unpickle_file, (f.name, f.mode, f.tell())
    except (IOError, ValueError):
        # IOError: not seekable
        # ValueError: closed
        return unpickle_file, (f.name, f.mode, -1)

# register the picklers for file and cStringIO
if PY2: # pragma: no cover
    copyreg.pickle(file, pickle_file)  # pylint: disable=undefined-variable
copyreg.pickle(io.BufferedReader, pickle_file)
copyreg.pickle(io.BufferedWriter, pickle_file)
copyreg.pickle(io.TextIOWrapper, pickle_file)
copyreg.pickle(io.BufferedRandom, pickle_file)
copyreg.pickle(io.BytesIO, pickle_bytesio)

# patch codecs.StreamReader and -Writer
if PY2: # pragma: no cover
    def patched_getstate(self):
        return vars(self)

    def patched_setstate(self, dict):
        vars(self).update(dict)

    for streamclass in (codecs.StreamReader, codecs.StreamWriter, codecs.StreamReaderWriter):
        streamclass.__getstate__ = patched_getstate
        streamclass.__setstate__ = patched_setstate


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
