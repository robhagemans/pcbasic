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
# for clear_graphics_view
import graphics




def exec_cls(ins):
    if util.skip_white(ins) in util.end_statement:
        if graphics.graph_view_set:
            val=1
        elif console.view_set:
            val=2
        else:        
            val=0
    else:
        val = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    if util.skip_white_read_if(ins, (',',)):
        # comma is ignored, but a number after means syntax error
        util.require(ins, util.end_statement)    
    else:
        util.require(ins, util.end_statement, err=5)    
    # cls is only executed if no errors have occurred    
    if val==0:
        console.clear()  
    elif val==1 and graphics.is_graphics_mode():
        graphics.clear_graphics_view()
    elif val==2:
        console.clear_view()  
    else:
        raise error.RunError(5)                  
    
    
def exec_color(ins):
    [fore, back, bord] = expressions.parse_int_list(ins, 3, 5)          
    if bord == None:
        bord = 0 
    mode = console.get_mode()
    if mode == 2: 
        # screen 2: illegal fn call
        raise error.RunError(5)
    elif mode == 1:
        # screen 1
        # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
        # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
        fore_old, dummy = console.get_attr()
        back_old = console.get_palette_entry(0)
        pal, back = back, fore
        if pal <0 or back<0 or bord<0 or pal >255 or back>255 or bord>255:
            raise error.RunError(5)
        if back == None: 
            back=back_old
        if pal%2 == 1:
            console.set_palette([0,3,5,7])
        elif pal%2 == 0:
            console.set_palette([0,2,4,6])
        console.set_palette_entry(0,back&0xf)
    elif mode == 0:
        # screen 0
        fore_old, back_old = console.get_attr()
        if fore==None:
            fore=fore_old
        if back==None: 
            back=back_old
        if not (console.colours_ok(fore) and back>=0 and back<16 and bord>=0 and bord<16):
            raise error.RunError(5)
        console.set_attr(fore, back)
        # border not implemented
    elif mode == 9:
        # screen 9
        fore_old, dummy = console.get_attr()
        back_old = console.get_palette_entry(0)
        if fore==None:
            fore=fore_old
        if back==None: 
            back=back_old
        if not (console.colours_ok(fore) and back>=0 and back<console.num_palette):
            raise error.RunError(5)
        # in graphics mode, bg colour is always 0 and controlled by palette
        console.set_attr(fore, 0)
        console.set_palette_entry(0, back)
    else:
        # screen 7,8
        fore_old, dummy = console.get_attr()
        back_old = console.get_palette_entry(0)
        if fore==None:
            fore=fore_old
        if back==None: 
            back=back_old
        if fore==0 or not console.colours_ok(fore) or not console.colours_ok(back):
            raise error.RunError(5)
        # in graphics mode, bg colour is always 0 and controlled by palette
        console.set_attr(fore, 0)
        # in screen 7 and 8, only low intensity palette is used.
        console.set_palette_entry(0, back%8)    
    
    
def exec_palette(ins):
    # can't set blinking colours separately
    num_palette_entries = console.num_colours
    if num_palette_entries==32:
        num_palette_entries=16
    d = util.skip_white(ins)
    if d in util.end_statement:
        # reset palette
        console.set_palette()
    elif d=='\xD7': # USING
        ins.read(1)
        array_name = util.get_var_name(ins)
        start_index = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        new_palette=[]
        for i in range(num_palette_entries):
            val = vartypes.pass_int_unpack(var.get_array(array_name, [start_index+i]))
            if val==-1:
                val = console.get_palette_entry(i)
            if val<-1 or val>=console.num_palette:
                raise error.RunError(5) 
            new_palette.append(val)
        console.set_palette(new_palette)
    else:
        pair = expressions.parse_int_list(ins, 2, err=5)
        if pair[0]<0 or pair[0]>=num_palette_entries or pair[1]<-1 or pair[1]>=console.num_palette:
            raise error.RunError(5)
        if pair[1]>-1:
            console.set_palette_entry(pair[0], pair[1])
    util.require(ins, util.end_statement)    
        

        

def exec_key(ins):
    d = util.skip_white(ins)
    if d == '\x95': # ON
        if not console.keys_visible:
           console.show_keys()
    elif d == '\xdd': # OFF
        if console.keys_visible:
           console.hide_keys()   
    elif d== '\x93': # LIST
        for i in range(10):
            text = list(events.key_replace[i])
            for j in range(len(text)):
                if text[j]=='\x0d':   #  CR
                    text[j] = '\x1b'  # arrow left
            console.write('F'+str(i+1)+' '+''.join(text)+util.endl)    
    elif d=='(':
        # key (n)
        num = vartypes.pass_int_unpack(expressions.parse_bracket(ins))
        if num<0 or num>255:
            raise error.RunError(5)
        d = util.skip_white_read(ins)
        # others are ignored
        if num >=1 and num <= 20:
            if d=='\x95': # ON
                events.key_enabled[num-1] = True
                events.key_stopped[num-1] = False
            elif d=='\xDD': # OFF
                events.key_enabled[num-1] = False
            elif d=='\x90': # STOP
                events.key_stopped[num-1] = True
            else:
                raise error.RunError(2)
    else:
        # key n, "TEXT"    
        keynum = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        if keynum<1 or keynum>255:
            raise error.RunError(5)
        util.require_read(ins, (',',), err=5)
        text = vartypes.pass_string_unpack(expressions.parse_expression(ins))
        # only length-2 expressions can be assigned to KEYs over 10
        # (in which case it's a key scancode definition, which is not implemented)
        if keynum <=10:
            events.key_replace[keynum] = text
        else:
            if len(text)!=2:
               raise error.RunError(5)
            # can't redefine scancodes for keys 1-14
            if keynum >=15 and keynum <= 20:    
                events.key_numbers[keynum-1] = text
    # rest of statement is ignored
    util.skip_to(ins, util.end_statement)


def exec_locate(ins):
    [row, col, cursor, start, stop] = expressions.parse_int_list(ins, 5, 2)          
    [crow, ccol] = [console.get_row(), console.get_col()]            
    if row==None:
        row = crow
    if col==None:
        col = ccol
    check_view(row, col)
    console.set_pos(row, col, scroll_ok=False)    
    if cursor!=None:
        console.show_cursor(cursor)
    # FIXME: cursor shape not implemented


def exec_write(ins, screen=None):
    screen = expressions.parse_file_number(ins)
    if screen==None:
        screen=console
    expr = expressions.parse_expression(ins, allow_empty=True)
    if expr!=('',''):
        while True:
            if expr[0]=='$':
                screen.write('"'+vartypes.unpack_string(expr)+'"')
            else:                
                screen.write(vartypes.unpack_string(vartypes.value_to_str_keep(expr, screen=True, write=True)))
            if util.skip_white(ins) ==',':
                ins.read(1)
                screen.write(',')
            else:
                break
            expr = expressions.parse_expression(ins, allow_empty=True)
            if expr==('',''):
                raise error.RunError(2)        
    util.require(ins, util.end_statement)        
    screen.write(util.endl)

        
        
def exec_print(ins, screen=None):
    if screen==None:
        screen = expressions.parse_file_number(ins)
        if screen==None:
            screen=console
    zone_width = 14 #15
    number_zones = int(screen.width/zone_width)
    output = ''
    newline = True
    if util.skip_white_read_if(ins, '\xD7'): # USING
       exec_print_using(ins, screen)
       return
    while True:
        d = util.skip_white(ins)
        if d in util.end_statement:
            screen.write(output)
            if newline:
                 screen.write(util.endl)
            output = ''
            break 
        elif d==',':
            newline = False
            ins.read(1)
            screen.write(output)
            col = screen.get_col()
            next_zone = int((col-1)/zone_width)+1
            if next_zone >= number_zones:
                output = util.endl
            else:            
                output = ' '*(1+zone_width*next_zone-col)
            screen.write(output)
            output=''
        elif d==';':
            newline = False
            ins.read(1)
            screen.write(output)
            output = ''
        elif d=='\xD2': #SPC(
            newline=False
            ins.read(1)
            screen.write(output)
            output = ''
            numspaces = vartypes.pass_int_unpack(expressions.parse_expression(ins), 0xffff)
            numspaces %= screen.width
            util.require_read(ins, (')',))
            screen.write(' '*numspaces)
            output=''
        elif d=='\xCE': #TAB(
            newline=False
            ins.read(1)
            screen.write(output)
            output = ''
            pos = vartypes.pass_int_unpack(expressions.parse_expression(ins), 0xffff)
            pos %= screen.width
            util.require_read(ins, (')',))
            col = screen.get_col()
            if pos < col:
                screen.write(output+util.endl+' '*(pos-1))
            else:
                screen.write(output+' '*(pos-col))
            output=''    
        else:
            newline = True
            expr = expressions.parse_expression(ins)
            word = vartypes.unpack_string(vartypes.value_to_str_keep(expr, screen=True))
            # numbers always followed by a space
            if expr[0] in ('%', '!', '#'):
                word += ' '
            if screen.get_col() + len(word) -1 > screen.width and screen.get_col() != 1:
                # prevent breaking up of numbers through newline
                output += util.endl
            output += str(word)
            
            
def get_next_expression(ins): 
    util.skip_white(ins)
    expr = expressions.parse_expression(ins)
    # no semicolon: nothing more to read afterwards
    if not util.skip_white_read_if(ins, ';'):
        return False, False, expr
    # more to come?
    if util.skip_white(ins) in util.end_statement:
        return False, True, expr
    #return more_data, semicolon, expr
    return True, True, expr


def exec_print_using(ins, screen):
    util.skip_white(ins)
    format_expr = vartypes.pass_string_unpack(expressions.parse_expression(ins))
    if format_expr == '':
        raise error.RunError(5)
    fors = StringIO(format_expr)
    util.require_read(ins, (';',))
    semicolon = False    
    more_data = False
    format_chars = False    
    while True:
        c = fors.read(1)
        if c=='':
            if not format_chars:
                # there were no format chars in the string, illegal fn call
                raise error.RunError(5) 
            # loop the format string if more variables to come
            if more_data:
                fors.seek(0)
            else:
                # no more data, no more format chars -> done
                break
        elif c=='_':
            c = fors.read(1)
            if c != '':
                screen.write(c)
            else:
                screen.write('_')
        elif c=='!':
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins) 
            screen.write(vartypes.pass_string_unpack(expr)[0])
        elif c=='&':
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins) 
            screen.write(vartypes.pass_string_unpack(expr))
        elif c=='\\':
            pos=0
            word = c
            is_token = True
            while True: 
                c = fors.read(1)
                pos+=1
                word += c
                if c=='\\':
                    break
                elif c=='':
                    is_token=False
                    break 
                elif c !=' ':
                    is_token = False
            if is_token:
                format_chars = True
                more_data, semicolon, expr = get_next_expression(ins) 
                eword = vartypes.pass_string_unpack(expr)
                if len(eword)>len(word):
                    screen.write( eword[:len(word)] )
                else:
                    screen.write( eword ) 
                    screen.write( ' '*(len(word)-len(eword)) )
            else:
                screen.write( word )
        elif (c=='#' 
                or (c in ('$', '*') and util.peek(fors)==c) 
                or (c=='+' and  util.peek(fors) == '#' or util.peek(fors,2) in ('##', '**')) 
                ):    
            # numeric token
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins) 
            # feed back c, we need it
            fors.seek(-1,1)
            varstring = format_number(vartypes.pass_float_keep(expr), fors)     
            screen.write( varstring )
        else:
            screen.write( c )
    if not semicolon:
        screen.write(util.endl)
    util.require(ins, util.end_statement)
       


def exec_lprint(ins):
    exec_print(ins, deviceio.lpt1)
    deviceio.lpt1.flush()
    

# does nothing in GWBASIC except give some errors. See e.g. http://shadowsshot.ho.ua/docs001.htm#LCOPY    
def exec_lcopy(ins):    
    value = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    if value<0 or value>255:
        error.RunError(5)
    util.require(ins, util.end_statement)
       
                             
def exec_view_print(ins):
    d = util.skip_white(ins)
    if d in util.end_statement:
        console.set_view()
    else:  
        start = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require_read(ins, ('\xCC',)) # TO
        stop = vartypes.pass_int_unpack(expressions.parse_expression(ins))
        util.require(ins, util.end_statement)
        console.set_view(start, stop)


def check_view(row, col):
    if row == console.height and console.keys_visible:
        raise error.RunError(5)
    elif console.view_set:
        if row > console.scroll_height or col > console.width or row<console.view_start or col<1:
            raise error.RunError(5)
    else:
        if row > console.height or col > console.width or row<1 or col<1:
            raise error.RunError(5)
        if row== console.height:
            # temporarily allow writing on last row
            console.last_row_on()       

    
def exec_width(ins):
    device = ''
    d = util.skip_white(ins)
    if d=='#':
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
        if device=='SCRN:':
            dev = console
        else:
            dev = deviceio.output_devices[device]
        util.require_read(ins, (',',))
    else:
        dev = console
    # we can do calculations, but they must be bracketed...
    w = vartypes.pass_int_unpack(expressions.parse_expr_unit(ins))
    # get the appropriate errors out there for WIDTH [40|80] [,[,]]
    if dev==console and device=='':
        # two commas are accepted
        util.skip_white_read_if(ins, ',')
        if not util.skip_white_read_if(ins, ','):
            # one comma, then stuff - illegal function call
            util.require(ins, util.end_statement, err=5)
    # anything after that is a syntax error      
    util.require(ins, util.end_statement)        
    if dev == console:        
        # FIXME: WIDTH should do mode changes if not in text mode
        # raise an error if the width value doesn't make sense
        if w not in (40, 80):
            raise error.RunError(5)
        if w != console.width:    
            dev.set_width(w)    
    else:
        dev.set_width(w)    
    
        
#############################################################        
                
def format_number(value, fors):
    if value[0] =='#':
        type_sign, exp_sign = '#', 'D'
    else:
        type_sign, exp_sign = '!', 'E'
    c = fors.read(1)
    width = 0
    plus_sign = (c=='+')
    if plus_sign:
        c = fors.read(1)
        width+=1
    digits_before = 0
    dollar_sign = (c=='$')
    if c =='$':
        fors.read(1)
        c = fors.read(1)        
        digits_before +=2
    asterisk = (c=='*')    
    if c=='*':    
        fors.read(1)
        c = fors.read(1)
        digits_before += 2        
        if c=='$':
            dollar_sign=True
            c= fors.read(1)
            digits_before += 1
    if asterisk:
        fill_char='*'
    else:
        fill_char=' '
    while c=='#':
        digits_before+=1
        c = fors.read(1)
        if c==',':
            digits_before+=1
            c = fors.read(1)            
    decimals=0    
    dots=0
    if c=='.':
        dots+=1
        c=fors.read(1)
        while c=='#':
            decimals += 1
            c = fors.read(1)
    width += digits_before + decimals + dots
    exp_form=False
    if c=='^':
        if util.peek(fors,3)=='^^^':
            fors.read(3)
            c=fors.read(1)
            exp_form=True
            width+=4
    sign_after = c in ('-','+') and not plus_sign
    if sign_after:
        if c=='+':
            plus_sign=True
        c = fors.read(1)
        width+=1
    if digits_before+decimals > 24:
        # illegal function call
        raise error.RunError(5)

    ###########                
    ###########                

    # format to string
    expr = fp.unpack(vartypes.number_abs(value))
    if exp_form:
        if not plus_sign and not sign_after and digits_before > 0:
            # reserve space for sign
            digits_before -=1
        work_digits = digits_before + decimals
        if work_digits > expr.digits:
            # decimal precision of the type
            work_digits = expr.digits
        if work_digits>0:
            # scientific representation
            lim_bot = fp.just_under(fp.pow_int(expr.ten, work_digits-1))
        else:
            # special case when work_digits == 0, see also below
            # setting to 0.1 results in incorrect rounding (why?)
            lim_bot = expr.one
        lim_top = lim_bot.copy()
        lim_top.imul10()
        num, exp10 = expr.bring_to_range(lim_bot, lim_top)
        digitstr = fp.get_digits(num, work_digits)
        if len(digitstr) < digits_before+decimals:
            digitstr+='0'*(digits_before+decimals-len(digitstr))
        # this is just to reproduce GW results for no digits: 
        # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
        if work_digits==0:
            exp10+=1
        exp10 += digits_before + decimals - 1  
        fp_repr = fp.scientific_notation(digitstr, exp10, exp_sign, digits_to_dot=digits_before, force_dot=(dots>0))
    
    else:
        # fixed-point representation
        factor = fp.pow_int(expr.ten, decimals) 
        unrounded = fp.mul(expr, factor)
        num = unrounded.copy().iround()
        # find exponent 
        exp10 = 1
        pow10 = fp.pow_int(expr.ten, exp10) # pow10 = 10L**exp10
        while num.gt(pow10) or num.equals(pow10): # while pow10 <= num:
            pow10.imul10() #pow10*=10
            exp10 += 1
        work_digits = exp10 + 1
        diff = 0
        if exp10 > expr.digits:
            diff = exp10 - expr.digits
            factor = fp.pow_int(expr.ten, diff) # pow10 = 10L**exp10
            num = fp.div(unrounded, factor).iround() #expr.from_int(10L**diff))
            work_digits -= diff
        num = num.trunc_to_int()   
        # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
        digitstr = fp.get_digits(num, work_digits-1, remove_trailing=False)
        # fill up with zeros
        digitstr+='0'*diff
        fp_repr = fp.decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', (dots>0))
    
    ##########
    ##########
    
    valstr = ''
    if dollar_sign:
        valstr+='$'
    valstr += fp_repr    
    sign = vartypes.unpack_int(vartypes.number_sgn(value))
    if sign_after:
        sign_str = ' '
    else:
        sign_str = ''    
    if sign < 0:
        sign_str = '-'
    elif plus_sign:
        sign_str = '+'    
    if sign_after:
        valstr += sign_str
    else:
        valstr = sign_str + valstr
    if len(valstr)>width:
        valstr='%'+valstr
    else:
        valstr=fill_char*(width-len(valstr)) + valstr
    return valstr
    


def exec_screen(ins):
    params = expressions.parse_int_list(ins, 4)
    util.require(ins, util.end_statement)        
    mode = params[0]
    mode_info = console.mode_info(mode) 
    # backend does not support mode
    if mode_info == None:
        raise error.RunError(5)
    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, illegal fn call.
    if params[2] == None:
        params[2] = console.apagenum
    if params[3] == None:
        params[3] = console.vpagenum    
    if params[2] >= mode_info[5] or params[3] >= mode_info[5]:
       raise error.RunError(5)
    console.set_palette()
    if mode != console.screen_mode:
        console.set_view()
        console.set_mode(mode)
    # set active page & visible page, counting from 0. if higher than max pages, illegal fn call.            
    if not console.set_apage(console.apagenum):
       raise error.RunError(5)
    if not console.set_vpage(console.vpagenum):
       raise error.RunError(5)
    # in SCREEN 0, the colorswitch parameter doesn't actually switch colors on and off
    # but if it's different from the existing one, the screen is cleared.
    if params[1] != None and (params[1]!=0) != console.colorswitch:
        console.set_colorswitch( params[1]!=0 )
        # clear all screen pages
        console.clear_all()
        console.set_view()
                
    
def exec_pcopy(ins):
    src = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require_read(ins, (',',))
    dst = vartypes.pass_int_unpack(expressions.parse_expression(ins))
    util.require(ins, util.end_statement)
    if not console.copy_page(src,dst):
        raise error.RunError(5)
    
        
           
                
