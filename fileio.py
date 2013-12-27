#
# PC-BASIC 3.23 - fileio.py
#
# File I/O oeprations 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


import error
import var
import os
import StringIO

import util
import expressions
import oslayer


# file numbers
files = {}
# fields are preserved on file close, so have a separate store
fields= {}


# close all non-system files
def close_all():
    for f in files:
        if f > 0:
            files[f].fhandle.close()
        
        
# close all files
def close_all_all_all():
    for f in files:
        files[f].fhandle.close()
        
        
def get_file(number):        
    return files[number]

    
def open_system_text_file(unixpath, access='rb'):
    inst = TextFile()
    
    number = -1
    while number in files:
        number -= 1
            
    if 'W' in access.upper() and not os.path.exists(unixpath):
        tempf = oslayer.safe_open(unixpath,'wb')
        tempf.close() 
        
    inst.fhandle = oslayer.safe_open(unixpath, access)
    inst.number = number
    inst.access = access
    if 'W' in access.upper():
        inst.mode = 'O'
    else:
        inst.mode = 'I'
    inst.init()
    files[number] = inst


def device_open(number, device, mode='I', access='rb'):
    inst = device
    if number <0 or number>255:
        # bad file number
        raise error.RunError(52)
    if number in files:
        # file already open
        raise error.RunError(55)

    if device==None:
        # device unavailable
        raise error.RunError(68)

    inst.number = number
    inst.access = access
    inst.mode = mode.upper()
    
    files[number] = inst

   
def fopen(number, unixpath, mode='I', access='rb', reclen=128, lock='rw'):
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
    if 'W' in access.upper() and not os.path.exists(unixpath):
        tempf = oslayer.safe_open(unixpath,'wb')
        tempf.close() 
        
    inst.fhandle = oslayer.safe_open(unixpath, access)
    oslayer.safe_lock(inst.fhandle, access, lock)
    
    
    inst.number = number
    inst.access = access
    inst.mode = mode.upper()
    inst.init(reclen)
    files[number] = inst


def pseudo_textfile(stringio):
    # open a pseudo text file over a byte stream
    text_file = TextFile()
    text_file.fhandle = stringio
    #text_file.fhandle.seek(0)
    text_file.mode='P'
    text_file.init()
    return text_file        



            
def lock_file(thefile, lock, lock_start, lock_length):

    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
        
    if isinstance(thefile, TextFile):
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock)
    else:
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock, lock_start, lock_length)


class TextFile:

    # width=255 means line wrap
    width = 255
    col=1
    
    def get_stream(self):
        return self.fhandle
        
    def init(self, answer=42):
        if self.mode.upper() in ('I', 'O', 'R', 'P'):
            self.fhandle.seek(0)
        else:
            # self.mode == 'A' 
            self.fhandle.seek(0, 2)
        
        
    def close(self):
        if self.access=='wb':
            # write EOF char
            self.fhandle.write('\x1a')
        self.fhandle.close()
        del files[self.number]
    
    
        
    # read line    
    def read(self):
        if self.eof():
            # input past end
            raise error.RunError(62)

        # this breaks line on \x0A, we can only break on \x0D or \x0D\x0A
        #s = self.fhandle.readline()
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
        # eof error if len<num?
        #if len(s)<num:
            # input past end
            raise error.RunError(62)
        
        return s 
        
        
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
        last = ''
        for c in s:
                
            if self.col > self.width:
                s_out+= '\x0d\x0a'
                self.col=1
   
            if c in ('\x0a','\x0d'): # CR, LF
                s_out+=c
                self.col = 1
            else:    
                s_out+=c
                
            if ord(c)>=32:
                self.col+=1
                
            last=c    
        self.fhandle.write(s_out)



    def get_col(self):
        return self.col
    
    def set_width(self, new_width=255):
        self.width = new_width
    
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
        pass
 
 
class RandomFile:

    width = 255
    col=1
    
    # all text-file operations on a RANDOM file number actually work on the FIELD buffer
    def get_stream(self):
        return self.field_text_file.fhandle
    
    # read line (from field buffer)    
    def read(self):
        if self.field_text_file.fhandle.tell() >= self.reclen:

            raise error.RunError(50) # FIELD overflow
        return self.field_text_file.read()
        
    def read_chars(self, num):
        if self.field_text_file.fhandle.tell() + num > self.reclen:
            raise error.RunError(50) # FIELD overflow
        return self.field_text_file.read_chars(num)

    def peek_chars(self, num=1):
        return self.field_text_file.peek_chars(num)


    # write one or more chars to field buffer
    def write(self, s):
        ins = StringIO.StringIO(s)
        
        while self.field_text_file.fhandle.tell() < self.reclen:
            self.field_text_file.write(ins.read(1))
        if ins.tell()<len(s):
            raise error.RunError(50) # FIELD overflow
        
    
    def init(self, reclen=128):
        self.reclen = reclen
        self.recpos=0
        self.fhandle.seek(0)
        if self.number in fields:
            self.field = fields[self.number]
        else:
            self.field = var.create_string_ptr('\x00'*reclen,0, self.reclen)
            fields[self.number] = self.field
            
        # open a pseudo text file over the buffer stream
        # to make WRITE# etc possible
        self.field_text_file = pseudo_textfile(self.field.stream)
        
        
    def close(self):
        self.fhandle.close()
        del files[self.number]
        
    # read record    
    def read_field(self):
        self.field.stream.seek(0)
        if self.eof():
            self.field.stream.write('\x00'*self.reclen)
        else:
            self.field.stream.write(self.fhandle.read(self.reclen))
        self.recpos += 1
        self.field.stream.seek(0)
#        self.field_text_file.fhandle.seek(0)
        return True
        
    #write record
    def write_field(self):
        current_length = self.lof()
        if self.recpos > current_length:
            self.fhandle.seek(0,2)
            numrecs = self.recpos-current_length
            self.fhandle.write('\x00'*numrecs*self.reclen)
        self.fhandle.write(str(self.field))
        self.recpos+=1
        
        self.field.stream.seek(0)
#        self.field_text_file.fhandle.seek(0)
        
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
        
        return self.recpos*self.reclen> self.lof() #   util.peek(self.fhandle)==''
            
    def lof(self):
        current = self.fhandle.tell()
        self.fhandle.seek(0,2)
        lof = self.fhandle.tell()
        self.fhandle.seek(current)
        
        return lof
        
    def flush(self):
        pass
            
            

