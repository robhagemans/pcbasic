"""
PC-BASIC - interface package
Video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time
import logging

from .base import InitFailed

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

# create the window icon
from ..basic import typeface
icon_hex = '00003CE066606666666C6678666C3CE67F007F007F007F007F007F007F000000'
icon = typeface.Font(16, {'icon': icon_hex.decode('hex')}
                            ).build_glyph('icon', 16, 16, False, False)


###############################################################################
# interface event loop

delay = 0.024

def run(input_queue, video_queue, tone_queue, message_queue, interface_name, video_params, audio_params):
    """Start the main interface event loop."""
    with _get_video_plugin(input_queue, video_queue, interface_name, **video_params) as video_plugin:
        with _get_audio_plugin(tone_queue, message_queue, interface_name, **audio_params) as audio_plugin:
            while audio_plugin.alive or video_plugin.alive:
                # ensure both queues are drained
                video_plugin.cycle()
                audio_plugin.cycle()
                # do not hog cpu
                if not audio_plugin.playing and not video_plugin.screen_changed:
                    time.sleep(delay)


###############################################################################
# video plugin

video_plugins = {
    # interface_name: video_plugin_name, fallback, warn_on_fallback
    'none': ((VideoNone,), None),
    'cli': ((VideoCLI,), 'none'),
    'text': ((VideoCurses, VideoANSI), 'cli'),
    'graphical':  ((VideoPygame,), 'text'),
    # force a particular plugin to be used
    'ansi': ((VideoANSI,), None),
    'curses': ((VideoCurses,), None),
    'pygame': ((VideoPygame,), None),
    'sdl2': ((VideoSDL2,), None),
    }

def _get_video_plugin(input_queue, video_queue, interface_name, **kwargs):
    """Find and initialise video plugin for given interface."""
    while True:
        # select interface
        plugins, fallback = video_plugins[interface_name]
        for plugin_class in plugins:
            try:
                plugin = plugin_class(input_queue, video_queue, icon=icon, **kwargs)
            except InitFailed:
                logging.debug('Could not initialise video plugin "%s".', plugin_class.__name__)
            else:
                return plugin
        if fallback:
            logging.info('Could not initialise %s interface. Falling back to %s interface.', interface_name, fallback)
            interface_name = fallback
        else:
            raise InitFailed()


###############################################################################
# audio plugin

audio_plugins = {
    # interface_name: plugin_name, fallback, warn_on_fallback
    'none': (AudioNone,),
    'cli': (AudioBeep, AudioNone),
    'text': (AudioBeep, AudioNone),
    'graphical': (AudioPygame, AudioBeep, AudioNone),
    'ansi': (AudioNone,),
    'curses': (AudioNone,),
    'graphical': (AudioPygame, AudioNone),
    'sdl2': (AudioSDL2, AudioNone),
    }

def _get_audio_plugin(tone_queue, message_queue, interface_name, nosound):
    """Find and initialise audio plugin for given interface."""
    if nosound:
        interface_name = 'none'
    for plugin_class in audio_plugins[interface_name]:
        try:
            plugin = plugin_class(tone_queue, message_queue)
        except InitFailed:
            logging.debug('Could not initialise audio plugin "%s".', plugin_class.__name__)
        else:
            return plugin
    raise InitFailed()
