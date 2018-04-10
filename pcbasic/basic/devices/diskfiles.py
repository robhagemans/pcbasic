"""
PC-BASIC - devices.diskfiles
Disk Files

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import string
from ..base.bytestream import ByteStream

from ..base import error
from . import devicebase


class BinaryFile(devicebase.RawFile):
    """File class for binary (B, P, M) files on disk device."""

    def __init__(self, fhandle, filetype, number, name, mode,
                       seg, offset, length, locks=None):
        """Initialise program file object and write header."""
        devicebase.RawFile.__init__(self, fhandle, filetype, mode)
        self.number = number
        # don't lock binary files
        self.lock = b''
        # we need the Locks object to register file as open
        self._locks = locks
        self.access = b'RW'
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


class _CRLFTextFileBase(devicebase.TextFileBase):
    """Text File with CRLF replacement."""

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
        """Write string or bytearray and newline to file."""
        self.write(str(s) + '\r\n')


class RandomFile(_CRLFTextFileBase):
    """Random-access file on disk device."""

    def __init__(self, output_stream, number, name,
                        access, lock, field, reclen=128, locks=None):
        """Initialise random-access file."""
        # all text-file operations on a RANDOM file (PRINT, WRITE, INPUT, ...)
        # actually work on the FIELD buffer; the file stream itself is not
        # touched until PUT or GET.
        self.reclen = reclen
        # replace with empty field if already exists
        self._field = field
        devicebase.TextFileBase.__init__(self, ByteStream(self._field.buffer), b'D', b'R')
        self.operating_mode = b'I'
        # note that for random files, output_stream must be a seekable stream.
        self.output_stream = output_stream
        self.lock_type = lock
        self.access = access
        self.lock_list = set()
        self._locks = locks
        self.number = number
        self.name = name
        # position at start of file
        self.recpos = 0
        self.output_stream.seek(0)

    def switch_mode(self, new_mode):
        """Switch to input or output mode"""
        if new_mode == b'I' and self.operating_mode == b'O':
            self.flush()
            self.next_char = self.fhandle.read(1)
            self.operating_mode = b'I'
        elif new_mode == b'O' and self.operating_mode == b'I':
            self.fhandle.seek(-1, 1)
            self.operating_mode = b'O'

    def _check_overflow(self):
        """Check for FIELD OVERFLOW."""
        write = self.operating_mode == b'O'
        # FIELD overflow happens if last byte in record has been read or written
        if self.fhandle.tell() > self.reclen + write - 1:
            raise error.BASICError(error.FIELD_OVERFLOW)

    def input_chars(self, num):
        """Read a number of characters from the field buffer."""
        # switch to reading mode and fix readahead buffer
        self.switch_mode('I')
        word = devicebase.TextFileBase.input_chars(self, num)
        self._check_overflow()
        return word

    def write(self, s, can_break=True):
        """Write the string s to the field, taking care of width settings."""
        # switch to writing mode and fix readahead buffer
        self.switch_mode(b'O')
        devicebase.TextFileBase.write(self, s, can_break)
        self._check_overflow()

    def close(self):
        """Close random-access file."""
        devicebase.TextFileBase.close(self)
        self.output_stream.close()
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

    def get(self, dummy=None):
        """Read a record."""
        if self.eof():
            contents = b'\0' * self.reclen
        else:
            contents = self.output_stream.read(self.reclen)
        # take contents and pad with NULL to required size
        self._field.buffer[:] = contents + b'\0' * (self.reclen - len(contents))
        # reset field text file loc
        self.fhandle.seek(0)
        self.recpos += 1

    def put(self, dummy=None):
        """Write a record."""
        current_length = self.lof()
        if self.recpos > current_length:
            self.output_stream.seek(0, 2)
            numrecs = self.recpos-current_length
            self.output_stream.write(b'\0' * numrecs * self.reclen)
        self.output_stream.write(self._field.buffer)
        self.recpos += 1

    def set_pos(self, newpos):
        """Set current record number."""
        # first record is newpos number 1
        self.output_stream.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        """Get number of record just past, for LOC."""
        return self.recpos

    def eof(self):
        """Return whether we're past currentg end-of-file, for EOF."""
        return self.recpos*self.reclen > self.lof()

    def lof(self):
        """Get length of file, in bytes, for LOF."""
        current = self.output_stream.tell()
        self.output_stream.seek(0, 2)
        lof = self.output_stream.tell()
        self.output_stream.seek(current)
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


class TextFile(_CRLFTextFileBase):
    """Text file on disk device."""

    def __init__(self, fhandle, filetype, number, name,
                 mode=b'A', access=b'RW', lock=b'',
                 codepage=None, universal=False, locks=None):
        """Initialise text file object."""
        devicebase.TextFileBase.__init__(self, fhandle, filetype, mode, b'')
        self.lock_list = set()
        self.lock_type = lock
        self._locks = locks
        self.access = access
        self.number = number
        self.name = name
        # if a codepage is supplied, text is converted to utf8
        # otherwise, it is read/written as raw bytes
        self._codepage = codepage
        self._universal = universal
        self._spaces = []
        if self.mode == b'A':
            self.fhandle.seek(0, 2)
        elif self.mode == b'O' and self._codepage is not None:
            # start UTF-8 files with BOM as many Windows readers expect this
            self.fhandle.write(b'\xef\xbb\xbf')

    def close(self):
        """Close text file."""
        if self.mode in (b'O', b'A') and self._codepage is None:
            # write EOF char
            self.fhandle.write(b'\x1a')
        devicebase.TextFileBase.close(self)
        if self._locks is not None:
            self._locks.release(self.number)
            self._locks.close_file(self.number)

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

    def write_line(self, s=''):
        """Write to file in normal or UTF-8 mode."""
        if self._codepage is not None:
            s = (self._codepage.str_to_unicode(s).encode(b'utf-8', b'replace'))
        devicebase.TextFileBase.write(self, s + '\r\n')

    def write(self, s, can_break=True):
        """Write to file in normal or UTF-8 mode."""
        if self._codepage is not None:
            s = (self._codepage.str_to_unicode(s).encode(b'utf-8', b'replace'))
        devicebase.TextFileBase.write(self, s, can_break)

    def _read_line_universal(self):
        """Read line from ascii program file with universal newlines."""
        # keep reading until any kind of line break
        # is followed by a line starting with a number
        s, c = self._spaces, b''
        self._spaces = []
        while len(s) < 255:
            # read converts CRLF to CR
            c = self.read(1)
            if not c:
                break
            elif c in (b'\r', b'\n'):
                # break on CR, CRLF, LF if next line starts with number or eof
                while self.next_char in (b' ', b'\0'):
                    c = self.read(1)
                    self._spaces.append(c)
                if self.next_char in string.digits or self.next_char in (b'', b'\x1a'):
                    break
                else:
                    s += [b'\n'] + self._spaces
                    self._spaces = []
            else:
                s.append(c)
        if not c and not s:
            return None, c
        return ''.join(s), c

    def read_line(self):
        """Read line from text file."""
        if not self._universal:
            s, cr = _CRLFTextFileBase.read_line(self)
        else:
            s, cr = self._read_line_universal()
        if self._codepage is not None and s is not None:
            s = self._codepage.str_from_unicode(s.decode(b'utf-8', errors='replace'))
        return s, cr

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
