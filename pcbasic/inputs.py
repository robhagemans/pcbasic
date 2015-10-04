"""
PC-BASIC - inputs.py
Keyboard, pen and joystick handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import plat
import config
import state
import error
import unicodepage
import scancode
import redirect

import backend


###############################################################################
# keyboard queue

# let OS handle capslock effects
ignore_caps = True
# treat Ctrl-C as Ctrl-Break
ctrl_c_is_break = False


# bit flags for modifier keys
toggle = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10}
modifier = {
    scancode.ALT: 0x8, scancode.CTRL: 0x4,
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1}


def prepare():
    """ Prepare input method handling. """
    global ignore_caps
    global ctrl_c_is_break
    redirect.prepare_redirects()
    # inserted keystrokes
    if plat.system == 'Android':
        # string_escape not available on PGS4A
        keystring = config.get('keys').decode('utf-8')
    else:
        keystring = config.get('keys').decode('string_escape').decode('utf-8')
    state.console_state.keyb = Keyboard()
    for u in keystring:
        c = u.encode('utf-8')
        try:
            state.console_state.keyb.buf.insert(unicodepage.from_utf8(c), check_full=False)
        except KeyError:
            state.console_state.keyb.buf.insert(c, check_full=False)
    # handle caps lock only if requested
    ignore_caps = not config.get('capture-caps')
    # function keys: F1-F12 for tandy, F1-F10 for gwbasic and pcjr
    # if true, treat Ctrl+C *exactly* like ctrl+break (unlike GW-BASIC)
    ctrl_c_is_break = config.get('ctrl-c-break')


class KeyboardBuffer(object):
    """ Quirky emulated ring buffer for keystrokes. """

    def __init__(self, ring_length, s=''):
        """ Initialise to given length. """
        self.buffer = []
        self.ring_length = ring_length
        self.start = 0
        self.insert(s)
        # expansion buffer for keyboard macros; also used for DBCS
        self.expansion_vessel = []
        # dict (scancode: modifier) of all keys that have been pressed for event polls
        # includes keys that have not made it into the buffer
        self.has_been_pressed_event = {}

    def length(self):
        """ Return the number of keystrokes in the buffer. """
        return min(self.ring_length, len(self.buffer))

    def is_empty(self):
        """ True if no keystrokes in buffer. """
        return len(self.buffer) == 0 and len(self.expansion_vessel) == 0

    def insert(self, s, check_full=True):
        """ Append a string of e-ascii keystrokes. Does not trigger events (we have no scancodes). """
        d = ''
        for c in s:
            if d or c != '\0':
                self.insert_keypress(d+c, None, None, check_full)
                d = ''
            elif c == '\0':
                d = c

    def insert_keypress(self, eascii, scancode, modifier, check_full=True):
        """ Append a single keystroke with scancode, modifier. """
        self.has_been_pressed_event[scancode] = modifier
        if eascii:
            if check_full and len(self.buffer) >= self.ring_length:
                # emit a sound signal when buffer is full (and we care)
                state.console_state.sound.play_sound(800, 0.01)
            else:
                self.buffer.append((eascii, scancode, modifier))

    def getc(self, expand=True):
        """ Read a keystroke. """
        try:
            return self.expansion_vessel.pop(0)
        except IndexError:
            try:
                c = self.buffer.pop(0)[0]
            except IndexError:
                c = ''
            if c:
                self.start = (self.start + 1) % self.ring_length
            if not expand:
                return c
            else:
                self.expansion_vessel = expand_key(c)
                try:
                    return self.expansion_vessel.pop(0)
                except IndexError:
                    return ''

    def poll_event(self, scancode):
        """ Poll the keyboard for a keypress event since last poll. """
        try:
            pressed = self.has_been_pressed_event[scancode]
            del self.has_been_pressed_event[scancode]
            return (scancode, pressed)
        except KeyError:
            return (None, None)

    def peek(self):
        """ Show top keystroke in keyboard buffer. """
        try:
            return self.buffer[0][0]
        except IndexError:
            return ''

    def drop_any(self, scancode, modifier):
        """ Drop any characters with given scancode & mod from keyboard buffer. """
        self.buffer = [c for c in self.buffer if c[1:] != (scancode, modifier)]

    def drop(self, n):
        """ Drop n characters from keyboard buffer. """
        n = min(n, len(self.buffer))
        self.buffer = self.buffer[n:]
        self.start = (self.start + n) % self.ring_length

    def stop(self):
        """ Ring buffer stopping index. """
        return (self.start + self.length()) % self.ring_length

    def ring_index(self, index):
        """ Get index for ring position. """
        index -= self.start
        if index < 0:
            index += self.ring_length + 1
        return index

    def ring_read(self, index):
        """ Read character at position i in ring. """
        index = self.ring_index(index)
        if index == self.ring_length:
            # marker of buffer position
            return '\x0d'
        try:
            return self.buffer[index][0]
        except IndexError:
            return '\0\0'

    def ring_write(self, index, c):
        """ Write e-ascii character at position i in ring. """
        index = self.ring_index(index)
        if index < self.ring_length:
            try:
                self.buffer[index] = (c, None, None)
            except IndexError:
                pass

    def ring_set_boundaries(self, start, stop):
        """ Set start and stop index. """
        length = (stop - start) % self.ring_length
        # rotate buffer to account for new start and stop
        start_index = self.ring_index(start)
        stop_index = self.ring_index(stop)
        self.buffer = self.buffer[start_index:] + self.buffer[:stop_index]
        self.buffer += [('\0', None, None)]*(length - len(self.buffer))
        self.start = start


###############################################################################
# keyboard operations

class Keyboard(object):
    """ Keyboard handling. """

    def __init__(self):
        """ Initilise keyboard state. """
        # key queue
        self.buf = KeyboardBuffer(15)
        # INP(&H60) scancode
        self.last_scancode = 0
        # active status of caps, num, scroll, alt, ctrl, shift modifiers
        self.mod = 0
        # store for alt+keypad ascii insertion
        self.keypad_ascii = ''
        # PAUSE is active
        self.pause = False

    def read_chars(self, num):
        """ Read num keystrokes, blocking. """
        word = []
        for _ in range(num):
            word.append(self.get_char_block())
        return word

    def get_char(self):
        """ Read any keystroke, nonblocking. """
        backend.wait()
        return self.buf.getc()

    def wait_char(self):
        """ Wait for character, then return it but don't drop from queue. """
        while self.buf.is_empty() and not redirect.input_closed:
            backend.wait()
        return self.buf.peek()

    def get_char_block(self):
        """ Read any keystroke, blocking. """
        self.wait_char()
        return self.buf.getc()

    def insert_chars(self, s, check_full=False):
        """ Insert characters into keyboard buffer. """
        self.pause = False
        self.buf.insert(s, check_full)

    def key_down(self, scan, eascii='', check_full=True):
        """ Insert a key-down event. Keycode is extended ascii, including DBCS. """
        # set port and low memory address regardless of event triggers
        self.pause = False
        if scan is not None:
            self.last_scancode = scan
        # set modifier status
        try:
            self.mod |= modifier[scan]
        except KeyError:
           pass
        # set toggle-key modifier status
        try:
           self.mod ^= toggle[scan]
        except KeyError:
           pass
        # handle BIOS events
        if (scan == scancode.DELETE and
                    self.mod & modifier[scancode.CTRL] and
                    self.mod & modifier[scancode.ALT]):
                # ctrl-alt-del: if not captured by the OS, reset the emulator
                # meaning exit and delete state. This is useful on android.
            raise error.Reset()
        elif ((scan in (scancode.BREAK, scancode.SCROLLOCK) or
                        ctrl_c_is_break and scan==scancode.c)
                    and self.mod & modifier[scancode.CTRL]):
            raise error.Break()
        elif (scan == scancode.BREAK or
                (scan == scancode.NUMLOCK and self.mod & modifier[scancode.CTRL])):
            self.pause = True
            return
        elif scan == scancode.PRINT:
            if (self.mod &
                    (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT])):
                # shift + printscreen
                state.console_state.screen.print_screen()
            if self.mod & modifier[scancode.CTRL]:
                # ctrl + printscreen
                redirect.toggle_echo(state.io_state.lpt1_file)
        # alt+keypad ascii replacement
        # we can't depend on internal NUM LOCK state as it doesn't get updated
        if (self.mod & modifier[scancode.ALT] and
                len(eascii) == 1 and eascii >= '0' and eascii <= '9'):
            try:
                self.keypad_ascii += scancode.keypad[scan]
                return
            except KeyError:
                pass
        if not eascii or (scan is not None and self.mod &
                    (modifier[scancode.ALT] | modifier[scancode.CTRL])):
            # any provided e-ASCII value overrides when CTRL & ALT are off
            # this helps make keyboards do what's expected
            # independent of language setting
            try:
                eascii = scan_to_eascii(scan, self.mod)
            except KeyError:
                # no eascii found
                return
        if (self.mod & toggle[scancode.CAPSLOCK]
                and not ignore_caps and len(eascii) == 1):
            if eascii >= 'a' and eascii <= 'z':
                eascii = chr(ord(eascii)-32)
            elif eascii >= 'A' and eascii <= 'Z':
                eascii = chr(ord(eascii)+32)
        self.buf.insert_keypress(eascii, scan, self.mod, check_full=True)

    def key_up(self, scan):
        """ Insert a key-up event. """
        if scan is not None:
            self.last_scancode = 0x80 + scan
        try:
            # switch off ephemeral modifiers
            self.mod &= ~modifier[scan]
        except KeyError:
           pass
        # ALT+keycode
        if scan == scancode.ALT and self.keypad_ascii:
            char = chr(int(self.keypad_ascii)%256)
            if char == '\0':
                char = '\0\0'
            self.buf.insert(char, check_full=True)
            self.keypad_ascii = ''


################

# user definable key list
state.console_state.key_replace = [
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r',
    'TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '' ]
# default function key eascii codes for KEY autotext. F1-F10
# F11 and F12 here are TANDY eascii codes only!
function_key = {
    '\0\x3b': 0, '\0\x3c': 1, '\0\x3d': 2, '\0\x3e': 3,
    '\0\x3f': 4, '\0\x40': 5, '\0\x41': 6, '\0\x42': 7,
    '\0\x43': 8, '\0\x44': 9, '\x98': 10, '\x99': 11}
# switch off macro repacements
state.basic_state.key_macros_off = False


def expand_key(c):
    """ Expand function key macros. """
    try:
        keynum = function_key[c]
        return list(state.console_state.key_replace[keynum])
    except KeyError:
        return [c]

def scan_to_eascii(scan, mod):
    """ Translate scancode and modifier state to e-ASCII. """
    if mod & modifier[scancode.ALT]:
        return scancode.eascii_table[scan][3]
    elif mod & modifier[scancode.CTRL]:
        return scancode.eascii_table[scan][2]
    elif mod & (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT]):
        return scancode.eascii_table[scan][1]
    else:
        return scancode.eascii_table[scan][0]


###############################################################################
# light pen

pen_is_down = False
pen_pos = (0, 0)

class Pen(object):
    """ Light pen support. """

    def __init__(self):
        """ Initialise light pen. """
        # signal pen has been down for PEN polls in poll()
        self.was_down = False
        # signal pen has been down for event triggers in poll_event()
        self.was_down_event = False
        self.down_pos = (0, 0)

    def down(self, x, y):
        """ Report a pen-down event at graphical x,y """
        global pen_is_down
        # TRUE until polled
        self.was_down = True
        # TRUE until events checked
        self.was_down_event = True
        # TRUE until pen up
        pen_is_down = True
        self.down_pos = x, y

    def up(self):
        """ Report a pen-up event at graphical x,y """
        global pen_is_down
        pen_is_down = False

    def moved(self, x, y):
        """ Report a pen-move event at graphical x,y """
        global pen_pos
        pen_pos = x, y

    def poll_event(self):
        """ Poll the pen for a pen-down event since last poll. """
        result, self.was_down_event = self.was_down_event, False
        return result

    def poll(self, fn):
        """ Poll the pen. """
        posx, posy = pen_pos
        fw = state.console_state.screen.mode.font_width
        fh = state.console_state.screen.mode.font_height
        if fn == 0:
            pen_down_old, self.was_down = self.was_down, False
            return -1 if pen_down_old else 0
        elif fn == 1:
            return self.down_pos[0]
        elif fn == 2:
            return self.down_pos[1]
        elif fn == 3:
            return -1 if pen_is_down else 0
        elif fn == 4:
            return posx
        elif fn == 5:
            return posy
        elif fn == 6:
            return 1 + self.down_pos[1]//fh
        elif fn == 7:
            return 1 + self.down_pos[0]//fw
        elif fn == 8:
            return 1 + posy//fh
        elif fn == 9:
            return 1 + posx//fw

state.console_state.pen = Pen()


###############################################################################
# joysticks

stick_is_firing = [[False, False], [False, False]]
# axis 0--255; 128 is mid but reports 0, not 128 if no joysticks present
stick_axis = [[0, 0], [0, 0]]

class Stick(object):
    """ Joystick support. """

    def __init__(self):
        """ Initialise joysticks. """
        self.is_on = False
        self.was_fired = [[False, False], [False, False]]
        self.was_fired_event = [[False, False], [False, False]]

    def switch(self, on):
        """ Switch joystick handling on or off. """
        self.is_on = on

    def down(self, joy, button):
        """ Report a joystick button down event. """
        try:
            self.was_fired[joy][button] = True
            stick_is_firing[joy][button] = True
            self.was_fired_event[joy][button] = True
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def up(self, joy, button):
        """ Report a joystick button up event. """
        try:
            stick_is_firing[joy][button] = False
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def moved(self, joy, axis, value):
        """ Report a joystick axis move. """
        try:
            stick_axis[joy][axis] = value
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def poll_event(self, joy, button):
        """ Poll the joystick for button events since last poll. """
        result = self.was_fired_event[joy][button]
        self.was_fired_event[joy][button] = False
        return result

    def poll(self, fn):
        """ Poll the joystick axes. """
        joy, axis = fn // 2, fn % 2
        try:
            return stick_axis[joy][axis]
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass

    def poll_trigger(self, fn):
        """ Poll the joystick buttons. """
        joy, trig = fn // 4, (fn//2) % 2
        try:
            if fn % 2 == 0:
                # has been fired
                stick_was_trig = self.was_fired[joy][trig]
                self.was_fired[joy][trig] = False
                return stick_was_trig
            else:
                # is currently firing
                return stick_is_firing[joy][trig]
        except IndexError:
            # ignore any joysticks/axes beyond the 2x2 supported by BASIC
            pass


state.console_state.stick = Stick()


###############################################################################

prepare()
