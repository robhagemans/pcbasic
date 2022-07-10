"""
PC-BASIC - strings.py
String values

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import struct
import logging
from operator import itemgetter

from ...compat import iteritems

from ..base import error
from . import numbers


class String(numbers.Value):
    """String pointer."""

    sigil = b'$'
    size = 3

    def __init__(self, buffer, values):
        """Initialise the pointer."""
        numbers.Value.__init__(self, buffer, values)
        self._stringspace = values.stringspace

    def length(self):
        """String length."""
        return bytearray(self._buffer)[0]

    def address(self):
        """Pointer address."""
        return struct.unpack_from('<H', self._buffer, 1)[0]

    def dereference(self):
        """String value pointed to."""
        length, address = struct.unpack('<BH', self._buffer)
        return self._stringspace.view(length, address).tobytes()

    def from_str(self, python_str):
        """Set to value of python str."""
        assert isinstance(python_str, bytes), type(python_str)
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
            self._stringspace.view(*target)[offset:offset+num] = (
                self._stringspace.view(*source)[:num]
            )
        else:
            # copy byte by byte from left to right
            # to conform to GW overwriting of source string on overlap
            for i in range(num):
                self._stringspace.view(*target)[i+offset:i+offset+1] = (
                    self._stringspace.view(*source)[i:i+1]
                )
        return self


    ######################################################################
    # unary functions

    def len(self):
        """LEN: length of string."""
        return numbers.Integer(None, self._values).from_int(self.length())

    def asc(self):
        """ASC: ordinal ASCII value of a character."""
        s = bytearray(self.to_str())
        error.throw_if(not s)
        return numbers.Integer(None, self._values).from_int(s[0])

    def space(self, num):
        """SPACE$: repeat spaces."""
        num = num.to_integer().to_int()
        error.range_check(0, 255, num)
        return self.new().from_str(b' ' * num)


class StringSpace(object):
    """Table of strings accessible by their length and address."""

    def __init__(self, memory):
        """Initialise empty string space."""
        self._memory = memory
        self._strings = {}
        self._temp = None
        self.clear()

    def __repr__(self):
        """Debugging representation of string table."""
        return '\n'.join('%x: %r' % (n, v) for n, v in iteritems(self._strings))

    def clear(self):
        """Empty string space."""
        self._strings.clear()
        # strings are placed at the top of string memory, just below the stack
        self.current = self._memory.stack_start()

    def rebuild(self, stringspace):
        """Rebuild from stored copy."""
        self.clear()
        self._strings.update(stringspace._strings)
        self.current = stringspace.current

    def copy_to(self, string_space, length, address):
        """Copy a string to another string space."""
        return string_space.store(self.view(length, address).tobytes())

    def _retrieve(self, length, address):
        """Retrieve a string by its pointer."""
        # if string length == 0, return empty string
        try:
            return bytearray() if length == 0 else self._strings[address]
        except KeyError: # pragma: no cover
            raise KeyError(u'Dereferencing detached string at %x (%d)' % (address, address))

    def view(self, length, address):
        """Return a writeable view of a string from its string pointer."""
        # empty string pointers can point anywhere
        if length == 0:
            return memoryview(bytearray())
        if address >= self._memory.var_start():
            # string stored in string space
            return memoryview(self._retrieve(length, address))
        elif address >= self._memory.code_start:
            # get string stored in code as bytearray
            codestr = self._memory.program.get_memory_block(address, length)
            # NOTE this is a writeable view of a *copy* of the code!
            return memoryview(codestr)
        else:
            # string stored in field buffers
            return self._memory.view_field_memory(address, length)

    def check_modify(self, length, address):
        """Assign a new string into an existing buffer."""
        # if it is a code literal, we now do need to allocate space for a copy
        if address >= self._memory.code_start and address < self._memory.var_start():
            length, address = self.store(self.view(length, address).tobytes())
        return length, address

    def store(self, in_str, address=None, check_free=True):
        """Store a new string and return the string pointer."""
        length = len(in_str)
        # don't store overlong strings
        if length > 255:
            raise error.BASICError(error.STRING_TOO_LONG)
        # don't store if address is provided (code or FIELD strings)
        if address is None:
            # reserve string space; collect garbage if necessary
            if check_free:
                self._memory.check_free(length, error.OUT_OF_STRING_SPACE)
            # find new string address
            self.current -= length
            address = self.current + 1
            # don't store empty strings
            if length > 0:
                # copy and convert to bytearray
                self._strings[address] = bytearray(in_str)
        return length, address

    def _delete_last(self):
        """Delete the string provided if it is at the top of string space."""
        last_address = self.current + 1
        try:
            length = len(self._strings[last_address])
            self.current += length
            del self._strings[last_address]
        except KeyError: # pragma: no cover
            # maybe happens if we're called before an out-of-memory exception is handled
            # and the string wasn't allocated
            pass

    def collect_garbage(self, string_ptrs):
        """Re-store the strings referenced in string_ptrs, delete the rest."""
        # string_ptrs should be a list of memoryviews to the original pointers
        # retrieve addresses and copy strings
        string_list = []
        # find last non-temporary string
        last_permanent = self._memory.stack_start()
        last_perm_view = None
        for view in string_ptrs:
            length, addr = struct.unpack('<BH', view.tobytes())
            # exclude empty elements of string arrays (len==0 and addr==0)
            # exclude strings is not located in memory (FIELD or code strings)
            if addr >= self._memory.var_start():
                string_list.append((view, addr, self._retrieve(length, addr)))
                # set sentinel string (lowest-address permanent string)
                # don't use zero-length strings as sentinel:
                # they share an address with allocated strings and may get swapped on sorting
                # in which case the allocated permanent string ends up below the sentinel
                if self._temp is not None and length > 0:
                    if addr > self._temp and addr < last_permanent:
                        last_permanent, last_perm_view = addr, view
        # sort by address, largest first (maintain order of storage)
        string_list.sort(key=itemgetter(1), reverse=True)
        # clear the string buffer and re-store all referenced strings
        self.clear()
        for view, _, string in string_list:
            # re-allocate string space
            # update the original pointers supplied (these are memoryviews)
            view[:] = struct.pack('<BH', *self.store(string, check_free=False))
        # readdress  start of temporary strings
        if last_perm_view is None:
            self._temp = None
        elif self._temp is not None and self._temp != self._memory.stack_start():
            self._temp = -1 + struct.unpack_from('<H', last_perm_view.tobytes(), 1)[0]

    def get_memory(self, address):
        """Retrieve data from data memory: string space """
        # find the variable we're in
        for try_address, value in iteritems(self._strings):
            length = len(value)
            if try_address <= address < try_address + length:
                return value[address - try_address]
        return -1

    def fix_temporaries(self):
        """Make all temporary strings permanent."""
        self._temp = self.current

    def reset_temporaries(self):
        """Delete temporary string at top of string space."""
        if self._temp is not None and self._temp != self.current:
            self._delete_last()
        self._temp = self.current

    def is_permanent(self, string):
        """Return whether string is in permanent string space."""
        addr = string.address()
        return addr > self._temp

    def is_field_string(self, string):
        """Return whether string is a FIELD string."""
        return string.address() < self._memory.code_start
