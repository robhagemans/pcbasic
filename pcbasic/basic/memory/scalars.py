"""
PC-BASIC - scalars.py
Scalar variable management

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct

from ...compat import iteritems, iterkeys

from ..base import error
from .. import values


class Scalars(object):
    """Scalar variables."""

    def __init__(self, memory, values):
        """Initialise scalars."""
        self._memory = memory
        self._values = values
        self.clear()

    def __contains__(self, varname):
        """Check if a scalar has been defined."""
        return varname in self._vars

    def __iter__(self):
        """Return an iterable over all scalar names."""
        return iterkeys(self._vars)

    def __repr__(self):
        """Debugging representation of variable dictionary."""
        return '\n'.join(
            '%s: %s' % (n.decode('ascii'), self._values.from_bytes(v))
            for n, v in iteritems(self._vars)
        )

    def clear(self):
        """Clear scalar variables."""
        self._vars = {}
        self._var_memory = {}
        self.current = 0

    @staticmethod
    def _record_size(name):
        """Calculate size of scalar record in bytes."""
        # first two bytes: chars of name or 0 if name is one byte long
        return max(3, len(name)) + 1

    @staticmethod
    def _buffer_size(name):
        """Calculate size of scalar buffer in bytes."""
        return values.size_bytes(name)

    @staticmethod
    def memory_size(name):
        """Calculate size of scalar record and buffer in bytes."""
        return Scalars._record_size(name) + Scalars._buffer_size(name)

    def set(self, name, value=None):
        """Assign a value to a variable."""
        if isinstance(value, values.String):
            self._memory.strings.fix_temporaries()
        type_char = name[-1:]
        if value is not None:
            value = values.to_type(type_char, value)
        # update memory model
        # check if garbage needs collecting before allocating memory
        if name not in self._var_memory:
            # don't add string length, string already stored
            size = self.memory_size(name)
            self._memory.check_free(size, error.OUT_OF_MEMORY)
            # first two bytes: chars of name or 0 if name is one byte long
            name_ptr = self._memory.var_current()
            # byte_size first_letter second_letter_or_nul remaining_length_or_nul
            var_ptr = name_ptr + self._record_size(name)
            self.current += size
            self._var_memory[name] = (name_ptr, var_ptr)
        # don't change the value if just checking allocation
        if value is None:
            if name in self._vars:
                return
            else:
                value = self._values.new(type_char)
        # copy buffers
        try:
            # in-place copy is crucial for FOR
            self._vars[name][:] = value.to_bytes()[:]
        except KeyError:
            # copy into new buffer if not existing
            self._vars[name] = value.to_bytes()[:]

    def get(self, name):
        """Retrieve the value of a scalar variable."""
        try:
            # we can't copy as we may end up with stale string pointers
            return self._values.create(self._vars[name])
        except KeyError:
            return self._values.new(name[-1:])

    def view(self, name):
        """Retrieve a view of an existing scalar variable."""
        return self._values.create(self._vars[name])

    def view_buffer(self, name):
        """Retrieve a view of an existing scalar variable's buffer."""
        return memoryview(self._vars[name])

    def varptr(self, name):
        """Retrieve the address of a scalar variable."""
        _, var_ptr = self._var_memory[name]
        return var_ptr

    def dereference(self, address):
        """Get a value for a scalar given its pointer address."""
        for name, data in iteritems(self._var_memory):
            if data[1] == address:
                return self.get(name)
        return None

    def get_memory(self, address):
        """Retrieve data from data memory: variable space """
        name_addr = -1
        var_addr = -1
        the_var = None
        for name in self._var_memory:
            name_try, var_try = self._var_memory[name]
            if name_try <= address and name_try > name_addr:
                name_addr, var_addr = name_try, var_try
                the_var = name
        if the_var is None: # pragma: no cover
            return -1
        if address >= var_addr:
            offset = address - var_addr
            if offset >= values.size_bytes(the_var): # pragma: no cover
                return -1
            var_rep = self._vars[the_var]
            return var_rep[offset]
        else:
            offset = address - name_addr
            return get_name_in_memory(the_var, offset)

    def get_strings(self):
        """Return a list of views of string scalars."""
        return [
            memoryview(value) for name, value in iteritems(self._vars) if name[-1:] == values.STR
        ]


###############################################################################
# variable memory

def get_name_in_memory(name, offset):
    """Memory representation of variable name."""
    # 00 type size in bytes
    # 01 1st char of name
    # 02 2nd char of name or 00
    # 03 length of name minus 3, 00 if less than 3 chars
    # 04-- remaining chars of name, excluding sigil, shifted so that A is encoded as &hC1
    #
    normname = bytearray(name.upper())[:-1]
    if offset == 0:
        return values.size_bytes(name)
    elif offset == 1:
        return normname[0]
    elif offset == 2:
        if len(name) > 2:
            return normname[1]
        else:
            return 0
    elif offset == 3:
        if len(name) > 3:
            return len(name)-3
        else:
            return 0
    elif 4 <= offset <= len(normname)+1:
        # rest of name is encoded such that c1 == 'A'
        return normname[offset-2] - ord(b'A') + 0xC1
    else: # pragma: no cover
        return -1
