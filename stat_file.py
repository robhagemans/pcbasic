#
# PC-BASIC 3.23 - stat_file.py
#
# File I/O statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import fileio
import error
import vartypes
import var
import expressions
import fp
import util
import oslayer
import deviceio

short_modes = ['I','O','R','A']
long_modes = ['\x85', 'OUTPUT', 'RANDOM', 'APPEND']  # \x85 is INPUT token
access_tokens = ['\x87', '\xB7', '\x87 \xB7'] # READ, WRITE, READ WRITE
lock_modes = ['SHARED', '\xFE\xA7 \x87', '\xFE\xA7 \xB7', '\xFE\xA7 \x87 \xB7'] # SHARED, LOCK READ, LOCK WRITE, LOCK READ WRITE

access_modes = { 'I':'rb', 'O':'wb', 'R':'r+b', 'A':'wb' }
position_modes = { 'I':0, 'O':0, 'R':0, 'A':-1 }
            
lock_list = {}

# close all files
def exec_reset(ins):
    fileio.close_all()
    util.require(ins, util.end_statement)

    
def exec_open(ins):
    first_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    d = util.skip_white(ins)
    if d==',':
        # first syntax
        mode = first_expr[0].upper()
        access = access_modes[mode]    
        util.require_read(ins, (',',))
        number = expressions.parse_file_number_opthash(ins)
        util.require_read(ins, (',',))
        name = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
        if util.skip_white_read_if(ins, ','):
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        # second syntax
        name = str(first_expr)
        mode = 'R' # RANDOM        
        if util.skip_white_read_if(ins, '\x82'): # FOR
            c = util.skip_white_read(ins)
            # read word
            word=''
            while c not in util.whitespace:
                word += c
                c = ins.read(1) 
            if word.upper() not in long_modes:
                raise error.RunError(2)
            if word=='\x85':
                mode = 'I'
            else:
                mode = word[0].upper()           
            access= access_modes[mode]    
        # it seems to be *either* a FOR clause *or* an ACCESS clause is allowed
        elif util.skip_white(ins) == 'A': 
            if util.peek(ins, 6) != 'ACCESS':
                raise error.RunError(2)
            ins.read(6)
            d = util.skip_white(ins)
            if d == '\xB7': # WRITE
                access = 'wb'        
            elif d == '\x87': # READ
                if util.skip_white(ins) == '\xB7': # READ WRITE
                    access = 'r+b'
                else:
                    access = 'rb'
        # lock clause
        lock = 'rw'
        util.skip_white(ins) 
        if util.peek(ins,2)=='\xFE\xA7':
            ins.read(2)
            d = util.skip_white(ins)
            if d == '\xB7': # WRITE
                lock = 'w'        
            elif d == '\x87': # READ
                if util.skip_white(ins) == '\xB7': # READ WRITE
                    lock = 'rw'
                else:
                    lock = 'r'
        elif util.peek(ins,6)=='SHARED':
            ins.read(6)  
            lock=''     
        util.skip_white(ins)
        if util.peek(ins,2) != 'AS':
            raise error.RunError(2)
        ins.read(2)
        number = expressions.parse_file_number_opthash(ins)
        util.skip_white(ins)             
        if util.peek(ins,2) == '\xFF\x92':  #LEN
            ins.read(2)
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    dev_name = name.upper().split(':')[0] + ':' 
    if deviceio.is_device(dev_name): 
        deviceio.device_open(number, dev_name, mode, access)
    else:    
        if access.upper()=='RB' or access.upper()=='R':
            name = oslayer.dospath_read(name, '', 53)
        else:
            name = oslayer.dospath_write(name, '', 76)
        # open the file
        fileio.open_file(number, name, mode, access, lock)    
    util.require(ins, util.end_statement)

    
                
def exec_close(ins):
    while True:
        number = expressions.parse_file_number_opthash(ins)
        if number in fileio.files:
            fileio.files[number].close()
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)

         
            
def exec_field(ins):
    number = expressions.parse_file_number_opthash(ins)
    if number not in fileio.files:
        raise error.RunError(52)
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54) 
    if util.skip_white_read_if(ins, (',',)):
        field = fileio.files[number].field 
        offset = 0    
        while True:
            width = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            if width<0 or width>255:
                raise error.RunError(5)
            util.skip_white(ins)
            if util.peek(ins,2).upper() != 'AS':
                raise error.RunError(5)
            ins.read(2)
            name = util.get_var_name(ins)
            var.set_field_var(field, name, offset, width)         
            offset += width
            if not util.skip_white_read_if(ins,','):
                break
    util.require(ins, util.end_statement)
        
        

def exec_put_file(ins):
    number = expressions.parse_file_number_opthash(ins)
    if number not in fileio.files:
        raise error.RunError(52)
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54)    
    if util.skip_white_read_if(ins, ','):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)).round_to_int())
        if pos<1 or pos>2**25:   # not 2^32-1 as the manual boasts! pos-1 apparently needs to fit in a single-prec mantissa
            raise error.RunError(63)
        fileio.files[number].set_pos(pos)    
    fileio.files[number].write_field()    
    util.require(ins, util.end_statement)
            

def exec_get_file(ins):
    number = expressions.parse_file_number_opthash(ins)
    if number not in fileio.files:
        raise error.RunError(52)
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54)    
    if util.skip_white_read_if(ins, ','):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
        if pos<1 or pos>2**25:   # not 2^32-1 as the manual boasts!
            raise error.RunError(63)
        fileio.files[number].set_pos(pos)    
    fileio.files[number].read_field()    
    util.require(ins, util.end_statement)


def parse_lock(ins):
    number = expressions.parse_file_number_opthash(ins)
    if number not in fileio.files:
        raise error.RunError(52)
    thefile = fileio.files[number]
    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
    lock_start=0
    lock_length=0
    if util.skip_white_read_if(ins, ','):
        lock_start_rec = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        lock_start = (lock_start_rec-1) * thefile.reclen
        lock_length = thefile.reclen
    util.skip_white(ins)
    if util.peek(ins,2)=='TO':
        ins.read(2)
        lock_stop_rec = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        lock_stop = lock_stop_rec * thefile.reclen
        lock_length = lock_stop - lock_start
    return thefile.number, lock_start, lock_length     
           
            
def exec_lock(ins):
    nr,start,length = parse_lock(ins) 
    lock_list.append((nr,start,length))
    fileio.lock_file(nr, 'rw', start, length)                   
    util.require(ins, util.end_statement)
           
            
def exec_unlock(ins):
    unlock = parse_lock(ins)
    # permission denied if the exact record range wasn't given before
    if unlock not in lock_list:
        raise error.RunError(70)
    else:
        lock_list.remove(unlock)
        (nr,start,length) = unlock    
        fileio.lock_file(nr, '', start, length)                   
        util.require(ins, util.end_statement)
    
    
