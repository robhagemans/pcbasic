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
            
lock_list = set()

# close all files
def exec_reset(ins):
    fileio.close_all()
    util.require(ins, util.end_statement)

def exec_open(ins):
    first_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    d = util.skip_white(ins)
    if d == ',':
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
        if util.skip_white_read_if(ins, ('\x82',)): # FOR
            c = util.skip_white_read(ins)
            # read word
            word = ''
            while c not in util.whitespace:
                word += c
                c = ins.read(1) 
            if word.upper() not in long_modes:
                raise error.RunError(2)
            if word=='\x85':
                mode = 'I'
            else:
                mode = word[0].upper()           
            access = access_modes[mode]    
        # it seems to be *either* a FOR clause *or* an ACCESS clause is allowed
        # could be 'AS' too
        elif util.peek(ins,2) == 'AC': 
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
        else:
            # neither specified -> it is a RANDOM (or COM) file
            mode = 'R'
            access = access_modes[mode]
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
    fileio.open_dosname(number, name, mode, access, lock) 
    util.require(ins, util.end_statement)
                
def exec_close(ins):
    while True:
        number = expressions.parse_file_number_opthash(ins)
        try:    
            fileio.files[number].close()
        except KeyError:
            pass    
        if not util.skip_white_read_if(ins, (',',)):
            break
    util.require(ins, util.end_statement)
            
def exec_field(ins):
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    if util.skip_white_read_if(ins, (',',)):
        field = the_file.field 
        offset = 0    
        while True:
            width = vartypes.pass_int_unpack(expressions.parse_expression(ins))
            util.range_check(0, 255, width)
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
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, ','):
        pos = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins)).round_to_int())
        if pos<1 or pos>2**25:   # not 2^32-1 as the manual boasts! pos-1 apparently needs to fit in a single-prec mantissa
            raise error.RunError(63)
        if not isinstance(the_file, deviceio.SerialFile):
            the_file.set_pos(pos)    
        else:
            num_bytes = pos    
    the_file.write_field(num_bytes)
    util.require(ins, util.end_statement)

def exec_get_file(ins):
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, ','):
        pos = fp.unpack(vartypes.pass_double_keep(expressions.parse_expression(ins))).round_to_int()
        if pos < 1 or pos > 2**25:   
            raise error.RunError(63)
        if not isinstance(the_file, deviceio.SerialFile):
            the_file.set_pos(pos)
        else:
            # 'pos' means number of bytes for COM files
            num_bytes = pos                
    the_file.read_field(num_bytes)
    util.require(ins, util.end_statement)

def parse_lock(ins):
    thefile = fileio.get_file(expressions.parse_file_number_opthash(ins))
    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
    lock_start, lock_length = 0, 0
    lock_start_rec = 1
    if util.skip_white_read_if(ins, ','):
        lock_start_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
        lock_start = (lock_start_rec-1) * thefile.reclen
        lock_length = thefile.reclen
    util.skip_white(ins)
    lock_stop_rec = lock_start_rec
    if util.skip_white_read_if(ins, ('\xCC',)): # TO
        lock_stop_rec = fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))).round_to_int()
        lock_stop = lock_stop_rec * thefile.reclen
        lock_length = lock_stop - lock_start
    if lock_start_rec < 1 or lock_start_rec > 2**25-2 or lock_stop_rec < 1 or lock_stop_rec > 2**25-2:   
        raise error.RunError(63)
    return thefile.number, lock_start, lock_length     
                 
def exec_lock(ins):
    nr, start, length = parse_lock(ins) 
    thefile = fileio.get_file(nr)
    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
    if isinstance(thefile, fileio.TextFile):
        start, length = 0, 0
    else:
        for nr_1, start_1, length_1 in lock_list:
            if (start >= start_1 and start < start_1+length_1) or (start+length >= start_1 and start+length < start_1+length_1):
                raise error.RunError(70)
    lock_list.add((nr, start, length))
    oslayer.safe_lock(thefile.fhandle, 'rw', start, length)                   
    util.require(ins, util.end_statement)
            
def exec_unlock(ins):
    unlock = parse_lock(ins)
    nr, start, length = unlock    
    thefile = fileio.get_file(nr)
    if deviceio.is_device(thefile):
        # permission denied
        raise error.RunError(70)
    if isinstance(thefile, fileio.TextFile):
        start, length = 0, 0
    # permission denied if the exact record range wasn't given before
    try:
        lock_list.remove(unlock)
    except KeyError:
        raise error.RunError(70)
    oslayer.safe_lock(thefile.fhandle, '', start, length)                   
    util.require(ins, util.end_statement)
    
# ioctl: not implemented
def exec_ioctl(ins):
    fileio.get_file(expressions.parse_file_number_opthash(ins))
    raise error.RunError(5)   
    
    
