#
# PC-BASIC 3.23 - string_ptr.py
#
# String pointer implementation
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

def apply_slice(slice0, slice1):
    if isinstance(slice1, slice):
        start, stop = slice0.start + slice1.start, slice0.start + slice1.stop
    else:
        start, stop = slice0.start + slice1, slice0.start + slice1 + 1
    if stop > slice0.stop:
        stop = slice0.stop
    return slice(start, stop) 


# string pointer implementation, allows for unions of strings (for FIELD)
class StringPtr:
    def assign(self, in_str):
        self.stream[self.slice] = in_str[len(self)] + ' '*(len(self)-len(in_str))
    
    def get(self):
        return self.stream[self.slice]
        
    def __str__(self):
        return str(self.stream[self.slice])
        
    def __len__(self):
        return self.slice.stop - self.slice.start

    def __init__(self, stream, offset, length):
        if length < 0:
            length = 0
        if isinstance(stream, StringPtr):
            self.stream = stream.stream
            self.slice = slice(stream.slice.start + offset, stream.slice.start+offset+length)
            max_length = stream.length-offset
        else:
            # this must be a mutable type - list or bytearray
            self.stream = stream  
            max_length = len(stream)
            self.slice = slice(offset, offset+length)
        # BASIC string length limit
        if max_length > 255:
            max_length = 255
        if self.slice.stop - self.slice.start > max_length:
            self.slice.stop = self.slice.start + max_length
    
    def __getitem__(self, key):
        return self.stream[self.slice][key]

    def __setitem__(self, key, value):
        self.stream[apply_slice(self.slice, key)] = value    
        
