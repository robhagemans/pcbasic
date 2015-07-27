"""
PC-BASIC - audio_beep.py
Sound implementation through the linux beep utility

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import datetime
import time
import threading
import Queue

import sound


##############################################################################
# interface

def init():
    """ Initialise sound system. """
    if init_sound():
        launch_thread()
        return True
    return False

def close():
    """ Clean up and exit sound system. """
    pass

# sound generators for sounds not played yet
# if not None, something is playing
next_tone = [ None, None, None, None ]

##############################################################################
# implementation

import plat

tick_s = 0.024
now_playing = [None, None, None, None]
now_looping = [None, None, None, None]

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.daemon = True
    thread.start()

def consumer_thread():
    """ Audio signal queue consumer thread. """
    while True:
        drain_message_queue()
        empty = drain_tone_queue()
        # handle playing queues
        play_sound()
        # do not hog cpu
        if empty and next_tone == [None, None, None, None]:
            time.sleep(tick_s)

def drain_message_queue():
    """ Drain signal queue. """
    global now_playing, now_looping
    while True:
        try:
            signal = sound.message_queue.get(False)
        except Queue.Empty:
            break
        if signal.event_type == sound.AUDIO_STOP:
            # stop all channels
            for voice in now_playing:
                if voice and voice.poll() is None:
                    voice.terminate()
            next_tone = [None, None, None, None]
            now_playing = [None, None, None, None]
            now_looping = [None, None, None, None]
            hush()
        elif signal.event_type == sound.AUDIO_QUIT:
            # close thread
            return False
        elif signal.event_type == sound.AUDIO_PERSIST:
            # allow/disallow mixer to quit
            pass
        sound.message_queue.task_done()

def drain_tone_queue():
    """ Drain tone queue. """
    global next_tone
    empty = False
    while not empty:
        empty = True
        for voice, q in enumerate(sound.tone_queue):
            if next_tone[voice] is None:
                try:
                    signal = q.get(False)
                    empty = False
                except Queue.Empty:
                    continue
                if signal.event_type == sound.AUDIO_TONE:
                    # enqueue a tone
                    next_tone[voice] = signal.params
                elif signal.event_type == sound.AUDIO_NOISE:
                    # enqueue a noise (play as regular note)
                    next_tone[voice] = signal.params[1:]
    return empty

def play_sound():
    """ Play sounds. """
    for voice in range(4):
        if now_looping[voice]:
            if next_tone[voice] and busy(voice):
                now_playing[voice].terminate()
                now_looping[voice] = None
                hush()
            elif not busy(voice):
                play_now(*now_looping[voice], voice=voice)
        if next_tone[voice] and not busy(voice):
            play_now(*next_tone[voice], voice=voice)
            next_tone[voice] = None

def busy(voice):
    """ Is the mixer busy? """
    return now_playing[voice] and now_playing[voice].poll() is None


if plat.system == 'Windows':
    def init_sound():
        """ This module is not supported under Windows. """
        return False

    def beep():
        """ This module is not supported under Windows. """
        pass

    def sleep():
        """ This module is not supported under Windows. """
        pass

    def hush():
        """ This module is not supported under Windows. """
        pass

else:
    import subprocess

    def init_sound():
        """ Initialise sound module. """
        return subprocess.call("command -v beep >/dev/null 2>&1",
                                shell=True) == 0

    def beep(frequency, duration, fill):
        """ Emit a sound. """
        return subprocess.Popen(('beep -f %f -l %d -D %d' %
            (frequency, duration*fill*1000, duration*(1-fill)*1000)).split())

    def sleep(duration):
        """ Wait for given number of seconds. """
        return subprocess.Popen(('sleep %f') % duration)

    def hush():
        """ Turn off any sound. """
        subprocess.call('beep -f 1 -l 0'.split())


def play_now(frequency, duration, fill, loop, volume, voice):
    """ Play a sound immediately. """
    frequency = max(1, min(19999, frequency))
    if loop:
        duration, fill = 5, 1
        now_looping[voice] = (frequency, duration, fill, loop, volume)
    if voice == 1:
        now_playing[voice] = beep(frequency, duration, fill)
    else:
        # don't play other channels as there is no mixer or noise generator
        now_playing[voice] = sleep(duration)
