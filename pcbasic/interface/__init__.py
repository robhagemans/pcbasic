"""
PC-BASIC - interface package
Video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import run, video_plugins, audio_plugins, InitFailed

# video plugins
from .video_none import VideoNone
from .video_ansi import VideoANSI
from .video_cli import VideoCLI
from .video_curses import VideoCurses
from .video_pygame import VideoPygame
from .video_sdl2 import VideoSDL2

# audio plugins
from .audio_none import AudioNone
from .audio_beep import AudioBeep
from .audio_pygame import AudioPygame
from .audio_sdl2 import AudioSDL2


video_plugins.update({
    # interface_name: ((video_plugin_name, ...), fallback)
    'none': ((VideoNone,), None),
    'cli': ((VideoCLI,), 'none'),
    'text': ((VideoCurses, VideoANSI), 'cli'),
    'graphical':  ((VideoPygame,), 'text'),
    # force a particular plugin to be used
    'ansi': ((VideoANSI,), None),
    'curses': ((VideoCurses,), None),
    'pygame': ((VideoPygame,), None),
    'sdl2': ((VideoSDL2,), None),
    })

audio_plugins.update({
    'none': (AudioNone,),
    'cli': (AudioBeep, AudioNone),
    'text': (AudioBeep, AudioNone),
    'graphical': (AudioPygame, AudioBeep, AudioNone),
    'ansi': (AudioNone,),
    'curses': (AudioNone,),
    'pygame': (AudioPygame, AudioNone),
    'sdl2': (AudioSDL2, AudioNone),
    })
