"""
PC-BASIC 3.23 - backend.py

Event loop; video, audio, keyboard, pen and joystick handling

(c) 2013, 2014 Rob Hagemans 

This file is released under the GNU GPL version 3. 
please see text file COPYING for licence terms.
"""

import logging

import config
import state 
import timedate
import unicodepage
import error
    
# backend implementations
video = None
audio = None 

#############################################
# sound queue

# sound queue
state.console_state.music_queue = [[], [], [], []]
# sound capabilities - '', 'pcjr' or 'tandy'
pcjr_sound = ''

#############################################
# keyboard queue

# capslock, numlock, scrollock mode 
state.console_state.caps = False
state.console_state.num = False
state.console_state.scroll = False
# let OS handle capslock effects
ignore_caps = True

# default function keys for KEY autotext. F1-F10
# F11 and F12 here are TANDY screencodes only!
function_key = { 
        '\x00\x3b':0, '\x00\x3c':1, '\x00\x3d':2, '\x00\x3e':3, '\x00\x3f':4,
        '\x00\x40':5, '\x00\x41':6, '\x00\x42':7, '\x00\x43':8, '\x00\x44':9,
        '\x00\x98':10, '\x00\x99':11 }
# user definable key list
state.console_state.key_replace = [ 
    'LIST ', 'RUN\r', 'LOAD"', 'SAVE"', 'CONT\r', ',"LPT1:"\r',
    'TRON\r', 'TROFF\r', 'KEY ', 'SCREEN 0,0,0\r', '', '' ]
# keyboard queue
state.console_state.keybuf = ''
# key buffer
# INP(&H60) scancode
state.console_state.inp_key = 0
# keypressed status of caps, num, scroll, alt, ctrl, shift
state.console_state.keystatus = 0
# input has closed
input_closed = False

#############################################
# screen buffer

class ScreenRow(object):
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


class ScreenBuffer(object):
    """ Buffer for a screen page. """
    
    def __init__(self, battr, bwidth, bheight):
        """ Initialise the screen buffer to given dimensions. """
        self.row = [ScreenRow(battr, bwidth) for _ in xrange(bheight)]


# redirect i/o to file or printer
input_echos = []
output_echos = []

#############################################
# initialisation

def prepare():
    """ Initialise backend module. """
    global pcjr_sound, ignore_caps, egacursor
    if config.options['capture_caps']:
        ignore_caps = False
    # inserted keystrokes
    for u in config.options['keys'].decode('string_escape').decode('utf-8'):
        c = u.encode('utf-8')
        try:
            state.console_state.keybuf += unicodepage.from_utf8(c)
        except KeyError:
            state.console_state.keybuf += c
    egacursor = config.options['video'] == 'ega'
    # pcjr/tandy sound
    pcjr_sound = config.options['pcjr_syntax']
    # tandy has SOUND ON by default, pcjr has it OFF
    state.console_state.sound_on = (pcjr_sound == 'tandy')
           
def init_video():
    """ Initialise the video backend. """
    global video
    if not video:
        return False
    return video.init()
    
def init_sound():
    """ Initialise the audio backend. """
    global audio
    if not audio or not audio.init_sound():
        return False
    # rebuild sound queue
    for voice in range(4):    
        for note in state.console_state.music_queue[voice]:
            audio.play_sound(*note)
    return True

#############################################
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
    check_quit_sound()
    # check console events
    video.check_events()   
    # trigger & handle BASIC events
    if state.basic_state.run_mode:
        # trigger TIMER, PLAY and COM events
        check_timer_event()
        check_play_event()
        check_com_events()
        # KEY, PEN and STRIG are triggered elsewhere
        # handle all events
        for handler in state.basic_state.all_handlers:
            handler.handle()


##############################
# screen buffer read/write

def put_screen_char_attr(cpage, crow, ccol, c, cattr, 
                         one_only=False, for_keys=False):
    """ Put a byte to the screen, redrawing SBCS and DBCS as necessary. """
    cattr = cattr & 0xf if state.console_state.screen_mode else cattr
    # update the screen buffer
    cpage.row[crow-1].buf[ccol-1] = (c, cattr)
    # mark the replaced char for refreshing
    start, stop = ccol, ccol+1
    cpage.row[crow-1].double[ccol-1] = 0
    # mark out sbcs and dbcs characters
    # only do dbcs in 80-character modes
    if unicodepage.dbcs and state.console_state.width == 80:
        orig_col = ccol
        # replace chars from here until necessary to update double-width chars
        therow = cpage.row[crow-1]    
        # replacing a trail byte? take one step back
        # previous char could be a lead byte? take a step back
        if (ccol > 1 and therow.double[ccol-2] != 2 and 
                (therow.buf[ccol-1][0] in unicodepage.trail or 
                 therow.buf[ccol-2][0] in unicodepage.lead)):
            ccol -= 1
            start -= 1
        # check all dbcs characters between here until it doesn't matter anymore
        while ccol < state.console_state.width:
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
            if (ccol >= state.console_state.width or 
                    (one_only and ccol > orig_col)):
                break  
        # check for box drawing
        if unicodepage.box_protect:
            ccol = start-2
            connecting = 0
            bset = -1
            while ccol < stop+2 and ccol < state.console_state.width:
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
                    if (ccol < state.console_state.width-1 and 
                            therow.double[ccol+1] == 2):
                        therow.double[ccol+1] = 0
                        stop = max(stop, ccol+2)
                ccol += 1        
    # update the screen            
    refresh_screen_range(cpage, crow, start, stop, for_keys)

def get_screen_char_attr(crow, ccol, want_attr):
    """ Retrieve a byte from the screen (SBCS or DBCS half-char). """
    ca = state.console_state.apage.row[crow-1].buf[ccol-1][want_attr]
    return ca if want_attr else ord(ca)

def get_text(start_row, start_col, stop_row, stop_col):   
    """ Retrieve a clip of the text between start and stop. """     
    r, c = start_row, start_col
    full = ''
    clip = ''
    while r < stop_row or (r == stop_row and c <= stop_col):
        clip += state.console_state.vpage.row[r-1].buf[c-1][0]    
        c += 1
        if c > state.console_state.width:
            if not state.console_state.vpage.row[r-1].wrap:
                full += unicodepage.UTF8Converter().to_utf8(clip) + '\r\n'
                clip = ''
            r += 1
            c = 1
    full += unicodepage.UTF8Converter().to_utf8(clip)        
    return full

def redraw_row(start, crow, wrap=True):
    """ Draw the screen row, wrapping around and reconstructing DBCS buffer. """
    while True:
        therow = state.console_state.apage.row[crow-1]  
        for i in range(start, therow.end): 
            # redrawing changes colour attributes to current foreground (cf. GW)
            # don't update all dbcs chars behind at each put
            put_screen_char_attr(state.console_state.apage, crow, i+1, 
                    therow.buf[i][0], state.console_state.attr, one_only=True)
        if (wrap and therow.wrap and 
                crow >= 0 and crow < state.console_state.height-1):
            crow += 1
            start = 0
        else:
            break    

def refresh_screen_range(cpage, crow, start, stop, for_keys=False):
    """ Redraw a section of a screen row, assuming DBCS buffer has been set. """
    therow = cpage.row[crow-1]
    ccol = start
    while ccol < stop:
        double = therow.double[ccol-1]
        if double == 1:
            ca = therow.buf[ccol-1]
            da = therow.buf[ccol]
            video.set_attr(da[1]) 
            video.putwc_at(crow, ccol, ca[0], da[0], for_keys)
            therow.double[ccol-1] = 1
            therow.double[ccol] = 2
            ccol += 2
        else:
            if double != 0:
                logging.debug('DBCS buffer corrupted at %d, %d', crow, ccol)
            ca = therow.buf[ccol-1]        
            video.set_attr(ca[1]) 
            video.putc_at(crow, ccol, ca[0], for_keys)
            ccol += 1


def redraw_text_screen():
    """ Redraw the active screen page, reconstructing DBCS buffers. """
    # force cursor invisible during redraw
    show_cursor(False)
    # this makes it feel faster
    video.clear_rows(state.console_state.attr, 1, 25)
    # redraw every character
    for crow in range(state.console_state.height):
        thepage = state.console_state.apage
        therow = thepage.row[crow]  
        for i in range(state.console_state.width): 
            put_screen_char_attr(thepage, crow+1, i+1, 
                                 therow.buf[i][0], therow.buf[i][1])
    # set cursor back to previous state                             
    update_cursor_visibility()

def print_screen():
    """ Output the visible page to LPT1. """
    for crow in range(1, state.console_state.height+1):
        line = ''
        for c, _ in state.console_state.vpage.row[crow-1].buf:
            line += c
        state.io_state.devices['LPT1:'].write_line(line)

def copy_page(src, dst):
    """ Copy source to destination page. """
    for x in range(state.console_state.height):
        dstrow = state.console_state.pages[dst].row[x]
        srcrow = state.console_state.pages[src].row[x]
        dstrow.buf[:] = srcrow.buf[:]
        dstrow.end = srcrow.end
        dstrow.wrap = srcrow.wrap            
    video.copy_page(src, dst)

def clear_screen_buffer_at(x, y):
    """ Remove the character covering a single pixel. """
    fx, fy = state.console_state.font_width, state.console_state.font_height
    cymax, cxmax = state.console_state.height-1, state.console_state.width-1 
    cx = min(cxmax, max(0, x // fx))
    cy = min(cymax, max(0, y // fy)) 
    state.console_state.apage.row[cy].buf[cx] = (' ', state.console_state.attr)

def clear_screen_buffer_area(x0, y0, x1, y1):
    """ Remove all characters from a rectangle of the graphics screen. """
    fx, fy = state.console_state.font_width, state.console_state.font_height
    cymax, cxmax = state.console_state.height-1, state.console_state.width-1 
    cx0 = min(cxmax, max(0, x0 // fx)) 
    cy0 = min(cymax, max(0, y0 // fy))
    cx1 = min(cxmax, max(0, x1 // fx)) 
    cy1 = min(cymax, max(0, y1 // fy))
    for r in range(cy0, cy1+1):
        state.console_state.apage.row[r].buf[cx0:cx1+1] = [
            (' ', state.console_state.attr)] * (cx1 - cx0 + 1)
    
##############################
# keyboard buffer read/write

def key_down(keycode, inpcode=None, keystatuscode=None):
    """ Insert a key-down event. Keycode is ascii, DBCS or NUL+scancode. """
    if keycode != '':
        insert_key(keycode)
    if inpcode != None:
        state.console_state.inp_key = inpcode
    if keystatuscode != None:
        state.console_state.keystatus |= keystatuscode
    
def key_up(inpcode=None, keystatuscode=None):
    """ Insert a key-up event. """
    if inpcode != None:
        state.console_state.inp_key = 0x80 + inpcode
    if keystatuscode != None:
        state.console_state.keystatus &= (0xffff ^ keystatuscode)
    
def insert_special_key(name):
    """ Insert a low-level handled: caps, num, scroll, print, break. """
    if name == 'break':
        raise error.Break()
    elif name == 'reset':
        raise error.Reset()
    elif name == 'quit':
        raise error.Exit()
    elif name == 's+print':
        print_screen()
    elif name == 'c+print':
        toggle_echo_lpt1()
    elif name == 'caps':
        state.console_state.caps = not state.console_state.caps
    elif name == 'num':
        state.console_state.num = not state.console_state.num
    elif name == 'scroll':
        state.console_state.scroll = not state.console_state.scroll
    else:
        logging.debug('Unknown special key: %s', name)
        
def insert_key(c):
    """ Insert character into keyboard buffer, apply macros, trigger events. """
    if len(c) > 0:
        try:
            keynum = state.basic_state.event_keys.index(c)
            if keynum > -1 and keynum < 20:
                if state.basic_state.key_handlers[keynum].enabled:
                    # trigger only once at most
                    state.basic_state.key_handlers[keynum].triggered = True
                    # don't enter into key buffer
                    return
        except ValueError:
            pass
    if state.console_state.caps and not ignore_caps:
        if c >= 'a' and c <= 'z':
            c = chr(ord(c)-32)
        elif c >= 'A' and c <= 'z':
            c = chr(ord(c)+32)
    if len(c) < 2:
        state.console_state.keybuf += c
    else:
        try:
            # only check F1-F10
            keynum = function_key[c]
            # can't be redefined in events - so must be event keys 1-10.
            if (state.basic_state.run_mode and 
                    state.basic_state.key_handlers[keynum].enabled or 
                    keynum > 9):
                # this key is being trapped, don't replace
                state.console_state.keybuf += c
            else:
                macro = state.console_state.key_replace[keynum]
                state.console_state.keybuf += macro
        except KeyError:
            state.console_state.keybuf += c

def peek_char():
    """ Peek character or scancode from keyboard buffer. """
    ch = ''
    if len(state.console_state.keybuf)>0:
        ch = state.console_state.keybuf[0]
        if ch == '\x00' and len(state.console_state.keybuf) > 0:
            ch += state.console_state.keybuf[1]
    return ch 

def wait_char():
    """ Wait for character, then return it but don't drop from queue. """
    while len(state.console_state.keybuf) == 0 and not input_closed:
        wait()
    return peek_char()

def pass_char(ch):
    """ Drop characters from keyboard buffer. """
    state.console_state.keybuf = state.console_state.keybuf[len(ch):]        
    return ch

#############################################
# cursor

def show_cursor(do_show):
    """ Force cursor to be visible/invisible. """
    video.update_cursor_visibility(do_show)

def update_cursor_visibility():
    """ Set cursor visibility to its default state. """
    # visible if in interactive mode, unless forced visible in text mode.
    visible = (not state.basic_state.execute_mode)
    if state.console_state.screen_mode == 0:
        visible = visible or state.console_state.cursor
    video.update_cursor_visibility(visible)

def set_cursor_shape(from_line, to_line):
    """ Set the cursor shape. """
    # A block from from_line to to_line in 8-line modes.
    # Use compatibility algo in higher resolutions
    if egacursor:
        # odd treatment of cursors on EGA machines, 
        # presumably for backward compatibility
        # the following algorithm is based on DOSBox source int10_char.cpp 
        #     INT10_SetCursorShape(Bit8u first,Bit8u last)    
        max_line = state.console_state.font_height-1
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
    state.console_state.cursor_from = max(0, min(from_line, 
                                      state.console_state.font_height-1))
    state.console_state.cursor_to = max(0, min(to_line, 
                                    state.console_state.font_height-1))
    video.build_cursor(state.console_state.cursor_width, 
                       state.console_state.font_height, 
                       state.console_state.cursor_from, 
                       state.console_state.cursor_to)
    video.update_cursor_attr(state.console_state.apage.row[state.console_state.row-1].buf[state.console_state.col-1][1] & 0xf)


#############################################
# I/O redirection

def toggle_echo_lpt1():
    """ Toggle copying of all screen I/O to LPT1. """
    lpt1 = state.io_state.devices['LPT1:']
    if lpt1.write in input_echos:
        input_echos.remove(lpt1.write)
        output_echos.remove(lpt1.write)
    else:    
        input_echos.append(lpt1.write)
        output_echos.append(lpt1.write)

##############################################
# light pen

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
    state.console_state.pen_pos = x, y
    
def get_pen(fn):
    """ Poll the pen. """
    posx, posy = pen_pos
    fw = state.console_state.font_width
    fh = state.console_state.font_height
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

state.console_state.music_foreground = True

base_freq = 3579545./1024.
state.console_state.noise_freq = [base_freq / v 
                                  for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
state.console_state.noise_freq[3] = 0.
state.console_state.noise_freq[7] = 0.

# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000
quiet_ticks = 0

def beep():
    """ Play the BEEP sound. """
    play_sound(800, 0.25)

def play_sound(frequency, duration, fill=1, loop=False, voice=0, volume=15):
    """ Play a sound on the tone generator. """
    if frequency < 0:
        frequency = 0
    if ((pcjr_sound == 'tandy' or 
            (pcjr_sound == 'pcjr' and state.console_state.sound_on)) and
            frequency < 110. and frequency != 0):
        # pcjr, tandy play low frequencies as 110Hz
        frequency = 110.
    state.console_state.music_queue[voice].append(
            (frequency, duration, fill, loop, volume))
    audio.play_sound(frequency, duration, fill, loop, voice, volume) 
    if voice == 2:
        # reset linked noise frequencies
        # /2 because we're using a 0x4000 rotation rather than 0x8000
        state.console_state.noise_freq[3] = frequency/2.
        state.console_state.noise_freq[7] = frequency/2.
    # at most 16 notes in the sound queue (not 32 as the guide says!)
    wait_music(15, wait_last=False)    

def play_noise(source, volume, duration, loop=False):
    """ Play a sound on the noise generator. """
    audio.set_noise(source > 3)
    frequency = state.console_state.noise_freq[source]
    state.console_state.music_queue[3].append(
            (frequency, duration, 1, loop, volume))
    audio.play_sound(frequency, duration, 1, loop, 3, volume) 
    # don't wait for noise

def stop_all_sound():
    """ Terminate all sounds immediately. """
    state.console_state.music_queue = [ [], [], [], [] ]
    audio.stop_all_sound()
        
def wait_music(wait_length=0, wait_last=True):
    """ Wait until the music has finished playing. """
    while ((wait_last and audio.busy()) or
            len(state.console_state.music_queue[0])+wait_last-1 > wait_length or
            len(state.console_state.music_queue[1])+wait_last-1 > wait_length or
            len(state.console_state.music_queue[2])+wait_last-1 > wait_length ):
        wait()
    
def music_queue_length(voice=0):
    """ Return the number of notes in the queue. """
    # top of sound_queue is currently playing
    return max(0, len(state.console_state.music_queue[voice])-1)
        
def sound_done(voice, number_left):
    """ Report a sound has finished playing, remove from queue. """ 
    # remove the notes that have been played
    while len(state.console_state.music_queue[voice]) > number_left:
        state.console_state.music_queue[voice].pop(0)

def check_quit_sound():
    """ Quit the mixer if not running a program and sound quiet for a while. """
    global quiet_ticks
    if state.console_state.music_queue == [[], [], [], []] and not audio.busy():
        # could leave out the is_quiet call but for looping sounds 
        quiet_ticks = 0
    else:
        quiet_ticks += 1    
        if quiet_ticks > quiet_quit:
            # mixer is quiet and we're not running a program. 
            # quit to reduce pulseaudio cpu load
            if not state.basic_state.run_mode:
                # this takes quite a while and leads to missed frames...
                audio.quit_sound()
                quiet_ticks = 0
            
#############################################
# BASIC event triggers        
        
def check_timer_event():
    """ Trigger timer events. """
    mutimer = timedate.timer_milliseconds() 
    if mutimer >= state.basic_state.timer_start+state.basic_state.timer_period:
        state.basic_state.timer_start = mutimer
        state.basic_state.timer_handler.triggered = True

def check_play_event():
    """ Trigger music queue events. """
    play_now = [music_queue_length(voice) for voice in range(3)]
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
    ports = (state.io_state.devices['COM1:'], state.io_state.devices['COM2:'])
    for comport in (0, 1):
        if ports[comport] and ports[comport].peek_char():
            state.basic_state.com_handlers[comport].triggered = True

prepare()
