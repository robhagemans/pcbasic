import wave
import math
import struct
import logging

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

token_to_type = {0: 'D', 1:'M', 0xa0:'P', 0x20:'P', 0x40:'A', 0x80:'B'}
type_to_token = dict((reversed(item) for item in token_to_type.items()))
type_to_magic = {'D': '', 'A':'', 'M':'\xfd', 'P':'\xfe', 'B':'\xff'}
magic_to_type = {'\xfd': 'M', '\xfe': 'P', '\xff': 'B'}

#############################

# console to output Found and Skipped messages
msgstream = None

#############################

class CassetteException(Exception):
    """ Cassette exception. """

    def __str__(self):
        """ Return exception desription (by default, the docstring.) """
        return self.__doc__.strip()


class EOF(CassetteException):
    """ End-of-tape exception. """
    pass

class UnsupportedFormat(CassetteException):
    """ Cassette format not supported. """
    pass

class UnsupportedType(CassetteException):
    """ File type not supported. """
    pass

class UnknownRecord(CassetteException):
    """ Unknown record type. """
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

class IncorrectMode(CassetteException):
    """ File not open for this operation. """
    pass


#############################

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

#############################

def passthrough():
    """ Passthrough filter. """
    x = []
    while True:
        x = yield x

def butterworth(sample_rate, cutoff_freq):
    """ Second-order Butterworth low-pass filter. """
    # cf. src/arch/ibmpc/cassette.c (Hampa Hug) in PCE sources
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

#############################

def parse_header(record):
    """ Extract header information. """
    if not record or record[0] != '\xa5':
        return None
    name = record[1:9]
    token = ord(record[9])
    nbytes = ord(record[10]) + ord(record[11]) * 0x100
    # for programs this is start address: cf to offset of next line in prgram
    seg = ord(record[12]) + ord(record[13]) * 0x100
    offs = ord(record[14]) + ord(record[15]) * 0x100
    return name, token, nbytes, seg, offs

def header(name, token, nbytes, seg, offs):
    """ Encode header information. """
    data = '\xa5'
    data += name[:8] + ' ' * (8-len(name))
    data += chr(token)
    # length
    data += ''.join(map(chr, word_le(nbytes)))
    # load address segment
    data += ''.join(map(chr, word_le(seg)))
    # load address offset
    data += ''.join(map(chr, word_le(offs)))
    # seems to end at 0x00, 0x01, then filled out with last char
    data += '\x00\x01'
    return data

#############################


class TapeStream(object):
    """ Cassette tape stream interface. """

    def __init__(self):
        """ Initialise tape interface. """
        # sync byte for IBM PC tapes
        self.sync_byte = 0x16
        # state variables
        self.last_seg, self.last_offs, self.last_length = 0, 0, 0
        self.loc = 0
        self.mask = 0
        self.current_byte = 0
        self.record_stream = StringIO()

    def __enter__(self):
        """ Context guard for 'with'. """
        return self

    def __exit__(self, type, value, traceback):
        """ Context guard for 'with'. """
        self.eject()

    def stamp(self):
        """ Time stamp. """
        return ''

    def eject(self):
        """ Eject tape. """
        self.close()
        self.stop()

    def play(self):
        """ Switch tape to reading mode. """
        self.stop()
        self.operating_mode == 'play'
        # start by reading next byte
        self.mask = 0

    def record(self):
        """ Switch tape to writing mode. """
        self.stop()
        self.operating_mode == 'rec'
        # don't write out zero-ed current byte on start
        self.mask = 0x100

    def stop(self):
        """ Stop tape play/record. """
        self.close()
        self.flush_bit_buffer()
        self.mask = 0
        self.current_byte = 0
        self.operating_mode = ''

    def open(self, filename, filetype, mode, length=0, seg=0, offs=0):
        """ Open a file on the tape. """
        if mode in ('L', 'I'):
            self.play()
            return self.read_header(filename, filetype)
        elif mode in ('S', 'O'):
            self.record()
            self.write_header(filename, filetype, length, seg, offs)

    def close(self):
        """ Close a file on tape. """
        # terminate text files with NUL
        if self.file_type in ('D', 'A'):
            self.write('\0')
        self.flush_record_buffer()

    def read_header(self, trunk=None, allowed_types=('D', 'A', 'M', 'B', 'P')):
        """ Play until a file header record is found. """
        while True:
            record = self.read_record(None)
            header = parse_header(record)
            if not header:
                # unknown record type
                logging.debug(self.stamp() + "Skipped record of unknown type.")
            else:
                file_trunk, file_token, file_bytes, seg, offs = header
                file_ext = token_to_type[file_token]
                if ((not trunk or file_trunk.rstrip() == trunk.rstrip()) and
                        file_ext in allowed_types):
                    msgstream.write_line("%s Found." % (file_trunk + '.' + file_ext))
                    logging.debug(self.stamp() + "%s Found." % (file_trunk + '.' + file_ext))
                    return file_trunk, file_ext, file_bytes, seg, offs
                else:
                    msgstream.write_line("%s Skipped." % (file_trunk + '.' + file_ext))
                    logging.debug(self.stamp() + "%s Skipped." % (file_trunk + '.' + file_ext))
                self.file_type = file_ext
                self.record_num = 0

    def read_leader(self):
        """ Read the leader / pilot wave. """
        while True:
            while self.read_bit.next() != 1:
                pass
            counter = 0
            while True:
                b = self.read_bit.next()
                if b != 1:
                    break
                counter += 1
            # sync bit 0 has been read, check sync byte 0x16
            # at least 64*8 bits
            if b != None and counter >= 512:
                sync = self.read_byte(skip_start=True)
                if sync == self.sync_byte:
                    return

    def read_block(self):
        """ Read a block of data from tape. """
        count = 0
        data = ''
        while True:
            if count == 256:
                break
            byte = self.read_byte()
            if byte == None:
                raise PulseError()
            data += chr(byte)
            count += 1
        bytes0, bytes1 = self.read_byte(), self.read_byte()
        crc_given = bytes0 * 0x100 + bytes1
        crc_calc = crc(data)
        # if crc for either polarity matches, return that
        if crc_given == crc_calc:
            return data
        raise CRCError(crc_given, crc_calc)

    def read(self, nbytes):
        """ Read bytes from a file on tape. """
        if self.operating_mode == 'rec' or current_file == None:
            raise IncorrectMode()
        c = ''
        while True:
            c += self.record_stream.read(len(c) - nbytes)
            if len(c) == nbytes:
                return c
            if not self.fill_record_buffer():
                return c

    def read_record(self, reclen):
        """ Read a record from tape. """
        self.read_leader()
        self.record_num += 1
        record = ''
        block_num = 0
        byte_count = 0
        while byte_count < reclen or reclen == None:
            try:
                data = self.read_block()
            except (PulseError, FramingError, CRCError) as e:
                logging.warning(self.stamp() + "%d %s" % (self.wav_pos, str(e)))
            record += data
            byte_count += len(data)
            if (reclen == None):
                # and
                #    (data[:3] == '\xff\xff\xff' or
                #    (block_num == 0 and data[0] == '\xa5'))):
                break
            block_num += 1
        if reclen != None:
            return record[:reclen]
        return record

    def fill_record_buffer(self):
        """ Read to fill the tape buffer. """
        if self.record_num > 0:
            return False
        if self.file_type in ('M', 'B', 'P'):
            # bsave, tokenised and protected come in one multi-block record
            self.record_stream = StringIO(self.read_record(file_bytes))
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            # TODO: we should probably read only one block at a time (when do crc errors occur?)
            self.record_stream = StringIO()
            while True:
                record = self.read_record(256)
                num_bytes = ord(record[0])
                record = record[1:]
                if num_bytes != 0:
                    record = record[:num_bytes-1]
                # text/data files are stored on tape with CR line endings
                self.record_buffer.write(record.replace('\r', '\r\n'))
                if num_bytes != 0:
                    break
            self.record_stream.seek(0)
        return True

    def read_byte(self, skip_start=False):
        """ Read a byte from the tape. """
        # NOTE: skip_start is ignored
        byte = 0
        for i in xrange(8):
            bit = self.read_bit.next()
            if bit == None:
                return None
            byte += bit * 128 >> i
        return byte

    def write_byte(self, byte):
        """ Write a byte to tape image. """
        bits = [ 1 if (byte & ( 128 >> i) != 0) else 0 for i in range(8) ]
        for bit in bits:
            self.write_bit(bit)

    def write_intro(self):
        """ Write some noise to give the reader something to get started. """
        # We just need some bits here
        # however on a new CAS file this works like a magic-sequence...
        for b in bytearray('CAS1:'):
            self.write_byte(b)
        # Write seven bits, so that we are byte-aligned after the sync bit
        # (after the 256-byte pilot). Makes CAS-files easier to read in hex.
        for _ in range(7):
            self.write_bit(0)
        self.write_pause(100)

    def write_leader(self):
        """ Write the leader / pilot tone. """
        for _ in range(256):
            self.write_byte(0xff)
        self.write_bit(0)
        self.write_byte(0x16)

    def write_block(self, data):
        """ Write a 256-byte block to tape. """
        # fill out short blocks with last byte
        data += data[-1]*(256-len(data))
        for b in data:
            self.write_byte(ord(b))
        crc_word = crc(data)
        # crc is written big-endian
        lo, hi = word_le(crc_word)
        self.write_byte(hi)
        self.write_byte(lo)

    def write_record(self, data):
        """ Write a data record to tape. """
        self.write_leader()
        while len(data) > 0:
            self.write_block(data[:256])
            data = data[256:]
        # closing sequence is 30 1-bits followed by a zero bit (based on PCE output).
        # Not 32 1-bits as per http://fileformats.archiveteam.org/wiki/IBM_PC_data_cassette.
        self.write_byte(0xff)
        self.write_byte(0xff)
        self.write_byte(0xff)
        for b in (1,1,1,1,1,1,0):
            self.write_bit(b)
        # write 100 ms second pause to make clear separation between blocks
        self.write_pause(100)

    def write_header(self, name, file_type, length, seg, offs):
        """ Write a file header to the tape. """
        if file_type not in ('D', 'A', 'M', 'B', 'P'):
            raise UnsupportedType()
        if file_type in ('A', 'D'):
            # ASCII program files: length, seg, offset are untouched,
            # remain that of the previous file recorded!
            seg, offs, length = self.last_seg, self.last_offs, self.last_length
        else:
            self.last_seg, self.last_offs, self.last_length = seg, offs, length
        self.file_type = file_type
        self.write_record(header(name, type_to_token[file_type], length, seg, offs))

    def write(self, c):
        """ Write a string to a file on tape. """
        if self.file_type in ('D', 'A'):
            c = c.replace('\r\n', '\r')
        self.record_stream.write(c)

    def flush_record_buffer(self):
        """ Write the tape file buffer to tape. """
        if self.operating_mode == 'rec':
            data = self.record_stream.getvalue()
            if self.file_type in ('M', 'B', 'P'):
                # bsave, tokenised and protected come in one multi-block record
                self.write_record(data)
            else:
                # ascii and data come as a sequence of one-block records
                # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
                # TODO: we should probably write only one block at a time
                blocks, last = divmod(len(data), 255)
                for i in range(blocks):
                    offset = i*255
                    self.write_record('\0' + data[offset:offset+255])
                if last > 0:
                    self.write_record(chr(last) + data[-last:])
        self.record_stream = StringIO()

    def flush_bit_buffer(self):
        """ Write remaining bits to tape (stub). """
        pass


class CASStream(TapeStream):
    """ CAS-file cassette image reader. """

    def __init__(self, image_name):
        """ Initialise CAS-file for reading. """
        TapeStream.__init__(self)
        self.operating_mode = ''
        self.cas_name = image_name
        # byte location in file
        self.loc = 0
        self.current_byte = 0
        try:
            # try reading first to ensure failure if file does not exist
            self.cas = open(self.cas_name, 'r+b')
        except IOError:
            self.cas = open(self.cas_name, 'wb')
            self.write_intro()
            self.cas.close()
            self.cas = open(self.cas_name, 'r+b')
            self.cas.seek(0, 2)

    def eject(self):
        """ Close tape image. """
        # ensure any buffered bits are written
        Tapestream.eject(self)
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
            self.cas.write(chr(self.current_byte))
            self.mask = 0x80
        self.current_byte |= bit * self.mask

    def write_pause(self, milliseconds):
        """ Write pause to tape image (dummy). """
        pass

    def flush_bit_buffer(self):
        """ Write remaining bits to tape. """
        if self.operating_mode == 'rec':
            # flush bits in write buffer
            # pad with zero if necessary to align on byte limit
            self.cas.write(self.current_byte)

#######################################



class WAVStream(TapeStream):
    """ WAV-file cassette image reader. """

    def __init__(self, filename):
        """ Initialise WAV-file for reading. """
        TapeStream.__init__(self)
        self.wav_pos = 0
        self.buf_len = 1024
        self.wav = wave.open(filename, 'rb')
        self.nchannels =  self.wav.getnchannels()
        self.sampwidth = self.wav.getsampwidth()
        self.framerate = self.wav.getframerate()
        nframes = self.wav.getnframes()
        # convert 8-bit and 16-bit values to ints
        int_max = 1 << (self.sampwidth*8)
        if self.sampwidth == 1:
            self.sub_threshold = 0
            self.subtractor = 128*self.nchannels
        else:
            self.sub_threshold = int_max*self.nchannels/2
            self.subtractor =  int_max*self.nchannels
        # volume above/below zero that is interpreted as zero
        self.zero_threshold = int_max*self.nchannels/256 # 128 #64
        if self.sampwidth > 3:
            raise UnsupportedFormat()
        self.conv_format = '<' + {1:'B', 2:'h'}[self.sampwidth]*self.nchannels*self.buf_len
        # 1000 us for 1, 500 us for 0; threshold for half-pulse (500 us, 250 us)
        self.length_cut = 375*self.framerate/1000000
        self.length_max = 2*self.length_cut
        self.length_min = self.length_cut / 2
        # 2048 halves = 1024 pulses = 512 1-bits = 64 bytes of leader
        self.min_leader_halves = 2048
        # initialise generators
        #self.lowpass = butterworth(self.framerate, 3000)
        self.lowpass = butterband4(self.framerate, 500, 3000)
        #self.lowpass = butterband_sox(self.framerate, 1500, 1000)
        self.lowpass.send(None)
        self.read_half = self.gen_read_halfpulse()
        self.read_bit = self.gen_read_bit()

    def stamp(self):
        """ Time stamp. """
        return "[%d:%02d:%02d] " % hms(self.wav_pos/self.framerate)

    def read_buffer(self):
        """ Fill buffer with frames and pre-process. """
        frame_buf = []
        frames = self.wav.readframes(self.buf_len)
        # convert bytes into ints (little-endian if 16 bit)
        try:
            frames2 = struct.unpack(self.conv_format, frames)
        except struct.error:
            if not frames:
                raise EOF
            frames2 = struct.unpack(self.conv_format[:len(frames)//self.sampwidth+1], frames)
        # sum frames over channels
        frames3 = map(sum, zip(*[iter(frames2)]*self.nchannels))
        frames4 = [ x-self.subtractor if x >= self.sub_threshold else x for x in frames3 ]
        return self.lowpass.send(frames4)

    def gen_read_halfpulse(self):
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
                frame_buf = self.read_buffer()
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

    def gen_read_bit(self):
        """ Generator to yield the next bit. """
        while True:
            length_up, length_dn = self.read_half.next(), self.read_half.next()
            if (length_up > self.length_max or length_dn > self.length_max or
                    length_up < self.length_min or length_dn < self.length_min):
                yield None
            elif length_up >= self.length_cut:
                yield 1
            else:
                yield 0
        
    def eject(self):
        """ Close WAV-file. """
        TapeStream.eject(self)
        self.wav.close()


#class WAVWriter(TapeWriter):
#    """ WAV-file recording interface. """

#    def __init__(self, filename):
#        """ Initialise WAV tape image writer. """
#        TapeWriter.__init__(self)
#        self.create(filename)

#    def create(self, filename):
#        """ Create or overwrite WAV tape image. """
#        self.framerate = 22050
#        self.sampwidth = 1
#        self.halflength = [250*self.framerate/1000000, 500*self.framerate/1000000]
#        # create/overwrite file
#        self.wav = wave.open(filename, 'wb')
#        self.wav.setnchannels(1)
#        self.wav.setsampwidth(1)
#        self.wav.setframerate(self.framerate)
#        self.write_intro()

#    def write_pulse(self, half_length):
#        """ Write a single full pulse to the tape. """
#        self.wav.writeframesraw('\x00' * half_length + '\xff' * half_length)

#    def write_pause(self, milliseconds):
#        """ Write a pause of given length to the tape. """
#        self.wav.writeframesraw('\x7f' * (milliseconds * self.framerate / 1000))

#    def gen_write_bit(self):
#        """ Generator to write a bit to tape. """
#        while True:
#            bit = yield
#            self.write_pulse(self.halflength[bit])

#    def close(self):
#        """ Close WAV tape image. """
#        self.wav.close()



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

    def gen_read_bit(self):
        """ Generator to yield the next bit. """
        while True:
            pulse0 = (self.read_half.next(), self.read_half.next())
            # one = two pulses of 417 us; zero = one pulse of 833 us
            if sum(pulse0) < self.length_cut:
                pulse1 = (self.read_half.next(), self.read_half.next())
                if sum(pulse1) < self.length_cut:
                    yield 1
                else:
                    yield None
            else:
                yield 0

    def read_byte(self, skip_start=False):
        """ Read a byte from the tape. """
        if skip_start:
            start = 0
        else:
            start = self.read_bit.next()
        byte = 0
        bits = [ self.read_bit.next() for _ in xrange(8) ]
        if self.dropbit == 1 and self.last_error_bit == 0 and bits[-2:] == [1, 1]:
            # error-correcting: have we gone one too far?
            stop0, stop1 = bits[-2:]
            bits = [self.dropbit, start] + bits[:-2]
            start = self.last_error_bit
        elif self.dropbit == 0 and bits[-1] == 1:
            # error-correcting: keep dropbit
            stop0, stop1 = bits[-1], self.read_bit.next()
            bits = [start] + bits[:-1]
            start = self.dropbit
        else:
            # normal case, no error last time
            # or can't find a working correction
            stop0 = self.read_bit.next()
            stop1 = self.read_bit.next()
        if start == 1 or stop0 == 0 or stop1 == 0:
            self.last_error_bit = stop1
            # incorrect start/stop bit, try to recover by shifting
            self.dropbit = self.read_bit.next()
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
        msgstream.write_line("BASICODE.A Found." % (file_trunk + '.' + file_ext))
        logging.debug(self.stamp() + "BASICODE.A Found.")
        return 'BASICODE', 'A', 0, 0, 0

    def read_file(self, file_type='D', file_bytes=0):
        """ Read a file from tape. """
        if file_type not in ('D', 'A'):
            raise UnsupportedType()
        data = ''
        # xor sum includes STX byte
        checksum = 0x02
        while True:
            try:
                byte = self.read_byte()
            except (PulseError, FramingError) as e:
                logging.warning(self.stamp() + "%d %s" % (self.wav_pos, str(e)))
                # insert a zero byte as a marker for the error
                byte = 0
            except EOF as e:
                logging.warning(self.stamp() + "%d %s" % (self.wav_pos, str(e)))
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
        except (PulseError, FrameError, EOF) as e:
            logging.warning(self.stamp() + "Could not read checksum: %s " % str(e))
        # checksum shld be 0 for even # bytes, 128 for odd
        if checksum_byte == None or checksum^checksum_byte not in (0,128):
            logging.warning(self.stamp() + "Checksum: [FAIL]  Required: %02x  Realised: %02x" % (checksum_byte, checksum))
        else:
            logging.warning(self.stamp() + "Checksum: [ ok ] ")
        return data

    def read_leader(self):
        """ Read the leader / pilot wave. """
        while True:
            while self.read_bit.next() != 1:
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
                        logging.warning(self.stamp() + "Incorrect sync byte: %02x" % sync)
                except (PulseError, FramingError) as e:
                    logging.warning(self.stamp() + "Error in sync byte: %s" % str(e))




