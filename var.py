#
# PC-BASIC 3.23 - var.py
#
# Variable & array management
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from cStringIO import StringIO

import error
import fp
import vartypes
import util


variables = {}
arrays= {}
functions = {}

array_base = 0

# set by COMMON
common_names = []
common_array_names = []


# 'free memory' as reported by FRE
total_mem = 60300    
free_mem = total_mem    



# string pointer implementation, allows for unions of strings (for FIELD)
class StringPtr:
    def __init__(self):
        self.stream = None
        self.offset = 0
        self.length = 0
        
    def get_str(self):
        pos = self.stream.tell()
        self.stream.seek(self.offset)
        sstr = self.stream.read(self.length)
        self.stream.seek(pos)
        return sstr
         
    def set_str(self, in_str):
        pos = self.stream.tell()
        ins = StringIO(in_str)
        self.stream.seek(self.offset)    
        for _ in range(self.length):
            c = ins.read(1)
            if c=='':
                c=' '
            self.stream.write(c)    
        self.stream.seek(pos)
        
    def __str__(self):
        return self.get_str()
        
    def __len__(self):
        return self.length

    
def create_string_ptr(stream, offset, length):
    new = StringPtr()
    if isinstance(stream, StringPtr):
        new.stream, new.offset, new.length = stream.stream, stream.offset+offset, length     
        max_length = stream.length
    else:
        new.stream= StringIO(stream)
        new.stream.seek(0)    
        max_length = len(stream)
        new.offset, new.length = offset, length
    # BASIC string length limit
    if new.length>255:
        new.length=255
    if new.offset+new.length > max_length:
        new.length = max_length-new.offset
        if new.length<0:
            new.length=0    
    return new
    
    

##########################################################

def clear_variables():
    global variables, arrays, array_base, functions, common_names, common_array_names
    variables = {}
    arrays = {}
    array_base = 0
    functions = {}
    vartypes.deftype = ['!']*26
    # at least I think these should be cleared by CLEAR?
    common_names = []
    common_array_names = []


def set_var(name, value):
    global variables
    name = vartypes.complete_name(name)
    if value[0]=='$':
        if len(str(value[1]))>255:
            # this is a copy if we use StringPtr!
            value = ('$', str(value[1][:255]))
    variables[name] = vartypes.pass_type_keep(name[-1], value)[1]
    
    
def get_var(name):
    name = vartypes.complete_name(name)
    try:
        if name[-1] == '$':
            return ('$', str(variables[name]) ) # cast StringPtrs, if any
        else:
            return (name[-1], variables[name])
    except KeyError:
        return vartypes.null_keep(name[-1])


def swap_var(name1, name2):
    global variables
    name1 = vartypes.complete_name(name1)
    name2 = vartypes.complete_name(name2)
    if name1[-1] != name2[-1]:
        # type mismatch
        raise error.RunError(13)
    elif name1 not in variables or name2 not in variables:
        # illegal function call
        raise error.RunError(5)
    else:
        val1 = variables[name1] # we need a pointer swap #get_var(name1)
        variables[name1] = variables[name2]
        variables[name2] = val1
        

def erase_array(name):
    global arrays
    try: 
        del arrays[name]
    except KeyError:
        # illegal fn call
        raise error.RunError(5)    


def index_array(index, dimensions):
    bigindex = 0
    area = 1
    for i in range(len(index)):
        # WARNING: dimensions is the *maximum index number*, regardless of array_base!
        bigindex += area*(index[i]-array_base)
        area *= (dimensions[i]+1-array_base)
    return bigindex 

    
def array_len(dimensions):
    return index_array(dimensions, dimensions)+1    


def dim_array(name, dimensions):
    global arrays
    name = vartypes.complete_name(name)
    if name in arrays:
        # duplicate definition
        raise error.RunError(10)
    for d in dimensions:
        if d < 0:
            # illegal function call
            raise error.RunError (5)
        elif d < array_base:
            # subscript out of range
            raise error.RunError (9)
    size = array_len(dimensions)
    arrays[name] = [ dimensions, [vartypes.null_keep(name[-1])[1]]*size ]  


def check_dim_array(name, index):
    if name not in arrays:
        # auto-dimension - 0..10 or 1..10 
        # this even fixes the dimensions if the index turns out to be out of range!
        dimensions = [ 10 ] * len(index)
        dim_array(name, dimensions)
    [dimensions, lst] = arrays[name]
    if len(index) != len(dimensions):
        raise error.RunError(9)
    for i in range(len(index)):
        if index[i] < 0:
            raise error.RunError(5)
        elif index[i] < array_base or index[i] > dimensions[i]: 
            # WARNING: dimensions is the *maximum index number*, regardless of array_base!
            raise error.RunError(9)
    return [dimensions, lst]


def var_size_bytes(name):
    if name[-1] == '$':
        raise error.RunError(5)
    elif name[-1] == '%':
        return 2
    elif name[-1] == '!':
        return 4    
    elif name[-1] == '#':
        return 8        


def array_size_bytes(name):
    try:
        [dimensions, lst] = arrays[name]
    except KeyError:
        return 0
    size = array_len(dimensions)
    return size*var_size_bytes(name)     


def get_array_byte(name, byte_num):
    try:
        [dimensions, lst] = arrays[name]
    except KeyError:
        return '\x00'
    bytespernumber = var_size_bytes(name)
    bigindex = byte_num / bytespernumber
    if bigindex >= len(lst):
        return '\x00'
    number = lst[bigindex]    
    byteindex = byte_num % bytespernumber        
    if name[-1]=='%':
        return (vartypes.value_to_sint(number))[byteindex] 
    elif name[-1]=='!':
        return (number)[byteindex]
    elif name[-1]=='#':
        return (number)[byteindex]
    return '\x00'       


def set_array_byte(name, byte_num, value):
    try:    
        [dimensions, lst] = arrays[name]
    except KeyError:
        return 0
    bytespernumber = var_size_bytes(name)
    bigindex = byte_num / bytespernumber
    if bigindex >= len(lst):
        return 0
    number = lst[bigindex]    
    byteindex = byte_num % bytespernumber        
    if name[-1]=='%':
        bytepair = list(vartypes.value_to_sint(number))
        bytepair[byteindex] = value
        #number = ('%', vartypes.sint_to_value(bytepair) )
        number = vartypes.sint_to_value(bytepair)
    elif name[-1] in ('!', '#'):
        byte_array = list(number)
        byte_array[byteindex] = value
        number=byte_array
    # still referencing the stored array
    lst[bigindex] = number    


def base_array(base):
    global array_base
    if base not in (1, 0):
        # syntax error
        raise error.RunError(2)    
    if arrays != {}:
        # duplicate definition
        raise error.RunError(10)
    array_base = base


def get_array(name, index):
    [dimensions, lst] = check_dim_array(name, index)
    bigindex = index_array(index, dimensions)
    return (name[-1], lst[bigindex])

    
def set_array(name, index, value):
    [dimensions, lst] = check_dim_array(name, index)
    bigindex = index_array(index, dimensions)
    lst[bigindex] = vartypes.pass_type_keep(name[-1], value)[1]

    
def get_var_or_array(name, indices):
    if indices == []:
        return get_var(name)            
    else:
        return get_array(name, indices)


def set_var_or_array(name, indices, value):
    if indices != []:    
        set_array(name, indices, value)
    else:
        set_var(name, value)


def set_field_var(field, varname, offset, length):
    if varname[-1] != '$':
        # type mismatch
        raise error.RunError(13)
    str_ptr = create_string_ptr(field, offset, length)
    # assign the string ptr to the variable name
    # desired side effect: if we re-assign this string variable through LET, it's no longer connected to the FIELD.
    set_var(varname, ('$', str_ptr))

    
def lset(varname, value, justify_right=False):
    if varname[-1] != '$' or value[0] != '$':
        # type mismatch
        raise error.RunError(13)
    s = value[1]
    try:
        el = len(variables[varname])    
    except KeyError:
        return
    if len(s) > el:
        s = s[:el]
    if len(s) < el:
        if justify_right:
            s = ' '*(el-len(s)) + s
        else:
            s += ' '*(el-len(s))
    if isinstance(variables[varname], StringPtr):
        variables[varname].set_str(s)    
    else:
        variables[varname] = s    


# for reporting by FRE()        
def variables_memory_size():
    mem_used = 0
    for name in variables:
        mem_used += 1 + max(3, len(name))
        if name[-1] == '$':
            mem_used += 3+len(variables[name])
        else:
            mem_used += var_size_bytes(name)
    for name in arrays:
        mem_used += 4 + array_size_bytes(name) + max(3, len(name))
        dimensions, dummy = arrays[name]
        mem_used += 2*len(dimensions)    
        # can't have array of strings
    return mem_used


