"""
PC-BASIC - sound.py
Sound handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
import Queue
import string
import datetime

from .base import error
from .base import signals
from .base import tokens as tk
from . import mlparser
from . import values


class Sound(object):
    """Sound queue manipulations."""

    # base frequency for noise source
    _base_freq = 3579545./1024.

    def __init__(self, queues, values, syntax):
        """Initialise sound queue."""
        # for wait() and queues
        self._queues = queues
        self._values = values
        # Tandy/PCjr noise generator
        # frequency for noise sources
        self.noise_freq = [self._base_freq / v for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
        self.noise_freq[3] = 0.
        self.noise_freq[7] = 0.
        # pc-speaker on/off; (not implemented; not sure whether should be on)
        self.beep_on = True
        if syntax in ('pcjr', 'tandy'):
            self.capabilities = syntax
        else:
            self.capabilities = ''
        # Tandy/PCjr SOUND ON and BEEP ON
        # tandy has SOUND ON by default, pcjr has it OFF
        self.sound_on = (self.capabilities == 'tandy')
        # timed queues for each voice
        self.voice_queue = [TimedQueue(), TimedQueue(), TimedQueue(), TimedQueue()]
        self.foreground = True

    def beep_(self, args):
        """BEEP: produce an alert sound or switch internal speaker on/off."""
        command, = args
        if command:
            self.beep_on = (command == tk.ON)
        else:
            self.play_alert()

    def play_alert(self):
        """Produce an alert sound."""
        self.play_sound(800, 0.25)

    def play_sound_no_wait(self, frequency, duration, fill=1, loop=False, voice=0, volume=15):
        """Play a sound on the tone generator."""
        if frequency < 0:
            frequency = 0
        if ((self.capabilities == 'tandy' or
                (self.capabilities == 'pcjr' and self.sound_on)) and
                frequency < 110. and frequency != 0):
            # pcjr, tandy play low frequencies as 110Hz
            frequency = 110.
        if fill != 1:
            # put a placeholder 0-duration tone on the queue to represent the gap
            # the gap is included in the actual tone, but it needs to be counted for events
            gap = signals.Event(signals.AUDIO_TONE, [voice, 0, 0, 0, 0, 0])
            self._queues.audio.put(gap)
        tone = signals.Event(signals.AUDIO_TONE, [voice, frequency, duration, fill, loop, volume])
        self._queues.audio.put(tone)
        self.voice_queue[voice].put(tone, None if loop else duration)
        if voice == 2 and frequency != 0:
            # reset linked noise frequencies
            # /2 because we're using a 0x4000 rotation rather than 0x8000
            self.noise_freq[3] = frequency/2.
            self.noise_freq[7] = frequency/2.

    def sound_(self, args):
        """SOUND: produce a sound or switch external speaker on/off."""
        arg0 = next(args)
        if self.capabilities in ('pcjr', 'tandy') and arg0 in (tk.ON, tk.OFF):
            command = arg0
        else:
            command = None
            freq = values.to_int(arg0)
            dur = values.to_single(next(args)).to_value()
            error.range_check(-65535, 65535, dur)
            volume = next(args)
            if volume is None:
                volume = 15
            else:
                volume = values.to_int(volume)
                error.range_check(-1, 15, volume)
                if volume == -1:
                    volume = 15
            voice = next(args)
            if voice is None:
                voice = 0
            else:
                voice = values.to_int(voice)
                error.range_check(0, 2, voice) # can't address noise channel here
        list(args)
        if command is not None:
            self.sound_on = (command == tk.ON)
            return
        if dur == 0:
            self.stop_all_sound()
            return
        # Tandy only allows frequencies below 37 (but plays them as 110 Hz)
        if freq != 0:
            # 32767 is pause
            error.range_check(-32768 if self.capabilities == 'tandy' else 37, 32767, freq)
        # calculate duration in seconds
        dur_sec = dur / 18.2
        # in BASIC, 1/44 = 0.02272727248 which is '\x8c\x2e\x3a\x7b'
        if dur < 0.02272727248:
            # play indefinitely in background
            self.play_sound(freq, 1, loop=True, voice=voice, volume=volume)
        else:
            self.play_sound(freq, dur_sec, voice=voice, volume=volume)
            if self.foreground:
                self.wait_music()

    def play_sound(self, frequency, duration, fill=1, loop=False, voice=0, volume=15):
        """Play a sound on the tone generator; wait if tone queue is full."""
        self.play_sound_no_wait(frequency, duration, fill, loop, voice, volume)
        # at most 16 notes in the sound queue with gaps, or 32 without gaps
        self.wait_music(31)

    def noise_(self, args):
        """Generate a noise (NOISE statement)."""
        if not self.sound_on:
            raise error.BASICError(error.IFC)
        source = values.to_int(next(args))
        error.range_check(0, 7, source)
        volume = values.to_int(next(args))
        error.range_check(0, 15, volume)
        dur = values.to_single(next(args)).to_value()
        error.range_check(-65535, 65535, dur)
        list(args)
        # calculate duration in seconds
        dur_sec = dur / 18.2
        # in BASIC, 1/44 = 0.02272727248 which is '\x8c\x2e\x3a\x7b'
        if dur < 0.02272727248:
            self.play_noise(source, volume, dur_sec, loop=True)
        else:
            self.play_noise(source, volume, dur_sec)

    def play_noise(self, source, volume, duration, loop=False):
        """Generate a noise."""
        frequency = self.noise_freq[source]
        noise = signals.Event(signals.AUDIO_NOISE, [source > 3, frequency, duration, 1, loop, volume])
        self._queues.audio.put(noise)
        self.voice_queue[3].put(noise, None if loop else duration)
        # don't wait for noise

    def wait_music(self, wait_length=0):
        """Wait until a given number of notes are left on the queue."""
        while (self.queue_length(0) > wait_length or
                self.queue_length(1) > wait_length or
                self.queue_length(2) > wait_length):
            self._queues.wait()

    def wait_all_music(self):
        """Wait until all music (not noise) has finished playing."""
        while (self.is_playing(0) or self.is_playing(1) or self.is_playing(2)):
            self._queues.wait()

    def stop_all_sound(self):
        """Terminate all sounds immediately."""
        for q in self.voice_queue:
            q.clear()
        self._queues.audio.put(signals.Event(signals.AUDIO_STOP))

    def queue_length(self, voice=0):
        """Return the number of notes in the queue."""
        # NOTE: this returns zero when there are still TWO notes to play
        # this agrees with empirical GW-BASIC ON PLAY() timings!
        return max(0, self.voice_queue[voice].qsize()-2)

    def is_playing(self, voice):
        """A note is playing or queued at the given voice."""
        return self.voice_queue[voice].qsize() > 0

    def persist(self, flag):
        """Set mixer persistence flag (runmode)."""
        self._queues.audio.put(signals.Event(signals.AUDIO_PERSIST, (flag,)))

    def rebuild(self):
        """Rebuild tone queues."""
        # should we pop one at a time from each voice queue to equalise timings?
        for voice, q in enumerate(self.voice_queue):
            last_expiry = datetime.datetime.now()
            for item, expiry in q.iteritems():
                # adjust duration
                duration = (expiry - last_expiry).total_seconds()
                last_expiry = expiry
                item.params[2] = duration
                self._queues.audio.put(item)

    def play_fn_(self, args):
        """PLAY function: get length of music queue."""
        voice = values.to_int(next(args))
        list(args)
        error.range_check(0, 255, voice)
        if not(self.capabilities in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return self._values.new_integer().from_int(self.queue_length(voice))


###############################################################################
# PLAY parser

class PlayState(object):
    """State variables of the PLAY command."""

    def __init__(self):
        """Initialise play state."""
        self.octave = 4
        self.speed = 7./8.
        self.tempo = 2. # 2*0.25 =0 .5 seconds per quarter note
        self.length = 0.25
        self.volume = 15


class PlayParser(object):
    """MML Parser."""

    # 12-tone equal temperament
    # C, C#, D, D#, E, F, F#, G, G#, A, A#, B
    _note_freq = [440.*2**((i-33.)/12.) for i in range(84)]
    _notes = {'C':0, 'C#':1, 'D-':1, 'D':2, 'D#':3, 'E-':3, 'E':4, 'F':5, 'F#':6,
              'G-':6, 'G':7, 'G#':8, 'A-':8, 'A':9, 'A#':10, 'B-':10, 'B':11}

    def __init__(self, sound, memory, values):
        """Initialise parser."""
        self._memory = memory
        self._values = values
        self._sound = sound
        # initialise PLAY state
        self.reset()

    def reset(self):
        """Reset PLAY state."""
        # music foreground (MF) mode
        self._sound.foreground = True
        # reset all PLAY state
        self._state = [PlayState(), PlayState(), PlayState()]

    def play_(self,  args):
        """Parse a list of Music Macro Language strings (PLAY statement)."""
        # retrieve Music Macro Language string
        mml_list = list(values.next_string(args) for _ in range(3))
        list(args)
        # at least one string must be specified
        if not any(mml_list):
            raise error.BASICError(error.MISSING_OPERAND)
        # on PCjr, three-voice PLAY requires SOUND ON
        if self._sound.capabilities == 'pcjr' and not self._sound.sound_on and len(mml_list) > 1:
            raise error.BASICError(error.STX)
        mml_list += [''] * (3-len(mml_list))
        ml_parser_list = [mlparser.MLParser(mml, self._memory, self._values) for mml in mml_list]
        next_oct = 0
        voices = range(3)
        while True:
            if not voices:
                break
            for voice in voices:
                vstate = self._state[voice]
                mmls = ml_parser_list[voice]
                c = mmls.skip_blank_read().upper()
                if c == '':
                    voices.remove(voice)
                    continue
                elif c == ';':
                    continue
                elif c == 'X':
                    # insert substring
                    sub = mmls.parse_string()
                    pos = mmls.tell()
                    rest = mmls.read()
                    mmls.seek(pos)
                    mmls.truncate()
                    mmls.write(sub)
                    mmls.write(rest)
                    mmls.seek(pos)
                elif c == 'N':
                    note = mmls.parse_number()
                    error.range_check(0, 84, note)
                    dur = vstate.length
                    c = mmls.skip_blank().upper()
                    if c == '.':
                        mmls.read(1)
                        dur *= 1.5
                    if note == 0:
                        self._sound.play_sound(0, dur*vstate.tempo, vstate.speed,
                                        volume=0, voice=voice)
                    else:
                        self._sound.play_sound(self._note_freq[note-1], dur*vstate.tempo,
                                        vstate.speed, volume=vstate.volume,
                                        voice=voice)
                elif c == 'L':
                    recip = mmls.parse_number()
                    error.range_check(1, 64, recip)
                    vstate.length = 1. / recip
                elif c == 'T':
                    recip = mmls.parse_number()
                    error.range_check(32, 255, recip)
                    vstate.tempo = 240. / recip
                elif c == 'O':
                    octave = mmls.parse_number()
                    error.range_check(0, 6, octave)
                    vstate.octave = octave
                elif c == '>':
                    vstate.octave += 1
                    if vstate.octave > 6:
                        vstate.octave = 6
                elif c == '<':
                    vstate.octave -= 1
                    if vstate.octave < 0:
                        vstate.octave = 0
                elif c in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'P'):
                    note = c
                    dur = vstate.length
                    length = None
                    if mmls.skip_blank_read_if(('#', '+')):
                        note += '#'
                    elif mmls.skip_blank_read_if(('-',)):
                        note += '-'
                    c = mmls.skip_blank_read_if(string.digits)
                    if c is not None:
                        numstr = [c]
                        while mmls.skip_blank() in set(string.digits):
                            numstr.append(mmls.read(1))
                        # NOT ml_parse_number, only literals allowed here!
                        length = int(''.join(numstr))
                        error.range_check(0, 64, length)
                        if length > 0:
                            dur = 1. / float(length)
                    if mmls.skip_blank_read_if(('.',)):
                        error.throw_if(note == 'P' and length == 0)
                        dur *= 1.5
                        break
                    if note == 'P':
                        # length must be specified
                        if length is None:
                            raise error.BASICError(error.IFC)
                        # don't do anything for length 0
                        elif length > 0:
                            self._sound.play_sound(0, dur * vstate.tempo, vstate.speed,
                                            volume=vstate.volume, voice=voice)
                    else:
                        # use default length for length 0
                        try:
                            self._sound.play_sound(
                                self._note_freq[(vstate.octave+next_oct)*12 + self._notes[note]],
                                dur * vstate.tempo, vstate.speed,
                                volume=vstate.volume, voice=voice)
                        except KeyError:
                            raise error.BASICError(error.IFC)
                    next_oct = 0
                elif c == 'M':
                    c = mmls.skip_blank_read().upper()
                    if c == 'N':
                        vstate.speed = 7./8.
                    elif c == 'L':
                        vstate.speed = 1.
                    elif c == 'S':
                        vstate.speed = 3./4.
                    elif c == 'F':
                        self._sound.foreground = True
                    elif c == 'B':
                        self._sound.foreground = False
                    else:
                        raise error.BASICError(error.IFC)
                elif c == 'V' and (self._sound.capabilities == 'tandy' or
                                    (self._sound.capabilities == 'pcjr' and self._sound.sound_on)):
                    vol = mmls.parse_number()
                    error.range_check(-1, 15, vol)
                    if vol == -1:
                        vstate.volume = 15
                    else:
                        vstate.volume = vol
                else:
                    raise error.BASICError(error.IFC)
        max_time = max(q.expiry() for q in self._sound.voice_queue[:3])
        for voice, q in enumerate(self._sound.voice_queue):
            dur = (max_time - q.expiry()).total_seconds()
            if dur > 0:
                self._sound.play_sound(0, dur, fill=1, loop=False, voice=voice)
        if self._sound.foreground:
            self._sound.wait_all_music()


###############################################################################
# sound queue

class TimedQueue(object):
    """Queue with expiring elements."""

    def __init__(self):
        """Initialise timed queue."""
        self._deque = deque()

    def __getstate__(self):
        """Get pickling dict for queue."""
        self._check_expired()
        return {
            'deque': self._deque,
            'now': datetime.datetime.now()}

    def __setstate__(self, st):
        """Initialise queue from pickling dict."""
        offset = datetime.datetime.now() - st['now']
        self._deque = deque((item, expiry+offset) for (item, expiry) in st['deque'])

    def _check_expired(self):
        """Drop expired items from queue."""
        try:
            while self._deque[0][1] <= datetime.datetime.now():
                self._deque.popleft()
        except (IndexError, TypeError):
            pass

    def put(self, item, duration):
        """Put item onto queue with duration in seconds. Items with duration None remain until next item is put."""
        self._check_expired()
        try:
            if self._deque[-1][1] is None:
                self._deque.pop()
        except IndexError:
            pass
        if duration is None:
            expiry = None
        elif self._deque:
            expiry = max(self._deque[-1][1], datetime.datetime.now()) + datetime.timedelta(seconds=duration)
        else:
            expiry = datetime.datetime.now() + datetime.timedelta(seconds=duration)
        self._deque.append((item, expiry))

    def clear(self):
        """Clear the queue."""
        self._deque.clear()

    def qsize(self):
        """Number of elements in queue."""
        self._check_expired()
        return len(self._deque)

    def expiry(self):
        """Last expiry in queue."""
        try:
            return self._deque[-1][1]
        except IndexError:
            return datetime.datetime.now()

    def iteritems(self):
        """Iterate over items in queue."""
        self._check_expired()
        for item in self._deque:
            yield item
