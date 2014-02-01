#
# PC-BASIC 3.23  - protect.py
#
# Source encryption/decryption 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
# Acknowledgements:
# Paul Kocher discovered the decryption algorithm, published here:
#   The Cryptogram computer supplement #19, American Cryptogram Association, Summer 1994 
#
 

# 13-byte and 11-byte keys used by GW-BASIC 
key1 = [0xA9, 0x84, 0x8D, 0xCD, 0x75, 0x83, 0x43, 0x63, 0x24, 0x83, 0x19, 0xF7, 0x9A]
key2 = [0x1E, 0x1D, 0xC4, 0x77, 0x26, 0x97, 0xE0, 0x74, 0x59, 0x88, 0x7C]
      
""" Decrypt a byte stream read from the GWBASIC ,P (read protected) format. This will allow it to be subsequently parsed """
def unprotect(ins, outs):    
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
        index = (index+1) % (13*11);
        s = nxt
    return True
    
""" Encrypt a byte stream read from the GWBASIC tokenised format """
def protect(ins, outs):    
    index = 0
    s = ins.read(1)
    while s != '': 
        nxt = ins.read(1)
        # drop last char (EOF 0x1a)
        if nxt == '':
            break
        c = ord(s)
        # inverse Kocher's algorithm:
        c -= 13 - (index % 13)
        c ^= key1 [index % 13]
        c ^= key2 [index % 11]
        c += 11 - (index % 11)
        outs.write(chr(c%256))
        index = (index+1) % (13*11);
        s = nxt
    return True
    

