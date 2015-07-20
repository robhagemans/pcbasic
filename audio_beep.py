"""
PC-BASIC - sound_beep.py
Sound implementation through the linux beep utility

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import datetime
import time
import threading
import Queue
from collections import deque

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

def busy():
    """ Is the mixer busy? """
    is_busy = False
    for voice in range(4):
        is_busy = is_busy or ((not now_loop[voice]) and
                    now_playing[voice] and now_playing[voice].poll() == None)
    return is_busy

def queue_length(voice):
    """ Number of unfinished sounds per voice. """
    # wait for signal queue to drain (should be fast)
    # don't drain fully to avoid skipping of music
    while sound.thread_queue[voice].qsize() > 1:
        pass
    # FIXME - accessing deque from other threads leads to errors, use an int fiekd
    return len(sound_queue[voice])


##############################################################################
# implementation

import plat

tick_s = 0.024
sound_queue = [ deque(), deque(), deque(), deque() ]
now_playing = [None, None, None, None]
now_loop = [None, None, None, None]

def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.daemon = True
    thread.start()

def consumer_thread():
    """ Audio signal queue consumer thread. """
    while True:
        empty = not drain_queue()
        # handle playing queues
        check_sound()
        for voice in range(4):
            empty = empty and not sound_queue[voice]
        # do not hog cpu
        if empty:
            time.sleep(tick_s)

def drain_queue():
    """ Drain signal queue. """
    global sound_queue, now_playing, now_loop
    empty = False
    while not empty:
        empty = True
        for i, q in enumerate(sound.thread_queue):
            try:
                signal = q.get(False)
                empty = False
            except Queue.Empty:
                continue
            if signal.event_type == sound.AUDIO_TONE:
                # enqueue a tone
                frequency, duration, fill, loop, voice, volume = signal.params
                sound_queue[voice].append((frequency, duration, fill, loop, volume))
            elif signal.event_type == sound.AUDIO_STOP:
                # stop all channels
                for voice in now_playing:
                    if voice and voice.poll() == None:
                        voice.terminate()
                sound_queue = [deque(), deque(), deque(), deque()]
                now_playing = [None, None, None, None]
                now_loop = [None, None, None, None]
                hush()
            elif signal.event_type == sound.AUDIO_NOISE:
                # enqueue a noise (play as regular note)
                is_white, frequency, duration, fill, loop, volume = signal.params
                sound_queue[voice].append((frequency, duration, fill, loop, volume))
            elif signal.event_type == sound.AUDIO_QUIT:
                # close thread
                return False
            elif signal.event_type == sound.AUDIO_PERSIST:
                # allow/disallow mixer to quit
                pass
            q.task_done()
    return not empty


if plat.system == 'Windows':
    def init_sound():
        """ This module is not supported under Windows. """
        return False

    def beep():
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

    def hush():
        """ Turn off any sound. """
        subprocess.call('beep -f 1 -l 0'.split())


def check_sound():
    """ Update the sound queue and play sounds. """
    global now_loop
    for voice in range(4):
        if now_loop[voice]:
            if (sound_queue[voice] and now_playing[voice]
                    and now_playing[voice].poll() == None):
                now_playing[voice].terminate()
                now_loop[voice] = None
                hush()
            elif not now_playing[voice] or now_playing[voice].poll() != None:
                play_now(*now_loop[voice], voice=voice)
        if (sound_queue[voice] and
                (not now_playing[voice] or now_playing[voice].poll() != None)):
            play_now(*sound_queue[voice].popleft(), voice=voice)

def play_now(frequency, duration, fill, loop, volume, voice):
    """ Play a sound immediately. """
    frequency = max(1, min(19999, frequency))
    if loop:
        duration = 5
        fill = 1
        now_loop[voice] = (frequency, duration, fill, loop, volume)
    if voice == 3:
        # ignore noise channel
        pass
    else:
        now_playing[voice] = beep(frequency, duration, fill)
