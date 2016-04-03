"""
PC-BASIC - memory.py
Model memory

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import error
import var
import vartypes

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


class Memory(object):
    """ Memory model. """

    def __init__(self, bytecode, total_memory, reserved_memory, max_reclen, max_files):
        """ Initialise memory. """
        self.segment = data_segment
        # program buffer is initialised elsewhere
        self.bytecode = bytecode
        # BASIC stack (determined by CLEAR)
        # Initially, the stack space should be set to 512 bytes,
        # or one-eighth of the available memory, whichever is smaller.
        self.stack_size = 512
        # total size of data segment (set by CLEAR)
        self.total_memory = total_memory
        # first field buffer address (workspace size; 3429 for gw-basic)
        self.field_mem_base = reserved_memory
        # file header (at head of field memory)
        file_header_size = 194
        # bytes distance between field buffers
        self.field_mem_offset = file_header_size + max_reclen
        # start of 1st field =3945, includes FCB & header header of 1st field
        # used by var.py
        self.field_mem_start = self.field_mem_base + self.field_mem_offset + file_header_size
        # data memory model: start of code section
        # code_start+1: offsets in files (4718 == 0x126e)
        self.code_start = self.field_mem_base + (max_files+1) * self.field_mem_offset
        # scalar space
        self.scalars = var.Scalars(self)
        # array space
        self.arrays = var.Arrays(self)
        # string space
        self.strings = var.StringSpace(self)

    def clear_variables(self, preserve_vars, preserve_arrays, new_strings):
        """ Reset and clear variables, arrays, common definitions and functions. """
        # preserve COMMON variables
        # this is a re-assignment which is not FOR-safe;
        # but clear_variables is only called in CLEAR which also clears the FOR stack
        with self.scalars.preserve(preserve_vars, new_strings):
            self.scalars.clear()
        with self.arrays.preserve(preserve_arrays, new_strings):
            self.arrays.clear()
        if not(preserve_vars or preserve_arrays):
            # clear OPTION BASE
            self.arrays.clear_base()

    def get_free(self):
        """ Return the amount of memory available to variables, arrays, strings and code. """
        return self.strings.current - self.var_current() - self.arrays.current

    def collect_garbage(self):
        """ Collect garbage from string space. Compactify string storage. """
        # find all strings that are actually referenced
        string_ptrs = self.scalars.get_strings() + self.arrays.get_strings()
        self.strings.collect_garbage(string_ptrs)

    def check_free(self, size, err):
        """ Check if sufficient free memory is avilable, raise error if not. """
        if self.get_free() <= size:
            self.collect_garbage()
            if self.get_free() <= size:
                raise error.RunError(err)

    def var_start(self):
        """ Start of variable data. """
        return self.code_start + self._code_size()

    def var_current(self):
        """ Current variable pointer."""
        return self.var_start() + self.scalars.current

    def _code_size(self):
        """ Size of code space """
        return len(self.bytecode.getvalue())

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
        if new_size > self.total_memory:
            return False
        self.total_memory = new_size
        return True

    def get(self, address):
        """ Retrieve data from data memory. """
        address -= data_segment * 0x10
        if address < self.var_current():
            return self.scalars.get_memory(address)
        elif address < self.var_current() + self.arrays.current:
            return self.arrays.get_memory(address)
        elif address > self.strings.current:
            return self.strings.get_memory(address)
        else:
            # unallocated var space
            return -1


    ###############################################################################
    # generic variable access

    def get_variable(self, name, indices):
        """ Retrieve the value of a scalar variable or an array element. """
        if indices == []:
            return self.scalars.get(name)
        else:
            # array is allocated if retrieved and nonexistant
            return self.arrays.get(name, indices)

    def set_variable(self, name, indices, value):
        """ Assign a value to a scalar variable or an array element. """
        if indices == []:
            self.scalars.set(name, value)
        else:
            self.arrays.set(name, indices, value)

    def varptr(self, name, indices):
        """ Get address of variable. """
        if indices == []:
            return self.scalars.varptr(name)
        else:
            return self.arrays.varptr(name, indices)

    def dereference(self, address):
        """ Get a value for a variable given its pointer address. """
        found = self.scalars.dereference(address)
        if found is not None:
            return found
        # no scalar found, try arrays
        found = self.arrays.dereference(address)
        if found is not None:
            return found
        raise error.RunError(error.IFC)

    def get_value_for_varptrstr(self, varptrstr):
        """ Get a value given a VARPTR$ representation. """
        if len(varptrstr) < 3:
            raise error.RunError(error.IFC)
        varptrstr = bytearray(varptrstr)
        varptr = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(varptrstr[1:3]))
        return self.dereference(varptr)

    def swap(self, name1, index1, name2, index2):
        """ Swap two variables. """
        if name1[-1] != name2[-1]:
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        elif ((index1 == [] and name1 not in self.scalars.variables) or
                (index1 != [] and name1 not in self.arrays.arrays) or
                (index2 == [] and name2 not in self.scalars.variables) or
                (index2 != [] and name2 not in self.arrays.arrays)):
            # illegal function call
            raise error.RunError(error.IFC)
        typechar = name1[-1]
        size = vartypes.byte_size[typechar]
        # get buffers (numeric representation or string pointer)
        if index1 == []:
            p1, off1 = self.scalars.variables[name1], 0
        else:
            dimensions, p1, _ = self.arrays.arrays[name1]
            off1 = self.arrays.index(index1, dimensions)*size
        if index2 == []:
            p2, off2 = self.scalars.variables[name2], 0
        else:
            dimensions, p2, _ = self.arrays.arrays[name2]
            off2 = self.arrays.index(index2, dimensions)*size
        # swap the contents
        p1[off1:off1+size], p2[off2:off2+size] =  p2[off2:off2+size], p1[off1:off1+size]
        # inc version
        if name1 in self.arrays.arrays:
            self.arrays.arrays[name1][2] += 1
        if name2 in self.arrays.arrays:
            self.arrays.arrays[name2][2] += 1
