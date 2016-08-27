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
from . import values
from . import numbers


class String(numbers.Value):
    """String pointer"""

    sigil = '$'
    size = 3

    def __init__(self, buffer, stringspace):
        """Initialise the pointer"""
        numbers.Value.__init__(buffer)
        self.stringspace = memoryview(stringspace)

    def length(self):
        """String length"""
        return ord(self.buffer[0])

    def address(self):
        """Pointer address"""
        return struct.unpack_from('<H', self.buffer, 1)[0]

    def dereference(self):
        """String value pointed to"""
        addr = self.address()
        return bytearray(self.stringspace[addr : addr+self.length])

    to_value = dereference


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
