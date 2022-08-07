"""
PC-BASIC - inputs.keyboard
Keyboard handling

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
from contextlib import contextmanager

from ...compat import iterchar, int2byte

from ..base import error
from ..base import scancode
from ..base import signals
from ..base.eascii import as_bytes as ea
from ..base.eascii import as_unicode as uea


# bit flags for modifier keys - these are exposed via peek(1047) in low memory
# sticky modifiers
TOGGLE = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10
}

# nonsticky modifiers
MODIFIER = {
    scancode.ALT: 0x8, scancode.CTRL: 0x4,
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1
}

# default function key eascii codes for KEY autotext.
FUNCTION_KEY = {
    ea.F1: 0, ea.F2: 1, ea.F3: 2, ea.F4: 3,
    ea.F5: 4, ea.F6: 5, ea.F7: 6, ea.F8: 7,
    ea.F9: 8, ea.F10: 9, ea.F11: 10, ea.F12: 11
}

# numeric keypad
KEYPAD = {
    scancode.KP0: b'0', scancode.KP1: b'1', scancode.KP2: b'2', scancode.KP3: b'3',
    scancode.KP4: b'4', scancode.KP5: b'5', scancode.KP6: b'6', scancode.KP7: b'7',
    scancode.KP8: b'8', scancode.KP9: b'9'
}

# function-key macros
DEFAULT_MACROS = (
    b'LIST ', b'RUN\r', b'LOAD"', b'SAVE"', b'CONT\r', b',"LPT1:"\r',
    b'TRON\r', b'TROFF\r', b'KEY ', b'SCREEN 0,0,0\r', b'', b''
)

# short beep (0.1s at 800Hz) emitted if buffer is full
FULL_TONE = (0, 800, 0.01, False, 15)


###############################################################################
# keyboard ring buffer

class KeyboardBuffer(object):
    """Quirky emulated ring buffer for keystrokes."""

    def __init__(self, queues, ring_length, check_full):
        """Initialise to given length."""
        self._queues = queues
        # buffer holds tuples (eascii/codepage, scancode, modifier)
        self._buffer = [(b'\0\0', 0)] * ring_length
        self._ring_length = ring_length
        self._start = ring_length
        # check if ring is full
        self._check_full = check_full

    @contextmanager
    def ignore_limit(self):
        """Enable/diable buffer limit check."""
        save, self._check_full = self._check_full, False
        yield
        self._check_full = save

    def append(self, cp_c, scan):
        """Append a single keystroke with eascii/codepage, scancode, modifier."""
        # if check_full is off, we pretend the ring buffer is infinite
        # this is for inserting keystrokes and pasting text into the emulator
        if cp_c:
            if self._check_full and len(self._buffer) - self._start >= self._ring_length-1:
                # when buffer is full, GW-BASIC inserts a \r at the end but doesn't count it
                self._buffer[self._start-1] = (b'\r', scancode.RETURN)
                # emit a sound signal; keystroke is dropped
                self._queues.audio.put(signals.Event(signals.AUDIO_TONE, FULL_TONE))
            else:
                self._buffer.append((cp_c, scan))

    def getc(self):
        """Read a keystroke as eascii/codepage."""
        try:
            c = self._buffer[self._start][0]
        except IndexError:
            c = b''
        else:
            self._start += 1
        return c

    def peek(self):
        """Show top keystroke in keyboard buffer as eascii/codepage."""
        try:
            return self._buffer[self._start][0]
        except IndexError:
            return b''

    def _ring_index(self, index):
        """Get index for ring position."""
        diff = len(self._buffer) % self._ring_length - index
        offset = len(self._buffer) - diff
        if diff <= 0:
            offset -= self._ring_length
        return offset

    @property
    def length(self):
        """Return the number of keystrokes in the buffer."""
        return min(self._ring_length, len(self._buffer) - self._start)

    @property
    def empty(self):
        """True if no keystrokes in buffer."""
        return self._start >= len(self._buffer)

    @property
    def start(self):
        """Ring buffer starting index."""
        return self._start % self._ring_length

    @property
    def stop(self):
        """Ring buffer stopping index."""
        return (self._start + self.length) % self._ring_length

    def ring_read(self, index):
        """Read character at position i in ring as eascii/codepage."""
        return self._buffer[self._ring_index(index)]

    def ring_write(self, index, c, scan):
        """Write character at position i in ring as eascii/codepage."""
        self._buffer[self._ring_index(index)] = (c, scan)

    def ring_set_boundaries(self, newstart, newstop):
        """Set start and stop index."""
        length = (newstop - newstart) % self._ring_length
        # rotate buffer to account for new start and stop
        # these are between length - ring_length and length
        start_index = self._ring_index(newstart)
        stop_index = self._ring_index(newstop)
        start = self._ring_index(self._start)
        # drop any extended buffer beyond ring limits
        self._buffer = self._buffer[:self._start + self._ring_length]
        # cut to ring limits, we should be exactly the right size
        start -= len(self._buffer) - self._ring_length
        self._buffer = self._buffer[-self._ring_length:]
        # rotate so that the stop index is at the end
        shift = len(self._buffer[start+length:])
        self._buffer = self._buffer[start+length:] + self._buffer[:start+length]
        start += shift
        start = start % self._ring_length
        # insert zeros before buffer to get the correct modulo
        while start % self._ring_length != newstart:
            start += 1
            self._buffer = [(b'\0\0', 0)] + self._buffer
        self._start = start


###############################################################################
# keyboard operations

def _iter_keystrokes(ueascii_seq):
    """Iterate over e-ascii/unicode sequences."""
    out = u''
    for char in ueascii_seq:
        if out or char != u'\0':
            yield out + char
            out = u''
        elif char == u'\0':
            # eascii code is \0 plus one char
            out = char


class Keyboard(object):
    """Keyboard handling."""

    def __init__(self, queues, values, codepage, check_full):
        """Initilise keyboard state."""
        self._values = values
        # needed for wait() in wait_char()
        self._queues = queues
        # key queue (holds bytes); ring buffer of length 16
        self.buf = KeyboardBuffer(queues, 16, check_full)
        # INP(&H60) scancode
        self.last_scancode = 0
        # active status of caps, num, scroll, alt, ctrl, shift modifiers
        self.mod = 0
        # store for alt+keypad ascii insertion
        self.keypad_ascii = b''
        # ignore caps lock, let OS handle it
        # this is now switched off hard-coded, but logic remains for now
        self._ignore_caps = True
        # pre-inserted keystrings
        self._codepage = codepage
        # stream buffer
        self._stream_buffer = deque()
        # redirected input stream has closed
        self._input_closed = False
        # expansion buffer for keyboard macros
        # expansion vessel holds codepage chars
        self._expansion_vessel = []
        # f-key macros
        self._key_replace = list(DEFAULT_MACROS)

    # event handler

    def check_input(self, signal):
        """Handle keyboard input signals and clipboard paste."""
        if signal.event_type == signals.KEYB_DOWN:
            # params is e-ASCII/unicode character sequence, scancode, modifier
            self._key_down(*signal.params)
        elif signal.event_type == signals.KEYB_UP:
            self._key_up(*signal.params)
        elif signal.event_type == signals.STREAM_CHAR:
            # params is a unicode sequence
            self._stream_chars(*signal.params)
        elif signal.event_type == signals.STREAM_CLOSED:
            self._close_input()
        elif signal.event_type == signals.CLIP_PASTE:
            self._stream_chars(*signal.params)
        else:
            return False
        return True

    def _key_down(self, c, scan, mods):
        """Insert a key-down event by eascii/unicode, scancode and modifiers."""
        if scan is not None:
            self.last_scancode = scan
        # update ephemeral modifier status at every keypress
        # mods is a list of scancodes; OR together the known modifiers
        self.mod &= ~(
            MODIFIER[scancode.CTRL] | MODIFIER[scancode.ALT] |
            MODIFIER[scancode.LSHIFT] | MODIFIER[scancode.RSHIFT]
        )
        if mods:
            for m in mods:
                self.mod |= MODIFIER.get(m, 0)
        # set toggle-key modifier status
        # these are triggered by keydown events
        try:
            self.mod ^= TOGGLE[scan]
        except KeyError:
            pass
        # alt+keypad ascii replacement
        if mods and (scancode.ALT in mods):
            try:
                self.keypad_ascii += KEYPAD[scan]
                return
            except KeyError:
                pass
        if (
                self.mod & TOGGLE[scancode.CAPSLOCK]
                and not self._ignore_caps and len(c) == 1
            ):
            c = c.swapcase()
        self.buf.append(self._codepage.unicode_to_bytes(c), scan)

    def _key_up(self, scan):
        """Insert a key-up event."""
        if scan is not None:
            self.last_scancode = 0x80 + scan
        try:
            # switch off ephemeral modifiers
            self.mod &= ~MODIFIER[scan]
        except KeyError:
           pass
        # ALT+keycode
        if scan == scancode.ALT and self.keypad_ascii:
            char = int2byte(int(self.keypad_ascii)%256)
            if char == b'\0':
                char = b'\0\0'
            self.buf.append(char, None)
            self.keypad_ascii = b''

    def _stream_chars(self, us):
        """Insert eascii/unicode string into stream buffer."""
        for ea_char in _iter_keystrokes(us):
            ea_cp = self._codepage.unicode_to_bytes(ea_char)
            # don't append empty strings arising from unknown unicode
            # as this will be interpreted as end of stream, terminating the interpreter
            if ea_cp:
                self._stream_buffer.append(ea_cp)

    def inject_keystrokes(self, keystring):
        """Insert eascii/unicode string into keyboard buffer."""
        with self.buf.ignore_limit():
            for ea_char in _iter_keystrokes(keystring):
                self.buf.append(self._codepage.unicode_to_bytes(ea_char), None)

    def _close_input(self):
        """Signal that input stream has closed."""
        self._input_closed = True

    # macros

    def set_macro(self, num, macro):
        """Set macro for given function key."""
        # NUL terminates macro string, rest is ignored
        # macro starting with NUL is empty macro
        self._key_replace[num-1] = macro.split(b'\0', 1)[0]

    def get_macro(self, num):
        """Get macro for given function key."""
        return self._key_replace[num]

    # character retrieval

    def wait_char(self, keyboard_only=False):
        """Block until character appears in keyboard queue or stream."""
        # if input stream has closed, don't wait but return empty
        # which will tell the Editor to close
        # except if we're waiting for KYBD: input
        while (
                (not self._expansion_vessel) and (self.buf.empty) and (
                    keyboard_only or (not self._input_closed and not self._stream_buffer)
                )
            ):
            self._queues.wait()

    def _read_kybd_byte(self, expand=True):
        """Read one byte from keyboard buffer, expanding macros if required."""
        try:
            return self._expansion_vessel.pop(0)
        except IndexError:
            pass
        c = self.buf.getc()
        if not expand or c not in FUNCTION_KEY:
            return c
        # function key macro expansion
        self._expansion_vessel = list(iterchar(self._key_replace[FUNCTION_KEY[c]]))
        try:
            return self._expansion_vessel.pop(0)
        except IndexError:
            # function macro has been redefined as empty: return scancode
            # e.g. KEY 1, "" enables catching F1 with INKEY$
            return c

    def inkey_(self, args):
        """INKEY$: read one byte from keyboard or stream; nonblocking."""
        list(args)
        inkey = self.read_byte()
        return self._values.new_string().from_str(inkey)

    def read_byte(self):
        """Read one byte from keyboard or stream; nonblocking."""
        # wait a tick to reduce load in loops
        self._queues.wait()
        inkey = self._read_kybd_byte()
        if not inkey and self._stream_buffer:
            inkey = self._stream_buffer.popleft()
        return inkey

    def read_bytes_block(self, n):
        """Read bytes from keyboard or stream; blocking."""
        word = []
        for _ in range(n):
            self.wait_char(keyboard_only=False)
            word.append(self.read_byte())
        print
        return b''.join(word)

    def peek_byte_kybd_file(self):
        """Peek from keyboard only; for KYBD: files; blocking."""
        self.wait_char(keyboard_only=True)
        return self.buf.peek()

    def read_bytes_kybd_file(self, num):
        """Read num bytes from keyboard only; for KYBD: files; blocking."""
        word = []
        for _ in range(num):
            self.wait_char(keyboard_only=True)
            word.append(self._read_kybd_byte(expand=False))
        return word

    def get_fullchar(self, expand=True):
        """Read one (sbcs or dbcs) full character; nonblocking."""
        c = self._read_kybd_byte(expand)
        # insert dbcs chars from keyboard buffer two bytes at a time
        if (c in self._codepage.lead and self.buf.peek() in self._codepage.trail):
            c += self._read_kybd_byte(expand)
        if not c and self._stream_buffer:
            c = self._stream_buffer.popleft()
            if (c in self._codepage.lead and self._stream_buffer and
                        self._stream_buffer[0] in self._codepage.trail):
                c += self._stream_buffer.popleft()
        return c

    def get_fullchar_block(self, expand=True):
        """Read one (sbcs or dbcs) full character; blocking."""
        self.wait_char()
        return self.get_fullchar(expand)
