"""
PC-BASIC - interface.audio
Base class for audio plugins

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..compat import queue
from ..basic.base import signals


class AudioPlugin(object):
    """Base class for audio interface plugins."""

    def __init__(self, audio_queue, **kwargs):
        """Setup the audio interface and start the event handling thread."""
        # sound generators for sounds not played yet
        # if not None, something is playing
        self._next_tone = [None, None, None, None]
        self.alive = True
        self._audio_queue = audio_queue

    # called by Interface

    @property
    def busy(self):
        """Something is playing."""
        return self._next_tone != [None, None, None, None]

    def cycle(self):
        """Audio event cycle."""
        if self.alive:
            self._drain_queue()
        if self.alive:
            self._work()

    # private methods

    def _drain_queue(self):
        """Drain audio queue."""
        while True:
            try:
                signal = self._audio_queue.get(False)
            except queue.Empty:
                return
            self._audio_queue.task_done()
            if signal.event_type == signals.QUIT:
                # close thread
                self.alive = False
            elif signal.event_type == signals.AUDIO_STOP:
                self.hush()
            elif signal.event_type == signals.AUDIO_PERSIST:
                self.persist(*signal.params)
            elif signal.event_type == signals.AUDIO_TONE:
                self.tone(*signal.params)
            elif signal.event_type == signals.AUDIO_NOISE:
                self.noise(*signal.params)

    # plugin overrides

    def __exit__(self, type, value, traceback):
        """Close the audio interface."""

    def __enter__(self):
        """Perform any necessary initialisations."""
        return self

    def _work(self):
        """Play some of the sounds queued."""

    # signal handlers

    def hush(self):
        """Be quiet."""

    def persist(self, do_persist):
        """Allow or disallow mixer to quit."""

    def tone(self, voice, frequency, duration, loop, volume):
        """Enqueue a tone."""

    def noise(self, source, frequency, duration, loop, volume):
        """Enqueue a noise."""
