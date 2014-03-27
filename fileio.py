#
# PC-BASIC 3.23 - fileio.py
#
# File I/O operations 
# 
# (c) 2013, 2014 Rob Hagemans 
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


def open_file_or_device(number, name, mode='I', access='R', lock='', reclen=128, defext=''):
    if not name or number < 0 or number > max_files:
        # bad file number; also for name='', for some reason
        raise error.RunError(52)
    if number in files:
        # file already open
        raise error.RunError(55)
    name, mode = str(name), mode.upper()
    inst = None
    split_colon = name.upper().split(':')
    if len(split_colon) > 1: # : found
        dev_name = split_colon[0] + ':' 
        try:
            inst = deviceio.device_open(name, number, mode, access, lock, reclen)
        except KeyError:    
            if len(dev_name) > 2:
                # devname could be A:, B:, C:, etc.. but anything longer is an error (bad file number, for some reason).
                raise error.RunError(52)   
    if not inst:
        # translate the file name to something DOS-ish is necessary
        if mode in ('I', 'L', 'R'):
            name = oslayer.dospath_read(name, defext, 53)
        else:
            name = oslayer.dospath_write(name, defext, 76)
        if mode in ('O', 'A'):
            # don't open output or append files more than once
            check_file_not_open(name)
        # obtain a lock
        request_lock(name, lock, access)
        # open the file
        fhandle = oslayer.safe_open(name, mode, access)
        # apply the BASIC file wrapper
        if mode in ('S', 'L'): # save, load
            inst = BaseFile(fhandle, name, number, mode, access, lock)
        elif mode in ('I', 'O', 'A'):
            inst = TextFile(fhandle, name, number, mode, access, lock)
        else:
            inst = RandomFile(fhandle, name, number, mode, access, lock, reclen)
    return inst    
    
def get_file(num, mode='IOAR'):
    try:
        the_file = files[num]
    except KeyError:
        # bad file number
        raise error.RunError(52)
    if the_file.mode.upper() not in mode:
        raise error.RunError(54)    
    return the_file    
     
def check_file_not_open(name):
    for f in files:
        if name == files[f].name:
            raise error.RunError(55)

def find_files_by_name(name):
    return [files[f] for f in files if files[f].name == name]
      
def close_all():
    for f in list(files):
        if f > 0:
            files[f].close()

def lock_records(nr, start, stop):
    thefile = get_file(nr)
    if thefile.name in deviceio.devices:
        # permission denied
        raise error.RunError(70)
    lock_list = set()
    for f in find_files_by_name(thefile.name):
        lock_list |= f.lock_list
    if isinstance(thefile, TextFile):
        bstart, bstop = 0, -1
        if lock_list:
            raise error.RunError(70)    
    else:
        bstart, bstop = (start-1) * thefile.reclen, stop*thefile.reclen - 1
        for start_1, stop_1 in lock_list:
            if stop_1 == -1 or (bstart >= start_1 and bstart <= stop_1) or (bstop >= start_1 and bstop <= stop_1):
                raise error.RunError(70)
    thefile.lock_list.add((bstart, bstop))

def unlock_records(nr, start, stop):    
    thefile = get_file(nr)
    if thefile.name in deviceio.devices:
        # permission denied
        raise error.RunError(70)
    if isinstance(thefile, TextFile):
        bstart, bstop = 0, -1
    else:
        bstart, bstop = (start-1) * thefile.reclen, stop*thefile.reclen - 1
    # permission denied if the exact record range wasn't given before
    try:
        thefile.lock_list.remove((bstart, bstop))
    except KeyError:
        raise error.RunError(70)
    
def request_lock(name, lock, access):
    same_files = find_files_by_name(name)
    if not lock: # default mode; don't accept default mode if SHARED/LOCK present
        for f in same_files:
            if f.lock:
                raise error.RunError(70)    
    elif lock == 'RW':  # LOCK READ WRITE
        raise error.RunError(70)    
    elif lock == 'S':   # SHARED
        for f in same_files:
            if not f.lock:
                raise error.RunError(70)       
    else:               # LOCK READ or LOCK WRITE
        for f in same_files:
            if f.access == lock or lock == 'RW':
                raise error.RunError(70)


#################################################################################


class BaseFile(object):
    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        # width=255 means line wrap
        self.fhandle = fhandle
        self.name = name
        self.number = number
        self.mode = mode.upper()
        self.access = access
        self.lock = lock
        self.lock_list = set()    
        if number != 0:
            files[number] = self
    
    # set_width
    # width
    # col
    # lof
    # loc
    # eof

    def close(self):
        self.fhandle.flush()
        # don't close the handle - for devices
        if self.number != 0:
            del files[self.number]
    
    def read_chars(self, num):
        return list(self.fhandle.read(num)) 
        
    def read(self, num):
        return ''.join(self.read_chars(num))
    
    def read_line(self):
        out = ''
        while True:
            c = self.read(1)
            if c == '\r':
                break
            out += c
        return out            
            
    def peek_char(self):
        s = self.fhandle.read(1)
        self.fhandle.seek(-len(s), 1)
        return s
    
    def tell(self):
        return self.fhandle.tell()
        
    def seek(self, num, from_where=0):    
        self.fhandle.seek(num, from_where)
    
    def write(self, s):
        self.fhandle.write(str(s))
    
    def write_line(self, s=''):
        self.write(str(s) + '\r\n')    

    def end_of_file(self):
        return self.peek_char() == ''
        
    def flush(self):
        self.fhandle.flush()

    def truncate(self):
        self.fhandle.truncate()

class TextFile(BaseFile):
    def __init__(self, fhandle, name='', number=0, mode='A', access='RW', lock=''):
        BaseFile.__init__(self, fhandle, name, number, mode, access, lock)
        if self.mode in ('I', 'O', 'R', 'S', 'L'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
        # width=255 means line wrap
        self.width = 255
        self.col = 1
    
    def close(self):
        if self.mode in ('O', 'A', 'S'):
            # write EOF char
            self.fhandle.write('\x1a')
        BaseFile.close(self)
        self.fhandle.close()
        
    # read line    
    def read_line(self):
        if self.end_of_file():
            # input past end
            raise error.RunError(62)
        # readline breaks line on LF, we can only break on CR or CRLF
        s = ''
        while True:
            c = self.fhandle.read(1)
            if c in ('', '\x1a'):
                break
            elif c == '\n':
                s += c
                # special: allow LFCR (!) to pass
                if self.peek_char() == '\r':
                    self.fhandle.read(1)
                    s += '\r'
            elif c == '\r':
                # check for CR/LF
                if self.peek_char() == '\n':
                    self.fhandle.read(1)
                break
            else:        
                s += c    
        return s

    def read_chars(self, num):
        s = []
        for _ in range(num):
            c = self.fhandle.read(1)
            # check for \x1A (EOF char - this will actually stop further reading (that's true in files but not devices)
            if c in ('\x1a', ''):
                # input past end
                raise error.RunError(62)
            s.append(c)
        return s 
        
    # write one or more chars
    def write(self, s):
        for c in str(s):
            if self.col >= self.width and self.width != 255:  # width 255 means wrapping enabled
                self.fhandle.write('\r\n')
                self.flush()
                self.col = 1
            if c in ('\n', '\r'): # don't replace with CRLF when writing to files
                self.fhandle.write(c)
                self.flush()
                self.col = 1
            elif c == '\b':   # BACKSPACE
                if self.col > 1:
                    self.col -= 1
                    self.seek(-1, 1)
                    self.truncate()  
            else:    
                self.fhandle.write(c)
                # nonprinting characters including tabs are not counted for WIDTH
                # for lpt1 and files , nonprinting chars are not counted in LPOS; but chr$(8) will take a byte out of the buffer
                if ord(c) >= 32:
                    self.col += 1

    def set_width(self, new_width=255):
        self.width = new_width
    
    # for internal use    
    def end_of_file(self):
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def eof(self):
        # for EOF(i)
        if self.mode in ('A', 'O'):
            return False
        return (util.peek(self.fhandle) in ('', '\x1a'))
    
    def loc(self):
        # for LOC(i)
        if self.mode == 'I':
            return max(1, (127+self.fhandle.tell())/128)
        return self.fhandle.tell()/128

    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0, 2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        return lof


class RandomBase(BaseFile):
    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        BaseFile.__init__(self, fhandle, name, number, mode, access, lock)
        self.reclen = reclen
        if self.mode in ('I', 'O', 'R', 'S', 'L'):
            self.fhandle.seek(0)
        else:
            self.fhandle.seek(0, 2)
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
    
    # write one or more chars to field buffer
    def write(self, s):
        ins = StringIO(s)
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell() < len(s):
            raise error.RunError(self.overflow_error) 
    
    def peek_char(self):
        return self.field_text_file.peek_char()
    
    def seek(self, n, from_where):
        return self.field_text_file.seek(n, from_where)
        
    def truncate(self):
    # this is only used when writing chr$(8), not sure how to implement for random files
        pass
        
    @property
    def col(self):
        return self.field_text_file.col
    
    @property
    def width(self):
        return self.field_text_file.width
    
    def set_width(self, new_width=255):
        self.field_test_file.width = new_width

        
class RandomFile(RandomBase):
    # FIELD overflow
    overflow_error = 50
    
    def __init__(self, fhandle, name, number, mode, access, lock, reclen=128):
        RandomBase.__init__(self, fhandle, name, number, mode, access, lock, reclen=128)
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

#################################################################################

'''ByteStream is a StringIO-like wrapper for bytearray '''        
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

