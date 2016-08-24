"""
PC-BASIC - arrays.py
Array variable management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from . import error
from . import values
from .scalars import get_name_in_memory


class Arrays(object):

    def __init__(self, memory, values):
        """Initialise arrays."""
        self.memory = memory
        self.values = values
        self.clear()
        # OPTION BASE is unset
        self.base_index = None

    def clear(self):
        """Clear arrays."""
        self.arrays = {}
        self.array_memory = {}
        self.current = 0

    def erase(self, name):
        """Remove an array from memory."""
        try:
            del self.arrays[name]
        except KeyError:
            # illegal fn call
            raise error.RunError(error.IFC)

    def index(self, index, dimensions):
        """Return the flat index for a given dimensioned index."""
        bigindex = 0
        area = 1
        for i in range(len(index)):
            # dimensions is the *maximum index number*, regardless of self.base_index
            bigindex += area*(index[i]-self.base_index)
            area *= (dimensions[i]+1-self.base_index)
        return bigindex

    def array_len(self, dimensions):
        """Return the flat length for given dimensioned size."""
        return self.index(dimensions, dimensions) + 1

    def array_size_bytes(self, name):
        """Return the byte size of an array, if it exists. Return 0 otherwise."""
        try:
            dimensions, _, _ = self.arrays[name]
        except KeyError:
            return 0
        return self.array_len(dimensions) * values.size_bytes(name)

    def dim(self, name, dimensions):
        """Allocate array space for an array of given dimensioned size. Raise errors if duplicate name or illegal index value."""
        if self.base_index is None:
            self.base_index = 0
        name = self.memory.complete_name(name)
        if name in self.arrays:
            raise error.RunError(error.DUPLICATE_DEFINITION)
        for d in dimensions:
            if d < 0:
                raise error.RunError(error.IFC)
            elif d < self.base_index:
                raise error.RunError(error.SUBSCRIPT_OUT_OF_RANGE)
        size = self.array_len(dimensions)
        # update memory model
        # first two bytes: chars of name or 0 if name is one byte long
        name_ptr = self.current
        record_len = 1 + max(3, len(name)) + 3 + 2*len(dimensions)
        array_ptr = name_ptr + record_len
        array_bytes = size*values.size_bytes(name)
        self.memory.check_free(record_len + array_bytes, error.OUT_OF_MEMORY)
        self.current += record_len + array_bytes
        self.array_memory[name] = (name_ptr, array_ptr)
        try:
            self.arrays[name] = [ dimensions, bytearray(array_bytes), 0 ]
        except OverflowError:
            # out of memory
            raise error.RunError(error.OUT_OF_MEMORY)
        except MemoryError:
            # out of memory
            raise error.RunError(error.OUT_OF_MEMORY)

    def check_dim(self, name, index):
        """Check if an array has been allocated. If not, auto-allocate if indices are <= 10; raise error otherwise."""
        try:
            dimensions, lst, _ = self.arrays[name]
        except KeyError:
            # auto-dimension - 0..10 or 1..10
            # this even fixes the dimensions if the index turns out to be out of range
            dimensions = [10] * len(index)
            self.dim(name, dimensions)
            dimensions, lst, _ = self.arrays[name]
        if len(index) != len(dimensions):
            raise error.RunError(error.SUBSCRIPT_OUT_OF_RANGE)
        for i, d in zip(index, dimensions):
            if i < 0:
                raise error.RunError(error.IFC)
            elif i < self.base_index or i > d:
                # dimensions is the *maximum index number*, regardless of self.base_index
                raise error.RunError(error.SUBSCRIPT_OUT_OF_RANGE)
        return dimensions, lst

    def clear_base(self):
        """Unset the array base."""
        self.base_index = None

    def base(self, base):
        """Set the array base to 0 or 1 (OPTION BASE). Raise error if already set."""
        if base not in (1, 0):
            # syntax error
            raise error.RunError(error.STX)
        if self.base_index is not None and base != self.base_index:
            # duplicate definition
            raise error.RunError(error.DUPLICATE_DEFINITION)
        self.base_index = base

    def view(self, name, index):
        """Return a memoryview to an array element."""
        dimensions, lst = self.check_dim(name, index)
        bigindex = self.index(index, dimensions)
        bytesize = values.size_bytes(name)
        return memoryview(lst)[bigindex*bytesize:(bigindex+1)*bytesize]

    def get(self, name, index):
        """Retrieve a copy of the value of an array element."""
        return (name[-1], bytearray(self.view(name, index)))

    def set(self, name, index, value):
        """Assign a value to an array element."""
        # copy value into array
        self.view(name, index)[:] = self.values.to_type(name[-1], value)[1]
        # increment array version
        self.arrays[name][2] += 1

    def varptr(self, name, indices):
        """Retrieve the address of an array."""
        name = self.memory.complete_name(name)
        try:
            dimensions, _, _ = self.arrays[name]
            _, array_ptr = self.array_memory[name]
            # arrays are kept at the end of the var list
            return self.memory.var_current() + array_ptr + values.size_bytes(name) * self.index(indices, dimensions)
        except KeyError:
            return -1

    def dereference(self, address):
        """Get a value for an array given its pointer address."""
        found_addr = -1
        found_name = None
        for name, data in self.array_memory.iteritems():
            addr = self.memory.var_current() + data[1]
            if addr > found_addr and addr <= address:
                found_addr = addr
                found_name = name
        if not found_name:
            return None
        _, lst, _ = self.arrays[name]
        offset = address - found_addr
        return (name[-1], lst[offset : offset+values.size_bytes(name)])

    def get_memory(self, address):
        """Retrieve data from data memory: array space """
        name_addr = -1
        arr_addr = -1
        the_arr = None
        for name in self.array_memory:
            name_try, arr_try = self.array_memory[name]
            if name_try <= address and name_try > name_addr:
                name_addr, arr_addr = name_try, arr_try
                the_arr = name
        if the_arr is None:
            return -1
        var_current = self.memory.var_current()
        if address >= var_current + arr_addr:
            offset = address - arr_addr - var_current
            if offset >= self.array_size_bytes(the_arr):
                return -1
            _, byte_array, _ = self.arrays[the_arr]
            return byte_array[offset]
        else:
            offset = address - name_addr - var_current
            if offset < max(3, len(the_arr))+1:
                return get_name_in_memory(the_arr, offset)
            else:
                offset -= max(3, len(the_arr))+1
                dimensions, _, _ = self.arrays[the_arr]
                data_rep = struct.pack('<HB', self.array_size_bytes(the_arr) + 1 + 2*len(dimensions), len(dimensions))
                for d in dimensions:
                    data_rep += struct.pack('<H', d + 1 - self.base_index)
                return data_rep[offset]

    def get_strings(self):
        """Return a list of views of string array elements."""
        return [memoryview(record[1])[i:i+3]
                    for name, record in self.arrays.iteritems()
                        if name[-1] == '$'
                            for i in range(0, len(record[1]), 3)]


    ###########################################################################
    # helper functions for Python interface

    def from_list(self, python_list, name):
        """Convert Python list to BASIC array."""
        self._from_list(python_list, name, [])

    def _from_list(self, python_list, name, index):
        """Convert Python list to BASIC array."""
        if not python_list:
            return
        if isinstance(python_list[0], list):
            for i, v in enumerate(python_list):
                self._from_list(v, name, index+[i+(self.base_index or 0)])
        else:
            for i, v in enumerate(python_list):
                self.set(name, index+[i+(self.base_index or 0)], self.values.from_value(v, name[-1]))

    def to_list(self, name):
        """Convert BASIC array to Python list."""
        if name in self.arrays:
            indices, _, _ = self.arrays[name]
            return self._to_list(name, [], indices)
        else:
            return []

    def _to_list(self, name, index, remaining_dimensions):
        """Convert BASIC array to Python list."""
        if not remaining_dimensions:
            return []
        elif len(remaining_dimensions) == 1:
            return [self.values.to_value(self.get(name, index+[i+(self.base_index or 0)])) for i in xrange(remaining_dimensions[0])]
        else:
            return [self._to_list(name, index+[i+(self.base_index or 0)], remaining_dimensions[1:]) for i in xrange(remaining_dimensions[0])]
