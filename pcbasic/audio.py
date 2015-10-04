"""
PC-BASIC - audio.py
Base classes for audio handlers

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import logging
import threading
import Queue
import time

import backend

plugin_dict = {}
plugin = None


def prepare():
    """ Initialise audio module. """

def init(plugin_name):
    """ Start audio plugin. """
    global plugin
    # initialise video plugin
    try:
        plugin = plugin_dict[plugin_name]()
        return True
    except (KeyError, InitFailed):
        close()
        return False

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
        # start video thread
        self.thread = threading.Thread(target=self._consumer_thread)
        self.thread.start()

    def close(self):
        """ Close the audio interface. """
        # drain signal queue (to allow for persistence) and request exit
        if backend.message_queue:
            backend.message_queue.put(backend.Event(backend.AUDIO_QUIT))
            backend.message_queue.join()
        # don't wait for tone que, it will not drain but be pickled later.
        if self.thread and self.thread.is_alive():
            # signal quit and wait for thread to finish
            self.thread.join()


    # queue management

    def _consumer_thread(self):
        """ Video signal queue consumer thread. """
        self._init_sound()
        while self._drain_message_queue():
            empty = self._drain_tone_queue()
            self._play_sound()
            # do not hog cpu
            if empty and self.next_tone == [None, None, None, None]:
                self._sleep()

    def _sleep(self):
        """ Sleep a tick to avoid hogging the cpu. """
        time.sleep(0.024)

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
