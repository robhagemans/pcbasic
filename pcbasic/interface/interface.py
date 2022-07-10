"""
PC-BASIC - interface.interface
Interface class

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import threading
import logging
import traceback

from ..compat import queue

from ..basic.base import signals
from .base import InitFailed, video_plugins, audio_plugins, WAIT_MESSAGE
from .audio import AudioPlugin


# millisecond delay
DELAY = 12


class Interface(object):
    """User interface for PC-BASIC session."""

    def __init__(self, guard=None, try_interfaces=(), audio_override=None, wait=False, **kwargs):
        """Initialise interface."""
        self._input_queue = queue.Queue()
        self._video_queue = queue.Queue()
        self._audio_queue = queue.Queue()
        self._wait = wait
        self._guard = guard
        self._video, self._audio = None, None
        for video in try_interfaces:
            try:
                self._video = video_plugins[video](self._input_queue, self._video_queue, **kwargs)
            except KeyError:
                logging.error('Unknown video plugin `%s`', video)
            except InitFailed as e:
                logging.info('Could not initialise video plugin `%s`: %s', video, e)
            if self._video:
                break
        else:
            # video plugin is necessary, fail without it
            raise InitFailed('Failed to initialise any video plugin.')
        audio = audio_override or video
        try:
            self._audio = audio_plugins[audio](self._audio_queue, **kwargs)
        except KeyError:
            # ignore if an interface has no audio, but not if an override doesn't exist
            if audio_override and audio_override != 'none':
                logging.error('Unknown audio plugin `%s`', audio)
        except InitFailed as e:
            logging.info('Could not initialise audio plugin `%s`: %s', audio, e)
        if not self._audio:
            # audio fallback to no-plugin
            self._audio = AudioPlugin(self._audio_queue, **kwargs)

    def get_queues(self):
        """Retrieve interface queues."""
        return self._input_queue, self._video_queue, self._audio_queue

    def launch(self, target, **kwargs):
        """Start an interactive interpreter session."""
        thread = threading.Thread(target=self._thread_runner, args=(target,), kwargs=kwargs)
        try:
            # launch the BASIC thread
            thread.start()
            # run the interface
            self.run()
        except Exception as e:
            logging.error('Fatal error in interface')
            logging.error(''.join(traceback.format_exception(*sys.exc_info())))
        finally:
            self.quit_input()
            thread.join()

    def _thread_runner(self, target, **kwargs):
        """Session runner."""
        try:
            target(interface=self, guard=self._guard, **kwargs)
        finally:
            if self._wait:
                self.pause(WAIT_MESSAGE)
            self.quit_output()

    def run(self):
        """Start the main interface event loop."""
        with self._audio:
            with self._video:
                while self._audio.alive or self._video.alive:
                    # ensure both queues are drained
                    self._video.cycle()
                    self._audio.cycle()
                    if not self._audio.busy and not self._video.busy:
                        # nothing to do, come back later
                        self._video.sleep(DELAY)

    def pause(self, message):
        """Pause and wait for a key."""
        self._video_queue.put(signals.Event(signals.VIDEO_SET_CAPTION, (message,)))
        self._video_queue.put(signals.Event(signals.VIDEO_SHOW_CURSOR, (False, False)))
        while True:
            signal = self._input_queue.get()
            if signal.event_type in (signals.KEYB_DOWN, signals.QUIT):
                break

    def quit_input(self):
        """Send signal through the input queue to quit BASIC."""
        self._input_queue.put(signals.Event(signals.QUIT))
        # drain video queue (joined in other thread)
        while not self._video_queue.empty():
            try:
                signal = self._video_queue.get(False)
            except queue.Empty:
                continue
            self._video_queue.task_done()
        # drain audio queue
        while not self._audio_queue.empty():
            try:
                signal = self._audio_queue.get(False)
            except queue.Empty:
                continue
            self._audio_queue.task_done()

    def quit_output(self):
        """Send signal through the output queues to quit plugins."""
        self._video_queue.put(signals.Event(signals.QUIT))
        self._audio_queue.put(signals.Event(signals.QUIT))
