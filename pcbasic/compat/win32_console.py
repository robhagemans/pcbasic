"""
PC-BASIC - compat.win32_console
Windows console support:
- unicode output for Python 2
- scroll prevention
- ANSI input & adjustable echo

(c) 2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.

Borrows code from colorama, which is Copyright Jonathan Hartley 2013. BSD 3-Clause license
"""

import os
import sys
import time
import msvcrt
import ctypes
from collections import deque
from ctypes import windll, wintypes, POINTER, byref, Structure, cast

from .base import PY2, wrap_input_stream, wrap_output_stream

if PY2:
    from .python2 import SimpleNamespace
else:
    from types import SimpleNamespace


# Windows virtual key codes
KEYS = SimpleNamespace(
    PAGEUP = 0x21, # VK_PRIOR
    PAGEDOWN = 0x22, # VK_NEXT
    END = 0x23,
    HOME = 0x24,
    LEFT = 0x25,
    UP = 0x26,
    RIGHT = 0x27,
    DOWN = 0x28,
    INSERT = 0x2d,
    DELETE = 0x2e,
    F1 = 0x70,
    F2 = 0x71,
    F3 = 0x72,
    F4 = 0x73,
    F5 = 0x74,
    F6 = 0x75,
    F7 = 0x76,
    F8 = 0x77,
    F9 = 0x78,
    F10 = 0x79,
    F11 = 0x7a,
    F12 = 0x7b,
)

# Windows colour constants
COLOURS = SimpleNamespace(
    BLACK = 0,
    BLUE = 1,
    GREEN = 2,
    CYAN = 3,
    RED = 4,
    MAGENTA = 5,
    YELLOW = 6,
    WHITE = 7, # GREY
)

# windpws constants
KEY_EVENT = 1
VK_MENU = 0x12

# character attributes, from wincon.h
NORMAL = 0x00
BRIGHT = 0x08


##############################################################################
# ctypes wrappers

class KEY_EVENT_RECORD(Structure):
    _fields_ = (
        ('bKeyDown', wintypes.BOOL), #32 bit?
        ('wRepeatCount', wintypes.WORD), #16
        ('wVirtualKeyCode', wintypes.WORD),#16
        ('wVirtualScanCode', wintypes.WORD), #16
        # union with CHAR AsciiChar
        ('UnicodeChar', wintypes.WCHAR), #32
        ('dwControlKeyState', wintypes.DWORD), #32
        # note that structure is in a union with other event records
        # but it is the largest type. mouseeventrecord is 128 bytes
    )

class INPUT_RECORD(Structure):
    _fields_ = (
        ('EventType', wintypes.WORD),
        # union of many event types but we only care about key events
        # total size is 16 bytes
        ('KeyEvent', KEY_EVENT_RECORD),
    )

class CHAR_INFO(Structure):
    _fields_ = (
        ('UnicodeChar', wintypes.WCHAR),
        ('Attributes', wintypes.WORD),
    )

class CONSOLE_SCREEN_BUFFER_INFO(Structure):
    _fields_ = (
        ('dwSize', wintypes._COORD),
        ('dwCursorPosition', wintypes._COORD),
        ('wAttributes', wintypes.WORD),
        ('srWindow', wintypes.SMALL_RECT),
        ('dwMaximumWindowSize', wintypes._COORD),
    )

class CONSOLE_CURSOR_INFO(Structure):
    _fields_ = (
        ("dwSize", wintypes.DWORD),
        ("bVisible", wintypes.BOOL),
    )

_GetStdHandle = windll.kernel32.GetStdHandle
_GetStdHandle.argtypes = (wintypes.DWORD,)
_GetStdHandle.restype = wintypes.HANDLE

_WriteConsoleW = windll.kernel32.WriteConsoleW
_WriteConsoleW.argtypes = (
    wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD, POINTER(wintypes.DWORD), wintypes.LPVOID
)

_WriteConsoleOutputW = windll.kernel32.WriteConsoleOutputW
_WriteConsoleOutputW.argtypes = (
    wintypes.HANDLE, POINTER(CHAR_INFO),
    wintypes._COORD, wintypes._COORD, POINTER(wintypes.SMALL_RECT)
)

_ReadConsoleInputW = windll.kernel32.ReadConsoleInputW
_ReadConsoleInputW.argtypes = (
    wintypes.HANDLE, POINTER(INPUT_RECORD), wintypes.DWORD, POINTER(wintypes.DWORD)
)

_GetNumberOfConsoleInputEvents = windll.kernel32.GetNumberOfConsoleInputEvents
_GetNumberOfConsoleInputEvents.argtypes = (wintypes.HANDLE, POINTER(wintypes.DWORD))

_GetConsoleScreenBufferInfo = windll.kernel32.GetConsoleScreenBufferInfo
_GetConsoleScreenBufferInfo.argtypes = (wintypes.HANDLE, POINTER(CONSOLE_SCREEN_BUFFER_INFO))

_SetConsoleTitleW = windll.kernel32.SetConsoleTitleW
_SetConsoleTitleW.argtypes = (wintypes.LPCWSTR,)
_SetConsoleTitleW.restype = wintypes.BOOL

_FillConsoleOutputCharacterW = windll.kernel32.FillConsoleOutputCharacterW
_FillConsoleOutputCharacterW.argtypes = (
    wintypes.HANDLE,
    wintypes.WCHAR,
    wintypes.DWORD,
    wintypes._COORD,
    POINTER(wintypes.DWORD),
)
_FillConsoleOutputCharacterW.restype = wintypes.BOOL

_FillConsoleOutputAttribute = windll.kernel32.FillConsoleOutputAttribute
_FillConsoleOutputAttribute.argtypes = (
    wintypes.HANDLE,
    wintypes.WORD,
    wintypes.DWORD,
    wintypes._COORD,
    POINTER(wintypes.DWORD),
)
_FillConsoleOutputAttribute.restype = wintypes.BOOL

_SetConsoleCursorPosition = windll.kernel32.SetConsoleCursorPosition
_SetConsoleCursorPosition.argtypes = (wintypes.HANDLE, wintypes._COORD)
_SetConsoleCursorPosition.restype = wintypes.BOOL

_GetConsoleCursorInfo = windll.kernel32.GetConsoleCursorInfo
_GetConsoleCursorInfo.argtypes = (wintypes.HANDLE, POINTER(CONSOLE_CURSOR_INFO))

_SetConsoleCursorInfo = windll.kernel32.SetConsoleCursorInfo
_SetConsoleCursorInfo.argtypes = (wintypes.HANDLE, POINTER(CONSOLE_CURSOR_INFO))

_ScrollConsoleScreenBuffer = windll.kernel32.ScrollConsoleScreenBufferW
_ScrollConsoleScreenBuffer.argtypes = (
    wintypes.HANDLE,
    POINTER(wintypes.SMALL_RECT),
    POINTER(wintypes.SMALL_RECT),
    wintypes._COORD,
    POINTER(CHAR_INFO),
)

_SetConsoleTextAttribute = windll.kernel32.SetConsoleTextAttribute
_SetConsoleTextAttribute.argtypes = (wintypes.HANDLE, wintypes.WORD)
_SetConsoleTextAttribute.restype = wintypes.BOOL

_SetConsoleScreenBufferSize = windll.kernel32.SetConsoleScreenBufferSize
_SetConsoleScreenBufferSize.argtypes = (wintypes.HANDLE, wintypes._COORD)

_SetConsoleWindowInfo = windll.kernel32.SetConsoleWindowInfo
_SetConsoleWindowInfo.argtypes = (
    wintypes.HANDLE,
    wintypes.BOOL,
    POINTER(wintypes.SMALL_RECT),
)


def GetConsoleScreenBufferInfo(handle):
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    _GetConsoleScreenBufferInfo(handle, byref(csbi))
    return csbi

def FillConsoleOutputCharacter(handle, char, length, start):
    length = wintypes.DWORD(length)
    num_written = wintypes.DWORD(0)
    _FillConsoleOutputCharacterW(handle, char, length, start, byref(num_written))
    return num_written.value

def FillConsoleOutputAttribute(handle, attr, length, start):
    attribute = wintypes.WORD(attr)
    length = wintypes.DWORD(length)
    return _FillConsoleOutputAttribute(handle, attribute, length, start, byref(wintypes.DWORD()))

def GetConsoleCursorInfo(handle):
    cci = CONSOLE_CURSOR_INFO()
    _GetConsoleCursorInfo(handle, byref(cci))
    return cci

def SetConsoleCursorInfo(handle, cci):
    _SetConsoleCursorInfo(handle, byref(cci))

def ScrollConsoleScreenBuffer(handle, scroll_rect, clip_rect, new_position, char, attr):
    char_info = CHAR_INFO(char, attr)
    _ScrollConsoleScreenBuffer(
        handle, byref(scroll_rect), byref(clip_rect), new_position, byref(char_info)
    )


HSTDIN = _GetStdHandle(-10)
HSTDOUT = _GetStdHandle(-11)
HSTDERR = _GetStdHandle(-12)


def _write_console(handle, unistr):
    """Write character to console, avoid scroll on bottom line."""
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    _GetConsoleScreenBufferInfo(handle, byref(csbi))
    col, row = csbi.dwCursorPosition.X, csbi.dwCursorPosition.Y
    width, height = csbi.dwSize.X, csbi.dwSize.Y
    for ch in unistr:
        if (row == height-1 and col >= width - 1 and ch != u'\n'):
            ci = CHAR_INFO(ch, csbi.wAttributes)
            # do not advance cursor if we're on the last position of the
            # screen buffer, to avoid unwanted scrolling.
            _WriteConsoleOutputW(
                handle, byref(ci), wintypes._COORD(1, 1), wintypes._COORD(0, 0),
                wintypes.SMALL_RECT(col, row, col, row)
            )
        else:
            _WriteConsoleW(
                handle, ch, 1,
                byref(wintypes.DWORD()), byref(wintypes.DWORD())
            )


# preserve original terminal size
def _get_term_size():
    """Get size of terminal window."""
    try:
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        left, top = csbi.srWindow.Left, csbi.srWindow.Top,
        right, bottom = csbi.srWindow.Right, csbi.srWindow.Bottom
        return bottom-top+1, right-left+1
    except Exception:
        return 25, 80


##############################################################################
# console class

class Win32Console(object):
    """Win32API-based console implementation."""

    keys = KEYS
    colours = COLOURS

    def __init__(self):
        """Set up console"""
        self.original_size = _get_term_size()
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        self._default = csbi.wAttributes
        self._attrs = csbi.wAttributes
        # input
        self._input_buffer = deque()
        self._echo = True

    def set_raw(self):
        """Enter raw terminal mode."""
        self._echo = False

    def unset_raw(self):
        """Leave raw terminal mode."""
        self._echo = True

    def key_pressed(self):
        """key pressed on keyboard."""
        return msvcrt.kbhit()

    def set_caption(self, caption):
        """Set terminal caption."""
        _SetConsoleTitleW(caption)

    def resize(self, height, width):
        """Resize terminal."""
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        # SetConsoleScreenBufferSize can't make the buffer smaller than the window
        # SetConsoleWindowInfo can't make the window larger than the buffer (in either direction)
        # allow for both shrinking and growing by calling one of them twice,
        # for each direction separately
        new_size = wintypes._COORD(width, csbi.dwSize.Y)
        new_window = wintypes.SMALL_RECT(0, 0, width-1, csbi.dwSize.Y-1)
        _SetConsoleScreenBufferSize(HSTDOUT, new_size)
        _SetConsoleWindowInfo(HSTDOUT, True, new_window)
        _SetConsoleScreenBufferSize(HSTDOUT, new_size)
        new_size = wintypes._COORD(width, height)
        new_window = wintypes.SMALL_RECT(0, 0, width-1, height-1)
        _SetConsoleScreenBufferSize(HSTDOUT, new_size)
        _SetConsoleWindowInfo(HSTDOUT, True, new_window)
        _SetConsoleScreenBufferSize(HSTDOUT, new_size)

    ##########################################################################
    # output

    def write(self, unistr):
        """Write text to the console."""
        _write_console(HSTDOUT, unistr)

    def clear(self):
        """Clear the screen."""
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        # fill the entire screen with blanks
        FillConsoleOutputCharacter(
            HSTDOUT, u' ', csbi.dwSize.X * csbi.dwSize.Y, wintypes._COORD(0, 0)
        )
        # now set the buffer's attributes accordingly
        FillConsoleOutputAttribute(
            HSTDOUT, self._attrs, csbi.dwSize.X * csbi.dwSize.Y, wintypes._COORD(0, 0)
        )
        _SetConsoleCursorPosition(HSTDOUT, wintypes._COORD(0, 0))

    def clear_row(self):
        """Clear the current row."""
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        from_coord = wintypes._COORD(0, csbi.dwCursorPosition.Y)
        # fill the entire screen with blanks
        FillConsoleOutputCharacter(HSTDOUT, u' ', csbi.dwSize.X, from_coord)
        # now set the buffer's attributes accordingly
        FillConsoleOutputAttribute(HSTDOUT, self._attrs, csbi.dwSize.X, from_coord)

    def _set_cursor_visibility(self, visible):
        """Set the visibility of the cursor."""
        curs_info = GetConsoleCursorInfo(HSTDOUT)
        curs_info.bVisible = visible
        SetConsoleCursorInfo(HSTDOUT, curs_info);

    def show_cursor(self):
        """Show the cursor."""
        self._set_cursor_visibility(True)

    def hide_cursor(self):
        """Hide the cursor."""
        self._set_cursor_visibility(False)

    def move_cursor_left(self, n):
        """Move cursor n cells to the left."""
        self._move_cursor(0, -n)

    def move_cursor_right(self, n):
        """Move cursor n cells to the right."""
        self._move_cursor(0, n)

    def _move_cursor(self, rows, cols):
        """Move cursor relative to current position."""
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        position = csbi.dwCursorPosition
        self.move_cursor_to(position.Y+1 + rows, position.X+1 + cols)

    def move_cursor_to(self, row, col):
        """Move cursor to a new position (1,1 is top left)."""
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        row, col = row-1, col-1
        while col >= csbi.dwSize.X:
            col -= csbi.dwSize.X
            row += 1
        while col < 0:
            col += csbi.dwSize.X
            row -= 1
        # If the position is out of range, do nothing.
        if row >= 0 and col >= 0:
            _SetConsoleCursorPosition(HSTDOUT, wintypes._COORD(col, row))

    def _scroll(self, start, stop, rows):
        if not rows:
            return
        csbi = GetConsoleScreenBufferInfo(HSTDOUT)
        # absolute position of window in screen buffer
        # interpret other coordinates as relative to the window
        window = csbi.srWindow
        # scroll region
        clip_rect = wintypes.SMALL_RECT(
            window.Left, window.Top + start, window.Right, window.Top + stop
        )
        if rows > 0:
            region = wintypes.SMALL_RECT(window.Left, window.Top + rows, window.Right, window.Bottom)
            new_pos = wintypes._COORD(window.Left, window.Top)
        else:
            region = wintypes.SMALL_RECT(window.Left, window.Top, window.Right, window.Bottom + rows)
            new_pos = wintypes._COORD(window.Left, window.Top + rows)
        # workaround: in this particular case, Windows doesn't seem to respect the clip area.
        if (
                clip_rect.Bottom == window.Bottom-1 and
                region.Bottom >= window.Bottom-1 and
                new_pos.Y < region.Top
            ):
            # first scroll everything up
            clip_rect.Bottom = window.Bottom
            bottom, region.Bottom = region.Bottom, window.Bottom
            ScrollConsoleScreenBuffer(HSTDOUT, region, clip_rect, new_pos, u' ', self._attrs)
            # and then scroll the bottom back down
            new_pos.Y = window.Bottom
            region.Top = bottom-1
            ScrollConsoleScreenBuffer(HSTDOUT, region, clip_rect, new_pos, u' ', self._attrs)
        else:
            ScrollConsoleScreenBuffer(HSTDOUT, region, clip_rect, new_pos, u' ', self._attrs)

    def scroll_up(self, top, bottom):
        """Scroll the region between top and bottom one row up."""
        self._scroll(top-1, bottom-1, 1)

    def scroll_down(self, top, bottom):
        """Scroll the region between top and bottom one row down."""
        self._scroll(top-1, bottom-1, -1)

    def reset_attributes(self):
        """Reset to default attributes."""
        self._attrs = self._default
        _SetConsoleTextAttribute(HSTDOUT, self._default)

    def set_attributes(self, fore, back, bright, blink, underline):
        """Set current attributes."""
        self._attrs = fore + back * 16 + (BRIGHT if bright else NORMAL)
        _SetConsoleTextAttribute(HSTDOUT, self._attrs)

    ##########################################################################
    # input

    def read_key(self):
        """
        Read keypress from console. Non-blocking. Returns:
        - unicode, if character key
        - int out of console.keys, if special key
        - EOF if closed
        """
        self._fill_buffer(blocking=False)
        if not self._input_buffer:
            return u''
        return self._input_buffer.popleft()

    def read_all_chars(self):
        """Read all characters in the buffer."""
        self._fill_buffer(blocking=False)
        closed = False
        if self._input_buffer and self._input_buffer[-1] == u'\x1a':
            closed = True
            self._input_buffer.pop()
            if not self._input_buffer:
                return None
        output = u''.join(
            _char for _char in self._input_buffer
            if not isinstance(_char, int)
        )
        self._input_buffer.clear()
        if closed:
            self._input_buffer.append(u'\x1a')
        return output

    def _fill_buffer(self, blocking):
        """Interpret all key events."""
        while True:
            nevents = wintypes.DWORD()
            _GetNumberOfConsoleInputEvents(HSTDIN, byref(nevents))
            if not nevents.value and not blocking:
                return
            # only ever block on first loop
            blocking = False
            if nevents.value > 0:
                input_buffer = (INPUT_RECORD * nevents.value)()
                nread = wintypes.DWORD()
                _ReadConsoleInputW(
                    HSTDIN,
                    cast(input_buffer, POINTER(INPUT_RECORD)),
                    nevents.value, byref(nread)
                )
                for event in input_buffer:
                    if event.EventType != KEY_EVENT:
                        continue
                    key = self._translate_event(event)
                    if key:
                        self._input_buffer.append(key)
                        if key == u'\x1a':
                            # ctrl-z is end of input on windows console
                            return
                        if self._echo:
                            self._echo_key(key)
            time.sleep(0.01)

    def _translate_event(self, event):
        char = event.KeyEvent.UnicodeChar
        key = event.KeyEvent.wVirtualKeyCode
        if char == u'\0':
            # windows uses null-terminated strings so \0 means no output
            char = u''
        if not event.KeyEvent.bKeyDown:
            # key-up event for unicode Alt+HEX input
            if event.KeyEvent.wVirtualKeyCode == VK_MENU:
                return char
            # ignore other key-up events
            return u''
        elif event.KeyEvent.dwControlKeyState & 0xf:
            # ctrl or alt are down; don't parse arrow keys etc.
            # but if any unicode is produced, send it on
            return char
        # this is hacky - is the key code a recognised one?
        elif key in self.keys.__dict__.values():
            return key
        return char

    def _echo_key(self, key):
        """Echo a character or special key."""
        if not isinstance(key, int):
            # caracter echo
            if key == u'\r':
                key = u'\n'
            _write_console(HSTDOUT, key)


def _has_console():
    """Determine if we have a console attached or are a GUI app."""
    try:
        return bool(windll.kernel32.GetConsoleMode(HSTDOUT, byref(wintypes.DWORD())))
    except Exception as e:
        return False


if _has_console():
    console = Win32Console()
else:
    console = None


##############################################################################
# non-blocking input

def read_all_available(stream):
    """Read all available characters from a stream; nonblocking; None if closed."""
    # are we're reading from (wrapped) stdin or not?
    if hasattr(stream, 'isatty') and stream.isatty():
        # this is shaky - try to identify unicode vs bytes stream
        is_unicode_stream = hasattr(stream, 'buffer')
        unistr = console.read_all_chars()
        if is_unicode_stream or unistr is None:
            return unistr
        else:
            return unistr.encode(stdin.encoding, 'replace')
    else:
        # this would work on unix too
        # just read the whole file and be done with it
        return stream.read() or None


##############################################################################
# standard i/o

if PY2:

    class _StreamWrapper(object):
        """Delegating stream wrapper."""

        def __init__(self, stream, handle, encoding='utf-8'):
            self._wrapped = stream
            self._handle = handle
            self.encoding = encoding

        def __getattr__(self, attr):
            return getattr(self._wrapped, attr)


    class _ConsoleOutput(_StreamWrapper):
        """Bytes stream wrapper using Unicode API, to replace Python2 sys.stdout."""

        def write(self, bytestr):
            if not isinstance(bytestr, bytes):
                raise TypeError('write() argument must be bytes, not %s' % type(bytestr))
            unistr = bytestr.decode(self.encoding)
            _write_console(self._handle, unistr)


    class _ConsoleInput(_StreamWrapper):
        """Bytes stream wrapper using Unicode API, to replace Python2 sys.stdin."""

        def __init__(self, encoding='utf-8'):
            _StreamWrapper.__init__(self, sys.stdin, HSTDIN, encoding)

        def read(self, size=-1):
            output = bytearray()
            while size < 0 or len(output) < size:
                key = console.read_key()
                if isinstance(key, int):
                    continue
                output.append(key.encode(self.encoding))
            return bytes(output)


    if sys.stdin.isatty():
        stdin = wrap_input_stream(_ConsoleInput())
    else:
        stdin = wrap_input_stream(sys.stdin)

    if sys.stdout.isatty():
        stdout = wrap_output_stream(_ConsoleOutput(sys.stdout, HSTDOUT))
    else:
        stdout = wrap_output_stream(sys.stdout)

    if sys.stderr.isatty():
        stderr = wrap_output_stream(_ConsoleOutput(sys.stderr, HSTDERR))
    else:
        stderr = wrap_output_stream(sys.stderr)

else:
    stdin = sys.stdin
    stdout = sys.stdout
    stderr = sys.stderr


# set stdio as binary, to avoid Windows messing around with CRLFs
# only do this for redirected output, as it breaks interactive Python sessions
try:
    if not sys.stdin.isatty():
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    if not sys.stdout.isatty():
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
except EnvironmentError:
    # raises an error if started in gui mode, as we have no stdio
    pass
