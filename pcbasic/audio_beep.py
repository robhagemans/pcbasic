"""
PC-BASIC - audio_beep.py
Sound implementation through the linux beep utility

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import time
import Queue
import subprocess

import plat
import backend

import audio

def prepare():
    """ Initialise audio_eep module. """
    audio.plugin_dict['beep'] = AudioBeep


class AudioBeep(audio.AudioPlugin):
    """ Audio plugin based on 'beep' command-line utility. """

    def __init__(self):
        """ Initialise sound system. """
        # Windows not supported as there's no beep utility anyway
        # and we can't run the test below on CMD
        if (plat.system == 'Windows' or
                subprocess.call("command -v beep >/dev/null 2>&1", shell=True) != 0):
            raise audio.InitFailed()
        self.now_playing = [None, None, None, None]
        self.now_looping = [None, None, None, None]
        audio.AudioPlugin.__init__(self)

    def _drain_message_queue(self):
        """ Drain signal queue. """
        alive = True
        while alive:
            try:
                signal = backend.message_queue.get(False)
            except Queue.Empty:
                return True
            if signal.event_type == backend.AUDIO_STOP:
                # stop all channels
                for voice in self.now_playing:
                    if voice and voice.poll() is None:
                        voice.terminate()
                self.next_tone = [None, None, None, None]
                self.now_playing = [None, None, None, None]
                self.now_looping = [None, None, None, None]
                hush()
            elif signal.event_type == backend.AUDIO_QUIT:
                # close thread after task_done
                alive = False
            # drop other messages
            backend.message_queue.task_done()

    def _drain_tone_queue(self):
        """ Drain tone queue. """
        empty = False
        while not empty:
            empty = True
            for voice, q in enumerate(backend.tone_queue):
                if self.next_tone[voice] is None:
                    try:
                        signal = q.get(False)
                        empty = False
                    except Queue.Empty:
                        continue
                    if signal.event_type == backend.AUDIO_TONE:
                        # enqueue a tone
                        self.next_tone[voice] = signal.params
                    elif signal.event_type == backend.AUDIO_NOISE:
                        # enqueue a noise (play as regular note)
                        self.next_tone[voice] = signal.params[1:]
        return empty

    def _play_sound(self):
        """ Play sounds. """
        for voice in range(4):
            if self.now_looping[voice]:
                if self.next_tone[voice] and self._busy(voice):
                    self.now_playing[voice].terminate()
                    self.now_looping[voice] = None
                    hush()
                elif not self._busy(voice):
                    self._play_now(*self.now_looping[voice], voice=voice)
            if self.next_tone[voice] and not self._busy(voice):
                self._play_now(*self.next_tone[voice], voice=voice)
                self.next_tone[voice] = None

    def _busy(self, voice):
        """ Is the beeper busy? """
        return self.now_playing[voice] and self.now_playing[voice].poll() is None

    def _play_now(self, frequency, duration, fill, loop, volume, voice):
        """ Play a sound immediately. """
        frequency = max(1, min(19999, frequency))
        if loop:
            duration, fill = 5, 1
            self.now_looping[voice] = (frequency, duration, fill, loop, volume)
        if voice == 0:
            self.now_playing[voice] = beep(frequency, duration, fill)
        else:
            # don't play other channels as there is no mixer or noise generator
            # but use a sleep process to get timings right
            self.now_playing[voice] = sleep(duration)


def hush():
    """ Turn off any sound. """
    subprocess.call('beep -f 1 -l 0'.split())

def beep(frequency, duration, fill):
    """ Emit a sound. """
    return subprocess.Popen(
            'beep -f {freq} -l {dur} -D {gap}'.format(
                freq=frequency, dur=duration*fill*1000,
                gap=duration*(1-fill)*1000
            ).split())

def sleep(duration):
    """ Wait for given number of seconds. """
    return subprocess.Popen('sleep {0}'.format(duration).split())


prepare()
