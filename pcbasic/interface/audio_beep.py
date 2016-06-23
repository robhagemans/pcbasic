"""
PC-BASIC - audio_beep.py
Sound implementation through the linux beep utility

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import Queue
import subprocess
import platform
from collections import deque
from datetime import datetime, timedelta

from ..basic import signals
from . import base


class AudioExternal(base.AudioPlugin):
    """Audio plugin based on external command-line utility."""

    def __init__(self, tone_queue, message_queue):
        """Initialise sound system."""
        if not self.beeper.ok():
            raise base.InitFailed()
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        base.AudioPlugin.__init__(self, tone_queue, message_queue)

    def tone(self, voice, frequency, duration, fill, loop, volume):
        """Enqueue a tone."""
        if voice == 0:
            self.generators[voice].append(self.beeper(
                    frequency, duration, fill, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self.next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()
        self.beeper.hush()

    def work(self):
        """Replenish sample buffer."""
        for voice in range(4):
            if self.next_tone[voice] is None or self.next_tone[voice].loop:
                try:
                    self.next_tone[voice] = self.generators[voice].popleft()
                except IndexError:
                    if self.next_tone[voice] is None:
                        continue
            self.next_tone[voice] = self.next_tone[voice].emit()


class Beeper(object):
    """Manage external beeper."""

    def __init__(self, frequency, duration, fill, loop, dummy_volume):
        """Initialise beeper."""
        self._frequency = frequency
        self._duration = duration
        self._fill = fill
        self._proc = None
        self.loop = loop

    @staticmethod
    def ok():
        # Windows not supported as there's no beep utility anyway
        # and we can't run the test below on CMD
        return (platform.system() != 'Windows' and
            subprocess.call('command -v beep >/dev/null 2>&1', shell=True) != 0)

    @staticmethod
    def hush():
        subprocess.call('beep -f 1 -l 0'.split())

    def emit(self):
        """Emit a sound."""
        if not self._proc or (self.loop and self._proc.poll() is not None):
            if self._frequency == 0 or self._frequency == 32767:
                self._proc = subprocess.Popen(
                    'sleep {0}'.format(self._duration).split())
            else:
                self._proc = subprocess.Popen(
                    'beep -f {freq} -l {dur} -D {gap}'.format(
                        freq=self._frequency, dur=self._duration*self._fill*1000,
                        gap=self._duration*(1-self._fill)*1000
                    ).split())
        # return self if still busy, None otherwise
        if self._proc and self._proc.poll() is None:
            return self
        else:
            return None


class AudioBeep(AudioExternal):
    """Audio plugin based on the beep utility."""
    beeper = Beeper
