"""
PC-BASIC - devices.py
Devices, Files and I/O operations

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
import copy

import config
import error
import console
import state
import memory

# file numbers
state.io_state.files = {}

# maximum file number = maximum number of open files
# this is a command line option -f
max_files = 3

nullstream = open(os.devnull, 'r+')

# devices - SCRN: KYBD: LPT1: etc.
state.io_state.devices = {}
state.io_state.scrn_file = None
state.io_state.kybd_file = None
state.io_state.lpt1_file = None

# set by disk.py
state.io_state.current_device = None

# magic chars used by some devices to indicate file type
type_to_magic = { 'B': '\xff', 'P': '\xfe', 'M': '\xfd' }
magic_to_type = { '\xff': 'B', '\xfe': 'P', '\xfd': 'M' }

def prepare():
    """ Initialise iolayer module. """
    global max_files
    max_files = min(16, config.get('max-files'))
    # console
    state.io_state.devices['SCRN:'] = SCRNDevice()
    state.io_state.devices['KYBD:'] = KYBDDevice()
    state.io_state.scrn_file = state.io_state.devices['SCRN:'].device_file
    state.io_state.kybd_file = state.io_state.devices['KYBD:'].device_file


############################################################################
# General file manipulation

def open_file(number, description, filetype, mode='I', access='R', lock='',
              reclen=128, seg=0, offset=0, length=0):
    """ Open a file on a device specified by description. """
    if (not description) or (number < 0) or (number > max_files):
        # bad file number; also for name='', for some reason
        raise error.RunError(error.BAD_FILE_NUMBER)
    if number in state.io_state.files:
        raise error.RunError(error.FILE_ALREADY_OPEN)
    name, mode = str(description), mode.upper()
    inst = None
    split_colon = name.split(':')
    if len(split_colon) > 1: # : found
        dev_name = split_colon[0].upper() + ':'
        dev_param = ''.join(split_colon[1:])
        try:
            device = state.io_state.devices[dev_name]
        except KeyError:
            # not an allowable device or drive name
            # bad file number, for some reason
            raise error.RunError(error.BAD_FILE_NUMBER)
    else:
        device = state.io_state.current_device
        dev_param = name
    # check if device exists and allows the requested mode
    new_file = device.open(number, dev_param, filetype, mode, access, lock,
                           reclen, seg, offset, length)
    if number:
        state.io_state.files[number] = new_file
    return new_file

def get_file(num, mode='IOAR'):
    """ Get the file object for a file number and check allowed mode. """
    try:
        the_file = state.io_state.files[num]
    except KeyError:
        raise error.RunError(error.BAD_FILE_NUMBER)
    if the_file.mode.upper() not in mode:
        raise error.RunError(error.BAD_FILE_MODE)
    return the_file

def close_file(num):
    """ Close a numbered file. """
    try:
        state.io_state.files[num].close()
        del state.io_state.files[num]
    except KeyError:
        pass

def close_files():
    """ Close all files. """
    for f in state.io_state.files.values():
        f.close()
    state.io_state.files = {}

def close_devices():
    """ Close device master files. """
    for d in state.io_state.devices.values():
        d.close()


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
    """ Retrieve protocol and options from argument. """
    argsplit = arg.split(':', 1)
    if len(argsplit) == 1:
        addr, val = None, argsplit[0]
    else:
        addr, val = argsplit[0].upper(), ''.join(argsplit[1:])
    return addr, val


class Device(object):
    """ Device interface for master-file devices. """

    allowed_modes = ''

    def __init__(self):
        """ Set up device. """
        self.device_file = None

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on the device. """
        if not self.device_file:
            raise error.RunError(error.DEVICE_UNAVAILABLE)
        if mode not in self.allowed_modes:
            raise error.RunError(error.BAD_FILE_MODE)
        new_file = self.device_file.clone(filetype, mode, reclen)
        return new_file

    def close(self):
        if self.device_file:
            self.device_file.close()


class SCRNDevice(Device):
    """ Screen device (SCRN:) """

    allowed_modes = 'OR'

    def __init__(self):
        """ Initialise screen device. """
        # open a master file on the screen
        Device.__init__(self)
        self.device_file = SCRNFile()


class KYBDDevice(Device):
    """ Keyboard device (KYBD:) """

    allowed_modes = 'IR'

    def __init__(self):
        """ Initialise keyboard device. """
        # open a master file on the keyboard
        Device.__init__(self)
        self.device_file = KYBDFile()


#################################################################################
# file classes


class RawFile(object):
    """ File class for raw access to underlying stream. """

    def __init__(self, fhandle, filetype, mode):
        """ Setup the basic properties of the file. """
        self.fhandle = fhandle
        self.filetype = filetype
        self.mode = mode.upper()
        # on master-file devices, this is the master file.
        self.is_master = True

    def __enter__(self):
        """ Context guard. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Context guard. """
        self.close()

    def clone(self, filetype, mode, reclen=128):
        """ Clone device file. """
        inst = copy.copy(self)
        inst.mode = mode
        inst.reclen = reclen
        inst.filetype = filetype
        inst.is_master = False
        return inst

    def close(self):
        """ Close the file. """
        try:
            self.fhandle.close()
        except EnvironmentError:
            pass

    def read_raw(self, num=-1):
        """ Read num chars. If num==-1, read all available. """
        try:
            return self.fhandle.read(num)
        except EnvironmentError:
            raise error.RunError(error.DEVICE_IO_ERROR)

    def read(self, num=-1):
        """ Read num chars. If num==-1, read all available. """
        return self.read_raw(num)

    def write(self, s):
        """ Write string or bytearray to file. """
        try:
            self.fhandle.write(str(s))
        except EnvironmentError:
            raise error.RunError(error.DEVICE_IO_ERROR)

    def flush(self):
        """ Write contents of buffers to file. """
        self.fhandle.flush()



#################################################################################
# Text file base

class TextFileBase(RawFile):
    """ Base for text files on disk, KYBD file, field buffer. """

    def __init__(self, fhandle, filetype, mode,
                 first_char='', split_long_lines=True):
        """ Setup the basic properties of the file. """
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

    def read_raw(self, num=-1):
        """ Read num characters as string. """
        s = ''
        while True:
            if (num > -1 and len(s) >= num):
                break
            # check for \x1A (EOF char will actually stop further reading
            # (that's true in disk text files but not on LPT devices)
            if self.next_char in ('\x1a', ''):
                break
            s += self.next_char
            self.next_char = self.fhandle.read(1)
        return s

    def read_line(self):
        """ Read a single line. """
        out = bytearray('')
        while not self._check_long_line(out):
            c = self.read(1)
            # don't check for CRLF on KYBD:, CAS:, etc.
            if not c or c == '\r':
                break
            out += c
        if not c and not out:
            return None
        return out

    def _check_long_line(self, line):
        """ Check if line is longer than max length; raise error if needed. """
        if len(line) >= 255:
            if self.split_long_lines:
                return True
            else:
                raise error.RunError(error.LINE_BUFFER_OVERFLOW)
        return False

    def write(self, s):
        """ Write the string s to the file, taking care of width settings. """
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
        if self.width != 255 and self.col != 1 and self.col-1 + s_width > self.width and not newline:
            self.write_line()
            self.flush()
            self.col = 1
        for c in str(s):
            # don't replace CR or LF with CRLF when writing to files
            if c in ('\n', '\r'):
                self.fhandle.write(c)
                self.flush()
                self.col = 1
            else:
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                if ord(c) >= 32:
                    self.col += 1

    def write_line(self, s=''):
        """ Write string or bytearray and follow with CR or CRLF. """
        self.write(str(s) + '\r')

    def eof(self):
        """ Check for end of file EOF. """
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return self.next_char in ('', '\x1a')

    def set_width(self, new_width=255):
        """ Set file width. """
        self.width = new_width


class CRLFTextFileBase(TextFileBase):
    """ Text file with CRLF line endings, on disk device or field buffer. """

    def read(self, num=-1):
        """ Read num characters, replacing CR LF with CR. """
        s = ''
        while len(s) < num:
            c = self.read_raw(1)
            if not c:
                break
            s += c
            # ignore LF after CR
            if c == '\r' and self.next_char == '\n':
                self.read_raw(1)
        return s

    def read_line(self):
        """ Read line from text file, break on CR or CRLF (not LF). """
        s, c = '', ''
        while not self._check_long_line(s):
            c, last = self.read(1), c
            if not c or (c == '\r' and last != '\n'):
                # break on CR, CRLF but allow LF, LFCR to pass
                break
            else:
                s += c
        if not c and not s:
            return None
        return s

    def write_line(self, s=''):
        """ Write string or bytearray and newline to file. """
        self.write(str(s) + '\r\n')


############################################################################
# FIELD buffers

class Field(object):
    """ Buffer for FIELD access. """

    def __init__(self, number):
        """ Set up empty FIELD buffer. """
        if number > 0:
            self.address = memory.field_mem_start + (number-1)*memory.field_mem_offset
        else:
            self.address = -1
        self.buffer = bytearray()

    def reset(self, reclen):
        """ Initialise FIELD buffer to reclen NULs. """
        self.buffer = bytearray(reclen)


#################################################################################
# Console files

class KYBDFile(TextFileBase):
    """ KYBD device: keyboard. """

    input_replace = {
        '\0\x47': '\xFF\x0B', '\0\x48': '\xFF\x1E', '\0\x49': '\xFE',
        '\0\x4B': '\xFF\x1D', '\0\x4D': '\xFF\x1C', '\0\x4F': '\xFF\x0E',
        '\0\x50': '\xFF\x1F', '\0\x51': '\xFE', '\0\x53': '\xFF\x7F', '\0\x52': '\xFF\x12'
        }

    col = 0

    def __init__(self):
        """ Initialise keyboard file. """
        # use mode = 'A' to avoid needing a first char from nullstream
        TextFileBase.__init__(self, nullstream, filetype='D', mode='A')

    def read_raw(self, n=1):
        """ Read a list of chars from the keyboard - INPUT$ """
        word = ''
        for char in state.console_state.keyb.read_chars(n):
            if len(char) > 1 and char[0] == '\0':
                # replace some scancodes than console can return
                if char[1] in ('\x4b', '\x4d', '\x48', '\x50',
                                '\x47', '\x49', '\x4f', '\x51', '\x53'):
                    word += '\0'
                # ignore all others
            else:
                word += char
        return word

    def read(self, n=1):
        """ Read a string from the keyboard - INPUT and LINE INPUT. """
        word = ''
        for c in state.console_state.keyb.read_chars(n):
            if len(c) > 1 and c[0] == '\0':
                try:
                    word += self.input_replace[c]
                except KeyError:
                    pass
            else:
                word += c
        return word

    def lof(self):
        """ LOF for KYBD: is 1. """
        return 1

    def loc(self):
        """ LOC for KYBD: is 0. """
        return 0

    def eof(self):
        """ KYBD only EOF if ^Z is read. """
        if self.mode in ('A', 'O'):
            return False
        # blocking peek
        return (state.console_state.keyb.wait_char() == '\x1a')

    def set_width(self, new_width=255):
        """ Setting width on KYBD device (not files) changes screen width. """
        if self.is_master:
            console.set_width(new_width)


class SCRNFile(RawFile):
    """ SCRN: file, allows writing to the screen as a text file.
        SCRN: files work as a wrapper text file. """

    def __init__(self):
        """ Initialise screen file. """
        RawFile.__init__(self, nullstream, filetype='D', mode='O')
        self._width = state.console_state.screen.mode.width
        self._col = state.console_state.col

    def clone(self, filetype, mode, reclen=128):
        """ Close screen file. """
        inst = RawFile.clone(self, filetype, mode, reclen)
        inst._write_magic(filetype)
        return inst

    def _write_magic(self, filetype):
        """ Write magic byte. """
        # SAVE "SCRN:" includes a magic byte
        try:
            self.write(type_to_magic[filetype])
        except KeyError:
            pass

    def write(self, s):
        """ Write string s to SCRN: """
        # writes to SCRN files should *not* be echoed
        do_echo = self.is_master
        self._col = state.console_state.col
        # take column 80+overflow int account
        if state.console_state.overflow:
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
        if (self.width != 255
                and self.col != 1 and self.col-1 + s_width > self.width and not newline):
            console.write_line(do_echo=do_echo)
            self._col = 1
        cwidth = state.console_state.screen.mode.width
        for c in str(s):
            if self.width <= cwidth and self.col > self.width:
                console.write_line(do_echo=do_echo)
                self._col = 1
            if self.col <= cwidth or self.width <= cwidth:
                console.write(c, do_echo=do_echo)
            if c in ('\n', '\r'):
                self._col = 1
            else:
                self._col += 1

    def write_line(self, inp=''):
        """ Write a string to the screen and follow by CR. """
        self.write(inp)
        console.write_line(do_echo=self.is_master)

    @property
    def col(self):
        """ Return current (virtual) column position. """
        if self.is_master:
            return state.console_state.col
        else:
            return self._col

    @property
    def width(self):
        """ Return (virtual) screen width. """
        if self.is_master:
            return state.console_state.screen.mode.width
        else:
            return self._width

    def set_width(self, new_width=255):
        """ Set (virtual) screen width. """
        if self.is_master:
            console.set_width(new_width)
        else:
            self._width = new_width

    def lof(self):
        """ LOF: bad file mode. """
        raise error.RunError(error.BAD_FILE_MODE)

    def loc(self):
        """ LOC: bad file mode. """
        raise error.RunError(error.BAD_FILE_MODE)

    def eof(self):
        """ EOF: bad file mode. """
        raise error.RunError(error.BAD_FILE_MODE)


prepare()
