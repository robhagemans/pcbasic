"""
PC-BASIC - memory.py
Model memory

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
from contextlib import contextmanager

from . import error
from . import strings
from . import values
from . import devices
from . import basictoken as tk


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



class DataSegment(object):
    """Memory model."""

    # data memory model: data segment
    # location depends on which flavour of BASIC we use (this is for GW-BASIC)
    data_segment = 0x13ad

    # protection flag
    protection_flag_addr = 1450

    def __init__(self, total_memory, reserved_memory, max_reclen, max_files):
        """Initialise memory."""
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
        self.field_mem_start = self.field_mem_base + self.field_mem_offset + file_header_size
        # data memory model: start of code section
        # code_start+1: offsets in files (4718 == 0x126e)
        self.code_start = self.field_mem_base + (max_files+1) * self.field_mem_offset
        # default sigils for names
        self.deftype = ['!']*26
        # FIELD buffers
        self.max_files = max_files
        self.max_reclen = max_reclen
        self.fields = {}
        self.reset_fields()

    def set_buffers(self, program, scalars, arrays, strings, values):
        """Register program and variables."""
        self.scalars = scalars
        self.arrays = arrays
        self.strings = strings
        self.program = program
        self.values = values

    def reset_fields(self):
        """Reset FIELD buffers."""
        self.fields.clear()
        # fields are indexed by BASIC file number, hence max_files+1
        # file 0 (program/system file) probably doesn't need a field
        for i in range(self.max_files+1):
            self.fields[i+1] = devices.Field(self.max_reclen, i+1, self)

    def clear_deftype(self):
        """Reset default sigils."""
        self.deftype = ['!']*26

    def set_deftype(self, start, stop, sigil):
        """Set default sigils."""
        start = ord(start.upper()) - ord('A')
        stop = ord(stop.upper()) - ord('A')
        self.deftype[start:stop+1] = [sigil] * (stop-start+1)

    def clear_variables(self, preserve_sc, preserve_ar):
        """Reset and clear variables, arrays, common definitions and functions."""
        new_strings = strings.StringSpace(self)
        # preserve COMMON variables
        # this is a re-assignment which is not FOR-safe;
        # but clear_variables is only called in CLEAR which also clears the FOR stack
        with self._preserve_scalars(preserve_sc, new_strings):
            self.scalars.clear()
        with self._preserve_arrays(preserve_ar, new_strings):
            self.arrays.clear()
        # clear old dict and copy into
        self.strings.clear()
        self.strings.strings.update(new_strings.strings)
        if not(preserve_sc or preserve_ar):
            # clear OPTION BASE
            self.arrays.clear_base()

    @contextmanager
    def _preserve_arrays(self, names, string_store):
        """Preserve COMMON variables."""
        common = {name:value for name, value in self.arrays.arrays.iteritems() if name in names}
        yield
        for name, value in common.iteritems():
            dimensions, buf, _ = value
            self.arrays.dim(name, dimensions)
            if name[-1] == '$':
                s = bytearray()
                for i in range(0, len(buf), 3):
                    ptr = values.Values.from_bytes(buf[i:i+3])
                    # if the string array is not full, pointers are zero
                    # but address is ignored for zero length
                    ptr = string_store.store(self.strings.copy(ptr))
                    s += values.Values.to_bytes(ptr)
                self.arrays.arrays[name][1] = s
            else:
                self.arrays.arrays[name] = value

    @contextmanager
    def _preserve_scalars(self, names, string_store):
        """Preserve COMMON variables."""
        common = {name:value for name, value in self.scalars.variables.iteritems() if name in names}
        yield
        for name, value in common.iteritems():
            full_var = values.Values.from_bytes(value)
            if name[-1] == '$':
                full_var = string_store.store(self.strings.copy(full_var))
            self.scalars.set(name, full_var)

    def get_free(self):
        """Return the amount of memory available to variables, arrays, strings and code."""
        return self.strings.current - self.var_current() - self.arrays.current

    def collect_garbage(self):
        """Collect garbage from string space. Compactify string storage."""
        # find all strings that are actually referenced
        string_ptrs = self.scalars.get_strings() + self.arrays.get_strings()
        self.strings.collect_garbage(string_ptrs)

    def check_free(self, size, err):
        """Check if sufficient free memory is avilable, raise error if not."""
        if self.get_free() <= size:
            self.collect_garbage()
            if self.get_free() <= size:
                raise error.RunError(err)

    def var_start(self):
        """Start of variable data."""
        return self.code_start + self.program.size()

    def var_current(self):
        """Current variable pointer."""
        return self.var_start() + self.scalars.current

    def stack_start(self):
        """Top of string space; start of stack space """
        return self.total_memory - self.stack_size - 2

    def set_stack_size(self, new_stack_size):
        """Set the stack size (on CLEAR) """
        self.stack_size = new_stack_size

    def set_basic_memory_size(self, new_size):
        """Set the data memory size (on CLEAR) """
        if new_size < 0:
            new_size += 0x10000
        if new_size > self.total_memory:
            return False
        self.total_memory = new_size
        return True

    def get_memory(self, addr):
        """Retrieve data from data memory."""
        addr -= self.data_segment*0x10
        if addr >= self.var_start():
            # variable memory
            return max(0, self._get_var_memory(addr))
        elif addr >= self.code_start:
            # code memory
            return max(0, self.program.get_memory(addr))
        elif addr >= self.field_mem_start:
            # file & FIELD memory
            return max(0, self._get_field_memory(addr))
        else:
            # other BASIC data memory
            return max(0, self._get_basic_memory(addr))

    def set_memory(self, addr, val):
        """Set datat in data memory."""
        addr -= self.data_segment*0x10
        if addr >= self.var_start():
            # POKING in variables
            self._not_implemented_pass(addr, val)
        elif addr >= self.code_start:
            # code memory
            self.program.set_memory(addr, val)
        elif addr >= self.field_mem_start:
            # file & FIELD memory
            self._not_implemented_pass(addr, val)
        elif addr >= 0:
            self._set_basic_memory(addr, val)

    ###############################################################################
    # File buffer access

    def varptr_file(self, filenum):
        """Get address of FCB for a given file number."""
        if filenum < 1 or filenum > self.max_files:
            raise error.RunError(error.BAD_FILE_NUMBER)
        return self.field_mem_base + filenum * self.field_mem_offset + 6

    def _get_field_memory(self, address):
        """Retrieve data from FIELD buffer."""
        if address < self.field_mem_start:
            return -1
        # find the file we're in
        start = address - self.field_mem_start
        number = 1 + start // self.field_mem_offset
        offset = start % self.field_mem_offset
        try:
            return self.fields[number].buffer[offset]
        except (KeyError, IndexError):
            return -1

    ###########################################################################
    # other memory access

    def _get_var_memory(self, address):
        """Retrieve data from data memory."""
        if address < self.var_current():
            return self.scalars.get_memory(address)
        elif address < self.var_current() + self.arrays.current:
            return self.arrays.get_memory(address)
        elif address > self.strings.current:
            return self.strings.get_memory(address)
        else:
            # unallocated var space
            return -1

    def _get_basic_memory(self, addr):
        """Retrieve data from BASIC memory."""
        if addr < 4:
            # sentinel value, used by some programs to identify GW-BASIC
            return (0, 0, 0x10, 0x82)[addr]
        # DS:2c, DS:2d  end of memory available to BASIC
        elif addr == 0x2C:
            return self.total_memory % 256
        elif addr == 0x2D:
            return self.total_memory // 256
        # DS:30, DS:31: pointer to start of program, excluding initial \0
        elif addr == 0x30:
            return (self.code_start+1) % 256
        elif addr == 0x31:
            return (self.code_start+1) // 256
        # DS:358, DS:359: start of variable space
        elif addr == 0x358:
            return self.var_start() % 256
        elif addr == 0x359:
            return self.var_start() // 256
        # DS:35A, DS:35B: start of array space
        elif addr == 0x35A:
            return self.var_current() % 256
        elif addr == 0x35B:
            return self.var_current() // 256
        # DS:35C, DS:35D: end of array space
        elif addr == 0x35C:
            return (self.var_current() + self.arrays.current) % 256
        elif addr == 0x35D:
            return (self.var_current() + self.arrays.current) // 256
        elif addr == self.protection_flag_addr:
            return self.program.protected * 255
        return -1

    def _not_implemented_pass(self, addr, val):
        """POKE into not implemented location; ignore."""

    def _set_basic_memory(self, addr, val):
        """Change BASIC memory."""
        if addr == self.protection_flag_addr and self.program.allow_protect:
            self.program.protected = (val != 0)


    ###############################################################################
    # generic variable access

    def complete_name(self, name):
        """Add default sigil to a name, if missing."""
        if name and name[-1] not in tk.sigils:
            name += self.deftype[ord(name[0].upper()) - ord('A')]
        return name

    def get_variable(self, name, indices):
        """Retrieve the value of a scalar variable or an array element."""
        name = self.complete_name(name)
        if indices == []:
            return self.scalars.get(name)
        else:
            # array is allocated if retrieved and nonexistant
            return self.arrays.get(name, indices)

    def set_variable(self, name, indices, value):
        """Assign a value to a scalar variable or an array element."""
        name = self.complete_name(name)
        if indices == []:
            self.scalars.set(name, value)
        else:
            self.arrays.set(name, indices, value)

    def varptr(self, name, indices):
        """Get address of variable."""
        name = self.complete_name(name)
        if indices == []:
            return self.scalars.varptr(name)
        else:
            return self.arrays.varptr(name, indices)

    def dereference(self, address):
        """Get a value for a variable given its pointer address."""
        found = self.scalars.dereference(address)
        if found is not None:
            return found
        # no scalar found, try arrays
        found = self.arrays.dereference(address)
        if found is not None:
            return found
        raise error.RunError(error.IFC)

    def get_value_for_varptrstr(self, varptrstr):
        """Get a value given a VARPTR$ representation."""
        if len(varptrstr) < 3:
            raise error.RunError(error.IFC)
        varptrstr = bytearray(varptrstr)
        varptr, = struct.unpack('<H', varptrstr[1:3])
        return self.dereference(varptr)

    def _view_buffer(self, name, indices):
        """Retrieve a memoryview to a scalar variable or an array element's buffer."""
        if indices == []:
            if name not in self.scalars.variables:
                raise error.RunError(error.IFC)
            return memoryview(self.scalars.variables[name])
        else:
            if name not in self.arrays.arrays:
                raise error.RunError(error.IFC)
            # array would be allocated if retrieved and nonexistant
            return self.arrays.view_buffer(name, indices)

    def swap(self, name1, index1, name2, index2):
        """Swap two variables."""
        if name1[-1] != name2[-1]:
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        # get buffers (numeric representation or string pointer)
        left = self._view_buffer(name1, index1)
        right = self._view_buffer(name2, index2)
        # swap the contents
        left[:], right[:] = right.tobytes(), left.tobytes()
        # inc version
        if name1 in self.arrays.arrays:
            self.arrays.arrays[name1][2] += 1
        if name2 in self.arrays.arrays:
            self.arrays.arrays[name2][2] += 1
