"""
PC-BASIC - strings.py
String values

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging
from operator import itemgetter

from .. import error
from . import numbers


class String(numbers.Value):
    """String pointer."""

    sigil = '$'
    size = 3

    def __init__(self, buffer, values):
        """Initialise the pointer."""
        numbers.Value.__init__(self, buffer, values)
        self._stringspace = values.stringspace

    def length(self):
        """String length."""
        return ord(self._buffer[0])

    def address(self):
        """Pointer address."""
        return struct.unpack_from('<H', self._buffer, 1)[0]

    def dereference(self):
        """String value pointed to."""
        length, address = struct.unpack('<BH', self._buffer)
        return self._stringspace.view(length, address).tobytes()

    def from_str(self, python_str):
        """Set to value of python str."""
        self._buffer[:] = struct.pack('<BH', *self._stringspace.store(python_str))
        return self

    def from_pointer(self, length, address):
        """Set buffer to string pointer."""
        self._buffer[:] = struct.pack('<BH', length, address)
        return self

    def to_pointer(self):
        """Get length and address."""
        return struct.unpack('<BH', self._buffer)

    from_value = from_str
    to_value = dereference
    to_str = dereference

    def add(self, right):
        """Concatenate strings. In-place for the pointer."""
        return self.new().from_str(self.dereference() + right.dereference())

    def eq(self, right):
        """This string equals the right-hand side."""
        return self.to_str() == right.to_str()

    def gt(self, right):
        """This string orders after the right-hand side."""
        left = self.to_str()
        right = right.to_str()
        shortest = min(len(left), len(right))
        for i in range(shortest):
            if left[i] > right[i]:
                return True
            elif left[i] < right[i]:
                return False
        # the same so far...
        # the shorter string is said to be less than the longer,
        # provided they are the same up till the length of the shorter.
        if len(left) > len(right):
            return True
        # left is shorter, or equal strings
        return False

    def lset(self, in_str, justify_right):
        """Justify a str into an existing buffer and pad with spaces."""
        # v is empty string if variable does not exist
        # trim and pad to size of target buffer
        length = self.length()
        in_str = in_str.to_value()
        if justify_right:
            in_str = in_str[:length].rjust(length)
        else:
            in_str = in_str[:length].ljust(length)
        # make a copy only if not in a writeable location
        target = self._stringspace.check_modify(*self.to_pointer())
        self.from_pointer(*target)
        # copy the new string in
        self._stringspace.view(*target)[:] = in_str
        return self

    def midset(self, start, num, val):
        """Modify a string in an existing buffer."""
        # we need to decrement basic offset by 1 to get python offset
        offset = start - 1
        # don't overwrite more of the old string than the length of the new string
        num = min(num, val.length())
        # ensure the length of source string matches target
        length = self.length()
        if offset + num > length:
            num = length - offset
        if num <= 0:
            return self
        # make a copy only if not in a writeable location
        target = self._stringspace.check_modify(*self.to_pointer())
        self.from_pointer(*target)
        source = val.to_pointer()
        if source != target:
            self._stringspace.view(*target)[offset:offset+num] = self._stringspace.view(*source)[:num]
        else:
            # copy byte by byte from left to right
            # to conform to GW overwriting of source string on overlap
            for i in range(num):
                self._stringspace.view(*target)[i+offset:i+offset+1] = self._stringspace.view(*source)[i]
        return self


    ######################################################################
    # unary functions

    def len(self):
        """LEN: length of string."""
        return numbers.Integer(None, self._values).from_int(self.length())

    def asc(self):
        """ASC: ordinal ASCII value of a character."""
        s = self.to_str()
        error.throw_if(not s)
        return numbers.Integer(None, self._values).from_int(ord(s[0]))

    def space(self, num):
        """SPACE$: repeat spaces."""
        num = num.to_integer().to_int()
        error.range_check(0, 255, num)
        return self.new().from_str(' ' * num)


class StringSpace(object):
    """Table of strings accessible by their length and address."""

    def __init__(self, memory):
        """Initialise empty string space."""
        self._memory = memory
        self._strings = {}
        self.clear()

    def __str__(self):
        """Debugging representation of string table."""
        return '\n'.join('%x: %s' % (n, repr(v)) for n, v in self._strings.iteritems())

    def clear(self):
        """Empty string space."""
        self._strings.clear()
        # strings are placed at the top of string memory, just below the stack
        self.current = self._memory.stack_start()

    def rebuild(self, stringspace):
        """Rebuild from stored copy."""
        self.clear()
        self._strings.update(stringspace._strings)

    def copy_to(self, string_space, length, address):
        """Copy a string to another string space."""
        return string_space.store(self.view(length, address).tobytes())

    def _retrieve(self, length, address):
        """Retrieve a string by its pointer."""
        # if string length == 0, return empty string
        return bytearray() if length == 0 else self._strings[address]

    def view(self, length, address):
        """Return a writeable view of a string from its string pointer."""
        # empty string pointers can point anywhere
        if length == 0:
            return memoryview(bytearray())
        # address >= self._memory.var_start(): if we no longer double-store code strings in string space object
        if address >= self._memory.code_start:
            # string stored in string space
            return memoryview(self._retrieve(length, address))
        else:
            # string stored in field buffers
            # find the file we're in
            start = address - self._memory.field_mem_start
            number = 1 + start // self._memory.field_mem_offset
            offset = start % self._memory.field_mem_offset
            if (number not in self._memory.fields) or (start < 0):
                raise KeyError('Invalid string pointer')
            # memoryview slice continues to point to buffer, does not copy
            return memoryview(self._memory.fields[number].buffer)[offset:offset+length]

    def check_modify(self, length, address):
        """Assign a new string into an existing buffer."""
        # if it is a code literal, we now do need to allocate space for a copy
        if address >= self._memory.code_start and address < self._memory.var_start():
            length, address = self.store(self.view(length, address).tobytes())
        return length, address

    def store(self, in_str, address=None):
        """Store a new string and return the string pointer."""
        length = len(in_str)
        # don't store overlong strings
        if length > 255:
            raise error.RunError(error.STRING_TOO_LONG)
        if address is None:
            # reserve string space; collect garbage if necessary
            self._memory.check_free(length, error.OUT_OF_STRING_SPACE)
            # find new string address
            self.current -= length
            address = self.current + 1
        # don't store empty strings
        if length > 0:
            # copy and convert to bytearray
            self._strings[address] = bytearray(in_str)
        return length, address

    def delete_last(self):
        """Delete the string provided if it is at the top of string space."""
        last_address = self.current + 1
        try:
            length = len(self._strings[last_address])
            self.current += length
            del self._strings[last_address]
        except KeyError:
            # happens if we're called before an out-of-memory exception is handled
            # and the string wasn't allocated
            pass

    def collect_garbage(self, string_ptrs):
        """Re-store the strings refrerenced in string_ptrs, delete the rest."""
        # retrieve addresses and copy strings
        string_list = []
        for value in string_ptrs:
            try:
                length, address = struct.unpack('<BH', value.tobytes())
                string_list.append((value, address,
                        self._retrieve(length, address)))
            except KeyError:
                # string is not located in memory - FIELD or code
                pass
        # sort by str_ptr, largest first (maintain order of storage)
        string_list.sort(key=itemgetter(1), reverse=True)
        # clear the string buffer and re-store all referenced strings
        self.clear()
        for item in string_list:
            # re-allocate string space
            item[0][:] = struct.pack('<BH', *self.store(item[2]))

    def get_memory(self, address):
        """Retrieve data from data memory: string space """
        # find the variable we're in
        for try_address, value in self._strings.iteritems():
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
