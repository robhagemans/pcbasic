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
import string
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
# Exceptions

class CassetteIOError(IOError): pass
class EndOfTape(CassetteIOError): pass
class CRCError(CassetteIOError): pass
class PulseError(CassetteIOError): pass
class FramingError(CassetteIOError): pass


#################################################################################
# Cassette device

class CASDevice(object):
    """ Cassette tape device (CASn:) """

    def __init__(self, arg):
        """ Initialise tape device. """
        addr, val = iolayer.parse_protocol_string(arg)
        ext = val.split('.')[-1].upper()
        try:
            if not val:
                self.tapestream = None
            elif addr == 'BC':
                self.tapestream = BasicodeStream(BasicodeWAVBitStream(val, 'r'))
            elif addr == 'WAV' or (addr != 'CAS' and ext == 'WAV'):
                # if unspecified, determine type on the basis of filename extension
                self.tapestream = CassetteStream(WAVBitStream(val, 'r'))
            else:
                # 'CAS' is default
                self.tapestream = CassetteStream(CASBitStream(val, 'r'))
        except EnvironmentError as e:
            logging.warning("Couldn't attach %s to CAS device: %s",
                            val, str(e))
            self.tapestream = None

    def close(self):
        """ Close tape device. """
        if self.tapestream:
            self.tapestream.close_tape()

    def open(self, number, param, filetype, mode, access, lock,
                   reclen, seg, offset, length):
        """ Open a file on tape. """
        if not self.tapestream:
            # device unavailable
            raise error.RunError(68)
        if self.tapestream.is_open:
            # file already open
            raise error.RunError(55)
        if mode == 'O':
            self.tapestream.open_write(param, filetype, seg, offset, length)
        elif mode == 'I':
            _, filetype, seg, offset, length = self._search(param, filetype)
        else:
            raise error.RunError(54)
        if filetype in ('D', 'A'):
            return CASTextFile(self.tapestream, filetype, mode)
        else:
            return CASBinaryFile(self.tapestream, filetype, mode, seg, offset, length)

    def _search(self, trunk_req=None, filetypes_req=None):
        """ Play until a file header record is found for the given filename. """
        try:
            while True:
                trunk, filetype, seg, offset, length = self.tapestream.open_read()
                if ((not trunk_req or trunk.rstrip() == trunk_req.rstrip()) and
                        (not filetypes_req or filetype in filetypes_req)):
                    message = "%s Found." % (trunk + '.' + filetype)
                    msgstream.write_line(message)
                    logging.debug(timestamp(self.tapestream.counter()) + message)
                    return trunk, filetype, seg, offset, length
                else:
                    message = "%s Skipped." % (trunk + '.' + filetype)
                    msgstream.write_line(message)
                    logging.debug(timestamp(self.tapestream.counter()) + message)
        except EndOfTape:
            # reached end-of-tape without finding appropriate file
            # device timeout
            raise error.RunError(24)

#################################################################################
# Cassette files

class CASBinaryFile(iolayer.RawFile):
    """ Program or Memory file on CASn: device. """

    def __init__(self, fhandle, filetype, mode, seg, offset, length):
        """ Initialise binary file. """
        iolayer.RawFile.__init__(self, fhandle, filetype, mode)
        self.seg, self.offset, self.length = seg, offset, length

    def read_raw(self, nbytes=-1):
        """ Read bytes from a file on tape. """
        try:
            return iolayer.RawFile.read_raw(self, nbytes)
        except CassetteIOError as e:
            logging.warning("%s Cassette I/O Error during read: %s",
                            timestamp(self.fhandle.counter()), e)
            # Device I/O error
            raise error.RunError(57)


class CASTextFile(iolayer.TextFileBase):
    """ Text file on CASn: device. """

    def lof(self):
        """ LOF: illegal function call. """
        raise error.RunError(5)

    def loc(self):
        """ LOC: illegal function call. """
        raise error.RunError(5)

    def read_raw(self, nbytes=-1):
        """ Read bytes from a file on tape. """
        try:
            return iolayer.TextFileBase.read_raw(self, nbytes)
        except CassetteIOError as e:
            logging.warning("%s Cassette I/O Error during read: %s",
                            timestamp(self.fhandle.counter()), e)
            # Device I/O error
            raise error.RunError(57)

    def close(self):
        """ Close a file on tape. """
        # terminate cassette text files with NUL
        if self.mode == 'O':
            self.write('\0')
        iolayer.TextFileBase.close(self)


class CassetteStream(object):
    """ Byte stream on CASn: device. """

    def __init__(self, bitstream):
        """ Initialise file on tape. """
        self.bitstream = bitstream
        # is a file open on this stream?
        self.is_open = False
        # keep track of last seg, offs, length to reproduce GW-BASIC oddity
        self.last = 0, 0, 0
        self.buffer_complete = False
        self.length = 0
        self.filetype = ''
        self.rwmode = ''

    def close(self):
        """ Finalise the track on the tape stream. """
        if self.is_open:
            self._close_record_buffer()
            self.is_open = False

    def flush(self):
        pass

    def close_tape(self):
        """ Eject the tape. """
        self.close()
        self.bitstream.close()

    def counter(self):
        """ Position on tape in seconds. """
        return self.bitstream.counter()

    def write(self, c):
        """ Write a string to a file on tape. """
        self.record_stream.write(c)
        self._flush_record_buffer()

    def read(self, nbytes=-1):
        """ Read bytes from a file on tape. """
        c = ''
        try:
            while True:
                if nbytes > -1:
                    c += self.record_stream.read(nbytes-len(c))
                    if len(c) >= nbytes:
                        return c
                else:
                    c += self.record_stream.read()
                if self.buffer_complete:
                    return c
                self._fill_record_buffer()
        except EndOfTape:
            return c

    def open_read(self):
        """ Play until a file header record is found. """
        self.record_num = 0
        self.record_stream = StringIO()
        self.buffer_complete = False
        self.bitstream.switch_mode('r')
        self.rwmode = 'r'
        while True:
            record = self._read_record(None)
            if record and record[0] == '\xa5':
                break
            else:
                # unknown record type
                logging.debug("%s Skipped non-header record.",
                              timestamp(self.bitstream.counter()))
        file_trunk = record[1:9]
        try:
            self.filetype = token_to_type[ord(record[9])]
        except KeyError:
            logging.debug('Unknown file type token: %x', ord(record[9]))
        self.length = ord(record[10]) + ord(record[11]) * 0x100
        # for programs this is start address
        seg = ord(record[12]) + ord(record[13]) * 0x100
        offset = ord(record[14]) + ord(record[15]) * 0x100
        self.record_num = 0
        self.buffer_complete = False
        self.is_open = True
        return file_trunk, self.filetype, seg, offset, self.length

    def open_write(self, name, filetype, seg, offs, length):
        """ Write a file header to the tape. """
        self.record_num = 0
        self.record_stream = StringIO()
        self.buffer_complete = False
        self.bitstream.switch_mode('w')
        self.rwmode = 'w'
        if filetype in ('A', 'D'):
            # ASCII program files: length, seg, offset are untouched,
            # remain that of the previous file recorded!
            seg, offs, length = self.last
        else:
            self.last = seg, offs, length
        self.filetype = filetype
        # header seems to end at 0x00, 0x01, then filled out with last char
        header = ('\xa5' + name[:8] + ' ' * (8-len(name))
                  + chr(type_to_token[filetype]) +
                  ''.join(map(chr, word_le(length))) +
                  ''.join(map(chr, word_le(seg))) +
                  ''.join(map(chr, word_le(offs))) +
                  '\x00\x01')
        self._write_record(header)
        self.is_open = True

    def _read_record(self, reclen):
        """ Read a record from tape. """
        if not self.bitstream.read_leader():
            # reached end-of-tape without finding appropriate file
            raise EndOfTape()
        self.record_num += 1
        record = ''
        block_num = 0
        byte_count = 0
        while byte_count < reclen or reclen == None:
            data = self._read_block()
            record += data
            byte_count += len(data)
            if (reclen == None):
                break
            block_num += 1
        self.bitstream.read_trailer()
        if reclen != None:
            return record[:reclen]
        return record

    def _write_record(self, data):
        """ Write a data record to tape. """
        self.bitstream.write_leader()
        while len(data) > 0:
            self._write_block(data[:256])
            data = data[256:]
        self.bitstream.write_trailer()
        # write 100 ms second pause to make clear separation between blocks
        self.bitstream.write_pause(100)

    def _read_block(self):
        """ Read a block of data from tape. """
        count = 0
        data = ''
        while True:
            if count == 256:
                break
            byte = self.bitstream.read_byte()
            if byte == None:
                raise PulseError()
            data += chr(byte)
            count += 1
        bytes0, bytes1 = self.bitstream.read_byte(), self.bitstream.read_byte()
        crc_given = bytes0 * 0x100 + bytes1
        crc_calc = crc(data)
        # if crc for either polarity matches, return that
        if crc_given == crc_calc:
            return data
        raise CRCError("CRC check failed, required: %04x realised: %04x" %
                        (crc_given, crc_calc))

    def _write_block(self, data):
        """ Write a 256-byte block to tape. """
        # fill out short blocks with last byte
        data += data[-1]*(256-len(data))
        for b in data:
            self.bitstream.write_byte(ord(b))
        crc_word = crc(data)
        # crc is written big-endian
        lo, hi = word_le(crc_word)
        self.bitstream.write_byte(hi)
        self.bitstream.write_byte(lo)

    def _fill_record_buffer(self):
        """ Read to fill the tape buffer. """
        if self.buffer_complete:
            return False
        if self.filetype in ('M', 'B', 'P'):
            # bsave, tokenised and protected come in one multi-block record
            self.record_stream = StringIO()
            self.record_stream.write(self._read_record(self.length))
            self.buffer_complete = True
        else:
            # ascii and data come as a sequence of one-block records
            # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
            self.record_stream = StringIO()
            record = self._read_record(256)
            num_bytes = ord(record[0])
            record = record[1:]
            if num_bytes != 0:
                record = record[:num_bytes-1]
                self.buffer_complete = True
            self.record_stream.write(record)
        self.record_stream.seek(0)
        return True

    def _flush_record_buffer(self):
        """ Write the tape buffer to tape. """
        if self.filetype not in ('M', 'B', 'P') and self.rwmode == 'w':
            data = self.record_stream.getvalue()
            while True:
                if len(data) < 255:
                    break
                chunk, data = data[:255], data[255:]
                # ascii and data come as a sequence of one-block records
                # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
                self._write_record('\0' + chunk)
            self.record_stream = StringIO()
            self.record_stream.write(data)
            self.record_stream.seek(0, 2)

    def _close_record_buffer(self):
        """ Write the tape buffer to tape and finalise. """
        if self.rwmode == 'w':
            self._flush_record_buffer()
            self.buffer_complete = True
            data = self.record_stream.getvalue()
            if self.filetype in ('M', 'B', 'P'):
                # bsave, tokenised and protected come in one multi-block record
                self._write_record(data)
            else:
                if data:
                    self._write_record(chr(len(data)) + data)
        self.record_stream = StringIO()



class BasicodeStream(CassetteStream):
    """ BASICODE-format byte stream on cassette. """

    # basicode-3 recognised keywords
    keywords = ['PRINT', 'INPUT', 'LET', 'GOTO', 'GOSUB', 'RETURN', 'FOR', 'TO',
        'STEP', 'NEXT', 'IF', 'THEN', 'ON', 'DIM', 'READ', 'DATA', 'RESTORE',
        'REM', 'DEF', 'FN', 'ABS', 'SGN', 'INT', 'SQR', 'SIN', 'COS',
        'TAN', 'ATN', 'EXP', 'LOG', 'ASC', 'VAL', 'LEN', 'CHR$', 'LEFT$', 'MID$',
        'RIGHT$', 'AND', 'OR', 'NOT']
    # TAB is recognised but does not get an extra space

    def open_read(self):
        """ Play until a file record is found. """
        if not self.bitstream.read_leader():
            # reached end-of-tape without finding appropriate file
            raise EndOfTape()
        self.filetype = 'A'
        self.record_num = 0
        return '', 'A', 0, 0, 0

    def _fill_record_buffer(self):
        """ Read a file from tape. """
        if self.record_num > 0:
            return False
        self.record_num += 1
        self.record_stream = StringIO()
        # xor sum includes STX byte
        checksum = 0x02
        word = ''
        is_rem, is_str = False, False
        while True:
            try:
                byte = self.bitstream.read_byte()
            except (PulseError, FramingError) as e:
                logging.warning("%s Cassette I/O error during read: %s",
                                timestamp(self.bitstream.counter()), e)
                # insert a zero byte as a marker for the error
                byte = 0
            except EndOfTape as e:
                logging.warning("%s Cassette I/O error during read: %s",
                                timestamp(self.bitstream.counter()), e)
                break
            checksum ^= byte
            if byte == 0x03:
                break
            c = chr(byte)
            self.record_stream.write(c)
            # CR -> CRLF
            if byte == 0x0d:
                self.record_stream.write('\n')
                is_rem, is_str = False, False
                word = ''
            # add space to keywords
            if c not in string.ascii_uppercase:
                word = ''
                if c == '"':
                    is_str = not is_str
            elif not is_rem and not is_str:
                word += c
                if word in self.keywords:
                    self.record_stream.write(' ')
                    if word == 'REM':
                        is_rem = True
                    word = ''
        # read one-byte checksum and report errors
        try:
            checksum_byte = self.bitstream.read_byte()
        except (PulseError, FramingError, EndOfTape) as e:
            logging.warning("%s, Could not read checksum: %s",
                            timestamp(self.bitstream.counter()), e)
        # checksum shld be 0 for even # bytes, 128 for odd
        if checksum_byte == None or checksum^checksum_byte not in (0,128):
            logging.warning("%s Checksum failed, required: %02x realised: %02x",
                            timestamp(self.bitstream.counter()),
                            checksum_byte, checksum)
        self.record_stream.seek(0)
        self.bitstream.read_trailer()
        return True

    def _flush_record_buffer(self):
        """ Write the tape buffer to tape. """
        pass

    def _close_record_buffer(self):
        """ Write the tape buffer to tape and finalise. """
        pass


##############################################################################


class TapeBitStream(object):
    """ Cassette tape bitstream interface. """

    # sync byte for IBM PC tapes
    sync_byte = 0x16
    # intro text
    intro = 'PC-BASIC tape\x1a'

    def __init__(self, mode='r'):
        """ Initialise tape interface. """
        pass

    def __enter__(self):
        """ Context guard. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Context guard. """
        self.close()

    def counter(self):
        """ Position on tape in seconds. """
        return 0

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
        try:
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
                        return True
        except EndOfTape:
            return False

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
                raise PulseError()
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

    def read_trailer(self):
        """ Read the trailing wave """
        try:
            while self.read_bit() == 1:
                pass
        except EndOfTape:
            pass

    def write_trailer(self):
        """ Write trailing wave. """
        # closing sequence is 30 1-bits followed by a zero bit (based on PCE output).
        # Not 32 1-bits as per http://fileformats.archiveteam.org/wiki/IBM_PC_data_
        for _ in range(30):
            self.write_bit(1)
        self.write_bit(0)

##############################################################################


class CASBitStream(TapeBitStream):
    """ CAS-file cassette image bit stream. """

    def __init__(self, image_name, mode):
        """ Initialise CAS-file. """
        TapeBitStream.__init__(self)
        # 'r' or 'w'
        self.cas_name = image_name
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
                raise EndOfTape
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



# http://www.topherlee.com/software/pcm-tut-wavformat.html
# The header of a WAV (RIFF) file is 44 bytes long and has the following format:

#    Positions	Sample Value	Description
#    1 - 4	"RIFF"	Marks the file as a riff file. Characters are each 1 byte long.
#    5 - 8	File size (integer)	Size of the overall file - 8 bytes, in bytes (32-bit integer). Typically, you'd fill this in after creation.
#    9 -12	"WAVE"	File Type Header. For our purposes, it always equals "WAVE".
#    13-16	"fmt "	Format chunk marker. Includes trailing null
#    17-20	16	Length of format data as listed above
#    21-22	1	Type of format (1 is PCM) - 2 byte integer
#    23-24	2	Number of Channels - 2 byte integer
#    25-28	44100	Sample Rate - 32 byte integer. Common values are 44100 (CD), 48000 (DAT). Sample Rate = Number of Samples per second, or Hertz.
#    29-32	176400	(Sample Rate * BitsPerSample * Channels) / 8.
#    33-34	4	(BitsPerSample * Channels) / 8.1 - 8 bit mono2 - 8 bit stereo/16 bit mono4 - 16 bit stereo
#    35-36	16	Bits per sample
#    37-40	"data"	"data" chunk header. Marks the beginning of the data section.
#    41-44	File size (data)	Size of the data section.
#    Sample values are given above for a 16-bit stereo source.

# data section consists of little-endian PCM audio data
# each sample consists of nchannels*samplewidth bytes


# pc cassette technical docs
# http://en.wikipedia.org/wiki/IBM_cassette_tape
# http://www.vintage-computer.com/vcforum/showthread.php?8829-IBM-PC-Cassette-interface/page2


# http://fileformats.archiveteam.org/wiki/IBM_PC_data_cassette
# The format consists of 1-millisecond-long pulses for each 1 bit, and
# 0.5-millisecond pulses for each 0 bit. A tape record starts with a leader
# of 256 bytes of all 1 bits (hex FF), followed by a single synchronization
# bit (0), and then a synchronization byte (hex 16, the ASCII character from
# the C0 controls designated as SYN). This is followed by one or more 256-byte
# data blocks. Each data block is followed by a 2-byte CRC, with the most
# significant byte first. After the last block, a 4-byte trailer is written
# of all 1 bits (hex FF).
#
# NOTE that the trailer consists of 30 1 bits and a 0 bit, not 32 1-bits as described here.

# Tokenised BASIC programs and memory areas saved by IBM Cassette BASIC consist
# of two records: the first one is a header (always 256 bytes, of which the
# first 16 are significant), and the second one contains the data.
# ASCII listings and data files consist of a sequence of 256-byte records; the
# first one is a header, as above, and subsequent ones contain the data. If
# the first byte of the record is 0, this is not the last record, and all 255
# following bytes are valid data. Otherwise it gives the number of valid bytes
# in the last record, plus one.
# The header layout is:
# Offset	Size	Description
# 0x00	Byte	Always 0xA5
# 0x01	8 bytes	Filename, ASCII
# 0x09	Byte	Flags:
# Bit	Meaning if set	Example command to create
# 7	Tokenised BASIC	SAVE "file"
# 6	ASCII listing	SAVE "file", A
# 5	Protected tokenised BASIC	SAVE "file", P
# 0	Memory area	BSAVE "file", address, length
# No bits set	Data	OPEN "O",1,"file"
# 0x0A	Word	Number of bytes in the following data record (little-endian word)
# 0x0C	Word	Segment of load address (little-endian word)
# 0x0E	Word	Offset of load address (little-endian word)




class WAVBitStream(TapeBitStream):
    """ WAV-file cassette image bit stream. """

    def __init__(self, filename, mode):
        """ Initialise WAV-file. """
        TapeBitStream.__init__(self)
        self.filename = filename
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

    def switch_mode(self, mode):
        """ Switch tape to reading or writing mode. """
        self.operating_mode = mode

    def counter(self):
        """ Time stamp in seconds. """
        return self.wav_pos/(1.*self.framerate)

    def read_bit(self):
        """ Read the next bit. """
        try:
            length_up, length_dn = next(self.read_half), next(self.read_half)
        except StopIteration:
            raise EndOfTape
        if (length_up > self.halflength_max or length_dn > self.halflength_max or
                length_up < self.halflength_min or length_dn < self.halflength_min):
            return None
        elif length_up >= self.halflength_cut:
            return 1
        else:
            return 0

    def close(self):
        """ Close WAV-file. """
        TapeBitStream.close(self)
        # write file length fields
        self.wav.seek(0, 2)
        end_pos = self.wav.tell()
        self.wav.seek(self.riff_pos, 0)
        self.wav.write(struct.pack('<4sL', 'RIFF', end_pos-self.riff_pos-8))
        self.wav.seek(self.data_pos, 0)
        self.wav.write(struct.pack('<4sL', 'data', end_pos-self.start))
        self.wav.close()

    def _fill_buffer(self):
        """ Fill buffer with frames and pre-process. """
        frame_buf = []
        frames = self.wav.read(self.buf_len*self.nchannels*self.sampwidth)
        if not frames:
            raise EndOfTape
        # convert MSBs to int (data stored little endian)
        # note that we simply throw away all the less significant bytes
        frames = map(ord, frames[self.sampwidth-1::self.sampwidth])
        # sum frames over channels
        frames = map(sum, zip(*[iter(frames)]*self.nchannels))
        frames = [ x-self.subtractor if x >= self.sub_threshold else x for x in frames ]
        return self.lowpass.send(frames)

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
        # this would normally be 0
        self.riff_pos = self.wav.tell() - 12
        riff_size = ch.getsize()
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
                self.data_pos = self.wav.tell() - 4
                #self.wav.read(4)
                self.start = self.wav.tell()
                return True
            chunk.skip()

    def _write_wav_header(self):
        """ Write RIFF WAV header. """
        # "RIFF" chunk header
        self.riff_pos = self.wav.tell()
        # length is corrected at close
        self.wav.write(struct.pack('<4sL4s', 'RIFF', 36, 'WAVE'))
        # "fmt " subchunk
        self.wav.write(struct.pack('<4sLHHLLHH', 'fmt ', 16,
            1, self.nchannels, self.framerate,
            self.nchannels * self.framerate * self.sampwidth,
            self.nchannels * self.sampwidth,
            self.sampwidth * 8))
        # "data" subchunk header
        self.data_pos = self.wav.tell()
        # length is corrected at close
        self.wav.write(struct.pack('<4sL', 'data', 0))
        self.start = self.wav.tell()

    def _is_leader_halfpulse(self, half):
        """ Return whether the half pulse is of pilot wave frequency. """
        return half >= self.length_cut/2

    def read_leader(self):
        """ Read the leader / pilot wave. """
        try:
            while True:
                while self.read_bit() != 1:
                    pass
                counter = 0
                pulse = (0,0)
                while True:
                    last = pulse
                    half = next(self.read_half)
                    if not self._is_leader_halfpulse(half):
                        if counter > self.min_leader_halves:
                            #  zero bit; try to sync
                            half = next(self.read_half)
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
                            return True
                        else:
                            logging.debug("%s Incorrect sync byte after %d pulses: %02x",
                                          timestamp(self.counter()), counter, sync)
                    except (PulseError, FramingError) as e:
                        logging.debug("%s Error in sync byte after %d pulses: %s",
                                      timestamp(self.counter()), counter, e)
        except (EndOfTape, StopIteration):
            return False

##############################################################################


# http://en.wikipedia.org/wiki/BASICODE
# A data block begins with the character 02 (STX, start of text), and ends with
# the character 03 (ETX, end of text). After ETX, a check byte made up of the
# previous bytes including STX and ETX by binary addition (XOR), is transmitted.
# A 0D character (decimal 13) marks the end of a line during transmission.
# Data files created by programs are able to use all characters as data and
# must contain no control characters. They are read and written in blocks
# of 1024 bytes.

# Each byte is transmitted in the sequence "1 start bit - 8 data bits - 2 stop
# bits". The data bits are little-endian ordered. The resulting redundancy is
# intended for maximising compatibility with different computers. Bit 7 is
# always 0, which is especially useful when transmitting ASCII characters,
# because these always have bit 7 set to 0.

# For the audio signals, square waves in the form of a 1200 Hz wave for a "0"
# bit and two 2400 Hz waves for a "1" bit are used, resulting in a time of
# 1/1200 seconds for each bit. A pause longer than 1/1800 seconds between
# waves marks the beginning of a byte, making the following wave the start
# bit. After the start bit and before the eight data bits is another pause of
# at least 1/1800 seconds. A 2400 Hz signal with a length of five seconds
# marks the beginning of a transmission and is used for synchronization of
# the reading program. At the end of the transmission, a 2400 Hz signal with
# a length of one second is sent.


# NOTE
# In actual recordings I find no 1/1800s pauses.
# Start and stop bits are 1. Bit 7 is inverted, hence 1 for ASCII chars.


# http://www.nostalgia8.nl/basicode.htm
# Het Basicode Protocol:
# 1200 baud / 8 data bit / 2 stop bit

#     Aanlooptoon
#     Startbyte ASCII 130 (10000010)
#     BASIC informatie
#     (Bit nummer 7 is bij Basicode altijd 1 in plaats van de eigenlijke 0)
#     Stopbyte ASCII 131 (10000011)
#     Checksum byte
#     Uitlooptoon

# De data in een Basicode file bestaat uit de 'schone' ASCII  karakters van
# Hex 20 (31 decimaal)  t/m Hex 7E (126 decimaal). De tekstregels worden
# afgesloten met Hex 0D (13 decimaal = ASCII code carriage return).

# Bij de omvorming naar AUDIO signalen wordt bit 7 (normaal 0) veranderd in
# een 1 (geinverteerd).



class BasicodeWAVBitStream(WAVBitStream):
    """ BASICODE-standard WAV image reader. """

    def __init__(self, filename, mode):
        """ Initialise BASICODE WAV-file reader. """
        WAVBitStream.__init__(self, filename, mode)
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
        try:
            pulse0 = (next(self.read_half), next(self.read_half))
            # one = two pulses of 417 us; zero = one pulse of 833 us
            if sum(pulse0) < self.length_cut:
                pulse1 = (next(self.read_half), next(self.read_half))
                if sum(pulse1) < self.length_cut:
                    return 1
                else:
                    return None
            else:
                return 0
        except StopIteration:
            raise EndOfTape

    def write_bit(self, bit):
        """ BASICODE writing not yet supported. """
        pass

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
            raise FramingError(
                "Byte not framed: %s " % ([start] + bits + [stop0, stop1]))
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

    def _is_leader_halfpulse(self, half):
        """ Return whether the half pulse is of pilot wave frequency. """
        return half <= self.length_cut/2


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
# see e.g. http://www.exstrom.com/journal/sigproc/


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
