#
# PC-BASIC 3.23 - expressions.py
#
# Expression parser 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#



import datetime
import os
from cStringIO import StringIO

import fp
import vartypes
import rnd
import tokenise

import oslayer
import util
import error
import var
import fileio
import deviceio


# for FRE() only
import program

import graphics
import console



def parse_int_list(ins, size, err=5):
    exprlist = parse_expr_list(ins, size, err)
    output = []
    for expr in exprlist:
        if expr==None:
            output.append(None)
        else:
            output.append(vartypes.pass_int_keep(expr)[1])
    
    return output




def parse_expr_list(ins, size, err=5, separators=(',',)):
    
    pos=0
    output = [None] * size
    while True:
        d = util.skip_white(ins)
        if d in separators: #==',':
            ins.read(1)
            pos += 1
            if pos >= size:
                # 5 = illegal function call
                raise error.RunError(err)
        elif d in util.end_expression:
            break
        else:  
            output[pos] = parse_expression(ins)
                    
    return output


def parse_file_number(ins):
    screen = None
    if util.skip_white_read_if(ins,'#'):
        number = vartypes.pass_int_keep(parse_expression(ins))[1]
        if number<0 or number>255:
            raise error.RunError(5)
        if number not in fileio.files:
            # bad file number
            raise error.RunError(52)
        screen = fileio.files[number]
        util.require_read(ins,',')
    
    return screen        


def parse_file_number_opthash(ins):
    if util.skip_white_read_if(ins, '#'):
        util.skip_white(ins)
    
    number = vartypes.pass_int_keep(parse_expression(ins))[1]
    if number<0 or number>255:
        raise error.RunError(5)
        
    return number    


def get_var_or_array_name(ins):
   
    name = var.get_var_name(ins)
    # array?
    indices=[]
    if util.skip_white(ins) in ('[', '('):
        ins.read(1)
        indices = parse_int_list(ins, 255, 9) # subscript out of range
        while len(indices)>0 and indices[-1]==None:
            indices = indices[:-1]
        if None in indices:
            raise error.RunError(2)
        if util.skip_white(ins) not in (']', ')'):
            raise error.RunError(2)
        else:
            ins.read(1) 
    return name, indices



# binary operator priority, lowest index is tightest bound 
# operators of the same priority are evaluated left to right      
priority = [
    ['\xED'], # ^  
    ['\xEB', '\xEC'], # *, /
    ['\xF4'], # \
    ['\xF3'], # MOD
    ['\xE9', '\xEA'], # +, -
    ['\xE6', '\xE7', '\xE8', '\xE6\xE7', '\xE8\xE7', '\xE8\xE6' ], # >, =, <, >=, <=, <>  
    ['\xEE'], # AND
    ['\xEF'], # OR
    ['\xF0'], # XOR
    ['\xF1'], # EQV
    ['\xF2'] # IMP
]

# flatten list
operator_tokens = [item for sublist in priority for item in sublist]






def parse_expression(ins, allow_empty=False):
    units = []
    operators = []
    
    d = util.skip_white(ins)
    
    
    while d not in util.end_expression: # and d not in util.end_statement:
        
        units.append(parse_expr_unit(ins))
        
        util.skip_white(ins)
        # string lit breaks expression, number after string lit breaks expression, + or - doesnt (could be an operator...
        #if d in util.end_expression or d in util.end_statement or d=='"' :
        d = util.peek(ins)
        if d not in operator_tokens:
            break
        else:
            ins.read(1)
        
        if d in ['\xE6', '\xE7', '\xE8']:
            nxt = util.skip_white(ins)
            if nxt in ['\xE6', '\xE7', '\xE8']:
                ins.read(1)
                if d==nxt:
                    raise error.RunError(2)
                else:    
                    d += nxt
                    if d[0] == '\xe7': #= 
                        # =>, =<
                        d= d[1]+d[0]
                    elif d == '\xe6\xe8': # ><
                        d='\xe8\xe6'    
        
        operators.append(d)
        d = util.skip_white(ins)           
        
    
    # empty expression is a syntax error (inside brackets) or Missing Operand (in an assignment) or ok (in print)
    if len(units) == 0:
        if allow_empty:
            return ('', '')
        else:    
            raise error.RunError(22)
    
    if len(units) <= len(operators):
        # missing operand
        raise error.RunError(22)
    
    return parse_operators(operators, units)
        

def parse_operators(operators, units):
    
    for current_priority in priority:
        pos = 0
        while pos < len(operators):
            if operators[pos] in current_priority:
                units[pos] = value_operator(operators[pos], units[pos], units[pos+1])
                del units[pos+1]
                del operators[pos]
            else:
                pos += 1
        
        if len(operators)==0:
            break
    
    if len(operators)>0:
        # unrecognised operator, syntax error
        raise error.RunError(2)
    
    return units[0]    
    
    
def value_operator(op, left, right):
    if op == '\xED':
        return vartypes.vcaret(left, right)
    elif op == '\xEB':
        return vartypes.vtimes(left, right)
    elif op == '\xEC':
        return vartypes.vdiv(left, right)
    elif op == '\xF4':
        return vartypes.vidiv(left, right)
    elif op == '\xF3':
        return vartypes.vmod(left, right)
    elif op == '\xE9':
        return vartypes.vplus(left, right)
    elif op == '\xEA':
        return vartypes.vminus(left, right)
    elif op ==  '\xE6':
        return vartypes.vgt(left, right)
    elif op ==  '\xE7':
        return vartypes.veq(left, right)
    elif op ==  '\xE8':
        return vartypes.vlt(left, right)
    elif op ==  '\xE6\xE7':
        return vartypes.vgte(left, right)
    elif op ==  '\xE8\xE7':
        return vartypes.vlte(left, right)
    elif op ==  '\xE8\xE6':
        return vartypes.vneq(left, right)
    elif op ==  '\xEE':
        return vartypes.vand(left, right)
    elif op ==  '\xEF':
        return vartypes.vor(left, right)
    elif op ==  '\xF0':
        return vartypes.vxor(left, right)
    elif op ==  '\xF1':
        return vartypes.veqv(left, right)
    elif op ==  '\xF2':
        return vartypes.vimp(left, right)
    else:
        raise error.RunError(2)
    



def parse_expr_unit(ins):
    d = util.skip_white_read(ins)
    
    if d=='"':
        output=''
        # string literal
        # while tokenised nmbers inside a string lieral will be printed as tokenised numbers, they don't actually execute as such:
        # a \00 character, even if inside a tokenised number, will break a string literal (and make the parser expect a 
        # line number afterwards, etc. We follow this.
        d = ins.read(1)
        while d not in util.end_line + ('"',)  : # ['"', '\x00', '']:
            output += d
            d = ins.read(1)        
        if d == '\x00':
            ins.seek(-1,1)
        return ('$', output)
            
    elif d >= 'A' and d <= 'Z': # variable name
        ins.seek(-1,1)
        name, indices = get_var_or_array_name(ins)
        return var.get_var_or_array(name, indices)
        
    elif d in tokenise.tokens_number:
        ins.seek(-1,1)
        return tokenise.parse_value(ins)   
        
    # gw-basic allows adding line numbers to numbers     
    elif d in tokenise.tokens_linenum:
        ins.seek(-1,1)
        return ('%', util.parse_jumpnum(ins))    
    
    elif d == '\x85':   # INPUT
        return value_input(ins)
    elif d == '\xC8':   # SCREEN
        return value_screen(ins)
    
    elif d == '\xD0':       # USR
        return value_usr(ins)
    elif d == '\xD1':       # FN
        return value_fn(ins)
    elif d == '\xD3':       # NOT
        return vartypes.vnot(parse_expr_unit(ins))
    elif d == '\xD4':       # ERL
        return value_erl(ins)
    elif d == '\xD5':       # ERR
        return value_err(ins)
    elif d == '\xD6':       # STRING$
        return value_string(ins)
    
    elif d == '\xD8':       # INSTR
        return value_instr(ins)    
    elif d == '\xDA':       # VARPTR
        return value_varptr(ins)
    
    elif d == '\xDB':       # CSRLIN
        return ('%', console.get_row())
    elif d == '\xDC':       # POINT
        return value_point(ins)
    
    elif d == '\xDE':       # INKEY$
        # wait a tick
        console.idle()
        return ('$', console.get_char())
    
    elif d == '\xE9':        # unary +
        return parse_expr_unit(ins)
    elif d == '\xEA':       # unary -
        return vartypes.vneg(parse_expr_unit(ins))     


    elif d == '\xFD':
        d = ins.read(1)
        if d== '\x81':            # CVI
            expr = parse_bracket(ins)
            cstr =  vartypes.pass_string_keep(expr)[1]
            if len(cstr) < 2:
                raise error.RunError(5)
            return ('%', vartypes.sint_to_value(cstr[:2]))
        elif d=='\x82':            # CVS
            cstr =  vartypes.pass_string_keep(parse_bracket(ins))[1]
            if len(cstr) < 4:
                raise error.RunError(5)
            return ('!', cstr[:4]) #('!', list(cstr[:4]))
        elif d=='\x83':            # CVD
            cstr =  vartypes.pass_string_keep(parse_bracket(ins))[1]
            if len(cstr) < 8:
                raise error.RunError(5)
            return ('#', cstr[:8])
        elif d=='\x84':   #MKI$
            cint = vartypes.pass_int_keep(parse_bracket(ins))[1]    
            return ('$', vartypes.value_to_sint(cint))
        elif d=='\x85':   #MKS$
            csng = vartypes.pass_single_keep(parse_bracket(ins))[1]    
            return ('$', "".join(csng))
        elif d=='\x86':   #MKD$
            cdbl = vartypes.pass_double_keep(parse_bracket(ins))[1]    
            return ('$', "".join(cdbl))
        elif d== '\x8b': # EXTERR
            return value_exterr(ins)

    
    elif d == '\xFE':
        d = ins.read(1)        
        if d== '\x8D': # DATE$
            return value_date(ins)
        elif d== '\x8E': # TIME$
            return value_time(ins)
        elif d== '\x94': # TIMER
            return value_timer(ins)
        elif d== '\x95': # ERDEV
            return value_erdev(ins)
        elif d== '\x96': # IOCTL
            return value_ioctl(ins)
        elif d== '\x9B': # ENVIRON$
            return value_environ(ins)
        elif d== '\x9E': # PMAP
            return value_pmap(ins)
                    
    elif d == '\xFF':
        d = ins.read(1)
        if d == '\x81':         # LEFT$
            return value_left(ins)
        elif d == '\x82':     # RIGHT$
            return value_right(ins)
        elif d == '\x83':     # MID$
            return value_mid(ins)
        elif d == '\x84':   # SGN
            return vartypes.vsgn(parse_bracket(ins))
        elif d == '\x85':   # INT
            return vartypes.vint(parse_bracket(ins))
        elif d == '\x86':   # ABS
            return vartypes.vabs(parse_bracket(ins))
        elif d == '\x87':   # SQR
            return vartypes.vsqrt(parse_bracket(ins))
        elif d == '\x88':   # RND
            util.skip_white(ins)
            if util.peek(ins) == '(':
                return rnd.vrnd(parse_bracket(ins))
            else:
                return rnd.vrnd(('',''))
        elif d == '\x89':   # SIN
            return vartypes.vsin(parse_bracket(ins))
        elif d == '\x8a':   # LOG
            return vartypes.vlog(parse_bracket(ins))
        elif d == '\x8b':   # EXP
            return vartypes.vexp(parse_bracket(ins))
        elif d == '\x8c':   # COS
            return vartypes.vcos(parse_bracket(ins))
        elif d == '\x8D':   # TAN
            return vartypes.vtan(parse_bracket(ins))
        elif d == '\x8E':   # ATN
            return vartypes.vatn(parse_bracket(ins))
       
            
        elif d == '\x8F':   # FRE
            # GW does grabge collection if a string-valued argument is specified. We don't.
            parse_bracket(ins)
            return ('%', var.free_mem - (len(program.bytecode.getvalue())-4) - var.variables_memory_size() )
        elif d == '\x90':   # INP
            return value_inp(ins)
        elif d == '\x91':   # POS
            # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
            parse_bracket(ins)
            return ('%', console.get_col())
        elif d == '\x92':   # LEN
            val= ('%', len(vartypes.pass_string_keep(parse_bracket(ins))[1]) )
            d = ins.read(1)
            if d !='':
                ins.seek(-1,1)
            return val
        elif d == '\x93':   # STR$
            s = parse_bracket(ins)
            if s[0]=='$':
                raise error.RunError(13)
            return vartypes.value_to_str_keep(s, screen=True)
        
        elif d == '\x94':   # VAL
            return tokenise.str_to_value_keep(parse_bracket(ins))
        elif d == '\x95':   # ASC
            s =vartypes.pass_string_keep(parse_bracket(ins))[1]
            if s!='':
                return ('%', ord(s[0]))
            else:
                raise error.RunError(5)
        elif d == '\x96':   # CHR$
            return ('$', chr(vartypes.pass_int_keep(parse_bracket(ins))[1]) )
        elif d == '\x97':   # PEEK
            return value_peek(ins)
            
        elif d == '\x98':   # SPACE$
            num = vartypes.pass_int_keep(parse_bracket(ins))[1]
            if num <0 or num > 255:
                raise error.RunError(5)
            return ('$', ' '*num )
        elif d == '\x99':   # OCT$
            # allow range -32768 to 65535
            val = vartypes.pass_int_keep(parse_bracket(ins), 0xffff)[1]
            if val <0:
                return ('$', vartypes.oct_to_str(vartypes.value_to_sint(val))[2:])
            else:
                return ('$', vartypes.oct_to_str(vartypes.value_to_uint(val))[2:])
        
        #    return ('$', oct(vartypes.pass_int_keep(parse_bracket(ins), 0xffff)[1])[1:] )
        
        elif d == '\x9A':   # HEX$
            # allow range -32768 to 65535
            val = vartypes.pass_int_keep(parse_bracket(ins), 0xffff)[1]
            if val <0:
                return ('$', vartypes.hex_to_str(vartypes.value_to_sint(val))[2:])
            else:
                return ('$', vartypes.hex_to_str(vartypes.value_to_uint(val))[2:])
                    
            #return ('$', hex(vartypes.pass_int_keep(parse_bracket(ins), 0xffff)[1])[2:].upper() )
        elif d == '\x9B':   # LPOS
            # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
            parse_bracket(ins)
            return ('%', deviceio.lpt1.get_col())
        elif d == '\x9C':   # CINT
            return vartypes.pass_int_keep(parse_bracket(ins))
        elif d == '\x9D':   # CSNG
            return vartypes.pass_single_keep(parse_bracket(ins))
        elif d == '\x9E':   # CDBL
            return vartypes.pass_double_keep(parse_bracket(ins))
        elif d == '\x9F':   # FIX
            return vartypes.vfix(parse_bracket(ins))    
        elif d == '\xA0':   # PEN
            return value_pen(ins)
        elif d == '\xA1':   # STICK
            return value_stick(ins)
        elif d == '\xA2':   # STRIG
            return value_strig(ins)
        elif d == '\xA3':   # EOF
            return value_eof(ins)
        elif d == '\xA4':   # LOC
            return value_loc(ins)
        elif d == '\xA5':   # LOF
            return value_lof(ins)

    elif d == '(':
        val = parse_expression(ins)
        if ins.read(1) != ')':
            raise error.RunError(2)                    
        return val    
       
    return ('', '')


def parse_bracket(ins):
    util.require_read(ins, '(')
    val = parse_expression(ins, allow_empty = True)
    if val==('',''):
        # we need a Syntax error, not a Missing operand
        raise error.RunError(2)
    util.require_read(ins, ')')
    return val





# string maniulation            
    
    
def value_instr(ins):
    util.require_read(ins, '(')

    s = parse_expression(ins, allow_empty=True)
    
    big = ''
    small = ''
    have_big = False
    n=1
    if s[0] == '':
        raise error.RunError(2)
    elif s[0] != '$':
        n = vartypes.pass_int_keep(s)[1]
        if n<1 or n>255:
            # illegal fn call
            raise error.RunError(5)
    else:
        big = vartypes.pass_string_keep(s)[1]
        have_big= True
        
    util.require_read(ins, ',')

    if not have_big:
        s = parse_expression(ins, allow_empty=True)
        big = vartypes.pass_string_keep(s)[1]
        
        util.require_read(ins, ',')

    s = parse_expression(ins, allow_empty=True)
    small = vartypes.pass_string_keep(s)[1]
    
    util.require_read(ins, ')')

    if big == '' or n > len(big):
        return ('%',0)
    
    # basic counts string positions from 1
    return ('%', n + big[n-1:].find(small))   
   
        

def value_mid(ins):
    # MID$
    util.require_read(ins, '(')
    s = vartypes.pass_string_keep(parse_expression(ins))[1]
    util.require_read(ins, ',')
    start = vartypes.pass_int_keep(parse_expression(ins))[1]

    if util.skip_white_read_if(ins, ','):
        num = vartypes.pass_int_keep(parse_expression(ins))[1]
    else:
        num = len(s)
    
    util.require_read(ins, ')')
    
    if start <1 or start>255:
        raise error.RunError(5)
    if num <0 or num>255:
        raise error.RunError(5)
    
    if num==0 or start>len(s):
        return ('$', '')
    
    start -= 1    
    stop = start + num 
    if stop > len(s):
        stop = len(s)
    return ('$', s[start:stop])  
         
    
def value_left(ins):
    # LEFT$
    util.require_read(ins, '(')
    s = vartypes.pass_string_keep(parse_expression(ins))[1]
    util.require_read(ins, ',')
    num = vartypes.pass_int_keep(parse_expression(ins))[1]
    util.require_read(ins, ')')
    
    if num <0 or num>255:
        raise error.RunError(5)
    
    if num==0:
        return ('$', '')
    
    stop = num 
    if stop > len(s):
        stop = len(s)
    return ('$', s[:stop])  
    
    
def value_right(ins):
    # RIGHT$
    util.require_read(ins, '(')
    s = vartypes.pass_string_keep(parse_expression(ins))[1]
    util.require_read(ins, ',')
    num = vartypes.pass_int_keep(parse_expression(ins))[1]
    util.require_read(ins, ')')
    
    if num <0 or num>255:
        raise error.RunError(5)
    
    if num==0:
        return ('$', '')
    
    stop = num 
    if stop > len(s):
        stop = len(s)
    return ('$', s[-stop:])  
    

def value_screen(ins):
    # SCREEN(x,y,[z])
    util.require_read(ins, '(')
    args = parse_int_list(ins, 3, 5) 
    util.require_read(ins, ')')
    
    if args[0] == None or args[1]==None:
        raise error.RunError(5)
    if args[0]<1 or args[0] > console.height:
        raise error.RunError(5)
    if console.view_set and args[0]<console.view_start or args[0] > console.scroll_height:
        raise error.RunError(5)
    
    if args[1]<1 or args[1] > console.width:
        raise error.RunError(5)
    
    (char, attr) = console.read_screen(args[0], args[1])
    
    if args[2] != None and args[2] != 0:
        return ('%', attr)
    else:
        return ('%', ord(char))
    
    
def value_input(ins):    # INPUT$
    if ins.read(1) != '$':
        raise error.RunError(2)
    
    util.require_read(ins, '(')
        
    num = vartypes.pass_int_keep(parse_expression(ins))[1]
    if num<1 or num>255:
        raise error.RunError(5)
    
    screen = console    
    if util.skip_white_read_if(ins, ','):
        util.skip_white_read_if(ins, '#')
        
        filenum = vartypes.pass_int_keep(parse_expression(ins))[1]
        
        if filenum<0 or filenum>255:
            raise error.RunError(5)
        if filenum not in fileio.files:
            # bad file number
            raise error.RunError(52)
        screen = fileio.files[filenum]
    
    if util.skip_white_read(ins) !=')':
        raise error.RunError(2)
         
    
    word = screen.read_chars(num)
    return ('$', word)        
    
           
def value_string(ins): # STRING$
    util.require_read(ins, '(')
    n, j = parse_expr_list(ins, 2)    
    
    n = vartypes.pass_int_keep(n)[1]
    if n<0 or n> 255:
        raise error.RunError(5)
    
    if j[0]=='$':
        j = ord(j[1][0])
    else:
        j = vartypes.pass_int_keep(j)[1]        
    
    if j<0 or j> 255:
        raise error.RunError(5)
    
    util.require_read(ins, ')')

    return ('$', chr(j)*n)


def value_loc(ins): # LOC

    util.skip_white(ins)
    num = vartypes.pass_int_keep(parse_bracket(ins), maxint=0xffff)[1]
    if num>255 or num<0 or num not in fileio.files:
        raise error.RunError(52)
        
    # refuse for output devices, such as SCRN: (bad file mode). Kybd: and com1: etc should be allowed
    if fileio.files[num] in deviceio.output_devices:
        # bad file mode
        raise error.RunError(54)
    
    return ('%', fileio.files[num].loc())
  

def value_eof(ins): # EOF

    util.skip_white(ins)
    num = vartypes.pass_int_keep(parse_bracket(ins), maxint=0xffff)[1]
    if num>255 or num<0 or num not in fileio.files:
        # bad file number
        raise error.RunError(52)
    
    if fileio.files[num].mode == 'O':
        # bad file mode
        raise error.RunError(54)
        
    return vartypes.bool_to_int_keep(fileio.files[num].eof())
  
def value_lof(ins): # LOF

    util.skip_white(ins)
    num = vartypes.pass_int_keep(parse_bracket(ins), maxint=0xffff)[1]
    if num>255 or num<0 or num not in fileio.files:
        raise error.RunError(52)
    
    return ('%', fileio.files[num].lof() )
    

######################################################################

######################################################################


       
def value_environ(ins):
    if ins.read(1)!='$':
        raise error.RunError(2)
        
    expr = parse_bracket(ins)
    if expr[0]=='$':
        val = os.getenv(expr[1])
    
        if val==None:
            val=''
        return ('$', val)
    
    else:
        expr = vartypes.pass_int_keep(expr)[1]
        envlist = list(os.environ)
            
        if expr<1 :
            raise error.RunError(5)
        if expr>len(envlist):
            return ('$', '')            
        else:
            val = os.getenv(envlist[expr-1])
            
            return ('$', envlist[expr-1]+'='+val)
    

        
        
def value_timer(ins):
    # precision of GWBASIC TIMER is about 1/20 of a second
    timer = fp.div( fp.from_int(fp.MBF_class, oslayer.timer_milliseconds()/50), fp.from_int(fp.MBF_class,20))
    return fp.pack(timer)
    
    
def value_time(ins):
    #time$
    now = datetime.datetime.today() + oslayer.time_offset
    timestr = now.strftime('%H:%M:%S')
    return ('$', timestr)
    
def value_date(ins):
    #date$
    now = datetime.datetime.today() + oslayer.time_offset
    timestr = now.strftime('%m-%d-%Y')
    return ('$', timestr)

#######################################################
# functions

def value_fn(ins):
    fnname = var.get_var_name(ins)
    
    if fnname not in var.functions:
        # undefined user function
        raise error.RunError(18)

    varnames, fncode = var.functions[fnname]
    
    # save existing vars
    varsave = {}
    for name in varnames:
        if name[0]=='$':
            # we're just not doing strings
            raise error.RunError(13)
        if name in var.variables:
            varsave[name] = var.variables[name]

    # read variables
    util.require_read(ins, '(')
    exprs = parse_expr_list(ins, len(varnames), err=2)
    if None in exprs:
        raise error.RunError(2)
    for i in range(len(varnames)):
        var.setvar(varnames[i], exprs[i])
    util.require_read(ins,')')
    
    fns = StringIO(fncode)
    fns.seek(0)
    value= parse_expression(fns)    

    # restore existing vars
    
    for name in varnames:
        del var.variables[name]
    for name in varsave:    
        var.variables[name] = varsave[name]

    return value    


###############################################################
# graphics    
    
def value_point(ins):
    util.require_read(ins, '(')
    lst = parse_expr_list(ins, 2, err=2)
    util.require_read(ins, ')')

    if lst[0]==None:
        raise error.RunError(2)
    if lst[1]==None:
        # single-argument version
        x,y = graphics.get_coord()
        fn = vartypes.pass_int_keep(lst[0])[1]
        if fn==0:
            return ('%', x)
        elif fn==1:
            return ('%', y)
        elif fn==2:
            fx, fy = graphics.get_window_coords(x,y)
            return fx
        elif fn==3:
            fx, fy = graphics.get_window_coords(x,y)
            return fy
    else:       
        return ('%', graphics.get_point(vartypes.pass_int_keep(lst[0])[1], vartypes.pass_int_keep(lst[1])[1]))        

def value_pmap(ins):
    util.require_read(ins, '(')
    coord = fp.unpack(vartypes.pass_single_keep(parse_expression(ins)))
    util.require_read(ins, ',')
    mode = vartypes.pass_int_keep(parse_expression(ins))[1]
    util.require_read(ins, ')')

 
    if mode == 0:
        value, dummy = graphics.window_coords(coord,fp.MBF_class.zero)       
        value = ('%', value)        
    elif mode == 1:
        dummy, value = graphics.window_coords(fp.MBF_class.zero,coord)       
        value = ('%', value)        
    elif mode == 2:
        value, dummy = graphics.get_window_coords(fp.round_to_int(coord),0)       
        value = fp.pack(value)
    elif mode == 3:
        dummy, value = graphics.get_window_coords(0,fp.round_to_int(coord))       
        value = fp.pack(value)
    else:
        raise error.RunError(5)
               
    return value
    
#####################################################################

def value_erl(ins):
    return ('%', error.get_error()[1])


def value_err(ins):
    return ('%', error.get_error()[0])
    
#####################################################################

def value_pen(ins):
    fn = vartypes.pass_int_keep(parse_bracket(ins))[1]
    if fn == 0:
        return vartypes.bool_to_int_keep(console.pen_has_been_down())
    elif fn == 1:
        x,y = console.get_last_pen_down_pos()
        return ('%', x)
    elif fn == 2:
        x,y = console.get_last_pen_down_pos()
        return ('%', y)
    elif fn == 3:
        return vartypes.bool_to_int_keep(console.pen_is_down())
    elif fn == 4:
        x,y = console.get_pen_pos()
        return ('%', x)
    elif fn == 5:
        x,y = console.get_pen_pos()
        return ('%', y)
    elif fn == 6:
        col, row = console.get_last_pen_down_pos_char()
        return ('%', row)
    elif fn == 7:
        col, row = console.get_last_pen_down_pos_char()
        return ('%', col)
    elif fn == 8:
        col, row = console.get_pen_pos_char()
        return ('%', row)
    elif fn == 9:
        col, row = console.get_pen_pos_char()
        return ('%', col)
    else:
        raise error.RunError(5)
        

# coordinated run 1..200 (says http://www.qb64.net/wiki/index.php?title=STICK)
# STICK(0) is required to get values from the other STICK functions. Always read it first!
def value_stick(ins):
    fn = vartypes.pass_int_keep(parse_bracket(ins))[1]
    
    if fn == 0:
        x,y = console.stick_coord(0)
        return ('%', x)
    elif fn == 1:
        x,y = console.stick_coord(0)
        return ('%', y)
    elif fn == 2:
        x,y = console.stick_coord(1)
        return ('%', x)
    elif fn == 3:
        x,y = console.stick_coord(1)
        return ('%', y)
    else:
        raise error.RunError(5)
    
    
    
def value_strig(ins):
    fn = vartypes.pass_int_keep(parse_bracket(ins))[1]
    # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
    if fn<0 or fn>7:
        raise error.RunError(5)
    
    joy = fn//4
    trig = (fn//2)%2
    if fn%2==0:
        return vartypes.bool_to_int_keep(console.stick_has_been_trig(joy,trig))
    else:
        return vartypes.bool_to_int_keep(console.stick_trig(joy,trig))
    
    
    
#########################################################
# not implemented

# pre-defined PEEK outputs
peek_values={}


# do-nothing PEEK    
def value_peek(ins):
    global peek_values
    addr = vartypes.pass_int_keep(parse_bracket(ins))[1]
    if addr in peek_values:
        return ('%', peek_values[addr])
    else:    
        return ('%',0)
        
# do-nothing VARPTR, VARPTR$    
def value_varptr(ins):    
    if util.peek(ins,1)=='$':
        ins.read(1) 
        parse_bracket(ins)
        return ('$', '')
    else:
        parse_bracket(ins)
        return ('%', 0)
        
def value_usr(ins):
    c= util.peek(ins,1)
    if c>= '0' and c<='9':
        ins.read(1)
        
    parse_bracket(ins)
    return ('%', 0)
    
def value_inp(ins):
    parse_bracket(ins)
    return ('%', 0)
        
def value_erdev(ins):
    if util.peek(ins,1)=='$':
        ins.read(1) 
        return ('$', '')
    else:    
        return ('%', 0)
        
def value_exterr(ins):
    parse_bracket(ins)
    return ('%', 0)
    
# ioctl$    
def value_ioctl(ins):
    if ins.read(1) != '$':
        raise error.RunError(2)
        
    parse_bracket(ins)
    return ('%', 0)
            
            
            
