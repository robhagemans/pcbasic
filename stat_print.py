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


import sys
import StringIO

import glob
import error
import events
import fp
import vartypes
import var
import rnd
import util

import expressions
import tokenise
import program
import fileio
import deviceio
import console
# for clear_graphics_view
import graphics

# KEY ON?
keys_visible = False




def exec_cls(ins):
    global keys_visible
    
    if util.skip_white(ins) in util.end_statement:
        if graphics.graph_view_set:
            val=1
        elif console.view_set:
            val=2
        else:        
            val=0
    else:
        val = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]

    if val==0:
        console.clear()  
        if keys_visible:
            show_keys()
    elif val==1:
        if graphics.is_graphics_mode():
            graphics.clear_graphics_view()
        else:
            console.clear_view()                
    elif val==2:
        console.clear_view()                
      
    util.require(ins, util.end_statement)    
    
    
def exec_color(ins):
    [fore, back, bord] = expressions.parse_int_list(ins, 3, 5)          
    
    if bord==None:
        bord =0 
            
    if console.get_mode()==2: 
        # screen 2: illegal fn call
        raise error.RunError(5)
    elif console.get_mode()==1:
        # screen 1
        # cga palette 1: 0,3,5,7 (Black, Ugh, Yuck, Bleah), hi: 0, 11,13,15 
        # cga palette 0: 0,2,4,6    hi 0, 10, 12, 14
    
    
        fore_old, dummy = console.get_attr()
        back_old = console.get_palette_entry(0)
        
        pal, back = back, fore

        if pal <0 or back<0 or bord<0 or pal >255 or back>255 or bord>255:
            raise error.RunError(5)

        
        if back==None: 
            back=back_old
        if pal%2==1:
            console.set_palette([0,3,5,7])
        elif pal%2==0:
            console.set_palette([0,2,4,6])
        
        console.set_palette_entry(0,back&0xf)
    elif not graphics.is_graphics_mode():
        #screen 0
        
        fore_old, back_old = console.get_attr()
        
        if fore==None:
            fore=fore_old
        if back==None: 
            back=back_old
        
        
        if not (console.colours_ok(fore) and console.colours_ok(back) and console.colours_ok(bord)):
            raise error.RunError(5)
       
        
        console.set_attr(fore, back)
        # border not implemented
    else:
    
        fore_old, dummy = console.get_attr()
        back_old = console.get_palette_entry(0)
        
        if fore==None:
            fore=fore_old
        if back==None: 
            back=back_old
        
        #if fore >console.num_colours or fore<=0 or back<0 or back>console.num_colours or bord<0 or bord>255:
        if fore==0 or not console.colours_ok(fore) or not console.colours_ok(back) or not console.colours_ok(fore) :
            raise error.RunError(5)

        # screen 7-10:
        # in graphics mode, bg colour is always 0 and controlled by palette
        console.set_attr(fore, 0)
        console.set_palette_entry(0,back)
    
    
def exec_palette(ins):
    d = util.skip_white(ins)
    if d in util.end_statement:
        # reset palette
        console.set_palette()
    elif d=='\xD7': # USING
        ins.read(1)
        array_name = var.get_var_name(ins)
        start_index = vartypes.pass_int_keep(expressions.parse_bracket(ins))[1]
        new_palette=[]
        for i in range(console.num_colours):
            val = vartypes.pass_int_keep(var.get_array(array_name, [start_index+i]))[1]
            if val==-1:
                val = console.get_palette_entry(i)
            if val<-1 or val>63:
                raise error.RunError(5) 
            new_palette.append(val)
        console.set_palette(new_palette)
        
    else:
        pair = expressions.parse_int_list(ins, 2, err=5)
        
        if pair[0]<0 or pair[0]>console.num_palette or pair[1]<-1 or pair[1]>console.num_palette:
            raise error.RunError(5)
        if pair[1]>-1:
            console.set_palette_entry(pair[0], pair[1])
    
    
    util.require(ins, util.end_statement)    
        
        
def show_keys():
    global keys_visible
    
    keys_visible = True
    pos = console.get_pos()
    attr = console.get_attr()
    
    save_curs = console.show_cursor(False)
    
    #console.bottom_line(True)
    for i in range(console.width/8):
        text = list(events.key_replace[i][:6])
        for j in range(len(text)):
            if text[j]=='\x0d':   #  CR
                text[j] = '\x1b'  # arrow left
    
        # allow pos=25 without scroll, this is reset as soon as row changes again.
        console.last_row_on()
        console.set_pos(25,1+i*8)
        console.set_attr(*attr)
        if i==9:
            console.write('0')
        else:
            console.write(str(i+1))
            
        if not graphics.is_graphics_mode():
            if attr[1]==0:    
                console.set_attr(0,7)
            else:
                console.set_attr(7,0)
        	
        console.write(''.join(text))
        console.set_attr(*attr)
        console.write(' '*(6-len(text)))
        console.write(' ')
    
    console.set_pos(*pos)
    console.set_attr(*attr)
    #console.bottom_line(False)
    console.show_cursor(save_curs)
        
def hide_keys():
    global keys_visible
    
    keys_visible = False
    pos = console.get_pos()
    #console.bottom_line(True)
    console.last_row_on()
    console.set_pos(25,1)
    console.write(' '*(console.width), scroll_ok=False)
    
    console.set_pos(*pos)
        

def exec_key(ins):
    global keys_visible
    
    d = util.skip_white(ins)
    if d == '\x95': # ON
        if not keys_visible:
           show_keys()
    elif d == '\xdd': # OFF
        if keys_visible:
           hide_keys()   
    elif d== '\x93': # LIST
        for i in range(10):
            text = list(events.key_replace[i])
            for j in range(len(text)):
                if text[j]=='\x0d':   #  CR
                    text[j] = '\x1b'  # arrow left
            console.write('F'+str(i+1)+' '+''.join(text)+util.endl)    
    
    elif d=='(':
        # key (n)
        num = vartypes.pass_int_keep(expressions.parse_bracket(ins))[1]
        if num<0 or num>255:
            raise error.RunError(5)

        d=util.skip_white_read(ins)
        # others are ignored
        if num >=1 and num <= 20:
            if d=='\x95': # ON
                events.key_enabled[num-1] = True
                events.key_stopped[num-1]= False
            elif d=='\xDD': # OFF
                events.key_enabled[num-1] = True
            elif d=='\x90': # STOP
                events.key_stopped[num-1]=True
            else:
                raise error.RunError(2)
    else:
        # key n, "TEXT"    
        keynum = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        
        if keynum<1 or keynum>255:
            raise error.RunError(5)
        
        d = util.skip_white(ins)
        if d!= ',':
            raise error.RunError(5)
        else:
            ins.read(1)
 
        text = vartypes.pass_string_keep(expressions.parse_expression(ins))[1]
 
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
                    
    
    util.skip_to(ins, util.end_statement)



    
    

def exec_locate(ins):
    [row, col, cursor, start, stop] = expressions.parse_int_list(ins, 5, 2)          

    [crow, ccol] = [console.get_row(), console.get_col()]            
    if row==None:
        row = crow
    if col==None:
        col = ccol
    
    check_view(row,col)
    console.set_pos(row, col, scroll_ok=False)    
    if cursor!=None:
        console.show_cursor(cursor)
    
    # cursor shape not implemented




def exec_write(ins, screen=None):
    
    screen = expressions.parse_file_number(ins)
    
    if screen==None:
        screen=console
        
    expr = expressions.parse_expression(ins, allow_empty=True)

    if expr!=('',''):
        while True:
            if expr[0]=='$':
                screen.write('"'+expr[1]+'"')
            else:                
                screen.write(vartypes.value_to_str_keep(expr, screen=True, write=True)[1])
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
            output = ''
            
            col = screen.get_col()
            next_zone = int((col-1)/zone_width)+1
            if next_zone >= number_zones:
                output += util.endl
            else:            
                output += ' '*(1+zone_width*next_zone-col)
            
            
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
            
            numspaces = vartypes.pass_int_keep(expressions.parse_expression(ins), 0xffff)[1]
            numspaces %= screen.width
            
            util.require_read(ins, ')')
            
            screen.write(' '*numspaces)
            output=''
        elif d=='\xCE': #TAB(
            newline=False
            ins.read(1)
            
            screen.write(output)
            output = ''
            
            pos = vartypes.pass_int_keep(expressions.parse_expression(ins), 0xffff)[1]
            pos %= screen.width
            
            util.require_read(ins, ')')
            
            col = screen.get_col()
            if pos < col:
                screen.write(output+util.endl+' '*(pos-1))
            else:
                screen.write(output+' '*(pos-col))
            output=''    
        else:
            newline = True
            
            expr = expressions.parse_expression(ins)
            word = vartypes.value_to_str_keep(expr, screen=True)[1]  
            
            # numbers always followed by a space
            if expr[0] in ('%', '!', '#'):
                word += ' '
            
            if screen.col + len(word) -1 > screen.width and screen.col != 1:
                # prevent breaking up of numbers through newline
                output += util.endl
            output += word    
            
            





def get_next_expression(ins, fors=0):    

    util.skip_white(ins)
    expr = expressions.parse_expression(ins)
    
    # no semicolon: nothing more to read afterwards
    if not util.skip_white_read_if(ins, ';'):
        more_data = False
        semicolon = False
        return more_data, semicolon, expr
    
    # more to come?
    if util.skip_white(ins) in util.end_statement:
        more_data = False
        semicolon = True
        return more_data, semicolon, expr
    
    
    return True, True, expr





def exec_print_using(ins, screen):
    string_format_tokens = ('!','\\','&','_')
    number_format_tokens = ('#','**','$$','^^^^','_')

    util.skip_white(ins)
    format_expr = vartypes.pass_string_keep(expressions.parse_expression(ins))
    if format_expr[1]=='':
        raise error.RunError(5)
    
    fors = StringIO.StringIO(format_expr[1])
    
    util.require_read(ins,';')
    
    semicolon=False#=True    
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
                        
        if c=='_':
            c = fors.read(1)
            if c != '':
                screen.write(c)
            else:
                screen.write('_')
                        
        elif c=='!':
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins, fors)
            screen.write(vartypes.pass_string_keep(expr)[1][0])
                        
        elif c=='&':
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins, fors)
            screen.write(vartypes.pass_string_keep(expr)[1])
            
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
                more_data, semicolon, expr = get_next_expression(ins, fors)
            
                eword = vartypes.pass_string_keep(expr)[1]
                if len(eword)>len(word):
                    screen.write( eword[:len(word)] )
                else:
                    screen.write( eword ) 
                    screen.write( ' '*(len(word)-len(eword)) )
            else:
                screen.write( word )
        
                
        elif c=='#' \
                or (c in ('$', '*') and util.peek(fors)==c) \
                or (c=='+' and  util.peek(fors) == '#' or util.peek(fors,2) in ('##', '**')) \
                :    
            # numeric token
            format_chars = True
            more_data, semicolon, expr = get_next_expression(ins, fors)
            
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
    value = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    if value<0 or value>255:
        error.RunError(5)
    util.require(ins, util.end_statement)
       
            
                             
def exec_view_print(ins):
    d = util.skip_white(ins)
    if d in util.end_statement:
        console.set_view()
    else:
        start = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        util.require_read(ins, '\xCC') # TO
        stop = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
        util.require(ins, util.end_statement)
            
        console.set_view(start, stop)


def check_view(row, col):
    global keys_visible
    
    if row==console.height and keys_visible:
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
    d=util.skip_white(ins)
    
    if d=='#':
        dev = expressions.parse_file_number(ins)
       
    elif d in ('"', ','):
        device = vartypes.pass_string_keep(expressions.parse_expression(ins))[1].upper()
        if device not in deviceio.devices:
            # bad file name
            raise error.RunError(64)
        dev = deviceio.devices[device]
        
    else:
        dev = console
        
    # we can do calculations, but they must be bracketed...
    w = vartypes.pass_int_keep(expressions.parse_expr_unit(ins))[1]
    # get the appropriate errors out there
    if dev==console:
        
        # two commas are accepted
        util.skip_white_read_if(ins, ',')
            
        if not util.skip_white_read_if(ins, ','):
            # one comma, then stuff - illegal function call
            util.require(ins, util.end_statement, err=5)
            
        # anything after that is a syntax error      
        util.require(ins, util.end_statement)        
        
        # and finally an error if the width value doesn't make sense
        if w not in (40,80):
            raise error.RunError(5)
    else:
        util.require(ins, util.end_statement)
        
    dev.set_width(w)    
    
    if dev==console:
        console.clear()
        if keys_visible:
            show_keys()    


    
    
                
def format_number(value, fors):
    
    mbf = fp.unpack(value)
    
    if value[0] =='#':
        type_sign, exp_sign = '#', 'D'
    else:
        type_sign, exp_sign = '!', 'E'


    c=fors.read(1)
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
    
    commas=False        
    while c=='#':
        digits_before+=1
        c = fors.read(1)
        if c==',':
            commas=True
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
    #digits = deigits_before + decimals
    
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
    
    expr = fp.unpack(vartypes.vabs(value))
    
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
            lim_bot = fp.just_under(fp.ipow(expr.ten, work_digits-1))
        
             
            #lim_bot = fp.just_under(fp.from_int(expr.__class__, 10L**(work_digits-1)))
        else:
            # special case when work_digits == 0, see also below
            # setting to 0.1 results in incorrect rounding (why?)
            lim_bot = expr.one
        lim_top = fp.mul10(lim_bot)

        num, exp10 = fp.bring_to_range(expr, lim_bot, lim_top)
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
        factor = fp.ipow(expr.ten, decimals) 
        unrounded = fp.mul(expr, factor)
        num = fp.round(unrounded) 
        
        # find exponent 
        exp10 = 1
        pow10 = fp.ipow(expr.ten, exp10) # pow10 = 10L**exp10
        while fp.gt(num, pow10) or fp.equals(num, pow10): # while pow10 <= num:
            pow10 = fp.mul10(pow10) #pow10*=10
            exp10 += 1
        
        work_digits = exp10 + 1
        diff = 0
        
        if exp10 > expr.digits:
            diff = exp10 - expr.digits
            factor = fp.ipow(expr.ten, diff) # pow10 = 10L**exp10
            unrounded = fp.div(unrounded, factor) #fp.from_int(expr.__class__, 10L**diff))
            num = fp.round(unrounded)  
            work_digits -= diff
        
        num = fp.trunc_to_int(num)   
        # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
        digitstr = fp.get_digits(num, work_digits-1, remove_trailing=False)
        # fill up with zeros
        digitstr+='0'*diff
        
        fp_repr = fp.decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', (dots>0))
        
    
    ##########
    
    
    valstr=''
    
    if dollar_sign:
        valstr+='$'
           
    valstr+= fp_repr    
    
    sign = vartypes.vsgn(value)[1]
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
    

# current screen mode    
screen_mode=0    
vpagenum = 0
apagenum = 0

def exec_screen(ins):
    global keys_visible, screen_mode
    global vpagenum, apagenum
    
    params = expressions.parse_int_list(ins, 4)
    util.require(ins, util.end_statement)        
    
    mode = params[0]
    mode_info = console.mode_info(mode) 
    
    # backend does not support mode
    if  mode_info == None:
        raise error.RunError(5)

    # vpage and apage nums are persistent on mode switch
    # if the new mode has fewer pages than current vpage/apage, illegal fn call.
    if params[2] !=None:            
        apagenum = params[2]
    if params[3] !=None:
        vpagenum = params[3]       

    if apagenum >= mode_info[5] or vpagenum >= mode_info[5]:
       raise error.RunError(5)


    console.set_palette()
    
    if mode!=screen_mode:
        console.set_mode(mode)
        if keys_visible:
            show_keys()
        screen_mode=mode    

    # set active page & visible page, counting from 0. if higher than max pages, illegal fn call.            
    if not console.set_apage(apagenum):
       raise error.RunError(5)
    if not console.set_vpage(vpagenum):
       raise error.RunError(5)
    
    
    # in SCREEN 0, the colorswitch parameter doesn't actually switch colors on and off
    # but if it's different from the existing one, the screen is cleared.
    if params[1] != None:
        if (params[1]!=0) != console.colorswitch:
            console.set_colorswitch( params[1]!=0 )
            # clear all screen pages
            console.clear_all()
            if keys_visible:
                show_keys()
                
    
def exec_pcopy(ins):
    
    src = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require_read(ins, ',')
    dst = vartypes.pass_int_keep(expressions.parse_expression(ins))[1]
    util.require(ins, util.end_statement)

    if not console.copy_page(src,dst):
        raise error.RunError(5)
    
        
           
                
