"""
PC-BASIC - devicebase.py
Devices, Files and I/O operations

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import io
import os
import struct

from ..base import error
from ..base.eascii import as_bytes as ea
from .. import values

def nullstream():
    return open(os.devnull, b'r+')


# magic chars used by some devices to indicate file type
TYPE_TO_MAGIC = { b'B': b'\xFF', b'P': b'\xFE', b'M': b'\xFD' }
MAGIC_TO_TYPE = { b'\xFF': b'B', b'\xFE': b'P', b'\xFD': b'M' }



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
        return None, b''
    argsplit = arg.split(':', 1)
    if len(argsplit) == 1:
        addr, val = None, argsplit[0]
    else:
        addr, val = argsplit[0].upper(), ''.join(argsplit[1:])
    return addr, val


class NullDevice(object):
    """Null device (NUL) """

    def __init__(self):
        """Set up device."""

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length, field):
        """Open a file on the device."""
        return TextFileBase(nullstream(), filetype, mode)

    def close(self):
        """Close the device."""

    def available(self):
        """Device is available."""
        return True


class Device(object):
    """Device interface for master-file devices."""

    allowed_modes = ''

    def __init__(self):
        """Set up device."""
        self.device_file = None

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length, field):
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

    allowed_modes = 'OR'

    def __init__(self, display):
        """Initialise screen device."""
        # open a master file on the screen
        Device.__init__(self)
        self.device_file = SCRNFile(display)


class KYBDDevice(Device):
    """Keyboard device (KYBD:) """

    allowed_modes = 'IR'

    def __init__(self, keyboard, display):
        """Initialise keyboard device."""
        # open a master file on the keyboard
        Device.__init__(self)
        self.device_file = KYBDFile(keyboard, display)


#################################################################################
# file classes

# file interface:
#    __enter__(self)
#   __exit__(self, exc_type, exc_value, traceback)
#   close(self)
#   switch_mode(self, new_mode)
#   input_chars(self, num)
#   read_raw(self, num=-1)
#   read(self, num=-1)
#   write(self, s)
#   flush(self)


class DeviceSettings(object):
    """Device-level settings, not a file as such."""

    def __init__(self):
        """Setup the basic properties of the file."""
        self.width = 255
        self.col = 1

    def set_width(self, width):
        """Set file width."""
        self.width = width

    def close(self):
        """Close dummy device file."""


class RawFile(object):
    """File class for raw access to underlying stream."""

    def __init__(self, fhandle, filetype, mode):
        """Setup the basic properties of the file."""
        self.fhandle = fhandle
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
        try:
            self.fhandle.close()
        except EnvironmentError:
            pass

    def switch_mode(self, new_mode):
        """Switch to input or output mode"""

    def input_chars(self, num):
        """Read a number of characters."""
        word = self.read_raw(num)
        if len(word) < num:
            # input past end
            raise error.BASICError(error.INPUT_PAST_END)
        return word

    def read_raw(self, num=-1):
        """Read num chars. If num==-1, read all available."""
        try:
            return self.fhandle.read(num)
        except EnvironmentError:
            raise error.BASICError(error.DEVICE_IO_ERROR)

    def read(self, num=-1):
        """Read num chars. If num==-1, read all available. Override to handle line endings."""
        return self.read_raw(num)

    def write(self, s):
        """Write string or bytearray to file."""
        try:
            self.fhandle.write(str(s))
        except EnvironmentError:
            raise error.BASICError(error.DEVICE_IO_ERROR)

    def flush(self):
        """Write contents of buffers to file."""
        self.fhandle.flush()



#################################################################################
# Text file base

# text interface: file interface +
#   col
#   width
#   read_line(self)
#   write_line(self, s='')
#   eof(self)
#   set_width(self, new_width=255)
#   input_entry(self, typechar, allow_past_end)
#   lof(self)
#   loc(self)

class TextFileBase(RawFile):
    """Base for text files on disk, KYBD file, field buffer."""

    def __init__(self, fhandle, filetype, mode,
                 first_char='', split_long_lines=True):
        """Setup the basic properties of the file."""
        RawFile.__init__(self, fhandle, filetype, mode)
        # width=255 means line wrap
        self.width = 255
        self.col = 1
        # allow first char to be specified (e.g. already read)
        self.next_char = first_char
        # Random files are derived from text files and start in 'I' operating mode
        if self.mode in 'IR' and not first_char:
            try:
                self.next_char = self.fhandle.read(1)
            except (EnvironmentError, ValueError):
                # only catching ValueError here because that's what Serial raises
                self.next_char = ''
        # handling of >255 char lines (False for programs)
        self.split_long_lines = split_long_lines
        self.char, self.last = '', ''

    def read_raw(self, num=-1):
        """Read num characters as string."""
        s = ''
        while True:
            if (num > -1 and len(s) >= num):
                break
            # check for \x1A (EOF char will actually stop further reading
            # (that's true in disk text files but not on LPT devices)
            if self.next_char in ('\x1a', ''):
                break
            s += self.next_char
            self.next_char, self.char, self.last = self.fhandle.read(1), self.next_char, self.char
        return s

    def write(self, s, can_break=True):
        """Write the string s to the file, taking care of width settings."""
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in str(s):
            if c in ('\r', '\n'):
                newline = True
                break
            if ord(c) >= 32:
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if can_break and self.width != 255 and self.col != 1 and self.col-1 + s_width > self.width and not newline:
            self.write_line()
            self.flush()
            self.col = 1
        for c in str(s):
            # don't replace CR or LF with CRLF when writing to files
            if c in ('\r',):
                self.fhandle.write(c)
                self.flush()
                self.col = 1
            else:
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                if ord(c) >= 32:
                    self.col += 1
                    # col-1 is a byte that wraps
                    if self.col == 257:
                        self.col = 1

    def _check_long_line(self, line):
        """Check if line is longer than max length; raise error if needed."""
        if len(line) > 255:
            if self.split_long_lines:
                return True
            else:
                raise error.BASICError(error.LINE_BUFFER_OVERFLOW)
        return False

    def read_line(self):
        """Read a single line."""
        out = []
        while not self._check_long_line(out):
            c = self.read(1)
            # don't check for CRLF on KYBD:, CAS:, etc.
            if not c or c == '\r':
                break
            out.append(c)
        if not c and not out:
            return None
        return b''.join(out)

    def write_line(self, s=''):
        """Write string or bytearray and follow with CR or CRLF."""
        self.write(str(s) + '\r')

    def eof(self):
        """Check for end of file EOF."""
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return self.next_char in ('', '\x1a')

    def set_width(self, new_width=255):
        """Set file width."""
        self.width = new_width

    # support for INPUT#

    # TAB x09 is not whitespace for input#. NUL \x00 and LF \x0a are.
    whitespace_input = ' \0\n'
    # numbers read from file can be separated by spaces too
    soft_sep = ' '

    def _skip_whitespace(self, whitespace):
        """Skip spaces and line feeds and NUL; return last whitespace char """
        c = ''
        while self.next_char and self.next_char in whitespace:
            # drop whitespace char
            c = self.read(1)
            # LF causes following CR to be dropped
            if c == '\n' and self.next_char == '\r':
                # LFCR: drop the CR, report as LF
                self.read(1)
        return c

    def input_entry(self, typechar, allow_past_end):
        """Read a number or string entry for INPUT """
        word, blanks = '', ''
        # fix readahead buffer (self.next_char)
        self.switch_mode(b'I')
        last = self._skip_whitespace(self.whitespace_input)
        # read first non-whitespace char
        c = self.read(1)
        # LF escapes quotes
        # may be true if last == '', hence "in ('\n', '\0')" not "in '\n0'"
        quoted = (c == '"' and typechar == values.STR and last not in ('\n', '\0'))
        if quoted:
            c = self.read(1)
        # LF escapes end of file, return empty string
        if not c and not allow_past_end and last not in ('\n', '\0'):
            raise error.BASICError(error.INPUT_PAST_END)
        # we read the ending char before breaking the loop
        # this may raise FIELD OVERFLOW
        while c and not ((typechar != values.STR and c in self.soft_sep) or
                        (c in ',\r' and not quoted)):
            if c == '"' and quoted:
                # whitespace after quote will be skipped below
                break
            elif c == '\n' and not quoted:
                # LF, LFCR are dropped entirely
                c = self.read(1)
                if c == '\r':
                    c = self.read(1)
                continue
            elif c == '\0':
                # NUL is dropped even within quotes
                pass
            elif c in self.whitespace_input and not quoted:
                # ignore whitespace in numbers, except soft separators
                # include internal whitespace in strings
                if typechar == values.STR:
                    blanks += c
            else:
                word += blanks + c
                blanks = ''
            if len(word) + len(blanks) >= 255:
                break
            if not quoted:
                c = self.read(1)
            else:
                # no CRLF replacement inside quotes.
                c = self.read_raw(1)
        # if separator was a whitespace char or closing quote
        # skip trailing whitespace before any comma or hard separator
        if c and c in self.whitespace_input or (quoted and c == '"'):
            self._skip_whitespace(' ')
            if (self.next_char in ',\r'):
                c = self.read(1)
        # file position is at one past the separator char
        return word, c


#################################################################################
# Console files


class InputTextFile(TextFileBase):
    """Handle INPUT from console."""

    # spaces do not separate numbers on console INPUT
    soft_sep = ''

    def __init__(self, line):
        """Initialise InputStream."""
        TextFileBase.__init__(self, io.BytesIO(line), 'D', 'I')


def input_entry_realtime(self, typechar, allow_past_end):
    """Read a number or string entry from KYBD: or COMn: for INPUT#."""
    word, blanks = '', ''
    if self._input_last:
        c, self._input_last = self._input_last, ''
    else:
        last = self._skip_whitespace(self.whitespace_input)
        # read first non-whitespace char
        c = self.read(1)
    # LF escapes quotes
    # may be true if last == '', hence "in ('\n', '\0')" not "in '\n0'"
    quoted = (c == '"' and typechar == values.STR and last not in ('\n', '\0'))
    if quoted:
        c = self.read(1)
    # LF escapes end of file, return empty string
    if not c and not allow_past_end and last not in ('\n', '\0'):
        raise error.BASICError(error.INPUT_PAST_END)
    # we read the ending char before breaking the loop
    # this may raise FIELD OVERFLOW
    # on reading from a KYBD: file, control char replacement takes place
    # which means we need to use read() not read_raw()
    parsing_trail = False
    while c and not (c in ',\r' and not quoted):
        if c == '"' and quoted:
            parsing_trail = True
        elif c == '\n' and not quoted:
            # LF, LFCR are dropped entirely
            c = self.read(1)
            if c == '\r':
                c = self.read(1)
            continue
        elif c == '\0':
            # NUL is dropped even within quotes
            pass
        elif c in self.whitespace_input and not quoted:
            # ignore whitespace in numbers, except soft separators
            # include internal whitespace in strings
            if typechar == values.STR:
                blanks += c
        else:
            word += blanks + c
            blanks = ''
        if len(word) + len(blanks) >= 255:
            break
        # there should be KYBD: control char replacement here even if quoted
        c = self.read(1)
        if parsing_trail:
            if c not in self.whitespace_input:
                if c not in (',', '\r'):
                    self._input_last = c
                break
        parsing_trail = parsing_trail or (typechar != values.STR and c == ' ')
    # file position is at one past the separator char
    return word, c


###############################################################################

class KYBDFile(TextFileBase):
    """KYBD device: keyboard."""

    # replace some eascii codes with control characters
    _input_replace = {
        ea.HOME: '\xFF\x0B', ea.UP: '\xFF\x1E', ea.PAGEUP: '\xFE',
        ea.LEFT: '\xFF\x1D', ea.RIGHT: '\xFF\x1C', ea.END: '\xFF\x0E',
        ea.DOWN: '\xFF\x1F', ea.PAGEDOWN: '\xFE',
        ea.DELETE: '\xFF\x7F', ea.INSERT: '\xFF\x12',
        ea.F1: '', ea.F2: '', ea.F3: '', ea.F4: '', ea.F5: '',
        ea.F6: '', ea.F7: '', ea.F8: '', ea.F9: '', ea.F10: '',
        }

    col = 0

    def __init__(self, keyboard, display):
        """Initialise keyboard file."""
        # use mode = 'A' to avoid needing a first char from nullstream
        TextFileBase.__init__(self, nullstream(), filetype='D', mode='A')
        # buffer for the separator character that broke the last INPUT# field
        # to be attached to the next
        self._input_last = ''
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

    def read_raw(self, n=1):
        """Read a string from the keyboard - INPUT$."""
        chars = b''
        while len(chars) < n:
            chars += b''.join(b'\0' if c in self._input_replace else c if len(c) == 1 else b''
                              for c in self._keyboard.read_bytes_kybd_file(n-len(chars)))
        return chars

    def read(self, n=1):
        """Read a string from the keyboard - INPUT and LINE INPUT."""
        chars = b''
        while len(chars) < n:
            # note that we need string length, not list length
            # as read_chars can return multi-byte eascii codes
            chars += b''.join(self._input_replace.get(c, c)
                              for c in self._keyboard.read_bytes_kybd_file(n-len(chars)))
        return chars

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
        return (self._keyboard.peek_byte_kybd_file() == b'\x1a')

    def set_width(self, new_width=255):
        """Setting width on KYBD device (not files) changes screen width."""
        if self._is_master:
            self._display.set_width(new_width)

    input_entry = input_entry_realtime


###############################################################################

class SCRNFile(RawFile):
    """SCRN: file, allows writing to the screen as a text file.
        SCRN: files work as a wrapper text file."""

    def __init__(self, display):
        """Initialise screen file."""
        RawFile.__init__(self, nullstream(), filetype='D', mode='O')
        # need display object as WIDTH can change graphics mode
        self._display = display
        # screen member is public, needed by print_
        self.screen = display.text_screen
        self._width = self.screen.mode.width
        self._col = self.screen.current_col
        # on master-file devices, this is the master file.
        self._is_master = True

    def open_clone(self, filetype, mode, reclen=128):
        """Clone screen file."""
        inst = SCRNFile(self._display)
        inst.mode = mode
        inst.reclen = reclen
        inst.filetype = filetype
        inst._is_master = False
        inst._write_magic(filetype)
        return inst

    def _write_magic(self, filetype):
        """Write magic byte."""
        # SAVE "SCRN:" includes a magic byte
        try:
            self.write(TYPE_TO_MAGIC[filetype])
        except KeyError:
            pass

    def write(self, s, can_break=True):
        """Write string s to SCRN: """
        # writes to SCRN files should *not* be echoed
        do_echo = self._is_master
        self._col = self.screen.current_col
        # take column 80+overflow into account
        if self.screen.overflow:
            self._col += 1
        # only break lines at the start of a new string. width 255 means unlimited width
        s_width = 0
        newline = False
        # find width of first line in s
        for c in str(s):
            if c in ('\r', '\n'):
                newline = True
                break
            if c == '\b':
                # for lpt1 and files, nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                s_width -= 1
            elif ord(c) >= 32:
                # nonprinting characters including tabs are not counted for WIDTH
                s_width += 1
        if can_break and (self.width != 255 and self.screen.current_row != self.screen.mode.height
                and self.col != 1 and self.col-1 + s_width > self.width and not newline):
            self.screen.write_line(do_echo=do_echo)
            self._col = 1
        cwidth = self.screen.mode.width
        for c in str(s):
            if self.width <= cwidth and self.col > self.width:
                self.screen.write_line(do_echo=do_echo)
                self._col = 1
            if self.col <= cwidth or self.width <= cwidth:
                self.screen.write(c, do_echo=do_echo)
            if c in ('\n', '\r'):
                self._col = 1
            else:
                self._col += 1

    def write_line(self, inp=''):
        """Write a string to the screen and follow by CR."""
        self.write(inp)
        self.screen.write_line(do_echo=self._is_master)

    @property
    def col(self):
        """Return current (virtual) column position."""
        if self._is_master:
            return self.screen.current_col
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
