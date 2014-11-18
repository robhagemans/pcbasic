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
# 3757      188         1st file header
#           128         1st file FIELD record (smaller or larger depending on /s)
# 4073      188         2nd file header
#           128         2nd file FIELD record
# 4389      188         3rd file header
#           128         3rd file FIELD record
#                       ... (more or fewer files depending on /f)
# 4705      13          unknown       
# 4718      2+c         program code
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
    global field_mem_start, field_mem_offset, code_start, stack_size
    # length of field record (by default 128)
    file_rec_len = config.options['max-reclen']
    # file header (at head of field memory)
    file_header_size = 188
    # number of file records
    num_files = config.options['max-files']
    # first field buffer address 
    field_mem_base = 3757
    # start of 1st field =3945, includes 188-byte header of 1st field
    field_mem_start = field_mem_base + file_header_size
    # bytes distance between field buffers
    field_mem_offset = file_header_size + file_rec_len
    # data memory model: start of code section
    code_start = field_mem_base + num_files * field_mem_offset + 13
    # BASIC stack (determined by CLEAR)
    stack_size = 512 + 4 

def code_size():
    """ Size of code space """
    return len(state.basic_state.bytecode.getvalue()) - 1 

def var_start():
    """ Start of var space """
    return code_start + code_size()

def stack_start():
    """ Top of string space; start of stack space """
    return total - stack_size
    
prepare()


