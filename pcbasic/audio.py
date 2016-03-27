"""
PC-BASIC - audio.py
Base classes for audio handlers

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import time

import backend

plugin_dict = {}
plugin = None


def prepare():
    """ Initialise audio module. """

def init(plugin_name):
    """ Start audio plugin. """
    global plugin
    # initialise audio plugin
    try:
        plugin = plugin_dict[plugin_name]()
    except (KeyError, InitFailed):
        return False
    else:
        return True

def close():
    """ Close audio plugin. """
    if plugin:
        plugin.close()

class InitFailed(Exception):
    """ Audio plugin initialisation failed. """


class AudioPlugin(object):
    """ Base class for display/input interface plugins. """

    def __init__(self):
        """ Setup the audio interface and start the event handling thread. """
        # sound generators for sounds not played yet
        # if not None, something is playing
        self.next_tone = [ None, None, None, None ]

    def close(self):
        """ Close the audio interface. """
        # drain signal queue (to allow for persistence) and request exit
        if backend.message_queue:
            backend.message_queue.join()

    def _init_sound(self):
        """ Perform any necessary initialisations. """

    def _play_sound(self):
        """ Play the sounds queued."""

    def _drain_message_queue(self):
        """ Process sound system messages. """
        return False

    def _drain_tone_queue(self):
        """ Process tone events. """
        return True


prepare()
