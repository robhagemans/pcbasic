"""
PC-BASIC - cassette.py
Cassette Tape Device

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import os
import math
import struct
import logging
from chunk import Chunk

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import error
import config
import backend
import iolayer
import console

token_to_type = {0: 'D', 1:'M', 0xa0:'P', 0x20:'P', 0x40:'A', 0x80:'B'}
type_to_token = dict((reversed(item) for item in token_to_type.items()))

# console to output Found and Skipped messages
msgstream = None


def prepare():
    """ Initialise cassette module. """
    global msgstream
    backend.devices['CAS1:'] = CASDevice(config.options['cas1'])
    msgstream = console


#################################################################################
# Cassette device

class CASDevice(object):
    """ Cassette tape device (CASn:) """

    allowed_protocols = ('CAS', 'WAV')
    allowed_modes = 'IOLS'

    def __init__(self, arg):
        """ Initialise tape device. """
        addr, val = iolayer.parse_protocol_string(arg)
        ext = val.split('.')[-1].upper()
        if not val:
            self.tapestream = None
        elif addr == 'WAV' or (addr != 'CAS' and ext == 'WAV'):
            # if unspecified, determine type on the basis of filename extension
            self.tapestream = WAVStream(val, 'r')
        else:
            # 'CAS' is default
            self.tapestream = CASStream(val, 'r')

    def close(self):
        """ Close tape device. """
        if self.tapestream:
            self.tapestream.close()

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on tape. """
        if not self.tapestream or not self.tapestream.ok():
            # device unavailable
            raise error.RunError(68)
        return CASFile(self.tapestream, filetype, param, number, mode,
                        seg, offset, length)



#################################################################################
# Cassette files

class CASFile(iolayer.NullFile):
    """ File on CASn: device. """

    def __init__(self, tapestream, filetype, name='', number=0, mode='A',
                 seg=0, offs=0, length=0):
        """ Initialise file on tape. """
        iolayer.NullFile.__init__(self)
        self.tapestream = tapestream
        self.record_num = 0
        self.record_stream = StringIO()
        if mode == 'I':
            self.tapestream.switch_mode('r')
            self._read_header(name)
        elif mode == 'O':
            self.filetype = filetype
            self.tapestream.switch_mode('w')
            self._write_header(name, filetype, length, seg, offs)
        self.number = number
        self.name = name
        self.mode = mode

    def lof(self):
        """ LOF: illegal function call. """
        raise error.RunError(5)

    def loc(self):
        """ LOC: illegal function call. """
        raise error.RunError(5)

    def eof(self):
        """ End of file. """
        if self.mode in ('A', 'O'):
            return False
#FIXME: undefined
#        return self.tapestream.eof()

    def read_chars(self, n):
        """ Read a list of chars from device. """
        return list(self.read(n))

    def read_line(self):
        """ Read a line from device. """
        if self.eof():
            # input past end
            raise error.RunError(62)
        # readline breaks line on LF, we can only break on CR
        s = ''
        while len(s) < 255:
            c = self.read(1)
            if c == '':
                break
            elif c == '\r':
                break
            else:
                s += c
        return s

    def write_line(self, s):
        """ Write string s and CR to tape file. """
        self.write(s + '\r')

    def read(self, nbytes=-1):
        """ Read bytes from a file on tape. """
        c = ''
        try:
            while True:
                if nbytes > -1 and len(c) >= nbytes:
                    return c
                if nbytes > -1:
                    c += self.record_stream.read(nbytes-len(c))
                else:
                    c += self.record_stream.read()
                if not self._fill_record_buffer():
                    return c
        except EOF:
            return c

    def write(self, c):
        """ Write a string to a file on tape. """
        if self.filetype in ('D', 'A'):
            c = c.replace('\r\n', '\r')
        self.record_stream.write(c)

    def close(self):
        """ Close a file on tape. """
        # terminate text files with NUL
        if self.filetype in ('D', 'A'):
            self.write('\0')
        if self.mode == 'O':
            self._flush_record_buffer()

    def _read_header(self, trunk=None):
        """ Play until a file header record is found. """
        try:
            while True:
                record = self._read_record(None)
                if not record or record[0] != '\xa5':
                    # unknown record type
                    logging.debug(timestamp(self.tapestream.counter()) + "Skipped non-header record.")
                    continue
                file_trunk = record[1:9]
                try:
                    filetype = token_to_type[ord(record[9])]
                except KeyError:
                    logging.debug('Unknown file type token: %x', ord(record[9]))
                if (not trunk or file_trunk.rstrip() == trunk.rstrip()):
                    message = "%s Found." % (file_trunk + '.' + filetype)
                    msgstream.write_line(message)
                    logging.debug(timestamp(self.tapestream.counter()) + message)
                    self.filetype = filetype
                    self.length = ord(record[10]) + ord(record[11]) * 0x100
                    # for programs this is start address
                    self.seg = ord(record[12]) + ord(record[13]) * 0x100
                    self.offset = ord(record[14]) + ord(record[15]) * 0x100
                    self.record_num = 0
                    return
                else:
                    message = "%s Skipped." % (file_trunk + '.' + filetype)
                    msgstream.write_line(message)
                    logging.debug(timestamp(self.tapestream.counter()) + message)
        except EOF:
            # reached end-of-tape without finding appropriate file
            # device timeout
            raise error.RunError(24)

    def _write_header(self, name, filetype, length, seg, offs):
        """ Write a file header to the tape. """
        if filetype in ('A', 'D'):
            # ASCII program files: length, seg, offset are untouched,
            # remain that of the previous file recorded!
            seg, offs, length = self.tapestream.last
        else:
            self.tapestream.last = seg, offs, length
        self.filetype = filetype
        # header seems to end at 0x00, 0x01, then filled out with last char
        header = ('\xa5' + name[:8] + ' ' * (8-len(name))
                  + chr(type_to_token[filetype]) +
                  ''.join(map(chr, word_le(length))) +
                  ''.join(map(chr, word_le(seg))) +
                  ''.join(map(chr, word_le(offs))) +
                  '\x00\x01')
        self._write_record(header)

    def _read_record(self, reclen):
        """ Read a record from tape. """
        self.tapestream.read_leader()
        self.record_num += 1
        record = ''
        block_num = 0
        byte_count = 0
        while byte_count < reclen or reclen == None:
            try:
                data = self._read_block()
            except (PulseError, FramingError, CRCError) as e:
                logging.warning(timestamp(self.tapestream.counter()) + "%s" % str(e))
            record += data
            byte_count += len(data)
            if (reclen == None):
                break
            block_num += 1
            # read 31-bit closing sequence
            self.tapestream.read_byte()
            self.tapestream.read_byte()
            self.tapestream.read_byte()
            for _ in xrange(7):
                self.tapestream.read_bit()
        if reclen != None:
            return record[:reclen]
        return record

    def _write_record(self, data):
        """ Write a data record to tape. """
        self.tapestream.write_leader()
        while len(data) > 0:
            self._write_block(data[:256])
            data = data[256:]
        # closing sequence is 30 1-bits followed by a zero bit (based on PCE output).
        # Not 32 1-bits as per http://fileformats.archiveteam.org/wiki/IBM_PC_data_
        self.tapestream.write_byte(0xff)
        self.tapestream.write_byte(0xff)
        self.tapestream.write_byte(0xff)
        for b in (1,1,1,1,1,1,0):
            self.tapestream.write_bit(b)
        # write 100 ms second pause to make clear separation between blocks
        self.tapestream.write_pause(100)

    def _read_block(self):
        """ Read a block of data from tape. """
        count = 0
        data = ''
        while True:
            if count == 256:
                break
            byte = self.tapestream.read_byte()
            if byte == None:
                raise PulseError()
            data += chr(byte)
            count += 1
        bytes0, bytes1 = self.tapestream.read_byte(), self.tapestream.read_byte()
        crc_given = bytes0 * 0x100 + bytes1
        crc_calc = crc(data)
        # if crc for either polarity matches, return that
        if crc_given == crc_calc:
            return data
        raise CRCError(crc_given, crc_calc)

    def _write_block(self, data):
        """ Write a 256-byte block to tape. """
        # fill out short blocks with last byte
        data += data[-1]*(256-len(data))
        for b in data:
            self.tapestream.write_byte(ord(b))
        crc_word = crc(data)
        # crc is written big-endian
        lo, hi = word_le(crc_word)
        self.tapestream.write_byte(hi)
        self.tapestream.write_byte(lo)

    def _fill_record_buffer(self):
        """ Read to fill the tape buffer. """
        if self.record_num > 0:
            return False
        if self.filetype in ('M', 'B', 'P'):
            # bsave, tokenised and protected come in one multi-block record
            self.record_stream = StringIO(self._read_record(self.length))
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            # TODO: we should probably read only one block at a time (when do crc errors occur?)
            self.record_stream = StringIO()
            while True:
                record = self._read_record(256)
                num_bytes = ord(record[0])
                record = record[1:]
                if num_bytes != 0:
                    record = record[:num_bytes-1]
                # text/data files are stored on tape with CR line endings
                self.record_stream.write(record.replace('\r', '\r\n'))
                if num_bytes != 0:
                    break
        self.record_stream.seek(0)
        return True

    def _flush_record_buffer(self):
        """ Write the tape file buffer to tape. """
        data = self.record_stream.getvalue()
        if self.filetype in ('M', 'B', 'P'):
            # bsave, tokenised and protected come in one multi-block record
            self._write_record(data)
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            # TODO: we should probably write only one block at a time
            blocks, last = divmod(len(data), 255)
            for i in range(blocks):
                offset = i*255
                self._write_record('\0' + data[offset:offset+255])
            if last > 0:
                self._write_record(chr(last) + data[-last:])
        self.record_stream = StringIO()


##############################################################################


class TapeStream(object):
    """ Cassette tape stream interface. """

    # sync byte for IBM PC tapes
    sync_byte = 0x16
    # intro text
    intro = 'PC-BASIC tape\x1a'

    def __init__(self, mode='r'):
        """ Initialise tape interface. """
        # keep track of last seg, offs, length to reproduce GW-BASIC oddity
        self.last = 0, 0, 0

    def __enter__(self):
        """ Context guard. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Context guard. """
        self.close()

    def ok(self):
        """ Tape stream can be accessed. """
        return False

    def read_intro(self):
        """ Try to read intro; ensure image not empty. """
        for b in bytearray(self.intro):
            c = self.read_byte()
            if c == '':
                # empty or short file
                return False
            if c != b:
                break
        else:
            for _ in range(7):
                self.read_bit()
        return True

    def write_intro(self):
        """ Write some noise to give the reader something to get started. """
        # We just need some bits here
        # however on a new CAS file this works like a magic-sequence...
        for b in bytearray(self.intro):
            self.write_byte(b)
        # Write seven bits, so that we are byte-aligned after the sync bit
        # (after the 256-byte pilot). Makes CAS-files easier to read in hex.
        for _ in range(7):
            self.write_bit(0)
        self.write_pause(100)

    def read_leader(self):
        """ Read the leader / pilot wave. """
        while True:
            while self.read_bit() != 1:
                pass
            counter = 0
            while True:
                b = self.read_bit()
                if b != 1:
                    break
                counter += 1
            # sync bit 0 has been read, check sync byte 0x16
            # at least 64*8 bits
            if b != None and counter >= 512:
                sync = self.read_byte(skip_start=True)
                if sync == self.sync_byte:
                    return

    def write_leader(self):
        """ Write the leader / pilot tone. """
        for _ in range(256):
            self.write_byte(0xff)
        self.write_bit(0)
        self.write_byte(0x16)

    def read_byte(self, skip_start=False):
        """ Read a byte from the tape. """
        # NOTE: skip_start is ignored
        byte = 0
        for i in xrange(8):
            bit = self.read_bit()
            if bit == None:
                return None
            byte += bit * 128 >> i
        return byte

    def write_byte(self, byte):
        """ Write a byte to tape image. """
        bits = [ 1 if (byte & (128 >> i) != 0) else 0 for i in range(8) ]
        for bit in bits:
            self.write_bit(bit)

    def close(self):
        """ Eject tape. """
        pass

    def switch_mode(self, new_mode):
        """ Switch tape to reading or writing mode. """
        pass

    def flush(self):
        """ Write remaining bits to tape (stub). """
        pass

    def read_bit(self):
        """ Read the next bit (stub). """
        return 0

    def write_bit(self, bit):
        """ Write the next bit (stub). """
        pass

    def write_pause(self, milliseconds):
        """ Write pause to tape image (stub). """
        pass

##############################################################################


class CASStream(TapeStream):
    """ CAS-file cassette image bit stream. """

    def __init__(self, image_name, mode):
        """ Initialise CAS-file. """
        TapeStream.__init__(self)
        # 'r' or 'w'
        self.cas_name = image_name
        try:
            if not os.path.exists(self.cas_name):
                self._create()
            else:
                self.operating_mode = 'r'
                self.mask = 0x100
                self.cas = open(self.cas_name, 'r+b')
                self.current_byte = self.cas.read(1)
                if self.current_byte == '' or not self.read_intro():
                    self.cas.close()
                    self._create()
            self.switch_mode(mode)
        except EnvironmentError as e:
            logging.warning("Couldn't attach %s to CAS device: %s", self.cas_name, str(e))
            self.cas = None
            return

    def ok(self):
        """ Tape stream can be accessed. """
        return self.cas is not None

    def counter(self):
        """ Time stamp in seconds. """
        # approximate: average 750 us per bit, cut on bytes
        return self.cas.tell() * 8 * 750 / 1000000.

    def close(self):
        """ Close tape image. """
        # ensure any buffered bits are written
        self.flush()
        self.cas.close()

    def read_bit(self):
        """ Read the next bit. """
        self.mask >>= 1
        if self.mask <= 0:
            self.current_byte = self.cas.read(1)
            if not self.current_byte:
                raise EOF
            self.mask = 0x80
        if (ord(self.current_byte) & self.mask == 0):
            return 0
        else:
            return 1

    def write_bit(self, bit):
        """ Write a bit to tape. """
        # note that CAS-files aren't necessarily byte aligned 
        # the ones we make are, but PCE's ones aren't.
        self.mask >>= 1
        if self.mask <= 0:
            self.cas.write(self.current_byte)
            self.current_byte = '\0'
            self.mask = 0x80
        self.current_byte = chr(ord(self.current_byte) | (bit*self.mask))

    def flush(self):
        """ Write remaining bits to tape. """
        if self.operating_mode == 'w':
            # write -> read
            # read bit on stream to combine with
            existing = self.cas.read(1)
            if not existing:
                existing = '\0'
            else:
                self.cas.seek(-1, 1)
            # 0b1000 -> 0b1111 etc.
            combine_mask = self.mask * 2 - 1
            self.current_byte = chr(
                (ord(existing) & combine_mask) +
                (ord(self.current_byte) & (0xff^combine_mask)))
            # flush bits in write buffer
            # pad with zero if necessary to align on byte limit
            self.cas.write(self.current_byte)
            # if we continue to write, we should seek(-1,1)
            self.cas.seek(-1, 1)

    def switch_mode(self, new_mode):
        """ Switch tape to reading or writing mode. """
        self.flush()
        if self.operating_mode == 'w' and new_mode == 'r':
            self.current_byte = self.cas.read(1)
        elif self.operating_mode == 'r' and new_mode == 'w':
            self.cas.seek(-1, 1)
        self.operating_mode = new_mode

    def _create(self):
        """ Create a new CAS-file. """
        self.current_byte = '\0'
        self.mask = 0x100
        with open(self.cas_name, 'wb') as self.cas:
            self.operating_mode = 'w'
            self.current_byte = '\0'
            self.write_intro()
        self.cas = open(self.cas_name, 'r+b')
        self.cas.seek(0, 2)


class WAVStream(TapeStream):
    """ WAV-file cassette image bit stream. """

    def __init__(self, filename, mode):
        """ Initialise WAV-file. """
        TapeStream.__init__(self)
        self.filename = filename
        try:
            if not os.path.exists(filename):
                # create/overwrite file
                self.framerate = 22050
                self.sampwidth = 1
                self.nchannels = 1
                self.wav = open(self.filename, 'wb')
                self._write_wav_header()
                self.operating_mode = 'w'
            else:
                # open file for reading and find wave parameters
                self.wav = open(self.filename, 'r+b')
                self._read_wav_header()
                self.operating_mode = 'r'
        except EnvironmentError as e:
            logging.warning("Couldn't attach %s to CAS device: %s", filename, str(e))
            self.wav = None
            return
        self.wav_pos = 0
        self.buf_len = 1024
        # convert 8-bit and 16-bit values to ints
        if self.sampwidth == 1:
            self.sub_threshold = 0
            self.subtractor = 128*self.nchannels
        else:
            self.sub_threshold = 256*self.nchannels/2
            self.subtractor =  256*self.nchannels
        # volume above/below zero that is interpreted as zero
        self.zero_threshold = self.nchannels
        # 1000 us for 1, 500 us for 0; threshold for half-pulse (500 us, 250 us)
        self.halflength = [250*self.framerate/1000000, 500*self.framerate/1000000]
        self.halflength_cut = 375*self.framerate/1000000
        self.halflength_max = 2*self.halflength_cut
        self.halflength_min = self.halflength_cut / 2
        self.length_cut = 2*self.halflength_cut
        # 2048 halves = 1024 pulses = 512 1-bits = 64 bytes of leader
        self.min_leader_halves = 2048
        # initialise generators
        #self.lowpass = butterworth(self.framerate, 3000)
        #self.lowpass = butterband_sox(self.framerate, 1500, 1000)
        #self.lowpass = butterband4(self.framerate, 500, 3000)
        self.lowpass = passthrough()
        self.lowpass.send(None)
        self.read_half = self._gen_read_halfpulse()
        # write fluff at start if this is a new file
        if self.operating_mode == 'w':
            self.write_intro()
        self.switch_mode(mode)

    def ok(self):
        """ Tape stream can be accessed. """
        return self.wav is not None

    def switch_mode(self, mode):
        """ Switch tape to reading or writing mode. """
        self.operating_mode = mode

    def counter(self):
        """ Time stamp in seconds. """
        return self.wav_pos/(1.*self.framerate)

    def read_bit(self):
        """ Read the next bit. """
        length_up, length_dn = self.read_half.next(), self.read_half.next()
        if (length_up > self.halflength_max or length_dn > self.halflength_max or
                length_up < self.halflength_min or length_dn < self.halflength_min):
            return None
        elif length_up >= self.halflength_cut:
            return 1
        else:
            return 0

    def close(self):
        """ Close WAV-file. """
        TapeStream.close(self)
        # write file length fields
        self.wav.seek(self._form_length_pos, 0)
        self.wav.write(struct.pack('<L', 36 + self.length))
        self.wav.seek(self._data_length_pos, 0)
        self.wav.write(struct.pack('<L', self.length))
        self.wav.close()

    def _fill_buffer(self):
        """ Fill buffer with frames and pre-process. """
        frame_buf = []
        frames = self.wav.read(self.buf_len*self.nchannels*self.sampwidth)
        if not frames:
            raise EOF
        # convert MSBs to int (data stored little endian)
        frames2 = map(ord, frames[self.sampwidth-1::self.sampwidth])
        # sum frames over channels
        frames3 = map(sum, zip(*[iter(frames2)]*self.nchannels))
        frames4 = [ x-self.subtractor if x >= self.sub_threshold else x for x in frames3 ]
        return self.lowpass.send(frames4)

    def _gen_read_halfpulse(self):
        """ Generator to read a half-pulse and yield its length. """
        length = 0
        frame = 1
        prezero = 1
        pos_in_frame = 0
        frame_buf = []
        while True:
            try:
                sample = frame_buf[pos_in_frame]
                pos_in_frame += 1
            except IndexError:
                frame_buf = self._fill_buffer()
                pos_in_frame = 0
                continue
            length += 1
            last, frame = frame, (sample > self.zero_threshold) + (sample >= -self.zero_threshold) - 1
            if last != frame and (last != 0 or frame == prezero):
                if frame == 0 and last != 0:
                    prezero = last
                self.wav_pos += length
                yield length
                length = 0

    def write_pause(self, milliseconds):
        """ Write a pause of given length to the tape. """
        length = (milliseconds * self.framerate / 1000)
        zero = { 1: '\x7f', 2: '\x00\x00'}
        self.wav.write(zero[self.sampwidth] * self.nchannels * length)
        self.wav_pos += length

    def write_bit(self, bit):
        """ Write a bit to tape. """
        half_length = self.halflength[bit]
        down = { 1: '\x00', 2: '\x00\x80'}
        up = { 1: '\xff', 2: '\xff\x7f'}
        self.wav.write(
            down[self.sampwidth] * self.nchannels * half_length +
            up[self.sampwidth] * self.nchannels * half_length)
        self.wav_pos += 2 * half_length

    def _read_wav_header(self):
        """ Read RIFF WAV header. """
        ch = Chunk(self.wav, bigendian=0)
        if ch.getname() != 'RIFF' or ch.read(4) != 'WAVE':
            logging.debug('Not a WAV file.')
            return False
        self.form_length_pos = self.wav.tell() - 8
        self.sampwidth, self.nchannels, self.framerate = 0, 0, 0
        while True:
            try:
                chunk = Chunk(ch, bigendian=0)
            except EOFError:
                logging.debug('No data chunk found in WAV file.')
                return False
            chunkname = chunk.getname()
            if chunkname == 'fmt ':
                format_tag, self.nchannels, self.framerate, _, _ = struct.unpack('<HHLLH', chunk.read(14))
                if format_tag == 1:
                    sampwidth = struct.unpack('<H', chunk.read(2))[0]
                    self.sampwidth = (sampwidth + 7) // 8
                else:
                    logging.debug('WAV file not in uncompressed PCM format.')
                    return False
            elif chunkname == 'data':
                if not self.sampwidth:
                    logging.debug('Format chunk not found.')
                    return False
                self.data_length_pos = self.wav.tell()
                self.wav.read(4)
                self.start = self.wav.tell()
                return True
            chunk.skip()

    def _write_wav_header(self):
        """ Write RIFF WAV header. """
        self.wav.write('RIFF')
        self.form_length_pos = self.wav.tell()
        # fill in length later
        length = 0
        self.wav.write(struct.pack('<L4s4sLHHLLHH4s',
            36 + length, 'WAVE', 'fmt ', 16,
            1, self.nchannels, self.framerate,
            self.nchannels * self.framerate * self.sampwidth,
            self.nchannels * self.sampwidth,
            self.sampwidth * 8, 'data'))
        self.data_length_pos = self.wav.tell()
        self.wav.write(struct.pack('<L', length))

    def read_leader(self):
        """ Read the leader / pilot wave. """
        while True:
            while self.read_bit() != 1:
                pass
            counter = 0
            pulse = (0,0)
            while True:
                last = pulse
                half = self.read_half.next()
                if half < self.length_cut/2:
                    if counter > self.min_leader_halves:
                        #  zero bit; try to sync
                        half = self.read_half.next()
                    break
                counter += 1
            # sync bit 0 has been read, check sync byte
            if counter >= self.min_leader_halves:
                # read rest of first byte
                try:
                    self.last_error_bit = None
                    self.dropbit = None
                    sync = self.read_byte(skip_start=True)
                    if sync == self.sync_byte:
                        return
                    else:
                        logging.debug(timestamp(self.counter()) + "Incorrect sync byte:" + repr(sync))
                except (PulseError, FramingError) as e:
                    logging.debug(timestamp(self.counter()) + "Error in sync byte: %s", str(e))


##############################################################################


class BasicodeStream(WAVStream):
    """ BASICODE-standard WAV image reader. """

    def __init__(self, filename):
        """ Initialise BASICODE WAV-file reader. """
        WAVStream.__init__(self, filename)
        # basicode uses STX as sync byte
        self.sync_byte = 0x02
        # fix frequencies to Basicode standards, 1200 / 2400 Hz
        # one = two pulses of 417 us; zero = one pulse of 833 us
        # value is cutoff for full pulse
        self.length_cut = 626*self.framerate/1000000
        self.length_max = 2*self.length_cut
        self.length_min = self.length_cut / 2
        # initialise generators
        self.lowpass = butterband4(self.framerate, 1350, 3450)
        #self.lowpass = butterband_sox(self.framerate, 2100, 1500)
        self.lowpass.send(None)
        # byte error correcting
        self.dropbit = None
        self.last_error_bit = None

    def read_bit(self):
        """ Read the next bit. """
        pulse0 = (self.read_half.next(), self.read_half.next())
        # one = two pulses of 417 us; zero = one pulse of 833 us
        if sum(pulse0) < self.length_cut:
            pulse1 = (self.read_half.next(), self.read_half.next())
            if sum(pulse1) < self.length_cut:
                return 1
            else:
                return None
        else:
            return 0

    def read_byte(self, skip_start=False):
        """ Read a byte from the tape. """
        if skip_start:
            start = 0
        else:
            start = self.read_bit()
        byte = 0
        bits = [ self.read_bit() for _ in xrange(8) ]
        if self.dropbit == 1 and self.last_error_bit == 0 and bits[-2:] == [1, 1]:
            # error-correcting: have we gone one too far?
            stop0, stop1 = bits[-2:]
            bits = [self.dropbit, start] + bits[:-2]
            start = self.last_error_bit
        elif self.dropbit == 0 and bits[-1] == 1:
            # error-correcting: keep dropbit
            stop0, stop1 = bits[-1], self.read_bit()
            bits = [start] + bits[:-1]
            start = self.dropbit
        else:
            # normal case, no error last time
            # or can't find a working correction
            stop0 = self.read_bit()
            stop1 = self.read_bit()
        if start == 1 or stop0 == 0 or stop1 == 0:
            self.last_error_bit = stop1
            # incorrect start/stop bit, try to recover by shifting
            self.dropbit = self.read_bit()
            raise FramingError([start] + bits + [stop0, stop1])
        else:
            # start/stopbits correct or unreadable
            self.last_error_bit = None
            self.dropbit = None
            if None in bits:
                raise PulseError()
            # bits in inverse order
            byte = sum(bit << i for i, bit in enumerate(bits))
            # flip bit 7
            byte ^= 0x80
            return byte

    def search_file(self, allowed_types=('A', 'D')):
        """ Play until a file record is found. """
        self.read_leader()
        msgstream.write_line("BASICODE.A Found.")
        logging.debug(timestamp(self.counter()) + "BASICODE.A Found.")
        return 'BASICODE', 'A', 0, 0, 0

    def read_file(self, filetype='D', file_bytes=0):
        """ Read a file from tape. """
        if filetype not in ('D', 'A'):
            # not supported
            return ''
        data = ''
        # xor sum includes STX byte
        checksum = 0x02
        while True:
            try:
                byte = self.read_byte()
            except (PulseError, FramingError) as e:
                logging.warning(timestamp(self.counter()) + "%d %s" % (self.wav_pos, str(e)))
                # insert a zero byte as a marker for the error
                byte = 0
            except EOF as e:
                logging.warning(timestamp(self.counter()) + "%d %s" % (self.wav_pos, str(e)))
                break
            checksum ^= byte
            if byte == 0x03:
                break
            data += chr(byte)
            # CR -> CRLF
            if byte == 0x0d:
                data += '\n'
        # read one-byte checksum and report errors
        try:
            checksum_byte = self.read_byte()
        except (PulseError, FramingError, EOF) as e:
            logging.warning(timestamp(self.counter()) + "Could not read checksum: %s " % str(e))
        # checksum shld be 0 for even # bytes, 128 for odd
        if checksum_byte == None or checksum^checksum_byte not in (0,128):
            logging.warning(timestamp(self.counter()) + "Checksum: [FAIL]  Required: %02x  Realised: %02x" % (checksum_byte, checksum))
        else:
            logging.warning(timestamp(self.counter()) + "Checksum: [ ok ] ")
        return data

    def read_leader(self):
        """ Read the leader / pilot wave. """
        while True:
            while self.read_bit() != 1:
                pass
            counter = 0
            pulse = (0,0)
            while True:
                last = pulse
                half = self.read_half.next()
                if half > self.length_cut/2:
                    if counter > self.min_leader_halves:
                        #  zero bit; try to sync
                        half = self.read_half.next()
                    break
                counter += 1
            # sync bit 0 has been read, check sync byte
            if counter >= self.min_leader_halves:
                # read rest of first byte
                try:
                    self.last_error_bit = None
                    self.dropbit = None
                    sync = self.read_byte(skip_start=True)
                    if sync == self.sync_byte:
                        return
                    else:
                        logging.warning(timestamp(self.counter()) + "Incorrect sync byte: %02x" % sync)
                except (PulseError, FramingError) as e:
                    logging.warning(timestamp(self.counter()) + "Error in sync byte: %s" % str(e))


#################################################################################

class CassetteException(Exception):
    """ Cassette exception. """

    def __str__(self):
        """ Return exception desription (by default, the docstring.) """
        return self.__doc__.strip()


class EOF(CassetteException):
    """ End-of-tape exception. """
    pass

class CRCError(CassetteException):
    """ CRC check failed. """

    def __init__(self, crc_calc, crc_given):
        self.crc_calc, self.crc_given = crc_calc, crc_given

    def __str__(self):
        return self.__doc__.strip() + ' Prescribed: %04x Realised: %04x' % (self.crc_given, self.crc_calc)


class PulseError(CassetteException):
    """ Pulse length error. """
    pass


class FramingError(CassetteException):
    """ Framing error. """

    def __init__(self, bitlist=[]):
        self.bits = bitlist

    def __str__(self):
        return self.__doc__.strip() + ' ' + repr(self.bits)


##############################################################################
# supporting functions

def crc(data):
    """ Calculate 16-bit CRC-16-CCITT for data. """
    # see http://en.wikipedia.org/wiki/Computation_of_cyclic_redundancy_checks
    # for a lookup table version, see e.g. WAV2CAS v1.3 for Poisk PC. by Tronix (C) 2013
    # however, speed is not critical for this function
    rem = 0xffff
    for d in bytearray(data):
        rem ^= d << 8
        for _ in range(8):
            rem <<= 1
            if rem & 0x10000:
                rem ^= 0x1021
            rem &= 0xffff
    return rem ^ 0xffff

def word_le(word):
    """ Convert word to little-endian list of bytes. """
    hi, lo = divmod(word, 256)
    return [lo, hi]

def hms(seconds):
    """ Return elapsed cassette time at given frame. """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return h, m, s

def timestamp(counter):
    """ Time stamp. """
    return "[%d:%02d:%02d] " % hms(counter)


##############################################################################
# filters

def passthrough():
    """ Passthrough filter. """
    x = []
    while True:
        x = yield x

def butterworth(sample_rate, cutoff_freq):
    """ Second-order Butterworth low-pass filter. """
    # cf. src/arch/ibmpc/c (Hampa Hug) in PCE sources
    x, y = [0, 0], [0, 0]
    om = 1. / math.tan((math.pi * cutoff_freq) / sample_rate)
    rb0 = 1. / (om*om + om*math.sqrt(2.) + 1.)
    b1, b2 = 2.*(1.-om*om), (om*om-om*math.sqrt(2.)+1.)
    while True:
        inp = yield y[2:]
        x = x[-2:] + inp
        y = y[-2:] + [0]*len(inp)
        for i in range(2, len(x)):
            y[i] = (x[i] + 2*x[i-1] + x[i-2] - b1*y[i-1] - b2*y[i-2]) * rb0

def butterband4(sample_rate, lo_freq, hi_freq):
    """ 4th-order Butterworth band-pass filter. """
    # cf. http://www.exstrom.com/journal/sigproc/bwbpf.c
    f1 = hi_freq
    f2 = lo_freq
    s = sample_rate
    n = 1
    #
    a = math.cos(math.pi*(f1+f2)/s) / math.cos(math.pi*(f1-f2)/s)
    a2 = a*a
    b = math.tan(math.pi*(f1-f2)/s)
    b2 = b*b
    #
    r = math.sin(math.pi*(1.0)/(4.))
    s = b2 + 2.0*b*r + 1.0
    A = (b2/s)   * 2 ## *2 to gain amplitude, my addition
    d1 = 4.0*a*(1.0+b*r)/s
    d2 = 2.0*(b2-2.0*a2-1.0)/s
    d3 = 4.0*a*(1.0-b*r)/s
    d4 = -(b2 - 2.0*b*r + 1.0)/s
    w0, w1, w2, w3, w4 = 0,0,0,0,0
    out = []
    while True:
        inp = yield out
        out = [0]*len(inp)
        for i, x in enumerate(inp):
            w0 = d1*w1 + d2*w2 + d3*w3 + d4*w4 + x
            out[i] = A*(w0 - 2.0*w2 + w4)
            w4, w3, w2, w1 = w3, w2, w1, w0

def butterband_sox(sample_rate, f0, width):
    """ 2-pole Butterworth band-pass filter. """
    # see http://musicdsp.org/files/Audio-EQ-Cookbook.txt
    # and SOX source code
    # width is difference between -3dB cutoff points
    # it seems f0 = sqrt(f_hi f_lo), width ~ f_hi - f_lo
    w0 = 2.*math.pi*f0/sample_rate
#    alpha = sin(w0)*sinh(log(2.)/2 * width_octaves * w0/sin(w0)) (digital)
#    alpha = sin(w0)*sinh(log(2.)/2 * width_octaves) (analogue)
    # this is from SOX:
    alpha = math.sin(w0)/(2.*f0/width)
    #
    b0 =   alpha
    #b1 =   0
    b2 =  -alpha
    a0 =   1. + alpha
    a1 =  -2.*math.cos(w0)
    a2 =   1. - alpha
    b0a = b0/a0
    b2a = b2/a0
    a1a = a1/a0
    a2a = a2/a0
    x, y = [0, 0], [0, 0]
    while True:
        inp = yield y[2:]
        x = x[-2:] + inp
        y = y[-2:] + [0]*len(inp)
        for i in range(2, len(x)):
            y[i] = b0a*x[i] + b2a*x[i-2] - a1a*y[i-1] - a2a*y[i-2]

prepare()

