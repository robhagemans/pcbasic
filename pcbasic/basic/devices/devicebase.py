"""
PC-BASIC - devicebase.py
Devices, Files and I/O operations

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import os
import struct
import logging
from contextlib import contextmanager

from ...compat import iterchar
from ..base import error
from ..base.eascii import as_bytes as ea
from .. import values

def nullstream():
    return open(os.devnull, 'r+b')


# magic chars used by some devices to indicate file type
TYPE_TO_MAGIC = {b'B': b'\xFF', b'P': b'\xFE', b'M': b'\xFD'}
MAGIC_TO_TYPE = {b'\xFF': b'B', b'\xFE': b'P', b'\xFD': b'M'}



############################################################################
# Device classes
#
#  Some devices have a master file, where newly opened files inherit
#  width (and other?) settings from this file
#  For example, WIDTH "SCRN:", 40 works directly on the console,
#  whereas OPEN "SCRN:" FOR OUTPUT AS 1: WIDTH #1,23 works on the wrapper file
#  but does ot affect other files on SCRN: nor the console itself.
#  Likewise, WIDTH "LPT1:" works on LLIST etc and on lpt1 for the next time it's opened.


############################################################################

def parse_protocol_string(arg):
    """Retrieve protocol and options from argument."""
    if not arg:
        return None, u''
    argsplit = arg.split(u':', 1)
    if len(argsplit) == 1:
        addr, val = None, argsplit[0]
    else:
        addr, val = argsplit[0].upper(), u''.join(argsplit[1:])
    return addr, val


class NullDevice(object):
    """Null device (NUL) """

    def __init__(self):
        """Set up device."""

    def open(
            self, number, param, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        ):
        """Open a file on the device."""
        return TextFileBase(nullstream(), filetype, mode)

    def close(self):
        """Close the device."""

    def available(self):
        """Device is available."""
        return True


class Device(object):
    """Device interface for master-file devices."""

    allowed_modes = b''

    def __init__(self):
        """Set up device."""
        self.device_file = None

    def open(
            self, number, param, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        ):
        """Open a file on the device."""
        if not self.device_file:
            raise error.BASICError(error.DEVICE_UNAVAILABLE)
        if mode not in self.allowed_modes:
            raise error.BASICError(error.BAD_FILE_MODE)
        new_file = self.device_file.open_clone(filetype, mode, reclen)
        return new_file

    def close(self):
        """Close the device."""
        if self.device_file:
            self.device_file.close()

    def available(self):
        """Device is available."""
        return True


class SCRNDevice(Device):
    """Screen device (SCRN:) """

    allowed_modes = b'OR'

    def __init__(self, display, console):
        """Initialise screen device."""
        # open a master file on the screen
        Device.__init__(self)
        self.device_file = SCRNFile(display, console)

    def open(
            self, number, param, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        ):
        """Open a file on the device."""
        new_file = Device.open(
            self, number, param, filetype, mode, access, lock,
            reclen, seg, offset, length, field
        )
        # SAVE "SCRN:" includes a magic byte
        new_file.write(TYPE_TO_MAGIC.get(filetype, b''))
        return new_file


class KYBDDevice(Device):
    """Keyboard device (KYBD:) """

    allowed_modes = b'IR'

    def __init__(self, keyboard, display):
        """Initialise keyboard device."""
        # open a master file on the keyboard
        Device.__init__(self)
        self.device_file = KYBDFile(keyboard, display)


#################################################################################
# file classes

# file interface:
#   __enter__(self)
#   __exit__(self, exc_type, exc_value, traceback)
#   close(self)
#   read(self, num=-1)
#   write(self, s)
#   filetype
#   mode


@contextmanager
def safe_io(err=error.DEVICE_IO_ERROR):
    """Catch and translate I/O errors."""
    try:
        yield
    except EnvironmentError as e:
        logging.warning('I/O error on stream access: %s', e)
        raise error.BASICError(err)


class RawFile(object):
    """File class for raw access to underlying stream."""

    def __init__(self, fhandle, filetype, mode):
        """Setup the basic properties of the file."""
        self._fhandle = fhandle
        self.filetype = filetype
        self.mode = mode.upper()

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context guard."""
        self.close()

    def close(self):
        """Close the file."""
        with safe_io():
            self._fhandle.close()

    def read(self, num=-1):
        """Read num chars. If num==-1, read all available."""
        with safe_io():
            return self._fhandle.read(num)

    def write(self, s):
        """Write string to file."""
        with safe_io():
            self._fhandle.write(s)

    def flush(self):
        """Stub for compatibility with file-like objects."""


#################################################################################
# Text file base

# text interface: file interface +
#   col
#   width
#   set_width(self, new_width=255)
#
#   read_line(self)
#   input_entry(self, typechar, allow_past_end)
#   write_line(self, s=b'')
#   eof(self)
#   lof(self)
#   loc(self)
#
#   internal use: read_one(), peek()
#   internal use: soft_sep

# TAB x09 is not whitespace for input#. NUL \x00 and LF \x0a are.
INPUT_WHITESPACE = b' \0\n'


class DeviceSettings(object):
    """Device-level width and column settings."""

    def __init__(self):
        """Setup the basic properties of the file."""
        self.width = 255
        self.col = 1

    def set_width(self, width):
        """Set file width."""
        self.width = width

    def close(self):
        """Close dummy device file."""


class TextFileBase(RawFile):
    """Base for text files on disk, KYBD file, field buffer."""

    # for INPUT# - numbers read from file can be separated by spaces too
    soft_sep = b' '

    def __init__(self, fhandle, filetype, mode):
        """Setup the basic properties of the file."""
        RawFile.__init__(self, fhandle, filetype, mode)
        # width=255 means line wrap
        self.width = 255
        self.col = 1
        # allow first char to be specified (e.g. already read)
        self._readahead = []
        self._current, self._previous = b'', b''

    # readable files

    def peek(self, num):
        """Return next num characters to be read; never returns more, fewer only at EOF."""
        to_read = num - len(self._readahead)
        if to_read > 0:
            with safe_io():
                self._readahead.extend(iterchar(self._fhandle.read(to_read)))
        return b''.join(self._readahead[:num])

    def read(self, num):
        """Read num characters."""
        output = self.peek(num)
        # check for \x1A - EOF char will actually stop further reading
        # (that's true in disk text files but not on COM devices)
        if b'\x1A' in output:
            output = output[:output.index(b'\x1A')]
        # drop read chars from buffer
        self._readahead = self._readahead[len(output):]
        if len(output) <= 1:
            self._previous = self._current
        else:
            self._previous = output[-2:]
        self._current = output[-1:]
        return output

    def read_one(self):
        """Read one character, converting device line ending to b'\r', EOF to b''."""
        # for use by input_entry() and read_line() only
        return self.read(1)

    def read_line(self):
        """\
            Read a single line until line break or 255 characters.
            Returns: (line, separator character)
            Separator character:
                b'\r' for device-standard line break (CR or CR LF)
                b'' at end of file
                None if line ended due to 255-char length limit
        """
        out = []
        while True:
            c = self.read_one()
            # don't check for CRLF on KYBD:, CAS:, etc.
            if not c or c == b'\r':
                break
            out.append(c)
            if len(out) == 255:
                c = b'\r' if self.peek(1) == b'\r' else None
                break
        return b''.join(out), c

    # writeable files

    def write(self, s, can_break=True):
        """Write the string s to the file, taking care of width settings."""
        assert isinstance(s, bytes)
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in iterchar(s):
            if c in (b'\r', b'\n'):
                newline = True
                break
            if c >= b' ':
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if (
                can_break and self.width != 255 and self.col != 1 and
                self.col-1 + s_width > self.width and not newline
            ):
            self.write_line()
            self.col = 1
        for c in iterchar(s):
            # don't replace CR or LF with CRLF when writing to files
            if c == b'\r':
                self._fhandle.write(c)
                self.col = 1
            else:
                self._fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                if c >= b' ':
                    self.col += 1
                    # col-1 is a byte that wraps
                    if self.col == 257:
                        self.col = 1

    def write_line(self, s=b''):
        """Write string and follow with device-standard line break."""
        self.write(s + b'\r')

    # available for read & write (but not always useful)

    def set_width(self, new_width=255):
        """Set file width."""
        self.width = new_width

    def eof(self):
        """Check for end of file EOF."""
        # for EOF(i)
        if self.mode in (b'A', b'O'):
            return False
        return self.peek(1) in (b'', b'\x1a')


class InputMixin(object):
    """Support for INPUT#."""

    def _skip_whitespace(self, whitespace):
        """Skip spaces and line feeds and NUL; return last whitespace char """
        c = b''
        while True:
            next_char = self.peek(1)
            if not next_char or next_char not in whitespace:
                break
            # drop whitespace char
            c = self.read_one()
            # LF causes following CR to be dropped
            if c == b'\n' and self.peek(1) == b'\r':
                # LFCR: drop the CR, report as LF
                # on disk devices, this means LFCRLF is reported as LF
                self.read_one()
        return c

    def input_entry(self, typechar, allow_past_end, suppress_unquoted_linefeed=True):
        """Read a number or string entry for INPUT """
        word, blanks = b'', b''
        # fix readahead buffer (self.next_char)
        last = self._skip_whitespace(INPUT_WHITESPACE)
        # read first non-whitespace char
        c = self.read_one()
        # LF escapes quotes
        # may be true if last == '', hence "in ('\n', '\0')" not "in '\n0'"
        quoted = (c == b'"' and typechar == values.STR and last not in (b'\n', b'\0'))
        if quoted:
            c = self.read_one()
        # LF escapes end of file, return empty string
        if not c and not allow_past_end and last not in (b'\n', b'\0'):
            raise error.BASICError(error.INPUT_PAST_END)
        # we read the ending char before breaking the loop
        # this may raise FIELD OVERFLOW
        while c and not (
                (typechar != values.STR and c in self.soft_sep) or
                (c in b',\r' and not quoted)
            ):
            if c == b'"' and quoted:
                # whitespace after quote will be skipped below
                break
            elif suppress_unquoted_linefeed and (c == b'\n' and not quoted):
                # LF, LFCR are dropped entirely
                c = self.read_one()
                if c == b'\r':
                    c = self.read_one()
                continue
            elif c == b'\0':
                # NUL is dropped even within quotes
                pass
            elif c in INPUT_WHITESPACE and not quoted:
                # ignore whitespace in numbers, except soft separators
                # include internal whitespace in strings
                if typechar == values.STR:
                    blanks += c
            else:
                word += blanks + c
                blanks = b''
            if len(word) + len(blanks) >= 255:
                break
            if not quoted:
                c = self.read_one()
            else:
                # no CRLF replacement inside quotes.
                c = self.read(1)
        # if separator was a whitespace char or closing quote
        # skip trailing whitespace before any comma or hard separator
        if c and c in INPUT_WHITESPACE or (quoted and c == b'"'):
            self._skip_whitespace(b' ')
            if self.peek(1) in b',\r':
                c = self.read_one()
        # file position is at one past the separator char
        return word, c


#################################################################################
# Console INPUT


class InputTextFile(TextFileBase, InputMixin):
    """Handle INPUT from console."""

    # spaces do not separate numbers on console INPUT
    soft_sep = b''

    def __init__(self, line):
        """Initialise InputStream."""
        TextFileBase.__init__(self, io.BytesIO(line), b'D', b'I')


#################################################################################
# Console files


class RealTimeInputMixin(object):
    """Support for INPUT# on non-seekable KYBD and COM files."""

    def input_entry(self, typechar, allow_past_end):
        """Read a number or string entry from KYBD: or COMn: for INPUT#."""
        word, blanks = b'', b''
        c = self.read_one()
        # LF escapes quotes
        quoted = (c == b'"' and typechar == values.STR)
        if quoted:
            c = self.read_one()
        # LF escapes end of file, return empty string
        if not c and not allow_past_end:
            raise error.BASICError(error.INPUT_PAST_END)
        # on reading from a KYBD: file, control char replacement takes place
        # which means we need to use read_one() not read()
        parsing_trail = False
        while c and not (c in b',\r' and not quoted):
            if c == b'"' and quoted:
                parsing_trail = True
            elif c == b'\n' and not quoted:
                # LF, LFCR are dropped entirely
                c = self.read_one()
                if c == b'\r':
                    c = self.read_one()
                continue
            elif c == b'\0':
                # NUL is dropped even within quotes
                pass
            elif c in INPUT_WHITESPACE and not quoted:
                # ignore whitespace in numbers, except soft separators
                # include internal whitespace in strings
                if typechar == values.STR:
                    blanks += c
            else:
                word += blanks + c
                blanks = b''
            if len(word) + len(blanks) >= 255:
                break
            # there should be KYBD: control char replacement here even if quoted
            save_prev = self._previous
            c = self.read_one()
            if parsing_trail:
                if c not in INPUT_WHITESPACE:
                    # un-read the character if it's not a separator
                    if c not in (b',', b'\r'):
                        self._readahead.insert(0, c)
                        self._current, self._previous = self._previous, save_prev
                    break
            parsing_trail = parsing_trail or (typechar != values.STR and c == b' ')
        # file position is at one past the separator char
        return word, c


###############################################################################


# replace some eascii codes with control characters
KYBD_REPLACE = {
    ea.HOME: b'\xFF\x0B', ea.UP: b'\xFF\x1E', ea.PAGEUP: b'\xFE',
    ea.LEFT: b'\xFF\x1D', ea.RIGHT: b'\xFF\x1C', ea.END: b'\xFF\x0E',
    ea.DOWN: b'\xFF\x1F', ea.PAGEDOWN: b'\xFE',
    ea.DELETE: b'\xFF\x7F', ea.INSERT: b'\xFF\x12',
    ea.F1: b'', ea.F2: b'', ea.F3: b'', ea.F4: b'', ea.F5: b'',
    ea.F6: b'', ea.F7: b'', ea.F8: b'', ea.F9: b'', ea.F10: b'',
}

class KYBDFile(TextFileBase, RealTimeInputMixin):
    """KYBD device: keyboard."""

    col = 0

    def __init__(self, keyboard, display):
        """Initialise keyboard file."""
        TextFileBase.__init__(self, nullstream(), filetype=b'D', mode=b'I')
        # buffer for the separator character that broke the last INPUT# field
        # to be attached to the next
        self._keyboard = keyboard
        # screen needed for width settings on KYBD: master file
        self._display = display
        # on master-file devices, this is the master file.
        self._is_master = True

    def open_clone(self, filetype, mode, reclen=128):
        """Clone device file."""
        inst = KYBDFile(self._keyboard, self._display)
        inst.mode = mode
        inst.reclen = reclen
        inst.filetype = filetype
        inst._is_master = False
        return inst

    def peek(self, num):
        """Return only readahead buffer, no blocking peek."""
        return b''.join(self._readahead[:num])

    def read(self, num):
        """Read a number of characters (INPUT$)."""
        # take at most num chars out of readahead buffer (holds just one on KYBD but anyway)
        chars, self._readahead = b''.join(self._readahead[:num]), self._readahead[num:]
        # fill up the rest with actual keyboard reads
        while len(chars) < num:
            chars += b''.join(
                # note that INPUT$ on KYBD files replaces some eascii with NUL
                b'\0' if c in KYBD_REPLACE else c if len(c) == 1 else b''
                for c in self._keyboard.read_bytes_kybd_file(num-len(chars))
            )
        return chars

    def read_one(self):
        """Read a character with line ending replacement (INPUT and LINE INPUT)."""
        # take char out of readahead buffer, if present; blocking keyboard read otherwise
        if self._readahead:
            chars, self._readahead = b''.join(self._readahead[:1]), self._readahead[1:]
            return chars
        else:
            # note that we need string length, not list length
            # as read_bytes_kybd_file can return multi-byte eascii codes
            # blocking read
            return b''.join(
                # INPUT and LINE INPUT on KYBD files replace some eascii with control sequences
                KYBD_REPLACE.get(c, c)
                for c in self._keyboard.read_bytes_kybd_file(1)
            )

    # read_line: inherited from TextFileBase, this calls peek()

    def lof(self):
        """LOF for KYBD: is 1."""
        return 1

    def loc(self):
        """LOC for KYBD: is 0."""
        return 0

    def eof(self):
        """KYBD only EOF if ^Z is read."""
        if self.mode in (b'A', b'O'):
            return False
        # blocking peek
        return (self._keyboard.peek_byte_kybd_file() == b'\x1A')

    def set_width(self, new_width=255):
        """Setting width on KYBD device (not files) changes screen width."""
        if self._is_master:
            self._display.set_width(new_width)


###############################################################################

class SCRNFile(RawFile):
    """SCRN: file, allows writing to the screen as a text file."""

    def __init__(self, display, console):
        """Initialise screen file."""
        RawFile.__init__(self, nullstream(), filetype=b'D', mode=b'O')
        # need display object as WIDTH can change graphics mode
        self._display = display
        # screen member is public, needed by print_
        self.console = console
        self._width = self.console.width
        self._col = self.console.current_col
        # on master-file devices, this is the master file.
        self._is_master = True

    def open_clone(self, filetype, mode, reclen=128):
        """Clone screen file."""
        inst = SCRNFile(self._display, self.console)
        inst.mode = mode
        inst.reclen = reclen
        inst.filetype = filetype
        inst._is_master = False
        return inst

    def write(self, s, can_break=True):
        """Write string s to SCRN: """
        if not s:
            return
        # writes to SCRN files should *not* be echoed
        do_echo = self._is_master
        self._col = self.console.current_col
        # take column 80+overflow into account
        if self.console.overflow:
            self._col += 1
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in iterchar(s):
            if c in (b'\r', b'\n'):
                newline = True
                break
            if c == b'\b':
                # for lpt1 and files, nonprinting chars are not counted in LPOS;
                # but chr$(8) will take a byte out of the buffer
                s_width -= 1
            elif c >= b' ':
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if can_break and (self.width != 255 and self.console.current_row != self.console.height
                and self.col != 1 and self.col-1 + s_width > self.width and not newline):
            self.console.write_line(do_echo=do_echo)
            self._col = 1
        cwidth = self.console.width
        output = []
        for c in iterchar(s):
            if self.width <= cwidth and self.col > self.width:
                self.console.write_line(b''.join(output), do_echo=do_echo)
                output = []
                self._col = 1
            if self.col <= cwidth or self.width <= cwidth:
                output.append(c)
            if c in (b'\n', b'\r'):
                self.console.write(b''.join(output), do_echo=do_echo)
                output = []
                self._col = 1
            else:
                self._col += 1
        self.console.write(b''.join(output), do_echo=do_echo)

    def write_line(self, inp=b''):
        """Write a string to the screen and follow by CR."""
        self.write(inp)
        self.console.write_line(do_echo=self._is_master)

    @property
    def col(self):
        """Return current (virtual) column position."""
        if self._is_master:
            return self.console.current_col
        else:
            return self._col

    @property
    def width(self):
        """Return (virtual) screen width."""
        if self._is_master:
            return self._display.mode.width
        else:
            return self._width

    def set_width(self, new_width=255):
        """Set (virtual) screen width."""
        if self._is_master:
            self._display.set_width(new_width)
        else:
            self._width = new_width

    def lof(self):
        """LOF: bad file mode."""
        raise error.BASICError(error.BAD_FILE_MODE)

    def loc(self):
        """LOC: bad file mode."""
        raise error.BASICError(error.BAD_FILE_MODE)

    def eof(self):
        """EOF: bad file mode."""
        raise error.BASICError(error.BAD_FILE_MODE)
