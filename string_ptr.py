#
# PC-BASIC 3.23 - string_ptr.py
#
# String pointer implementation
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

def apply_slice(slice0, slice1):
    """ Get a slice of a slice. """
    if isinstance(slice1, slice):
        start, stop = slice0.start + slice1.start, slice0.start + slice1.stop
    else:
        start, stop = slice0.start + slice1, slice0.start + slice1 + 1
    if stop > slice0.stop:
        stop = slice0.stop
    return slice(start, stop) 


class StringPtr:
    """ String pointer implementation. Allows for unions of strings (for FIELD). """

    def __init__(self, stream, offset, length):
        """ Set the buffer and where to put the string in it. Don't allocate, use the buffer provided. """
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
    
    def __len__(self):
        """ Return the length of the string. """
        return self.slice.stop - self.slice.start

    def __getitem__(self, key):
        """ Return a copy of a range of characters from the string. """
        return self.stream[self.slice][key]

    def __setitem__(self, key, value):
        """ Change a range of characters in the string. """
        self.stream[apply_slice(self.slice, key)] = value    
            def __str__(self):
        return str(self.stream[self.slice])
        
    def assign(self, in_str):
        """ Replace the string with a new value in-place. """
        self.stream[self.slice] = in_str[len(self)] + ' '*(len(self)-len(in_str))
    
    def get(self):
        """ Return a copy of the the full string value. """
        return self.stream[self.slice]
        

