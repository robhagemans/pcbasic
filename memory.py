"""
PC-BASIC 3.23 - memory.py
Model memory

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import config
import state

# data memory model: data segment
# location depends on which flavour of BASIC we use (this is for GW-BASIC)
data_segment = 0x13ad
# lowest (EGA) video memory address
video_segment = 0xa000
# read only memory
rom_segment = 0xf000
# total size of data segment
total = 65536

# Data Segment Map - default situation
# addr      size
# 0         3757        workspace - undefined in PC-BASIC
# 3429      6           file 0 (the program) 6-byte header
#           188             FCB
#           128             FIELD buffer ??       
# 3751      6           1st file 6-byte header: 0, (66*filenum)%256, 0, 0, 0, 0
#           188             FCB
#           128             FIELD buffer (smaller or larger depending on /s)
# 4073      194         2nd file header + FCB
#           128         2nd file FIELD buffer
# 4395      194         3rd file header + FCB
#           128         3rd file FIELD buffer
#                       ... (more or fewer files depending on /f)
# 4717      3+c         program code, starting with \0, ending with \0\0
# 4720+c    v           scalar variables 
# 4720+c+v  a           array variables
# 65020-s               top of string space        
# 65020     4           unknown
# 65024     512         BASIC stack (size determined by CLEAR)
# NOTE - the last two sections may be the other way around (4 bytes at end)
# 65536                 total size



# program bytecode buffer
state.basic_state.bytecode = StringIO()
state.basic_state.bytecode.write('\0\0\0')

def prepare():
    """ Initialise the memory module """
    global field_mem_base, field_mem_start, field_mem_offset
    global code_start, stack_size
    # length of field record (by default 128)
    file_rec_len = config.options['max-reclen']
    # file header (at head of field memory)
    file_header_size = 194
    # number of file records
    num_files = config.options['max-files']
    # first field buffer address 
    field_mem_base = 3429
    # bytes distance between field buffers
    field_mem_offset = file_header_size + file_rec_len
    # start of 1st field =3945, includes FCB & header header of 1st field
    # used by var.py
    field_mem_start = field_mem_base + field_mem_offset + file_header_size
    # data memory model: start of code section
    code_start = field_mem_base + (num_files+1) * field_mem_offset
    # BASIC stack (determined by CLEAR)
    # Initially, the stack space should be set to 512 bytes, 
    # or one-eighth of the available memory, whichever is smaller.
    stack_size = 512

def code_size():
    """ Size of code space """
    return len(state.basic_state.bytecode.getvalue())

def var_start():
    """ Start of var space """
    return code_start + code_size()

def stack_start():
    """ Top of string space; start of stack space """
    return total - stack_size - 4

def set_stack_size(new_stack_size):
    """ Set the stack size (on CLEAR) """
    global stack_size
    stack_size = new_stack_size
    
prepare()


