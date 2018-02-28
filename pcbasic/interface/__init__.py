"""
PC-BASIC - interface package
Video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import Interface, video_plugins, audio_plugins, InitFailed, video_plugin, audio_plugin

# video plugins
from .base import VideoPlugin
from .video_ansi import VideoANSI
from .video_cli import VideoCLI
from .video_curses import VideoCurses
from .video_pygame import VideoPygame
from .video_sdl2 import VideoSDL2

# audio plugins
from .base import AudioPlugin
from .audio_beep import AudioBeep
from .audio_pygame import AudioPygame
from .audio_sdl2 import AudioSDL2
from .audio_portaudio import AudioPortAudio


video_plugins.update({
    # interface_name: ((video_plugin_name, ...), fallback)
    'cli': ((VideoCLI,), None),
    'text': ((VideoCurses, VideoANSI), 'cli'),
    'graphical':  ((VideoSDL2, VideoPygame,), 'text'),
    })


audio_plugins.update({
    'cli': (AudioBeep, AudioPlugin),
    'text': (AudioBeep, AudioPlugin),
    'graphical': (AudioSDL2, AudioPygame, AudioBeep, AudioPlugin),
    })
