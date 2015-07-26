"""
PC-BASIC - audio_none.py
Null sound implementation

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
    launch_thread()
    return True

def close():
    """ Clean up and exit sound system. """
    pass

def busy():
    """ Is the mixer busy? """
    return False

def queue_length(voice):
    """ Number of unfinished sounds per voice. """
    # wait for signal queue to drain (should be fast)
    # don't drain fully to avoid skipping of music
    while sound.thread_queue[voice].qsize() > 1:
        pass
    return sound_queue_lengths[voice]


##############################################################################
# implementation

tick_s = 0.024
sound_queue = [ deque(), deque(), deque(), deque() ]
# keep an int for the lengths to avoid counting the deque from another thread
sound_queue_lengths = [0, 0, 0, 0]

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
        now = datetime.datetime.now()
        for voice in range(4):
            while sound_queue[voice] and now >= sound_queue[voice][0]:
                sound_queue[voice].popleft()
                sound_queue_lengths[voice] -= 1
            empty = empty and not sound_queue[voice]
        # do not hog cpu
        if empty:
            time.sleep(tick_s)

def drain_queue():
    """ Drain signal queue. """
    global sound_queue, sound_queue_lengths
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
                if sound_queue[voice]:
                    latest = max(sound_queue[voice])
                else:
                    latest = datetime.datetime.now()
                sound_queue[voice].append(latest + datetime.timedelta(seconds=duration))
                sound_queue_lengths[voice] += 1
            elif signal.event_type == sound.AUDIO_STOP:
                # stop all channels
                sound_queue = [deque(), deque(), deque(), deque()]
                sound_queue_lengths = [0, 0, 0, 0]
            elif signal.event_type == sound.AUDIO_NOISE:
                # enqueue a noise
                is_white, frequency, duration, fill, loop, volume = signal.params
                if sound_queue[voice]:
                    latest = max(sound_queue[voice])
                else:
                    latest = datetime.datetime.now()
                sound_queue[voice].append(latest + datetime.timedelta(seconds=duration))
                sound_queue_lengths[voice] += 1
            elif signal.event_type == sound.AUDIO_QUIT:
                # close thread
                return False
            elif signal.event_type == sound.AUDIO_PERSIST:
                # allow/disallow mixer to quit
                pass
            q.task_done()
    return not empty
