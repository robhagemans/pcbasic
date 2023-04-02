"""
PC-BASIC - audio_beep.py
Sound implementation through the linux beep utility

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import threading
import subprocess
from collections import deque
import time
import sys

from ..compat import WIN32, which

if WIN32:
    import winsound  # pylint: disable=import-error
    fcntl = None
else:
    import fcntl  # pylint: disable=import-error
    winsound = None

from .audio import AudioPlugin
from .base import audio_plugins, InitFailed


@audio_plugins.register('beep')
class AudioBeep(AudioPlugin):
    """Audio plugin based on the PC speaker."""

    def __init__(self, audio_queue, **kwargs):
        """Initialise sound system."""
        if WIN32:
            self.beeper = WinBeeper
        else:
            if LinuxBeeper.ok():
                self.beeper = LinuxBeeper
            else:
                self.beeper = Beeper
        if not self.beeper.ok():
            raise InitFailed('Beeper not supported')
        # sound generators for each voice
        self.generators = [deque(), deque(), deque(), deque()]
        AudioPlugin.__init__(self, audio_queue)

    def tone(self, voice, frequency, duration, loop, volume):
        """Enqueue a tone."""
        if voice == 0:
            self.generators[voice].append(self.beeper(
                    frequency, duration, loop, volume))

    def hush(self):
        """Stop sound."""
        for voice in range(4):
            self._next_tone[voice] = None
            while self.generators[voice]:
                self.generators[voice].popleft()
        self.beeper.hush()

    def _work(self):
        """Replenish sample buffer."""
        for voice in range(4):
            if self._next_tone[voice] is None or self._next_tone[voice].loop:
                try:
                    self._next_tone[voice] = self.generators[voice].popleft()
                except IndexError:
                    if self._next_tone[voice] is None:
                        continue
            self._next_tone[voice] = self._next_tone[voice].emit()


class Beeper(object):
    """Manage external beeper."""

    def __init__(self, frequency, duration, loop, dummy_volume):
        """Initialise beeper."""
        self._frequency = frequency
        self._duration = duration
        self._proc = None
        self.loop = loop

    @staticmethod
    def ok():
        """This beeper is supported."""
        return which('beep')

    @staticmethod
    def hush():
        """Stop sound."""
        subprocess.call('beep -f 1 -l 0'.split())

    def emit(self):
        """Emit a sound."""
        if not self._proc or (self.loop and self._proc.poll() is not None):
            if self._frequency == 0 or self._frequency == 32767:
                self._proc = subprocess.Popen(
                    'sleep {0}'.format(self._duration).split())
            else:
                self._proc = subprocess.Popen(
                    'beep -f {freq} -l {dur}'.format(
                        freq=self._frequency, dur=self._duration*1000,
                    ).split())
        # return self if still busy, None otherwise
        if self._proc and self._proc.poll() is None:
            return self
        else:
            return None


class WinBeeper(Beeper):
    """Manage speaker beeps through winsound."""

    @staticmethod
    def ok():
        """This beeper is supported when winsound is available."""
        return winsound is not None

    @staticmethod
    def hush():
        """Stop sound."""

    def emit(self):
        """Emit a sound."""
        if not self._proc or (self.loop and not self._proc.is_alive()):
            self._proc = threading.Thread(
                target=self._beep, args=(self._frequency, self._duration, self.loop))
            self._proc.start()
        # return self if still busy, None otherwise
        if self._proc and self._proc.is_alive():
            return self
        else:
            return None

    @staticmethod
    def _beep(frequency, duration, loop):
        """Beeping thread target."""
        if frequency < 37 or frequency >= 32767:
            time.sleep(duration)
        else:
            winsound.Beep(int(frequency), int(duration*1000))


KIOCSOUND = 0x4B2F
CLOCK_TICK_RATE = 1193180

class LinuxBeeper(WinBeeper):
    """Manage speaker beeps through Linux ioctl."""

    @staticmethod
    def ok():
        """This beeper is supported if the ioctl call works."""
        try:
            fcntl.ioctl(sys.stdout, KIOCSOUND, 0)
        except EnvironmentError:
            return False
        return True

    @staticmethod
    def hush():
        """Stop sound."""
        fcntl.ioctl(sys.stdout, KIOCSOUND, 0)

    @staticmethod
    def _beep(frequency, duration, loop):
        """Beeping thread target."""
        if frequency < 37 or frequency >= 32767:
            fcntl.ioctl(sys.stdout, KIOCSOUND, 0)
        else:
            fcntl.ioctl(sys.stdout, KIOCSOUND, int(CLOCK_TICK_RATE // frequency))
        time.sleep(duration)
        if not loop:
            fcntl.ioctl(sys.stdout, KIOCSOUND, 0)
