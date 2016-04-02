"""
PC-BASIC - var.py
Variable & array management

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import logging
from operator import itemgetter
from contextlib import contextmanager

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
        return memoryview(state.session.strings.retrieve(sequence))
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
    if address >= memory.code_start and address < state.session.memory.var_start():
        basic_string = state.session.strings.store(copy_str(basic_string))
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
        if name not in self.var_memory:
            # don't add string length, string already stored
            size = (max(3, len(name)) + 1 + vartypes.byte_size[type_char])
            check_free_memory(size, error.OUT_OF_MEMORY)
            # first two bytes: chars of name or 0 if name is one byte long
            name_ptr = state.session.memory.var_current
            # byte_size first_letter second_letter_or_nul remaining_length_or_nul
            var_ptr = name_ptr + max(3, len(name)) + 1
            state.session.memory.var_current += max(3, len(name)) + 1 + vartypes.byte_size[name[-1]]
            self.var_memory[name] = (name_ptr, var_ptr)
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
        self.var_memory = {}
        state.basic_state.memory.var_current = state.basic_state.memory.var_start()

    def varptr(self, name):
        """ Retrieve the address of a scalar variable. """
        name = vartypes.complete_name(name)
        try:
            _, var_ptr = self.var_memory[name]
            return var_ptr
        except KeyError:
            return -1

    def get_memory(self, address):
        """ Retrieve data from data memory: variable space """
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
            if offset >= vartypes.byte_size[the_var[-1]]:
                return -1
            var_rep = self.variables[the_var]
            return var_rep[offset]
        else:
            offset = address - name_addr
            return get_name_in_memory(the_var, offset)

    @contextmanager
    def preserve(self, names, string_store):
        """ Preserve COMMON variables. """
        common = {}
        for varname in names:
            try:
                common[varname] = self.variables[varname]
            except KeyError:
                pass
        yield
        for v in common:
            full_var = (v[-1], common[v])
            if v[-1] == '$':
                full_var = string_store.store(copy_str(full_var))
            self.set(v, full_var)


###############################################################################
# arrays

class Arrays(object):

    def __init__(self):
        """ Initialise arrays. """
        self.clear()
        # OPTION BASE is unset
        self.base_index = None

    def clear(self):
        """ Clear arrays. """
        self.arrays = {}
        self.array_memory = {}

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
        name_ptr = state.session.memory.array_current
        record_len = 1 + max(3, len(name)) + 3 + 2*len(dimensions)
        array_ptr = name_ptr + record_len
        array_bytes = size*var_size_bytes(name)
        check_free_memory(record_len + array_bytes, error.OUT_OF_MEMORY)
        state.session.memory.array_current += record_len + array_bytes
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

    def clear_base(self):
        """ Unset the array base. """
        self.base_index = None

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

    def varptr(self, name, indices):
        """ Retrieve the address of an array. """
        name = vartypes.complete_name(name)
        try:
            dimensions, _, _ = self.arrays[name]
            _, array_ptr = self.array_memory[name]
            # arrays are kept at the end of the var list
            return state.session.memory.var_current + array_ptr + var_size_bytes(name) * self.index(indices, dimensions)
        except KeyError:
            return -1

    def get_memory(self, address):
        """ Retrieve data from data memory: array space """
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
        if address >= state.session.memory.var_current + arr_addr:
            offset = address - arr_addr - state.session.memory.var_current
            if offset >= self.array_size_bytes(the_arr):
                return -1
            _, byte_array, _ = self.arrays[the_arr]
            return byte_array[offset]
        else:
            offset = address - name_addr - state.session.memory.var_current
            if offset < max(3, len(the_arr))+1:
                return get_name_in_memory(the_arr, offset)
            else:
                offset -= max(3, len(the_arr))+1
                dimensions, _, _ = self.arrays[the_arr]
                data_rep = vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(
                    self.array_size_bytes(the_arr) + 1 + 2*len(dimensions)) + chr(len(dimensions)))
                for d in dimensions:
                    data_rep += vartypes.integer_to_bytes(vartypes.int_to_integer_unsigned(
                                        d + 1 - self.base_index))
                return data_rep[offset]

    @contextmanager
    def preserve(self, names, string_store):
        """ Preserve COMMON variables. """
        common = {}
        for varname in names:
            try:
                common[varname] = self.arrays[varname]
            except KeyError:
                pass
        yield
        for a in common:
            self.dim(a, common[a][0])
            if a[-1] == '$':
                s = bytearray()
                for i in range(0, len(common[a][1]), vartypes.byte_size['$']):
                    old_ptr = vartypes.bytes_to_string(common[a][1][i : i+vartypes.byte_size['$']])
                    new_ptr = string_store.store(copy_str(old_ptr))
                    s += vartypes.string_to_bytes(new_ptr)
                self.arrays[a][1] = s
            else:
                self.arrays[a] = common[a]


###############################################################################
# generic variable access

def get_variable(name, indices):
    """ Retrieve the value of a scalar variable or an array element. """
    if indices == []:
        return state.session.scalars.get(name)
    else:
        # array is allocated if retrieved and nonexistant
        return state.session.arrays.get(name, indices)

def set_variable(name, indices, value):
    """ Assign a value to a scalar variable or an array element. """
    if indices == []:
        state.session.scalars.set(name, value)
    else:
        state.session.arrays.set(name, indices, value)

def varptr(name, indices):
    """Get address of variable. """
    if indices == []:
        return state.session.scalars.varptr(name)
    else:
        return state.session.arrays.varptr(name, indices)

def swap(name1, index1, name2, index2):
    """ Swap two variables by reference (Strings) or value (everything else). """
    if name1[-1] != name2[-1]:
        # type mismatch
        raise error.RunError(error.TYPE_MISMATCH)
    elif ((index1 == [] and name1 not in state.session.scalars.variables) or
            (index1 != [] and name1 not in state.session.arrays.arrays) or
            (index2 == [] and name2 not in state.session.scalars.variables) or
            (index2 != [] and name2 not in state.session.arrays.arrays)):
        # illegal function call
        raise error.RunError(error.IFC)
    typechar = name1[-1]
    size = vartypes.byte_size[typechar]
    # get buffers (numeric representation or string pointer)
    if index1 == []:
        p1, off1 = state.session.scalars.variables[name1], 0
    else:
        dimensions, p1, _ = state.session.arrays.arrays[name1]
        off1 = state.session.arrays.index(index1, dimensions)*size
    if index2 == []:
        p2, off2 = state.session.scalars.variables[name2], 0
    else:
        dimensions, p2, _ = state.session.arrays.arrays[name2]
        off2 = state.session.arrays.index(index2, dimensions)*size
    # swap the contents
    p1[off1:off1+size], p2[off2:off2+size] =  p2[off2:off2+size], p1[off1:off1+size]
    # inc version
    if name1 in state.session.arrays.arrays:
        state.session.arrays.arrays[name1][2] += 1
    if name2 in state.session.arrays.arrays:
        state.session.arrays.arrays[name2][2] += 1


###############################################################################
# variable memory

def clear_variables(preserve_vars, preserve_arrays, new_strings):
    """ Reset and clear variables, arrays, common definitions and functions. """
    # preserve COMMON variables
    # this is a re-assignment which is not FOR-safe;
    # but clear_variables is only called in CLEAR which also clears the FOR stack
    with state.session.scalars.preserve(preserve_vars, new_strings):
        state.session.scalars.clear()
    with state.session.arrays.preserve(preserve_arrays, new_strings):
        state.session.arrays.clear()
    if not(preserve_vars or preserve_arrays):
        # clear OPTION BASE
        state.session.arrays.clear_base()

def collect_garbage():
    """ Collect garbage from string space. Compactify string storage. """
    string_list = []
    # copy all strings that are actually referenced
    for name in state.session.scalars.variables:
        if name[-1] == '$':
            v = state.session.scalars.variables[name]
            try:
                string_list.append((v, 0,
                        state.session.strings.address(v),
                        state.session.strings.retrieve(v)))
            except KeyError:
                # string is not located in memory - FIELD or code
                pass
    for name in state.session.arrays.arrays:
        if name[-1] == '$':
            # ignore version - we can't put and get into string arrays
            dimensions, lst, _ = state.session.arrays.arrays[name]
            for i in range(0, len(lst), 3):
                v = lst[i:i+3]
                try:
                    string_list.append((lst, i,
                            state.session.strings.address(v),
                            state.session.strings.retrieve(v)))
                except KeyError:
                    # string is not located in memory - FIELD or code
                    pass
    # sort by str_ptr, largest first (maintain order of storage)
    string_list.sort(key=itemgetter(2), reverse=True)
    # clear the string buffer and re-store all referenced strings
    state.session.strings.clear()
    for item in string_list:
        # re-allocate string space
        item[0][item[1]:item[1]+3] = state.session.strings.store(item[3])[1]

def fre():
    """ Return the amount of memory available to variables, arrays, strings and code. """
    return state.basic_state.strings.current - state.basic_state.memory.var_current - state.basic_state.memory.array_current

def check_free_memory(size, err):
    """ Check if sufficient free memory is avilable, raise error if not. """
    if fre() <= size:
        collect_garbage()
        if fre() <= size:
            raise error.RunError(err)

def get_value_for_varptrstr(varptrstr):
    """ Get a value given a VARPTR$ representation. """
    if len(varptrstr) < 3:
        raise error.RunError(error.IFC)
    varptrstr = bytearray(varptrstr)
    varptr = vartypes.integer_to_int_unsigned(vartypes.bytes_to_integer(varptrstr[1:3]))
    for name, data in state.session.scalars.var_memory.iteritems():
        if data[1] == varptr:
            return state.session.scalars.get(name)
    # no scalar found, try arrays
    found_addr = -1
    found_name = None
    for name, data in state.session.arrays.array_memory.iteritems():
        addr = state.session.memory.var_current + data[1]
        if addr > found_addr and addr <= varptr:
            found_addr = addr
            found_name = name
    if found_name is None:
        raise error.RunError(error.IFC)
    _, lst, _ = state.session.arrays.arrays[name]
    offset = varptr - found_addr
    return (name[-1], lst[offset : offset+var_size_bytes(name)])


def get_data_memory(address):
    """ Retrieve data from data memory. """
    address -= memory.data_segment * 0x10
    if address < state.session.memory.var_current:
        return state.session.scalars.get_memory(address)
    elif address < state.session.memory.var_current + state.session.memory.array_current:
        return state.session.arrays.get_memory(address)
    elif address > state.session.strings.current:
        return get_data_memory_string(address)
    else:
        # unallocated var space
        return -1

def get_data_memory_string(address):
    """ Retrieve data from data memory: string space """
    # find the variable we're in
    str_nearest = -1
    the_var = None
    for name in state.session.scalars.variables:
        if name[-1] != '$':
            continue
        v = state.session.scalars.variables[name]
        str_try = state.session.strings.address(v)
        if str_try <= address and str_try > str_nearest:
            str_nearest = str_try
            the_var = v
    if the_var is None:
        for name in state.session.arrays.arrays:
            if name[-1] != '$':
                continue
            _, lst, _ = state.session.arrays.arrays[name]
            for i in range(0, len(lst), 3):
                str_try = state.session.strings.address(lst[i:i+3])
                if str_try <= address and str_try > str_nearest:
                    str_nearest = str_try
                    the_var = lst[i:i+3]
    try:
        return state.session.strings.retrieve(the_var)[address - str_nearest]
    except (IndexError, AttributeError, KeyError):
        return -1

def get_name_in_memory(name, offset):
    """ Memory representation of variable name. """
    if offset == 0:
        return vartypes.byte_size[name[-1]]
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


class Memory(object):
    """ Memory model. """

    def __init__(self):
        """ Initialise memory. """
        self.segment = memory.data_segment
        self.var_current = self.var_start()
        # arrays are always kept after all vars
        self.array_current = 0

    def var_start(self):
        """ Start of variable data. """
        return memory.code_start + self.code_size()

    def code_size(self):
        """ Size of code space """
        return len(state.basic_state.program.bytecode.getvalue())
