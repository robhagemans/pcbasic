import wave
import math
import struct

token_to_ext = {0: 'D', 1:'M', 0xa0:'P', 0x20:'P', 0x40:'A', 0x80:'B'}
token_to_magic = {0: '', 1:'\xfd', 0xa0:'\xfe', 0x20:'\xfe', 0x40:'', 0x80:'\xff'}
magic_to_token = {'\xfd': 1, '\xfe': 0xa0, '\xff': 0x80}


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
    """ Format not supported. """
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


class TapeReader(object):
    """ Cassette reading interface. """

    def __init__(self):
        """ Initialise tape readers. """
        self.sync_byte = 0x16

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
                bytes0, bytes1 = self.read_byte(), self.read_byte()
                crc_given = bytes0 * 0x100 + bytes1
                crc_calc = crc(data)
                # if crc for either polarity matches, return that
                if crc_given == crc_calc:
                    return data
                raise CRCError(crc_given, crc_calc)
            else:
                byte = self.read_byte()
                if byte == None:
                    raise PulseError()
                data += chr(byte)
                count += 1

    def read_record(self, reclen):
        """ Read a record from tape. """
        self.read_leader()
        record = ''
        self.block_num = 0
        byte_count = 0
        while byte_count < reclen or reclen == None:
            try:
                data = self.read_block()
            except (PulseError, FramingError, CRCError) as e:
                self.message("%d %s" % (self.wav_pos, str(e)))
            record += data
            byte_count += len(data)
            if (reclen == None and
                    (data[:4] == '\xff\xff\xff\xff' or
                    (self.block_num == 0 and data[0] == '\xa5'))):
                break
            self.block_num += 1
        if reclen != None:
            return record[:reclen]
        return record

    # TODO: optional name, as in LOAD"CAS1:" vs LOAD"CAS1:myfile"
    def read_file(self):
        """ Read a file from tape. """
        self.record_num = 0
        record = self.read_record(None)
        header = parse_header(record)
        if not header:
            # unknown record type
            self.message("File %d: Record of unknown type." % self.file_num)
            return 'DATA.X%02x' % self.file_num, record
        else:
            file_trunk, file_token, file_bytes, seg, offs = header
            file_ext = token_to_ext[file_token]
            self.message("File %d: %s Found." % (self.file_num, file_trunk + '.' + file_ext)),
            # for programs this is start address: cf to offset of next line in prgram
        file_name = file_trunk.rstrip() + '.' + file_ext + '%02x' % self.file_num
        data = token_to_magic[file_token]
        if file_token == 0x01:
            # bsave format: paste in 6-byte header for disk files
            data += ''.join(map(chr, word_le(seg)))
            data += ''.join(map(chr, word_le(offs)))
            data += ''.join(map(chr, word_le(file_bytes)))
        if file_token in (1, 0x80, 0x20, 0xa0):
            self.record_num += 1
            # bsave, tokenised and protected come in one multi-block record
            data += self.read_record(file_bytes)
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            while True:
                self.record_num += 1
                record = self.read_record(256)
                num_bytes = ord(record[0])
                record = record[1:]
                if num_bytes != 0:
                    record = record[:num_bytes-1]
                data += record
                if num_bytes != 0:
                    break
        # write EOF char
        data += '\x1a'
        self.message("End of File %d" % self.file_num)
        return file_name, data

    #D
    def read_tape(self):
        """ Read all files from tape. """
        # start parsing
        self.file_num = 0
        while True:
            try:
                file_name, data = self.read_file()
                with open(file_name, 'wb') as f:
                    f.write(str(bytearray(data)))
                self.file_num += 1
            except EOF:
                break

    def __enter__(self):
        """ Context guard for 'with'. """
        return self

    def __exit__(self, type, value, traceback):
        """ Context guard for 'with'. """
        self.close()


class WAVReader(TapeReader):
    """ WAV-file cassette image reader. """

    def __init__(self, filename):
        """ Initialise WAV-file for reading. """
        TapeReader.__init__(self)
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

    def message(self, msg):
        """ Output a message. """
        print "[%d:%02d:%02d]" % hms(self.wav_pos/self.framerate),
        print msg

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
        
    def close(self):
        """ Close WAV-file. """
        self.wav.close()


class BasicodeReader(WAVReader):
    """ BASICODE-standard WAV image reader. """

    def __init__(self, filename):
        """ Initialise BASICODE WAV-file reader. """
        WAVReader.__init__(self, filename)
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

    def read_file(self):
        """ Read a file from tape. """
        self.read_leader()
        self.message("Found File %d" % self.file_num)
        data = ''
        # xor sum includes STX byte
        checksum = 0x02
        while True:
            try:
                byte = self.read_byte()
            except (PulseError, FramingError) as e:
                self.message("%d %s" % (self.wav_pos, str(e)))
                # insert a zero byte as a marker for the error
                byte = 0
            except EOF as e:
                self.message("%d %s" % (self.wav_pos, str(e)))
                break
            checksum ^= byte
            if byte == 0x03:
                try:
                    checksum_byte = self.read_byte()
                except (PulseError, FrameError, EOF) as e:
                    self.message("Could not read checksum: %s " % str(e))
                # checksum shld be 0 for even # bytes, 128 for odd
                if checksum_byte == None or checksum^checksum_byte not in (0,128):
                    self.message("Checksum: [FAIL]  Required: %02x  Realised: %02x" % (checksum_byte, checksum))
                else:
                    self.message("Checksum: [ ok ] ")
                break
            data += chr(byte)
            # CR -> CRLF
            if byte == 0x0d:
                data += '\n'
        # write EOF char
        data += '\x1a'
        return "FILE%04x.ASC" % self.file_num, data

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
                        self.message("Incorrect sync byte: %02x" % sync)
                except (PulseError, FramingError) as e:
                    self.message("Error in sync byte: %s" % str(e))


class CASReader(TapeReader):
    """ CAS-file cassette image reader. """

    def message(self, msg):
        """ Output a message. """
        print msg

    def gen_read_bit(self):
        """ Generator to yield the next bit. """
        cas_byte_read = 0
        cas_mask = 0
        while True:
            cas_mask >>= 1
            if cas_mask <= 0:
                cas_byte_read = self.cas.read(1)
                if not cas_byte_read:
                    raise EOF
                cas_mask = 0x80
            if (ord(cas_byte_read) & cas_mask == 0):
                yield 0
            else:
                yield 1


    def __init__(self, filename):
        """ Initialise CAS-file for reading. """
        TapeReader.__init__(self)
        self.read_bit = self.gen_read_bit()
        self.cas = open(filename, 'rb')

    def close(self):
        """ Close CAS-file. """
        self.cas.close()


#######################################

class TapeWriter(object):
    """ Cassette recording interface. """

    def write_byte(self, byte):
        """ Write a byte to WAV file. """
        bits = [ 1 if (byte & ( 128 >> i) != 0) else 0 for i in range(8) ]
        for bit in bits:
            self.write_bit.send(bit)

    def write_intro(self):
        """ write some noise to give the reader something to get started. """
        for b in bytearray('CAS1:'):
            self.write_byte(b)
        for _ in range(7):
            self.write_bit.send(0)
        self.write_pause(100)

    def write_leader(self):
        """ Write the leader / pilot tone. """
        for _ in range(256):
            self.write_byte(0xff)
        self.write_bit.send(0)
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
        self.write_byte(0xff)
        self.write_byte(0xff)
        self.write_byte(0xff)
        for b in (1,1,1,1,1,1,0):
            self.write_bit.send(b)
        # write 100 ms second pause to make clear separation between blocks
        self.write_pause(100)

    def write_file(self, name, token, data):
        """ Write a file to the tape. """
        if token == 0x01:
            # bsave 6-byte header is cut off (magic byte has been cut off before)
            seg = ord(data[0]) + ord(data[1])*0x100
            offs = ord(data[2]) + ord(data[3])*0x100
            length = ord(data[4]) + ord(data[5])*0x100
            data = data[6:6+length]
        elif token in (0x80, 0x20, 0xa0):
            # TODO: calculate seg and offs from program data, if program file
            # protected file? unprotect first 3 bytes & use values
            seg = 0x60
            offs = 0x81e
            bytes = len(data)
        else:
            # TODO: ASCII program files: length, seg, offset are untouched, remain that of the previous file recorded!
            seg, offs, bytes = 0, 0, 0
            # text files have CR line endings on tape, not CR LF
            # they should also get a NUL at the end
            data = data.replace('\r\n', '\r')
            data += '\0'
        self.write_record(header(name, token, bytes, seg, offs))
        if token in (1, 0x80, 0x20, 0xa0):
            # bsave, tokenised and protected come in one multi-block record
            self.write_record(data)
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            blocks, last = divmod(len(data), 255)
            for i in range(blocks):
                offset = i*255
                self.write_record('\0' + data[offset:offset+255])
            if last > 0:
                self.write_record(chr(last) + data[-last:])

    #D
    def write_tape(self, files):
        """ Write a list of files to the tape. """
        self.write_intro()
        # write files
        for file_name in files:
            name = file_name.split('.')[0][:8]
            print "Recording %s to cassette." % file_name
            with open(file_name, 'rb') as f:
                magic = f.read(1)
                data = f.read()
                # cut off EOF marker
                if data and data[-1] == '\x1a':
                    data = data[:-1]
                try:
                    token = magic_to_token[magic]
                except KeyError:
                    # could also be data file, need some other test (extension?)
                    token = 0x40
                    data = magic + data
                self.write_file(name, token, data)

    def __init__(self):
        """ Initilaise tape image. """
        self.write_bit = self.gen_write_bit()
        self.write_bit.send(None)

    def __enter__(self):
        """ Context guard for 'with'. """
        return self

    def __exit__(self, type, value, traceback):
        """ Context guard for 'with'. """
        self.close()


class WAVWriter(TapeWriter):
    """ WAV-file recording interface. """

    def write_pulse(self, half_length):
        """ Write a single full pulse to the tape. """
        self.wav.writeframesraw('\x00' * half_length + '\xff' * half_length)

    def write_pause(self, milliseconds):
        """ Write a pause of given length to the tape. """
        self.wav.writeframesraw('\x7f' * (milliseconds * self.framerate / 1000))

    def gen_write_bit(self):
        """ Generator to write a bit to tape. """
        while True:
            bit = yield
            self.write_pulse(self.halflength[bit])

    def __init__(self, filename):
        """ Initialise WAV tape image writer. """
        self.framerate = 22050
        self.sampwidth = 1
        self.wav = wave.open(filename, 'wb')
        self.wav.setnchannels(1)
        self.wav.setsampwidth(1)
        self.wav.setframerate(self.framerate)
        self.halflength = [250*self.framerate/1000000, 500*self.framerate/1000000]
        TapeWriter.__init__(self)

    def close(self):
        """ Close WAV tape image. """
        self.wav.close()


class CASWriter(TapeWriter):
    """ CAS-file recording interface. """

    def write_pause(self, milliseconds):
        """ Write pause to tape image (dummy). """
        pass

    def gen_write_bit(self):
        """ Generator to write a bit to tape. """
        count, byte = 0, 0
        while True:
            bit = yield
            byte = (byte << 1) | bit
            count += 1
            if count >= 8:
                self.cas.write(chr(byte))
                count, byte = 0, 0

    def __init__(self, filename):
        """ Initialise CAS tape image writer. """
        self.cas = open(filename, 'wb')
        TapeWriter.__init__(self)

    def close(self):
        """ Close CAS tape image. """
        # ensure any buffered bits are written
        self.write_byte(0xff)
        self.cas.close()
    

