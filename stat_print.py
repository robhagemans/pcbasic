#
# PC-BASIC 3.23 - stat_print.py
#
# Console statements
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

from cStringIO import StringIO

import error
import events
import fp
import vartypes
import var
import util
import expressions
import deviceio
import console
import graphics

zone_width = 14
        

def exec_cls(ins):
    if util.skip_white(ins) in util.end_statement:
        val = 1 if graphics.graph_view_set else (2 if console.view_set else 0)
    else:
        val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, 2, val)
    if util.skip_white_read_if(ins, (',',)):
        # comma is ignored, but a number after means syntax error
        util.require(ins, util.end_statement)    
    else:
        util.require(ins, util.end_statement, err=5)    
    # cls is only executed if no errors have occurred    
    if val == 0:
        console.clear()  
        if graphics.is_graphics_mode():
            graphics.reset_graphics()
    elif val == 1 and graphics.is_graphics_mode():
        graphics.clear_graphics_view()
        graphics.reset_graphics()
    elif val == 2:
        console.clear_view()  

def exec_color(ins):
    fore, back, bord = expressions.parse_int_list(ins, 3, 5)          
    mode = console.screen_mode
    if mode == 1:
        return exec_color_mode_1(fore, back, bord)
    elif mode == 2: 
        # screen 2: illegal fn call
        raise error.RunError(5)
    fore_old, back_old = (console.attr>>7)*0x10 + (console.attr&0xf), (console.attr>>4) & 0x7
    bord = 0 if bord == None else bord
    util.range_check(0, 255, bord)
    fore = fore_old if fore == None else fore
    # graphics mode bg is always 0; sets palette instead
    back = back_old if mode == 0 and back == None else (console.get_palette_entry(0) if back == None else back)
    if mode == 0:
        util.range_check(0, console.num_colours-1, fore)
        util.range_check(0, 15, back, bord)
        console.attr = ((0x8 if (fore > 0xf) else 0x0) + (back & 0x7))*0x10 + (fore & 0xf) 
        # border not implemented
    elif mode in (7, 8):
        util.range_check(1, console.num_colours-1, fore)
        util.range_check(0, console.num_colours-1, back)
        console.attr = fore
        # in screen 7 and 8, only low intensity palette is used.
        console.set_palette_entry(0, back % 8)    
    elif mode == 9:
        util.range_check(0, console.num_colours-1, fore)
        util.range_check(0, console.num_palette-1, back)
        console.attr = fore
        console.set_palette_entry(0, back)
    
def exec_color_mode_1(back, pal, override):
    back = console.get_palette_entry(0) if back == None else back
    if override:
        # uses last entry as palette if given
        pal = override
    util.range_check(0, 255, back)
    if pal:
        util.range_check(0, 255, pal)
        if pal % 2 == 1:
            # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
            console.set_palette([back & 0xf, 3, 5, 7])
        else:
            # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
            console.set_palette([back & 0xf, 2, 4, 6])
    
def exec_palette(ins):
    d = util.skip_white(ins)
    if d in util.end_statement:
        # reset palette
        console.set_palette()
    elif d == '\xD7': # USING
        ins.read(1)
        exec_palette_using(ins)
    else:
        # can't set blinking colours separately
        num_palette_entries = console.num_colours if console.num_colours != 32 else 16
        pair = expressions.parse_int_list(ins, 2, err=5)
        util.range_check(0, num_palette_entries-1, pair[0])
        util.range_check(-1, console.num_palette-1, pair[1])
        if pair[1] > -1:
            console.set_palette_entry(pair[0], pair[1])
        util.require(ins, util.end_statement)    

def exec_palette_using(ins):
    num_palette_entries = console.num_colours if console.num_colours != 32 else 16
    array_name, start_indices = expressions.get_var_or_array_name(ins)
    try:     
        dimensions, lst, _ = var.arrays[array_name]    
    except KeyError:
        raise error.RunError(5)    
    if array_name[-1] != '%':
        raise error.RunError(13)
    start = var.index_array(start_indices, dimensions)
    if var.array_len(dimensions) - start  < num_palette_entries:
        raise error.RunError(5)
    new_palette = []
    for i in range(num_palette_entries):
        val = vartypes.pass_int_unpack(('%', lst[(start+i)*2:(start+i+1)*2]))
        util.range_check(-1, console.num_palette-1, val)
        new_palette.append(val if val > -1 else console.get_palette_entry(i))
    console.set_palette(new_palette)
    util.require(ins, util.end_statement) 

def exec_key(ins):
    d = util.skip_white_read(ins)
    if d == '\x95': # ON
        if not console.keys_visible:
           console.show_keys()
    elif d == '\xdd': # OFF
        if console.keys_visible:
           console.hide_keys()   
    elif d == '\x93': # LIST
        console.list_keys()
    elif d == '(':
        # key (n)
        ins.seek(-1, 1)
        exec_key_events(ins)
    else:
        # key n, "TEXT"    
        ins.seek(-len(d), 1)
        exec_key_define(ins)
    util.require(ins, util.end_statement)        

def exec_key_events(ins):        
    num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
    util.range_check(0, 255, num)
    d = util.skip_white(ins)
    # others are ignored
    if num >= 1 and num <= 20:
        if events.key_handlers[num-1].command(d):
            ins.read(1)
        else:    
            raise error.RunError(2)

def exec_key_define(ins):        
    keynum = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(1, 255, keynum)
    util.require_read(ins, (',',), err=5)
    text = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    # only length-2 expressions can be assigned to KEYs over 10
    # (in which case it's a key scancode definition, which is not implemented)
    if keynum <= 10:
        console.key_replace[keynum-1] = str(text)
        console.show_keys()
    else:
        if len(text) != 2:
           raise error.RunError(5)
        # can't redefine scancodes for keys 1-14
        if keynum >= 15 and keynum <= 20:    
            events.event_keys[keynum-1] = str(text)
    
def exec_locate(ins):
    row, col, cursor, start, stop, dummy = expressions.parse_int_list(ins, 6, 2, allow_last_empty=True)          
    if dummy != None:
        # can end on a 5th comma but no stuff allowed after it
        raise error.RunError(2)
    row = console.row if row == None else row
    col = console.col if col == None else col
    if row == console.height and console.keys_visible:
        raise error.RunError(5)
    elif console.view_set:
        util.range_check(console.view_start, console.scroll_height, row)
    else:
        util.range_check(1, console.height, row)
    util.range_check(1, console.width, col)
    if row == console.height:
        # temporarily allow writing on last row
        console.bottom_row_allowed = True       
    console.set_pos(row, col, scroll_ok=False) 
    if cursor != None:
        util.range_check(0, 1, cursor)   
        console.show_cursor(cursor != 0)
    if stop == None:
        stop = start
    if start != None:    
        util.range_check(0, 31, start, stop)
        console.set_cursor_shape(start, stop)

def exec_write(ins, screen=None):
    screen = expressions.parse_file_number(ins)
    screen = console if screen == None else screen
    expr = expressions.parse_expression(ins, allow_empty=True)
    if expr:
        while True:
            if expr[0] == '$':
                screen.write('"' + vartypes.unpack_string(expr) + '"')
            else:                
                screen.write(vartypes.unpack_string(vartypes.value_to_str_keep(expr, screen=True, write=True)))
            if util.skip_white_read_if(ins, (',',)):
                screen.write(',')
            else:
                break
            expr = expressions.parse_expression(ins, empty_err=2)
    util.require(ins, util.end_statement)        
    screen.write(util.endl)

def exec_print(ins, screen=None):
    if screen == None:
        screen = expressions.parse_file_number(ins)
        screen = console if screen == None else screen
    if util.skip_white_read_if(ins, ('\xD7',)): # USING
       return exec_print_using(ins, screen)
    number_zones = max(1, int(screen.width/zone_width))
    newline = True
    while True:
        d = util.skip_white(ins)
        if d in util.end_statement:
            break 
        elif d in (',', ';', '\xD2', '\xCE'):    
            ins.read(1)
            newline = False
            if d == ',':
                next_zone = int((screen.col-1)/zone_width)+1
                if next_zone >= number_zones and screen.width >= 14:
                    screen.write(util.endl)
                else:            
                    screen.write(' '*(1+zone_width*next_zone-screen.col))
            elif d == '\xD2': #SPC(
                numspaces = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2), 0xffff)) % screen.width
                util.require_read(ins, (')',))
                screen.write(' ' * numspaces)
            elif d == '\xCE': #TAB(
                pos = max(0, vartypes.pass_int_unpack(expressions.parse_expression(ins, empty_err=2), 0xffff)) % screen.width
                util.require_read(ins, (')',))
                if pos < screen.col:
                    screen.write(util.endl + ' '*(pos-1))
                else:
                    screen.write(' '*(pos-screen.col))
        else:
            newline = True
            expr = expressions.parse_expression(ins)
            word = vartypes.unpack_string(vartypes.value_to_str_keep(expr, screen=True))
            # numbers always followed by a space
            if expr[0] in ('%', '!', '#'):
                word += ' '
            if screen.col + len(word) - 1 > screen.width and screen.col != 1:
                screen.write(util.endl)
            screen.write(str(word))
    if newline:
         screen.write(util.endl)
            
def exec_print_using(ins, screen):
    format_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if format_expr == '':
        raise error.RunError(5)
    util.require_read(ins, (';',))
    fors = StringIO(format_expr)
    semicolon, format_chars = False, False
    while True:
        data_ends = util.skip_white(ins) in util.end_statement
        c = util.peek(fors)
        if c == '':
            if not format_chars:
                # there were no format chars in the string, illegal fn call (avoids infinite loop)
                raise error.RunError(5) 
            if data_ends:
                break
            # loop the format string if more variables to come
            fors.seek(0)
        elif c == '_':
            # escape char; write next char in fors or _ if this is the last char
            screen.write(fors.read(2)[-1])
        else:
            string_field = get_string_tokens(fors)
            if string_field:
                if not data_ends:
                    s = str(vartypes.pass_string_unpack(expressions.parse_expression(ins)))
                    if string_field == '&':
                        screen.write(s)    
                    else:
                        screen.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
            else:
                number_field, digits_before, decimals = get_number_tokens(fors)
                if number_field:
                    if not data_ends:
                        num = vartypes.pass_float_keep(expressions.parse_expression(ins))
                        screen.write(fp.format_number(num, number_field, digits_before, decimals))
                else:
                    screen.write(fors.read(1))       
            if string_field or number_field:
                format_chars = True
                semicolon = util.skip_white_read_if(ins, (';',))    
    if not semicolon:
        screen.write(util.endl)
    util.require(ins, util.end_statement)

########################################

def get_string_tokens(fors):
    word = ''
    c = util.peek(fors)
    if c in ('!', '&'):
        format_chars = True
        word += fors.read(1)
    elif c == '\\':
        word += fors.read(1)
        # count the width of the \ \ token; only spaces allowed and closing \ is necessary
        while True: 
            c = fors.read(1)
            word += c
            if c == '\\':
                format_chars = True
                s = vartypes.pass_string_unpack(expressions.parse_expression(ins))
                semicolon = util.skip_white_read_if(ins, (';',))    
                break
            elif c != ' ': # can be empty as well
                fors.seek(-len(word), 1)
                return ''
    return word

def get_number_tokens(fors):
    word, digits_before, decimals = '', 0, 0
    # + comes first
    leading_plus = (util.peek(fors) == '+')
    if leading_plus:
        word += fors.read(1)
    # $ and * combinations
    c = util.peek(fors)
    if c in ('$', '*'):
        word += fors.read(2)
        if word[-1] != c:
            fors.seek(-len(word), 1)
            return '', 0, 0
        if c == '*':
            digits_before += 2
            if util.peek(fors) == '$':
                word += fors.read(1)                
        else:
            digits_before += 1        
    # number field
    c = util.peek(fors)
    dot = (c == '.')
    if dot:
        word += fors.read(1)
    if c in ('.', '#'):
        while True:
            c = util.peek(fors)
            if not dot and c == '.':
                word += fors.read(1)
                dot = True
            elif c == '#' or (not dot and c == ','):
                word += fors.read(1)
                if dot:
                    decimals += 1
                else:
                    digits_before += 1    
            else:
                break
    if digits_before + decimals == 0:
        fors.seek(-len(word), 1)
        return '', 0, 0    
    # post characters        
    if util.peek(fors, 4) == '^^^^':
        word += fors.read(4)
    if not leading_plus and util.peek(fors) in ('-', '+'):
        word += fors.read(1)
    return word, digits_before, decimals    
                
########################################

def exec_lprint(ins):
    exec_print(ins, deviceio.lpt1)
    deviceio.lpt1.flush()
                             
def exec_view_print(ins):
    if util.skip_white(ins) in util.end_statement:
        console.unset_view()
    else:  
        start = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, ('\xCC',)) # TO
        stop = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        util.range_check(1, 24, start, stop)
        console.set_view(start, stop)
    
def exec_width(ins):
    device = ''
    d = util.skip_white(ins)
    if d == '#':
        dev = expressions.parse_file_number(ins)
    elif d in ('"', ','):
        device = vartypes.pass_string_unpack(expressions.parse_expression(ins)).upper()
        if device not in deviceio.output_devices:
            # bad file name
            raise error.RunError(64)
        # WIDTH "SCRN:, 40 works directy on console 
        # whereas OPEN "SCRN:" FOR OUTPUT AS 1: WIDTH #1,23 works on the wrapper text file
        # WIDTH "LPT1:" works on lpt1 for the next time it's opened
        # for other devices, the model of LPT1 is followed - not sure what GW-BASIC does there.
        if device == 'SCRN:':
            dev = console
        else:
            dev = deviceio.output_devices[device]
        util.require_read(ins, (',',))
    else:
        dev = console
    # we can do calculations, but they must be bracketed...
    w = vartypes.pass_int_unpack(expressions.parse_expr_unit(ins))
    # get the appropriate errors out there for WIDTH [40|80] [,[,]]
    if dev == console and device == '':
        # two commas are accepted
        util.skip_white_read_if(ins, (',',))
        if not util.skip_white_read_if(ins, (',',)):
            # one comma, then stuff - illegal function call
            util.require(ins, util.end_statement, err=5)
    # anything after that is a syntax error      
    util.require(ins, util.end_statement)        
    if dev == console:        
        # TODO: WIDTH should do mode changes if not in text mode
        # raise an error if the width value doesn't make sense
        if w not in (40, 80):
            raise error.RunError(5)
        if w != console.width:    
            dev.set_width(w)    
    else:
        dev.set_width(w)    
    
def exec_screen(ins):
    # in GW, screen 0,0,0,0,0,0 raises error after changing the palette... this raises error before:
    mode, colorswitch, apagenum, vpagenum = expressions.parse_int_list(ins, 4)
    # if any parameter not in [0,255], error 5 without doing anything 
    util.range_check(0, 255, mode, colorswitch, apagenum, vpagenum)
    # if the parameters are outside narrow ranges (e.g. not implemented screen mode, pagenum beyond max)
    # then the error is only raised after changing the palette.
    util.require(ins, util.end_statement)        
    console.set_mode(mode, colorswitch, apagenum, vpagenum)
    
def exec_pcopy(ins):
    src = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.range_check(0, console.num_pages-1, src)
    util.require_read(ins, (',',))
    dst = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    util.range_check(0, console.num_pages-1, dst)
    console.copy_page(src, dst)
        
