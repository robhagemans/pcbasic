"""
PC-BASIC - strings.py
String syorage management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging
from operator import itemgetter

from . import error
from . import numbers


class String(numbers.Value):
    """String pointer"""

    sigil = '$'
    size = 3

    def __init__(self, buf=None, values=None):
        """Initialise the pointer"""
        numbers.Value.__init__(self, buf, values)
        self._stringspace = values._strings

    def length(self):
        """String length"""
        return ord(self._buffer[0])

    def address(self):
        """Pointer address"""
        return struct.unpack_from('<H', self._buffer, 1)[0]

    def dereference(self):
        """String value pointed to"""
        length, address = struct.unpack('<BH', self._buffer)
        return self._stringspace.copy(length, address)

    def from_str(self, python_str):
        """Set to value of python str."""
        self._buffer[:] = self._stringspace.store(python_str)
        return self

    from_value = from_str
    to_value = dereference
    to_str = dereference

    def iconcat(self, right):
        """Concatenate strings. In-place for the pointer."""
        left_args = struct.unpack('<BH', self._buffer)
        right_args = struct.unpack('<BH', right._buffer)
        self._buffer[:] = self._stringspace.store(
                self._stringspace.copy(*left_args) +
                self._stringspace.copy(*right_args))
        return self

    # NOTE: in_str is a Python str
    def lset(self, in_str, justify_right):
        """Justify a str into an existing buffer and pad with spaces."""
        # v is empty string if variable does not exist
        # trim and pad to size of target buffer
        length = self.length()
        in_str = in_str[:length]
        if justify_right:
            in_str = ' '*(length-len(in_str)) + in_str
        else:
            in_str += ' '*(length-len(in_str))
        length, address = struct.unpack('<BH', self._buffer)
        self._buffer[:] = self._stringspace.modify(length, address, in_str, offset=None, num=None)
        return self

    # NOTE: val is a Python str
    def midset(self, start, num, val):
        """Modify a string in an existing buffer."""
        # we need to decrement basic offset by 1 to get python offset
        offset = start - 1
        # don't overwrite more of the old string than the length of the new string
        num = min(num, len(val))
        # ensure the length of source string matches target
        length = self.length()
        if offset + num > length:
            num = length - offset
        if num <= 0:
            return self
        # cut new string to size if too long
        val = val[:num]
        # copy new value into existing buffer if possible
        length, address = struct.unpack('<BH', self._buffer)
        self._buffer[:] = self._stringspace.modify(length, address, val, offset, num)
        return self


class StringSpace(object):
    """String space is a table of strings accessible by their 2-byte pointers."""

    def __init__(self, memory):
        """Initialise empty string space."""
        self._memory = memory
        self._strings = {}
        self.clear()

    def __str__(self):
        """Debugging representation of string table."""
        return '\n'.join('%x: %s' % (n, v) for n, v in self._strings.iteritems())

    def clear(self):
        """Empty string space."""
        self._strings.clear()
        # strings are placed at the top of string memory, just below the stack
        self.current = self._memory.stack_start()

    def rebuild(self, stringspace):
        """Rebuild from stored copy."""
        self.clear()
        self._strings.update(stringspace._strings)

    def _retrieve(self, length, address):
        """Retrieve a string by its 3-byte sequence. 2-byte keys allowed, but will return longer string for empty string."""
        # if string length == 0, return empty string
        print address, self._strings[address]
        return bytearray() if length == 0 else self._strings[address]

    def _view(self, length, address):
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

    def copy(self, length, address):
        """Return a copy of a string from its string pointer."""
        return self._view(length, address).tobytes()

    def modify(self, length, address, in_str, offset, num):
        """Assign a new string into an existing buffer."""
        # if it is a code literal, we now do need to allocate space for a copy
        if address >= self._memory.code_start and address < self._memory.var_start():
            sequence = self.store(self.copy(length, address))
            length, address = struct.unpack('<BH', sequence)
        else:
            sequence = bytearray(struct.pack('<BH', length, address))
        if num is None:
            self._view(length, address)[:] = in_str
        else:
            self._view(length, address)[offset:offset+num] = in_str
        return sequence

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
            if address in self._strings:
                logging.debug('String at %d already defined.' % (address,))
            # copy and convert to bytearray
            self._strings[address] = bytearray(in_str)
        return bytearray(struct.pack('<BH', length, address))

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
            item[0][:] = self.store(item[2])

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
