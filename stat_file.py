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

import glob
import fileio
import error
import vartypes
import var
import expressions
import fp

from util import *
import oslayer


short_modes = ['I','O','R','A']
long_modes = ['\x85', 'OUTPUT', 'RANDOM', 'APPEND']  # \x85 is INPUT token
access = ['\x87', '\xB7', '\x87 \xB7'] # READ, WRITE, READ WRITE
lock_modes = ['SHARED', '\xFE\xA7 \x87', '\xFE\xA7 \xB7', '\xFE\xA7 \x87 \xB7'] # SHARED, LOCK READ, LOCK WRITE, LOCK READ WRITE

access_modes = { 'I':'rb', 'O':'wb', 'R': 'rwb', 'A': 'wb' }
position_modes = { 'I':0, 'O':0, 'R':0, 'A':-1 }

def parse_file_number_opthash(ins):
    if skip_white_read_if(ins, '#'):
        skip_white(ins)
    
    number = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    if number<0 or number>255:
        raise error.RunError(5)
        
    return number    

# close all files
def exec_reset(ins):
    fileio.close_all()
    require(ins, end_statement)


    
def exec_open(ins):
    
    first_expr = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
    
    
    d =skip_white(ins)
    if d==',':
        
        # first syntax
        mode = first_expr[0].upper()
        
        access= access_modes[mode]    
        position = position_modes[mode]
        
        require_read(ins, ',')
        number = parse_file_number_opthash(ins)
        require_read(ins, ',')
        
        name = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
      
        if skip_white_read_if(ins, ','):
            reclen = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]

    else:
        
        # second syntax
        name = first_expr

        mode='R' # RANDOM        
        if skip_white(ins) == '\x82': # FOR
            
            ins.read(1)
            c = skip_white_read(ins)
            
            # read word
            word=''
            while c not in whitespace:
                word += c
                c = ins.read(1) 
            
            
            if word.upper() not in long_modes:
                raise error.RunError(2)
            
            if word=='\x85':
                mode = 'I'
            else:
                mode = word[0].upper()           
            
            access= access_modes[mode]    
            position = position_modes[mode]
        
        # it seems to be *either* a FOR clause *or* an ACCESS clause is allowed
        elif skip_white(ins) == 'A': 
            if peek(ins, 6) != 'ACCESS':
                raise error.RunError(2)
            ins.read(6)
            position = 0
            
            d = skip_white(ins)
            if d == '\xB7': # WRITE
                access = 'wb'        
            elif d == '\x87': # READ
                if skip_white(ins) == '\xB7': # READ WRITE
                    access = 'rwb'
                else:
                    access = 'rb'
        
        # lock clause
        lock = 'rw'
        skip_white(ins) 
        if peek(ins,2)=='\xFE\xA7':
            ins.read(2)
            
            d = skip_white(ins)
            if d == '\xB7': # WRITE
                lock = 'w'        
            elif d == '\x87': # READ
                if skip_white(ins) == '\xB7': # READ WRITE
                    lock = 'rw'
                else:
                    lock = 'r'
        
        elif peek(ins,6)=='SHARED':
            ins.read(6)  
            lock=''     
            
        skip_white(ins)
        if peek(ins,2) != 'AS':
            raise error.RunError(2)
        ins.read(2)
        
        
        number = parse_file_number_opthash(ins)
        
        
        skip_white(ins)             
        if peek(ins,2) == '\xFF\x92':  #LEN
            ins.read(2)
            reclen = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    
    
    dev_name = name.upper().split(':')[0] + ':' 
    if ':' in name and dev_name in glob.devices or dev_name in glob.input_devices:
        if mode.upper() in ('O', 'A') and dev_name in glob.devices:
            fileio.device_open(number, glob.devices[dev_name], mode, access)
        elif mode.upper() in ('I') and dev_name in glob.input_devices:
            fileio.device_open(number, glob.input_devices[dev_name], mode, access)
        elif mode.upper() in ('R') and dev_name in glob.random_devices:
            fileio.device_open(number, glob.random_devices[dev_name], mode, access)
        
        else:
            # bad file mode
            raise error.RunError(54)
    else:    
        if 'R' in access.upper():    #=='r' or access=='rb':
            name = oslayer.dospath_read(name, '', 53)
        else:
            name = oslayer.dospath_write(name, '', 76)
             
                
        # open the file
        fileio.fopen(number, name, mode, access, lock)    
    
    require(ins, end_statement)

    
                
def exec_close(ins):
                    
    while True:
        number = parse_file_number_opthash(ins)
            
        if number in fileio.files:
            fileio.files[number].close()
        
        if skip_white(ins) != ',':
            break
            
    require(ins, end_statement)

         
            
def exec_field(ins):
    number = parse_file_number_opthash(ins)
        
    if number not in fileio.files:
        raise error.RunError(52)
        
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54)    
    
    if skip_white_read(ins) != ',':
        raise error.RunError(2)
    
    field = fileio.files[number].field 
    offset = 0    
    while True:
        
        width = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        if width<0 or width>255:
            raise error.RunError(5)
        
        skip_white(ins)
        if peek(ins,2).upper() != 'AS':
            raise error.RunError(5)
        ins.read(2)
        skip_white(ins)
        name = var.getvarname(ins)
        
        var.set_field_var(field, name, offset, width)         
        
        offset+= width
        
        if skip_white(ins) != ',':
            break
            
        ins.read(1)
            
    require(ins, end_statement)
        
        

def exec_put_file(ins):
    number = parse_file_number_opthash(ins)
        
    if number not in fileio.files:
        raise error.RunError(52)
        
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54)    
    
    if skip_white(ins) == ',':
        ins.read(1)
        pos = fp.round_to_int(fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))))
        if pos<1 or pos>2**25:   # not 2^32-1 as the manual boasts! pos-1 apparently needs to fit in a single-prec mantissa
            raise error.RunError(63)
        fileio.files[number].set_pos(pos)    
            
    
    fileio.files[number].write_field()    
        
    require(ins, end_statement)
        
            

def exec_get_file(ins):
    number = parse_file_number_opthash(ins)
        
    if number not in fileio.files:
        raise error.RunError(52)
        
    if fileio.files[number].mode.upper() != 'R':
        raise error.RunError(54)    
    
    if skip_white(ins) == ',':
        ins.read(1)
        pos = fp.round_to_int(fp.unpack(vartypes.pass_single_keep(expressions.parse_expression(ins))))
        if pos<1 or pos>2**25:   # not 2^32-1 as the manual boasts!
            raise error.RunError(63)
        fileio.files[number].set_pos(pos)    
            
    
    fileio.files[number].read_field()    
        
    require(ins, end_statement)
            
    

def do_lock(ins, lock='rw'):
    number = parse_file_number_opthash(ins)
    
    if number not in fileio.files:
        raise error.RunError(52)
    
    
    thefile =fileio.files[number]
    
    lock_start=0
    lock_length=0
    if skip_white_read_if(ins, ','):
        lock_start_rec = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        lock_start = (lock_start_rec-1)*thefile.reclen
        lock_length = thefile.reclen
    skip_white(ins)
    
    
    if peek(ins,2)=='TO':
        lock_stop_rec = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        lock_stop = lock_stop_rec*thefile.reclen
        lock_length = lock_stop-lock_start
    
    if isinstance(thefile, TextFile):
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock)
    else:
        oslayer.safe_lock(thefile.fhandle, thefile.access, lock, lock_start, lock_length)
                   
    require(ins, end_statement)
    
    return (thefile.fhandle,lock_start,lock_length)        
            
            
            
lock_list = []
            
def exec_lock(ins):
    lock_list.append(do_lock(ins, rw))
            
def exec_unlock(ins):
    unlock = do_lock(ins, '')
    
    # permission denied if the exact record range wasn't given before
    if unlock not in lock_list:
        raise error.RunError(70)
    else:
        lock_list.remove(unlock)    
    
    
    
