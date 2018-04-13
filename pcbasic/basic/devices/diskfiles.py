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
from . import devicebase


class BinaryFile(devicebase.RawFile):
    """File class for binary (B, P, M) files on disk device."""

    def __init__(self, fhandle, filetype, number, name, mode,
                       seg, offset, length, locks=None):
        """Initialise program file object and write header."""
        devicebase.RawFile.__init__(self, fhandle, filetype, mode)
        # don't lock binary files
        # we need the Locks object to register file as open
        self.number = number
        self.lock = b''
        self.access = b'RW'
        self._locks = locks
        # binary file parameters
        self.seg, self.offset, self.length = 0, 0, 0
        if self.mode == b'O':
            self.write(devicebase.TYPE_TO_MAGIC[filetype])
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
                    self.seg, self.offset, self.length = struct.unpack(b'<HHH', header)
                else:
                    # truncated header
                    raise error.BASICError(error.BAD_FILE_MODE)

    def close(self):
        """Write EOF and close program file."""
        if self.mode == b'O':
            self.write(b'\x1a')
        devicebase.RawFile.close(self)
        if self._locks is not None:
            # no locking for binary files, but we do need to register it closed
            self._locks.close_file(self.number)


class TextFile(devicebase.TextFileBase):
    """Text file on disk device."""

    def __init__(
            self, fhandle, filetype, number, name, mode=b'A', access=b'RW', lock=b'', locks=None):
        """Initialise text file object."""
        devicebase.TextFileBase.__init__(self, fhandle, filetype, mode, b'')
        # locking members
        self.number = number
        self.name = name
        self.lock_list = set()
        self.lock_type = lock
        self.access = access
        self._locks = locks
        # in append mode, we need to start at end of file
        if self.mode == b'A':
            self.fhandle.seek(0, 2)

    def close(self):
        """Close text file."""
        if self.mode in (b'O', b'A'):
            # write EOF char
            self.fhandle.write(b'\x1a')
        devicebase.TextFileBase.close(self)
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

    def read(self, num=-1):
        """Read num characters, replacing CR LF with CR."""
        s = []
        while len(s) < num:
            c = self.input_chars(1)
            if not c:
                break
            s.append(c)
            # report CRLF as CR
            # but LFCR, LFCRLF, LFCRLFCR etc pass unmodified
            if (c == '\r' and self.last != '\n') and self.next_char == '\n':
                last, char = self.last, self.char
                self.input_chars(1)
                self.last, self.char = last, char
        return ''.join(s)

    def read_line(self):
        """Read line from text file, break on CR or CRLF (not LF)."""
        s = []
        while True:
            c = self.read(1)
            if not c or (c == '\r' and self.last != '\n'):
                # break on CR, CRLF but allow LF, LFCR to pass
                break
            s.append(c)
            if len(s) == 255:
                c = '\r' if self.next_char == '\r' else None
                break
        if not c and not s:
            return None, c
        return ''.join(s), c

    def write_line(self, s=''):
        """Write string and newline to file."""
        self.write(s + '\r\n')

    def loc(self):
        """Get file pointer LOC """
        # for LOC(i)
        if self.mode == b'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        """Get length of file LOF."""
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

    def lock(self, start, stop):
        """Lock the file."""
        if set.union(*(f.lock_list for f in self._locks.list(self.name))):
            raise error.BASICError(error.PERMISSION_DENIED)
        self.lock_list.add(True)

    def unlock(self, start, stop):
        """Unlock the file."""
        try:
            self.lock_list.remove(True)
        except KeyError:
            raise error.BASICError(error.PERMISSION_DENIED)


class FieldFile(TextFile):
    """Text file on FIELD."""

    def __init__(self, field, reclen):
        """Initialise text file object."""
        TextFile.__init__(self, ByteStream(field.buffer), b'D', -1, b'<field>', b'I')
        self._reclen = reclen

    def reset(self):
        """Reset fiel to start of field."""
        self.fhandle.seek(0)

    @contextmanager
    def use_mode(self, mode):
        """Use in input or output mode."""
        self._switch_mode(mode)
        yield
        self._check_overflow()

    def _switch_mode(self, new_mode):
        """Switch to input or output mode and fix readahaed buffer."""
        if new_mode == b'I' and self.mode == b'O':
            self.flush()
            self.next_char = self.fhandle.read(1)
            self.mode = b'I'
        elif new_mode == b'O' and self.mode == b'I':
            self.fhandle.seek(-1, 1)
            self.mode = b'O'

    def _check_overflow(self):
        """Check for FIELD OVERFLOW."""
        write = self.mode == b'O'
        # FIELD overflow happens if last byte in record has been read or written
        if self.fhandle.tell() > self._reclen + write - 1:
            raise error.BASICError(error.FIELD_OVERFLOW)


class RandomFile(devicebase.RawFile):
    """Random-access file on disk device."""

    def __init__(self, fhandle, number, name, access, lock, field, reclen=128, locks=None):
        """Initialise random-access file."""
        # note that for random files, output_stream must be a seekable stream.
        devicebase.RawFile.__init__(self, fhandle, b'D', b'R')
        self.reclen = reclen
        # locking members (used by Locks.acquire)
        self.number = number
        self.name = name
        self.lock_type = lock
        self.lock_list = set()
        self.access = access
        self._locks = locks
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self._field = field
        self._field_file = FieldFile(field, reclen)
        # position at start of file
        self._recpos = 0
        self.fhandle.seek(0)

    def close(self):
        """Close random-access file."""
        devicebase.RawFile.close(self)
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

    ##########################################################################
    # field text file operations

    def input_chars(self, num):
        """Read a number of characters from the field buffer."""
        with self._field_file.use_mode(b'I'):
            return self._field_file.input_chars(num)

    def input_entry(self, typechar, allow_past_end):
        """Read a number or string entry for INPUT """
        with self._field_file.use_mode(b'I'):
            return self._field_file.input_entry(typechar, allow_past_end)

    # is this needed?
    def read(self, n=-1):
        """Read a number of characters from the field buffer."""
        with self._field_file.use_mode(b'I'):
            return self._field_file.read(n)

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

    ##########################################################################

    def eof(self):
        """Return whether we're past current end-of-file, for EOF."""
        return self._recpos * self.reclen > self.lof()

    def get(self, dummy=None):
        """Read a record."""
        if self.eof():
            contents = b'\0' * self.reclen
        else:
            contents = self.fhandle.read(self.reclen)
        # take contents and pad with NULL to required size
        self._field.buffer[:] = contents + b'\0' * (self.reclen - len(contents))
        # reset field text file loc
        self._field_file.reset()
        self._recpos += 1

    def put(self, dummy=None):
        """Write a record."""
        current_length = self.lof()
        if self._recpos > current_length:
            self.fhandle.seek(0, 2)
            numrecs = self._recpos-current_length
            self.fhandle.write(b'\0' * numrecs * self.reclen)
        self.fhandle.write(self._field.buffer)
        self._recpos += 1

    def set_pos(self, newpos):
        """Set current record number."""
        # first record is newpos number 1
        self.fhandle.seek((newpos-1) * self.reclen)
        self._recpos = newpos - 1

    def loc(self):
        """Get number of record just past, for LOC."""
        return self._recpos

    def lof(self):
        """Get length of file, in bytes, for LOF."""
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

    def lock(self, start, stop):
        """Lock range of records."""
        other_lock_list = set.union(*(f.lock_list for f in self._locks.list(self.name)))
        for start_1, stop_1 in other_lock_list:
            if (stop_1 is None and start_1 is None
                        or (start >= start_1 and start <= stop_1)
                        or (stop >= start_1 and stop <= stop_1)):
                raise error.BASICError(error.PERMISSION_DENIED)
        self.lock_list.add((start, stop))

    def unlock(self, start, stop):
        """Unlock range of records."""
        # permission denied if the exact record range wasn't given before
        try:
            self.lock_list.remove((start, stop))
        except KeyError:
            raise error.BASICError(error.PERMISSION_DENIED)
