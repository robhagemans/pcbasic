#
# PC-BASIC 3.23 - audio_pygame.py
#
# Sound interface based on PyGame
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

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
    import pygame.mixer as mixer

import backend
import logging

def prepare():
    if pygame:
        # must be called before pygame.init()
        pre_init_mixer()

def init_sound():
    if not numpy:
        logging.warning('NumPy module not found. Failed to initialise audio.')
        return False
    init_mixer()    
    return True
    
def stop_all_sound():
    global sound_queue, loop_sound
    for voice in range(4):
        stop_channel(voice)
    loop_sound = [ None, None, None, None ]
    sound_queue = [ [], [], [], [] ]
    
# process sound queue in event loop
def check_sound():
    global loop_sound
    current_chunk = [ None, None, None, None ]
    if sound_queue == [ [], [], [], [] ] and loop_sound == [ None, None, None, None ]:
        return
    check_init_mixer()
    for voice in range(4):
        # if there is a sound queue, stop looping sound
        if sound_queue[voice] and loop_sound[voice]:
            stop_channel(voice)
            loop_sound[voice] = None
        if mixer.Channel(voice).get_queue() == None:
            if loop_sound[voice]:
                # loop the current playing sound; ok to interrupt it with play cos it's the same sound as is playing
                current_chunk[voice] = loop_sound[voice].build_chunk()
            elif sound_queue[voice]:
                current_chunk[voice] = sound_queue[voice][0].build_chunk()
                if not current_chunk[voice]:
                    sound_queue[voice].pop(0)
                    try:
                        current_chunk[voice] = sound_queue[voice][0].build_chunk()
                    except IndexError:
                        # sound_queue is empty
                        break
                if sound_queue[voice][0].loop:
                    loop_sound[voice] = sound_queue[voice].pop(0)
                    # any next sound in the sound queue will stop this looping sound
                else:   
                    loop_sound[voice] = None
    for voice in range(4):
        if current_chunk[voice]:
            mixer.Channel(voice).queue(current_chunk[voice])
    for voice in range(4):
        # remove the notes that have been sent to mixer
        backend.sound_done(voice, len(sound_queue[voice]))
            
def busy():
    return (not loop_sound[0] and not loop_sound[1] and not loop_sound[2] and not loop_sound[3]) and mixer.get_busy()
        
def play_sound(frequency, total_duration, fill, loop, voice=0, volume=15):
    sound_queue[voice].append(SoundGenerator(signal_sources[voice], frequency, total_duration, fill, loop, volume))

def set_noise(is_white):
    signal_sources[3].feedback = feedback_noise if is_white else feedback_periodic
    
# implementation

# sound generators for sounds not played yet
sound_queue = [ [], [], [], [] ]
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

class SignalSource(object):
    def __init__(self, feedback, init=0x01):
        self.lfsr = init 
        self.feedback = feedback
    
    def next(self):
        # get new sample bit
        bit = self.lfsr & 1
        self.lfsr >>= 1
        if bit:
            self.lfsr ^= self.feedback
        return bit

# three tone voices plus a noise source
signal_sources = [ SignalSource(feedback_tone), SignalSource(feedback_tone), SignalSource(feedback_tone), 
                        SignalSource(feedback_noise, init_noise) ]

# The SN76489 attenuates the volume by 2dB for each step in the volume register.
# see http://www.smspower.org/Development/SN76489
max_amplitude = (1<<(mixer_bits-1)) - 1
# 2 dB steps correspond to a voltage factor of 10**(-2./20.) as power ~ voltage**2 
step_factor = 10**(-2./20.)
# geometric list of amplitudes for volume values 
amplitude = [0]*16 if not numpy else numpy.int16(max_amplitude*(step_factor**numpy.arange(15,-1,-1)))
# zero volume means silent
amplitude[0] = 0


class SoundGenerator(object):
    def __init__(self, signal_source, frequency, total_duration, fill, loop, volume):
        # noise generator
        self.signal_source = signal_source
        # one wavelength at 37 Hz is 1192 samples at 44100 Hz
        self.chunk_length = 1192 * 4
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
        if self.count_samples >= self.num_samples:
            # done already
            return None
        # work on last element of sound queue
        check_init_mixer()
        if self.frequency == 0 or self.frequency == 32767:
            chunk = numpy.zeros(self.chunk_length, numpy.int16)
        else:
            half_wavelength = sample_rate / (2.*self.frequency)
            num_half_waves = int(ceil(self.chunk_length / half_wavelength))
            # generate bits
            bits = []
            for _ in range(num_half_waves):
                bits.append(-self.amplitude if self.signal_source.next() else self.amplitude)
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
            # make the last chunk longer than a normal chunk rather than shorter, to avoid jumping sound    
            if self.count_samples + 2*len(chunk) < self.num_samples:
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
        return pygame.sndarray.make_sound(chunk)   

def stop_channel(channel):
    if mixer.get_init():
        mixer.Channel(channel).stop()
        # play short silence to avoid blocking the channel - it won't play on queue()
        silence = pygame.sndarray.make_sound(numpy.zeros(1, numpy.int16))
        mixer.Channel(channel).play(silence)
    
def pre_init_mixer():
    if mixer:
        mixer.pre_init(sample_rate, -mixer_bits, channels=1, buffer=1024) #4096

def init_mixer():    
    if mixer:
        mixer.quit()
    
def check_init_mixer():
    if mixer.get_init() == None:
        mixer.init()

def quit_sound():
    if mixer.get_init() != None:
        mixer.quit()

prepare()

