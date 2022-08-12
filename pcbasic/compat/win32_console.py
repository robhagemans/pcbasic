"""
PC-BASIC - compat.win32_console
Windows console support:
- unicode output for Python 2
- scroll prevention
- ANSI input & adjustable echo

(c) 2018--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.

Borrows code from colorama, which is Copyright Jonathan Hartley 2013. BSD 3-Clause license
"""

# pylint: disable=no-name-in-module, no-member

import os
import sys
import time
import msvcrt
import ctypes
from contextlib import contextmanager
from collections import deque
from ctypes import windll, wintypes, POINTER, byref, Structure, cast

from .base import PY2
from .streams import StdIOBase

if PY2: # pragma: no cover
    from .python2 import SimpleNamespace
else:
    from types import SimpleNamespace



# Windows virtual key codes, mapped to standard key names
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
    #
    ALT = 0x12, # VK_MENU
)
VK_TO_KEY = {value: key for key, value in KEYS.__dict__.items()}
# alpha key codes
VK_TO_KEY.update({
    value: chr(value).lower() for value in range(0x30, 0x5b)
})

# control key state bit flags
# CAPSLOCK_ON = 0x0080,
# ENHANCED_KEY = 0x0100,
# LEFT_ALT_PRESSED = 0x0002,
# LEFT_CTRL_PRESSED = 0x0008,
# NUMLOCK_ON = 0x0020,
# RIGHT_ALT_PRESSED = 0x0001,
# RIGHT_CTRL_PRESSED = 0x0004,
# SCROLLLOCK_ON = 0x0040,
# SHIFT_PRESSED = 0x0010,
MODS = dict(
    CTRL = 0x0c,
    ALT = 0x03,
    SHIFT = 0x10,
)

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

class CONSOLE_SCREEN_BUFFER_INFOEX(Structure):
    _fields_ = (
        ('cbSize', wintypes.ULONG),
        ('dwSize', wintypes._COORD),
        ('dwCursorPosition', wintypes._COORD),
        ('wAttributes', wintypes.WORD),
        ('srWindow', wintypes.SMALL_RECT),
        ('dwMaximumWindowSize', wintypes._COORD),
        ('wPopupAttributes', wintypes.WORD),
        ('bFullscreenSupported', wintypes.BOOL),
        ('ColorTable', wintypes.DWORD*16),
    )

class SECURITY_ATTRIBUTES(Structure):
    _fields_ = (
        ('nLength', wintypes.DWORD),
        ('lpSecurityDescriptor', wintypes.LPVOID),
        ('bInheritHandle', wintypes.BOOL),
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

_SetConsoleScreenBufferInfoEx = windll.kernel32.SetConsoleScreenBufferInfoEx
_SetConsoleScreenBufferInfoEx.argtypes = (wintypes.HANDLE, POINTER(CONSOLE_SCREEN_BUFFER_INFOEX))

_GetConsoleScreenBufferInfoEx = windll.kernel32.GetConsoleScreenBufferInfoEx
_GetConsoleScreenBufferInfoEx.argtypes = (wintypes.HANDLE, POINTER(CONSOLE_SCREEN_BUFFER_INFOEX))

_ScrollConsoleScreenBuffer = windll.kernel32.ScrollConsoleScreenBufferW
_ScrollConsoleScreenBuffer.argtypes = (
    wintypes.HANDLE,
    POINTER(wintypes.SMALL_RECT),
    POINTER(wintypes.SMALL_RECT),
    wintypes._COORD,
    POINTER(CHAR_INFO),
)

_CreateConsoleScreenBuffer = windll.kernel32.CreateConsoleScreenBuffer
_CreateConsoleScreenBuffer.argtypes = (
    wintypes.DWORD,
    wintypes.DWORD,
    POINTER(SECURITY_ATTRIBUTES),
    wintypes.DWORD,
    wintypes.LPVOID
)
_CreateConsoleScreenBuffer.restype = wintypes.HANDLE

_SetConsoleActiveScreenBuffer = windll.kernel32.SetConsoleActiveScreenBuffer
_SetConsoleActiveScreenBuffer.argtypes = (wintypes.HANDLE,)
_SetConsoleActiveScreenBuffer.restype = wintypes.BOOL


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

_SetConsoleMode = windll.kernel32.SetConsoleMode
_SetConsoleMode.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
)

_GetConsoleMode = windll.kernel32.GetConsoleMode
_GetConsoleMode.argtypes = (
    wintypes.HANDLE,
    POINTER(wintypes.DWORD),
)
_GetConsoleMode.restype = wintypes.BOOL


PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
_SetConsoleCtrlHandler = windll.kernel32.SetConsoleCtrlHandler
_SetConsoleCtrlHandler.argtypes = (
    PHANDLER_ROUTINE,
    wintypes.BOOL,
)
_SetConsoleCtrlHandler.restype = wintypes.BOOL


def GetConsoleScreenBufferInfo(handle):
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    _GetConsoleScreenBufferInfo(handle, byref(csbi))
    return csbi

def GetConsoleScreenBufferInfoEx(handle):
    csbie = CONSOLE_SCREEN_BUFFER_INFOEX()
    csbie.cbSize = wintypes.ULONG(ctypes.sizeof(csbie))
    _GetConsoleScreenBufferInfoEx(handle, byref(csbie))
    # work around Windows bug
    # see https://stackoverflow.com/questions/35901572/setconsolescreenbufferinfoex-bug
    csbie.srWindow.Bottom += 1
    csbie.srWindow.Right += 1
    return csbie

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

def GetConsoleMode(handle):
    mode = wintypes.DWORD()
    _GetConsoleMode(handle, mode)
    return mode


# standard stream constants
# these remain unchanged if we switch to another screen buffer
HSTDIN = _GetStdHandle(-10)
HSTDOUT = _GetStdHandle(-11)
HSTDERR = _GetStdHandle(-12)


class _ConsoleWriter:
    """Singleton to manage writing to console and consequent scrolling."""

    _overflow = False

    @classmethod
    def write(cls, handle, unistr):
        """Write character to console, avoid scroll on bottom line."""
        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        _GetConsoleScreenBufferInfo(handle, byref(csbi))
        col, row = csbi.dwCursorPosition.X, csbi.dwCursorPosition.Y
        width, height = csbi.dwSize.X, csbi.dwSize.Y
        for ch in unistr:
            if (col >= width - 1 and ch not in (u'\n', u'\b', u'\r') and not cls._overflow):
                ci = CHAR_INFO(ch, csbi.wAttributes)
                # do not advance cursor if we're on the last position of the
                # screen buffer, to avoid unwanted scrolling.
                _WriteConsoleOutputW(
                    handle, byref(ci), wintypes._COORD(1, 1), wintypes._COORD(0, 0),
                    wintypes.SMALL_RECT(col, row, col, row)
                )
            else:
                if cls._overflow and ch not in (u'\n', u'\r', u'\b'):
                    _WriteConsoleW(
                        handle, u'\r\n', 1,
                        byref(wintypes.DWORD()), byref(wintypes.DWORD())
                    )
                    col = 0
                    cls._overflow = False
                _WriteConsoleW(
                    handle, ch, 1,
                    byref(wintypes.DWORD()), byref(wintypes.DWORD())
                )
            # if we don't include \n here we get glitches on regular console writes
            # is it necessary to treat CR and LF separately *in raw mode*?
            # i.e. in raw mode,  shouldn't LF just move a line down without changing the column?
            if ch in (u'\r', u'\n'):
                col = 0
                cls._overflow = False
            elif ch == u'\b':
                col = max(col-1, 0)
                cls._overflow = False
            else:
                col = min(col+1, width-1)


##############################################################################
# console class

@PHANDLER_ROUTINE
def _ctrl_handler(fdwCtrlType):
    """Handle Ctrl-Break event."""
    # CTRL_BREAK_EVENT
    return (fdwCtrlType == 1)


class Win32Console(object):
    """Win32API-based console implementation."""

    def __init__(self):
        """Set up console"""
        # preserve original settings
        self._orig_csbie = GetConsoleScreenBufferInfoEx(HSTDOUT)
        self._orig_stdin_mode = GetConsoleMode(HSTDIN)
        self._attrs = self._orig_csbie.wAttributes
        # input
        self._input_buffer = deque()
        self._echo = True
        self._save_stdout = None
        # standard streams - these may change in alternative screen buffe rmode
        self._hstdin = HSTDIN
        self._hstdout = HSTDOUT
        self._hstderr = HSTDERR

    def set_raw(self):
        """Enter raw terminal mode (no echo, don't exit on ctrl-C)."""
        self._echo = False
        # unset ENABLE_PROCESSED_INPUT
        _SetConsoleMode(self._hstdin, wintypes.DWORD(self._orig_stdin_mode.value & ~0x0001))
        # don't exit on ctrl-Break
        _SetConsoleCtrlHandler(_ctrl_handler, True)

    def unset_raw(self):
        """Leave raw terminal mode."""
        self._echo = True
        _SetConsoleMode(self._hstdin, self._orig_stdin_mode)

    def start_screen(self):
        """Enter full-screen/application mode."""
        # https://docs.microsoft.com/en-us/windows/console/reading-and-writing-blocks-of-characters-and-attributes
        new_buffer = _CreateConsoleScreenBuffer(
            wintypes.DWORD(0xc0000000), # GENERIC_READ | GENERIC_WRITE
            wintypes.DWORD(0x3), # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            wintypes.DWORD(1), # CONSOLE_TEXTMODE_BUFFER
            None
        )
        _SetConsoleActiveScreenBuffer(new_buffer)
        self._save_stdout, self._hstdout = self._hstdout, new_buffer
        self.set_raw()

    def close_screen(self):
        """Leave full-screen/application mode."""
        self.unset_raw()
        self.reset()
        self._hstdout = self._save_stdout
        _SetConsoleActiveScreenBuffer(self._hstdout)

    def key_pressed(self):
        """key pressed on keyboard."""
        return msvcrt.kbhit()

    def set_caption(self, caption):
        """Set terminal caption."""
        _SetConsoleTitleW(caption)

    def resize(self, height, width):
        """Resize terminal."""
        csbi = GetConsoleScreenBufferInfo(self._hstdout)
        # SetConsoleScreenBufferSize can't make the buffer smaller than the window
        # SetConsoleWindowInfo can't make the window larger than the buffer (in either direction)
        # allow for both shrinking and growing by calling one of them twice,
        # for each direction separately
        new_size = wintypes._COORD(width, csbi.dwSize.Y)
        new_window = wintypes.SMALL_RECT(0, 0, width-1, csbi.dwSize.Y-1)
        _SetConsoleScreenBufferSize(self._hstdout, new_size)
        _SetConsoleWindowInfo(self._hstdout, True, new_window)
        _SetConsoleScreenBufferSize(self._hstdout, new_size)
        new_size = wintypes._COORD(width, height)
        new_window = wintypes.SMALL_RECT(0, 0, width-1, height-1)
        _SetConsoleScreenBufferSize(self._hstdout, new_size)
        _SetConsoleWindowInfo(self._hstdout, True, new_window)
        _SetConsoleScreenBufferSize(self._hstdout, new_size)

    ##########################################################################
    # output

    def write(self, unistr):
        """Write (unicode) text to the console."""
        _ConsoleWriter.write(self._hstdout, unistr)

    def clear(self):
        """Clear the screen."""
        csbi = GetConsoleScreenBufferInfo(self._hstdout)
        # fill the entire screen with blanks
        FillConsoleOutputCharacter(
            self._hstdout, u' ', csbi.dwSize.X * csbi.dwSize.Y, wintypes._COORD(0, 0)
        )
        # now set the buffer's attributes accordingly
        FillConsoleOutputAttribute(
            self._hstdout, self._attrs, csbi.dwSize.X * csbi.dwSize.Y, wintypes._COORD(0, 0)
        )
        _SetConsoleCursorPosition(self._hstdout, wintypes._COORD(0, 0))

    def clear_row(self, width=None):
        """Clear the current row."""
        csbi = GetConsoleScreenBufferInfo(self._hstdout)
        from_coord = wintypes._COORD(0, csbi.dwCursorPosition.Y)
        # fill the entire row with blanks
        if width is None:
            width = csbi.dwSize.X
        FillConsoleOutputCharacter(self._hstdout, u' ', width, from_coord)
        # now set the buffer's attributes accordingly
        FillConsoleOutputAttribute(self._hstdout, self._attrs, width, from_coord)

    def set_cursor_colour(self, colour):
        """Set the current cursor colour attribute - not supported."""

    def show_cursor(self, block=False):
        """Show the cursor."""
        curs_info = GetConsoleCursorInfo(self._hstdout)
        curs_info.bVisible = True
        curs_info.dwSize = 100 if block else 20
        SetConsoleCursorInfo(self._hstdout, curs_info)

    def hide_cursor(self):
        """Hide the cursor."""
        curs_info = GetConsoleCursorInfo(self._hstdout)
        curs_info.bVisible = False
        SetConsoleCursorInfo(self._hstdout, curs_info)

    def move_cursor_to(self, row, col):
        """Move cursor to a new position (1,1 is top left)."""
        csbi = GetConsoleScreenBufferInfo(self._hstdout)
        row, col = row-1, col-1
        while col >= csbi.dwSize.X:
            col -= csbi.dwSize.X
            row += 1
        while col < 0:
            col += csbi.dwSize.X
            row -= 1
        # If the position is out of range, do nothing.
        if row >= 0 and col >= 0:
            _SetConsoleCursorPosition(self._hstdout, wintypes._COORD(col, row))

    def scroll(self, top, bottom, rows):
        """Scroll the region between top and bottom one row up (-) or down (+)."""
        if not rows:
            return
        # use zero-based indexing
        start, stop = top-1, bottom-1
        # we're using opposuite sign conventions
        csbi = GetConsoleScreenBufferInfo(self._hstdout)
        # absolute position of window in screen buffer
        # interpret other coordinates as relative to the window
        window = csbi.srWindow
        # scroll region
        clip_rect = wintypes.SMALL_RECT(
            window.Left, window.Top + start, window.Right, window.Top + stop
        )
        if rows < 0:
            # minus signs since rows is a negative number
            region = wintypes.SMALL_RECT(window.Left, window.Top - rows, window.Right, window.Bottom)
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
            ScrollConsoleScreenBuffer(self._hstdout, region, clip_rect, new_pos, u' ', self._attrs)
            # and then scroll the bottom back down
            new_pos.Y = window.Bottom
            region.Top = bottom-1
            ScrollConsoleScreenBuffer(self._hstdout, region, clip_rect, new_pos, u' ', self._attrs)
        else:
            ScrollConsoleScreenBuffer(self._hstdout, region, clip_rect, new_pos, u' ', self._attrs)

    def reset(self):
        """Reset to default attributes."""
        _SetConsoleScreenBufferInfoEx(self._hstdout, byref(self._orig_csbie))
        self._attrs = self._orig_csbie.wAttributes
        self.show_cursor()

    def set_attributes(self, fore, back, blink, underline):
        """Set current attributes."""
        self._attrs = fore % 8 + back * 16 + (BRIGHT if fore > 8 else NORMAL)
        _SetConsoleTextAttribute(self._hstdout, self._attrs)

    def set_palette_entry(self, attr, red, green, blue):
        """Set palette entry for attribute (0--16)."""
        csbie = GetConsoleScreenBufferInfoEx(self._hstdout)
        csbie.ColorTable[attr] = (
            0x00010000 * blue + 0x00000100 * green + 0x00000001 * red
        )
        _SetConsoleScreenBufferInfoEx(self._hstdout, byref(csbie))

    ##########################################################################
    # input

    def read_key(self):
        """
        Read keypress from console. Non-blocking.
        Returns tuple (unicode, keycode, set of mods)
        """
        self._fill_buffer(blocking=False)
        if not self._input_buffer:
            return (u'', None, {})
        return self._input_buffer.popleft()

    def read_all_chars(self):
        """Read all characters in the buffer."""
        self._fill_buffer(blocking=False)
        closed = False
        if self._input_buffer and self._input_buffer[-1][0] == u'\x1a':
            closed = True
            self._input_buffer.pop()
            if not self._input_buffer:
                return None
        output = u''.join(
            _char for _char, _, _ in self._input_buffer
        )
        self._input_buffer.clear()
        if closed:
            self._input_buffer.append(u'\x1a')
        return output

    def _fill_buffer(self, blocking):
        """Interpret all key events."""
        while True:
            nevents = wintypes.DWORD()
            _GetNumberOfConsoleInputEvents(self._hstdin, byref(nevents))
            if not nevents.value and not blocking:
                return
            # only ever block on first loop
            blocking = False
            if nevents.value > 0:
                input_buffer = (INPUT_RECORD * nevents.value)()
                nread = wintypes.DWORD()
                _ReadConsoleInputW(
                    self._hstdin,
                    cast(input_buffer, POINTER(INPUT_RECORD)),
                    nevents.value, byref(nread)
                )
                for event in input_buffer:
                    if event.EventType != 1: # KEY_EVENT
                        continue
                    char, key, mods = self._translate_event(event)
                    if char or key:
                        self._input_buffer.append((char, key, mods))
                        if char == u'\x1a':
                            # ctrl-z is end of input on windows console
                            return
                        if self._echo:
                            _ConsoleWriter.write(self._hstdout, char.replace(u'\r', u'\n'))
            time.sleep(0.01)

    def _translate_event(self, event):
        char = event.KeyEvent.UnicodeChar
        key = event.KeyEvent.wVirtualKeyCode
        control = event.KeyEvent.dwControlKeyState
        if char == u'\0':
            # windows uses null-terminated strings so \0 means no output
            char = u''
        if not event.KeyEvent.bKeyDown:
            # key-up event for unicode Alt+HEX input
            if event.KeyEvent.wVirtualKeyCode == KEYS.ALT:
                return char, None, set()
            # ignore other key-up events
            return u'', None, set()
        # decode modifier bit flags
        mods = set(key for key, mask in MODS.items() if control & mask)
        key = VK_TO_KEY.get(key, None)
        return char, key, mods


def _has_console():
    """Determine if we have a console attached or are a GUI app."""
    try:
        return bool(_GetConsoleMode(HSTDOUT, byref(wintypes.DWORD())))
    except Exception as e:
        return False


IS_CONSOLE_APP = _has_console()

if _has_console():
    console = Win32Console()
else:
    console = None


##############################################################################
# non-blocking input

def read_all_available(stream):
    """Read all available bytes or unicode from a stream; nonblocking; None if closed."""
    # are we're reading from (wrapped) stdin or not?
    if hasattr(stream, 'isatty') and stream.isatty():
        # this is shaky - try to identify unicode vs bytes stream
        is_unicode_stream = hasattr(stream, 'buffer')
        # console always produces unicode
        unistr = console.read_all_chars()
        # but convert to bytes if the tty stream provides was a bytes stream
        if is_unicode_stream or unistr is None:
            return unistr
        else:
            return unistr.encode(stdio.stdin.encoding, 'replace')
    else:
        # this would work on unix too
        # just read the whole file and be done with it
        # bytes or unicode, depends on stream
        return stream.read() or None


##############################################################################
# standard i/o

if PY2: # pragma: no cover

    class _StreamWrapper(object):
        """Delegating stream wrapper."""

        def __init__(self, stream, handle, encoding='utf-8'):
            self._wrapped = stream
            self._handle = handle
            self.encoding = encoding

        def __getattr__(self, attr):
            return getattr(self._wrapped, attr)

        def __getstate__(self):
            return vars(self)

        def __setstate__(self, stdict):
            return vars(self).update(stdict)


    class _ConsoleOutput(_StreamWrapper):
        """Bytes stream wrapper using Unicode API, to replace Python2 sys.stdout."""

        def write(self, bytestr):
            if not isinstance(bytestr, bytes):
                raise TypeError('write() argument must be bytes, not %s' % type(bytestr))
            unistr = bytestr.decode(self.encoding, errors='replace')
            _ConsoleWriter.write(self._handle, unistr)


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
                output.append(key.encode(self.encoding, errors='replace'))
            return bytes(output)


class StdIO(StdIOBase):
    """Holds standard unicode streams."""

    if PY2: # pragma: no cover
        def _attach_stdin(self):
            if sys.stdin.isatty():
                self.stdin = self._wrap_input_stream(_ConsoleInput())
            else:
                self.stdin = self._wrap_input_stream(sys.stdin)

        def _attach_output_stream(self, stream_name, redirected=False):
            stream = getattr(sys, '__%s__' % (stream_name,))
            handle = {'stdout': HSTDOUT, 'stderr': HSTDERR}[stream_name]
            if stream.isatty() and not redirected:
                new_stream = self._wrap_output_stream(_ConsoleOutput(stream, handle))
            else:
                encoding = 'utf-8' if redirected else None
                new_stream = self._wrap_output_stream(stream, encoding)
            setattr(self, stream_name, new_stream)

stdio = StdIO()


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
