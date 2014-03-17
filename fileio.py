#
# PC-BASIC 3.23 - fileio.py
#
# File I/O operations 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from cStringIO import StringIO

import error
import util
import oslayer
import deviceio

# file numbers
files = {}
# fields are preserved on file close, so have a separate store
fields = {}

# maximum file number = maximum number of open files
# in GW, this is a command line option
max_files = 3

'''ByteStream is a wrapper for bytearray that keeps track of a location. '''        
class ByteStream(object):
    def __init__(self, contents=''):       
        self.setvalue(contents)

    '''assign a bytearray s, move location to 0. this does not create a copy, changes affect the original bytearray'''
    def setvalue(self, contents=''):
        self._contents = contents
        self._loc = 0
    
    '''retrieve the bytearray. changes will affect the bytestream.'''
    def getvalue(self):
        return self._contents
        
    '''get the current location'''    
    def tell(self):
        return self._loc
        
    '''moves loc by n bytes from start(w=0), current(w=1) or end(w=2)'''    
    def seek(self, n_bytes, from_where=0):
        if from_where == 0:
            self._loc = n_bytes
        elif from_where == 1:
            self._loc += n_bytes
        elif from_where == 2:
            self._loc = len(self._contents)-n_bytes        
        if self._loc < 0:
            self._loc = 0
        elif self._loc > len(self._contents):
            self._loc = len(self._contents)    
    
    '''get an n-length string and move the location n forward. if loc>len, returns empty'''
    def read(self, n_bytes=None):
        if n_bytes==None:
            n_bytes = len(self._contents) - self._loc
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)
            return ''
        peeked = self._contents[self._loc:self._loc+n_bytes]
        self._loc += len(peeked)   
        return peeked
            
    '''writes a str or bytearray or char s to the current location. overwrite, not insert'''    
    def write(self, substr):
        if self._loc >= len(self._contents):
            self._contents += substr
            self._loc = len(self._contents)    
        else:    
            self._contents[self._loc:self._loc+len(substr)] = substr
            self._loc += len(substr)

    '''clips off the bytearray after position n'''
    def truncate(self, n=None):
        if n==None:
            n=self._loc
        self._contents = self._contents[:n]
        if self._loc >= len(self._contents):
            self._loc = len(self._contents)

    def close(self):
        pass            


class BaseFile(object):
    def __init__(self, fhandle, number, mode, access):
        # width=255 means line wrap
        self.fhandle = fhandle
        self.number = number
        self.mode = mode.upper()
        self.access = access
        if self.mode in ('I', 'O', 'R', 'S', 'L'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        if number != 0:
            files[number] = self

    def close(self):
        self.fhandle.close()
        if self.number != 0:
            del files[self.number]
    
    def read_chars(self, num):
        return list(self.fhandle.read(num)) 
        
    def read(self, num):
        return ''.join(self.read_chars(num))
            
    def peek_char(self):
        s = self.fhandle.read(1)
        self.fhandle.seek(-len(s), 1)
        return s
    
    def seek(self, num, from_where=0):    
        self.fhandle.seek(num, from_where)
    
    def write(self, s):
        self.fhandle.write(str(s))

    def end_of_file(self):
        return peek_char() == ''
        
    def flush(self):
        self.fhandle.flush()

    def truncate(self):
        self.fhandle.truncate()

class TextFile(BaseFile):
    def __init__(self, fhandle, number=0, mode='A', access='r+b'):
        BaseFile.__init__(self, fhandle, number, mode, access)
        # width=255 means line wrap
        self.width = 255
        self.col = 1
    
    def close(self):
        if self.access == 'wb':
            # write EOF char
            self.fhandle.write('\x1a')
        BaseFile.close(self)
        
    # read line    
    def read_line(self):
        if self.end_of_file():
            # input past end
            raise error.RunError(62)
        # readline breaks line on \x0A, we can only break on \x0D or \x0D\x0A
        s = ''
        while True:
            c = self.fhandle.read(1)
            if c in ('', '\x1a'):
                break
            elif c=='\x0A':
                s += c
                # special: allow \x0A\x0D to pass
                if self.peek_char() == '\x0D':
                    self.fhandle.read(1)
                    s+= '\x0D'
            elif c=='\x0D':
                # check for CR/LF
                if self.peek_char() == '\x0A':
                    self.fhandle.read(1)
                break
            else:        
                s += c    
        return s

    def read_chars(self, num):
        s = []
        for _ in range(num):
            c = self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading FIXME: that's true in files but not devices)
            if c in ('\x1a', ''):
                # input past end
                raise error.RunError(62)
            s.append(c)
        return s 
        
    # write one or more chars
    def write(self, s):
        for c in str(s):
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                self.fhandle.write('\x0d\x0a')
                self.col = 1
            if c in ('\x0a','\x0d'): # CR, LF
                self.fhandle.write(c)
                self.col = 1
            elif c == '\x08':
                if self.col > 1:
                    self.col -= 1
                self.fhandle.seek(-1, 1)
                self.truncate()                    
            else:    
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                # FIXME: this is true for text files, but not for SCRN:  
                # for lpt1 and files , nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                if ord(c) >= 32:
                    self.col += 1

    def set_width(self, new_width=255):
        self.width = new_width
    
    def loc(self):
        # for LOC(i)
        if self.mode == 'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    # for internal use    
    def end_of_file(self):
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def eof(self):
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof


class RandomBase(object):
    def __init__(self, fhandle, number, mode, access, reclen=128):
        self.fhandle = fhandle
        self.number = number
        self.mode = mode.upper()
        self.access = access
        self.reclen = reclen
        # replace with empty field if already exists    
        try:
            self.field = fields[self.number]
        except KeyError:
            self.field = bytearray()
            fields[self.number] = self.field
        self.field[:] = bytearray('\x00')*reclen
        # open a pseudo text file over the buffer stream
        # to make WRITE# etc possible
        # all text-file operations on a RANDOM file number actually work on the FIELD buffer
        self.field_text_file = TextFile(ByteStream(self.field))
        self.field_text_file.col = 1
        # width=255 means line wrap
        self.field_text_file.width = 255
        if number != 0:
            files[number] = self
    
    # read line (from field buffer)    
    def read_line(self):
        # FIELD overflow happens if last byte in record is actually read
        if self.field_text_file.fhandle.tell() >= self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read_line()
        
    def read_chars(self, num):
        if self.field_text_file.fhandle.tell() + num > self.reclen-1:
            raise error.RunError(self.overflow_error) # FIELD overflow
        return self.field_text_file.read_chars(num)
    
    def read(self, num):
        return ''.join(self.read_chars(num))
    
    # write one or more chars to field buffer
    def write(self, s):
        ins = StringIO(s)
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell() < len(s):
            raise error.RunError(self.overflow_error) 
    
    def close(self):
        # don't close the handle in case it's a serial device
        if self.number != 0:
            del files[self.number]
    
    def flush(self):
        self.fhandle.flush()

    def peek_char(self):
        return self.field_text_file.peek_char()
    
    def seek(self, n, from_where):
        return self.field_text_file.seek(n, from_where)
        
    @property
    def col(self):
        return self.field_text_file.col
    
    @property
    def width(self):
        return self.field_text_file.width
    
    def set_width(self, new_width=255):
        self.field_test_file.width = new_width

    def truncate(self):
    # this is only used when writing chr$(8), not sure how to implement for random files
        pass
        
    def end_of_file(self):
        return self.peek_char() == ''
        
class RandomFile(RandomBase):
    # FIELD overflow
    overflow_error = 50
    
    def __init__(self, fhandle, number, mode, access, reclen=128):
        RandomBase.__init__(self, fhandle, number, mode, access, reclen=128)
        # position at start of file
        self.recpos = 0
        self.fhandle.seek(0)
    
    def close(self):
        RandomBase.close(self)
        self.fhandle.close()
        
    # read record    
    def read_field(self, dummy=None):
        if self.eof():
            self.field[:] = '\x00'*self.reclen
        else:
            self.field[:] = self.fhandle.read(self.reclen)
        self.field_text_file.seek(0)    
        self.recpos += 1
        
    # write record
    def write_field(self, dummy=None):
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0, 2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\x00'*numrecs*self.reclen)
        self.fhandle.write(self.field)
        self.recpos += 1
        
    def set_pos(self, newpos):
        # first record is newpos number 1
        self.fhandle.seek((newpos-1)*self.reclen)
        self.recpos = newpos - 1

    def loc(self):
        # for LOC(i)
        # returns number of record we're just past
        return self.recpos
        
    def eof(self):
        # for EOF(i)
        return self.recpos*self.reclen > self.lof()
            
    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof

# posix access modes for BASIC modes INPUT ,OUTPUT, RANDOM, APPEND and internal LOAD and SAVE modes
access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'ab', 'L': 'rb', 'S': 'wb' }
# posix access modes for BASIC ACCESS mode for RANDOM files only
access_access = { 'R': 'rb', 'W': 'wb', 'RW': 'r+b' }

def check_file_not_open(name):
    for f in files:
        if name == files[f].fhandle.name:
            raise error.RunError(55)
    
def open_file_or_device(number, name, mode='I', access='', lock='rw', reclen=128, defext=''):
    if number < 0 or number > max_files:
        # bad file number
        raise error.RunError(52)
    if number in files:
        # file already open
        raise error.RunError(55)
    name, mode = str(name), mode.upper()
    if not access or mode != 'R':
        access = access_modes[mode]
    else:
        access = access_access[access]    
    split_colon = name.upper().split(':')
    if len(split_colon) > 1: # : found
        dev_name = split_colon[0] + ':' 
        if deviceio.is_device(dev_name): 
            inst = deviceio.device_open(number, dev_name, mode, access)
        elif len(dev_name) > 2:
            # devname could be A:, B:, C:, etc.. but anything longer is an error (bad file number, for some reason).
            raise error.RunError(52)   
    else:    
        # translate the file name to something DOS-ish is necessary
        if access == 'rb' or access == 'r':
            name = oslayer.dospath_read(name, defext, 53)
        else:
            name = oslayer.dospath_write(name, defext, 76)
        if mode in ('O', 'A'):
            # don't open output or append files more than once
            check_file_not_open(name)
        # open the file
        fhandle = oslayer.safe_open(name, access)
        # obtain a lock
        oslayer.safe(oslayer.lock, fhandle, lock)
        # apply the BASIC file wrapper
        if mode in ('S', 'L'): # save, load
            inst = BaseFile(fhandle, number, mode, access)
        elif mode in ('I', 'O', 'A'):
            inst = TextFile(fhandle, number, mode, access)
        else:
            inst = RandomFile(fhandle, number, mode, access, reclen)
    return inst    
           
def close_all():
    for f in list(files):
        if f > 0:
            files[f].close()

def get_file(num, mode='IOAR'):
    try:
        the_file = files[num]
    except KeyError:
        # bad file number
        raise error.RunError(52)
    if the_file.mode.upper() not in mode:
        raise error.RunError(54)    
    return the_file    
    
