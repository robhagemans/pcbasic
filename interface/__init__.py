"""
PC-BASIC - interface package
Video, input and audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time
import logging

from base import InitFailed

# video plugins
from interface.video_none import VideoNone
from interface.video_ansi import VideoANSI
from interface.video_cli import VideoCLI
from interface.video_curses import VideoCurses
from interface.video_pygame import VideoPygame
from interface.video_sdl2 import VideoSDL2

# audio plugins
from interface.audio_none import AudioNone
from interface.audio_beep import AudioBeep
from interface.audio_pygame import AudioPygame
from interface.audio_sdl2 import AudioSDL2

# create the window icon
from pcbasic import typeface
icon_hex = '00003CE066606666666C6678666C3CE67F007F007F007F007F007F007F000000'
icon = typeface.Font(16, {'icon': icon_hex.decode('hex')}
                            ).build_glyph('icon', 16, 16, False, False)


###############################################################################
# interface event loop

delay = 0.024

def run(input_queue, video_queue, tone_queue, message_queue, interface_name, video_params, audio_params):
    """ Start the main interface event loop. """
    with _get_video_plugin(input_queue, video_queue, interface_name, **video_params) as video_plugin:
        with _get_audio_plugin(tone_queue, message_queue, interface_name, **audio_params) as audio_plugin:
            while True:
                # ensure both queues are drained
                video_plugin.cycle()
                audio_plugin.cycle()
                if not audio_plugin.alive and not video_plugin.alive:
                    break
                # do not hog cpu
                if not audio_plugin.playing and not video_plugin.screen_changed:
                    time.sleep(delay)



###############################################################################
# video plugin

# plugins will need to register themselves
video_plugin_dict = {
    'ansi': VideoANSI,
    'cli': VideoCLI,
    'curses': VideoCurses,
    'none': VideoNone,
    'pygame': VideoPygame,
    'sdl2': VideoSDL2,
}

video_plugins = {
    # interface_name: video_plugin_name, fallback, warn_on_fallback
    'none': (('none',), None),
    'cli': (('cli',), 'none'),
    'text': (('curses', 'ansi'), 'cli'),
    'graphical':  (('pygame',), 'text'),
    # force a particular plugin to be used
    'ansi': (('ansi',), None),
    'curses': (('curses',), None),
    'pygame': (('pygame',), None),
    'sdl2': (('sdl2',), None),
    }


def _get_video_plugin(input_queue, video_queue, interface_name, **kwargs):
    """ Find and initialise video plugin for given interface. """
    while True:
        # select interface
        names, fallback = video_plugins[interface_name]
        for video_name in names:
            try:
                plugin = video_plugin_dict[video_name](
                    input_queue, video_queue,
                    icon=icon, **kwargs)
            except KeyError:
                logging.debug('Video plugin "%s" not available.', video_name)
            except InitFailed:
                logging.debug('Could not initialise video plugin "%s".', video_name)
            else:
                return plugin
        if fallback:
            logging.info('Could not initialise %s interface. Falling back to %s interface.', interface_name, fallback)
            interface_name = fallback
        else:
            raise InitFailed()



###############################################################################
# audio plugin

audio_plugin_dict = {
    'beep': AudioBeep,
    'none': AudioNone,
    'pygame': AudioPygame,
    'sdl2': AudioSDL2,
}


audio_plugins = {
    # interface_name: plugin_name, fallback, warn_on_fallback
    'none': ('none',),
    'cli': ('beep', 'none'),
    'text': ('beep', 'none'),
    'graphical': ('pygame', 'beep', 'none'),
    'ansi': ('none',),
    'curses': ('none',),
    'pygame': ('pygame', 'none'),
    'sdl2': ('sdl2', 'none'),
    }


def _get_audio_plugin(tone_queue, message_queue, interface_name, nosound):
    """ Find and initialise audio plugin for given interface. """
    if nosound:
        interface_name = 'none'
    names = audio_plugins[interface_name]
    for audio_name in names:
        try:
            plugin = audio_plugin_dict[audio_name](tone_queue, message_queue)
        except KeyError:
            logging.debug('Audio plugin "%s" not available.', audio_name)
        except InitFailed:
            logging.debug('Could not initialise audio plugin "%s".', audio_name)
        else:
            return plugin
    logging.error('Audio plugin malfunction. Could not initialise interface.')
    raise InitFailed()
