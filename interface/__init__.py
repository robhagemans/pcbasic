"""
PC-BASIC - interface package
Video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from base import InitFailed, run

# video plugins
from interface import video_none
from interface import video_ansi
from interface import video_cli
from interface import video_curses
from interface import video_pygame
from interface import video_sdl2

# audio plugins
from interface import audio_none
from interface import audio_beep
from interface import audio_pygame
from interface import audio_sdl2
