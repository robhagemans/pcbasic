"""
PC-BASIC - signals.py
Signals for communication between interpreter and interface

(c) 2013--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""


class Event(object):
    """Signal object for input, video or audio queue."""

    def __init__(self, event_type, params=()):
        """Create signal."""
        self.event_type = event_type
        self.params = params


# audio queue signals
AUDIO_TONE = 0
AUDIO_STOP = 1
AUDIO_NOISE = 2
AUDIO_QUIT = 4
AUDIO_PERSIST = 6

# video queue signals
# save state and quit
VIDEO_QUIT = 0
# change video mode
VIDEO_SET_MODE = 1
# switch page
VIDEO_SET_PAGE = 2
# copy page
VIDEO_COPY_PAGE = 28
# show/hide cursor
VIDEO_SHOW_CURSOR = 14
# set cursor shape
VIDEO_SET_CURSOR_SHAPE = 3
# move cursor
VIDEO_MOVE_CURSOR = 5
# set border attribute
VIDEO_SET_BORDER_ATTR = 7
# put character glyph
VIDEO_PUT_TEXT = 8
# clear rows
VIDEO_CLEAR_ROWS = 10
# scroll
VIDEO_SCROLL_UP = 11
VIDEO_SCROLL_DOWN = 12
# set palette
VIDEO_SET_PALETTE = 15
# put rect
VIDEO_PUT_RECT = 20
# set caption message
VIDEO_SET_CAPTION = 29
# clipboard copy reply
VIDEO_SET_CLIPBOARD_TEXT = 30

# input queue signals
# quit interpreter
KEYB_QUIT = 0
# insert keydown
KEYB_DOWN = 5
# insert keyup
KEYB_UP = 6
# redirect or stdio input
STREAM_CHAR = 7
# redirect or stdio closed
STREAM_CLOSED = 8
# light pen events
PEN_DOWN = 101
PEN_UP = 102
PEN_MOVED = 103
# joystick events
STICK_DOWN = 201
STICK_UP = 202
STICK_MOVED = 203
# clipboard events
CLIP_COPY = 254
CLIP_PASTE = 255
