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


# number of tones, gaps or markers in background buffer
BACKGROUND_BUFFER_LENGTH = 32


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
        self._noise_freq = [self._base_freq / v for v in [1., 2., 4., 1., 1., 2., 4., 1.]]
        self._noise_freq[3] = 0.
        self._noise_freq[7] = 0.
        # pc-speaker on/off; (not implemented; not sure whether should be on)
        self._beep_on = True
        if syntax in ('pcjr', 'tandy'):
            self.capabilities = syntax
        else:
            self.capabilities = ''
        # Tandy/PCjr SOUND ON and BEEP ONfor c in value
        # tandy has SOUND ON by default, pcjr has it OFF
        self.sound_on = (self.capabilities == 'tandy')
        # timed queues for each voice (including gaps, for background counting & rebuilding)
        self.voice_queue = [TimedQueue(), TimedQueue(), TimedQueue(), TimedQueue()]
        self.foreground = True

    def beep_(self, args):
        """BEEP: produce an alert sound or switch internal speaker on/off."""
        command, = args
        if command:
            self._beep_on = (command == tk.ON)
        else:
            self.play_alert()

    def play_alert(self):
        """Produce an alert sound."""
        self.play_sound_no_wait(800, 0.25, fill=1, loop=False, voice=0, volume=15)
        # at most 16 notes in the sound queue with gaps, or 32 without gaps
        self._wait_background()

    def play_sound_no_wait(self, frequency, duration, fill, loop, voice, volume):
        """Play a sound on the tone generator."""
        if frequency < 0:
            frequency = 0
        if self.capabilities in ('tandy', 'pcjr') and self.sound_on and 0 < frequency < 110.:
            # pcjr, tandy play low frequencies as 110Hz
            frequency = 110.
        tone = signals.Event(signals.AUDIO_TONE, [voice, frequency, fill*duration, loop, volume])
        self._queues.audio.put(tone)
        self.voice_queue[voice].put(tone, None if loop else fill*duration, True)
        # separate gap event, except for legato (fill==1)
        if fill != 1 and not loop:
            gap = signals.Event(signals.AUDIO_TONE, [voice, 0, (1-fill) * duration, 0, 0])
            self._queues.audio.put(gap)
            self.voice_queue[voice].put(gap, (1-fill)*duration, False)
        if voice == 2 and frequency != 0:
            # reset linked noise frequencies
            # /2 because we're using a 0x4000 rotation rather than 0x8000
            self._noise_freq[3] = frequency/2.
            self._noise_freq[7] = frequency/2.

    def play_noise(self, source, volume, duration, loop):
        """Generate a noise."""
        frequency = self._noise_freq[source]
        noise = signals.Event(signals.AUDIO_NOISE, [source > 3, frequency, duration, loop, volume])
        self._queues.audio.put(noise)
        self.voice_queue[3].put(noise, None if loop else duration, True)

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
            self.play_sound_no_wait(freq, dur_sec, fill=1, loop=True, voice=voice, volume=volume)
            self._wait_background()
        else:
            self.play_sound_no_wait(freq, dur_sec, fill=1, loop=False, voice=voice, volume=volume)
            self.wait()

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
        self.play_noise(source, volume, dur_sec, loop=(dur < 0.02272727248))
        # don't wait for noise

    def wait(self):
        """Wait for the queue to become free."""
        if self.foreground:
            # wait until fully done
            self._wait(0)
        else:
            self._wait_background()

    def _wait_background(self):
        """Wait until the background queue becomes available."""
        # 32 plus one playing
        self._wait(BACKGROUND_BUFFER_LENGTH+1)

    def _wait(self, wait_length):
        """Wait until queue is shorter than or equal to given length."""
        # top of queue is the currently playing tone or gap
        while (self.voice_queue[0].qsize() > wait_length or
                self.voice_queue[1].qsize() > wait_length or
                self.voice_queue[2].qsize() > wait_length):
            self._queues.wait()

    def queue_length(self, voice=0):
        """Return the number of notes in the queue."""
        # one note is currently playing, i.e. not "queued"
        # two notes seems to produce better timings in practice
        return max(0, self.voice_queue[voice].qsize(False))

    def stop_all_sound(self):
        """Terminate all sounds immediately."""
        for q in self.voice_queue:
            q.clear()
        self._queues.audio.put(signals.Event(signals.AUDIO_STOP))

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
        self.fill = 7./8.
        self.tempo = 2. # 2*0.25 = 0.5 seconds per quarter note
        self.length = 0.25
        self.volume = 15


class PlayParser(object):
    """MML Parser."""

    # 12-tone equal temperament
    # C, C#, D, D#, E, F, F#, G, G#, A, A#, B
    _note_freq = [440.*2**((i-33.)/12.) for i in range(84)]
    _notes = {
        'C': 0, 'C#': 1, 'D-': 1, 'D': 2, 'D#': 3, 'E-': 3, 'E': 4, 'F': 5, 'F#': 6,
        'G-': 6, 'G': 7, 'G#': 8, 'A-': 8, 'A': 9, 'A#': 10, 'B-': 10, 'B': 11
    }

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
        if not self._sound.sound_on and len(mml_list) > 1:
            raise error.BASICError(error.STX)
        # a marker is inserted at the start of the PLAY statement
        # this takes up one spot in the buffer and thus affects timings
        for queue in self._sound.voice_queue[:3]:
            queue.put(signals.Event(signals.AUDIO_TONE, [0, 0, 0, 0, 0]), 0.002, None)
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
                    while mmls.skip_blank_read_if(('.',)):
                        dur *= 1.5
                    if note == 0:
                        # pause
                        self._sound.play_sound_no_wait(
                                0, dur*vstate.tempo,
                                1, False, voice, vstate.volume)
                    else:
                        self._sound.play_sound_no_wait(
                                self._note_freq[note-1], dur*vstate.tempo,
                                vstate.fill, False, voice, vstate.volume)
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
                    while mmls.skip_blank_read_if(('.',)):
                        error.throw_if(note == 'P' and length == 0)
                        dur *= 1.5
                    if note == 'P':
                        # length must be specified
                        if length is None:
                            raise error.BASICError(error.IFC)
                        # don't do anything for length 0
                        elif length > 0:
                            self._sound.play_sound_no_wait(
                                    0, dur * vstate.tempo,
                                    1, False, voice, vstate.volume)
                    else:
                        # use default length for length 0
                        try:
                            self._sound.play_sound_no_wait(
                                self._note_freq[(vstate.octave+next_oct)*12 + self._notes[note]],
                                dur * vstate.tempo, vstate.fill, False, voice, vstate.volume)
                        except KeyError:
                            raise error.BASICError(error.IFC)
                    next_oct = 0
                elif c == 'M':
                    c = mmls.skip_blank_read().upper()
                    if c == 'N':
                        vstate.fill = 7./8.
                    elif c == 'L':
                        vstate.fill = 1.
                    elif c == 'S':
                        vstate.fill = 3./4.
                    elif c == 'F':
                        self._sound.foreground = True
                    elif c == 'B':
                        self._sound.foreground = False
                    else:
                        raise error.BASICError(error.IFC)
                elif c == 'V' and (
                        self._sound.capabilities in ('tandy', 'pcjr') and self._sound.sound_on):
                    vol = mmls.parse_number()
                    error.range_check(-1, 15, vol)
                    if vol == -1:
                        vstate.volume = 15
                    else:
                        vstate.volume = vol
                else:
                    raise error.BASICError(error.IFC)
        # remove marker if nothing got added to the queue
        # FIXME: private member access
        last_entries = [queue._deque[-1][2] if queue else None for queue in self._sound.voice_queue[:3]]
        if last_entries == [None, None, None]:
            for queue in self._sound.voice_queue[:3]:
                queue._deque.pop()
        # align voices (excluding noise) at the end of each PLAY statement
        max_time = max(q.expiry() for q in self._sound.voice_queue[:3])
        for voice, q in enumerate(self._sound.voice_queue[:3]):
            dur = (max_time - q.expiry()).total_seconds()
            if dur > 0:
                self._sound.play_sound_no_wait(0, dur, fill=1, loop=False, voice=voice, volume=0)
        self._sound.wait()


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
        counts = 0
        try:
            while self._deque[0][1] <= datetime.datetime.now():
                self._deque.popleft()
        except (IndexError, TypeError):
            pass

    def put(self, item, duration, count_for_size):
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
        self._deque.append((item, expiry, count_for_size))

    def clear(self):
        """Clear the queue."""
        self._deque.clear()

    def qsize(self, count_all=True):
        """Number of elements in queue."""
        self._check_expired()
        if count_all:
            return len([item for i, item in enumerate(self._deque)])
        else:
            #print [ counts for _, dur, counts in self._deque ]
            # count number of notes waiting, exclude the top of queue ("now playing")
            return len([item for i, item in enumerate(self._deque) if item[2] and i])


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
