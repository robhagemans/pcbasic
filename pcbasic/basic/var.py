"""
PC-BASIC - var.py
Variable & array management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging
from operator import itemgetter

from . import error
from . import values


###############################################################################
# strings

class StringSpace(object):
    """String space is a table of strings accessible by their 2-byte pointers."""

    def __init__(self, memory):
        """Initialise empty string space."""
        self.memory = memory
        self.strings = {}
        self.clear()

    def clear(self):
        """Empty string space."""
        self.strings.clear()
        # strings are placed at the top of string memory, just below the stack
        self.current = self.memory.stack_start()

    def _retrieve(self, key):
        """Retrieve a string by its 3-byte sequence. 2-byte keys allowed, but will return longer string for empty string."""
        key = str(key)
        if len(key) == 2:
            return self.strings[key]
        elif len(key) == 3:
            # if string length == 0, return empty string
            return bytearray('') if ord(key[0]) == 0 else self.strings[key[-2:]]
        else:
            raise KeyError('String key %s has wrong length.' % repr(key))

    def _view(self, basic_string):
        """Return a writeable view of a string from its string pointer."""
        length = values.string_length(basic_string)
        # empty string pointers can point anywhere
        if length == 0:
            return bytearray()
        address = values.string_address(basic_string)
        # address >= self.memory.var_start(): if we no longer double-store code strings in string space object
        if address >= self.memory.code_start:
            # string stored in string space
            sequence = values.Values.to_bytes(basic_string)
            return memoryview(self._retrieve(sequence))
        else:
            # string stored in field buffers
            # find the file we're in
            start = address - self.memory.field_mem_start
            number = 1 + start // self.memory.field_mem_offset
            offset = start % self.memory.field_mem_offset
            if (number not in self.memory.fields) or (start < 0):
                raise KeyError('Invalid string pointer')
            # memoryview slice continues to point to buffer, does not copy
            return memoryview(self.memory.fields[number].buffer)[offset:offset+length]

    def copy(self, basic_string):
        """Return a copy of a string from its string pointer."""
        return str(bytearray(self._view(basic_string)))

    def _modify(self, basic_string, in_str, offset=None, num=None):
        """Assign a new string into an existing buffer."""
        # if it is a code literal, we now do need to allocate space for a copy
        address = values.string_address(basic_string)
        if address >= self.memory.code_start and address < self.memory.var_start():
            basic_string = self.store(self.copy(basic_string))
        if num is None:
            self._view(basic_string)[:] = in_str
        else:
            self._view(basic_string)[offset:offset+num] = in_str
        return basic_string

    def lset(self, basic_string, in_str, justify_right):
        """Justify a new string into an existing buffer and pad with spaces."""
        # v is empty string if variable does not exist
        # trim and pad to size of target buffer
        length = values.string_length(basic_string)
        in_str = in_str[:length]
        if justify_right:
            in_str = ' '*(length-len(in_str)) + in_str
        else:
            in_str += ' '*(length-len(in_str))
        return self._modify(basic_string, in_str)

    def midset(self, basic_str, start, num, val):
        """Modify a string in an existing buffer."""
        # we need to decrement basic offset by 1 to get python offset
        offset = start-1
        # don't overwrite more of the old string than the length of the new string
        num = min(num, len(val))
        # ensure the length of source string matches target
        length = values.string_length(basic_str)
        if offset + num > length:
            num = length - offset
        if num <= 0:
            return basic_str
        # cut new string to size if too long
        val = val[:num]
        # copy new value into existing buffer if possible
        return self._modify(basic_str, val, offset, num)

    def store(self, in_str, address=None):
        """Store a new string and return the string pointer."""
        size = len(in_str)
        # don't store overlong strings
        if size > 255:
            raise error.RunError(error.STRING_TOO_LONG)
        if address is None:
            # reserve string space; collect garbage if necessary
            self.memory.check_free(size, error.OUT_OF_STRING_SPACE)
            # find new string address
            self.current -= size
            address = self.current + 1
        key = struct.pack('<H', address)
        # don't store empty strings
        if size > 0:
            if key in self.strings:
                logging.debug('String key %s at %d already defined.' % (repr(key), address))
            # copy and convert to bytearray
            self.strings[key] = bytearray(in_str)
        return values.Values.from_bytes(chr(size) + key)

    def delete_last(self):
        """Delete the string provided if it is at the top of string space."""
        last_key = struct.pack('<H', self.current + 1)
        try:
            length = len(self.strings[last_key])
            self.current += length
            del self.strings[last_key]
        except KeyError:
            # happens if we're called before an out-of-memory exception is handled
            # and the string wasn't allocated
            pass

    def address(self, key):
        """Return the address of a given key."""
        return struct.unpack('<H', key[-2:])[0]

    def collect_garbage(self, string_ptrs):
        """Re-store the strings refrerenced in string_ptrs, delete the rest."""
        # retrieve addresses and copy strings
        string_list = []
        for value in string_ptrs:
            try:
                string_list.append((value,
                        self.address(bytes(bytearray(value))),
                        self._retrieve(bytes(bytearray(value)))))
            except KeyError:
                # string is not located in memory - FIELD or code
                pass
        # sort by str_ptr, largest first (maintain order of storage)
        string_list.sort(key=itemgetter(1), reverse=True)
        # clear the string buffer and re-store all referenced strings
        self.clear()
        for item in string_list:
            # re-allocate string space
            item[0][:] = values.Values.to_bytes(self.store(item[2]))

    def get_memory(self, address):
        """Retrieve data from data memory: string space """
        # find the variable we're in
        for key, value in self.strings.iteritems():
            try_address = self.address(key)
            length = len(value)
            if try_address <= address < try_address + length:
                return value[address - try_address]
        return -1

    def __enter__(self):
        """Enter temp-string context guard."""
        self.temp = self.current

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit temp-string context guard."""
        if self.temp != self.current:
            self.delete_last()


###############################################################################
# scalar variables


class Scalars(object):
    """Scalar variables."""

    def __init__(self, memory, values):
        """Initialise scalars."""
        self.memory = memory
        self.values = values
        self.clear()

    def clear(self):
        """Clear scalar variables."""
        self.variables = {}
        self.var_memory = {}
        self.current = 0

    def set(self, name, value=None):
        """Assign a value to a variable."""
        name = self.memory.complete_name(name)
        type_char = name[-1]
        if value is not None:
            value = self.values.to_type(type_char, value)
        # update memory model
        # check if garbage needs collecting before allocating memory
        if name not in self.var_memory:
            # don't add string length, string already stored
            size = (max(3, len(name)) + 1 + values.size_bytes(type_char))
            self.memory.check_free(size, error.OUT_OF_MEMORY)
            # first two bytes: chars of name or 0 if name is one byte long
            name_ptr = self.memory.var_current()
            # byte_size first_letter second_letter_or_nul remaining_length_or_nul
            var_ptr = name_ptr + max(3, len(name)) + 1
            self.current += max(3, len(name)) + 1 + values.size_bytes(name)
            self.var_memory[name] = (name_ptr, var_ptr)
        # don't change the value if just checking allocation
        if value is None:
            if name in self.variables:
                return
            else:
                value = values.null(type_char)
        # copy buffers
        try:
            # in-place copy is crucial for FOR
            self.variables[name][:] = value[1][:]
        except KeyError:
            # copy into new buffer if not existing
            self.variables[name] = value[1][:]

    def get(self, name):
        """Retrieve the value of a scalar variable."""
        name = self.memory.complete_name(name)
        try:
            return (name[-1], self.variables[name])
        except KeyError:
            return values.null(name[-1])

    def varptr(self, name):
        """Retrieve the address of a scalar variable."""
        name = self.memory.complete_name(name)
        try:
            _, var_ptr = self.var_memory[name]
            return var_ptr
        except KeyError:
            return -1

    def dereference(self, address):
        """Get a value for a scalar given its pointer address."""
        for name, data in self.var_memory.iteritems():
            if data[1] == address:
                return self.get(name)
        return None

    def get_memory(self, address):
        """Retrieve data from data memory: variable space """
        name_addr = -1
        var_addr = -1
        the_var = None
        for name in self.var_memory:
            name_try, var_try = self.var_memory[name]
            if name_try <= address and name_try > name_addr:
                name_addr, var_addr = name_try, var_try
                the_var = name
        if the_var is None:
            return -1
        if address >= var_addr:
            offset = address - var_addr
            if offset >= values.size_bytes(the_var):
                return -1
            var_rep = self.variables[the_var]
            return var_rep[offset]
        else:
            offset = address - name_addr
            return get_name_in_memory(the_var, offset)

    def get_strings(self):
        """Return a list of views of string scalars."""
        return [memoryview(value) for name, value in self.variables.iteritems() if name[-1] == '$']


###############################################################################
# arrays

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


###############################################################################
# variable memory

def get_name_in_memory(name, offset):
    """Memory representation of variable name."""
    if offset == 0:
        return values.size_bytes(name)
    elif offset == 1:
        return ord(name[0].upper())
    elif offset == 2:
        if len(name) > 2:
            return ord(name[1].upper())
        else:
            return 0
    elif offset == 3:
        if len(name) > 3:
            return len(name)-3
        else:
            return 0
    else:
        # rest of name is encoded such that c1 == 'A'
        return ord(name[offset-1].upper()) - ord('A') + 0xC1
