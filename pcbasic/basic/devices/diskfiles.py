"""
PC-BASIC - devices.diskfiles
Disk Files

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import string
from contextlib import contextmanager

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

    def __init__(self, fhandle, filetype, number, mode, seg, offset, length, locks=None):
        """Initialise program file object and write header."""
        RawFile.__init__(self, fhandle, filetype, mode)
        # don't lock binary files
        # we need the Locks object to register file as open
        self._locks = locks
        self.number = number
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
        if self._locks is not None:
            # no locking for binary files, but we do need to register it closed
            self._locks.close_file(self.number)


class TextFile(TextFileBase, InputMixin):
    """Text file on disk device."""

    def __init__(self, fhandle, filetype, number, mode=b'A', locks=None, universal=False):
        """Initialise text file object."""
        TextFileBase.__init__(self, fhandle, filetype, mode)
        self._locks = locks
        self.number = number
        self._universal = universal
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
        if self._locks is not None:
            self._locks.close_file(self.number)

    def read(self, n):
        """Read num characters."""
        if self._locks:
            self._locks.try_access(self, b'R')
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
        # universal newlines: report \n as line break
        if (self._universal and c == b'\n'):
            c = b'\r'
        return c

    def read_line(self):
        """Read line from text file, break on CR or CRLF (not LF, unless universal newlines)."""
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
        if self._locks:
            self._locks.try_access(self, b'W')
        TextFileBase.write(self, s, can_break)

    def write_line(self, s=''):
        """Write string and newline to file."""
        self.write(s + b'\r\n')

    def loc(self):
        """Get file pointer (LOC)."""
        with safe_io():
            if self.mode == b'I':
                tell = self._fhandle.tell() - len(self._readahead)
                return max(1, (127+tell) / 128)
            return self._fhandle.tell() / 128

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
        if self._locks:
            self._locks.acquire_record_lock(self, None, None)

    def unlock(self, start, stop):
        """Unlock the file."""
        if self._locks:
            self._locks.release_record_lock(self, None, None)


class FieldFile(TextFile):
    """Text file on FIELD."""

    def __init__(self, field, reclen):
        """Initialise text file object."""
        TextFile.__init__(self, ByteStream(field.buffer), b'D', None, b'I')
        self._reclen = reclen

    def reset(self):
        """Reset file to start of field."""
        self._fhandle.seek(0)

    @contextmanager
    def use_mode(self, mode):
        """Use in input or output mode."""
        self._switch_mode(mode)
        yield
        self._check_overflow()

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


class RandomFile(RawFile):
    """Random-access file on disk device."""

    def __init__(self, fhandle, number, field, reclen=128, locks=None):
        """Initialise random-access file."""
        # note that for random files, output_stream must be a seekable stream.
        RawFile.__init__(self, fhandle, b'D', b'R')
        self.reclen = reclen
        self._locks = locks
        self.number = number
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self._field = field
        self._field_file = FieldFile(field, reclen)
        # position at start of file
        self._recpos = 0
        self._fhandle.seek(0)

    def close(self):
        """Close random-access file."""
        RawFile.close(self)
        if self._locks is not None:
            self._locks.close_file(self.number)

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

    def get(self, dummy=None):
        """Read a record."""
        if self._locks:
            self._locks.try_access(self, b'R')
            # exceptionally, GET is allowed if the file holding the lock is open for OUTPUT
            self._locks.try_record_lock(self, self._recpos+1, self._recpos+1, read_only=True)
        if self.eof():
            contents = b'\0' * self.reclen
        else:
            with safe_io():
                contents = self._fhandle.read(self.reclen)
        # take contents and pad with NULL to required size
        self._field.buffer[:] = contents + b'\0' * (self.reclen - len(contents))
        # reset field text file loc
        self._field_file.reset()
        self._recpos += 1

    def put(self, dummy=None):
        """Write a record."""
        if self._locks:
            self._locks.try_access(self, b'W')
            self._locks.try_record_lock(self, self._recpos+1, self._recpos+1)
        current_length = self.lof()
        with safe_io():
            if self._recpos > current_length:
                self._fhandle.seek(0, 2)
                numrecs = self._recpos - current_length
                self._fhandle.write(b'\0' * numrecs * self.reclen)
            self._fhandle.write(self._field.buffer)
        self._recpos += 1

    def set_pos(self, newpos):
        """Set current record number."""
        # first record is newpos number 1
        with safe_io():
            self._fhandle.seek((newpos-1) * self.reclen)
        self._recpos = newpos - 1

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
        if self._locks:
            self._locks.acquire_record_lock(self, start, stop)

    def unlock(self, start, stop):
        """Unlock range of records."""
        if self._locks:
            self._locks.release_record_lock(self, start, stop)
