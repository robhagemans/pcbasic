"""
PC-BASIC - memory.py
Model memory

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
from contextlib import contextmanager
from collections import deque

from ..base import error
from ..base import tokens as tk
from .. import values
from . import scalars
from . import arrays


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


############################################################################
# FIELD buffers

class Field(object):
    """Buffer for FIELD access."""

    def __init__(self, reclen, number=0, memory=None):
        """Set up empty FIELD buffer."""
        if number > 0:
            self.address = memory.field_mem_start + (number-1)*memory.field_mem_offset
        else:
            self.address = -1
        self.buffer = bytearray(reclen)
        self.memory = memory

    def attach_var(self, name, indices, offset, length):
        """Attach a FIELD variable."""
        if self.address < 0 or self.memory == None:
            raise AttributeError("Can't attach variable to non-memory-mapped field.")
        if name[-1] != values.STR:
            # type mismatch
            raise error.BASICError(error.TYPE_MISMATCH)
        if offset + length > len(self.buffer):
            # FIELD overflow
            raise error.BASICError(error.FIELD_OVERFLOW)
        # create a string pointer
        str_addr = self.address + offset
        str_sequence = struct.pack('<BH', length, str_addr)
        # assign the string ptr to the variable name
        # desired side effect: if we re-assign this string variable through LET, it's no longer connected to the FIELD.
        self.memory.set_variable(name, indices, self.memory.values.from_bytes(str_sequence))


class DataSegment(object):
    """Memory model."""

    # data memory model: data segment
    # location depends on which flavour of BASIC we use (this is for GW-BASIC)
    data_segment = 0x13ad

    # protection flag
    protection_flag_addr = 1450

    def __init__(self, total_memory, reserved_memory, max_reclen, max_files, double):
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
        # string space
        self.strings = values.StringSpace(self)
        # prepare string and number handler
        self.values = values.Values(self.strings, double)
        # scalar space
        self.scalars = scalars.Scalars(self, self.values)
        # array space
        self.arrays = arrays.Arrays(self, self.values)
        # temporary values
        self._stack = []
        # FIELD buffers
        self.reset_fields()

    def set_buffers(self, program):
        """Register program and variables."""
        self.program = program

    def reset_fields(self):
        """Reset FIELD buffers."""
        self.fields.clear()
        # fields are indexed by BASIC file number, hence max_files+1
        # file 0 (program/system file) probably doesn't need a field
        for i in range(self.max_files+1):
            self.fields[i+1] = Field(self.max_reclen, i+1, self)

    @contextmanager
    def get_stack(self):
        """Reset temporary variables and return a (mutable) deque to use as stack."""
        self._stack.append(deque())
        yield self._stack[-1]
        self._stack.pop()

    def clear_deftype(self):
        """Reset default sigils."""
        self.deftype = ['!']*26

    def deftype_(self, sigil, args):
        """DEFSTR/DEFINT/DEFSNG/DEFDBL: set type defaults for variables."""
        for start, stop in args:
            start = ord(start.upper()) - ord('A')
            if stop:
                stop = ord(stop.upper()) - ord('A')
            else:
                stop = start
            self.deftype[start:stop+1] = [sigil] * (stop-start+1)

    def defint_(self, args):
        """Set default integer variables."""
        self.deftype_(values.INT, args)

    def defsng_(self, args):
        """Set default single variables."""
        self.deftype_(values.SNG, args)

    def defdbl_(self, args):
        """Set default souble variables."""
        self.deftype_(values.DBL, args)

    def defstr_(self, args):
        """Set default string variables."""
        self.deftype_(values.STR, args)

    def clear(self, preserve_base, preserve_deftype):
        """Reset and clear variables, type definitions, array base and fields."""
        if not preserve_deftype:
            # deftype is not preserved on CHAIN with ALL, but is preserved with MERGE
            self.clear_deftype()
        # clear arrays, scalars and string space
        self.scalars.clear()
        self.arrays.clear()
        self.strings.clear()
        if not(preserve_base):
            # clear OPTION BASE
            self.arrays.clear_base()
        # release all disk buffers (FIELD)?
        self.reset_fields()

    @contextmanager
    def preserve_commons(self, preserve_common, preserve_all):
        """Preserve COMMON variables."""
        # preserve COMMON variables
        if preserve_all:
            preserve_sc, preserve_ar = self.scalars, self.arrays
        elif preserve_common:
            preserve_sc, preserve_ar = preserve_common
        else:
            preserve_sc, preserve_ar = set(), set()
        string_store = values.StringSpace(self)
        # preserve scalars
        common_scalars = {
                name: self.scalars.get(name)
                for name in preserve_sc if name in self.scalars}
        for name, value in common_scalars.iteritems():
            if name[-1] == values.STR:
                length, address = self.strings.copy_to(string_store, *value.to_pointer())
                value = self.values.new_string().from_pointer(length, address)
                common_scalars[name] = value
        # preserve arrays
        common_arrays = {
                name: (self.arrays.dimensions(name), bytearray(self.arrays.view_full_buffer(name)))
                for name in preserve_ar if name in self.arrays}
        for name, value in common_arrays.iteritems():
            if name[-1] == values.STR:
                dimensions, buf = value
                for i in range(0, len(buf), 3):
                    # if the string array is not full, pointers are zero
                    # but address is ignored for zero length
                    length, address = self.strings.copy_to(
                                string_store, *struct.unpack('<BH', buf[i:i+3]))
                    # modify the stored bytearray
                    buf[i:i+3] = struct.pack('<BH', length, address)
        yield
        # check if there is sufficient memory
        scalar_size = sum(self.scalars.memory_size(name)
                            for name in common_scalars.iterkeys())
        array_size = sum(self.arrays.memory_size(name, val[0])
                            for name, val in common_arrays.iteritems())
        if self.var_start() + scalar_size + array_size > string_store.current:
            raise error.BASICError(error.OUT_OF_MEMORY)
        self.strings.rebuild(string_store)
        for name, value in common_scalars.iteritems():
            self.scalars.set(name, value)
        for name, value in common_arrays.iteritems():
            dimensions, buf = value
            self.arrays.allocate(name, dimensions)
            # copy the array buffers back
            self.arrays.view_full_buffer(name)[:] = buf

    def _get_free(self):
        """Return the amount of memory available to variables, arrays, strings and code."""
        return self.strings.current - self.var_current() - self.arrays.current

    def _collect_garbage(self):
        """Collect garbage from string space. Compactify string storage."""
        # find all strings that are actually referenced
        stack_strings = [value.view() for stack in self._stack for value in stack if isinstance(value, values.String)]
        string_ptrs = self.scalars.get_strings() + self.arrays.get_strings() + stack_strings
        self.strings.collect_garbage(string_ptrs)

    def check_free(self, size, err):
        """Check if sufficient free memory is avilable, raise error if not."""
        if self._get_free() <= size:
            self._collect_garbage()
            if self._get_free() <= size:
                raise error.BASICError(err)

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
        if new_stack_size == 0:
            raise error.BASICError(error.IFC)
        self.stack_size = new_stack_size

    def set_basic_memory_size(self, new_size):
        """Set the data memory size (on CLEAR) """
        if new_size == 0:
            raise error.BASICError(error.IFC)
        elif new_size < 0:
            new_size += 0x10000
        if new_size > self.total_memory:
            raise error.BASICError(error.OUT_OF_MEMORY)
        self.total_memory = new_size

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
        if name and name[-1] not in tk.SIGILS:
            name += self.deftype[ord(name[0].upper()) - ord('A')]
        return name

    def view_or_create_variable(self, name, indices):
        """Retrieve the value of a scalar variable or an array element."""
        name = self.complete_name(name)
        if indices == []:
            return self.scalars.get(name)
        else:
            # array is allocated if retrieved and nonexistant
            return self.arrays.get(name, indices)

    def let_(self, args):
        """LET: assign value to variable or array."""
        name, indices = next(args)
        name = self.complete_name(name)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            # e.g. 'a[1,1]' gives a syntax error, but even so 'a[1]' is out of range afterwards
            self.arrays.check_dim(name, indices)
        value = next(args)
        if isinstance(value, values.String):
            # if already permanent, store a deep copy to avoid double referencing
            if self.strings.is_permanent(value):
                value = value.new().from_str(value.dereference())
        self.set_variable(name, indices, value)

    def set_variable(self, name, indices, value):
        """Assign a value to a scalar variable or an array element."""
        # note that for strings, this assigns the pointer
        # but does not deep copy the string
        name = self.complete_name(name)
        if indices == []:
            self.scalars.set(name, value)
        else:
            self.arrays.set(name, indices, value)

    def varptr(self, name, indices):
        """Get address of variable."""
        # this is an evaluation-time determination
        # as we could have passed another DEFtype statement
        name = self.complete_name(name)
        try:
            if indices == []:
                return self.scalars.varptr(name)
            else:
                return self.arrays.varptr(name, indices)
        except KeyError:
            raise error.BASICError(error.IFC)

    def varptr_(self, args):
        """VARPTR: get memory address for variable or FCB."""
        arg0 = next(args)
        if isinstance(arg0, values.Number):
            filenum = values.to_int(arg0)
            error.range_check(0, 255, filenum)
            error.throw_if(filenum > self.max_files, error.BAD_FILE_NUMBER)
            list(args)
            # file number 0 is allowed for VARPTR
            if filenum < 0 or filenum > self.max_files:
                raise error.BASICError(error.BAD_FILE_NUMBER)
            var_ptr = self.field_mem_base + filenum * self.field_mem_offset + 6
        else:
            name = arg0
            error.throw_if(not name, error.STX)
            indices, = args
            var_ptr = self.varptr(name, indices)
        return self.values.new_integer().from_int(var_ptr, unsigned=True)

    def varptr_str_(self, args):
        """VARPTR$: Get address of variable in string representation."""
        name = next(args)
        error.throw_if(not name, error.STX)
        indices = next(args)
        list(args)
        var_ptr = self.varptr(name, indices)
        vps = struct.pack('<BH', values.size_bytes(self.complete_name(name)), var_ptr)
        return self.values.new_string().from_str(vps)

    def dereference(self, address):
        """Get a value for a variable given its pointer address."""
        found = self.scalars.dereference(address)
        if found is not None:
            return found
        # no scalar found, try arrays
        found = self.arrays.dereference(address)
        if found is not None:
            return found
        raise error.BASICError(error.IFC)

    def get_value_for_varptrstr(self, varptrstr):
        """Get a value given a VARPTR$ representation."""
        if len(varptrstr) < 3:
            raise error.BASICError(error.IFC)
        varptrstr = bytearray(varptrstr)
        varptr, = struct.unpack('<H', varptrstr[1:3])
        return self.dereference(varptr)

    def _view_buffer(self, name, indices, empty_err):
        """Retrieve a memoryview to a scalar variable or an array element's buffer."""
        if not indices:
            if name not in self.scalars:
                # variable will be allocated
                self.scalars.set(name)
                if empty_err:
                    raise error.BASICError(error.IFC)
            return self.scalars.view_buffer(name)
        else:
            # array will be allocated if retrieved and nonexistant
            return self.arrays.view_buffer(name, indices)

    def swap_(self, args):
        """Swap two variables."""
        name1, index1 = next(args)
        name2, index2 = next(args)
        name1, name2 = self.complete_name(name1), self.complete_name(name2)
        if name1[-1] != name2[-1]:
            # type mismatch
            raise error.BASICError(error.TYPE_MISMATCH)
        list(args)
        # get buffers (numeric representation or string pointer)
        left = self._view_buffer(name1, index1, False)
        right = self._view_buffer(name2, index2, True)
        # swap the contents
        left[:], right[:] = right.tobytes(), left.tobytes()
        # drop caches
        if name1 in self.arrays:
            self.arrays.set_cache(name1, None)
        if name2 in self.arrays:
            self.arrays.set_cache(name2, None)

    def fre_(self, args):
        """FRE: get free memory and optionally collect garbage."""
        val, = args
        if isinstance(val, values.String):
            # grabge collection if a string-valued argument is specified.
            self._collect_garbage()
        return self.values.new_single().from_int(self._get_free())

    def lset_(self, args):
        """LSET: assign string value in-place; left justified."""
        name, index = next(args)
        name = self.complete_name(name)
        v = values.pass_string(self.view_or_create_variable(name, index))
        # we're not using a temp string here
        # as it would delete the new string generated by lset if applied to a code literal
        s = values.pass_string(next(args))
        list(args)
        self.set_variable(name, index, v.lset(s, justify_right=False))

    def rset_(self, args):
        """RSET: assign string value in-place; right justified."""
        name, index = next(args)
        name = self.complete_name(name)
        v = values.pass_string(self.view_or_create_variable(name, index))
        # we're not using a temp string here
        # as it would delete the new string generated by lset if applied to a code literal
        s = values.pass_string(next(args))
        list(args)
        self.set_variable(name, index, v.lset(s, justify_right=True))

    def mid_(self, args):
        """MID$: set part of a string."""
        name, indices = next(args)
        name = self.complete_name(name)
        if indices != []:
            # pre-dim even if this is not a legal statement!
            self.arrays.check_dim(name, indices)
        start = values.to_int(next(args))
        num = next(args)
        if num is None:
            num = 255
        else:
            num = values.to_int(num)
        s = values.pass_string(self.view_or_create_variable(name, indices)).to_str()
        error.range_check(0, 255, num)
        if num > 0:
            error.range_check(1, len(s), start)
        # we're not using a temp string here
        # as it would delete the new string generated by midset if applied to a code literal
        val = values.pass_string(next(args))
        # ensure parsing is completed
        list(args)
        # copy new value into existing buffer if possible
        basic_str = self.view_or_create_variable(name, indices)
        self.set_variable(name, indices, basic_str.midset(start, num, val))
