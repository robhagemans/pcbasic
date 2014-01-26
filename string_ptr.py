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


# string pointer implementation, allows for unions of strings (for FIELD)
class StringPtr:
    def set_str(self, in_str):
        self.stream[self.offset:self.offset+self.length] = in_str[:self.length] + ' '*(self.length-len(in_str))
        
    def __str__(self):
        return str(self.stream[self.offset:self.offset+self.length])
        
    def __len__(self):
        return self.length

    def __init__(self, stream, offset, length):
        if isinstance(stream, StringPtr):
            self.stream, self.offset, self.length = stream.stream, stream.offset+offset, length     
            max_length = stream.length
        else:
            self.stream = stream  # this must be a mutable type - list or bytearray
            max_length = len(stream)
            self.offset, self.length = offset, length
        # BASIC string length limit
        if self.length > 255:
            self.length = 255
        if self.offset+self.length > max_length:
            self.length = max_length-self.offset
            if self.length < 0:
                self.length = 0    
        
        
