"""
PC-BASIC - scalars.py
Scalar variable management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from . import error
from . import values


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
            self.variables[name][:] = self.values.to_bytes(value)[:]
        except KeyError:
            # copy into new buffer if not existing
            self.variables[name] = self.values.to_bytes(value)[:]

    def get(self, name):
        """Retrieve the value of a scalar variable."""
        try:
            return self.values.from_bytes(self.variables[name])
        except KeyError:
            return values.null(name[-1])

    def view(self, name):
        """Retrieve a view of an existing scalar variable."""
        return self.values.create(self.variables[name])

    def view_buffer(self, name):
        """Retrieve a view of an existing scalar variable's buffer."""
        return memoryview(self.variables[name])

    def varptr(self, name):
        """Retrieve the address of a scalar variable."""
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
