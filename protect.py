"""
PC-BASIC - protect.py
Source encryption/decryption

(c) 2013, 2014, 2015 Rob Hagemans 
This file is released under the GNU GPL version 3.

Paul Kocher reverse engineered the decryption algorithm, published in:
The Cryptogram computer supplement #19, American Cryptogram Association, Summer 1994
"""

# 13-byte and 11-byte keys used by GW-BASIC
key1 = [0xA9, 0x84, 0x8D, 0xCD, 0x75, 0x83, 0x43, 0x63, 0x24, 0x83, 0x19, 0xF7, 0x9A]
key2 = [0x1E, 0x1D, 0xC4, 0x77, 0x26, 0x97, 0xE0, 0x74, 0x59, 0x88, 0x7C]

def unprotect(ins, outs):
    """ Decrypt a byte stream read from the GWBASIC ,P (read protected) format. This will allow it to be subsequently parsed """
    index = 0
    s = ins.read(1)
    while s != '':
        nxt = ins.read(1)
        # drop last char (EOF 0x1a)
        if nxt == '':
            break
        c = ord(s)
        # Kocher's algorithm:
        c -= 11 - (index % 11)
        c ^= key1 [index % 13]
        c ^= key2 [index % 11]
        c += 13 - (index % 13)
        outs.write(chr(c%256))
        index = (index+1) % (13*11)
        s = nxt
    # return last char written
    return chr(c%256)

def protect(ins, outs):
    """ Encrypt a byte stream read from the GWBASIC tokenised format """
    index = 0
    nxt = ins.read(1)
    while nxt != '':
        s = nxt
        c = ord(s)
        # inverse Kocher's algorithm:
        c -= 13 - (index % 13)
        c ^= key1 [index % 13]
        c ^= key2 [index % 11]
        c += 11 - (index % 11)
        outs.write(chr(c%256))
        index = (index+1) % (13*11)
        nxt = ins.read(1)
    # return last char read
    return s
