"""
PC-BASIC - var.py
Variable & array management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from operator import itemgetter

import error
import vartypes
import state
import memory


###############################################################################
# strings

class StringSpace(object):
    """ String space is a table of strings accessible by their 2-byte pointers. """

    def __init__(self):
        """ Initialise empty string space. """
        self.clear()

    def clear(self):
        """ Empty string space. """
        self.strings = {}
        # strings are placed at the top of string memory, just below the stack
        self.current = memory.stack_start()

    def retrieve(self, key):
        """ Retrieve a string by its 3-byte sequence. 2-byte keys allowed, but will return longer string for empty string. """
        key = str(key)
        if len(key) == 2:
            return self.strings[key]
        elif len(key) == 3:
            # if string length == 0, return empty string
            return bytearray('') if ord(key[0]) == 0 else self.strings[key[-2:]]
        else:
            raise KeyError('String key %s has wrong length.' % repr(key))

    def copy(self, key):
        """ Return a copy of the string by its 2-byte key or 3-byte sequence. """
        return str(self.retrieve(key))

    def store(self, in_str, address=None):
        """ Store a new string and return the string pointer. """
        size = len(in_str)
        # don't store overlong strings
        if size > 255:
            raise error.RunError(error.STRING_TOO_LONG)
        if address is None:
            # reserve string space; collect garbage if necessary
            check_free_memory(size, error.OUT_OF_STRING_SPACE)
            # find new string address
            self.current -= size
            address = self.current + 1
        key = str(vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(address)))
        # don't store empty strings
        if size > 0:
            if key in self.strings:
                logging.debug('String key %s at %d already defined.' % (repr(key), address))
            # copy and convert to bytearray
            self.strings[key] = bytearray(in_str)
        return vartypes.bytes_to_string(chr(size) + key)

    def delete_last(self):
        """ Delete the string provided if it is at the top of string space. """
        last_address = self.current + 1
        last_key = str(vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(last_address)))
        try:
            length = len(self.strings[last_key])
            self.current += length
            del self.strings[last_key]
        except KeyError:
            # happens if we're called before an out-of-memory exception is handled
            # and the string wasn't allocated
            pass

    def address(self, key):
        """ Return the address of a given key. """
        return vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(key[-2:]))

    def __enter__(self):
        """ Enter temp-string context guard. """
        self.temp = self.current

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Exit temp-string context guard. """
        if self.temp != self.current:
            self.delete_last()


def copy_str(basic_string):
    """ Return a copy of a string from its string pointer. """
    try:
        return str(bytearray(view_str(basic_string)))
    except KeyError:
        # 'Not a field string'
        length = vartypes.string_length(basic_string)
        return '\0'*length


def view_str(basic_string):
    """ Return a writeable view of a string from its string pointer. """
    length = vartypes.string_length(basic_string)
    address = vartypes.string_address(basic_string)
    # address >= memory.var_start(): if we no longer double-store code strings in string space object
    if address >= memory.code_start:
        # string stored in string space
        sequence = vartypes.string_to_bytes(basic_string)
        return memoryview(state.basic_state.strings.retrieve(sequence))
    else:
        # string stored in field buffers
        # find the file we're in
        start = address - memory.field_mem_start
        number = 1 + start // memory.field_mem_offset
        offset = start % memory.field_mem_offset
        if (number not in state.io_state.fields) or (start < 0):
            raise KeyError('Not a field string')
        # memoryview slice continues to point to buffer, does not copy
        return memoryview(state.io_state.fields[number].buffer)[offset:offset+length]

def set_str(basic_string, in_str, offset=None, num=None):
    """ Assign a new string into an existing buffer. """
    # if it is a code literal, we now do need to allocate space for a copy
    address = vartypes.string_address(basic_string)
    if address >= memory.code_start and address < memory.var_start():
        basic_string = state.basic_state.strings.store(copy_str(basic_string))
    if num is None:
        view_str(basic_string)[:] = in_str
    else:
        view_str(basic_string)[offset:offset+num] = in_str
    return basic_string


###############################################################################
# scalar variables

def var_size_bytes(name):
    """ Return the size of a variable, if it exists. Raise ILLEGAL FUNCTION CALL otherwise. """
    try:
        return vartypes.byte_size[name[-1]]
    except KeyError:
        raise error.RunError(error.IFC)


class Scalars(object):
    """ Scalar variables. """

    def __init__(self):
        """ Initialise scalars. """
        self.clear()

    def set(self, name, value=None):
        """ Assign a value to a variable. """
        name = vartypes.complete_name(name)
        type_char = name[-1]
        if value is not None:
            value = vartypes.pass_type(type_char, value)
        # update memory model
        # check if garbage needs collecting before allocating memory
        if name not in state.basic_state.var_memory:
            # don't add string length, string already stored
            size = (max(3, len(name)) + 1 + vartypes.byte_size[type_char])
            check_free_memory(size, error.OUT_OF_MEMORY)
            # first two bytes: chars of name or 0 if name is one byte long
            name_ptr = state.basic_state.var_current
            # byte_size first_letter second_letter_or_nul remaining_length_or_nul
            var_ptr = name_ptr + max(3, len(name)) + 1
            state.basic_state.var_current += max(3, len(name)) + 1 + vartypes.byte_size[name[-1]]
            state.basic_state.var_memory[name] = (name_ptr, var_ptr)
        # don't change the value if just checking allocation
        if value is None:
            if name in self.variables:
                return
            else:
                value = vartypes.null(type_char)
        # copy buffers
        try:
            # in-place copy is crucial for FOR
            self.variables[name][:] = value[1][:]
        except KeyError:
            # copy into new buffer if not existing
            self.variables[name] = value[1][:]

    def get(self, name):
        """ Retrieve the value of a scalar variable. """
        name = vartypes.complete_name(name)
        try:
            return (name[-1], self.variables[name])
        except KeyError:
            return vartypes.null(name[-1])

    def clear(self):
        """ Clear scalar variables. """
        self.variables = {}
        state.basic_state.var_memory = {}
        state.basic_state.var_current = memory.var_start()


###############################################################################
# arrays

class Arrays(object):

    def __init__(self):
        """ Initialise arrays. """
        self.clear()

    def clear(self):
        """ Clear arrays. """
        self.arrays = {}
        state.basic_state.array_memory = {}
        # arrays are always kept after all vars
        state.basic_state.array_current = 0


    def erase(self, name):
        """ Remove an array from memory. """
        try:
            del self.arrays[name]
        except KeyError:
            # illegal fn call
            raise error.RunError(error.IFC)

    def index(self, index, dimensions):
        """ Return the flat index for a given dimensioned index. """
        bigindex = 0
        area = 1
        for i in range(len(index)):
            # dimensions is the *maximum index number*, regardless of self.base_index
            bigindex += area*(index[i]-self.base_index)
            area *= (dimensions[i]+1-self.base_index)
        return bigindex

    def array_len(self, dimensions):
        """ Return the flat length for given dimensioned size. """
        return self.index(dimensions, dimensions) + 1

    def array_size_bytes(self, name):
        """ Return the byte size of an array, if it exists. Return 0 otherwise. """
        try:
            dimensions, _, _ = self.arrays[name]
        except KeyError:
            return 0
        return self.array_len(dimensions) * var_size_bytes(name)

    def dim(self, name, dimensions):
        """ Allocate array space for an array of given dimensioned size. Raise errors if duplicate name or illegal index value. """
        if self.base_index is None:
            self.base_index = 0
        name = vartypes.complete_name(name)
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
        name_ptr = state.basic_state.array_current
        record_len = 1 + max(3, len(name)) + 3 + 2*len(dimensions)
        array_ptr = name_ptr + record_len
        array_bytes = size*var_size_bytes(name)
        check_free_memory(record_len + array_bytes, error.OUT_OF_MEMORY)
        state.basic_state.array_current += record_len + array_bytes
        state.basic_state.array_memory[name] = (name_ptr, array_ptr)
        try:
            self.arrays[name] = [ dimensions, bytearray(array_bytes), 0 ]
        except OverflowError:
            # out of memory
            raise error.RunError(error.OUT_OF_MEMORY)
        except MemoryError:
            # out of memory
            raise error.RunError(error.OUT_OF_MEMORY)

    def check_dim(self, name, index):
        """ Check if an array has been allocated. If not, auto-allocate if indices are <= 10; raise error otherwise. """
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

    def base(self, base):
        """ Set the array base to 0 or 1 (OPTION BASE). Raise error if already set. """
        if base not in (1, 0):
            # syntax error
            raise error.RunError(error.STX)
        if self.base_index is not None and base != self.base_index:
            # duplicate definition
            raise error.RunError(error.DUPLICATE_DEFINITION)
        self.base_index = base

    def get(self, name, index):
        """ Retrieve the value of an array element. """
        dimensions, lst = self.check_dim(name, index)
        bigindex = self.index(index, dimensions)
        value = lst[bigindex*var_size_bytes(name):(bigindex+1)*var_size_bytes(name)]
        return (name[-1], value)

    def set(self, name, index, value):
        """ Assign a value to an array element. """
        dimensions, lst = self.check_dim(name, index)
        bigindex = self.index(index, dimensions)
        # make a copy of the value, we don't want them to be linked
        value = (vartypes.pass_type(name[-1], value)[1])[:]
        bytesize = var_size_bytes(name)
        lst[bigindex*bytesize:(bigindex+1)*bytesize] = value
        # inc version
        self.arrays[name][2] += 1


###############################################################################
# generic variable access

def get_variable(name, indices):
    """ Retrieve the value of a scalar variable or an array element. """
    if indices == []:
        return state.basic_state.session.scalars.get(name)
    else:
        # array is allocated if retrieved and nonexistant
        return state.basic_state.session.arrays.get(name, indices)

def set_variable(name, indices, value):
    """ Assign a value to a scalar variable or an array element. """
    if indices == []:
        state.basic_state.session.scalars.set(name, value)
    else:
        state.basic_state.session.arrays.set(name, indices, value)

def swap(name1, index1, name2, index2):
    """ Swap two variables by reference (Strings) or value (everything else). """
    if name1[-1] != name2[-1]:
        # type mismatch
        raise error.RunError(error.TYPE_MISMATCH)
    elif ((index1 == [] and name1 not in state.basic_state.session.scalars.variables) or
            (index1 != [] and name1 not in state.basic_state.session.arrays.arrays) or
            (index2 == [] and name2 not in state.basic_state.session.scalars.variables) or
            (index2 != [] and name2 not in state.basic_state.session.arrays.arrays)):
        # illegal function call
        raise error.RunError(error.IFC)
    typechar = name1[-1]
    size = vartypes.byte_size[typechar]
    # get buffers (numeric representation or string pointer)
    if index1 == []:
        p1, off1 = state.basic_state.session.scalars.variables[name1], 0
    else:
        dimensions, p1, _ = state.basic_state.session.arrays.arrays[name1]
        off1 = state.basic_state.session.arrays.index(index1, dimensions)*size
    if index2 == []:
        p2, off2 = state.basic_state.session.scalars.variables[name2], 0
    else:
        dimensions, p2, _ = state.basic_state.session.arrays.arrays[name2]
        off2 = state.basic_state.session.arrays.index(index2, dimensions)*size
    # swap the contents
    p1[off1:off1+size], p2[off2:off2+size] =  p2[off2:off2+size], p1[off1:off1+size]
    # inc version
    if name1 in state.basic_state.session.arrays.arrays:
        state.basic_state.session.arrays.arrays[name1][2] += 1
    if name2 in state.basic_state.session.arrays.arrays:
        state.basic_state.session.arrays.arrays[name2][2] += 1


###############################################################################
# variable memory

def clear_variables(preserve_common=False, preserve_all=False, preserve_deftype=False):
    """ Reset and clear variables, arrays, common definitions and functions. """
    if not preserve_deftype:
        # deftype is not preserved on CHAIN with ALL, but is preserved with MERGE
        state.basic_state.deftype = ['!']*26
    if not preserve_all:
        if preserve_common:
            # preserve COMMON variables (CHAIN does this)
            common, common_arrays = {}, {}
            for varname in state.basic_state.common_names:
                try:
                    common[varname] = state.basic_state.session.scalars.variables[varname]
                except KeyError:
                    pass
            for varname in state.basic_state.common_array_names:
                try:
                    common_arrays[varname] = state.basic_state.session.arrays.arrays[varname]
                except KeyError:
                    pass
        else:
            # clear OPTION BASE
            state.basic_state.arrays.base_index = None
            common = {}
            common_arrays = {}
            # at least I think these should be cleared by CLEAR?
            state.basic_state.common_names = []
            state.basic_state.common_array_names = []
        # restore only common variables
        # this is a re-assignment which is not FOR-safe; but clear_variables is only called in CLEAR which also clears the FOR stack
        state.basic_state.scalars.clear()
        state.basic_state.arrays.clear()
        # functions are cleared except when CHAIN ... ALL is specified
        state.basic_state.functions = {}
        # reset string space
        new_strings = StringSpace()
        # preserve common variables
        # use set_scalar and dim_array to rebuild memory model
        for v in common:
            full_var = (v[-1], common[v])
            if v[-1] == '$':
                full_var = new_strings.store(copy_str(full_var))
            state.basic_state.scalars.set(v, full_var)
        for a in common_arrays:
            state.basic_state.session.arrays.dim(a, common_arrays[a][0])
            if a[-1] == '$':
                s = bytearray()
                for i in range(0, len(common_arrays[a][1]), vartypes.byte_size['$']):
                    old_ptr = vartypes.bytes_to_string(common_arrays[a][1][i:i+vartypes.byte_size['$']])
                    new_ptr = new_strings.store(copy_str(old_ptr))
                    s += vartypes.string_to_bytes(new_ptr)
                state.basic_state.session.arrays.arrays[a][1] = s
            else:
                state.basic_state.session.arrays.arrays[a] = common_arrays[a]
        state.basic_state.strings = new_strings


def collect_garbage():
    """ Collect garbage from string space. Compactify string storage. """
    string_list = []
    # copy all strings that are actually referenced
    for name in state.basic_state.session.scalars.variables:
        if name[-1] == '$':
            v = state.basic_state.session.scalars.variables[name]
            try:
                string_list.append((v, 0,
                        state.basic_state.strings.address(v),
                        state.basic_state.strings.retrieve(v)))
            except KeyError:
                # string is not located in memory - FIELD or code
                pass
    for name in state.basic_state.session.arrays.arrays:
        if name[-1] == '$':
            # ignore version - we can't put and get into string arrays
            dimensions, lst, _ = state.basic_state.session.arrays.arrays[name]
            for i in range(0, len(lst), 3):
                v = lst[i:i+3]
                try:
                    string_list.append((lst, i,
                            state.basic_state.strings.address(v),
                            state.basic_state.strings.retrieve(v)))
                except KeyError:
                    # string is not located in memory - FIELD or code
                    pass
    # sort by str_ptr, largest first (maintain order of storage)
    string_list.sort(key=itemgetter(2), reverse=True)
    # clear the string buffer and re-store all referenced strings
    state.basic_state.strings.clear()
    for item in string_list:
        # re-allocate string space
        item[0][item[1]:item[1]+3] = state.basic_state.strings.store(item[3])[1]

def fre():
    """ Return the amount of memory available to variables, arrays, strings and code. """
    return state.basic_state.strings.current - state.basic_state.var_current - state.basic_state.array_current

def check_free_memory(size, err):
    """ Check if sufficient free memory is avilable, raise error if not. """
    if fre() <= size:
        collect_garbage()
        if fre() <= size:
            raise error.RunError(err)
