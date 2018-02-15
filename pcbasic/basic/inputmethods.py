"""
PC-BASIC - inputmethods.py
Keyboard, pen and joystick handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime

from .base import error
from .base import scancode
from .base import tokens as tk
from .base import signals
from .base.eascii import as_bytes as ea
from .base.eascii import as_unicode as uea
from . import values


# bit flags for modifier keys
# sticky modifiers
TOGGLE = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10}
# nonsticky modifiers
MODIFIER = {
    scancode.ALT: 0x8, scancode.CTRL: 0x4,
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1}

# default function key eascii codes for KEY autotext.
FUNCTION_KEY = {
    ea.F1: 0, ea.F2: 1, ea.F3: 2, ea.F4: 3,
    ea.F5: 4, ea.F6: 5, ea.F7: 6, ea.F8: 7,
    ea.F9: 8, ea.F10: 9, ea.F11: 10, ea.F12: 11}



###############################################################################
# clipboard copy & print screen handler

# clipboard copy & print screen are special cases:
# they to handle an input signal, read the screen
# and write the text to an output queue or file
# independently of what BASIC is doing

class ScreenCopyHandler(object):
    """Event handler for clipboard copy and print screen."""

    def __init__(self, screen, lpt1_file):
        """Initialise copy handler."""
        self._screen = screen
        self._lpt1_file = lpt1_file

    def check_input(self, signal):
        """Handle input signals."""
        if signal.event_type == signals.CLIP_COPY:
            self._screen.copy_clipboard(*signal.params)
            return True
        elif signal.event_type == signals.KEYB_DOWN:
            c, scan, mod = signal.params
            if scan == scancode.PRINT and (
                    scancode.LSHIFT in mod or scancode.RSHIFT in mod):
                # shift+printscreen triggers a print screen
                self._screen.print_screen(self._lpt1_file)
                return True
        return False


###############################################################################
# keyboard queue

class KeyboardBuffer(object):
    """Quirky emulated ring buffer for keystrokes."""

    _default_macros = (
        'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r',
        'TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '')

    # short beep (0.1s at 800Hz) emitted if buffer is full
    _full_tone = signals.Event(signals.AUDIO_TONE, [0, 800, 0.01, 1, False, 15])

    def __init__(self, queues, ring_length):
        """Initialise to given length."""
        # buffer holds tuples (eascii/codepage, scancode, modifier)
        self.buffer = []
        self.ring_length = ring_length
        self.start = 0
        # expansion buffer for keyboard macros
        # expansion vessel holds codepage chars
        self.expansion_vessel = []
        self._queues = queues
        # f-key macros
        self.key_replace = list(self._default_macros)

    def length(self):
        """Return the number of keystrokes in the buffer."""
        return min(self.ring_length, len(self.buffer))

    def is_empty(self):
        """True if no keystrokes in buffer."""
        return len(self.buffer) == 0 and len(self.expansion_vessel) == 0

    def insert(self, cp_s, check_full=True):
        """Append a string of e-ascii/codepage as keystrokes. Does not trigger events (we have no scancodes)."""
        d = ''
        for c in cp_s:
            if d or c != '\0':
                self.insert_keypress(d+c, None, None, check_full)
                d = ''
            elif c == '\0':
                # eascii code is \0 plus one char
                d = c

    def insert_keypress(self, cp_c, scancode, modifier, check_full=True):
        """Append a single keystroke with eascii/codepage, scancode, modifier."""
        if cp_c:
            if check_full and len(self.buffer) >= self.ring_length:
                # emit a sound signal when buffer is full (and we care)
                self._queues.audio.put(self._full_tone)
            else:
                self.buffer.append((cp_c, scancode, modifier))

    def getc(self, expand=True):
        """Read a keystroke as eascii/codepage."""
        try:
            return self.expansion_vessel.pop(0)
        except IndexError:
            pass
        try:
            c = self.buffer.pop(0)[0]
        except IndexError:
            c = ''
        if c:
            self.start = (self.start + 1) % self.ring_length
        if not expand or c not in FUNCTION_KEY:
            return c
        self.expansion_vessel = list(self.key_replace[FUNCTION_KEY[c]])
        try:
            return self.expansion_vessel.pop(0)
        except IndexError:
            # function macro has been redefined as empty: return scancode
            # e.g. KEY 1, "" enables catching F1 with INKEY$
            return c

    def peek(self):
        """Show top keystroke in keyboard buffer as eascii/codepage."""
        try:
            return self.buffer[0][0]
        except IndexError:
            return ''

    def peek_scancodes(self):
        """Show keystrokes in keyboard buffer as scancode."""
        try:
            return [element[1] for element in self.buffer]
        except IndexError:
            return []

    def stop(self):
        """Ring buffer stopping index."""
        return (self.start + self.length()) % self.ring_length

    def ring_index(self, index):
        """Get index for ring position."""
        index -= self.start
        if index < 0:
            index += self.ring_length + 1
        return index

    def ring_read(self, index):
        """Read character at position i in ring as eascii/codepage."""
        index = self.ring_index(index)
        if index == self.ring_length:
            # marker of buffer position
            return '\x0d', 0
        try:
            return self.buffer[index][0:2]
        except IndexError:
            return '\0\0', 0

    def ring_write(self, index, c, scan):
        """Write character at position i in ring as eascii/codepage."""
        index = self.ring_index(index)
        if index < self.ring_length:
            try:
                self.buffer[index] = (c, scan, None)
            except IndexError:
                pass

    def ring_set_boundaries(self, start, stop):
        """Set start and stop index."""
        length = (stop - start) % self.ring_length
        # rotate buffer to account for new start and stop
        start_index = self.ring_index(start)
        stop_index = self.ring_index(stop)
        self.buffer = self.buffer[start_index:] + self.buffer[:stop_index]
        self.buffer += [('\0\0', None, None)]*(length - len(self.buffer))
        self.start = start


###############################################################################
# keyboard operations

class Keyboard(object):
    """Keyboard handling."""

    def __init__(self, queues, values, codepage, keystring, ignore_caps):
        """Initilise keyboard state."""
        self._values = values
        # key queue (holds bytes)
        self.buf = KeyboardBuffer(queues, 15)
        # INP(&H60) scancode
        self.last_scancode = 0
        # active status of caps, num, scroll, alt, ctrl, shift modifiers
        self.mod = 0
        # store for alt+keypad ascii insertion
        self.keypad_ascii = ''
        # ignore caps lock, let OS handle it
        self.ignore_caps = ignore_caps
        # pre-inserted keystrings
        self.codepage = codepage
        self.buf.insert(self.codepage.str_from_unicode(keystring), check_full=False)
        # redirected input stream has closed
        self._input_closed = False
        # needed for wait() in wait_char()
        self._queues = queues

    def check_input(self, signal):
        """Handle keyboard input signals and clipboard paste."""
        if signal.event_type == signals.KEYB_DOWN:
            # params is e-ASCII/unicode character sequence, scancode, modifier
            self.key_down(*signal.params)
        elif signal.event_type == signals.KEYB_UP:
            self.key_up(*signal.params)
        elif signal.event_type == signals.STREAM_CHAR:
            # params is a unicode sequence
            self.insert_chars(*signal.params, check_full=False)
        elif signal.event_type == signals.STREAM_CLOSED:
            self.close_input()
        elif signal.event_type == signals.CLIP_PASTE:
            self.insert_chars(*signal.params, check_full=False)
        else:
            return False
        return True

    def set_macro(self, num, macro):
        """Set macro for given function key."""
        # NUL terminates macro string, rest is ignored
        # macro starting with NUL is empty macro
        self.buf.key_replace[num-1] = macro.split('\0', 1)[0]

    def get_macro(self, num):
        """Get macro for given function key."""
        return self.buf.key_replace[num]

    def wait_char(self):
        """Wait for character, then return it but don't drop from queue."""
        while self.buf.is_empty() and not self._input_closed:
            self._queues.wait()
        return self.buf.peek()

    def inkey_(self, args):
        """INKEY$: read one byte; nonblocking."""
        list(args)
        self._queues.wait()
        inkey = self.buf.getc()
        return self._values.new_string().from_str(inkey)

    def read_bytes_kybd_file(self, num):
        """Read num bytes; for KYBD: files; blocking."""
        word = []
        for _ in range(num):
            self.wait_char()
            word.append(self.buf.getc(expand=False))
        return word

    def get_fullchar(self, expand=True):
        """Read one (sbcs or dbcs) full character; nonblocking."""
        c = self.buf.getc()
        # insert dbcs chars from keyboard buffer two bytes at a time
        if (c in self.codepage.lead and self.buf.peek() in self.codepage.trail):
            c += self.buf.getc()
        return c

    def get_fullchar_block(self, expand=True):
        """Read one (sbcs or dbcs) full character; blocking."""
        self.wait_char()
        return self.get_fullchar(expand)

    def insert_chars(self, us, check_full=True):
        """Insert eascii/unicode string into keyboard buffer."""
        self.buf.insert(self.codepage.str_from_unicode(us), check_full)

    def key_down(self, c, scan, mods, check_full=True):
        """Insert a key-down event by eascii/unicode, scancode and modifiers."""
        if scan is not None:
            self.last_scancode = scan
        # update ephemeral modifier status at every keypress
        # mods is a list of scancodes; OR together the known modifiers
        self.mod &= ~(MODIFIER[scancode.CTRL] | MODIFIER[scancode.ALT] |
                    MODIFIER[scancode.LSHIFT] | MODIFIER[scancode.RSHIFT])
        for m in mods:
            self.mod |= MODIFIER.get(m, 0)
        # set toggle-key modifier status
        # these are triggered by keydown events
        try:
            self.mod ^= TOGGLE[scan]
        except KeyError:
            pass
        # alt+keypad ascii replacement
        if (scancode.ALT in mods):
            try:
                self.keypad_ascii += scancode.keypad[scan]
                return
            except KeyError:
                pass
        if (self.mod & TOGGLE[scancode.CAPSLOCK]
                and not self.ignore_caps and len(c) == 1):
            c = c.swapcase()
        self.buf.insert_keypress(self.codepage.from_unicode(c), scan, self.mod, check_full)

    def key_up(self, scan):
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
            char = chr(int(self.keypad_ascii)%256)
            if char == '\0':
                char = '\0\0'
            self.buf.insert(char, check_full=True)
            self.keypad_ascii = ''

    def close_input(self):
        """Signal that input stream has closed."""
        self._input_closed = True


###############################################################################
# light pen

class Pen(object):
    """Light pen support."""

    def __init__(self):
        """Initialise light pen."""
        self.is_down = False
        self.pos = 0, 0
        # signal pen has been down for PEN polls in pen_()
        self.was_down = False
        self.down_pos = (0, 0)

    def check_input(self, signal):
        """Handle pen-related input signals."""
        if signal.event_type == signals.PEN_DOWN:
            self.down(*signal.params)
        elif signal.event_type == signals.PEN_UP:
            self.up()
        elif signal.event_type == signals.PEN_MOVED:
            self.moved(*signal.params)
        else:
            return False
        return True

    def down(self, x, y):
        """Report a pen-down event at graphical x,y """
        # TRUE until polled
        self.was_down = True
        # TRUE until pen up
        self.is_down = True
        self.down_pos = x, y

    def up(self):
        """Report a pen-up event at graphical x,y """
        self.is_down = False

    def moved(self, x, y):
        """Report a pen-move event at graphical x,y """
        self.pos = x, y

    def poll(self, fn, enabled, screen):
        """PEN: poll the light pen."""
        fn = values.to_int(fn)
        error.range_check(0, 9, fn)
        posx, posy = self.pos
        if fn == 0:
            pen_down_old, self.was_down = self.was_down, False
            pen = -1 if pen_down_old else 0
        elif fn == 1:
            pen = self.down_pos[0]
        elif fn == 2:
            pen = self.down_pos[1]
        elif fn == 3:
            pen = -1 if self.is_down else 0
        elif fn == 4:
            pen = posx
        elif fn == 5:
            pen = posy
        elif fn == 6:
            pen = 1 + self.down_pos[1] // screen.mode.font_height
        elif fn == 7:
            pen = 1 + self.down_pos[0] // screen.mode.font_width
        elif fn == 8:
            pen = 1 + posy // screen.mode.font_height
        elif fn == 9:
            pen = 1 + posx // screen.mode.font_width
        if not enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return pen


###############################################################################
# joysticks


class Stick(object):
    """Joystick support."""

    def __init__(self, values):
        """Initialise joysticks."""
        self._values = values
        self.is_firing = [[False, False], [False, False]]
        # axis 0--255; 128 is mid but reports 0, not 128 if no joysticks present
        self.axis = [[0, 0], [0, 0]]
        self.is_on = False
        self.was_fired = [[False, False], [False, False]]
        # timer for reading game port
        self.out_time = self._decay_timer()

    def check_input(self, signal):
        """Handle joystick-related input signals."""
        if signal.event_type == signals.STICK_DOWN:
            self.down(*signal.params)
        elif signal.event_type == signals.STICK_UP:
            self.up(*signal.params)
        elif signal.event_type == signals.STICK_MOVED:
            self.moved(*signal.params)
        else:
            return False
        return True

    def strig_statement_(self, args):
        """Switch joystick handling on or off."""
        on, = args
        self.is_on = (on == tk.ON)

    def down(self, joy, button):
        """Report a joystick button down event."""
        try:
            self.was_fired[joy][button] = True
            self.is_firing[joy][button] = True
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def up(self, joy, button):
        """Report a joystick button up event."""
        try:
            self.is_firing[joy][button] = False
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def moved(self, joy, axis, value):
        """Report a joystick axis move."""
        try:
            self.axis[joy][axis] = value
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def stick_(self, args):
        """STICK: poll the joystick axes."""
        fn, = args
        fn = values.to_int(fn)
        error.range_check(0, 3, fn)
        joy, axis = fn // 2, fn % 2
        try:
            result = self.axis[joy][axis]
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            result = 0
        return self._values.new_integer().from_int(result)

    def strig_(self, args):
        """STRIG: poll the joystick fire button."""
        fn, = args
        fn = values.to_int(fn)
        error.range_check(0, 7, fn)
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        joy, trig = fn // 4, (fn//2) % 2
        if fn % 2 == 0:
            # has been fired
            stick_was_trig = self.was_fired[joy][trig]
            self.was_fired[joy][trig] = False
            result = -1 if stick_was_trig else 0
        else:
            # is currently firing
            result = -1 if self.is_firing[joy][trig] else 0
        return self._values.new_integer().from_int(result)

    def decay(self):
        """Return time since last game port reset."""
        return (self._decay_timer() - self.out_time) % 86400000

    def reset_decay(self):
        """Reset game port."""
        self.out_time = self._decay_timer()

    def _decay_timer(self):
        """Millisecond timer for game port decay."""
        now = datetime.datetime.now()
        return now.second*1000 + now.microsecond/1000
