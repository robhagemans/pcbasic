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
            
    
class TextFile(object):
    def __init__(self):
        # width=255 means line wrap
        self.width = 255
        self.col=1
        self.fhandle= None
        self.number=0
        self.mode=''
        self.access=''
        
    def init(self, dummy=42):
        if self.mode.upper() in ('I', 'O', 'R', 'P'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        
    def close(self):
        if self.access=='wb':
            # write EOF char
            self.fhandle.write('\x1a')
        self.fhandle.close()
        if self.number != 0:
            del files[self.number]
        
    # read line    
    def read(self):
        if self.eof():
            # input past end
            raise error.RunError(62)
        # readline breaks line on \x0A, we can only break on \x0D or \x0D\x0A
        s=''
        while True:
            c = self.fhandle.read(1)
            if c in ('', '\x1a'):
                break
            elif c=='\x0A':
                s += c
                # special: allow \x0A\x0D to pass
                if util.peek(self.fhandle) == '\x0D':
                    self.fhandle.read(1)
                    s+= '\x0D'
            elif c=='\x0D':
                # check for CR/LF
                if util.peek(self.fhandle) == '\x0A':
                    self.fhandle.read(1)
                break
            else:        
                s += c    
        return s

    def read_chars(self, num):
        s=''
        for _ in range(num):
            c=self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading)
            if c in ('\x1a', ''):
                break
            s+=c
        if self.eof():    
            # input past end
            raise error.RunError(62)
        return s 
        
    def peek_char(self):
        return self.peek_chars()
        
    def peek_chars(self,num=1):
        s=''
        for _ in range(num):
            c = self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading)
            if c =='':
                break
            if c=='\x1a':
                self.fhandle.seek(-1,1)
                break
            s+=c
        self.fhandle.seek(-len(s),1)
        return s

    # write one or more chars
    def write(self, s):
        s_out = ''
        #last = ''
        for c in s:
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                s_out+= '\x0d\x0a'
                self.col=1
            if c in ('\x0a','\x0d'): # CR, LF
                s_out+=c
                self.col = 1
            else:    
                s_out+=c
            # nonprinting characters including tabs are not counted for WIDTH
            # FIXME: this is true for text files, but not for SCRN: and LPT1:    
            if ord(c)>=32:
                self.col+=1
        self.fhandle.write(s_out)

    def get_col(self):
        return self.col
    
    def set_width(self, new_width=255):
        self.width = new_width
    
    def get_width(self):
        return self.width
    
    def loc(self):
        # for LOC(i)
        return self.fhandle.tell()/128
    
    def eof(self):
        # for EOF(i)
        if self.mode in ('A', 'O', 'P'):
            return False
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def lof(self):
        return self.fhandle.tell()
 
    def flush(self):
        self.fhandle.flush()
        pass
 
 
class RandomFile(object):
    def __init__(self):
        # width=255 means line wrap
        self.width = 255
        self.col=1
        self.fhandle= None
        self.number=0
        self.mode=''
        self.access=''
    
    # all text-file operations on a RANDOM file number actually work on the FIELD buffer
#    def get_stream(self):
#        return self.field_text_file.fhandle
    
    # read line (from field buffer)    
    def read(self):
        if self.field_text_file.fhandle.tell() >= self.reclen:
            raise error.RunError(50) # FIELD overflow
        return self.field_text_file.read()
        
    def read_chars(self, num):
        if self.field_text_file.fhandle.tell() + num > self.reclen:
            raise error.RunError(50) # FIELD overflow
        return self.field_text_file.read_chars(num)

    def peek_char(self):
        return self.peek_chars()
        
    def peek_chars(self, num=1):
        return self.field_text_file.peek_chars(num)

    # write one or more chars to field buffer
    def write(self, s):
        ins = StringIO(s)
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell()<len(s):
            raise error.RunError(50) # FIELD overflow
    
    def set_width(self, new_width=255):
        self.width = new_width
    
    def get_width(self):
        return self.width
    
    def init(self, reclen=128):
        self.reclen = reclen
        self.recpos = 0
        self.fhandle.seek(0)
        if self.number in fields:
            self.field = fields[self.number]
        else:
            self.field = bytearray('\x00')*reclen
            fields[self.number] = self.field
        # open a pseudo text file over the buffer stream
        # to make WRITE# etc possible
        self.field_text_file = pseudo_textfile(ByteStream(self.field))
        
    def close(self):
        self.fhandle.close()
        if self.number !=0:
            del files[self.number]
        
    # read record    
    def read_field(self):
        if self.eof():
            self.field[:] = '\x00'*self.reclen
        else:
            self.field[:] = self.fhandle.read(self.reclen)
        self.recpos += 1
        return True
        
    #write record
    def write_field(self):
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0,2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\x00'*numrecs*self.reclen)
        self.fhandle.write(self.field)
        self.recpos+=1
        
    def set_pos(self, newpos):
        # first record is newpos number 1
        self.fhandle.seek((newpos-1)*self.reclen)
        self.recpos = newpos-1

    def loc(self):
        # for LOC(i)
        # returns number of record we're just past
        return self.recpos
        
    def eof(self):
        # for EOF(i)
        return self.recpos*self.reclen > self.lof()
            
    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0,2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof
        
    def flush(self):
        self.fhandle.flush()
            
          
# essentially just a text file that doesn't close if asked to
class DeviceFile(TextFile):
    def __init__(self, unixpath, access='rb'):
        TextFile.__init__(self)
        self.fhandle = oslayer.safe_open(unixpath, access)
        self.number = 0 # number
        self.access = access
        if 'W' in access.upper():
            self.mode = 'O'
        else:
            self.mode = 'I'
        self.init()
        
    def close(self):
        # don't close the file handle as we may have copies
        if self.number !=0:
            del files[self.number]
        

# close all non-system files
# system files have negative file number
def close_all():
    for f in list(files):
        if f > 0:
            files[f].close()
        
# close all files
def close_all_all_all():
    for f in list(files):
        files[f].close()
        
def get_file(number):        
    return files[number]
    
def pseudo_textfile(stringio):
    # open a pseudo text file over a byte stream
    text_file = TextFile()
    number = -1
    while number in files:
        number -= 1
    text_file.fhandle = stringio
    text_file.mode='P'
    text_file.number = number
    text_file.access = 'rwb'
    text_file.init()
    return text_file        
   
def open_file(number, unixpath, mode='I', access='rb', lock='rw', reclen=128):
    if mode.upper() in ('I','O','A'):
        inst = TextFile()
    else:
        inst = RandomFile()
        access = 'r+b'
    if number <0 or number>255:
        # bad file number
        raise error.RunError(52)
    if number in files:
        # file already open
        raise error.RunError(55)
    # create file if writing and doesn't exist yet    
    # TODO: CHECK: this still necessaary? there's no w in r+b
#    if 'W' in access.upper() and not os.path.exists(unixpath):
#        tempf = oslayer.safe_open(unixpath,'wb')
#        tempf.close() 
    inst.fhandle = oslayer.safe_open(unixpath, access)
    oslayer.safe_lock(inst.fhandle, access, lock)
    inst.number = number
    inst.access = access
    inst.mode = mode.upper()
    inst.init(reclen)
    files[number] = inst
            
def lock_file(thefile, lock, lock_start, lock_length):
    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
    if isinstance(thefile, TextFile):
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock)
    elif isinstance(thefile, RandomFile):
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock, lock_start, lock_length)
        
    



