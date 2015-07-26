"""
PC-BASIC - audio_pygame.py
Sound interface based on PyGame

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

from math import ceil

try:
    import pygame
except ImportError:
    pygame = None

try:
    import numpy
except ImportError:
    numpy = None

import plat
if plat.system == 'Android':
    android = True
    # don't do sound for now on Android
    mixer = None
    numpy = None
else:
    android = False
    if pygame:
        import pygame.mixer as mixer
    else:
        mixer = None

import logging
import threading
import Queue

import sound

def prepare():
    """ Initialise sound module. """
    if pygame:
        # must be called before pygame.init()
        if mixer:
            mixer.pre_init(sample_rate, -mixer_bits, channels=1, buffer=1024) #4096


##############################################################################
# interface

def init():
    """ Initialise sound system. """
    if not numpy:
        logging.warning('NumPy module not found. Failed to initialise audio.')
        return False
    if not mixer:
        return False
    launch_thread()
    return True

def close():
    """ Close sound queue at exit. """
    # drain signal queue (to allow for persistence) and request exit
    if sound.tone_queue:
        for i in range(4):
            sound.tone_queue[i].join()
        sound.message_queue.put(sound.AudioEvent(sound.AUDIO_QUIT))
        if thread and thread.is_alive():
            # signal quit and wait for thread to finish
            thread.join()

def queue_length(voice):
    """ Number of unfinished sounds per voice. """
    # this is just sound.tone_queue[voice].unfinished_tasks but not part of API
    return sound.tone_queue[voice].qsize() + (next_tone[voice] is not None)


##############################################################################
# implementation

thread = None

tick_ms = 24
# quit sound server after quiet period of quiet_quit ticks
# to avoid high-ish cpu load from the sound server.
quiet_quit = 10000
quiet_ticks = 0
# do not quit mixer if true
persist = False

# sound generators for sounds not played yet
next_tone = [ None, None, None, None ]

# currently looping sound
loop_sound = [ None, None, None, None ]

# mixer settings
mixer_bits = 16
sample_rate = 44100

# initial condition - see dosbox source
init_noise = 0x0f35
# white noise feedback
feedback_noise = 0x4400
# 'periodic' feedback mask (15-bit rotation)
feedback_periodic = 0x4000
# square wave feedback mask
feedback_tone = 0x2

# The SN76489 attenuates the volume by 2dB for each step in the volume register.
# see http://www.smspower.org/Development/SN76489
max_amplitude = (1<<(mixer_bits-1)) - 1
# 2 dB steps correspond to a voltage factor of 10**(-2./20.) as power ~ voltage**2
step_factor = 10**(-2./20.)
# geometric list of amplitudes for volume values
amplitude = [0]*16 if not numpy else numpy.int16(max_amplitude*(step_factor**numpy.arange(15,-1,-1)))
# zero volume means silent
amplitude[0] = 0

# one wavelength at 37 Hz is 1192 samples at 44100 Hz
chunk_length = 1192 * 4


class SignalSource(object):
    """ Linear Feedback Shift Register to generate noise or tone. """

    def __init__(self, feedback, init=0x01):
        """ Initialise the signal source. """
        self.lfsr = init
        self.feedback = feedback

    def next(self):
        """ Get a sample bit. """
        bit = self.lfsr & 1
        self.lfsr >>= 1
        if bit:
            self.lfsr ^= self.feedback
        return bit


class SoundGenerator(object):
    """ Sound sample chunk generator. """

    def __init__(self, signal_source, feedback, frequency, total_duration, fill, loop, volume):
        """ Initialise the generator. """
        # noise generator
        self.signal_source = signal_source
        self.feedback = feedback
        # actual duration and gap length
        self.duration = fill * total_duration
        self.gap = (1-fill) * total_duration
        self.amplitude = amplitude[volume]
        self.frequency = frequency
        self.loop = loop
        self.bit = 0
        self.count_samples = 0
        self.num_samples = int(self.duration * sample_rate)

    def build_chunk(self):
        """ Build a sound chunk. """
        self.signal_source.feedback = self.feedback
        if self.count_samples >= self.num_samples:
            # done already
            return None
        # work on last element of sound queue
        check_init_mixer()
        if self.frequency == 0 or self.frequency == 32767:
            chunk = numpy.zeros(chunk_length, numpy.int16)
        else:
            half_wavelength = sample_rate / (2.*self.frequency)
            num_half_waves = int(ceil(chunk_length / half_wavelength))
            # generate bits
            bits = [ -self.amplitude if self.signal_source.next() else self.amplitude for _ in xrange(num_half_waves) ]
            # do sampling by averaging the signal over bins of given resolution
            # this allows to use numpy all the way which is *much* faster than looping over an array
            # stretch array by half_wavelength * resolution
            resolution = 20
            matrix = numpy.repeat(numpy.array(bits, numpy.int16), int(half_wavelength*resolution))
            # cut off on round number of resolution blocks
            matrix = matrix[:len(matrix)-(len(matrix)%resolution)]
            # average over blocks
            matrix = matrix.reshape((len(matrix)/resolution, resolution))
            chunk = numpy.int16(numpy.average(matrix, axis=1))
        if not self.loop:
            # last chunk is shorter
            if self.count_samples + len(chunk) < self.num_samples:
                self.count_samples += len(chunk)
            else:
                # append final chunk
                rest_length = self.num_samples - self.count_samples
                chunk = chunk[:rest_length]
                # append quiet gap if requested
                if self.gap:
                    gap_chunk = numpy.zeros(int(self.gap * sample_rate), numpy.int16)
                    chunk = numpy.concatenate((chunk, gap_chunk))
                # done
                self.count_samples = self.num_samples
        # if loop, attach one chunk to loop, do not increment count
        return chunk
#        return pygame.sndarray.make_sound(chunk)


# three tone voices plus a noise source
signal_sources = [  SignalSource(feedback_tone),
                    SignalSource(feedback_tone),
                    SignalSource(feedback_tone),
                    SignalSource(feedback_noise, init_noise) ]


def launch_thread():
    """ Launch consumer thread. """
    global thread
    thread = threading.Thread(target=consumer_thread)
    thread.daemon = True
    thread.start()

def consumer_thread():
    """ Audio signal queue consumer thread. """
    # initialise mixer as silent
    # this is necessary to be able to set channels to mono
    mixer.quit()
    while True:
        drain_message_queue()
        empty = drain_tone_queue()
        # generate and play chunks
        play_sound()
        # check if mixer can be quit
        check_quit()
        # do not hog cpu
        if empty and not next_tone[0] and not next_tone[1] and not next_tone[2] and not next_tone[3]:
            pygame.time.wait(tick_ms)

def drain_message_queue():
    global next_tone, loop_sound, persist
    while True:
        try:
            signal = sound.message_queue.get(False)
        except Queue.Empty:
            break
        if signal.event_type == sound.AUDIO_STOP:
            # stop all channels
            for voice in range(4):
                stop_channel(voice)
            loop_sound = [None, None, None, None]
            next_tone = [None, None, None, None]
        elif signal.event_type == sound.AUDIO_QUIT:
            # close thread
            return False
        elif signal.event_type == sound.AUDIO_PERSIST:
            # allow/disallow mixer to quit
            persist = signal.params
        sound.message_queue.task_done()

def drain_tone_queue():
    """ Drain signal queue. """
    empty = False
    while not empty:
        empty = True
        for voice, q in enumerate(sound.tone_queue):
            # don't get the next tone if we're still working on one
            if next_tone[voice]:
                continue
            try:
                signal = q.get(False)
                empty = False
            except Queue.Empty:
                continue
            if signal.event_type == sound.AUDIO_TONE:
                # enqueue a tone
                frequency, total_duration, fill, loop, _, volume = signal.params
                next_tone[voice] = SoundGenerator(signal_sources[voice], feedback_tone, frequency, total_duration, fill, loop, volume)
            elif signal.event_type == sound.AUDIO_NOISE:
                # enqueue a noise
                is_white, frequency, total_duration, fill, loop, volume = signal.params
                feedback = feedback_noise if is_white else feedback_periodic
                next_tone[voice] = SoundGenerator(signal_sources[3], feedback, frequency, total_duration, fill, loop, volume)
    return empty

def play_sound():
    """ play sounds. """
    global loop_sound
    current_chunk = [ None, None, None, None ]
    if (next_tone == [ None, None, None, None ]
            and loop_sound == [ None, None, None, None ]):
        return
    check_init_mixer()
    for voice in range(4):
        # if there is a sound queue, stop looping sound
        if next_tone[voice] and loop_sound[voice]:
            stop_channel(voice)
            loop_sound[voice] = None
        if mixer.Channel(voice).get_queue() is None:
            if next_tone[voice]:
                if next_tone[voice].loop:
                    # it's a looping tone, handle there
                    loop_sound[voice] = next_tone[voice]
                    next_tone[voice] = None
                    sound.tone_queue[voice].task_done()
                else:
                    current_chunk[voice] = numpy.array([], dtype=numpy.int16)
                    while next_tone[voice] and len(current_chunk[voice]) < chunk_length:
                        chunk = next_tone[voice].build_chunk()
                        if chunk is None:
                            # tone has finished
                            next_tone[voice] = None
                            sound.tone_queue[voice].task_done()
                        else:
                            current_chunk[voice] = numpy.concatenate((current_chunk[voice], chunk))
            if loop_sound[voice]:
                # currently looping sound
                current_chunk[voice] = loop_sound[voice].build_chunk()
    for voice in range(4):
        if current_chunk[voice] is not None and len(current_chunk[voice]) != 0:
            sound = pygame.sndarray.make_sound(current_chunk[voice])
            mixer.Channel(voice).queue(sound)

def check_quit():
    """ Quit the mixer if not running a program and sound quiet for a while. """
    global quiet_ticks
    if next_tone != [None, None, None, None]:
        quiet_ticks = 0
    else:
        quiet_ticks += 1
        if not persist and quiet_ticks > quiet_quit:
            # mixer is quiet and we're not running a program.
            # quit to reduce pulseaudio cpu load
            # this takes quite a while and leads to missed frames...
            if mixer.get_init() != None:
                mixer.quit()
            quiet_ticks = 0

def stop_channel(channel):
    """ Stop sound on a channel. """
    if mixer.get_init():
        mixer.Channel(channel).stop()
        # play short silence to avoid blocking the channel - it won't play on queue()
        silence = pygame.sndarray.make_sound(numpy.zeros(1, numpy.int16))
        mixer.Channel(channel).play(silence)

def check_init_mixer():
    """ Initialise the mixer if necessary. """
    if mixer.get_init() == None:
        mixer.init()

prepare()
