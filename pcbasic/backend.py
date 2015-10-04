"""
PC-BASIC - backend.py
Event loop; video, keyboard, pen and joystick handling

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import logging

import time
import Queue

import plat
import config
import state
import timedate
import unicodepage
import scancode
import error
import redirect


video_queue = Queue.Queue()
input_queue = Queue.Queue()

class Event(object):
    """ Signal object for video queue. """

    def __init__(self, event_type, params=None):
        """ Create signal. """
        self.event_type = event_type
        self.params = params


# video queue signals
# save state and quit
VIDEO_QUIT = 0
# change video mode
VIDEO_SET_MODE = 1
# switch page
VIDEO_SET_PAGE = 2
# set cursor shape
VIDEO_SET_CURSOR_SHAPE = 3
# move cursor
VIDEO_MOVE_CURSOR = 5
# set cursor attribute
VIDEO_SET_CURSOR_ATTR = 6
# set border attribute
VIDEO_SET_BORDER_ATTR = 7
# put character glyph
VIDEO_PUT_GLYPH = 8
# clear rows
VIDEO_CLEAR_ROWS = 10
# scroll
VIDEO_SCROLL_UP = 11
VIDEO_SCROLL_DOWN = 12
# set colorburst
VIDEO_SET_COLORBURST = 13
# show/hide cursor
VIDEO_SHOW_CURSOR = 14
# set palette
VIDEO_SET_PALETTE = 15
# build glyphs
VIDEO_BUILD_GLYPHS = 16
# put pixel
VIDEO_PUT_PIXEL = 17
# put interval
VIDEO_PUT_INTERVAL = 18
VIDEO_FILL_INTERVAL = 19
# put rect
VIDEO_PUT_RECT = 20
VIDEO_FILL_RECT = 21
# copy page
VIDEO_COPY_PAGE = 28
# set caption message
VIDEO_SET_CAPTION = 29

# input queue signals
# special keys
KEYB_QUIT = 0
# break event (an alternative to Ctrl+Break keydown events)
KEYB_BREAK = 1
# insert character
KEYB_CHAR = 4
# insert keydown
KEYB_DOWN = 5
# insert keyup
KEYB_UP = 6
# light pen events
PEN_DOWN = 101
PEN_UP = 102
PEN_MOVED = 103
# joystick events
STICK_DOWN = 201
STICK_UP = 202
STICK_MOVED = 203
# clipboard events
CLIP_PASTE = 255



###############################################################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global pcjr_sound
    prepare_keyboard()
    redirect.prepare_redirects()
    state.basic_state.events = Events()
    # we need this for PLAY event
    if config.get('syntax') in ('pcjr', 'tandy'):
        pcjr_sound = config.get('syntax')
    else:
        pcjr_sound = None

###############################################################################
# main event checker

tick_s = 0.0006
longtick_s = 0.024 - tick_s

icon = None
initial_mode = None

def wait(suppress_events=False):
    """ Wait and check events. """
    time.sleep(longtick_s)
    if not suppress_events:
        check_events()

def check_events():
    """ Main event cycle. """
    time.sleep(tick_s)
    check_input()
    if state.basic_state.run_mode:
        for e in state.basic_state.events.all:
            e.check()

def check_input():
    """ Handle input events. """
    while True:
        try:
            signal = input_queue.get(False)
        except Queue.Empty:
            if not state.console_state.keyb.pause:
                break
            else:
                time.sleep(tick_s)
                continue
        # we're on it
        input_queue.task_done()
        if signal.event_type == KEYB_QUIT:
            raise error.Exit()
        elif signal.event_type == KEYB_BREAK:
            raise error.Break()
        elif signal.event_type == KEYB_CHAR:
            state.console_state.keyb.insert_chars(signal.params, check_full=True)
        elif signal.event_type == KEYB_DOWN:
            scan, eascii = signal.params
            state.console_state.keyb.key_down(scan, eascii, check_full=True)
        elif signal.event_type == KEYB_UP:
            state.console_state.keyb.key_up(signal.params)
        elif signal.event_type == PEN_DOWN:
            state.console_state.pen.down(*signal.params)
        elif signal.event_type == PEN_UP:
            state.console_state.pen.up()
        elif signal.event_type == PEN_MOVED:
            state.console_state.pen.moved(*signal.params)
        elif signal.event_type == STICK_DOWN:
            state.console_state.stick.down(*signal.params)
        elif signal.event_type == STICK_UP:
            state.console_state.stick.up(*signal.params)
        elif signal.event_type == STICK_MOVED:
            state.console_state.stick.moved(*signal.params)
        elif signal.event_type == CLIP_PASTE:
            state.console_state.keyb.insert_chars(signal.params, check_full=False)


###############################################################################
# BASIC event triggers

class EventHandler(object):
    """ Manage event triggers. """

    def __init__(self):
        """ Initialise untriggered and disabled. """
        self.reset()

    def reset(self):
        """ Reset to untriggered and disabled initial state. """
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

    def set_jump(self, jump):
        """ Set the jump line number. """
        self.gosub = jump

    def command(self, command_char):
        """ Turn the event ON, OFF and STOP. """
        if command_char == '\x95':
            # ON
            self.enabled = True
            self.stopped = False
        elif command_char == '\xDD':
            # OFF
            self.enabled = False
        elif command_char == '\x90':
            # STOP
            self.stopped = True
        else:
            return False
        return True

    def trigger(self):
        """ Trigger the event. """
        self.triggered = True

    def check(self):
        """ Stub for event checker. """


class PlayHandler(EventHandler):
    """ Manage PLAY (music queue) events. """

    def __init__(self):
        """ Initialise PLAY trigger. """
        EventHandler.__init__(self)
        self.last = [0, 0, 0]
        self.trig = 1

    def check(self):
        """ Check and trigger PLAY (music queue) events. """
        play_now = [state.console_state.sound.queue_length(voice) for voice in range(3)]
        if pcjr_sound:
            for voice in range(3):
                if (play_now[voice] <= self.trig and
                        play_now[voice] > 0 and
                        play_now[voice] != self.last[voice]):
                    self.trigger()
        else:
            if (self.last[0] >= self.trig and
                    play_now[0] < self.trig):
                self.trigger()
        self.last = play_now

    def set_trigger(self, n):
        """ Set PLAY trigger to n notes. """
        self.trig = n


class TimerHandler(EventHandler):
    """ Manage TIMER events. """

    def __init__(self):
        """ Initialise TIMER trigger. """
        EventHandler.__init__(self)
        self.period = 0
        self.start = 0

    def set_trigger(self, n):
        """ Set TIMER trigger to n milliseconds. """
        self.period = n

    def check(self):
        """ Trigger TIMER events. """
        mutimer = timedate.timer_milliseconds()
        if mutimer >= self.start + self.period:
            self.start = mutimer
            self.trigger()


class ComHandler(EventHandler):
    """ Manage COM-port events. """

    def __init__(self, port):
        """ Initialise COM trigger. """
        EventHandler.__init__(self)
        # devices aren't initialised at this time so just keep the name
        self.portname = ('COM1:', 'COM2:')[port]

    def check(self):
        """ Trigger COM-port events. """
        if (state.io_state.devices[self.portname] and
                    state.io_state.devices[self.portname].char_waiting()):
            self.trigger()


class KeyHandler(EventHandler):
    """ Manage KEY events. """

    def __init__(self, scancode=None):
        """ Initialise KEY trigger. """
        EventHandler.__init__(self)
        self.modcode = None
        self.scancode = scancode
        self.predefined = (scancode is not None)
        # poll scancode to clear it from keypress dict
        # where it might liger if this scancode has not tbeen polled before
        state.console_state.keyb.buf.poll_event(self.scancode)

    def check(self):
        """ Trigger KEY events. """
        if self.scancode is None:
            return False
        scancode, modifiers = state.console_state.keyb.buf.poll_event(self.scancode)
        if scancode != self.scancode:
            return False
        # build KEY trigger code
        # see http://www.petesqbsite.com/sections/tutorials/tuts/keysdet.txt
        # second byte is scan code; first byte
        #  0       if the key is pressed alone
        #  1 to 3    if any Shift and the key are combined
        #    4       if Ctrl and the key are combined
        #    8       if Alt and the key are combined
        #   32       if NumLock is activated
        #   64       if CapsLock is activated
        #  128       if we are defining some extended key
        # extended keys are for example the arrow keys on the non-numerical keyboard
        # presumably all the keys in the middle region of a standard PC keyboard?
        #
        # for predefined keys, modifier is ignored
        # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
        if (self.predefined) or (modifiers is None or self.modcode == modifiers & 0x6f):
            # trigger event
            self.trigger()
            # drop key from key buffer
            if self.enabled:
                state.console_state.keyb.buf.drop_any(scancode, modifiers)
                return True
        return False

    def set_trigger(self, keystr):
        """ Set KEY trigger to chr(modcode)+chr(scancode). """
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self.predefined:
            self.modcode = ord(keystr[0])
            self.scancode = ord(keystr[1])


class PenHandler(EventHandler):
    """ Manage PEN events. """

    def check(self):
        """ Trigger PEN events. """
        if state.console_state.pen.poll_event():
            self.trigger()


class StrigHandler(EventHandler):
    """ Manage STRIG events. """

    def __init__(self, joy, button):
        """ Initialise STRIG trigger. """
        EventHandler.__init__(self)
        self.joy = joy
        self.button = button

    def check(self):
        """ Trigger STRIG events. """
        if state.console_state.stick.poll_event(self.joy, self.button):
            self.trigger()


class Events(object):
    """ Event management. """

    def __init__(self):
        """ Initialise event triggers. """
        self.reset()

    def reset(self):
        """ Initialise or reset event triggers. """
        # KEY: init key events
        keys = [
            scancode.F1, scancode.F2, scancode.F3, scancode.F4, scancode.F5,
            scancode.F6, scancode.F7, scancode.F8, scancode.F9, scancode.F10]
        if num_fn_keys == 12:
            # Tandy only
            keys += [scancode.F11, scancode.F12]
        keys += [scancode.UP, scancode.LEFT, scancode.RIGHT, scancode.DOWN]
        keys += [None] * (20 - num_fn_keys - 4)
        self.key = [KeyHandler(sc) for sc in keys]
        # other events
        self.timer = TimerHandler()
        self.play = PlayHandler()
        self.com = [ComHandler(0), ComHandler(1)]
        self.pen = PenHandler()
        # joy*2 + button
        self.strig = [StrigHandler(joy, button)
                      for joy in range(2) for button in range(2)]
        # all handlers in order of handling; TIMER first
        # key events are not handled FIFO but first 11-20 in that order, then 1-10
        self.all = ([self.timer]
            + [self.key[num] for num in (range(10, 20) + range(10))]
            + [self.play] + self.com + [self.pen] + self.strig)
        # set suspension off
        self.suspend_all = False



###############################################################################
# keyboard queue

# let OS handle capslock effects
ignore_caps = True

# bit flags for modifier keys
toggle = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10}
modifier = {
    scancode.ALT: 0x8, scancode.CTRL: 0x4,
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1}


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


def prepare_keyboard():
    """ Prepare keyboard handling. """
    global ignore_caps
    global num_fn_keys
    global ctrl_c_is_break
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
    if config.get('syntax') == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10
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
        wait()
        return self.buf.getc()

    def wait_char(self):
        """ Wait for character, then return it but don't drop from queue. """
        while self.buf.is_empty() and not redirect.input_closed:
            wait()
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
