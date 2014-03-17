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

long_modes = {'\x85': 'I', 'OUTPUT':'O', 'RANDOM':'R', 'APPEND':'A'}  # \x85 is INPUT
allowed_access_modes = { 'I':'R', 'O':'W', 'A':'RW' }
lock_list = set()

# close all files
def exec_reset(ins):
    fileio.close_all()
    util.require(ins, util.end_statement)

def exec_open(ins):
    first_expr = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
    mode, access, lock, reclen = 'R', '', 'rw', 128
    if util.skip_white_read_if(ins, (',',)):
        # first syntax
        try:
            mode = first_expr[0].upper()
            access = access_modes[mode]    
        except (IndexError, KeyError):
            # Bad file mode
            raise error.RunError(54)
        util.require_read(ins, (',',))
        number = expressions.parse_file_number_opthash(ins)
        util.require_read(ins, (',',))
        name = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
        if util.skip_white_read_if(ins, (',',)):
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    else:
        # second syntax
        name = first_expr
        if util.skip_white_read_if(ins, ('\x82',)): # FOR
            c = util.skip_white_read(ins)
            # read word
            word = ''
            while c not in util.whitespace:
                word += c
                c = ins.read(1).upper()
            try:
                mode = long_modes[word]
            except KeyError:
                raise error.RunError(2)
        if util.skip_white_read_if(ins, ('ACCESS',)):
            d = util.skip_white(ins)
            if d == '\xB7': # WRITE
                ins.read(1)
                access = 'W'        
            elif d == '\x87': # READ
                ins.read(1)
                access = 'RW' if util.skip_white_read_if(ins, ('\xB7',)) else 'R' # WRITE
        # lock clause
        if util.skip_white_read_if(ins, ('\xFE\xA7',)): # LOCK
            d = util.skip_white(ins)
            if d == '\xB7': # WRITE
                ins.read(1)
                lock = 'w'        
            elif d == '\x87': # READ
                ins.read(1)
                lock = 'rw' if util.skip_white_read_if(ins, ('\xB7',)) else 'r' # READ WRITE
        elif util.skip_white_read_if(ins, ('SHARED',)):
            lock = ''     
        if not util.skip_white_read_if(ins, ('AS',)):
            raise error.RunError(2)
        number = expressions.parse_file_number_opthash(ins)
        if util.skip_white_read_if(ins, ('\xFF\x92',)):  # LEN
            util.require_read(ins, '\xE7') # =
            reclen = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    # mode and access must match if not a RANDOM file
    # If FOR APPEND ACCESS WRITE is specified, raises PATH/FILE ACCESS ERROR
    # If FOR and ACCESS mismatch in other ways, raises SYNTAX ERROR.
    if mode == 'A' and access == 'W':
            raise error.RunError(75)
    elif mode != 'R' and access and access != allowed_access_modes[mode]:
        raise error.RunError(2)        
    util.range_check(1, 128, reclen)        
    fileio.open_file_or_device(number, name, mode, access, lock, reclen) 
    util.require(ins, util.end_statement)
                
def exec_close(ins):
    # allow empty CLOSE
    if util.skip_white(ins) in util.end_statement:
        return
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
            util.require_read(ins, ('AS',), err=5)
            name = util.get_var_name(ins)
            var.set_field_var(field, name, offset, width)         
            offset += width
            if not util.skip_white_read_if(ins, (',',)):
                break
    util.require(ins, util.end_statement)

def exec_put_file(ins):
    the_file = fileio.get_file(expressions.parse_file_number_opthash(ins), 'R')
    # for COM files
    num_bytes = the_file.reclen
    if util.skip_white_read_if(ins, (',',)):
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
    if util.skip_white_read_if(ins, (',',)):
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
    if util.skip_white_read_if(ins, (',',)):
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
    oslayer.safe(oslayer.lock, thefile.fhandle, 'rw', start, length)                   
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
    oslayer.safe(oslayer.unlock, thefile.fhandle, start, length)                   
    util.require(ins, util.end_statement)
    
# ioctl: not implemented
def exec_ioctl(ins):
    fileio.get_file(expressions.parse_file_number_opthash(ins))
    raise error.RunError(5)   
    
