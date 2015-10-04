"""
PC-BASIC - audio_none.py
Null sound implementation

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import datetime
import Queue
import subprocess

import plat
import backend

import audio

def prepare():
    """ Initialise audio_eep module. """
    audio.plugin_dict['none'] = AudioNone


class AudioNone(audio.AudioPlugin):
    """ Null audio plugin. """

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
                self.next_tone = [None, None, None, None]
            elif signal.event_type == backend.AUDIO_QUIT:
                # close thread after task_done
                alive = False
            # drop other messages
            backend.message_queue.task_done()

    def _drain_tone_queue(self):
        """ Drain signal queue. """
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
                    duration = 0
                    if signal.event_type == backend.AUDIO_TONE:
                        # enqueue a tone
                        frequency, duration, fill, loop, volume = signal.params
                    elif signal.event_type == backend.AUDIO_NOISE:
                        # enqueue a noise
                        is_white, frequency, duration, fill, loop, volume = signal.params
                    latest = self.next_tone[voice] or datetime.datetime.now()
                    self.next_tone[voice] = latest + datetime.timedelta(seconds=duration)
        return empty

    def _play_sound(self):
        """ Play sounds. """
        # handle playing queues
        now = datetime.datetime.now()
        for voice in range(4):
            if self.next_tone[voice] is not None and now >= self.next_tone[voice]:
                self.next_tone[voice] = None
                backend.tone_queue[voice].task_done()


prepare()
