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
import subprocess

import plat
import sound


##############################################################################
# interface

def init():
    """ Initialise sound system. """
    if plat.system == 'Windows':
        # Windows not supported as there's no beep utility anyway
        # and we can't run the test below on CMD
        return False
    elif subprocess.call("command -v beep >/dev/null 2>&1", shell=True) == 0:
        launch_thread()
        return True
    return False

def close():
    """ Clean up and exit sound system. """
    # drain signal queue (to allow for persistence) and request exit
    if sound.message_queue:
        sound.message_queue.put(sound.AudioEvent(sound.AUDIO_QUIT))
        sound.message_queue.join()
    # don't wait for tone que, it will not drain but be pickled later.
    if thread and thread.is_alive():
        # signal quit and wait for thread to finish
        thread.join()


# sound generators for sounds not played yet
# if not None, something is playing
next_tone = [ None, None, None, None ]

##############################################################################
# implementation

tick_s = 0.024
now_playing = [None, None, None, None]
now_looping = [None, None, None, None]

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.start()

def consumer_thread():
    """ Audio signal queue consumer thread. """
    while drain_message_queue():
        empty = drain_tone_queue()
        # handle playing queues
        play_sound()
        # do not hog cpu
        if empty and next_tone == [None, None, None, None]:
            time.sleep(tick_s)

def drain_message_queue():
    """ Drain signal queue. """
    global next_tone, now_playing, now_looping
    while True:
        try:
            signal = sound.message_queue.get(False)
        except Queue.Empty:
            return True
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
    """ Is the beeper busy? """
    return now_playing[voice] and now_playing[voice].poll() is None

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

def hush():
    """ Turn off any sound. """
    subprocess.call('beep -f 1 -l 0'.split())

def play_now(frequency, duration, fill, loop, volume, voice):
    """ Play a sound immediately. """
    frequency = max(1, min(19999, frequency))
    if loop:
        duration, fill = 5, 1
        now_looping[voice] = (frequency, duration, fill, loop, volume)
    if voice == 0:
        now_playing[voice] = beep(frequency, duration, fill)
    else:
        # don't play other channels as there is no mixer or noise generator
        # but use a sleep process to get timings right
        now_playing[voice] = sleep(duration)
