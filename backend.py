"""
PC-BASIC 3.23 - backend.py
Event loop; video, audio, keyboard, pen and joystick handling

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import logging
from copy import copy

import plat
import config
import state 
import timedate
import unicodepage
import scancode
import error
import vartypes
import util

# backend implementations
video = None
audio = None 

#############################################

# devices - SCRN: KYBD: LPT1: etc. These are initialised in iolayer module
devices = {}


###############################################################################
# initialisation

def prepare():
    """ Initialise backend module. """
    prepare_keyboard()
    prepare_audio()
    prepare_video()
    # initialise event triggers
    reset_events()    

def prepare_keyboard():
    """ Prepare keyboard handling. """
    global ignore_caps
    global num_fn_keys
    # inserted keystrokes
    if plat.system == 'Android':
        # string_escape not available on PGS4A
        keystring = config.options['keys'].decode('utf-8')
    else:
        keystring = config.options['keys'].decode('string_escape').decode('utf-8')    
    for u in keystring:
        c = u.encode('utf-8')
        try:
            state.console_state.keybuf.insert(unicodepage.from_utf8(c))
        except KeyError:
            state.console_state.keybuf.insert(c)
    # handle caps lock only if requested
    if config.options['capture-caps']:
        ignore_caps = False
    # function keys: F1-F12 for tandy, F1-F10 for gwbasic and pcjr
    if config.options['syntax'] == 'tandy':
        num_fn_keys = 12
    else:
        num_fn_keys = 10

def prepare_audio():
    """ Prepare the audio subsystem. """
    global pcjr_sound
    # pcjr/tandy sound
    if config.options['syntax'] in ('pcjr', 'tandy'):
        pcjr_sound = config.options['syntax']
    # initialise sound queue
    state.console_state.sound = Sound()
    #D
    state.console_state.music_queue = state.console_state.sound.queue
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
        for note in state.console_state.music_queue[voice]:
            audio.play_sound(*note)
    return True

def prepare_video():
    """ Prepare the video subsystem. """
    global egacursor
    global video_capabilities, composite_monitor, mono_monitor, mono_tint
    global colours16_mono, colours_ega_mono_0, colours_ega_mono_1, cga_low
    global colours_ega_mono_text
    global circle_aspect
    video_capabilities = config.options['video']
    if video_capabilities == 'tandy':
        circle_aspect = (3072, 2000)
    else:
        circle_aspect = (4, 3)
    # do all text modes with >8 pixels have an ega-cursor?    
    egacursor = config.options['video'] in (
        'ega', 'mda', 'ega_mono', 'vga', 'olivetti', 'hercules')
    composite_monitor = config.options['monitor'] == 'composite'
    mono_monitor = config.options['monitor'] == 'mono'
    if video_capabilities == 'ega' and mono_monitor:
        video_capabilities = 'ega_mono'
    if video_capabilities not in ('ega', 'vga'):
        state.console_state.colours = colours16
        state.console_state.palette = cga16_palette[:]
    cga_low = config.options['cga-low']
    set_cga4_palette(1)    
    # set monochrome tint and build mono palettes
    if config.options['mono-tint']:
        mono_tint = config.options['mono-tint']
    colours16_mono[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity16_mono ]            
    colours_ega_mono_0[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_ega_mono_0 ]            
    colours_ega_mono_1[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_ega_mono_1 ]        
    colours_mda_mono[:] = [ [tint*i//255 for tint in mono_tint]
                       for i in intensity_mda_mono ]
    if mono_monitor:
        # copy to replace 16-colours with 16-mono
        colours16[:] = colours16_mono
    # prepare video mode list
    # only allow the screen modes that the given machine supports
    # PCjr starts in 40-column mode
    # video memory size - default is EGA 256K
    state.console_state.screen = Screen(config.options['text-width'], 
                                        config.options['video-memory'])

###############################################################################
# stage 2 initialisation
           
def init_video(video_module):
    """ Initialise the video backend. """
    global video
    video = video_module
    if not video or not video.init():
        return False
    if state.loaded:
        # reload the screen in resumed state
        return resume_screen()
    else:        
        # initialise a fresh textmode screen
        state.console_state.screen.screen(None, None, None, None)
        return True

def resume_screen():
    """ Load a video mode from storage and initialise. """
    cmode = state.console_state.screen.mode
    nmode = state.console_state.screen.screen_mode
    if (not cmode.is_text_mode and 
            (nmode not in mode_data or cmode.name != mode_data[nmode].name)):
        logging.warning(
            "Resumed screen mode %d (%s) not supported by this setup",
            nmode, cmode.name)
        return False
    if not cmode.is_text_mode:    
        mode_info = mode_data[nmode]
    else:
        mode_info = text_data[cmode.width]
    if (cmode.is_text_mode and cmode.name != mode_info.name):
        # we switched adaptes on resume; fix font height, palette, cursor
        state.console_state.cursor_from = (state.console_state.cursor_from *
            mode_info.font_height) // cmode.font_height
        state.console_state.cursor_to = (state.console_state.cursor_to *
            mode_info.font_height) // cmode.font_height
        set_palette()
    # set up the appropriate screen resolution
    if (cmode.is_text_mode or video.supports_graphics_mode(mode_info)):
        # set the visible and active pages
        video.set_page(state.console_state.screen.vpagenum, 
                       state.console_state.screen.apagenum)
        # set the screen mde
        video.init_screen_mode(mode_info)
        # initialise rgb_palette global
        set_palette(state.console_state.palette, check_mode=False)
        video.update_palette(state.console_state.rgb_palette,
                             state.console_state.rgb_palette1)
        video.set_attr(state.console_state.screen.attr)
        # fix the cursor
        video.build_cursor(
            state.console_state.cursor_width, mode_info.font_height, 
            state.console_state.cursor_from, state.console_state.cursor_to)    
        video.move_cursor(state.console_state.row, state.console_state.col)
        video.update_cursor_attr(
                state.console_state.screen.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)
        update_cursor_visibility()
        video.set_border(state.console_state.screen.border_attr)
    else:
        # fix the terminal
        video.close()
        # mode not supported by backend
        logging.warning(
            "Resumed screen mode %d not supported by this interface.", nmode)
        return False
    if (cmode.is_text_mode and cmode.name != mode_info.name):
        state.console_state.screen.mode = mode_info
        redraw_text_screen()
    else:
        # load the screen contents from storage
        video.load_state()
    return True
    
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
        check_timer_event()
        check_play_event()
        check_com_events()
        # KEY, PEN and STRIG are triggered on handling the queue


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
# user definable key list
state.console_state.key_replace = [ 
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r',
    'TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '' ]
# switch off macro repacements
state.basic_state.key_macros_off = False    
# input has closed
input_closed = False
# bit flags for modifier keys
toggle = {
    scancode.INSERT: 0x80, scancode.CAPSLOCK: 0x40,  
    scancode.NUMLOCK: 0x20, scancode.SCROLLOCK: 0x10}
modifier = {    
    scancode.ALT: 0x8, scancode.CTRL: 0x4, 
    scancode.LSHIFT: 0x2, scancode.RSHIFT: 0x1}


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
        while self.buf.is_empty() and not input_closed:
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
            play_sound(800, 0.01)

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
        if (scan in (scancode.BREAK, scancode.SCROLLOCK) and
                    self.mod & modifier[scancode.CTRL]):
                raise error.Break()
        if scan == scancode.PRINT:
            if (self.mod & 
                    (modifier[scancode.LSHIFT] | modifier[scancode.RSHIFT])):
                # shift + printscreen
                state.console_state.screen.print_screen()
            if self.mod & modifier[scancode.CTRL]:
                # ctrl + printscreen
                toggle_echo_lpt1()
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
                    and state.basic_state.key_handlers[keynum].enabled):
                # this key is paused from being trapped, don't replace
                self.insert_chars(scan_to_eascii(scan, self.mod, 
                                  check_full=check_full))
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
            elif eascii >= 'A' and eascii <= 'z':
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


state.console_state.keyb = Keyboard()
#D 
state.console_state.keybuf = state.console_state.keyb.buf

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
# palette and colours

# CGA colours
colours16_colour = [    
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0x55,0x00), (0xaa,0xaa,0xaa), 
    (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) ]
# EGA colours
colours64 = [ 
    (0x00,0x00,0x00), (0x00,0x00,0xaa), (0x00,0xaa,0x00), (0x00,0xaa,0xaa),
    (0xaa,0x00,0x00), (0xaa,0x00,0xaa), (0xaa,0xaa,0x00), (0xaa,0xaa,0xaa), 
    (0x00,0x00,0x55), (0x00,0x00,0xff), (0x00,0xaa,0x55), (0x00,0xaa,0xff),
    (0xaa,0x00,0x55), (0xaa,0x00,0xff), (0xaa,0xaa,0x55), (0xaa,0xaa,0xff),
    (0x00,0x55,0x00), (0x00,0x55,0xaa), (0x00,0xff,0x00), (0x00,0xff,0xaa),
    (0xaa,0x55,0x00), (0xaa,0x55,0xaa), (0xaa,0xff,0x00), (0xaa,0xff,0xaa),
    (0x00,0x55,0x55), (0x00,0x55,0xff), (0x00,0xff,0x55), (0x00,0xff,0xff),
    (0xaa,0x55,0x55), (0xaa,0x55,0xff), (0xaa,0xff,0x55), (0xaa,0xff,0xff),
    (0x55,0x00,0x00), (0x55,0x00,0xaa), (0x55,0xaa,0x00), (0x55,0xaa,0xaa),
    (0xff,0x00,0x00), (0xff,0x00,0xaa), (0xff,0xaa,0x00), (0xff,0xaa,0xaa),
    (0x55,0x00,0x55), (0x55,0x00,0xff), (0x55,0xaa,0x55), (0x55,0xaa,0xff),
    (0xff,0x00,0x55), (0xff,0x00,0xff), (0xff,0xaa,0x55), (0xff,0xaa,0xff),
    (0x55,0x55,0x00), (0x55,0x55,0xaa), (0x55,0xff,0x00), (0x55,0xff,0xaa),
    (0xff,0x55,0x00), (0xff,0x55,0xaa), (0xff,0xff,0x00), (0xff,0xff,0xaa),
    (0x55,0x55,0x55), (0x55,0x55,0xff), (0x55,0xff,0x55), (0x55,0xff,0xff),
    (0xff,0x55,0x55), (0xff,0x55,0xff), (0xff,0xff,0x55), (0xff,0xff,0xff) ]

# mono intensities
# CGA mono
intensity16_mono = range(0x00, 0x100, 0x11) 
# SCREEN 10 EGA pseudocolours, blink state 0 and 1
intensity_ega_mono_0 = [0x00, 0x00, 0x00, 0xaa, 0xaa, 0xaa, 0xff, 0xff, 0xff]
intensity_ega_mono_1 = [0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff, 0x00, 0xaa, 0xff]
# MDA/EGA mono text intensity (blink is attr bit 7, like in colour mode)
intensity_mda_mono = [0x00, 0xaa, 0xff] 
# colour of monochrome monitor
mono_tint = (0xff, 0xff, 0xff)
# mono colours
colours16_mono = []
colours_ega_mono_0 = []
colours_ega_mono_1 = []
colours_mda_mono = []
colours16 = copy(colours16_colour)

# default cga 4-color palette can change with mode, so is a list
cga_mode_5 = False
cga4_palette = [0, 11, 13, 15]
# default 16-color and ega palettes
cga16_palette = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)
ega_palette = (0, 1, 2, 3, 4, 5, 20, 7, 56, 57, 58, 59, 60, 61, 62, 63)
ega_mono_palette = (0, 4, 1, 8)
# http://qbhlp.uebergeord.net/screen-statement-details-colors.html
# http://www.seasip.info/VintagePC/mda.html
# underline/intensity/reverse video attributes are slightly different from mda
# attributes 1, 9 should have underlining. 
ega_mono_text_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 0)
mda_palette = (0, 1, 1, 1, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 2, 2)
# use ega palette by default


# the available colours
state.console_state.colours = colours64
# blinking *colours* - only SCREEN 10, otherwise blink is an *attribute*
state.console_state.colours1 = None
# the palette defines the colour for each attribute
state.console_state.palette = list(ega_palette)


def set_palette_entry(index, colour, check_mode=True):
    """ Set a new colour for a given attribute. """
    # effective palette change is an error in CGA; ignore in Tandy/PCjr SCREEN 0
    if check_mode:
        if video_capabilities in ('cga', 'cga_old', 'mda', 
                                   'hercules', 'olivetti'):
            raise error.RunError(5)
        elif (video_capabilities in ('tandy', 'pcjr') and 
                state.console_state.screen.mode.is_text_mode):
            return
    state.console_state.palette[index] = colour
    state.console_state.rgb_palette[index] = (
        state.console_state.colours[colour])
    if state.console_state.colours1:
        state.console_state.rgb_palette1[index] = (
        state.console_state.colours1[colour])
    video.update_palette(state.console_state.rgb_palette,
                         state.console_state.rgb_palette1)

def get_palette_entry(index):
    """ Retrieve the colour for a given attribute. """
    return state.console_state.palette[index]

def set_palette(new_palette=None, check_mode=True):
    """ Set the colours for all attributes. """
    if check_mode and new_palette:
        if video_capabilities in ('cga', 'cga_old', 'mda', 
                                   'hercules', 'olivetti'):
            raise error.RunError(5)
        elif (video_capabilities in ('tandy', 'pcjr') and 
                state.console_state.screen.mode.is_text_mode):
            return
    if new_palette:
        state.console_state.palette = new_palette[:]
    else:    
        state.console_state.palette = list(state.console_state.screen.mode.palette)
    state.console_state.rgb_palette = [ 
        state.console_state.colours[i] for i in state.console_state.palette]
    if state.console_state.colours1:
        state.console_state.rgb_palette1 = [ 
            state.console_state.colours1[i] for i in state.console_state.palette]
    else:
        state.console_state.rgb_palette1 = None
    video.update_palette(state.console_state.rgb_palette, 
                         state.console_state.rgb_palette1)


cga4_palette_num = 1
def set_cga4_palette(num):
    """ Change the default CGA palette according to palette number & mode. """
    global cga4_palette_num
    cga4_palette_num = num
    # palette 1: Black, Ugh, Yuck, Bleah, choice of low & high intensity
    # palette 0: Black, Green, Red, Brown/Yellow, low & high intensity
    # tandy/pcjr have high-intensity white, but low-intensity colours
    # mode 5 (SCREEN 1 + colorburst on RGB) has red instead of magenta
    if video_capabilities in ('pcjr', 'tandy'):
        # pcjr does not have mode 5
        if num == 0:
            cga4_palette[:] = (0, 2, 4, 6)
        else:    
            cga4_palette[:] = (0, 3, 5, 15)
    elif cga_low:
        if cga_mode_5:
            cga4_palette[:] = (0, 3, 4, 7)
        elif num == 0:
            cga4_palette[:] = (0, 2, 4, 6)
        else:    
            cga4_palette[:] = (0, 3, 5, 7)
    else:
        if cga_mode_5:
            cga4_palette[:] = (0, 11, 12, 15)
        elif num == 0:
            cga4_palette[:] = (0, 10, 12, 14)
        else:    
            cga4_palette[:] = (0, 11, 13, 15)

def set_colorburst(on=True):
    """ Set the composite colorburst bit. """
    # On a composite monitor:
    # - on SCREEN 2 this enables artifacting
    # - on SCREEN 1 and 0 this switches between colour and greyscale
    # On an RGB monitor:
    # - on SCREEN 1 this switches between mode 4/5 palettes (RGB)
    # - ignored on other screens
    global cga_mode_5
    colorburst_capable = video_capabilities in (
                                'cga', 'cga_old', 'tandy', 'pcjr')
    if ((not state.console_state.screen.mode.is_text_mode) and
            state.console_state.screen.mode.name =='320x200x4' and 
            not composite_monitor):
        # ega ignores colorburst; tandy and pcjr have no mode 5
        cga_mode_5 = not (on or video_capabilities not in ('cga', 'cga_old'))
        set_cga4_palette(1)
    elif (on or not composite_monitor and not mono_monitor):
        # take modulo in case we're e.g. resuming ega text into a cga machine
        colours16[:] = colours16_colour
    else:
        colours16[:] = colours16_mono
    set_palette()
    video.set_colorburst(on and colorburst_capable, 
        state.console_state.rgb_palette, state.console_state.rgb_palette1)

###############################################################################
# video modes

class VideoMode(object):
    """ Base class for video modes. """
    def __init__(self, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages,
                  has_underline, has_blink,
                  video_segment, page_size
                  ):
        """ Initialise video mode settings. """
        self.is_text_mode = False
        self.name = name
        self.height = int(height)
        self.width = int(width)
        self.font_height = int(font_height)
        self.font_width = int(font_width)
        self.pixel_height = self.height*self.font_height
        self.pixel_width = self.width*self.font_width
        self.attr = int(attr)
        self.palette = tuple(palette)
        self.num_attr = len(palette)
        # colours is a reference
        self.colours = colours
        # colours1 is only used by EGA mono mode
        self.colours1 = None
        self.has_blink = has_blink
        self.has_underline = has_underline
        self.video_segment = int(video_segment)
        self.page_size = int(page_size)
        self.num_pages = int(num_pages) # or video_mem_size // self.page_size)
    
class TextMode(VideoMode):
    """ Default settings for a text mode. """
    
    def __init__(self, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages,
                  is_mono=False, has_underline=False, has_blink=True):
        """ Initialise video mode settings. """
        video_segment = 0xb000 if is_mono else 0xb800
        page_size = 0x1000 if width == 80 else 0x800
        VideoMode.__init__(self, name, height, width,
                  font_height, font_width, 
                  attr, palette, colours, 
                  num_pages, has_underline, has_blink, 
                  video_segment, page_size)
        self.is_text_mode = True
        self.num_attr = 32
        self.has_underline = has_underline
    
    def get_memory(addr):
        """ Retrieve a byte from textmode video memory. """
        addr -= self.video_segment*0x10
        page = addr // self.page_size
        offset = addr % self.page_size
        ccol = (offset % (self.width*2)) // 2
        crow = offset // (self.width*2)
        try:
            c = state.console_state.text.pages[page].row[crow].buf[ccol][addr%2]  
            return c if addr%2==1 else ord(c)
        except IndexError:
            return -1    
    
    def set_memory(addr, val):
        """ Set a byte in textmode video memory. """
        addr -= self.video_segment*0x10
        page = addr // self.page_size
        offset = addr % self.page_size
        ccol = (offset % (self.width*2)) // 2
        crow = offset // (self.width*2)
        try:
            c, a = state.console_state.text.pages[page].row[crow].buf[ccol]
            if addr%2 == 0:
                c = chr(val)
            else:
                a = val
            state.console_state.pages[page].put_char_attr(crow+1, ccol+1, c, a)
        except IndexError:
            pass


def get_pixel_byte(page, x, y, plane):
    """ Retrieve a byte with 8 packed pixels for one colour plane. """
    # modes 1-5: interleaved scan lines, pixels sequentially packed into bytes
    return sum(( ((video.get_pixel(x+shift, y, page) >> plane) & 1) 
                  << (7-shift) for shift in range(8) ))

def set_pixel_byte(page, x, y, plane_mask, byte):
    """ Set a packed-pixel byte for a given colour plane. """
    inv_mask = 0xff ^ plane_mask
    for shift in range(8):
        bit = (byte >> (7-shift)) & 1
        current = video.get_pixel(x + shift, y, page) & inv_mask
        video.put_pixel(x + shift, y, 
                                current | (bit * plane_mask), page)  

def get_area_ega(self, x0, y0, x1, y1, byte_array):
    """ Read a sprite from the screen in EGA modes. """
    dx = x1 - x0 + 1
    dy = y1 - y0 + 1
    # illegal fn call if outside screen boundary
    util.range_check(0, self.pixel_width-1, x0, x1)
    util.range_check(0, self.pixel_height-1, y0, y1)
    bpp = self.bitsperpixel
    # clear existing array only up to the length we'll use
    row_bytes = (dx+7) // 8
    length = 4 + dy * bpp * row_bytes
    byte_array[:length] = '\x00'*length
    byte_array[0:4] = vartypes.value_to_uint(dx) + vartypes.value_to_uint(dy) 
    byte = 4
    mask = 0x80
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            if mask == 0: 
                mask = 0x80
            pixel = video.get_pixel(x, y)
            for b in range(bpp):
                offset = ((y-y0) * bpp + b) * row_bytes + (x-x0) // 8 + 4
                try:
                    if pixel & (1 << b):
                        byte_array[offset] |= mask 
                except IndexError:
                    raise error.RunError(5)   
            mask >>= 1
        # byte align next row
        mask = 0x80

def set_area_ega(self, x0, y0, byte_array, operation):
    """ Put a stored sprite onto the screen in EGA modes. """
    bpp = self.bitsperpixel
    dx = vartypes.uint_to_value(byte_array[0:2])
    dy = vartypes.uint_to_value(byte_array[2:4])
    x1, y1 = x0+dx-1, y0+dy-1
    # illegal fn call if outside screen boundary
    util.range_check(0, self.pixel_width-1, x0, x1)
    util.range_check(0, self.pixel_height-1, y0, y1)
    video.apply_graph_clip()
    byte = 4
    mask = 0x80
    row_bytes = (dx+7) // 8
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            if mask == 0: 
                mask = 0x80
            if (x < 0 or x >= self.pixel_width
                    or y < 0 or y >= self.pixel_height):
                pixel = 0
            else:
                pixel = video.get_pixel(x,y)
            index = 0
            for b in range(bpp):
                try:
                    if (byte_array[4 + ((y-y0)*bpp + b)*row_bytes + (x-x0)//8] 
                            & mask) != 0:
                        index |= 1 << b  
                except IndexError:
                    pass
            mask >>= 1
            if (x >= 0 and x < self.pixel_width and 
                    y >= 0 and y < self.pixel_height):
                video.put_pixel(x, y, operation(pixel, index)) 
        # byte align next row
        mask = 0x80
    video.remove_graph_clip()
    return x0, y0, x1, y1

def build_tile_cga(self, pattern):
    """ Build a flood-fill tile for CGA screens. """
    tile = []    
    bpp = self.bitsperpixel
    strlen = len(pattern)
    # in modes 1, (2), 3, 4, 5, 6 colours are encoded in consecutive bits
    # each byte represents one scan line
    mask = 8 - bpp
    for y in range(strlen):
        line = []
        for x in range(8): # width is 8//bpp
            c = 0
            for b in range(bpp-1, -1, -1):
                c = (c<<1) + ((pattern[y] >> (mask+b)) & 1) 
            mask -= bpp
            if mask < 0:
                mask = 8 - bpp
            line.append(c)    
        tile.append(line)
    return tile


class GraphicsMode(VideoMode):
    """ Default settings for a graphics mode. """
    
    def __init__(self, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size,
                  num_pages=None,
                  has_blink=False,
                  supports_artifacts=False,
                  cursor_index=None,
                  pixel_aspect=None,
                  video_segment=0xb800,
                  ):
        """ Initialise video mode settings. """
        font_width = int(pixel_width // text_width)
        font_height = int(pixel_height // text_height)
        self.interleave_times = int(interleave_times)
        # cga bank_size = 0x2000 interleave_times=2
        self.bank_size = int(bank_size)
        page_size = self.interleave_times * self.bank_size
        VideoMode.__init__(self, name, text_height, text_width, 
                          font_height, font_width, attr, palette, colours,
                          num_pages, False, has_blink, video_segment, page_size)
        self.is_text_mode = False
        self.bitsperpixel = int(bitsperpixel)
        self.num_attr = 2**self.bitsperpixel
        self.bytes_per_row = int(pixel_width) * self.bitsperpixel // 8
        self.supports_artifacts = supports_artifacts
        self.cursor_index = cursor_index
        if pixel_aspect:
            self.pixel_aspect = pixel_aspect
        else:      
            self.pixel_aspect = (self.pixel_height * circle_aspect[0], 
                                 self.pixel_width * circle_aspect[1])

    def coord_ok(self, page, x, y):
        """ Check if a page and coordinates are within limits. """
        return (page >= 0 and page < self.num_pages and
                x >= 0 and x < self.pixel.width and
                y >= 0 and y < self.pixel.height)

    def cutoff_coord(self, x, y):
        """ Ensure coordinates are within screen + 1 pixel. """
        return min(self.pixel_width, max(-1, x)), min(self.pixel_height, max(-1, y))
    

class CGAMode(GraphicsMode):
    """ Default settings for a CGA graphics mode. """

    def get_coords(self, addr):
        """ Get video page and coordinates for address. """
        addr = int(addr) - self.video_segment * 0x10
        # modes 1-5: interleaved scan lines, pixels sequentially packed into bytes
        page, addr = addr//self.page_size, addr%self.page_size
        # 2 x interleaved scan lines of 80bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = col * 8 // self.bitsperpixel
        y = bank + self.interleave_times * row
        return page, x, y        
        
    def get_memory(self, addr):
        """ Retrieve a byte from CGA memory. """
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            return sum(( (video.get_pixel(x+shift, y, page) 
                            & (2**self.bitsperpixel-1)) 
                            << (8-(shift+1)*self.bitsperpixel) 
                    for shift in range(8//self.bitsperpixel)))

    def set_memory(self, addr, val):
        """ Set a byte in CGA memory. """
        mask = self.num_attr - 1 # 2**bpp-1
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            for shift in range(8 // self.bitsperpixel):
                nbit = (byte >> (8-(shift+1)*self.bitsperpixel)) & mask
                video.put_pixel(x + shift, y, nbit, page) 

    def get_area(self, x0, y0, x1, y1, byte_array):
        """ Read a sprite from the screen. """
        dx = x1 - x0 + 1
        dy = y1 - y0 + 1
        # illegal fn call if outside screen boundary
        util.range_check(0, self.pixel_width-1, x0, x1)
        util.range_check(0, self.pixel_height-1, y0, y1)
        bpp = self.bitsperpixel
        # clear existing array only up to the length we'll use
        length = 4 + ((dx * bpp + 7) // 8)*dy
        byte_array[:length] = '\x00'*length
        byte_array[0:2] = vartypes.value_to_uint(dx*bpp)
        byte_array[2:4] = vartypes.value_to_uint(dy)
        byte = 4
        shift = 8 - bpp
        for y in range(y0, y1+1):
            for x in range(x0, x1+1):
                if shift < 0:
                    byte += 1
                    shift = 8 - bpp
                pixel = video.get_pixel(x,y) # 2-bit value
                try:
                    byte_array[byte] |= pixel << shift
                except IndexError:
                    raise error.RunError(5)      
                shift -= bpp
            # byte align next row
            byte += 1
            shift = 8 - bpp

    def set_area(self, x0, y0, byte_array, operation):
        """ Put a stored sprite onto the screen. """
        # in cga modes, number of x bits is given rather than pixels
        bpp = self.bitsperpixel
        dx = vartypes.uint_to_value(byte_array[0:2]) / bpp
        dy = vartypes.uint_to_value(byte_array[2:4])
        x1, y1 = x0+dx-1, y0+dy-1
        # illegal fn call if outside screen boundary
        util.range_check(0, self.pixel_width-1, x0, x1)
        util.range_check(0, self.pixel_height-1, y0, y1)
        video.apply_graph_clip()
        byte = 4
        shift = 8 - bpp
        for y in range(y0, y1+1):
            for x in range(x0, x1+1):
                if shift < 0:
                    byte += 1
                    shift = 8 - bpp
                if (x < 0 or x >= self.pixel_width or 
                        y < 0 or y >= self.pixel_height):
                    pixel = 0
                else:
                    pixel = video.get_pixel(x,y)
                    try:    
                        index = (byte_array[byte] >> shift) % self.num_attr   
                    except IndexError:
                        pass                
                    video.put_pixel(x, y, operation(pixel, index))    
                shift -= bpp
            # byte align next row
            byte += 1
            shift = 8 - bpp
        video.remove_graph_clip()        
        return x0, y0, x1, y1

    build_tile = build_tile_cga


class EGAMode(GraphicsMode):
    """ Default settings for a EGA graphics mode. """

    def __init__(self, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size, num_pages, 
                  colours1=None, has_blink=False, planes_used=range(4), 
                  ):
        """ Initialise video mode settings. """
        GraphicsMode.__init__(self, name, pixel_width, pixel_height,
                  text_height, text_width, 
                  attr, palette, colours, bitsperpixel, 
                  interleave_times, bank_size,
                  num_pages, has_blink)
        # EGA uses colour planes, 1 bpp for each plane
        self.bytes_per_row = pixel_width // 8
        self.video_segment = 0xa000
        self.planes_used = planes_used
        self.plane_mask = sum([ 2**x for x in planes_used ])
        # this is a reference
        self.colours1 = colours1

    def get_coords(self, addr):
        """ Get video page and coordinates for address. """
        addr = int(addr) - self.video_segment * 0x10
        # modes 7-9: 1 bit per pixel per colour plane                
        page, addr = addr//self.page_size, addr%self.page_size
        x, y = (addr%self.bytes_per_row)*8, addr//self.bytes_per_row
        return page, x, y

    def get_memory(self, addr):   
        """ Retrieve a byte from EGA memory. """
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            plane = state.console_state.colour_plane % (max(planes_used)+1)
            if plane in planes_used:
                return get_pixel_byte(page, x, y, plane)

    def set_memory(self, addr, val):
        """ Set a byte in EGA video memory. """
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            mask = state.console_state.colour_plane_write_mask & self.plane_mask
            set_pixel_byte(page, x, y, mask, val)

    set_area = set_area_ega
    get_area = get_area_ega

    def build_tile(self, pattern):
        """ Build a flood-fill tile. """
        tile = []    
        bpp = self.bitsperpixel
        while len(pattern) % bpp != 0:
            # finish off the pattern with zeros
            pattern.append(0)
        strlen = len(pattern)
        # in modes (2), 7, 8, 9 each byte represents 8 bits
        # colour planes encoded in consecutive bytes
        mask = 7
        for y in range(strlen//bpp):
            line = []
            for x in range(8):
                c = 0
                for b in range(bpp-1, -1, -1):
                    c = (c<<1) + ((pattern[(y*bpp+b)%strlen] >> mask) & 1)
                mask -= 1
                if mask < 0:
                    mask = 7
                line.append(c)
            tile.append(line)    
        return tile


class Tandy6Mode(GraphicsMode):
    """ Default settings for Tandy graphics mode 6. """

    def __init__(self, *args, **kwargs):
        """ Initialise video mode settings. """
        GraphicsMode.__init__(self, *args, **kwargs)
        # mode 6: 4x interleaved scan lines, 8 pixels per two bytes, 
        # low attribute bits stored in even bytes, high bits in odd bytes.        
        self.bytes_per_row = self.pixel_width * 2 // 8
        self.video_segment = 0xb800

    def get_coords(addr):
        """ Get video page and coordinates for address. """
        addr =  int(addr) - self.video_segment * 0x10
        page, addr = addr//self.page_size, addr%self.page_size
        # 4 x interleaved scan lines of 160bytes
        bank, offset = addr//self.bank_size, addr%self.bank_size
        row, col = offset//self.bytes_per_row, offset%self.bytes_per_row
        x = (col // 2) * 8
        y = bank + 4 * row
        return page, x, y

    def get_memory(addr):
        """ Retrieve a byte from Tandy 640x200x4 """
        # 8 pixels per 2 bytes
        # low attribute bits stored in even bytes, high bits in odd bytes.        
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            return get_pixel_byte(page, x, y, addr%2) 

    def set_memory(addr, val):
        """ Set a byte in Tandy 640x200x4 memory. """
        page, x, y = self.get_coords(addr)
        if self.coord_ok(page, x, y):
            set_pixel_byte(page, x, y, 1<<(addr%2), val) 

    set_area = set_area_ega
    get_area = get_area_ega
    build_tile = build_tile_cga


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

    def put_char_attr(self, crow, ccol, c, cattr, one_only=False):
        """ Put a byte to the screen, reinterpreting SBCS and DBCS as necessary. """
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

# ega, tandy, pcjr
video_capabilities = 'ega'


# video memory
state.console_state.colour_plane = 0
state.console_state.colour_plane_write_mask = 0xff

        
        
class Screen(object):
    """ Screen manipulation operations. """

    def __init__(self, initial_width, video_mem_size):
        """ Minimal initialisiation of the screen. """
        self.screen_mode = 0
        self.colorswitch= 1
        self.apagenum = 0
        self.vpagenum = 0
        # current attribute
        self.attr = 7
        # border attribute
        self.border_attr = 0
        self.video_mem_size = video_mem_size
        self.prepare_modes()
        self.mode = text_data[initial_width]



    def prepare_modes(self):
        # Tandy/PCjr pixel aspect ratio is different from normal
        # suggesting screen aspect ratio is not 4/3.
        # Tandy pixel aspect ratios, experimentally found with CIRCLE:
        # screen 2, 6:     48/100   normal if aspect = 3072, 2000
        # screen 1, 4, 5:  96/100   normal if aspect = 3072, 2000
        # screen 3:      1968/1000 
        # screen 3 is strange, slighly off the 192/100 you'd expect
        graphics_mode = {
            # 04h 320x200x4  16384B 2bpp 0xb8000    screen 1
            # tandy:2 pages if 32k memory; ega: 1 page only 
            '320x200x4': 
                CGAMode('320x200x4', 320, 200, 25, 40, 3,
                        cga4_palette, colours16, bitsperpixel=2, 
                        interleave_times=2, bank_size=0x2000, 
                        num_pages=(
                            video_mem_size // (2*0x2000)
                            if video_capabilities in ('pcjr', 'tandy') 
                            else 1)),
            # 06h 640x200x2  16384B 1bpp 0xb8000    screen 2
            '640x200x2': 
                CGAMode('640x200x2', 640, 200, 25, 80, 1,
                        palette=(0, 15), colours=colours16, bitsperpixel=1,
                        interleave_times=2, bank_size=0x2000, num_pages=1,
                        supports_artifacts=True),
            # 08h 160x200x16 16384B 4bpp 0xb8000    PCjr/Tandy screen 3
            '160x200x16': 
                CGAMode('160x200x16', 160, 200, 25, 20, 15,
                        cga16_palette, colours16, bitsperpixel=4,
                        interleave_times=2, bank_size=0x2000,
                        num_pages=video_mem_size//(2*0x2000),
                        pixel_aspect=(1968, 1000), cursor_index=3),
            #     320x200x4  16384B 2bpp 0xb8000   Tandy/PCjr screen 4
            '320x200x4pcjr': 
                CGAMode('320x200x4pcjr', 320, 200, 25, 40, 3,
                        cga4_palette, colours16, bitsperpixel=2,
                        interleave_times=2, bank_size=0x2000,
                        num_pages=video_mem_size//(2*0x2000),
                        cursor_index=3),
            # 09h 320x200x16 32768B 4bpp 0xb8000    Tandy/PCjr screen 5
            '320x200x16pcjr': 
                CGAMode('320x200x16pcjr', 320, 200, 25, 40, 15,
                        cga16_palette, colours16, bitsperpixel=4,
                        interleave_times=4, bank_size=0x2000,
                        num_pages=video_mem_size//(4*0x2000),
                        cursor_index=3),
            # 0Ah 640x200x4  32768B 2bpp 0xb8000   Tandy/PCjr screen 6
            '640x200x4': 
                Tandy6Mode('640x200x4', 640, 200, 25, 80, 3,
                            cga4_palette, colours16, bitsperpixel=2,
                            interleave_times=4, bank_size=0x2000,
                            num_pages=video_mem_size//(4*0x2000),
                            cursor_index=3),
            # 0Dh 320x200x16 32768B 4bpp 0xa0000    EGA screen 7
            '320x200x16': 
                EGAMode('320x200x16', 320, 200, 25, 40, 15,
                        cga16_palette, colours16, bitsperpixel=4,
                        num_pages=video_mem_size//(4*0x2000),
                        interleave_times=1, bank_size=0x2000),                 
            # 0Eh 640x200x16    EGA screen 8
            '640x200x16': 
                EGAMode('640x200x16', 640, 200, 25, 80, 15,
                        cga16_palette, colours16, bitsperpixel=4,
                        num_pages=video_mem_size//(4*0x4000),
                        interleave_times=1, bank_size=0x4000),                 
            # 10h 640x350x16    EGA screen 9
            '640x350x16': 
                EGAMode('640x350x16', 640, 350, 25, 80, 15,
                        ega_palette, colours64, bitsperpixel=4,
                        num_pages=video_mem_size//(4*0x8000),
                        interleave_times=1, bank_size=0x8000),                 
            # 0Fh 640x350x4     EGA monochrome screen 10
            '640x350x4': 
                EGAMode('640x350x16', 640, 350, 25, 80, 1,
                        ega_mono_palette, colours_ega_mono_0, bitsperpixel=2,
                        interleave_times=1, bank_size=0x8000,
                        num_pages=video_mem_size//(2*0x8000),
                        colours1=colours_ega_mono_1, has_blink=True,
                        planes_used=(1, 3)),                 
            # 40h 640x400x2   1bpp  olivetti screen 3
            '640x400x2': 
                CGAMode('640x400x2', 640, 400, 25, 80, 1,
                        palette=(0, 15), colours=colours16, bitsperpixel=1,
                        interleave_times=4, bank_size=0x2000,
                        num_pages=1,
                        has_blink=True),
            # hercules screen 3
            '720x348x2': 
                # TODO hercules - this actually produces 350, not 348
                # two scan lines must be left out somewhere, somehow
                CGAMode('720x348x2', 720, 350, 25, 80, 1,
                        palette=(0, 15), colours=colours16_mono, bitsperpixel=1,
                        interleave_times=4, bank_size=0x2000,
                        num_pages=2,
                        has_blink=True),
            }
        if video_capabilities == 'vga':    
            # technically, VGA text does have underline 
            # but it's set to an invisible scanline
            # so not, so long as we're not allowing to set the scanline
            self.text_data = {
                40: TextMode('vgatext40', 25, 40, 16, 9, 7, 
                             ega_palette, colours64, num_pages=8),            
                80: TextMode('vgatext80', 25, 80, 16, 9, 7, 
                             ega_palette, colours64, num_pages=4)}
            self.mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                7: graphics_mode['320x200x16'],
                8: graphics_mode['640x200x16'],
                9: graphics_mode['640x350x16']}
        elif video_capabilities == 'ega':    
            self.text_data = {
                40: TextMode('egatext40', 25, 40, 14, 8, 7, 
                             ega_palette, colours64, num_pages=8),
                80: TextMode('egatext80', 25, 80, 14, 8, 7, 
                             ega_palette, colours64, num_pages=4)}
            self.mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                7: graphics_mode['320x200x16'],
                8: graphics_mode['640x200x16'],
                9: graphics_mode['640x350x16']}
        elif video_capabilities == 'ega_mono': 
            self.text_data = {
                40: TextMode('ega_monotext40', 25, 40, 14, 8, 7, 
                             mda_palette, colours_mda_mono, 
                             is_mono=True, has_underline=True, num_pages=8),
                80: TextMode('ega_monotext80', 25, 80, 14, 8, 7, 
                             mda_palette, colours_mda_mono, 
                             is_mono=True, has_underline=True, num_pages=4)}
            self.mode_data = {
                10: graphics_mode['640x350x4']}
        elif video_capabilities == 'mda': 
            self.text_data = {
                40: TextMode('mdatext40', 25, 40, 14, 9, 7,
                             mda_palette, colours_mda_mono,
                             is_mono=True, has_underline=True, num_pages=1),
                80: TextMode('mdatext80', 25, 80, 14, 9, 7,
                             mda_palette, colours_mda_mono,
                             is_mono=True, has_underline=True, num_pages=1) }
            self.mode_data = {}
        elif video_capabilities in ('cga', 'cga_old', 'pcjr', 'tandy'):    
            if video_capabilities == 'tandy': 
                self.text_data = {
                    40: TextMode('tandytext40', 25, 40, 9, 8, 7, 
                                  cga16_palette, colours16, num_pages=8),
                    80: TextMode('tandytext80', 25, 80, 9, 8, 7, 
                                  cga16_palette, colours16, num_pages=4)}
            else:
                self.text_data = {
                    40: TextMode('cgatext40', 25, 40, 8, 8, 7, 
                                 cga16_palette, colours16, num_pages=8),
                    80: TextMode('cgatext80', 25, 80, 8, 8, 7, 
                                 cga16_palette, colours16, num_pages=4)}
            if video_capabilities in ('cga', 'cga_old'):                     
                self.mode_data = {
                    1: graphics_mode['320x200x4'],
                    2: graphics_mode['640x200x2']}
            else:
                self.mode_data = {
                    1: graphics_mode['320x200x4'],
                    2: graphics_mode['640x200x2'],
                    3: graphics_mode['160x200x16'],
                    4: graphics_mode['320x200x4pcjr'],
                    5: graphics_mode['320x200x16pcjr'],
                    6: graphics_mode['640x200x4']}
        elif video_capabilities == 'hercules': 
            # herc attributes shld distinguish black, dim, normal, bright
            # see http://www.seasip.info/VintagePC/hercplus.html
            self.text_data = {
                40: TextMode('herculestext40', 25, 40, 14, 9, 7, 
                             mda_palette, colours_mda_mono,
                             is_mono=True, has_underline=True, num_pages=2),
                80: TextMode('herculestext80', 25, 80, 14, 9, 7, 
                             mda_palette, colours_mda_mono,
                             is_mono=True, has_underline=True, num_pages=2) }
            self.mode_data = {
                3: graphics_mode['720x348x2']}
        elif video_capabilities == 'olivetti': 
            self.text_data = {
                40: TextMode('olivettitext40', 25, 40, 16, 8, 7,
                              cga16_palette, colours16, num_pages=8),
                80: TextMode('olivettitext80', 25, 80, 16, 8, 7,
                              cga16_palette, colours16, num_pages=4) }
            self.mode_data = {
                1: graphics_mode['320x200x4'],
                2: graphics_mode['640x200x2'],
                3: graphics_mode['640x400x2']}
            # on Olivetti M24, all numbers 3-255 give the same altissima risoluzione
            for mode in range(4, 256):
                self.mode_data[mode] = graphics_mode['640x400x2']


    def screen(self, new_mode, new_colorswitch, new_apagenum, new_vpagenum, 
                 erase=1, new_width=None, recursion_depth=0):
        """ Change the video mode, colourburst, visible or active page. """
        # set default arguments
        if new_mode == None:
            new_mode = self.screen_mode
        if new_colorswitch == None:    
            new_colorswitch = self.colorswitch 
        else:
            new_colorswitch = (new_colorswitch != 0)
        # TODO: implement erase level (Tandy/pcjr)
        # Erase tells basic how much video memory to erase
        # 0: do not erase video memory
        # 1: (default) erase old and new page if screen or bust changes
        # 2: erase all video memory if screen or bust changes 
        if new_mode == 0 and new_width == None:
            # width persists on change to screen 0
            new_width = self.mode.width 
            # if we switch out of a 20-col mode (Tandy screen 3), switch to 40-col.
            if new_width == 20:
                new_width = 40
        try:
            if new_mode != 0:    
                info = mode_data[new_mode]
            else:
                info = text_data[new_width]
        except KeyError:
            # no such mode
            info = None
        # vpage and apage nums are persistent on mode switch
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
        # if the new mode has fewer pages than current vpage/apage, 
        # illegal fn call before anything happens.
        if (not info or new_apagenum >= info.num_pages or 
                new_vpagenum >= info.num_pages or 
                (new_mode != 0 and not video.supports_graphics_mode(info))):
            # reset palette happens 
            # even if the function fails with Illegal Function Call
            set_palette(self.mode.palette)
            return False
        # attribute persists on width-only change
        if not (self.screen_mode == 0 and new_mode == 0 
                and self.apagenum == new_apagenum 
                and self.vpagenum == new_vpagenum):
            self.attr = info.attr
        # start with black border 
        if new_mode != self.screen_mode:
            set_border(0)
        # set the screen parameters
        self.screen_mode = new_mode
        self.colorswitch = new_colorswitch 
        # set all state vars
        self.mode = info
        # these are all duplicates
        state.console_state.colours = info.colours
        state.console_state.colours1 = info.colours1
        # build the screen buffer    
        self.text = TextBuffer(self.attr, self.mode.width, 
                               self.mode.height, self.mode.num_pages)
        # set active page & visible page, counting from 0. 
        self.set_page(new_vpagenum, new_apagenum)
        # set graphics characteristics
        if not self.mode.is_text_mode:
            # viewport        
            self.view_absolute = False
            self.view = None
            # logical window
            state.console_state.graph_window = None
            state.console_state.graph_window_bounds = None
            # centre of new graphics screen
            state.console_state.last_point = (
                            self.mode.pixel_width/2, self.mode.pixel_height/2)
            state.console_state.pixel_aspect_ratio = self.mode.pixel_aspect
            state.console_state.last_attr = self.attr
        # cursor width starts out as single char
        state.console_state.cursor_width = info.font_width        
        # signal the backend to change the screen resolution
        if not video.init_screen_mode(info):
            # something broke at the backend. fallback to text mode and give error.
            # this is not ideal but better than crashing.
            if not recursion_depth:
                self.screen(0, 0, 0, 0, recursion_depth=recursion_depth+1)
            return False
        # set the palette (essential on first run, or not all globals defined)
        set_palette()
        # set the attribute
        video.set_attr(self.attr)
        # in screen 0, 1, set colorburst (not in SCREEN 2!)
        if info.is_text_mode:
            set_colorburst(new_colorswitch)
        elif info.name == '320x200x4':    
            set_colorburst(not new_colorswitch)
        elif info.name == '640x200x2':
            set_colorburst(False)    
        return True

    def set_width(self, to_width):
        """ Set the character width of the screen. """
        if to_width == 20:
            if video_capabilities in ('pcjr', 'tandy'):
                return self.screen(3, None, None, None)
            else:
                return False
        elif self.mode.is_text_mode:
            return self.screen(0, None, None, None, new_width=to_width) 
        elif to_width == 40:
            if self.mode.name == '640x200x2':
                return self.screen(1, None, None, None)
            elif self.mode.name == '160x200x16':
                return self.screen(1, None, None, None)
            elif self.mode.name == '640x200x4':
                return self.screen(5, None, None, None)
            elif self.mode.name == '640x200x16':
                return self.screen(7, None, None, None)
            elif self.mode.name == '640x350x16':
                return self.screen(7, None, None, None)
        elif to_width == 80:
            if self.mode.name == '320x200x4':
                return self.screen(2, None, None, None)
            elif self.mode.name == '160x200x16':
                return self.screen(2, None, None, None)
            elif self.mode.name == '320x200x4pcjr':
                return self.screen(2, None, None, None)
            elif self.mode.name == '320x200x16pcjr':
                return self.screen(6, None, None, None)
            elif self.mode.name == '320x200x16':
                return self.screen(8, None, None, None)
        return False

    def set_video_memory_size(new_size):
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
        new_mode = mode_data[self.screen_mode]
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
                            one_only=False, for_keys=False):
        """ Put a byte to the screen, redrawing as necessary. """
        if not self.mode.is_text_mode:
            cattr = cattr & 0xf
        start, stop = self.text.pages[pagenum].put_char_attr(crow, ccol, c, cattr, one_only)
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
                    logging.debug('DBCS buffer corrupted at %d, %d', crow, ccol)
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
                        therow.buf[i][0], self.attr, one_only=True)
            if (wrap and therow.wrap and 
                    crow >= 0 and crow < self.text.height-1):
                crow += 1
                start = 0
            else:
                break    

    def redraw_text_screen(self):
        """ Redraw the active screen page, reconstructing DBCS buffers. """
        # force cursor invisible during redraw
        show_cursor(False)
        # this makes it feel faster
        video.clear_rows(self.attr, 1, self.mode.height)
        # redraw every character
        for crow in range(self.mode.height):
            therow = self.apage.row[crow]  
            for i in range(self.mode.width): 
                self.put_char_attr(self.apagenum, crow+1, i+1, 
                                     therow.buf[i][0], therow.buf[i][1])
        # set cursor back to previous state                             
        update_cursor_visibility()

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

    ## graphics primitives

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

    def fill_rect(self, x0, y0, x1, y1, index):
        """ Fill a rectangle in a solid attribute. """
        video.fill_rect(x0, y0, x1, y1, index)
        self.clear_text_area(x0, y0, x1, y1)

    def fill_interval(self, x0, x1, y, tile, solid):
        """ Fill a scanline interval in a tile pattern or solid attribute. """
        video.fill_interval(x0, x1, y, tile, solid)
        self.clear_text_area(x0, y, x1, y)

    ## viewport

    def unset_view(self):
        """ Unset the graphics viewport. """
        self.view_absolute = False
        self.view = None
        state.console_state.last_point = video.unset_graph_clip()
        if state.console_state.graph_window_bounds != None:
            graphics.set_graph_window(*state.console_state.graph_window_bounds)
    
    def set_view(self, x0, y0, x1, y1, absolute=True):
        """ Set the graphics viewport. """
        # VIEW orders the coordinates
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        self.view_absolute = absolute
        self.view = x0, y0, x1, y1
        video.set_graph_clip(x0, y0, x1, y1)
        if self.view_absolute:
            state.console_state.last_point = x0 + (x1-x0)/2, y0 + (y1-y0)/2
        else:
            state.console_state.last_point = (x1-x0)/2, (y1-y0)/2
        if state.console_state.graph_window_bounds != None:
            graphics.set_graph_window(*state.console_state.graph_window_bounds)

    def view_coords(self, x, y):
        """ Retrieve absolute coordinates for viewport coordinates. """
        if (not self.view) or self.view_absolute:
            return x, y
        else:
            return x + self.view[0], y + self.view[1]

    def clear_view(self):
        """ Clear the current graphics viewport. """
        if not state.console_state.screen.mode.is_text_mode:
            video.clear_graph_clip((self.attr>>4) & 0x7)

    

#############################################
# cursor

# cursor visible in execute mode?
state.console_state.cursor = False
# cursor shape
state.console_state.cursor_from = 0
state.console_state.cursor_to = 0    


def show_cursor(do_show):
    """ Force cursor to be visible/invisible. """
    video.update_cursor_visibility(do_show)

def update_cursor_visibility():
    """ Set cursor visibility to its default state. """
    # visible if in interactive mode, unless forced visible in text mode.
    visible = (not state.basic_state.execute_mode)
    if state.console_state.screen.mode.is_text_mode:
        visible = visible or state.console_state.cursor
    video.update_cursor_visibility(visible)

def set_cursor_shape(from_line, to_line):
    """ Set the cursor shape. """
    # A block from from_line to to_line in 8-line modes.
    # Use compatibility algo in higher resolutions
    mode = state.console_state.screen.mode
    fx, fy = mode.font_width, mode.font_height
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
    state.console_state.cursor_from = max(0, min(from_line, fy-1))
    state.console_state.cursor_to = max(0, min(to_line, fy-1))
    video.build_cursor(state.console_state.cursor_width, fy, 
                       state.console_state.cursor_from, 
                       state.console_state.cursor_to)
    video.update_cursor_attr(state.console_state.screen.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)

#############################################
# I/O redirection

# redirect i/o to file or printer
input_echos = []
output_echos = []

def toggle_echo_lpt1():
    """ Toggle copying of all screen I/O to LPT1. """
    lpt1 = devices['LPT1:']
    if lpt1.write in input_echos:
        input_echos.remove(lpt1.write)
        output_echos.remove(lpt1.write)
    else:    
        input_echos.append(lpt1.write)
        output_echos.append(lpt1.write)




##############################################
# light pen

state.console_state.pen_is_on = False
state.console_state.pen_was_down = False
pen_is_down = False
state.console_state.pen_down_pos = (0, 0)
pen_pos = (0, 0)

def pen_down(x, y):
    """ Report a pen-down event at graphical x,y """
    global pen_is_down
    state.basic_state.pen_handler.triggered = True
    state.console_state.pen_was_down = True # TRUE until polled
    pen_is_down = True # TRUE until pen up
    state.console_state.pen_down_pos = x, y

def pen_up():
    """ Report a pen-up event at graphical x,y """
    global pen_is_down
    pen_is_down = False
    
def pen_moved(x, y):
    """ Report a pen-move event at graphical x,y """
    global pen_pos
    pen_pos = x, y
    
def get_pen(fn):
    """ Poll the pen. """
    posx, posy = pen_pos
    fw = state.console_state.screen.mode.font_width
    fh = state.console_state.screen.mode.font_height
    if fn == 0:
        pen_down_old, state.console_state.pen_was_down = (
                state.console_state.pen_was_down, False)
        return -1 if pen_down_old else 0
    elif fn == 1:
        return state.console_state.pen_down_pos[0]
    elif fn == 2:
        return state.console_state.pen_down_pos[1]
    elif fn == 3:
        return -1 if pen_is_down else 0 
    elif fn == 4:
        return posx
    elif fn == 5:
        return posy
    elif fn == 6:
        return 1 + state.console_state.pen_down_pos[1]//fh
    elif fn == 7:
        return 1 + state.console_state.pen_down_pos[0]//fw
    elif fn == 8:
        return 1 + posy//fh
    elif fn == 9:
        return 1 + posx//fw
 
##############################################
# joysticks

state.console_state.stick_is_on = False
state.console_state.stick_was_fired = [[False, False], [False, False]]
stick_is_firing = [[False, False], [False, False]]
# axis 0--255; 128 is mid but reports 0, not 128 if no joysticks present
stick_axis = [[0, 0], [0, 0]]

def stick_down(joy, button):
    """ Report a joystick button down event. """
    state.console_state.stick_was_fired[joy][button] = True
    stick_is_firing[joy][button] = True
    state.basic_state.strig_handlers[joy*2 + button].triggered = True

def stick_up(joy, button):
    """ Report a joystick button up event. """
    stick_is_firing[joy][button] = False

def stick_moved(joy, axis, value):
    """ Report a joystick axis move. """
    stick_axis[joy][axis] = value

def get_stick(fn):
    """ Poll the joystick axes. """    
    joy, axis = fn // 2, fn % 2
    return stick_axis[joy][axis]
    
def get_strig(fn):       
    """ Poll the joystick buttons. """    
    joy, trig = fn // 4, (fn//2) % 2
    if fn % 2 == 0:
        # has been fired
        stick_was_trig = state.console_state.stick_was_fired[joy][trig]
        state.console_state.stick_was_fired[joy][trig] = False
        return stick_was_trig
    else:
        # is currently firing
        return stick_is_firing[joy][trig]


##############################
# sound queue read/write

# sound capabilities - '', 'pcjr' or 'tandy'
pcjr_sound = ''

# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000
# base frequency for noise source
base_freq = 3579545./1024.

class Sound(object):
    """ Sound queue manipulations. """

    def __init__(self):
        """ Initialise sound queue. """
        self.queue = [[], [], [], []]
        # music foreground (MF) mode        
        self.foreground = True
        # Tandy/PCjr noise generator
        # frequency for noise sources
        self.noise_freq = [base_freq / v for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
        self.noise_freq[3] = 0.
        self.noise_freq[7] = 0.
        self.quiet_ticks = 0
        # Tandy/PCjr SOUND ON and BEEP ON
        self.sound_on = False
        self.beep_on = True

    def beep(self):
        """ Play the BEEP sound. """
        self.play_sound(800, 0.25)

    def play_sound(self, frequency, duration, fill=1, loop=False, voice=0, volume=15):
        """ Play a sound on the tone generator. """
        if frequency < 0:
            frequency = 0
        if ((pcjr_sound == 'tandy' or 
                (pcjr_sound == 'pcjr' and state.console_state.sound.sound_on)) and
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
        self.music_queue = [ [], [], [], [] ]
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

#D        
def sound_done(voice, number_left):
    """ Report a sound has finished playing, remove from queue. """ 
    state.console_state.sound.done(voice, number_left)

            
#############################################
# BASIC event triggers        
        
class EventHandler(object):
    """ Keeps track of event triggers. """
    
    def __init__(self):
        """ Initialise untriggered and disabled. """
        self.reset()
        
    def reset(self):
        """ Reet to untriggered and disabled initial state. """
        self.gosub = None
        self.enabled = False
        self.stopped = False
        self.triggered = False

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

def reset_events():
    """ Initialise or reset event triggers. """
    # TIMER
    state.basic_state.timer_period, state.basic_state.timer_start = 0, 0
    state.basic_state.timer_handler = EventHandler()
    # KEY
    state.basic_state.event_keys = [''] * 20
    # F1-F10
    state.basic_state.event_keys[0:10] = [
        '\x00\x3b', '\x00\x3c', '\x00\x3d', '\x00\x3e', '\x00\x3f',
        '\x00\x40', '\x00\x41', '\x00\x42', '\x00\x43', '\x00\x44']
    # Tandy F11, F12
    if num_fn_keys == 12:
        state.basic_state.event_keys[10:12] = ['\x00\x98', '\x00\x99']
    # up, left, right, down
    state.basic_state.event_keys[num_fn_keys:num_fn_keys+4] = [   
        '\x00\x48', '\x00\x4b', '\x00\x4d', '\x00\x50']
    # the remaining keys are user definable        
    state.basic_state.key_handlers = [EventHandler() for _ in xrange(20)]
    # PLAY
    state.basic_state.play_last = [0, 0, 0]
    state.basic_state.play_trig = 1
    state.basic_state.play_handler = EventHandler()
    # COM
    state.basic_state.com_handlers = [EventHandler(), EventHandler()]  
    # PEN
    state.basic_state.pen_handler = EventHandler()
    # STRIG
    state.basic_state.strig_handlers = [EventHandler() for _ in xrange(4)]
    # all handlers in order of handling; TIMER first
    state.basic_state.all_handlers = [state.basic_state.timer_handler]  
    # key events are not handled FIFO but first 11-20 in that order, then 1-10
    state.basic_state.all_handlers += [state.basic_state.key_handlers[num] 
                                       for num in (range(10, 20) + range(10))]
    # this determined handling order
    state.basic_state.all_handlers += (
            [state.basic_state.play_handler] + state.basic_state.com_handlers + 
            [state.basic_state.pen_handler] + state.basic_state.strig_handlers)
    # set suspension off
    state.basic_state.suspend_all_events = False

def check_timer_event():
    """ Trigger TIMER events. """
    mutimer = timedate.timer_milliseconds() 
    if mutimer >= state.basic_state.timer_start+state.basic_state.timer_period:
        state.basic_state.timer_start = mutimer
        state.basic_state.timer_handler.triggered = True

def check_play_event():
    """ Trigger PLAY (music queue) events. """
    play_now = [state.console_state.sound.queue_length(voice) for voice in range(3)]
    if pcjr_sound: 
        for voice in range(3):
            if (play_now[voice] <= state.basic_state.play_trig and 
                    play_now[voice] > 0 and 
                    play_now[voice] != state.basic_state.play_last[voice] ):
                state.basic_state.play_handler.triggered = True 
    else:    
        if (state.basic_state.play_last[0] >= state.basic_state.play_trig and 
                play_now[0] < state.basic_state.play_trig):    
            state.basic_state.play_handler.triggered = True     
    state.basic_state.play_last = play_now

def check_com_events():
    """ Trigger COM-port events. """
    ports = (devices['COM1:'], devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports[comport].peek_char():
            state.basic_state.com_handlers[comport].triggered = True

def check_key_event(scancode, modifiers):
    """ Trigger KEYboard events. """
    # "Extended ascii": ascii 1-255 or NUL+code where code is often but not
    # always the keyboard scancode. See e.g. Tandy 1000 BASIC manual for a good
    # overview. DBCS is simply entered as a string of ascii codes.
    # check for scancode (inp_code) events
    if not scancode:
        return False
    try:
        keynum = state.basic_state.event_keys.index('\0' + chr(scancode))
        # for pre-defined KEYs 1-14 (and 1-16 on Tandy) the modifier status 
        # is ignored.
        if (keynum >= 0 and keynum < num_fn_keys + 4 and 
                    state.basic_state.key_handlers[keynum].enabled):
                # trigger function or arrow key event
                state.basic_state.key_handlers[keynum].triggered = True
                # don't enter into key buffer
                return True
    except ValueError:
        pass
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
    # from modifiers, exclude scroll lock at 0x10 and insert 0x80.
    trigger_code = chr(modifiers & 0x6f) + chr(scancode)
    try:
        keynum = state.basic_state.event_keys.index(trigger_code)
        if (keynum >= num_fn_keys + 4 and keynum < 20 and
                    state.basic_state.key_handlers[keynum].enabled):
                # trigger user-defined key
                state.basic_state.key_handlers[keynum].triggered = True
                # don't enter into key buffer
                return True
    except ValueError:
        pass
    return False



prepare()
