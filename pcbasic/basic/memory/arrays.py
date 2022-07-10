"""
PC-BASIC - arrays.py
Array variable management

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import binascii
import struct

from ...compat import iteritems, iterkeys

from ..base import error
from .. import values
from .scalars import get_name_in_memory


class Arrays(object):

    def __init__(self, memory, values):
        """Initialise arrays."""
        self._memory = memory
        self._values = values
        self.clear()
        self.clear_base()

    def __contains__(self, varname):
        """Check if a scalar has been defined."""
        return varname in self._dims

    def __iter__(self):
        """Return an iterable over all scalar names."""
        return iterkeys(self._dims)

    def __repr__(self):
        """Debugging representation of variable dictionary."""
        return '\n'.join(
            '%s%s: %s' % (n, v, binascii.hexlify(bytes(self._buffers[n])))
            for n, v in iteritems(self._dims)
        )

    def clear(self):
        """Clear arrays."""
        self._dims = {}
        self._buffers = {}
        self._array_memory = {}
        self.current = 0

    def erase_(self, args):
        """Remove an array from memory."""
        for name in args:
            name = self._memory.complete_name(name)
            if name not in self._dims:
                # IFC if array does not exist
                raise error.BASICError(error.IFC)
            dimensions = self._dims[name]
            record_len = 1 + max(3, len(name)) + 3 + 2*len(dimensions)
            freed_bytes = self.array_len(dimensions) * values.size_bytes(name) + record_len
            erased_name_ptr, _ = self._array_memory[name]
            # delete buffers
            del self._dims[name]
            del self._buffers[name]
            del self._array_memory[name]
            # update memory model
            for name in self._array_memory:
                name_ptr, array_ptr = self._array_memory[name]
                if name_ptr > erased_name_ptr:
                    self._array_memory[name] = name_ptr - freed_bytes, array_ptr - freed_bytes
            self.current -= freed_bytes
        # if all arrays have been cleared and array base was set to 0 implicitly by DIM, unset it
        # however, if array base was set explicitly by OPTION BASE, it remains set.
        if not self._dims and self._base_set_by_dim:
            self.clear_base()

    def index(self, index, dimensions):
        """Return the flat index for a given dimensioned index."""
        bigindex = 0
        area = 1
        for i in range(len(index)):
            # dimensions is the *maximum index number*, regardless of self._base
            bigindex += area * (index[i] - self._base)
            area *= dimensions[i] + 1 - self._base
        return bigindex

    def array_len(self, dimensions):
        """Return the flat length for given dimensioned size."""
        return self.index(dimensions, dimensions) + 1

    def array_size_bytes(self, name):
        """Return the byte size of an array, if it exists. Return 0 otherwise."""
        try:
            dimensions = self._dims[name]
        except KeyError:
            return 0
        return self.array_len(dimensions) * values.size_bytes(name)

    def view_full_buffer(self, name):
        """Return a memoryview to a full array."""
        return memoryview(self._buffers[name])

    def dimensions(self, name):
        """Return the dimensions of an array."""
        return self._dims[name]

    def dim_(self, args):
        """DIM: dimension arrays."""
        for a in args:
            name, indices = a
            self.allocate(self._memory.complete_name(name), indices)

    @staticmethod
    def _record_size(name, dimensions):
        """Calculate size of array record in bytes."""
        # first two bytes: chars of name or 0 if name is one byte long
        return 1 + max(3, len(name)) + 3 + 2*len(dimensions)

    def _buffer_size(self, name, dimensions):
        """Calculate size of array buffer in bytes."""
        return self.array_len(dimensions) * values.size_bytes(name)

    def memory_size(self, name, dimensions):
        """Calculate size of array record and buffer in bytes."""
        return self._record_size(name, dimensions) + self._buffer_size(name, dimensions)

    def allocate(self, name, dimensions):
        """
        Allocate array space for an array of given dimensioned size.
        Raise errors if duplicate name or illegal index value.
        """
        if not dimensions:
            # DIM A does nothing
            return
        if self._base is None:
            self._base = 0
            self._base_set_by_dim = True
        if name in self._dims:
            raise error.BASICError(error.DUPLICATE_DEFINITION)
        for d in dimensions:
            if d < 0:
                raise error.BASICError(error.IFC)
            elif d < self._base:
                raise error.BASICError(error.SUBSCRIPT_OUT_OF_RANGE)
        # update memory model
        name_ptr = self.current
        record_len = self._record_size(name, dimensions)
        array_bytes = self._buffer_size(name, dimensions)
        array_ptr = name_ptr + record_len
        total_bytes = record_len + array_bytes
        self._memory.check_free(total_bytes, error.OUT_OF_MEMORY)
        self.current += total_bytes
        self._array_memory[name] = (name_ptr, array_ptr)
        self._buffers[name] = bytearray(array_bytes)
        self._dims[name] = dimensions

    def check_dim(self, name, index):
        """
        Check if an array has been allocated.
        If not, auto-allocate if indices are <= 10; raise error otherwise.
        """
        try:
            dimensions = self._dims[name]
        except KeyError:
            # auto-dimension - 0..10 or 1..10
            # this even fixes the dimensions if the index turns out to be out of range
            dimensions = [10] * len(index)
            self.allocate(name, dimensions)
        lst = self._buffers[name]
        if len(index) != len(dimensions):
            raise error.BASICError(error.SUBSCRIPT_OUT_OF_RANGE)
        for i, d in zip(index, dimensions):
            if i < 0:
                raise error.BASICError(error.IFC)
            elif i < self._base or i > d:
                # dimensions is the *maximum index number*, regardless of self._base
                raise error.BASICError(error.SUBSCRIPT_OUT_OF_RANGE)
        return dimensions, lst

    def clear_base(self):
        """Unset the array base."""
        # OPTION BASE value. NONE: unset
        self._base = None
        # OPTION BASE set by DIM rather than explicitly
        self._base_set_by_dim = False

    def option_base_(self, args):
        """Set the array base to 0 or 1 (OPTION BASE). Raise error if already set."""
        base, = args
        base = int(base)
        if self._base is not None and base != self._base:
            # duplicate definition
            raise error.BASICError(error.DUPLICATE_DEFINITION)
        self._base = base

    def view_buffer(self, name, index):
        """Return a memoryview to an array element."""
        dimensions, lst = self.check_dim(name, index)
        bigindex = self.index(index, dimensions)
        bytesize = values.size_bytes(name)
        return memoryview(lst)[bigindex*bytesize:(bigindex+1)*bytesize]

    def get(self, name, index):
        """Retrieve a view of the value of an array element."""
        # do not make a copy - we may end up with stale string pointers
        # due to garbage collection
        return self._values.create(self.view_buffer(name, index))

    def set(self, name, index, value):
        """Assign a value to an array element."""
        if isinstance(value, values.String):
            self._memory.strings.fix_temporaries()
        # copy value into array
        self.view_buffer(name, index)[:] = values.to_type(name[-1:], value).to_bytes()
        # drop cache here

    def varptr(self, name, indices):
        """Retrieve the address of an array."""
        dimensions = self._dims[name]
        _, array_ptr = self._array_memory[name]
        # arrays are kept at the end of the var list
        return (
            self._memory.var_current() + array_ptr +
            values.size_bytes(name) * self.index(indices, dimensions)
        )

    def dereference(self, address):
        """Get a value for an array given its pointer address."""
        found_addr = -1
        found_name = None
        for name, data in iteritems(self._array_memory):
            addr = self._memory.var_current() + data[1]
            if addr > found_addr and addr <= address:
                found_addr = addr
                found_name = name
        if not found_name:
            return None
        lst = self._buffers[name]
        offset = address - found_addr
        return self._values.from_bytes(lst[offset : offset+values.size_bytes(name)])

    def get_memory(self, address):
        """Retrieve data from data memory: array space """
        name_addr = -1
        arr_addr = -1
        the_arr = None
        for name in self._array_memory:
            name_try, arr_try = self._array_memory[name]
            if name_try <= address and name_try > name_addr:
                name_addr, arr_addr = name_try, arr_try
                the_arr = name
        if the_arr is None:
            return -1
        var_current = self._memory.var_current()
        if address >= var_current + arr_addr:
            offset = address - arr_addr - var_current
            if offset >= self.array_size_bytes(the_arr):
                return -1
            byte_array = self._buffers[the_arr]
            return byte_array[offset]
        else:
            offset = address - name_addr - var_current
            if offset < max(3, len(the_arr))+1:
                return get_name_in_memory(the_arr, offset)
            else:
                offset -= max(3, len(the_arr))+1
                dimensions = self._dims[the_arr]
                data_rep = struct.pack(
                    '<HB',
                    self.array_size_bytes(the_arr) + 1 + 2*len(dimensions),
                    len(dimensions)
                )
                for d in dimensions:
                    data_rep += struct.pack('<H', d + 1 - self._base)
                return data_rep[offset]

    def get_strings(self):
        """Return a list of views of string array elements."""
        return [
            memoryview(buf)[i:i+3]
            for name, buf in iteritems(self._buffers)
            if name[-1:] == values.STR
            for i in range(0, len(buf), 3)
        ]


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
                self._from_list(v, name, index+[i+(self._base or 0)])
        else:
            for i, v in enumerate(python_list):
                self.set(name, index+[i+(self._base or 0)], self._values.from_value(v, name[-1:]))

    def to_list(self, name):
        """Convert BASIC array to Python list."""
        if name in self._dims:
            indices = self._dims[name]
            return self._to_list(name, [], indices)
        else:
            return []

    def _to_list(self, name, index, remaining_dimensions):
        """Convert BASIC array to Python list."""
        if not remaining_dimensions:
            return []
        elif len(remaining_dimensions) == 1:
            return [
                self.get(name, index+[i]).to_value()
                for i in range((self._base or 0), remaining_dimensions[0] + 1)
            ]
        else:
            return [
                self._to_list(name, index+[i], remaining_dimensions[1:])
                for i in range((self._base or 0), remaining_dimensions[0] + 1)
            ]
