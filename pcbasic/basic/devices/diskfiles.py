"""
PC-BASIC - devices.diskfiles
Disk Files

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import ntpath
from contextlib import contextmanager

from ...compat import iteritems, iterchar

from ..base.bytestream import ByteStream
from ..base import error
from .devicebase import RawFile, TextFileBase, InputMixin, safe_io, TYPE_TO_MAGIC


# binary file interface: file interface +
#   seg
#   offset
#   length

# locking interface
#   number
#   lock()
#   unlock()


class BinaryFile(RawFile):
    """File class for binary (B, P, M) files on disk device."""

    def __init__(self, fhandle, filetype, number, mode, seg, offset, length, locks):
        """Initialise program file object and write header."""
        RawFile.__init__(self, fhandle, filetype, mode)
        # don't lock binary files
        # we need the Locks object to register file as open
        self._locks = locks
        self._number = number
        # binary file parameters
        self.seg, self.offset, self.length = 0, 0, 0
        if self.mode == b'O':
            self.write(TYPE_TO_MAGIC[filetype])
            if self.filetype == b'M':
                self.write(struct.pack(b'<HHH', seg, offset, length))
                self.seg, self.offset, self.length = seg, offset, length
        else:
            # drop magic byte
            self.read(1)
            if self.filetype == b'M':
                # self.length gets ignored: even the \x1a at the end is read
                header = self.read(6)
                if len(header) == 6:
                    self.seg, self.offset, self.length = struct.unpack('<HHH', header)
                else:
                    # truncated header
                    raise error.BASICError(error.BAD_FILE_MODE)

    def close(self):
        """Write EOF and close program file."""
        if self.mode == b'O':
            self.write(b'\x1a')
        RawFile.close(self)
        # no locking for binary files, but we do need to register it closed
        self._locks.close_file(self._number)


class TextFile(TextFileBase, InputMixin):
    """Text file on disk device."""

    def __init__(self, fhandle, filetype, number, mode, locks):
        """Initialise text file object."""
        TextFileBase.__init__(self, fhandle, filetype, mode)
        self._locks = locks
        self._number = number
        # in append mode, we need to start at end of file
        if self.mode == b'A':
            with safe_io():
                self._fhandle.seek(0, 2)

    def close(self):
        """Close text file."""
        if self.mode in (b'O', b'A'):
            # write EOF char
            with safe_io():
                self._fhandle.write(b'\x1a')
        TextFileBase.close(self)
        self._locks.close_file(self._number)

    def read(self, n):
        """Read num characters."""
        self._locks.try_access(self._number, b'R')
        return TextFileBase.read(self, n)

    def read_one(self):
        """Read one character, replacing CR LF with CR."""
        c = self.read(1)
        if not c:
            return c
        # report CRLF as CR
        # but LFCR, LFCRLF, LFCRLFCR etc pass unmodified
        if (c == b'\r' and self._previous != b'\n') and self.peek(1) == b'\n':
            last, char = self._previous, self._current
            self.read(1)
            self._previous, self._current = last, char
        return c

    def read_line(self):
        """Read line from text file, break on CR or CRLF (not LF)."""
        s = []
        while True:
            c = self.read_one()
            if not c or (c == b'\r' and self._previous != b'\n'):
                # break on CR, CRLF but allow LF, LFCR to pass
                break
            s.append(c)
            if len(s) == 255:
                c = b'\r' if self.peek(1) == b'\r' else None
                break
        return b''.join(s), c

    def write(self, s, can_break=True):
        """Write string to file."""
        self._locks.try_access(self._number, b'W')
        TextFileBase.write(self, s, can_break)

    def write_line(self, s=b''):
        """Write string and newline to file."""
        self.write(s + b'\r\n')

    def loc(self):
        """Get file pointer (LOC)."""
        with safe_io():
            if self.mode == b'I':
                tell = self._fhandle.tell() - len(self._readahead)
                return max(1, (127+tell) // 128)
            return self._fhandle.tell() // 128

    def lof(self):
        """Get length of file (LOF)."""
        with safe_io():
            current = self._fhandle.tell()
            self._fhandle.seek(0, 2)
            lof = self._fhandle.tell()
            self._fhandle.seek(current)
        return lof

    def lock(self, start, stop):
        """Lock the file."""
        # range bounds are ignored on text file
        # we need a tuple in case the other file checking the lock is a random file
        self._locks.acquire_record_lock(self._number, None, None)

    def unlock(self, start, stop):
        """Unlock the file."""
        self._locks.release_record_lock(self._number, None, None)


class FieldFile(TextFile):
    """Text file on FIELD."""

    def __init__(self, field, reclen):
        """Initialise text file object."""
        # don't let the field file use device locks
        TextFile.__init__(self, ByteStream(field.view_buffer()), b'D', None, b'I', Locks())
        self._field = field
        self._reclen = reclen

    @contextmanager
    def use_mode(self, mode):
        """Use in input or output mode."""
        self._switch_mode(mode)
        yield
        self._check_overflow()

    def __getstate__(self):
        """Pickle."""
        pickledict = self.__dict__
        pickledict['_pos'] = self._fhandle.tell()
        # can't pickle memoryview objects
        del pickledict['_fhandle']
        return pickledict

    def __setstate__(self, pickledict):
        """Unpickle."""
        pos = pickledict.pop('_pos')
        self. __dict__ = pickledict
        self._fhandle = ByteStream(self._field.view_buffer())
        self._fhandle.seek(pos)

    def _switch_mode(self, new_mode):
        """Switch to input or output mode and fix readahaed buffer."""
        if new_mode == b'I' and self.mode == b'O':
            self._fhandle.flush()
            self.mode = b'I'
        elif new_mode == b'O' and self.mode == b'I':
            self._fhandle.seek(-len(self._readahead), 1)
            self._readahead = []
            self._previous, self._current = b'', b''
            self.mode = b'O'

    def _check_overflow(self):
        """Check for FIELD OVERFLOW."""
        # FIELD overflow happens if last byte in record has been read or written
        if self._fhandle.tell() - len(self._readahead) >= self._reclen:
            raise error.BASICError(error.FIELD_OVERFLOW)

    def set_buffer(self, contents):
        """Set the contents of the buffer."""
        # take contents and pad with NULL to required size
        try:
            self._field.view_buffer()[:self._reclen] = contents.ljust(self._reclen, b'\0')
        except ValueError:
            # can't modify size of memoryview
            raise error.BASICError(error.FIELD_OVERFLOW)
        # reset field text file loc
        self._fhandle.seek(0)

    def get_buffer(self):
        """Get a copy of the contents of the buffer."""
        return bytearray(self._field.view_buffer()[:self._reclen])

    def write(self, bytestr, can_break=True):
        """Write bytes to buffer."""
        try:
            TextFile.write(self, bytestr, can_break)
        except ValueError:
            # can't modify size of memoryview
            raise error.BASICError(error.FIELD_OVERFLOW)


class RandomFile(RawFile):
    """Random-access file on disk device."""

    def __init__(self, fhandle, number, field, reclen, locks):
        """Initialise random-access file."""
        # note that for random files, output_stream must be a seekable stream.
        RawFile.__init__(self, fhandle, b'D', b'R')
        self.reclen = reclen
        self._locks = locks
        self._number = number
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self._field_file = FieldFile(field, reclen)
        # position at start of file
        self._recpos = 0
        self._fhandle.seek(0)

    def close(self):
        """Close random-access file."""
        RawFile.close(self)
        self._locks.close_file(self._number)

    ##########################################################################
    # field text file operations

    def read(self, num):
        """Read a number of characters from the field buffer."""
        with self._field_file.use_mode(b'I'):
            return self._field_file.read(num)

    def input_entry(self, typechar, allow_past_end):
        """Read a number or string entry for INPUT """
        with self._field_file.use_mode(b'I'):
            # reading past end should give FIELD OVERFLOW, so suppress INPUT_PAST_END
            return self._field_file.input_entry(typechar, allow_past_end=True)

    def read_one(self):
        """Read a number of characters from the field buffer."""
        with self._field_file.use_mode(b'I'):
            return self._field_file.read_one()

    def read_line(self):
        """Read a line from the field buffer."""
        with self._field_file.use_mode(b'I'):
            return self._field_file.read_line()

    def write(self, s, can_break=True):
        """Write the string s to the field."""
        with self._field_file.use_mode(b'O'):
            self._field_file.write(s, can_break)

    def write_line(self, s=b''):
        """Write string and newline to the field buffer."""
        with self._field_file.use_mode(b'O'):
            self._field_file.write_line(s)

    @property
    def width(self):
        """Get the width setting on the field buffer."""
        return self._field_file.width

    def set_width(self, new_width):
        """Change the width setting on the field buffer."""
        self._field_file.set_width(new_width)

    @property
    def col(self):
        """Get the current column position on the field buffer."""
        return self._field_file.col

    ##########################################################################

    def eof(self):
        """Return whether we're past current end-of-file, for EOF."""
        return self._recpos * self.reclen > self.lof()

    def get(self, pos):
        """Read a record."""
        self._set_record_pos(pos)
        # exceptionally, GET is allowed if the file holding the lock is open for OUTPUT
        self._locks.try_record_access(self._number, self._recpos+1, self._recpos+1, b'R')
        if self.eof():
            contents = b'\0' * self.reclen
        else:
            with safe_io():
                contents = self._fhandle.read(self.reclen)
        # take contents and pad with NULL to required size
        self._field_file.set_buffer(contents)
        self._recpos += 1

    def put(self, pos):
        """Write a record."""
        self._set_record_pos(pos)
        self._locks.try_record_access(self._number, self._recpos+1, self._recpos+1, b'W')
        current_length = self.lof()
        with safe_io():
            if self._recpos > current_length:
                self._fhandle.seek(0, 2)
                numrecs = self._recpos - current_length
                self._fhandle.write(b'\0' * numrecs * self.reclen)
            self._fhandle.write(bytes(self._field_file.get_buffer()))
        self._recpos += 1

    def _set_record_pos(self, pos):
        """Move record pointer to new position."""
        if pos is not None:
            # first record is number 1
            with safe_io():
                self._fhandle.seek((pos-1) * self.reclen)
            self._recpos = pos - 1

    def loc(self):
        """Get number of record just past, for LOC."""
        return self._recpos

    def lof(self):
        """Get length of file, in bytes, for LOF."""
        with safe_io():
            current = self._fhandle.tell()
            self._fhandle.seek(0, 2)
            lof = self._fhandle.tell()
            self._fhandle.seek(current)
        return lof

    def lock(self, start, stop):
        """Lock range of records."""
        self._locks.acquire_record_lock(self._number, start, stop)

    def unlock(self, start, stop):
        """Unlock range of records."""
        self._locks.release_record_lock(self._number, start, stop)


###############################################################################
# Locks


class LockingParameters(object):
    """Record of a file's locking parameters."""

    def __init__(self, dos_name, mode, lock_type, access):
        """Build a record."""
        self.name = ntpath.basename(dos_name).upper()
        self.lock_set = set()
        self.lock_type = lock_type
        self.access = access
        self.mode = mode


class Locks(object):
    """Lock management."""

    def __init__(self):
        """Initialise locks."""
        # dict of LockingParameters objects, one for each open disk file, by file number
        self._locking_parameters = {}

    def list_open(self, name, exclude_number=None):
        """Retrieve a list of files open on the same disk device."""
        return [
            f for number, f in iteritems(self._locking_parameters)
            if f.name == ntpath.basename(name).upper() and number != exclude_number
        ]

    def open_file(self, name, number, mode, lock_type, access):
        """Register a disk file and try to acquire a file lock."""
        already_open = self.list_open(name)
        if mode in (b'O', b'A') and already_open:
            raise error.BASICError(error.FILE_ALREADY_OPEN)
        if not number:
            return
        for f in already_open:
            if (
                    # default mode: don't accept if SHARED/LOCK present
                    ((not lock_type) and f.lock_type) or
                    # LOCK READ WRITE: don't accept if already open
                    (lock_type == b'RW') or
                    # defined locking: don't accept if open in default mode
                    (lock_type and not f.lock_type) or
                    # LOCK READ or LOCK WRITE: accept based on ACCESS of open file
                    (
                        lock_type and lock_type != b'SHARED' and
                        f.access and set(iterchar(lock_type)) & set(iterchar(f.access))
                    ) or
                    (
                        f.lock_type and f.lock_type != b'SHARED' and
                        (
                            (access and set(iterchar(f.lock_type)) & set(iterchar(access))) or
                            # can't open with unspecified access if other is LOCK READ WRITE
                            (not access and set(iterchar(f.lock_type)) == {b'R', b'W'})
                        )
                    )
                ):
                raise error.BASICError(error.PERMISSION_DENIED)
        # setting this only after the lock acquisition makes the check asymmetric
        # which is what GW-BASIC does...
        # first file to open with unspecified access gets RW access
        # but second file gets checked for ''
        if lock_type and not access:
            access = b'RW'
        self._locking_parameters[number] = LockingParameters(name, mode, lock_type, access)

    def close_file(self, number):
        """Deregister disk file."""
        try:
            del self._locking_parameters[number]
        except KeyError:
            pass

    def try_access(self, number, access):
        """Attempt to access a file."""
        if not number:
            return
        this_file = self._locking_parameters[number]
        # access in violation of ACCESS declaration in OPEN: path/file access error
        if this_file.access and not (set(access) & set(this_file.access)):
            raise error.BASICError(error.PATH_FILE_ACCESS_ERROR)
        # access in violation of other's LOCK declation in OPEN: path/file access error
        others = self.list_open(this_file.name, number)
        for f in others:
            if (f.lock_type and f.lock_type != b'SHARED' and (set(f.lock_type) & set(access))):
                raise error.BASICError(error.PATH_FILE_ACCESS_ERROR)

    def try_record_access(self, number, start, stop, access=b'RW'):
        """Attempt to access a record."""
        self.try_access(number, access)
        self._try_record_lock(number, start, stop, allow_self=True, read_only=(access == b'R'))

    def _try_record_lock(self, number, start, stop, allow_self=True, read_only=False):
        """Attempt to access a record."""
        this_file = self._locking_parameters[number]
        other_locks = [
            f.lock_set for f in self.list_open(this_file.name, number if allow_self else None)
            # access parameter only exists to allow reading a record on locked OUTPUT file
            if not (f.mode in b'OA' and read_only)
        ]
        other_lock_set = set.union(*other_locks) if other_locks else set()
        # access in violation of other's LOCK#: permission denied
        # whole-file access sought
        if stop is None and start is None:
            if other_lock_set:
                raise error.BASICError(error.PERMISSION_DENIED)
        else:
            # range access sought
            for start_1, stop_1 in other_lock_set:
                if (
                        stop_1 is None and start_1 is None
                        or (start >= start_1 and start <= stop_1)
                        or (stop >= start_1 and stop <= stop_1)
                    ):
                    raise error.BASICError(error.PERMISSION_DENIED)

    def acquire_record_lock(self, number, start, stop):
        """Acquire a lock on a range of records."""
        self._try_record_lock(number, start, stop, allow_self=False)
        this_file = self._locking_parameters[number]
        this_file.lock_set.add((start, stop))

    def release_record_lock(self, number, start, stop):
        """Acquire a lock on a range of records."""
        this_file = self._locking_parameters[number]
        # permission denied if the exact record range wasn't given before
        try:
            this_file.lock_set.remove((start, stop))
        except KeyError:
            raise error.BASICError(error.PERMISSION_DENIED)
