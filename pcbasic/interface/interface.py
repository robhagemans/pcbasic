"""
PC-BASIC - interface.interface
Interface class

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import asyncio
import logging

from ..compat import queue

from ..basic.base import signals
from .base import InitFailed, video_plugins, audio_plugins, WAIT_MESSAGE
from .audio import AudioPlugin


# millisecond delay
DELAY = 12


class Interface(object):
    """User interface for PC-BASIC session."""

    def __init__(self, try_interfaces=(), audio_override=None, wait=False, **kwargs):
        """Initialise interface."""
        self._input_queue = asyncio.Queue()
        self._video_queue = asyncio.Queue()
        self._audio_queue = asyncio.Queue()
        self._wait = wait
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
            if audio_override and audio_override not in ('none', 'false'):
                logging.error('Unknown audio plugin `%s`', audio)
        except InitFailed as e:
            logging.info('Could not initialise audio plugin `%s`: %s', audio, e)
        if not self._audio:
            # audio fallback to no-plugin
            self._audio = AudioPlugin(self._audio_queue, **kwargs)

    def get_queues(self):
        """Retrieve interface queues."""
        return self._input_queue, self._video_queue, self._audio_queue

    async def launch(self, target, *args, **kwargs):
        """Start an interactive interpreter session."""
        await asyncio.gather(
            self._thread_runner(target, *args, **kwargs),
            self.run()
        )

    async def _thread_runner(self, target, *args, **kwargs):
        """Session runner."""
        try:
            await target(*args, **kwargs)
        finally:
            if self._wait:
                await self.pause(WAIT_MESSAGE)
            self.quit_output()

    async def run(self):
        """Start the main interface event loop."""
        with self._audio:
            with self._video:
                while self._audio.alive or self._video.alive:
                    # ensure both queues are drained
                    await self._video.cycle()
                    self._audio.cycle()
                    if not self._audio.busy and not self._video.busy:
                        # nothing to do, come back later
                        await self._video.sleep(DELAY / 1000)

                    await asyncio.sleep(0.01)

    async def pause(self, message):
        """Pause and wait for a key."""
        self._video_queue.put_nowait(signals.Event(signals.VIDEO_SET_CAPTION, (message,)))
        self._video_queue.put_nowait(signals.Event(signals.VIDEO_SHOW_CURSOR, (False, False)))
        while True:
            signal = await self._input_queue.get()
            if signal.event_type in (signals.KEYB_DOWN, signals.QUIT):
                self._video_queue.put_nowait(signals.Event(signals.VIDEO_SET_CAPTION, (u'',)))
                return signal

    def quit_input(self):
        """Send signal through the input queue to quit BASIC."""
        self._input_queue.put_nowait(signals.Event(signals.QUIT))
        # drain video queue (joined in other thread)
        while not self._video_queue.empty():
            try:
                signal = self._video_queue.get_nowait()
            except (queue.Empty, asyncio.QueueEmpty):
                continue
            self._video_queue.task_done()
        # drain audio queue
        while not self._audio_queue.empty():
            try:
                signal = self._audio_queue.get_nowait()
            except (queue.Empty, asyncio.QueueEmpty):
                continue
            self._audio_queue.task_done()

    def quit_output(self):
        """Send signal through the output queues to quit plugins."""
        self._video_queue.put_nowait(signals.Event(signals.QUIT))
        self._audio_queue.put_nowait(signals.Event(signals.QUIT))
