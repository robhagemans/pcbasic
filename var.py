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

import error
import vartypes
from string_ptr import StringPtr

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
byte_size = {'$':3, '%':2, '!':4, '#':8}

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
        if len(str(vartypes.unpack_string(value)))>255:
            # this is a copy if we use StringPtr!
            value = vartypes.pack_string(str(vartypes.unpack_string(value)[:255]))
    variables[name] = vartypes.pass_type_keep(name[-1], value)[1]
    
def get_var(name):
    name = vartypes.complete_name(name)
    try:
        if name[-1] == '$':
            return vartypes.pack_string(str(variables[name]) ) # cast StringPtrs, if any
        else:
            return (name[-1], variables[name])
    except KeyError:
        return vartypes.null[name[-1]]

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

#######################################

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

def var_size_bytes(name):
    try:
        return byte_size[name[-1]]  
    except KeyError:
        raise error.RunError(5)

def array_size_bytes(name):
    try:
        [dimensions, lst] = arrays[name]
    except KeyError:
        return 0
    size = array_len(dimensions)
    return size*var_size_bytes(name)     

def dim_array(name, dimensions):
    global arrays
    name = vartypes.complete_name(name)
    if name in arrays:
        # duplicate definition
        raise error.RunError(10)
    for d in dimensions:
        if d < 0:
            # illegal function call
            raise error.RunError(5)
        elif d < array_base:
            # subscript out of range
            raise error.RunError(9)
    size = array_len(dimensions)
    if name[-1]=='$':
        arrays[name] = [ dimensions, ['']*size ]  
    else:
        arrays[name] = [ dimensions, bytearray(size*var_size_bytes(name)) ]  

def check_dim_array(name, index):
    try:
        [dimensions, lst] = arrays[name]
    except KeyError:
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

def get_bytearray(name):
    if name[-1]=='$':
        # can't use string arrays for get/put
        raise error.RunError(13) # type mismatch
    try:
        [_, lst] = arrays[name]
        return lst
    except KeyError:
        return bytearray()

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
    if name[-1]=='$':
        return (name[-1], lst[bigindex])
    value = lst[bigindex*var_size_bytes(name):(bigindex+1)*var_size_bytes(name)]
    if name[-1]=='%':
        return ('%', vartypes.sint_to_value(value))
    else:
        return (name[-1], value)
    
def set_array(name, index, value):
    [dimensions, lst] = check_dim_array(name, index)
    bigindex = index_array(index, dimensions)
    value = vartypes.pass_type_keep(name[-1], value)[1]
    if name[-1]=='$':
       lst[bigindex] = value
       return 
    bytesize = var_size_bytes(name)
    if name[-1]=='%':
        lst[bigindex*bytesize:(bigindex+1)*bytesize] = vartypes.value_to_sint(value)
    else:
        lst[bigindex*bytesize:(bigindex+1)*bytesize] = value
    
def get_var_or_array(name, indices):
    if indices == []:
        return get_var(name)            
    else:
        return get_array(name, indices)

def set_var_or_array(name, indices, value):
    if indices == []:    
        set_var(name, value)
    else:
        set_array(name, indices, value)
        
def set_field_var(field, varname, offset, length):
    if varname[-1] != '$':
        # type mismatch
        raise error.RunError(13)
    str_ptr = StringPtr(field, offset, length)
    # assign the string ptr to the variable name
    # desired side effect: if we re-assign this string variable through LET, it's no longer connected to the FIELD.
    set_var(varname, vartypes.pack_string(str_ptr))
    
def lset(varname, value, justify_right=False):
    if varname[-1] != '$' or value[0] != '$':
        # type mismatch
        raise error.RunError(13)
    s = vartypes.unpack_string(value)
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
        dimensions, lst = arrays[name]
        mem_used += 2*len(dimensions)    
        if name[-1] == '$':
            for mem in lst:
                mem_used += len(mem)
    return mem_used


