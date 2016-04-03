"""
PC-BASIC - memory.py
Model memory

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import config
import state
import error

# data memory model: data segment
# location depends on which flavour of BASIC we use (this is for GW-BASIC)
data_segment = 0x13ad
# lowest (EGA) video memory address; max 128k reserved for video
video_segment = 0xa000
# read only memory
rom_segment = 0xf000
# segment that holds ram font
ram_font_segment = 0xc000

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
# 65020     2           unknown
# 65022     512         BASIC stack (size determined by CLEAR)
# NOTE - the last two sections may be the other way around (2 bytes at end)
# 65534                 total size (determined by CLEAR)




def prepare():
    """ Initialise the memory module """
    global field_mem_base, field_mem_start, field_mem_offset
    global code_start, max_memory
    # length of field record (by default 128)
    file_rec_len = config.get('max-reclen')
    # file header (at head of field memory)
    file_header_size = 194
    # number of file records
    num_files = config.get('max-files')
    # first field buffer address (workspace size; 3429 for gw-basic)
    field_mem_base = config.get('reserved-memory')
    # bytes distance between field buffers
    field_mem_offset = file_header_size + file_rec_len
    # start of 1st field =3945, includes FCB & header header of 1st field
    # used by var.py
    field_mem_start = field_mem_base + field_mem_offset + file_header_size
    # data memory model: start of code section
    # code_start+1: offsets in files (4718 == 0x126e)
    code_start = field_mem_base + (num_files+1) * field_mem_offset
    # max available memory to BASIC (set by /m)
    max_list = config.get('max-memory')
    max_list[1] = max_list[1]*16 if max_list[1] else max_list[0]
    max_list[0] = max_list[0] or max_list[1]
    max_memory = min(max_list) or 65534


class Memory(object):
    """ Memory model. """

    def __init__(self, program):
        """ Initialise memory. """
        self.segment = data_segment
        # program buffer is initialised elsewhere
        self.program = program
        # BASIC stack (determined by CLEAR)
        # Initially, the stack space should be set to 512 bytes,
        # or one-eighth of the available memory, whichever is smaller.
        self.stack_size = 512
        # total size of data segment (set by CLEAR)
        self.total_memory = max_memory
        # current variable pointer
        self.var_current = self.var_start()

    def get_free(self):
        """ Return the amount of memory available to variables, arrays, strings and code. """
        return state.session.strings.current - self.var_current - state.session.arrays.current

    def collect_garbage(self):
        """ Collect garbage from string space. Compactify string storage. """
        # find all strings that are actually referenced
        string_ptrs = state.session.scalars.get_strings() + state.session.arrays.get_strings()
        state.session.strings.collect_garbage(string_ptrs)

    def check_free(self, size, err):
        """ Check if sufficient free memory is avilable, raise error if not. """
        if self.get_free() <= size:
            self.collect_garbage()
            if self.get_free() <= size:
                raise error.RunError(err)

    def var_start(self):
        """ Start of variable data. """
        return code_start + self._code_size()

    def _code_size(self):
        """ Size of code space """
        return len(self.program.bytecode.getvalue())

    def stack_start(self):
        """ Top of string space; start of stack space """
        return self.total_memory - self.stack_size - 2

    def set_stack_size(self, new_stack_size):
        """ Set the stack size (on CLEAR) """
        self.stack_size = new_stack_size

    def set_basic_memory_size(self, new_size):
        """ Set the data memory size (on CLEAR) """
        if new_size < 0:
            new_size += 0x10000
        if new_size > max_memory:
            return False
        self.total_memory = new_size
        return True

    def get(self, address):
        """ Retrieve data from data memory. """
        address -= data_segment * 0x10
        if address < self.var_current:
            return state.session.scalars.get_memory(address)
        elif address < self.var_current + state.session.arrays.current:
            return state.session.arrays.get_memory(address)
        elif address > state.session.strings.current:
            return state.session.strings.get_memory(address)
        else:
            # unallocated var space
            return -1


prepare()
