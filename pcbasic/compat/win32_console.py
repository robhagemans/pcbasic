
# only needed for Python2

import sys
import ctypes
import codecs
import time
from ctypes import windll, wintypes, POINTER, byref, Structure, cast

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12

_GetStdHandle = windll.kernel32.GetStdHandle
_GetStdHandle.argtypes = (wintypes.DWORD,)
_GetStdHandle.restype = wintypes.HANDLE

_WriteConsoleW = windll.kernel32.WriteConsoleW
_WriteConsoleW.argtypes = (
    wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD, POINTER(wintypes.DWORD), wintypes.LPVOID
)

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

KEY_EVENT = 1
VK_MENU = 0x12

KEY_CODE_TO_ANSI = {
    0x21: u'\x1b[5~', # VK_PRIOR, page up
    0x22: u'\x1b[6~', # VK_NEXT, page down
    0x23: u'\x1bOF', # VK_END
    0x24: u'\x1bOH', # VK_HOME
    0x25: u'\x1b[D', # VK_LEFT
    0x26: u'\x1b[A', # VK_UP
    0x27: u'\x1b[C', # VK_RIGHT
    0x28: u'\x1b[B', # VK_DOWN
    0x2d: u'\x1b[2~', # VK_INSERT
    0x2e: u'\x1b[3~', # VK_DELETE
    0x70: u'\x1bOP', # VK_F1
    0x71: u'\x1bOQ', # VK_F2
    0x72: u'\x1bOR', # VK_F3
    0x73: u'\x1bOS', # VK_F4
    0x74: u'\x1b[15~', # VK_F5
    0x75: u'\x1b[17~', # VK_F6
    0x76: u'\x1b[18~', # VK_F7
    0x77: u'\x1b[19~', # VK_F8
    0x78: u'\x1b[20~', # VK_F9
    0x79: u'\x1b[21~', # VK_F10
    0x7a: u'\x1b[23~', # VK_F11
    0x7b: u'\x1b[24~', # VK_F12
}


_ReadConsoleInputW = windll.kernel32.ReadConsoleInputW
_ReadConsoleInputW.argtypes = (
    wintypes.HANDLE, POINTER(INPUT_RECORD), wintypes.DWORD, POINTER(wintypes.DWORD)
)

_GetNumberOfConsoleInputEvents = windll.kernel32.GetNumberOfConsoleInputEvents
_GetNumberOfConsoleInputEvents.argtypes = (wintypes.HANDLE, POINTER(wintypes.DWORD))


class _StreamWrapper(object):
    """Delegating stream wrapper."""

    def __init__(self, stream, nhandle, encoding='utf-8'):
        self._wrapped = stream
        self._handle = _GetStdHandle(nhandle)
        self.encoding = encoding

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)


class ConsoleOutput(_StreamWrapper):
    """Bytes stream wrapper using Unicode API, to replace Python2 sys.stdout."""

    def write(self, bytestr):
        if not isinstance(bytestr, bytes):
            raise TypeError('write() argument must be bytes, not %s' % type(bytestr))
        unistr = bytestr.decode(self.encoding)
        _WriteConsoleW(
            self._handle, unistr, len(unistr),
            byref(wintypes.DWORD()), byref(wintypes.DWORD())
        )


class ConsoleInput(_StreamWrapper):
    """Bytes stream wrapper using Unicode API, to replace Python2 sys.stdin."""

    def __init__(self, encoding='utf-8'):
        _StreamWrapper.__init__(self, sys.stdin, STD_INPUT_HANDLE, encoding)
        self._echo_handle = _GetStdHandle(STD_OUTPUT_HANDLE)
        self._bytes_buffer = bytearray()
        # public field - console echo
        self.echo = True

    def read(self, size=-1, blocking=True):
        self._fill_buffer(size, blocking)
        if size < 0:
            output, self._bytes_buffer = self._bytes_buffer, bytearray()
        else:
            output, self._bytes_buffer = self._bytes_buffer[:size], self._bytes_buffer[size:]
        return bytes(output)

    def _fill_buffer(self, size, blocking):
        while size < 0 or len(self._bytes_buffer) < size:
            nevents = wintypes.DWORD()
            _GetNumberOfConsoleInputEvents(_GetStdHandle(STD_INPUT_HANDLE), byref(nevents))
            if not nevents.value and not blocking:
                return
            if nevents.value > 0:
                input_buffer = (INPUT_RECORD * nevents.value)()
                nread = wintypes.DWORD()
                _ReadConsoleInputW(
                    _GetStdHandle(STD_INPUT_HANDLE),
                    cast(input_buffer, POINTER(INPUT_RECORD)),
                    nevents.value, byref(nread)
                )
                for event in input_buffer:
                    if event.EventType != KEY_EVENT:
                        continue
                    char = self._translate_event(event)
                    if char:
                        self._bytes_buffer += char.encode(self.encoding)
                        if self.echo:
                            _WriteConsoleW(
                                self._echo_handle, u'\n' if char == u'\r' else char, len(char),
                                byref(wintypes.DWORD()), byref(wintypes.DWORD())
                            )
                        if char == u'\x1a':
                            # ctrl-z is end of input on windows console
                            return
            time.sleep(0.01)

    def _translate_event(self, event):
        char = event.KeyEvent.UnicodeChar
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
        else:
            key_code = event.KeyEvent.wVirtualKeyCode
            return KEY_CODE_TO_ANSI.get(key_code, char)


# Python2-compatible standard bytes streams

if sys.stdin.isatty():
    bstdin = ConsoleInput()
else:
    bstdin = sys.stdin

if sys.stdout.isatty():
    bstdout = ConsoleOutput(sys.stdout, STD_OUTPUT_HANDLE)
else:
    bstdout = sys.stdout

if sys.stderr.isatty():
    bstderr = ConsoleOutput(sys.stderr, STD_ERROR_HANDLE)
else:
    bstderr = sys.stderr
