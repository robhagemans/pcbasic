#
# PC-BASIC 3.23 - machine.py
#
# Machine emulation and memory model 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

import config
import state
import backend
import vartypes
import var
import console
import error

# pre-defined PEEK outputs
peek_values = {}

# data memory model: data segment
data_segment = 0x13ad
# data memory model: current segment
state.basic_state.segment = data_segment
# lowest (EGA) video memory address
video_segment = 0xa000
font_segment = 0xf000
font_addr = 0xfa6e
low_segment = 0x40

def prepare():
    """ Initialise machine module. """ 
    try:
        for a in config.options['peek']:
            seg, addr, val = a.split(':')
            peek_values[int(seg)*0x10 + int(addr)] = int(val)
    except (TypeError, ValueError):
        pass     

def peek(addr):
    if addr < 0: 
        addr += 0x10000
    addr += state.basic_state.segment*0x10
    try:
        # try if there's a preset value
        return peek_values[addr]
    except KeyError: 
        if addr >= font_segment*0x10+ font_addr:
            return max(0, get_font_memory(addr))
        elif addr >= video_segment*0x10:
            # graphics and text memory
            return max(0, get_video_memory(addr))
        elif addr >= data_segment*0x10 + var.var_mem_start:
            # variable memory
            return max(0, get_data_memory(addr))
        elif addr >= data_segment*0x10 + var.field_mem_start:
            # file & FIELD memory
            return max(0, get_field_memory(addr))
        elif addr >= low_segment*0x10:
            return max(0, get_low_memory(addr))
        else:    
            return 0

def poke(addr, val):    
    if addr < 0: 
        addr += 0x10000
    addr += state.basic_state.segment * 0x10
    if addr >= font_segment*0x10+ font_addr:
        # that's ROM it seems
        pass
    elif addr >= video_segment*0x10:
        # can't poke into font memory, ignored even in GW-BASIC. ROM?
        # graphics and text memory
        set_video_memory(addr, val)
    elif addr >= data_segment*0x10 + var.var_mem_start:
        # POKING in variables not implemented
        #set_data_memory(addr, val)
        # just use it as storage...
        peek_values[addr] = val
    else:
        pass
        
def inp(port):    
    if port == 0x60:
        backend.wait()
        return state.console_state.inp_key 
    else:
        return 0
        
def out(addr, val):    
    if addr == 0x3c5:
        # officially, requires OUT &H3C4, 2 first (not implemented)
        state.console_state.colour_plane_write_mask = val
    elif addr == 0x3cf:
        # officially, requires OUT &H3CE, 4 first (not implemented)
        state.console_state.colour_plane = val        
    elif addr == 0x3d8:
        #OUT &H3D8,&H1A: REM enable color burst
        #OUT &H3D8,&H1E: REM disable color burst
        # 0x1a == 0001 1010     0x1e == 0001 1110
        backend.set_colorburst(val & 4 == 0)

def wait(addr, ander, xorer):
    store_suspend = state.basic_state.suspend_all_events
    state.basic_state.suspend_all_events = True
    while (((state.console_state.inp_key if addr == 0x60 else 0) ^ xorer) & ander) == 0:
        backend.wait()
    state.basic_state.suspend_all_events = store_suspend     

def bload(g, offset):    
    if g.read(1) != '\xfd':
        raise error.RunError(54)
    seg = vartypes.uint_to_value(bytearray(g.read(2)))
    foffset = vartypes.uint_to_value(bytearray(g.read(2)))
    if offset == None:
        offset = foffset
    # size. this gets ignored; even the \x1a at the end gets dumped onto the screen.
    vartypes.uint_to_value(bytearray(g.read(2))) 
    buf = bytearray()
    while True:
        c = g.read(1)
        if c == '':
            break
        buf += c
    # remove any EOF marker at end 
    if buf and buf[-1] == 0x1a:  
        buf = buf[:-1]
    g.close()
    addr = seg * 0x10 + offset
    if addr + len(buf) > video_segment*0x10:
        # graphics and text memory
        set_video_memory_block(addr, buf)

def bsave(g, offset, length):
    g.write('\xfd')
    g.write(str(vartypes.value_to_uint(state.basic_state.segment)))
    g.write(str(vartypes.value_to_uint(offset)))
    g.write(str(vartypes.value_to_uint(length)))
    addr = state.basic_state.segment * 0x10 + offset
    g.write(str(get_video_memory_block(addr, length)))
    g.write('\x1a')
    g.close()

def varptr(name, indices):
    name = vartypes.complete_name(name)
    if indices == []:
        try:
            _, var_ptr = state.basic_state.var_memory[name]
            return var_ptr
        except KeyError:
            return -1
    else:
        try:
            dimensions, _, _ = state.basic_state.arrays[name]
            _, array_ptr = state.basic_state.array_memory[name]
            # arrays are kept at the end of the var list
            return state.basic_state.var_current + array_ptr + var.var_size_bytes(name) * var.index_array(indices, dimensions) 
        except KeyError:
            return -1


def get_name_in_memory(name, offset):
    if offset == 0:
        return var.byte_size[name[-1]]
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

def get_field_memory(address):
    address -= data_segment * 0x10
    if address < var.field_mem_start:
        return -1
    # find the file we're in
    start = address - var.field_mem_start
    number = 1 + start // var.field_mem_offset
    offset = start % var.field_mem_offset
    try:
        return state.io_state.fields[number][offset]
    except KeyError, IndexError:
        return -1    
                            
def get_data_memory(address):
    address -= data_segment * 0x10
    if address < state.basic_state.var_current:
        # find the variable we're in
        name_addr = -1
        var_addr = -1
        the_var = None 
        for name in state.basic_state.var_memory:
            name_ptr, var_ptr = state.basic_state.var_memory[name]
            if name_ptr <= address and name_ptr > name_addr:
                name_addr, var_addr = name_ptr, var_ptr
                the_var = name
        if the_var == None:
            return -1        
        if address >= var_addr:
            offset = address - var_addr
            if offset >= var.byte_size[the_var[-1]]:
                return -1
            var_rep = state.basic_state.variables[the_var]
            return var_rep[offset]
        else:
            offset = address - name_ptr
            return get_name_in_memory(the_var, offset)
    elif address < state.basic_state.var_current + state.basic_state.array_current:
        name_addr = -1
        arr_addr = -1
        the_arr = None 
        for name in state.basic_state.array_memory:
            name_ptr, arr_ptr = state.basic_state.array_memory[name]
            if name_ptr <= address and name_ptr > name_addr:
                name_addr, arr_addr = name_ptr, arr_ptr
                the_arr = name
        if the_arr == None:
            return -1        
        if address >= state.basic_state.var_current + arr_addr:
            offset = address - arr_addr - state.basic_state.var_current
            if offset >= var.array_size_bytes(the_arr):
                return -1
            _, byte_array, _ = state.basic_state.arrays[the_arr]    
            return byte_array[offset]
        else:
            offset = address - name_ptr - state.basic_state.var_current
            if offset < max(3, len(the_arr))+1:
                return get_name_in_memory(the_arr, offset)
            else:
                offset -= max(3, len(the_arr))+1
                dimensions, _, _ = state.basic_state.arrays[the_arr]
                data_rep = vartypes.value_to_uint(var.array_size_bytes(the_arr) + 1 + 2*len(dimensions)) + chr(len(dimensions)) 
                for d in dimensions:
                    data_rep += vartypes.value_to_uint(d + 1 - state.basic_state.array_base)
                return data_rep[offset]               
    elif address > state.basic_state.strings.current:
        # string space
        # find the variable we're in
        str_nearest = -1
        the_var = None 
        for name in state.basic_state.variables:
            if name[-1] != '$':
                continue
            v = state.basic_state.variables[name]
            str_ptr = state.basic_state.strings.address(v)
            if str_ptr <= address and str_ptr > str_nearest:
                str_nearest = str_ptr
                the_var = v
        if the_var == None:
            for name in state.basic_state.arrays:
                if name[-1] != '$':
                    continue
                _, lst, _ = state.basic_state.arrays[name]
                for i in range(0, len(lst), 3):
                    str_ptr = state.basic_state.strings.address(lst[i:i+3])
                    if str_ptr <= address and str_ptr > str_nearest:
                        str_nearest = str_ptr
                        the_var = lst[i:i+3]
        try:
            return state.basic_state.strings.retrieve(v)[address - str_nearest]
        except IndexError, AttributeError:
            return -1
    else:
        # unallocated var space
        return -1
        
    
###############################################################
# video memory model
    
def get_video_memory(addr):
    """ Retrieve a byte from video memory. """
    return state.console_state.current_mode.get_memory(addr)

def set_video_memory(addr, val):
    """ Set a byte in video memory. """
    return state.console_state.current_mode.set_memory(addr, val)

def get_video_memory_block(addr, length):
    """ Retrieve a contiguous block of bytes from video memory. """
    block = bytearray()
    for a in range(addr, addr+length):
        block += chr(max(0, get_video_memory(a)))
        # keep updating the screen
        # we're not allowing keyboard breaks here 
        # in GW this is so fast that you can't check if it does or not
        backend.video.check_events()
    return block
    
def set_video_memory_block(addr, some_bytes):
    """ Set a contiguous block of bytes in video memory. """
    for a in range(len(some_bytes)):
        set_video_memory(addr + a, some_bytes[a])
        # keep updating the screen
        # we're not allowing keyboard breaks here 
        backend.video.check_events()
    

#################################################################################

def get_font_memory(addr):
    addr -= font_segment*0x10 + font_addr
    char = addr // 8
    if char > 127 or char<0:
        return -1
    return ord(backend.video.fonts[8][chr(char)][addr%8])

#################################################################################

def get_low_memory(addr):
    addr -= low_segment*0x10
    # from MEMORY.ABC: PEEKs and POKEs (Don Watkins)
    # http://www.qbasicnews.com/abc/showsnippet.php?filename=MEMORY.ABC&snippet=6
    # &h40:&h17 keyboard flag
    # &H80 - Insert state active
    # &H40 - CapsLock state has been toggled
    # &H20 - NumLock state has been toggled
    # &H10 - ScrollLock state has been toggled
    # &H08 - Alternate key depressed
    # &H04 - Control key depressed
    # &H02 - Left shift key depressed
    # &H01 - Right shift key depressed
    # &h40:&h18 keyboard flag
    # &H80 - Insert key is depressed
    # &H40 - CapsLock key is depressed
    # &H20 - NumLock key is depressed
    # &H10 - ScrollLock key is depressed
    # &H08 - Suspend key has been toggled
    backend.wait()
    if addr == 0x17:
        return state.console_state.mod 
    return -1    
    
prepare()
    
