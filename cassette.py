#!/usr/bin/env python2

import wave
import math
import sys
import struct
import cProfile
import sys

token_to_ext = {0: 'D', 1:'M', 0xa0:'P', 0x20:'P', 0x40:'A', 0x80:'B'}
token_to_magic = {0: '', 1:'\xfd', 0xa0:'\xfe', 0x20:'\xfe', 0x40:'', 0x80:'\xff'}
magic_to_token = {'\xfd': 1, '\xfe': 0xa0, '\xff': 0x80}


#############################

def warning(msg):
    print "[%d:%02d:%02d]" % hms(wav_pos),
    print "File %d, record %d, block %d: %s" % (file_num, record_num, block_num, msg)


#############################

def crc(data):
    # crc-16-ccitt, see http://en.wikipedia.org/wiki/Computation_of_cyclic_redundancy_checks
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


#############################



# cf. http://en.wikipedia.org/wiki/Low-pass_filter#Simple_infinite_impulse_response_filter
lowpass_last = 0
def lowpass(x, sample_freq, cutoff_freq):
    global lowpass_last
    dt = 1./sample_freq
    RC = 1./(2.*math.pi*cutoff_freq)
    alpha = dt / (RC + dt)
    y = [0]*len(x)
    y[0] = alpha * x[0] + (1-alpha) * lowpass_last
    for i in range(1, len(x)):
        y[i] = alpha * x[i] + (1.-alpha) * y[i-1]
    lowpass_last = y[-1]
    return y

# Second order butterworth low-pass filter
# cf. src/arch/ibmpc/cassette.c (Hampa Hug) in PCE sources
lowpass_last1 = 0
lowpass_x1 = 0
lowpass_x2 = 0
def butterworth(x, srate, freq):
    global lowpass_x1, lowpass_x2, lowpass_last, lowpass_last1
    om = 1. / math.tan((math.pi * freq) / srate)
    b0 = om*om + om*math.sqrt(2.) + 1.
    #a0, a1, a2 = 1, 2, 1
    b1, b2 = 2*(1-om*om), (om*om-om*math.sqrt(2)+1)
    y = [0]*len(x)
    y[0] = (x[0] + 2*lowpass_x1 + lowpass_x2 - b1*lowpass_last - b2*lowpass_last1) / b0
    y[1] = (x[1] + 2*x[0] + lowpass_x1 - b1*y[0] - b2*lowpass_last) / b0
    for i in range(2, len(x)):
        y[i] = (x[i] + 2*x[i-1] + x[i-2] - b1*y[i-1] - b2*y[i-2]) / b0
    lowpass_x1, lowpass_x2 = x[-1], x[-2]
    lowpass_last, lowpass_last1 = y[-1], y[-2]
    return y


#############################

class EOF(Exception):
    pass

#############################

frame_buf = []
buf_len = 1024
wav_pos = 0
frame_pos = 0

def read_frame():
    global wav_pos
    wav_pos += 1
    try:
        return frame_buf[wav_pos-frame_pos-1]
    except IndexError:
        fill_buffer()
        return frame_buf[0]

def fill_buffer():
    global frame_buf, frame_pos
    frames = wav.readframes(buf_len)
    # convert bytes into ints (little-endian if 16 bit)
    try:
        frames2 = struct.unpack(conv_format, frames)
    except struct.error:
        if not frames:
            raise EOF
        frames2 = struct.unpack(conv_format[:len(frames)//sampwidth+1], frames)
    # sum frames over channels
    frames3 = map(sum, zip(*[iter(frames2)]*nchannels))
    frames4 = [ x-subtractor if x >= threshold else x for x in frames3 ]
    frame_buf = butterworth(frames4, framerate, 3000)
    frame_pos += buf_len

def start_polarity_pos():
    global polarity
    frame = read_frame()
    while frame <= 0:
        frame = read_frame()
    polarity = 1   

def start_polarity_neg():
    global polarity
    frame = read_frame()
    while frame > 0:
        frame = read_frame()
    polarity = -1   
    
def start_polarity():
    global polarity    
    frame = read_frame()
    # initial threshold to determine polarity
    threshold = (256**sampwidth)/16
    while abs(frame) < threshold:
        frame = read_frame()
    polarity = 1 if frame>0 else -1

def read_pulse_pos():
    frame = read_frame()
    pos = wav_pos
    while frame > 0:
        frame = read_frame()
    length_up = wav_pos - pos + 1
    pos = wav_pos
    # move forward to positive polarity
    while frame <= 0:
        frame = read_frame()
    length_dn = wav_pos - pos + 1
    return length_dn, length_up

def read_pulse_neg():
    frame = read_frame()
    pos = wav_pos
    while frame < 0:
        frame = read_frame()
    length_up = wav_pos - pos + 1
    pos = wav_pos
    # move forward to positive polarity
    while frame >= 0:
        frame = read_frame()
    length_dn = wav_pos - pos + 1
    return length_dn, length_up



def read_bit():
    pulse = read_pulse()
    dn = 1 if pulse[0] >= length_cut else 0
    up = 1 if pulse[1] >= length_cut else 0
    if pulse[0] > 2*length_cut or pulse[1] > 2*length_cut:
        return None, None
    if pulse[0] < length_cut/2 or pulse[1] < length_cut/2:
        return None, None
    return dn, up


def read_byte():
    byte_dn, byte_up = 0, 0
    for i in xrange(8):
        bit_dn, bit_up = read_bit()
        if bit_dn == None or bit_up == None:
            return None, None
        byte_dn += bit_dn * 128 >> i
        byte_up += bit_up * 128 >> i
    return byte_dn, byte_up


def read_leader():
    while True:
        while read_bit()[0] != 1:
            pass
        counter = 0
        start_frame = wav_pos
        while True:
            b = read_bit()[0] 
            if b != 1:
                break
            counter += 1
        # sync bit 0 has been read, check sync byte 0x16
        # at least 64*8 bits
        if b != None and counter >= 512:
            sync = read_byte()[0]
            if sync == 0x16:
                return start_frame
        
def hms(loc):
    m, s = divmod(loc/framerate, 60)
    h, m = divmod(m, 60)
    return h, m, s


def read_block():
    count = 0
    data_dn, data_up = '', ''
    while True:
        if count == 256:
            bytes0 = read_byte()
            bytes1 = read_byte()
            crc_read_dn = bytes0[0] * 0x100 + bytes1[0]
            crc_read_up = bytes0[1] * 0x100 + bytes1[1]
            crc_dn = crc(data_dn)
            crc_up = crc(data_up)
            # if crc for either polarity matches, return that
            if crc_dn == crc_read_dn:
                return data_dn
            if crc_up == crc_read_up:
                return data_up
            # neither matches
            warning("crc: dn %04x [%04x]  up %04x [%04x]" % (crc_read_dn, crc_dn, crc_read_up, crc_up))
            return data_dn
        else:
            byte_dn, byte_up = read_byte()
            # if this is a header block, it must be 256 bytes
            if byte_dn == None or byte_up == None:
                warning("break")
                return []
            data_dn += chr(byte_dn)
            data_up += chr(byte_up)
            count += 1
            

def read_record(reclen):
    global block_num
    seconds = read_leader() / framerate 
    record = ''
    block_num = 0
    byte_count = 0
    while byte_count < reclen or reclen == None:
        data = read_block()
        if not data:
            break
        record += data
        byte_count += len(data)
        if (reclen == None and 
                (data[:4] == '\xff\xff\xff\xff' or 
                (block_num == 0 and data[0] == '\xa5'))):
            break
        block_num += 1
    if reclen != None:
        return record[:reclen]
    return record

def parse_header(record):
    if not record or record[0] != '\xa5':
        return None
    name = record[1:9]
    token = ord(record[9])
    nbytes = ord(record[10]) + ord(record[11]) * 0x100
    seg = ord(record[12]) + ord(record[13]) * 0x100
    offs = ord(record[14]) + ord(record[15]) * 0x100
    return name, token, nbytes, seg, offs


def read_file():
    global record_num
    loc = wav_pos
    record_num = 0           
    record = read_record(None)
    header = parse_header(record)
    print "[%d:%02d:%02d]" % hms(loc),
    print "File %d:" % file_num, 
    if not header:
        # unknown record type
        print "Record of unknown type."
        return 'DATA.X%02x' % file_num, record
    else:
        file_trunk, file_token, file_bytes, seg, offs = header
        file_ext = token_to_ext[file_token]
        print '%s Found.' % (file_trunk + '.' + file_ext),
        print "%d bytes," % file_bytes,
        print "load address %04x:%04x." % (seg, offs) 
        # for programs this is start address: cf to offset of next line in prgram
    file_name = file_trunk.rstrip() + '.' + file_ext + '%02x' % file_num
    data = token_to_magic[file_token]
    if file_token == 0x01:
        # bsave format: paste in 6-byte header for disk files
        data += ''.join(map(chr, word_le(seg)))
        data += ''.join(map(chr, word_le(offs)))
        data += ''.join(map(chr, word_le(file_bytes)))
    if file_token in (1, 0x80, 0x20, 0xa0):
        record_num += 1
        # bsave, tokenised and protected come in one multi-block record
        data += read_record(file_bytes)
    else:
        # ascii and data come as a sequence of one-block records
        # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
        while True:
            record_num += 1
            record = read_record(256)
            num_bytes = ord(record[0])
            record = record[1:]
            if num_bytes != 0:
                record = record[:num_bytes-1]
            data += record
            if num_bytes != 0:
                break
    # write EOF char
    data += '\x1a'
    return file_name, data
        
def read_wav():
    global wav, nchannels, sampwidth, framerate, nframes, lopass, length_cut, halflength
    global threshold, subtractor, bytesperframe, conv_format
    global file_num, record_num, block_num
    global read_pulse
    wav = wave.open(sys.argv[1], 'rb')
    nchannels =  wav.getnchannels()
    sampwidth = wav.getsampwidth()
    framerate = wav.getframerate()
    nframes = wav.getnframes()
    if sampwidth == 1:
        threshold = 0
        subtractor = 128
    else:
        threshold = (1 << (sampwidth*8-1))*nchannels
        subtractor =  (1 << (sampwidth*8))*nchannels
    bytesperframe = nchannels*sampwidth
    print "Cassette image %s: WAV audio" % sys.argv[1],
    print "%d:%02d:%02d," % hms(nframes),
    print "%d-bit," % (sampwidth*8),
    print "%d fps," % framerate,
    print "%d channels" % nchannels,
    print
    if sampwidth > 3:
        print "Can't convert WAV files of more than 16-bit."
    conv_format = '<' + {1:'B', 2:'h'}[sampwidth]*nchannels*buf_len
    # 1000 us for 1, 500 us for 0; threshould for half-pulse (500 us, 250 us)
    length_cut = 375 * framerate / 1000000
    halflength = [250 * framerate /1000000, 500 * framerate /1000000]
    # find most likely polarity of pulses (down-first or up-first)
    start_polarity()
    read_pulse = read_pulse_pos if polarity > 0 else read_pulse_neg
    # start parsing
    file_num = 0
    while True:
        try:
            file_name, data = read_file()
            with open(file_name, 'wb') as f:
                f.write(str(bytearray(data)))
            file_num += 1
        except EOF:
            break
    print "[%d:%02d:%02d] End of tape" % hms(wav_pos)
    wav.close



#######################################

def write_pulse(half_length):
    wav.writeframes('\x00' * half_length + '\xff' * half_length)

def write_pause(milliseconds):
    wav.writeframes('\x7f' * (milliseconds * framerate / 1000))
    
def write_bit(bit):
    write_pulse(halflength[bit])
    write_bit_cas(bit)

cas_byte = 0
cas_count = 0
def write_bit_cas(bit):
    global cas_byte, cas_count
    cas_byte = (cas_byte << 1) | bit
    cas_count += 1
    if cas_count >= 8:
        cas.write(chr(cas_byte))
        cas_count = 0
        cas_byte = 0
    
def write_byte(byte):
    bits = [ 1 if (byte & ( 128 >> i) != 0) else 0 for i in range(8) ]
    for bit in bits:
        write_bit(bit)

def write_intro():
    # write some noise to give the reader something to get started
    write_pause(100)
    

def write_leader():
    for _ in range(256):
        write_byte(0xff)
    write_bit(0)
    write_byte(0x16)    

def word_le(word):
    hi, lo = divmod(word, 256)
    return [lo, hi]

def header(name, token, nbytes, seg, offs):
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

def write_block(data):
    # fill out short blocks with last byte
    data += data[-1]*(256-len(data))
    for b in data:
        write_byte(ord(b))
    crc_word = crc(data)
    # crc is written big-endian
    lo, hi = word_le(crc_word)
    write_byte(hi)
    write_byte(lo)

def write_record(data):
    write_leader()
    while len(data) > 0:
        write_block(data[:256])
        data = data[256:]
    write_byte(0xff)
    write_byte(0xff)
    write_byte(0xff)
    for b in (1,1,1,1,1,1,0):
        write_bit(b)
    # write 100 ms second pause to make clear separation between blocks
    write_pause(100)

def write_file(name, token, data):
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
    write_record(header(name, token, bytes, seg, offs))
    if token in (1, 0x80, 0x20, 0xa0):
        # bsave, tokenised and protected come in one multi-block record
        write_record(data)
    else:
        # ascii and data come as a sequence of one-block records
        # 256 bytes less 1 length byte. CRC trailer comes after 256-byte block
        blocks, last = divmod(len(data), 255)
        for i in range(blocks):
            offset = i*255
            write_record('\0' + data[offset:offset+255])
        if last > 0:
            write_record(chr(last) + data[-last:])


def write_wav():     
    global wav, cas, halflength, framerate
    framerate = 22050
    sampwidth = 1
    cas = open(sys.argv[1]+'.cas', 'wb')
    wav = wave.open(sys.argv[1], 'wb')
    wav.setnchannels(1)
    wav.setsampwidth(1)
    wav.setframerate(framerate)
    halflength = [250 * framerate /1000000, 500 * framerate /1000000]
    write_intro()
    # write files
    for file_name in sys.argv[2:]:
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
            write_file(name, token, data)
    wav.close()
    cas.close()
    
#######################################

import os
if os.path.basename(sys.argv[0]) == 'readwav.py':
    read_wav()
elif os.path.basename(sys.argv[0]) == 'writewav.py':
    write_wav()

