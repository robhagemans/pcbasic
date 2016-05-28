"""
PC-BASIC - audio_none.py
Null sound implementation

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import datetime
import Queue

from ..basic import signals
from . import base as audio


class AudioNone(audio.AudioPlugin):
    """Null audio plugin."""

    def _drain_message_queue(self):
        """Drain signal queue."""
        alive = True
        while alive:
            try:
                signal = self.message_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == signals.AUDIO_STOP:
                # stop all channels
                for voice in range(4):
                    if self.next_tone[voice] is not None:
                        # ensure sender knows the tone has been dropped
                        self.tone_queue[voice].task_done()
                        self.next_tone[voice] = None
            elif signal.event_type == signals.AUDIO_QUIT:
                # close thread after task_done
                alive = False
            # drop other messages
            self.message_queue.task_done()

    def _drain_tone_queue(self):
        """Drain signal queue."""
        empty = False
        while not empty:
            empty = True
            for voice, q in enumerate(self.tone_queue):
                if self.next_tone[voice] is None:
                    try:
                        signal = q.get(False)
                        empty = False
                    except Queue.Empty:
                        continue
                    duration = 0
                    if signal.event_type == signals.AUDIO_TONE:
                        # enqueue a tone
                        frequency, duration, fill, loop, volume = signal.params
                    elif signal.event_type == signals.AUDIO_NOISE:
                        # enqueue a noise
                        is_white, frequency, duration, fill, loop, volume = signal.params
                    latest = self.next_tone[voice] or datetime.datetime.now()
                    self.next_tone[voice] = latest + datetime.timedelta(seconds=duration)
        return empty

    def _play_sound(self):
        """Play sounds."""
        # handle playing queues
        now = datetime.datetime.now()
        for voice in range(4):
            if self.next_tone[voice] is not None and now >= self.next_tone[voice]:
                self.next_tone[voice] = None
                self.tone_queue[voice].task_done()
