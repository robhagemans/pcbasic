"""
PC-BASIC 3.23 - backend.py
Event loop; video, audio, keyboard, pen and joystick handling

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import logging
from copy import copy

import plat
import config
import state 
import timedate
import unicodepage
import typeface
import scancode
import error
import vartypes
import util
import representation
import draw_and_play
import redirect
import modes
import graphics
import memory
import clipboard

# backend implementations
video = None
audio = None 

### devices - SCRN: KYBD: LPT1: etc. These are initialised in iolayer module
devices = {}

###############################################################################
# initialisation

def prepare():
    """ Initialise backend module. """
    prepare_keyboard()
    prepare_audio()
    prepare_video()
    redirect.prepare_redirects()
    state.basic_state.events = Events()


###############################################################################
# main event checker
    
def wait():
    """ Wait and check events. """
    video.idle()
    check_events()    

def idle():
    """ Wait a tick. """
    video.idle()

def check_events():
    """ Main event cycle. """
    # manage sound queue
    audio.check_sound()
    state.console_state.sound.check_quit()
    # check video, keyboard, pen and joystick events
    video.check_events()   
    # trigger & handle BASIC events
    if state.basic_state.run_mode:
        # trigger TIMER, PLAY and COM events
        state.basic_state.events.timer.check()
        state.basic_state.events.play.check()
        for c in state.basic_state.events.com:
            c.check()
        # KEY, PEN and STRIG are triggered on handling the queue

   
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
        pass


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
        if devices[self.portname] and devices[self.portname].peek_char():
            self.trigger()


class KeyHandler(EventHandler):
    """ Manage KEY events. """
    
    def __init__(self, scancode=None):
        """ Initialise KEY trigger. """
        EventHandler.__init__(self)
        self.modcode = None
        self.scancode = scancode
        self.predefined = (scancode != None)
    
    #D
    # access keyqueue from check() instead
    def set_scancode_for_check(self, scancode, modifiers):
        """ Kludge. """
        self.check_scancode = scancode
        self.check_modifiers = modifiers
    
    def check(self):
        """ Trigger KEY events. """
        scancode = self.check_scancode
        modifiers = self.check_modifiers
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
        if self.predefined:
            # for predefined keys, modifier is ignored
            modcode = None
        else:
            # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
            modcode = modifiers & 0x6f 
        if (self.modcode == modcode and self.scancode and 
                    self.scancode == scancode):
            self.trigger()
            return self.enabled
        return False            

    def set_trigger(self, keystr):
        """ Set KEY trigger to chr(modcode)+chr(scancode). """
        # can't redefine scancodes for predefined keys 1-14 (pc) 1-16 (tandy)
        if not self.predefined:
            self.modcode = ord(keystr[0])
            self.scancode = ord(keystr[1])

#D
def check_key_event(scancode, modifiers):
    """ Trigger KEYboard events. """
    if not scancode:
        return False
    result = False
    for k in state.basic_state.events.key:
        k.set_scancode_for_check(scancode, modifiers)
        # drop from keyboard queu if triggered and enabled
        result = result or k.check()
    return result


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
        self.pen = EventHandler()
        self.strig = [EventHandler() for _ in xrange(4)]
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

# default function key scancodes for KEY autotext. F1-F10
# F11 and F12 here are TANDY scancodes only!
function_key = {
    scancode.F1: 0, scancode.F2: 1, scancode.F3: 2, scancode.F4: 3, 
    scancode.F5: 4, scancode.F6: 5, scancode.F7: 6, scancode.F8: 7,
    scancode.F9: 8, scancode.F10: 9, scancode.F11: 10, scancode.F12: 11}
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
# switch off macro repacements
state.basic_state.key_macros_off = False    


def prepare_keyboard():
    """ Prepare keyboard handling. """
    global ignore_caps
    global num_fn_keys
    global ctrl_c_is_break
    # inserted keystrokes
    if plat.system == 'Android':
        # string_escape not available on PGS4A
        keystring = config.options['keys'].decode('utf-8')
    else:
        keystring = config.options['keys'].decode('string_escape').decode('utf-8')    
    state.console_state.keyb = Keyboard()
    for u in keystring:
        c = u.encode('utf-8')
        try:
            state.console_state.keyb.buf.insert(unicodepage.from_utf8(c))
        except KeyError:
            state.console_state.keyb.buf.insert(c)
    # handle caps lock only if requested
    if config.options['capture-caps']:
        ignore_caps = False
    # function keys: F1-F12 for tandy, F1-F10 for gwbasic and pcjr
    if config.options['syntax'] == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10
    # if true, treat Ctrl+C *exactly* like ctrl+break (unlike GW-BASIC)
    ctrl_c_is_break = config.options['ctrl-c-break']

class KeyboardBuffer(object):
    """ Quirky emulated ring buffer for keystrokes. """

    def __init__(self, ring_length, s=''):
        """ Initialise to given length. """
        self.buffer = []
        self.ring_length = ring_length
        self.start = 0
        self.insert(s)

    def length(self):
        """ Return the number of keystrokes in the buffer. """
        return min(self.ring_length, len(self.buffer))

    def is_empty(self):
        """ True if no keystrokes in buffer. """
        return len(self.buffer) == 0
    
    def insert(self, s, check_full=True):
        """ Append a string of e-ascii keystrokes. """
        d = ''
        for c in s:
            if check_full and len(self.buffer) >= self.ring_length:
                return False
            if d or c != '\0':
                self.buffer.append(d+c)
                d = ''
            elif c == '\0':
                d = c
        return True
        
    def getc(self):
        """ Read a keystroke. """
        try:
            c = self.buffer.pop(0)
        except IndexError:
            c = ''
        if c:
            self.start = (self.start + 1) % self.ring_length
        return c
            
    def peek(self):
        """ Show top keystroke in keyboard buffer. """
        try:
            return self.buffer[0]
        except IndexError:
            return ''
            
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
            return self.buffer[index]
        except IndexError:
            return '\0\0'
    
    def ring_write(self, index, c):
        """ Write e-ascii character at position i in ring. """
        index = self.ring_index(index)
        if index < self.ring_length:
            try:
                self.buffer[index] = c
            except IndexError:
                pass
    
    def ring_set_boundaries(self, start, stop):
        """ Set start and stop index. """ 
        length = (stop - start) % self.ring_length
        # rotate buffer to account for new start and stop
        start_index = self.ring_index(start)
        stop_index = self.ring_index(stop)
        self.buffer = self.buffer[start_index:] + self.buffer[:stop_index]
        self.buffer += ['\0']*(length - len(self.buffer))
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
        if not self.buf.insert(s, check_full):
            # keyboard buffer is full; short beep and exit
            state.console_state.sound.play_sound(800, 0.01)

    def key_down(self, scan, eascii='', check_full=True):
        """ Insert a key-down event. Keycode is extended ascii, including DBCS. """
        # set port and low memory address regardless of event triggers
        if scan != None:
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
        if ((scan in (scancode.BREAK, scancode.SCROLLOCK) or
                        ctrl_c_is_break and scan==scancode.c) 
                    and self.mod & modifier[scancode.CTRL]):
                raise error.Break()
        if scan == scancode.PRINT:
            if (self.mod & 
                    (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT])):
                # shift + printscreen
                state.console_state.screen.print_screen()
            if self.mod & modifier[scancode.CTRL]:
                # ctrl + printscreen
                redirect.toggle_echo(devices['LPT1:'])
        # alt+keypad ascii replacement        
        # we can't depend on internal NUM LOCK state as it doesn't get updated
        if (self.mod & modifier[scancode.ALT] and 
                len(eascii) == 1 and eascii >= '0' and eascii <= '9'):
            try:
                self.keypad_ascii += scancode.keypad[scan]
                return
            except KeyError:    
                pass
        # trigger events
        if check_key_event(scan, self.mod):
            # this key is being trapped, don't replace
            return
        # function key macros
        try:
            # only check function keys
            # can't be redefined in events - so must be fn 1-10 (1-12 on Tandy).
            keynum = function_key[scan]
            if (state.basic_state.key_macros_off or state.basic_state.run_mode 
                    and state.basic_state.events.key[keynum].enabled):
                # this key is paused from being trapped, don't replace
                self.insert_chars(scan_to_eascii(scan, self.mod), check_full)
                return
            else:
                macro = state.console_state.key_replace[keynum]
                # insert directly, avoid caps handling
                self.insert_chars(macro, check_full=check_full)
                return
        except KeyError:
            pass
        if not eascii or (scan != None and self.mod & 
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
        self.insert_chars(eascii, check_full=True)        

    def key_up(self, scan):
        """ Insert a key-up event. """
        if scan != None:
            self.last_scancode = 0x80 + scan
        try:
            # switch off ephemeral modifiers
            self.mod &= ~modifier[scan]
            # ALT+keycode    
            if scan == scancode.ALT and self.keypad_ascii:
                char = chr(int(self.keypad_ascii)%256)
                if char == '\0':
                    char = '\0\0'
                self.insert_chars(char, check_full=True)
                self.keypad_ascii = ''
        except KeyError:
           pass 


#D
def insert_chars(s, check_full=False):
    """ Insert characters into keyboard buffer. """
    state.console_state.keyb.insert_chars(s, check_full)

#D
def key_down(scan, eascii='', check_full=True):
    """ Insert a key-down event. Keycode is extended ascii, including DBCS. """
    state.console_state.keyb.key_down(scan, eascii, check_full)

#D
def key_up(scan):
    """ Insert a key-up event. """
    state.console_state.keyb.key_up(scan)
  
#D?    
def insert_special_key(name):
    """ Insert break, reset or quit events. """
    if name == 'quit':
        raise error.Exit()
    elif name == 'reset':
        raise error.Reset()
    elif name == 'break':
        raise error.Break()
    else:
        logging.debug('Unknown special key: %s', name)

#D?
def close_input():
    """ Signal end of keyboard stream. """
    redirect.input_closed = True

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
# clipboard

#D
def copy_clipboard(start_row, start_col, stop_row, stop_col, mouse):
    clipboard_handler.copy(state.console_state.screen.get_text(
                            start_row, start_col, stop_row, stop_col), mouse)

#D
def paste_clipboard(mouse):
    # ignore any bad UTF8 characters from outside
    text_utf8 = clipboard_handler.paste(mouse)
    for u in text_utf8.decode('utf-8', 'ignore'):
        c = u.encode('utf-8')
        last = ''
        if c == '\n':
            if last != '\r':
                insert_chars('\r')
        else:
            try:
                insert_chars(unicodepage.from_utf8(c))
            except KeyError:
                insert_chars(c)
        last = c

###############################################################################
# screen buffer

class TextRow(object):
    """ Buffer for a single row of the screen. """
    
    def __init__(self, battr, bwidth):
        """ Set up screen row empty and unwrapped. """
        # screen buffer, initialised to spaces, dim white on black
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0    
        # line continues on next row (either LF or word wrap happened)
        self.wrap = False
    
    def clear(self, battr):
        """ Clear the screen row buffer. Leave wrap untouched. """
        bwidth = len(self.buf)
        self.buf = [(' ', battr)] * bwidth
        # character is part of double width char; 0 = no; 1 = lead, 2 = trail
        self.double = [ 0 ] * bwidth
        # last non-whitespace character
        self.end = 0    


class TextPage(object):
    """ Buffer for a screen page. """
    
    def __init__(self, battr, bwidth, bheight, pagenum):
        """ Initialise the screen buffer to given dimensions. """
        self.row = [TextRow(battr, bwidth) for _ in xrange(bheight)]
        self.width = bwidth
        self.height = bheight
        self.pagenum = pagenum

    def get_char_attr(self, crow, ccol, want_attr):
        """ Retrieve a byte from the screen (SBCS or DBCS half-char). """
        ca = self.row[crow-1].buf[ccol-1][want_attr]
        return ca if want_attr else ord(ca)

    def put_char_attr(self, crow, ccol, c, cattr, one_only=False, force=False):
        """ Put a byte to the screen, reinterpreting SBCS and DBCS as necessary. """
        if self.row[crow-1].buf[ccol-1] == (c, cattr) and not force:
            # nothing to do
            return ccol, ccol
        # update the screen buffer
        self.row[crow-1].buf[ccol-1] = (c, cattr)
        # mark the replaced char for refreshing
        start, stop = ccol, ccol+1
        self.row[crow-1].double[ccol-1] = 0
        # mark out sbcs and dbcs characters
        # only do dbcs in 80-character modes
        if unicodepage.dbcs and self.width == 80:
            orig_col = ccol
            # replace chars from here until necessary to update double-width chars
            therow = self.row[crow-1]    
            # replacing a trail byte? take one step back
            # previous char could be a lead byte? take a step back
            if (ccol > 1 and therow.double[ccol-2] != 2 and 
                    (therow.buf[ccol-1][0] in unicodepage.trail or 
                     therow.buf[ccol-2][0] in unicodepage.lead)):
                ccol -= 1
                start -= 1
            # check all dbcs characters between here until it doesn't matter anymore
            while ccol < self.width:
                c = therow.buf[ccol-1][0]
                d = therow.buf[ccol][0]  
                if (c in unicodepage.lead and d in unicodepage.trail):
                    if (therow.double[ccol-1] == 1 and 
                            therow.double[ccol] == 2 and ccol > orig_col):
                        break
                    therow.double[ccol-1] = 1
                    therow.double[ccol] = 2
                    start, stop = min(start, ccol), max(stop, ccol+2)
                    ccol += 2
                else:
                    if therow.double[ccol-1] == 0 and ccol > orig_col:
                        break
                    therow.double[ccol-1] = 0
                    start, stop = min(start, ccol), max(stop, ccol+1)
                    ccol += 1
                if (ccol >= self.width or 
                        (one_only and ccol > orig_col)):
                    break  
            # check for box drawing
            if unicodepage.box_protect:
                ccol = start-2
                connecting = 0
                bset = -1
                while ccol < stop+2 and ccol < self.width:
                    c = therow.buf[ccol-1][0]
                    d = therow.buf[ccol][0]  
                    if bset > -1 and unicodepage.connects(c, d, bset): 
                        connecting += 1
                    else:
                        connecting = 0
                        bset = -1
                    if bset == -1:
                        for b in (0, 1):
                            if unicodepage.connects(c, d, b):
                                bset = b
                                connecting = 1
                    if connecting >= 2:
                        therow.double[ccol] = 0
                        therow.double[ccol-1] = 0
                        therow.double[ccol-2] = 0
                        start = min(start, ccol-1)
                        if ccol > 2 and therow.double[ccol-3] == 1:
                            therow.double[ccol-3] = 0
                            start = min(start, ccol-2)
                        if (ccol < self.width-1 and 
                                therow.double[ccol+1] == 2):
                            therow.double[ccol+1] = 0
                            stop = max(stop, ccol+2)
                    ccol += 1        
        return start, stop

class TextBuffer(object):
    """ Buffer for text on all screen pages. """

    def __init__(self, battr, bwidth, bheight, bpages):
        """ Initialise the screen buffer to given pages and dimensions. """
        self.pages = [TextPage(battr, bwidth, bheight, num) for num in range(bpages)]
        self.width = bwidth
        self.height = bheight

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        for x in range(self.height):
            dstrow = self.pages[dst].row[x]
            srcrow = self.pages[src].row[x]
            dstrow.buf[:] = srcrow.buf[:]
            dstrow.end = srcrow.end
            dstrow.wrap = srcrow.wrap            


###############################################################################
# screen operations

def prepare_video():
    """ Prepare the video subsystem. """
    global egacursor
    global video_capabilities, composite_monitor, mono_monitor
    global font_8, heights_needed
    video_capabilities = config.options['video']
    # do all text modes with >8 pixels have an ega-cursor?    
    egacursor = config.options['video'] in (
        'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules')
    composite_monitor = config.options['monitor'] == 'composite'
    mono_monitor = config.options['monitor'] == 'mono'
    if video_capabilities == 'ega' and mono_monitor:
        video_capabilities = 'ega_mono'
    # prepare video mode list
    # only allow the screen modes that the given machine supports
    # PCjr starts in 40-column mode
    # video memory size - default is EGA 256K
    state.console_state.screen = Screen(config.options['text-width'], 
                                        config.options['video-memory'])

    heights_needed = set()
    for mode in state.console_state.screen.text_data.values():
        heights_needed.add(mode.font_height)
    for mode in state.console_state.screen.mode_data.values():
        heights_needed.add(mode.font_height)
    # load the 8-pixel font that's available in RAM.
    font_8 = typeface.load(config.options['font'], 8, 
                           unicodepage.cp_to_unicodepoint)
    
    
def init_video(video_module):
    """ Initialise the video backend. """
    global video
    global clipboard_handler
    video = video_module
    if not video or not video.init():
        return False
    # clipboard handler may need an initialised pygame screen
    clipboard_handler = clipboard.get_handler()
    if state.loaded:
        # reload the screen in resumed state
        return state.console_state.screen.resume()
    else:        
        # initialise a fresh textmode screen
        state.console_state.screen.screen(None, None, None, None)
        return True

class Screen(object):
    """ Screen manipulation operations. """

    def __init__(self, initial_width, video_mem_size):
        """ Minimal initialisiation of the screen. """
        self.screen_mode = 0
        self.colorswitch = 1
        self.apagenum = 0
        self.vpagenum = 0
        # current attribute
        self.attr = 7
        # border attribute
        self.border_attr = 0
        self.video_mem_size = video_mem_size
        # prepare video modes
        self.cga_mode_5 = False
        self.cga4_palette = list(modes.cga4_palettes[1])
        self.prepare_modes()
        self.mode = self.text_data[initial_width]
        # cursor
        self.cursor = Cursor(self)
        # storage space for backend display strings
        self.display_storage = None

    def prepare_modes(self):
        """ Build lists of allowed graphics modes. """
        self.text_data, self.mode_data = modes.get_modes(self, 
                                    self.cga4_palette, self.video_mem_size)

    def close(self):
        """ Close the display. """
        self.save_state()
        video.close()

    def save_state(self):
        """ Save display for possible resume. """
        self.display_storage = video.save_state()

    def clear_saved_state(self):
        """ Clear storage space for saved display state. """
        self.display_storage = None

    def resume(self):
        """ Load a video mode from storage and initialise. """
        # recalculate modes in case we've changed hardware emulations
        self.prepare_modes()
        cmode = self.mode
        nmode = self.screen_mode
        if (not cmode.is_text_mode and 
                (nmode not in self.mode_data or 
                 cmode.name != self.mode_data[nmode].name)):
            logging.warning(
                "Resumed screen mode %d (%s) not supported by this setup",
                nmode, cmode.name)
            return False
        if not cmode.is_text_mode:    
            mode_info = self.mode_data[nmode]
        else:
            mode_info = self.text_data[cmode.width]
        if (cmode.is_text_mode and cmode.name != mode_info.name):
            # we switched adapters on resume; fix font height, palette, cursor
            self.cursor.from_line = (self.cursor.from_line *
                                       mode_info.font_height) // cmode.font_height
            self.cursor.to_line = (self.cursor.to_line *
                                     mode_info.font_height) // cmode.font_height
            self.palette = Palette(self.mode)
        # set the screen mde
        if video.init_screen_mode(mode_info):
            # set the visible and active pages
            video.set_page(self.vpagenum, self.apagenum)
            # rebuild palette
            self.palette.set_all(self.palette.palette, check_mode=False)
            video.set_attr(self.attr)
            # fix the cursor
            video.build_cursor(self.cursor.width, mode_info.font_height, 
                               self.cursor.from_line, self.cursor.to_line)    
            video.move_cursor(state.console_state.row, state.console_state.col)
            video.update_cursor_attr(
                self.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
            self.cursor.reset_visibility()
            video.set_border(self.border_attr)
        else:
            # fix the terminal
            video.close()
            # mode not supported by backend
            logging.warning(
                "Resumed screen mode %d not supported by this interface.", nmode)
            return False
        if (cmode.is_text_mode and cmode.name != mode_info.name):
            # text mode in different resolution; redraw.
            self.mode = mode_info
            self.redraw_text_screen()
        else:
            # load the screen contents from storage
            if not video.load_state(self.display_storage):
                # couldn't restore graphics - redraw the text screen
                self.redraw_text_screen()
        # throw away the display strings after use
        self.display_storage = None
        return True

    def screen(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum, 
               erase=1, new_width=None):
        """ SCREEN: change the video mode, colourburst, visible or active page. """
        # set default arguments
        if new_mode == None:
            new_mode = self.screen_mode
        # THIS IS HOW COLORSWITCH SHOULD WORK:
        #   SCREEN 0,0 - mono on composite, color on RGB
        #   SCREEN 0,1 - color (colorburst=True)
        #   SCREEN 1,0 - color (colorburst=True)
        #   SCREEN 1,1 - mono on composite, mode 5 on RGB
        # default colorswitch:
        #   SCREEN 0 = SCREEN 0,0 (pcjr)
        #   SCREEN 0 = SCREEN 0,1 (tandy, cga, ega, vga, ..)
        #   SCREEN 1 = SCREEN 1,0 (pcjr, tandy)
        #   SCREEN 1 = SCREEN 1,1 (cga, ega, vga, ...)
        # colorswitch is NOT preserved between screens when unspecified
        # colorswitch is NOT the same as colorburst (opposite on screen 1)
        if new_colorswitch == None:
            if video_capabilities == 'pcjr':
                new_colorswitch = 0
            elif video_capabilities == 'tandy':
                new_colorswitch = not new_mode
            else:
                new_colorswitch = 1
        new_colorswitch = (new_colorswitch != 0)
        if new_mode == 0 and new_width == None:
            # width persists on change to screen 0
            new_width = self.mode.width 
            # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
            if new_width == 20:
                new_width = 40
        # retrieve the specs for the new video mode
        try:
            if new_mode != 0:    
                info = self.mode_data[new_mode]
            else:
                info = self.text_data[new_width]
        except KeyError:
            # no such mode
            info = None
        # vpage and apage nums are persistent on mode switch with SCREEN
        # on pcjr only, reset page to zero if current page number would be too high.
        if new_vpagenum == None:    
            new_vpagenum = self.vpagenum 
            if (video_capabilities == 'pcjr' and info and 
                    new_vpagenum >= info.num_pages):
                new_vpagenum = 0
        if new_apagenum == None:
            new_apagenum = self.apagenum
            if (video_capabilities == 'pcjr' and info and 
                    new_apagenum >= info.num_pages):
                new_apagenum = 0    
        # Erase tells basic how much video memory to erase
        # 0: do not erase video memory
        # 1: (default) erase old and new page if screen or width changes
        # 2: erase all video memory if screen or width changes 
        # -> we're not distinguishing between 1 and 2 here
        if (erase == 0 and self.mode.video_segment == info.video_segment):
            save_mem = self.mode.get_memory(
                            self.mode.video_segment*0x10, self.video_mem_size)
        else:
            save_mem = None
        self.set_mode(info, new_mode, new_colorswitch, 
                      new_apagenum, new_vpagenum)
        if save_mem:
            self.mode.set_memory(self.mode.video_segment*0x10, save_mem)

    def set_mode(self, mode_info, new_mode, new_colorswitch, 
                 new_apagenum, new_vpagenum):
        """ Change the video mode, colourburst, visible or active page. """
        # reset palette happens even if the SCREEN call fails
        self.set_cga4_palette(1)
        # if the new mode has fewer pages than current vpage/apage, 
        # illegal fn call before anything happens.
        # signal the backend to change the screen resolution
        if (not mode_info or
                new_apagenum >= mode_info.num_pages or 
                new_vpagenum >= mode_info.num_pages or
                not video.init_screen_mode(mode_info)):
            # reset palette happens even if the SCREEN call fails
            self.palette = Palette(self.mode)
            raise error.RunError(5)
        # attribute and border persist on width-only change
        if (not (self.mode.is_text_mode and mode_info.is_text_mode) or
                self.apagenum != new_apagenum or self.vpagenum != new_vpagenum
                or self.colorswitch != new_colorswitch):
            self.attr = mode_info.attr
        if (not (self.mode.is_text_mode and mode_info.is_text_mode) and
                mode_info.name != self.mode.name):
            # start with black border 
            self.set_border(0)
        # set the screen parameters
        self.screen_mode = new_mode
        self.colorswitch = new_colorswitch 
        # set all state vars
        self.mode = mode_info
        # build the screen buffer    
        self.text = TextBuffer(self.attr, self.mode.width, 
                               self.mode.height, self.mode.num_pages)
        # ensure current position is not outside new boundaries
        state.console_state.row, state.console_state.col = 1, 1
        # set active page & visible page, counting from 0. 
        self.set_page(new_vpagenum, new_apagenum)
        # set graphics characteristics
        self.drawing = graphics.Drawing(self)
        # cursor width starts out as single char
        self.cursor.init_mode(self.mode)
        self.palette = Palette(self.mode)
        # set the attribute
        video.set_attr(self.attr)
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if self.mode.is_text_mode:
            self.set_colorburst(new_colorswitch)
        elif self.mode.name == '320x200x4':    
            self.set_colorburst(not new_colorswitch)
        elif self.mode.name == '640x200x2':
            self.set_colorburst(False)    

    def set_width(self, to_width):
        """ Set the character width of the screen, reset pages and change modes. """
        if to_width == 20:
            if video_capabilities in ('pcjr', 'tandy'):
                self.screen(3, None, 0, 0)
            else:
                raise error.RunError(5)
        elif self.mode.is_text_mode:
            self.screen(0, None, 0, 0, new_width=to_width) 
        elif to_width == 40:
            if self.mode.name == '640x200x2':
                self.screen(1, None, 0, 0)
            elif self.mode.name == '160x200x16':
                self.screen(1, None, 0, 0)
            elif self.mode.name == '640x200x4':
                self.screen(5, None, 0, 0)
            elif self.mode.name == '640x200x16':
                self.screen(7, None, 0, 0)
            elif self.mode.name == '640x350x16':
                # screen 9 switches to screen 1 (not 7) on WIDTH 40
                self.screen(1, None, 0, 0)
        elif to_width == 80:
            if self.mode.name == '320x200x4':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '160x200x16':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '320x200x4pcjr':
                self.screen(2, None, 0, 0)
            elif self.mode.name == '320x200x16pcjr':
                self.screen(6, None, 0, 0)
            elif self.mode.name == '320x200x16':
                self.screen(8, None, 0, 0)
        else:
            raise error.RunError(5)

    def set_colorburst(self, on=True):
        """ Set the composite colorburst bit. """
        # On a composite monitor:
        # - on SCREEN 2 this enables artifacting
        # - on SCREEN 1 and 0 this switches between colour and greyscale
        # On an RGB monitor:
        # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
        # - ignored on other screens
        colorburst_capable = video_capabilities in (
                                    'cga', 'cga_old', 'tandy', 'pcjr')
        if self.mode.name == '320x200x4' and not composite_monitor:
            # ega ignores colorburst; tandy and pcjr have no mode 5
            self.cga_mode_5 = not on
            self.set_cga4_palette(1)
        elif (on or not composite_monitor and not mono_monitor):
            modes.colours16[:] = modes.colours16_colour
        else:
            modes.colours16[:] = modes.colours16_mono
        # reset the palette to reflect the new mono or mode-5 situation
        self.palette = Palette(self.mode)
        video.set_colorburst(on and colorburst_capable,
                            self.palette.rgb_palette, self.palette.rgb_palette1)

    def set_cga4_palette(self, num):
        """ set the default 4-colour CGA palette. """
        self.cga4_palette_num = num
        # we need to copy into cga4_palette as it's referenced by mode.palette
        if self.cga_mode_5 and video_capabilities in ('cga', 'cga_old'):
            self.cga4_palette[:] = modes.cga4_palettes[5]
        else:
            self.cga4_palette[:] = modes.cga4_palettes[num]
        
    def set_video_memory_size(self, new_size):
        """ Change the amount of memory available to the video card. """
        self.video_mem_size = new_size
        # redefine number of available video pages
        self.prepare_modes()
        # text screen modes don't depend on video memory size
        if self.screen_mode == 0:
            return True
        # check if we need to drop out of our current mode
        page = max(self.vpagenum, self.apagenum)
        # reload max number of pages; do we fit? if not, drop to text
        new_mode = self.mode_data[self.screen_mode]
        if (page >= new_mode.num_pages):
            return False        
        self.mode = new_mode
        return True

    def set_page(self, new_vpagenum, new_apagenum):
        """ Set active page & visible page, counting from 0. """
        if new_vpagenum == None:
            new_vpagenum = self.vpagenum
        if new_apagenum == None:
            new_apagenum = self.apagenum
        if (new_vpagenum >= self.mode.num_pages or new_apagenum >= self.mode.num_pages):
            raise error.RunError(5)    
        self.vpagenum = new_vpagenum
        self.apagenum = new_apagenum
        self.vpage = self.text.pages[new_vpagenum]
        self.apage = self.text.pages[new_apagenum]
        video.set_page(new_vpagenum, new_apagenum)

    def set_attr(self, attr):
        """ Set the default attribute. """
        self.attr = attr

    def set_border(self, attr):
        """ Set the border attribute. """
        self.border_attr = attr
        video.set_border(attr)

    def copy_page(self, src, dst):
        """ Copy source to destination page. """
        self.text.copy_page(src, dst)    
        video.copy_page(src, dst)

    def get_char_attr(self, pagenum, crow, ccol, want_attr):
        """ Retrieve a byte from the screen. """
        return self.text.pages[pagenum].get_char_attr(crow, ccol, want_attr)

    def put_char_attr(self, pagenum, crow, ccol, c, cattr, 
                            one_only=False, for_keys=False, force=False):
        """ Put a byte to the screen, redrawing as necessary. """
        if not self.mode.is_text_mode:
            cattr = cattr & 0xf
        start, stop = self.text.pages[pagenum].put_char_attr(crow, ccol, c, cattr, one_only, force)
        # update the screen 
        self.refresh_range(pagenum, crow, start, stop, for_keys)

    def get_text(self, start_row, start_col, stop_row, stop_col):   
        """ Retrieve a clip of the text between start and stop. """     
        r, c = start_row, start_col
        full = ''
        clip = ''
        if self.vpage.row[r-1].double[c-1] == 2:
            # include lead byte
            c -= 1
        if self.vpage.row[stop_row-1].double[stop_col-1] == 1:
            # include trail byte
            stop_col += 1
        while r < stop_row or (r == stop_row and c <= stop_col):
            clip += self.vpage.row[r-1].buf[c-1][0]    
            c += 1
            if c > self.mode.width:
                if not self.vpage.row[r-1].wrap:
                    full += unicodepage.UTF8Converter().to_utf8(clip) + '\r\n'
                    clip = ''
                r += 1
                c = 1
        full += unicodepage.UTF8Converter().to_utf8(clip)        
        return full

    def refresh_range(self, pagenum, crow, start, stop, for_keys=False):
        """ Redraw a section of a screen row, assuming DBCS buffer has been set. """
        therow = self.text.pages[pagenum].row[crow-1]
        ccol = start
        while ccol < stop:
            double = therow.double[ccol-1]
            if double == 1:
                ca = therow.buf[ccol-1]
                da = therow.buf[ccol]
                video.set_attr(da[1]) 
                video.putwc_at(pagenum, crow, ccol, ca[0], da[0], for_keys)
                therow.double[ccol-1] = 1
                therow.double[ccol] = 2
                ccol += 2
            else:
                if double != 0:
                    logging.debug('DBCS buffer corrupted at %d, %d (%d)', crow, ccol, double)
                ca = therow.buf[ccol-1]        
                video.set_attr(ca[1]) 
                video.putc_at(pagenum, crow, ccol, ca[0], for_keys)
                ccol += 1

    # should be in console? uses wrap
    def redraw_row(self, start, crow, wrap=True):
        """ Draw the screen row, wrapping around and reconstructing DBCS buffer. """
        while True:
            therow = self.apage.row[crow-1]  
            for i in range(start, therow.end): 
                # redrawing changes colour attributes to current foreground (cf. GW)
                # don't update all dbcs chars behind at each put
                self.put_char_attr(self.apagenum, crow, i+1, 
                        therow.buf[i][0], self.attr, one_only=True, force=True)
            if (wrap and therow.wrap and 
                    crow >= 0 and crow < self.text.height-1):
                crow += 1
                start = 0
            else:
                break    

    def redraw_text_screen(self):
        """ Redraw the active screen page, reconstructing DBCS buffers. """
        # force cursor invisible during redraw
        self.cursor.show(False)
        # this makes it feel faster
        video.clear_rows(self.attr, 1, self.mode.height)
        # redraw every character
        for crow in range(self.mode.height):
            therow = self.apage.row[crow]  
            for i in range(self.mode.width): 
                # set for_keys to avoid echoing to CLI
                self.put_char_attr(self.apagenum, crow+1, i+1, 
                             therow.buf[i][0], therow.buf[i][1], for_keys=True)
        # set cursor back to previous state                             
        self.cursor.reset_visibility()

    #D -> devices['LPT1'].write(get_text(...))
    def print_screen(self):
        """ Output the visible page to LPT1. """
        for crow in range(1, self.mode.height+1):
            line = ''
            for c, _ in self.vpage.row[crow-1].buf:
                line += c
            devices['LPT1:'].write_line(line)

    def clear_text_at(self, x, y):
        """ Remove the character covering a single pixel. """
        fx, fy = self.mode.font_width, self.mode.font_height
        cymax, cxmax = self.mode.height-1, self.mode.width-1
        cx, cy = x // fx, y // fy
        if cx >= 0 and cy >= 0 and cx <= cxmax and cy <= cymax:
            self.apage.row[cy].buf[cx] = (' ', self.attr)

    def clear_text_area(self, x0, y0, x1, y1):
        """ Remove all characters from a rectangle of the graphics screen. """
        fx, fy = self.mode.font_width, self.mode.font_height
        cymax, cxmax = self.mode.height-1, self.mode.width-1 
        cx0 = min(cxmax, max(0, x0 // fx)) 
        cy0 = min(cymax, max(0, y0 // fy))
        cx1 = min(cxmax, max(0, x1 // fx)) 
        cy1 = min(cymax, max(0, y1 // fy))
        for r in range(cy0, cy1+1):
            self.apage.row[r].buf[cx0:cx1+1] = [
                (' ', self.attr)] * (cx1 - cx0 + 1)

    def rebuild_glyph(self, ordval):
        """ Signal the backend to rebuild a character after POKE. """
        video.rebuild_glyph(ordval)

    ## graphics primitives

    def start_graph(self):
        """ Apply the graphics clip area before performing graphics ops. """
        video.apply_graph_clip(*self.drawing.get_view())

    def finish_graph(self):
        """ Remove the graphics clip area after performing graphics ops. """
        video.remove_graph_clip()

    def put_pixel(self, x, y, index, pagenum=None):
        """ Put a pixel on the screen; empty character buffer. """
        if pagenum == None:
            pagenum = self.apagenum
        video.put_pixel(x, y, index, pagenum)
        self.clear_text_at(x, y)

    def get_pixel(self, x, y, pagenum=None):    
        """ Return the attribute a pixel on the screen. """
        if pagenum == None:
            pagenum = self.apagenum
        return video.get_pixel(x, y, pagenum)

    def get_interval(self, pagenum, x, y, length):
        """ Read a scanline interval into a list of attributes. """
        return video.get_interval(pagenum, x, y, length)

    def put_interval(self, pagenum, x, y, colours, mask=0xff):
        """ Write a list of attributes to a scanline interval. """
        video.put_interval(pagenum, x, y, colours, mask)
        self.clear_text_area(x, y, x+len(colours), y)

    def fill_interval(self, x0, x1, y, index):
        """ Fill a scanline interval in a solid attribute. """
        video.fill_interval(x0, x1, y, index)
        self.clear_text_area(x0, y, x1, y)

    def get_until(self, x0, x1, y, c):
        """ Get the attribute values of a scanline interval. """
        return video.get_until(x0, x1, y, c)

    def get_rect(self, x0, y0, x1, y1):
        """ Read a screen rect into an [y][x] array of attributes. """
        return video.get_rect(x0, y0, x1, y1)

    def put_rect(self, x0, y0, x1, y1, sprite, operation_token):
        """ Apply an [y][x] array of attributes onto a screen rect. """
        video.put_rect(x0, y0, x1, y1, sprite, operation_token)
        self.clear_text_area(x0, y0, x1, y1)

    def fill_rect(self, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """
        video.fill_rect(x0, y0, x1, y1, index)
        self.clear_text_area(x0, y0, x1, y1)

 
###############################################################################
# palette

class Palette(object):
    """ Colour palette. """
    
    def __init__(self, mode):
        """ Initialise palette. """
        self.set_all(mode.palette, check_mode=False)

    def set_entry(self, index, colour, check_mode=True):
        """ Set a new colour for a given attribute. """
        mode = state.console_state.screen.mode
        if check_mode and not self.mode_allows_palette(mode):
            return
        self.palette[index] = colour
        self.rgb_palette[index] = mode.colours[colour]
        if mode.colours1:
            self.rgb_palette1[index] = mode.colours1[colour]
        video.update_palette(self.rgb_palette, self.rgb_palette1)

    def get_entry(self, index):
        """ Retrieve the colour for a given attribute. """
        return self.palette[index]

    def set_all(self, new_palette, check_mode=True):
        """ Set the colours for all attributes. """
        mode = state.console_state.screen.mode
        if check_mode and new_palette and not self.mode_allows_palette(mode):
            return
        self.palette = list(new_palette)
        self.rgb_palette = [mode.colours[i] for i in self.palette]
        if mode.colours1:
            self.rgb_palette1 = [mode.colours1[i] for i in self.palette]
        else:
            self.rgb_palette1 = None
        video.update_palette(self.rgb_palette, self.rgb_palette1)

    def mode_allows_palette(self, mode):
        """ Check if the video mode allows palette change. """
        # effective palette change is an error in CGA
        if video_capabilities in ('cga', 'cga_old', 'mda', 'hercules', 'olivetti'):
            raise error.RunError(5)
        # ignore palette changes in Tandy/PCjr SCREEN 0
        elif video_capabilities in ('tandy', 'pcjr') and mode.is_text_mode:
            return False
        else:
            return True


###############################################################################
# cursor

class Cursor(object):
    """ Manage the cursor. """

    def __init__(self, screen):
        """ Initialise the cursor. """
        self.screen = screen
        # cursor visible in execute mode?
        self.visible_run = False
        # cursor shape
        self.from_line = 0
        self.to_line = 0    
        self.width = screen.mode.font_width
        self.height = screen.mode.font_height

    def init_mode(self, mode):
        """ Change the cursor for a new screen mode. """
        self.width = mode.font_width
        self.height = mode.font_height
        self.set_default_shape(True)
        self.reset_attr()
    
    def reset_attr(self):
        """ Set the text cursor attribute to that of the current location. """
        video.update_cursor_attr(self.screen.apage.row[
                state.console_state.row-1].buf[
                state.console_state.col-1][1] & 0xf)

    def show(self, do_show):
        """ Force cursor to be visible/invisible. """
        video.show_cursor(do_show)

    def set_visibility(self, visible_run):
        """ Set default cursor visibility. """
        self.visible_run = visible_run
        self.reset_visibility()
        
    def reset_visibility(self):
        """ Set cursor visibility to its default state. """
        # visible if in interactive mode, unless forced visible in text mode.
        visible = (not state.basic_state.execute_mode)
        # in graphics mode, we can't force the cursor to be visible on execute.
        if self.screen.mode.is_text_mode:
            visible = visible or self.visible_run
        video.show_cursor(visible)

    def set_shape(self, from_line, to_line):
        """ Set the cursor shape. """
        # A block from from_line to to_line in 8-line modes.
        # Use compatibility algo in higher resolutions
        mode = self.screen.mode
        fx, fy = self.width, self.height
        if egacursor:
            # odd treatment of cursors on EGA machines, 
            # presumably for backward compatibility
            # the following algorithm is based on DOSBox source int10_char.cpp 
            #     INT10_SetCursorShape(Bit8u first,Bit8u last)    
            max_line = fy - 1
            if from_line & 0xe0 == 0 and to_line & 0xe0 == 0:
                if (to_line < from_line):
                    # invisible only if to_line is zero and to_line < from_line
                    if to_line != 0: 
                        # block shape from *to_line* to end
                        from_line = to_line
                        to_line = max_line
                elif ((from_line | to_line) >= max_line or 
                            to_line != max_line-1 or from_line != max_line):
                    if to_line > 3:
                        if from_line+2 < to_line:
                            if from_line > 2:
                                from_line = (max_line+1) // 2
                            to_line = max_line
                        else:
                            from_line = from_line - to_line + max_line
                            to_line = max_line
                            if max_line > 0xc:
                                from_line -= 1
                                to_line -= 1
        self.from_line = max(0, min(from_line, fy-1))
        self.to_line = max(0, min(to_line, fy-1))
        video.build_cursor(self.width, fy, self.from_line, self.to_line)
        self.reset_attr()
        
    def set_default_shape(self, overwrite_shape):
        """ Set the cursor to one of two default shapes. """
        if overwrite_shape:
            if not self.screen.mode.is_text_mode: 
                # always a block cursor in graphics mode
                self.set_shape(0, self.height-1)
            elif video_capabilities == 'ega':
                # EGA cursor is on second last line
                self.set_shape(self.height-2, self.height-2)
            elif self.height == 9:
                # Tandy 9-pixel fonts; cursor on 8th
                self.set_shape(self.height-2, self.height-2)
            else:
                # other cards have cursor on last line
                self.set_shape(self.height-1, self.height-1)
        else:
            # half-block cursor for insert
            self.set_shape(self.height//2, self.height-1)

    def set_width(self, num_chars):
        """ Set the cursor with to num_chars characters. """
        new_width = num_chars * self.screen.mode.font_width
        # update cursor shape to new width if necessary    
        if new_width != self.width:
            self.width = new_width
            video.build_cursor(self.width, self.height, 
                               self.from_line, self.to_line)
            self.reset_attr()


###############################################################################
# light pen

pen_is_down = False
pen_pos = (0, 0)

class Pen(object):
    """ Light pen support. """
    
    def __init__(self):
        """ Initialise light pen. """
        self.was_down = False
        self.down_pos = (0, 0)

    def down(self, x, y):
        """ Report a pen-down event at graphical x,y """
        global pen_is_down
        # trigger PEN event
        state.basic_state.events.pen.trigger()
        # TRUE until polled
        self.was_down = True 
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

#D
def pen_down(x, y):
    """ Report a pen-down event at graphical x,y """
    state.console_state.pen.down(x, y)    
#D
def pen_up():
    """ Report a pen-up event at graphical x,y """
    state.console_state.pen.up()    
#D
def pen_moved(x, y):
    """ Report a pen-move event at graphical x,y """
    state.console_state.pen.moved(x, y)    
    
 
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

    def switch(self, on):
        """ Switch joystick handling on or off. """
        self.is_on = on

    def down(self, joy, button):
        """ Report a joystick button down event. """
        self.was_fired[joy][button] = True
        stick_is_firing[joy][button] = True
        # trigger STRIG event
        state.basic_state.events.strig[joy*2 + button].trigger()

    def up(self, joy, button):
        """ Report a joystick button up event. """
        stick_is_firing[joy][button] = False

    def moved(self, joy, axis, value):
        """ Report a joystick axis move. """
        stick_axis[joy][axis] = value

    def poll(self, fn):
        """ Poll the joystick axes. """    
        joy, axis = fn // 2, fn % 2
        return stick_axis[joy][axis]
        
    def poll_trigger(self, fn):       
        """ Poll the joystick buttons. """    
        joy, trig = fn // 4, (fn//2) % 2
        if fn % 2 == 0:
            # has been fired
            stick_was_trig = self.was_fired[joy][trig]
            self.was_fired[joy][trig] = False
            return stick_was_trig
        else:
            # is currently firing
            return stick_is_firing[joy][trig]


state.console_state.stick = Stick()


#D
def stick_down(joy, button):
    """ Report a joystick button down event. """
    state.console_state.stick.down(joy, button)
#D
def stick_up(joy, button):
    """ Report a joystick button up event. """
    state.console_state.stick.up(joy, button)
#D
def stick_moved(joy, axis, value):
    """ Report a joystick axis move. """
    state.console_state.stick.moved(joy, axis, value)
    

###############################################################################
# sound queue

# sound capabilities - '', 'pcjr' or 'tandy'
pcjr_sound = ''

# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000
# base frequency for noise source
base_freq = 3579545./1024.

# 12-tone equal temperament
# C, C#, D, D#, E, F, F#, G, G#, A, A#, B
note_freq = [ 440.*2**((i-33.)/12.) for i in range(84) ]
notes = {   'C':0, 'C#':1, 'D-':1, 'D':2, 'D#':3, 'E-':3, 'E':4, 'F':5, 'F#':6, 
            'G-':6, 'G':7, 'G#':8, 'A-':8, 'A':9, 'A#':10, 'B-':10, 'B':11 }


def prepare_audio():
    """ Prepare the audio subsystem. """
    global pcjr_sound
    # pcjr/tandy sound
    if config.options['syntax'] in ('pcjr', 'tandy'):
        pcjr_sound = config.options['syntax']
    # initialise sound queue
    state.console_state.sound = Sound()
    # tandy has SOUND ON by default, pcjr has it OFF
    state.console_state.sound.sound_on = (pcjr_sound == 'tandy')
    # pc-speaker on/off; (not implemented; not sure whether should be on)
    state.console_state.sound.beep_on = True

def init_audio():
    """ Initialise the audio backend. """
    global audio
    if not audio or not audio.init_sound():
        return False
    # rebuild sound queue
    for voice in range(4):    
        for note in state.console_state.sound.queue[voice]:
            frequency, duration, fill, loop, volume = note
            audio.play_sound(frequency, duration, fill, loop, voice, volume)
    return True


class PlayState(object):
    """ State variables of the PLAY command. """
    
    def __init__(self):
        """ Initialise play state. """
        self.octave = 4
        self.speed = 7./8.
        self.tempo = 2. # 2*0.25 =0 .5 seconds per quarter note
        self.length = 0.25
        self.volume = 15

class Sound(object):
    """ Sound queue manipulations. """

    def __init__(self):
        """ Initialise sound queue. """
        self.queue = [[], [], [], []]
        # Tandy/PCjr noise generator
        # frequency for noise sources
        self.noise_freq = [base_freq / v for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
        self.noise_freq[3] = 0.
        self.noise_freq[7] = 0.
        self.quiet_ticks = 0
        # Tandy/PCjr SOUND ON and BEEP ON
        self.sound_on = False
        self.beep_on = True
        self.reset()

    def reset(self):
        """ Reset PLAY state (CLEAR). """
        # music foreground (MF) mode        
        self.foreground = True
        # reset all PLAY state
        self.play_state = [ PlayState(), PlayState(), PlayState() ]

    def beep(self):
        """ Play the BEEP sound. """
        self.play_sound(800, 0.25)

    def play_sound(self, frequency, duration, fill=1, loop=False, voice=0, volume=15):
        """ Play a sound on the tone generator. """
        if frequency < 0:
            frequency = 0
        if ((pcjr_sound == 'tandy' or 
                (pcjr_sound == 'pcjr' and self.sound_on)) and
                frequency < 110. and frequency != 0):
            # pcjr, tandy play low frequencies as 110Hz
            frequency = 110.
        self.queue[voice].append((frequency, duration, fill, loop, volume))
        audio.play_sound(frequency, duration, fill, loop, voice, volume) 
        if voice == 2:
            # reset linked noise frequencies
            # /2 because we're using a 0x4000 rotation rather than 0x8000
            self.noise_freq[3] = frequency/2.
            self.noise_freq[7] = frequency/2.
        # at most 16 notes in the sound queue (not 32 as the guide says!)
        self.wait_music(15, wait_last=False)    

    def wait_music(self, wait_length=0, wait_last=True):
        """ Wait until the music has finished playing. """
        while ((wait_last and audio.busy()) or
                len(self.queue[0]) + wait_last - 1 > wait_length or
                len(self.queue[1]) + wait_last - 1 > wait_length or
                len(self.queue[2]) + wait_last - 1 > wait_length):
            wait()

    def stop_all_sound(self):
        """ Terminate all sounds immediately. """
        self.queue = [ [], [], [], [] ]
        audio.stop_all_sound()
        
    def play_noise(self, source, volume, duration, loop=False):
        """ Play a sound on the noise generator. """
        audio.set_noise(source > 3)
        frequency = self.noise_freq[source]
        self.queue[3].append((frequency, duration, 1, loop, volume))
        audio.play_sound(frequency, duration, 1, loop, 3, volume) 
        # don't wait for noise

    def queue_length(self, voice=0):
        """ Return the number of notes in the queue. """
        # top of sound_queue is currently playing
        return max(0, len(self.queue[voice])-1)

    def done(self, voice, number_left):
        """ Report a sound has finished playing, remove from queue. """ 
        # remove the notes that have been played
        while len(self.queue[voice]) > number_left:
            self.queue[voice].pop(0)

    def check_quit(self):
        """ Quit the mixer if not running a program and sound quiet for a while. """
        if self.queue != [[], [], [], []] or audio.busy():
            # could leave out the is_quiet call but for looping sounds 
            self.quiet_ticks = 0
        else:
            self.quiet_ticks += 1    
            if self.quiet_ticks > quiet_quit:
                # mixer is quiet and we're not running a program. 
                # quit to reduce pulseaudio cpu load
                if not state.basic_state.run_mode:
                    # this takes quite a while and leads to missed frames...
                    audio.quit_sound()
                    self.quiet_ticks = 0

    ### PLAY statement

    def play(self, mml_list):
        """ Parse a list of Music Macro Language strings. """
        gmls_list = []
        for mml in mml_list:
            gmls = StringIO()
            # don't convert to uppercase as VARPTR$ elements are case sensitive
            gmls.write(str(mml))
            gmls.seek(0)
            gmls_list.append(gmls)
        next_oct = 0
        voices = range(3)
        while True:
            if not voices:
                break
            for voice in voices:
                vstate = self.play_state[voice]
                gmls = gmls_list[voice]
                c = util.skip_read(gmls, draw_and_play.ml_whitepace).upper()
                if c == '':
                    voices.remove(voice)
                    continue
                elif c == ';':
                    continue
                elif c == 'X':
                    # execute substring
                    sub = draw_and_play.ml_parse_string(gmls)
                    pos = gmls.tell()
                    rest = gmls.read()
                    gmls.truncate(pos)
                    gmls.write(str(sub))
                    gmls.write(rest)
                    gmls.seek(pos)
                elif c == 'N':
                    note = draw_and_play.ml_parse_number(gmls)
                    dur = vstate.length
                    c = util.skip(gmls, draw_and_play.ml_whitepace).upper()
                    if c == '.':
                        gmls.read(1)
                        dur *= 1.5
                    if note > 0 and note <= 84:
                        self.play_sound(note_freq[note-1], dur*vstate.tempo, 
                                         vstate.speed, volume=vstate.volume,
                                         voice=voice)
                    elif note == 0:
                        self.play_sound(0, dur*vstate.tempo, vstate.speed,
                                        volume=0, voice=voice)
                elif c == 'L':
                    vstate.length = 1./draw_and_play.ml_parse_number(gmls)    
                elif c == 'T':
                    vstate.tempo = 240./draw_and_play.ml_parse_number(gmls)    
                elif c == 'O':
                    vstate.octave = min(6, max(0, draw_and_play.ml_parse_number(gmls)))
                elif c == '>':
                    vstate.octave += 1
                    if vstate.octave > 6:
                        vstate.octave = 6
                elif c == '<':
                    vstate.octave -= 1
                    if vstate.octave < 0:
                        vstate.octave = 0
                elif c in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'P'):
                    note = c
                    dur = vstate.length
                    while True:    
                        c = util.skip(gmls, draw_and_play.ml_whitepace).upper()
                        if c == '.':
                            gmls.read(1)
                            dur *= 1.5
                        elif c in representation.ascii_digits:
                            numstr = ''
                            while c in representation.ascii_digits:
                                gmls.read(1)
                                numstr += c 
                                c = util.skip(gmls, draw_and_play.ml_whitepace) 
                            length = vartypes.pass_int_unpack(representation.str_to_value_keep(('$', numstr)))
                            dur = 1. / float(length)
                        elif c in ('#', '+'):
                            gmls.read(1)
                            note += '#'
                        elif c == '-':
                            gmls.read(1)
                            note += '-'
                        else:
                            break                    
                    if note == 'P':
                        self.play_sound(0, dur * vstate.tempo, vstate.speed,
                                        volume=vstate.volume, voice=voice)
                    else:
                        self.play_sound(
                            note_freq[(vstate.octave+next_oct)*12 + notes[note]], 
                            dur * vstate.tempo, vstate.speed, 
                            volume=vstate.volume, voice=voice)
                    next_oct = 0
                elif c == 'M':
                    c = util.skip_read(gmls, draw_and_play.ml_whitepace).upper()
                    if c == 'N':        
                        vstate.speed = 7./8.
                    elif c == 'L':      
                        vstate.speed = 1.
                    elif c == 'S':      
                        vstate.speed = 3./4.        
                    elif c == 'F':      
                        self.foreground = True
                    elif c == 'B':      
                        self.foreground = False
                    else:
                        raise error.RunError(5)    
                elif c == 'V' and (pcjr_sound == 'tandy' or 
                                    (pcjr_sound == 'pcjr' and self.sound_on)): 
                    vstate.volume = min(15, 
                                    max(0, draw_and_play.ml_parse_number(gmls)))
                else:
                    raise error.RunError(5)    
        if self.foreground:
            self.wait_music()

#D        
def sound_done(voice, number_left):
    """ Report a sound has finished playing, remove from queue. """ 
    state.console_state.sound.done(voice, number_left)

###############################################################################
         
prepare()
