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

from cStringIO import StringIO


# string pointer implementation, allows for unions of strings (for FIELD)
class StringPtr:
    def get_str(self):
        pos = self.stream.tell()
        self.stream.seek(self.offset)
        sstr = self.stream.read(self.length)
        self.stream.seek(pos)
        return sstr
         
    def set_str(self, in_str):
        pos = self.stream.tell()
        #ins = StringIO(in_str)
        self.stream.seek(self.offset)    
        #for _ in range(self.length):
        #    c = ins.read(1)
        #    if c=='':
        #        c=' '
        #    self.stream.write(c)
        self.stream.write(in_str[:self.length] + ' '*(self.length-len(in_str)))
        #
        self.stream.seek(pos)
        
    def __str__(self):
        return self.get_str()
        
    def __len__(self):
        return self.length

    def __init__(self, stream, offset, length):
        if isinstance(stream, StringPtr):
            self.stream, self.offset, self.length = stream.stream, stream.offset+offset, length     
            max_length = stream.length
        else:
            self.stream = StringIO(stream)
            self.stream.seek(0)    
            max_length = len(stream)
            self.offset, self.length = offset, length
        # BASIC string length limit
        if self.length > 255:
            self.length = 255
        if self.offset+self.length > max_length:
            self.length = max_length-self.offset
            if self.length < 0:
                self.length = 0    
        
