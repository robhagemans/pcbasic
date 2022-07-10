"""
PC-BASIC - signals.py
Signals for communication between interpreter and interface

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""


class Event(object):
    """Signal object for input, video or audio queue."""

    def __init__(self, event_type, params=()):
        """Create signal."""
        self.event_type = event_type
        self.params = params

    def __repr__(self):
        """Represent signal as string."""
        return '<Event %s: %r>' % (self.event_type, self.params)


# general signals

QUIT = 'quit'


# audio queue signals

# play tone
AUDIO_TONE = 'tone'
# play noise
AUDIO_NOISE = 'noise'
# stop sound
AUDIO_STOP = 'hush'
# keep sound engine alive even if quiet
AUDIO_PERSIST = 'persist'


# video queue signals

# change video mode
VIDEO_SET_MODE = 'set_mode'
# show/hide cursor
VIDEO_SHOW_CURSOR = 'show_cursor'
# set cursor shape
VIDEO_SET_CURSOR_SHAPE = 'set_cursor_shape'
# move cursor
VIDEO_MOVE_CURSOR = 'move_cursor'
# set border attribute
VIDEO_SET_BORDER_ATTR = 'set_border_attr'
# clear rows
VIDEO_CLEAR_ROWS = 'clear_rows'
# scroll
VIDEO_SCROLL = 'scroll'
# set palette
VIDEO_SET_PALETTE = 'set_palette'
# update screen section
VIDEO_UPDATE = 'update'
# set caption message
VIDEO_SET_CAPTION = 'set_caption'
# clipboard copy reply
VIDEO_SET_CLIPBOARD_TEXT = 'set_clipboard_text'


# input queue signals

# redirect or stdio input
STREAM_CHAR = 'stream_char'
# redirect or stdio closed
STREAM_CLOSED = 'stream_closed'
# keyboard events
KEYB_DOWN = 'key_down'
KEYB_UP = 'key_up'
# light pen events
PEN_DOWN = 'pen_down'
PEN_UP = 'pen_up'
PEN_MOVED = 'pen_moved'
# joystick events
STICK_DOWN = 'stick_down'
STICK_UP = 'stick_up'
STICK_MOVED = 'stick_moved'
# clipboard events
CLIP_COPY = 'clip_copy'
CLIP_PASTE = 'clip_paste'
