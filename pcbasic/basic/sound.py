"""
PC-BASIC - sound.py
Sound handling

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from collections import deque
import datetime

from ..compat import iterchar, zip
from .base import error
from .base import signals
from .base import tokens as tk
from .base.tokens import DIGITS
from . import mlparser
from . import values


# NOTE - sound timings and queue lengths are fairly close to DOSBox for Tandy.
# For regular GW-BASIC there are some differences
# and the results of the original are difficult to understand


# number of tones, gaps or markers in background buffer
BACKGROUND_BUFFER_LENGTH = 32

# base frequency for noise source
BASE_FREQ = 3579545. / 1024.
# frequency multipliers for noise sources 0-7
NOISE_FREQ = tuple(BASE_FREQ * v for v in (1., 0.5, 0.25, 0., 1., 0.5, 0.25, 0.))

# 12-tone equal temperament
# C, C#, D, D#, E, F, F#, G, G#, A, A#,
NOTE_FREQ = tuple(440. * 2**((i-33.)/12.) for i in range(84))
NOTES = {
    b'C': 0, b'C#': 1, b'D-': 1, b'D': 2, b'D#': 3, b'E-': 3, b'E': 4, b'F': 5, b'F#': 6,
    b'G-': 6, b'G': 7, b'G#': 8, b'A-': 8, b'A': 9, b'A#': 10, b'B-': 10, b'B': 11
}

# critical duration value below which sound loops
# in BASIC, 1/44 = 0.02272727248 which is '\x8c\x2e\x3a\x7b'
LOOP_THRESHOLD = 0.02272727248

# length of a clock tick ("PIT tick", see Joel Yliluoma's noise.bas)
TICK_LENGTH = 0x1234DC / 65536.


class Sound(object):
    """Sound queue manipulations."""

    def __init__(self, queues, values, memory, syntax):
        """Initialise sound queue."""
        # for wait() and queues
        self._queues = queues
        self._values = values
        self._memory = memory
        # Tandy/PCjr noise generator
        # frequency for noise sources
        self._noise_freq = list(NOISE_FREQ)
        # advnced sound capabilities
        self._multivoice = syntax if syntax in ('pcjr', 'tandy') else b''
        # Tandy/PCjr SOUND ON and BEEP ON
        # tandy has SOUND ON by default, pcjr has it OFF
        self._sound_on = (self._multivoice == 'tandy')
        # pc-speaker on/off; (not implemented; not sure whether should be on)
        self._beep_on = True
        # timed queues for each voice (including gaps, for background counting & rebuilding)
        self._voice_queue = [TimedQueue(), TimedQueue(), TimedQueue(), TimedQueue()]
        self._foreground = True
        self._synch = False
        # initialise PLAY state
        self.reset_play()

    @property
    def multivoice(self):
        """We have multivoice capability."""
        return bool(self._multivoice)

    def beep_(self, args):
        """BEEP: produce an alert sound or switch internal speaker on/off."""
        command, = args
        if command:
            self._beep_on = (command == tk.ON)
        else:
            self.beep()

    def beep(self):
        """Produce an alert sound."""
        self.emit_tone(800, 0.25, fill=1, loop=False, voice=0, volume=15)
        # at most 16 notes in the sound queue with gaps, or 32 without gaps
        self._wait_background()

    def emit_tone(self, frequency, duration, fill, loop, voice, volume):
        """Play a sound on the tone generator."""
        if frequency < 0:
            frequency = 0
        if self._multivoice and self._sound_on and 0 < frequency < 110.:
            # pcjr, tandy play low frequencies as 110Hz
            frequency = 110.
        # if a synch is requested, emit it at the first tone or pause
        if self._synch:
            self.emit_synch()
        # no sound if switched off
        # see https://www.vogons.org/viewtopic.php?t=56735&p=626006
        if not (self._beep_on or self._sound_on):
            volume = 0
        tone = signals.Event(signals.AUDIO_TONE, (voice, frequency, fill*duration, loop, volume))
        self._queues.audio.put(tone)
        self._voice_queue[voice].put(tone, None if loop else fill*duration, True)
        # separate gap event, except for legato (fill==1)
        if fill != 1 and not loop:
            gap = signals.Event(signals.AUDIO_TONE, (voice, 0, (1-fill) * duration, 0, 0))
            self._queues.audio.put(gap)
            self._voice_queue[voice].put(gap, (1-fill) * duration, False)
        if voice == 2 and frequency != 0:
            # reset linked noise frequencies
            # /2 because we're using a 0x4000 rotation rather than 0x8000
            self._noise_freq[3] = frequency / 2.
            self._noise_freq[7] = frequency / 2.

    def emit_noise(self, source, volume, duration, loop):
        """Generate a noise."""
        frequency = self._noise_freq[source]
        # no sound if switched off
        if not (self._beep_on or self._sound_on):
            volume = 0
        noise = signals.Event(signals.AUDIO_NOISE, (source > 3, frequency, duration, loop, volume))
        self._queues.audio.put(noise)
        self._voice_queue[3].put(noise, None if loop else duration, True)

    def sound_(self, args):
        """SOUND: produce a sound or switch external speaker on/off."""
        arg0 = next(args)
        if self._multivoice and arg0 in (tk.ON, tk.OFF):
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
            self._sound_on = (command == tk.ON)
            self.stop_all_sound()
            return
        if dur == 0:
            self.stop_all_sound()
            return
        # Tandy only allows frequencies below 37 (but plays them as 110 Hz)
        if freq != 0:
            # 32767 is pause
            error.range_check(-32768 if self._multivoice == 'tandy' else 37, 32767, freq)
        # calculate duration in seconds
        dur_sec = dur / TICK_LENGTH
        # loop if duration less than 1/44 == 0.02272727248
        if dur < LOOP_THRESHOLD:
            # play indefinitely in background
            self.emit_tone(freq, dur_sec, fill=1, loop=True, voice=voice, volume=volume)
            self._wait_background()
        else:
            self.emit_tone(freq, dur_sec, fill=1, loop=False, voice=voice, volume=volume)
            if self._foreground:
                # continue when last tone has started playing, both on tandy and gw
                # this is different from what PLAY does!
                self._wait(1)
            else:
                self._wait_background()

    def noise_(self, args):
        """Generate a noise (NOISE statement)."""
        if not self._sound_on:
            raise error.BASICError(error.IFC)
        source = values.to_int(next(args))
        error.range_check(0, 7, source)
        volume = values.to_int(next(args))
        error.range_check(0, 15, volume)
        dur = values.to_single(next(args)).to_value()
        error.range_check(-65535, 65535, dur)
        list(args)
        # calculate duration in seconds
        dur_sec = dur / TICK_LENGTH
        # loop if duration less than 1/44 == 0.02272727248
        self.emit_noise(source, volume, dur_sec, loop=(dur < LOOP_THRESHOLD))
        # noise is always background
        self._wait_background()

    def _wait_background(self):
        """Wait until the background queue becomes available."""
        # 32 plus one playing
        self._wait(BACKGROUND_BUFFER_LENGTH+1)

    def _wait(self, wait_length):
        """Wait until queue is shorter than or equal to given length."""
        # top of queue is the currently playing tone or gap
        while max(len(queue) for queue in self._voice_queue) > wait_length:
            self._queues.wait()

    def stop_all_sound(self):
        """Terminate all sounds immediately."""
        for q in self._voice_queue:
            q.clear()
        self._queues.audio.put(signals.Event(signals.AUDIO_STOP))

    def persist(self, flag):
        """Set mixer persistence flag (runmode)."""
        self._queues.audio.put(signals.Event(signals.AUDIO_PERSIST, (flag,)))

    def rebuild(self):
        """Rebuild tone queues."""
        # should we pop one at a time from each voice queue to equalise timings?
        for voice, q in enumerate(self._voice_queue):
            for item, duration in q.items():
                item.params = list(item.params)
                item.params[2] = duration
                self._queues.audio.put(item)

    def play_fn_(self, args):
        """PLAY function: get length of music queue."""
        voice = values.to_int(next(args))
        list(args)
        error.range_check(0, 255, voice)
        if not(self._multivoice and voice in (1, 2)):
            voice = 0
        return self._values.new_integer().from_int(self._voice_queue[voice].tones_waiting())

    def tones_waiting(self):
        """Return max number of tones waiting in queues."""
        return max(self._voice_queue[voice].tones_waiting() for voice in range(3))

    def emit_synch(self):
        """Synchronise the three tone voices."""
        # on Tandy/PCjr, align voices (excluding noise) at the end of each PLAY statement
        if self._multivoice:
            max_time = max(q.expiry() for q in self._voice_queue[:3])
            for voice, q in enumerate(self._voice_queue[:3]):
                duration = (max_time - q.expiry()).total_seconds()
                # fill up the queue with the necessary amount of silence
                # this takes up one spot in the buffer and thus affects timings
                # which is intentional
                balloon = signals.Event(signals.AUDIO_TONE, (voice, 0, duration, False, 0))
                self._queues.audio.put(balloon)
                self._voice_queue[voice].put(balloon, duration, None)
        self._synch = False

    def reset_play(self):
        """Reset PLAY state."""
        # music foreground (MF) mode
        self._foreground = True
        # reset all PLAY state
        self._state = [PlayState(), PlayState(), PlayState()]

    def play_(self,  args):
        """Parse a list of Music Macro Language strings (PLAY statement)."""
        # retrieve Music Macro Language string
        mml_list = [values.to_string_or_none(arg) for arg, _ in zip(args, range(3))]
        list(args)
        # at least one string must be specified
        if not any(mml_list):
            raise error.BASICError(error.MISSING_OPERAND)
        # on PCjr, three-voice PLAY requires SOUND ON
        if not self._sound_on and len(mml_list) > 1:
            raise error.BASICError(error.STX)
        # a marker is inserted at the start of the PLAY statement
        # this takes up one spot in the buffer and thus affects timings
        self._synch = True
        mml_list += [b''] * (3 - len(mml_list))
        ml_parser_list = [mlparser.MLParser(mml, self._memory, self._values) for mml in mml_list]
        next_oct = 0
        voices = list(range(3))
        while True:
            if not voices:
                break
            for voice in voices:
                vstate = self._state[voice]
                mmls = ml_parser_list[voice]
                c = mmls.skip_blank_read().upper()
                if c == b'':
                    voices.remove(voice)
                    continue
                elif c == b';':
                    continue
                elif c == b'X':
                    # insert substring
                    sub = mmls.parse_string()
                    pos = mmls.tell()
                    rest = mmls.read()
                    mmls.seek(pos)
                    mmls.truncate()
                    mmls.write(sub)
                    mmls.write(rest)
                    mmls.seek(pos)
                elif c == b'N':
                    note = mmls.parse_number()
                    error.range_check(0, 84, note)
                    dur = vstate.length
                    while mmls.skip_blank_read_if((b'.',)):
                        dur *= 1.5
                    if note == 0:
                        # pause
                        self.emit_tone(0, dur*vstate.tempo, 1, False, voice, vstate.volume)
                    else:
                        self.emit_tone(
                                NOTE_FREQ[note-1], dur*vstate.tempo,
                                vstate.fill, False, voice, vstate.volume)
                elif c == b'L':
                    recip = mmls.parse_number()
                    error.range_check(1, 64, recip)
                    vstate.length = 1. / recip
                elif c == b'T':
                    recip = mmls.parse_number()
                    error.range_check(32, 255, recip)
                    vstate.tempo = 240. / recip
                elif c == b'O':
                    octave = mmls.parse_number()
                    error.range_check(0, 6, octave)
                    vstate.octave = octave
                elif c == b'>':
                    vstate.octave += 1
                    if vstate.octave > 6:
                        vstate.octave = 6
                elif c == b'<':
                    vstate.octave -= 1
                    if vstate.octave < 0:
                        vstate.octave = 0
                elif c in (b'A', b'B', b'C', b'D', b'E', b'F', b'G', b'P'):
                    note = c
                    dur = vstate.length
                    length = None
                    if mmls.skip_blank_read_if((b'#', b'+')):
                        note += b'#'
                    elif mmls.skip_blank_read_if((b'-',)):
                        note += b'-'
                    c = mmls.skip_blank_read_if(DIGITS)
                    if c is not None:
                        numstr = [c]
                        while mmls.skip_blank() in set(iterchar(DIGITS)):
                            numstr.append(mmls.read(1))
                        # NOT ml_parse_number, only literals allowed here!
                        length = int(b''.join(numstr))
                        error.range_check(0, 64, length)
                        if length > 0:
                            dur = 1. / float(length)
                    while mmls.skip_blank_read_if((b'.',)):
                        error.throw_if(note == b'P' and length == 0)
                        dur *= 1.5
                    if note == b'P':
                        # length must be specified
                        if length is None:
                            raise error.BASICError(error.IFC)
                        # don't do anything for length 0
                        elif length > 0:
                            self.emit_tone(0, dur * vstate.tempo, 1, False, voice, vstate.volume)
                    else:
                        # use default length for length 0
                        try:
                            self.emit_tone(
                                NOTE_FREQ[(vstate.octave + next_oct) * 12 + NOTES[note]],
                                dur * vstate.tempo, vstate.fill, False, voice, vstate.volume)
                        except KeyError:
                            raise error.BASICError(error.IFC)
                    next_oct = 0
                elif c == b'M':
                    c = mmls.skip_blank_read().upper()
                    if c == b'N':
                        vstate.fill = 7./8.
                    elif c == b'L':
                        vstate.fill = 1.
                    elif c == b'S':
                        vstate.fill = 3./4.
                    elif c == b'F':
                        self._foreground = True
                    elif c == b'B':
                        self._foreground = False
                    else:
                        raise error.BASICError(error.IFC)
                elif c == b'V' and self._multivoice and self._sound_on:
                    vol = mmls.parse_number()
                    error.range_check(-1, 15, vol)
                    if vol == -1:
                        vstate.volume = 15
                    else:
                        vstate.volume = vol
                else:
                    raise error.BASICError(error.IFC)
        self._synch = False
        if self._foreground:
            # wait until fully done on Tandy/PCjr, continue early on GW
            self._wait(0 if self._multivoice else 1)
        else:
            self._wait_background()


class PlayState(object):
    """State variables of the PLAY command."""

    def __init__(self):
        """Initialise play state."""
        self.octave = 4
        self.fill = 7./8.
        # 2*0.25 = 0.5 seconds per quarter note
        self.tempo = 2.
        self.length = 0.25
        self.volume = 15


###############################################################################
# sound queue

class TimedQueue(object):
    """Queue with expiring elements."""

    def __init__(self):
        """Initialise timed queue."""
        self._deque = deque()
        # hack to reproduce queue lengths as reported by GW-BASIC
        self._balloon_popped = False

    def __getstate__(self):
        """Get pickling dict for queue."""
        self._check_expired()
        return {
            'deque': self._deque,
            'now': datetime.datetime.now(),
            'balloon_popped': self._balloon_popped,
        }

    def __setstate__(self, st):
        """Initialise queue from pickling dict."""
        offset = datetime.datetime.now() - st['now']
        self._deque = deque((item, expiry+offset, counts) for (item, expiry, counts) in st['deque'])
        self._balloon_popped = st['balloon_popped']

    def _check_expired(self):
        """Drop expired items from queue."""
        counts = 0
        try:
            while self._deque[0][1] <= datetime.datetime.now():
                popped = self._deque.popleft()
                self._balloon_popped = (popped[2] is None)
        except (IndexError, TypeError):
            pass

    def put(self, item, duration, count_for_size):
        """
        Put item onto queue with duration in seconds.
        Items with duration None remain until next item is put.
        """
        self._check_expired()
        # drop looping elements
        try:
            if self._deque[-1][1] is None:
                self._deque.pop()
        except IndexError:
            pass
        if duration is None:
            expiry = None
        else:
            last = self._deque[-1][1] if self._deque else datetime.datetime.now()
            expiry = max(last, datetime.datetime.now()) + datetime.timedelta(seconds=duration)
        self._deque.append((item, expiry, count_for_size))

    def clear(self):
        """Clear the queue."""
        self._deque.clear()

    def __len__(self):
        """Number of elements in queue."""
        self._check_expired()
        return len(self._deque)

    def tones_waiting(self):
        """Number of tones (not gaps) waiting in queue."""
        self._check_expired()
        # count number of notes waiting, exclude the top of queue ("now playing")
        waiting = len([item for i, item in enumerate(self._deque) if item[2] and i])
        # hack: if the most recent item popped was a balloon
        # (i.e. we've just started a PLAY and the first note has not finished)
        # include the first note in the waiting queue length
        waiting += self._balloon_popped
        self._balloon_popped = False
        return waiting

    def expiry(self):
        """Last expiry in queue, return now() for looping sound."""
        self._check_expired()
        try:
            return self._deque[-1][1] or datetime.datetime.now()
        except IndexError:
            return datetime.datetime.now()

    def items(self):
        """Iterate over each item and its duration."""
        self._check_expired()
        last_expiry = datetime.datetime.now()
        for item, expiry, _ in self._deque:
            if expiry is None:
                duration = None
            else:
                # adjust duration
                duration = (expiry - last_expiry).total_seconds()
                last_expiry = expiry
            yield item, duration
