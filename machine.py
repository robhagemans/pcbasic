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


from operator import itemgetter

import state
import backend
import vartypes
import var
import console
import error
import on_event

# 'free memory' as reported by FRE
total_mem = 60300    
# pre-defined PEEK outputs
peek_values = {}

# data memory model: data segment
data_segment = 0x13ad
# data memory model: current segment
segment = data_segment
# data memory model: start of variables section
var_mem_start = 4720
# program memory model; offsets in files
program_memory_start = 0x126e
# video memory
state.console_state.colour_plane = 3
state.console_state.colour_plane_write_mask = 0xff
video_segment = { 0: 0xb800, 1: 0xb800, 2: 0xb800, 7: 0xa000, 8: 0xa000, 9: 0xa000 }
# memory model: text mode video memory
text_segment = 0xb800

def fre():
    return state.basic_state.string_current - var_mem_start - program_memory_size() - variables_memory_size()

def peek(addr):
    if addr < 0: 
        addr += 0x10000
    addr += segment*0x10
    try:
        # try if there's a preset value
        return peek_values[addr]
    except KeyError: 
        if addr >= video_segment[state.console_state.screen_mode]*0x10:
            # graphics and text memory
            return max(0, get_video_memory(addr))
        elif addr >= data_segment*0x10 + var_mem_start:
            # variable memory
            return max(0, get_data_memory(addr))
        else:    
            return 0

def poke(addr, val):    
    if addr < 0: 
        addr += 0x10000
    addr += segment * 0x10
    if addr >= video_segment[state.console_state.screen_mode]*0x10:
        # graphics and text memory
        set_video_memory(addr, val)
#    elif addr >= data_segment*0x10 + var_mem_start:
#        # variable memory
#        set_data_memory(addr)

def inp(port):    
    if port == 0x60:
        on_event.wait()
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

def wait(addr, ander, xorer):
    store_suspend = state.basic_state.suspend_all_events
    state.basic_state.suspend_all_events = True
    while (((state.console_state.inp_key if addr == 0x60 else 0) ^ xorer) & ander) == 0:
        on_event.wait()
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
    g.close()
    addr = seg * 0x10 + offset
    if addr + len(buf) > video_segment[state.console_state.screen_mode]*0x10:
        # graphics and text memory
        set_video_memory_block(addr, buf)

def bsave(g, offset, length):
    g.write('\xfd')
    g.write(str(vartypes.value_to_uint(segment)))
    g.write(str(vartypes.value_to_uint(offset)))
    g.write(str(vartypes.value_to_uint(length)))
    addr = segment * 0x10 + offset
    g.write(str(get_video_memory_block(addr, length)))
    g.write('\x1a')
    g.close()

def varptr(name, indices):
    name = vartypes.complete_name(name)
    if indices == []:
        try:
            _, var_ptr, _ = state.basic_state.var_memory[name]
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

##########################################
      
def program_memory_size():
    return len(state.basic_state.bytecode.getvalue()) - 4
    
def variables_memory_size():
#   TODO: memory model, does this work: ?
#    return state.basic_state.var_current + state.basic_state.array_current + (state.basic_state.var_current + total_mem - state.basic_state.string_current)
    mem_used = 0
    for name in state.basic_state.variables:
        mem_used += 1 + max(3, len(name))
        # string length incorporated through use of state.basic_state.string_current
        mem_used += var.var_size_bytes(name)
    for name in state.basic_state.arrays:
        mem_used += 4 + var.array_size_bytes(name) + max(3, len(name))
        dimensions, lst, _ = state.basic_state.arrays[name]
        mem_used += 2*len(dimensions)    
        if name[-1] == '$':
            for mem in lst:
                mem_used += len(mem)
    return mem_used

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
                            
def get_data_memory(address):
    address -= segment * 0x10
    if address < state.basic_state.var_current:
        # find the variable we're in
        name_addr = -1
        var_addr = -1
        str_addr = -1
        the_var = None 
        for name in state.basic_state.var_memory:
            name_ptr, var_ptr, str_ptr = state.basic_state.var_memory[name]
            if name_ptr <= address and name_ptr > name_addr:
                name_addr, var_addr, str_addr = name_ptr, var_ptr, str_ptr
                the_var = name
        if the_var == None:
            return -1        
        if address >= var_addr:
            offset = address - var_addr
            if offset >= var.byte_size[the_var[-1]]:
                return -1
            if the_var[-1] == '$':
                # string is represented as 3 bytes: length + uint pointer
                var_rep = bytearray(chr(len(state.basic_state.variables[the_var]))) + vartypes.value_to_uint(str_addr)
            else:
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
            if the_arr[-1] == '$':
                # TODO: not implemented for arrays of strings
                return 0
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
    elif address > state.basic_state.string_current:
        # string space
        # find the variable we're in
        name_addr = -1
        var_addr = -1
        str_addr = -1
        the_var = None 
        for name in state.basic_state.var_memory:
            name_ptr, var_ptr, str_ptr = state.basic_state.var_memory[name]
            if str_ptr <= address and str_ptr > str_addr:
                name_addr, var_addr, str_addr = name_ptr, var_ptr, str_ptr
                the_var = name
        if the_var == None:
            return -1
        offset = address - str_addr
        return state.basic_state.variables[the_var][offset]
    else:
        # unallocated var space
        return 0 
        
def collect_garbage():
    string_list = []
    for name in state.basic_state.var_memory:
        if name[-1] == '$':
            mem = state.basic_state.var_memory[name]
            string_list.append( (name, mem[0], mem[1], mem[2], len(state.basic_state.variables[name])) )
    # sort by str_ptr, largest first        
    string_list.sort(key=itemgetter(3), reverse=True)        
    new_string_current = var_mem_start + total_mem              
    for item in string_list:
        new_string_current -= item[4]
        state.basic_state.var_memory[item[0]] = (item[1], item[2], new_string_current + 1)     
    state.basic_state.string_current = new_string_current
     
    
###############################################################
# video memory model

def get_pixel_byte(page, x, y, plane):
    if y < state.console_state.size[1] and page < state.console_state.num_pages:
        return sum(( ((backend.video.get_pixel(x+shift, y, page) >> plane) & 1) << (7-shift) for shift in range(8) ))
    return -1    
    
def set_pixel_byte(page, x, y, plane_mask, byte):
    if y < state.console_state.size[1] and page < state.console_state.num_pages:
        for shift in range(8):
            bit = (byte>>(7-shift)) & 1
            backend.video.put_pixel(x + shift, y, bit * plane_mask, page)  
    
def get_video_memory(addr):
    if addr < video_segment[state.console_state.screen_mode]*0x10:
        return -1
    else:
        if state.console_state.screen_mode == 0:
            return get_text_memory(addr)
        addr -= video_segment[state.console_state.screen_mode]*0x10
        if state.console_state.screen_mode == 1:
            # interlaced scan lines of 80bytes, 4pixels per byte
            x, y = ((addr%0x2000)%80)*4, (addr>=0x2000) + 2*((addr%0x2000)//80)
            if y < state.console_state.size[1]:
                return ( (backend.video.get_pixel(x  , y)<<6) + (backend.video.get_pixel(x+1, y)<<4) 
                        + (backend.video.get_pixel(x+2, y)<<2) + (backend.video.get_pixel(x+3, y)))
        elif state.console_state.screen_mode == 2:
            # interlaced scan lines of 80bytes, 8 pixes per byte
            x, y = ((addr%0x2000)%80)*8, (addr>=0x2000) + 2*((addr%0x2000)//80)
            return get_pixel_byte(0, x, y, 0)
        elif state.console_state.screen_mode == 7:
            page, addr = addr//8192, addr%8192
            x, y = (addr%40)*8, addr//40
            return get_pixel_byte(page, x, y, state.console_state.colour_plane % 4)
        elif state.console_state.screen_mode == 8:
            page, addr = addr//16384, addr%16384
            x, y = (addr%80)*8, addr//80
            return get_pixel_byte(page, x, y, state.console_state.colour_plane % 4)
        elif state.console_state.screen_mode == 9:
            page, addr = addr//32768, addr%32768
            x, y = (addr%80)*8, addr//80
            return get_pixel_byte(page, x, y, state.console_state.colour_plane % 4)
        return -1   

def set_video_memory(addr, val):
    if addr >= video_segment[state.console_state.screen_mode]*0x10:
        if state.console_state.screen_mode == 0:
            return set_text_memory(addr, val)
        addr -= video_segment[state.console_state.screen_mode]*0x10
        if state.console_state.screen_mode == 1:
            # interlaced scan lines of 80bytes, 4pixels per byte
            x, y = ((addr%0x2000)%80)*4, (addr>=0x2000) + 2*((addr%0x2000)//80)
            if y < state.console_state.size[1]:
                for shift in range(4):
                    twobit = (val>>(6-shift*2)) & 3
                    backend.video.put_pixel(x + shift, y, twobit) 
        elif state.console_state.screen_mode == 2:
            # interlaced scan lines of 80bytes, 8 pixes per byte
            x, y = ((addr%0x2000)%80)*8, (addr>=0x2000) + 2*((addr%0x2000)//80)
            set_pixel_byte(0, x, y, 1, val)
        elif state.console_state.screen_mode == 7:
            page, addr = addr//8192, addr%8192
            x, y = (addr%40)*8, addr//40
            set_pixel_byte(page, x, y, state.console_state.colour_plane_write_mask & 0xf, val)
        elif state.console_state.screen_mode == 8:
            page, addr = addr//16384, addr%16384
            x, y = (addr%80)*8, addr//80
            set_pixel_byte(page, x, y, state.console_state.colour_plane_write_mask & 0xf, val)
        elif state.console_state.screen_mode == 9:
            page, addr = addr//32768, addr%32768
            x, y = (addr%80)*8, addr//80
            set_pixel_byte(page, x, y, state.console_state.colour_plane_write_mask & 0xf, val)            

def get_video_memory_block(addr, length):
    return bytearray( [ max(0, get_video_memory(a)) for a in range(addr, addr+length) ] )
    
def set_video_memory_block(addr, some_bytes):
    for a in range(len(some_bytes)):
        set_video_memory(addr + a, some_bytes[a])
    

#################################################################################

def get_text_memory(addr):
    addr -= text_segment*0x10
    page = addr // ((state.console_state.width*state.console_state.height*2 + 96)*4)
    offset = addr % ((state.console_state.width*state.console_state.height*2 + 96)*4)
    ccol, crow = (offset%(state.console_state.width*2))//2, offset//(state.console_state.width*2)
    try:
        c = state.console_state.pages[page].row[crow].buf[ccol][addr%2]  
        return c if addr%2==1 else ord(c)
    except IndexError:
        return -1    
    
def set_text_memory(addr, val):
    addr -= text_segment*0x10
    page = addr // ((state.console_state.width*state.console_state.height*2 + 96)*4)
    offset = addr % ((state.console_state.width*state.console_state.height*2 + 96)*4)
    ccol, crow = (offset%(state.console_state.width*2))//2, offset//(state.console_state.width*2)
    try:
        c, a = state.console_state.pages[page].row[crow].buf[ccol]
        if addr%2==0:
            c = chr(val)
        else:
            a = val
        console.put_screen_char_attr(state.console_state.pages[page], crow+1, ccol+1, c, a)
    except IndexError:
        pass
    
 
