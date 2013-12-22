#
# PC-BASIC 3.23 - util.py
#
# Token stream utilities
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


import error
import vartypes

# tokens

# LF is just whitespace if not preceded by CR
# (what about TAB? are there other whitespace chars in a tokenised file?)
whitespace = (' ', '\t', '\x0a')
# line ending tokens
end_line = ('', '\x00')
# statement ending tokens
end_statement = end_line + (':',) 
# expression ending tokens
end_expression = end_statement + (')', ']', ',', ';', '\xCC', '\x89', '\x8D', '\xCF', '\xCD') 
# '\xCC is 'TO', \x89 is GOTO, \x8D is GOSUB, \xCF is STEP, \xCD is THEN 


# whitespace for INPUT#, INPUT
# TAB x09 is not whitespace for input#. NUL \x00 and LF \x0a are. 
ascii_white = (' ', '\x00', '\x0a')


# stream utility functions


# StringIO does not seem to have a peek() function    
def peek(ins, n=1):
    d = ins.read(n)
    ins.seek(-len(d),1)
    return d


def skip_read(ins, skip_range):
    d = ins.read(1)
    while d in skip_range: 
        d = ins.read(1)
        if d=='':
            break
    return d

def skip(ins, skip_range):
    d = skip_read(ins, skip_range) 
    if d != '':
        ins.seek(-1,1)
    return d
    
def ascii_read_to(ins, findrange):
    out = ''
    while True:
        d = ins.read(1)
        if d=='':
            break
        if d in findrange:
            break
        out += d
    
    if d != '':    
        ins.seek(-1,1)    
    return out
        
##################################################
##################################################

# these are for tokenised streams only

def skip_white_read(ins):
    return skip_read(ins, whitespace)

def skip_white(ins):
    return skip(ins, whitespace)


def skip_to_read(ins, findrange):
    skip_to(ins, findrange)
    return ins.read(1)

def skip_to(ins, findrange, linum=-1, break_on_first_char=True):        
    out, linum = read_to(ins, findrange, linum, break_on_first_char)
    return linum
    
def read_to(ins, findrange, linum=-1, break_on_first_char=True):        
    out = ''
        
    while True: 
        c = ins.read(1)
        if c == '':
            break
        if c in findrange:
            if out != '' or break_on_first_char:
                break
        
        if c == '\x0f':
            out += c + ins.read(1)
        elif c in ('\x0b', '\x0c', '\x0d', '\x0e', '\x1c'):
            out += c + ins.read(2)
        elif c == '\x1d':
            out += c + ins.read(4)
        elif c == '\x1f':
            out += c + ins.read(8)
        elif c in ('\xff', '\xfe'):
            # two-byte tokens
            c+=ins.read(1)
            out += c 
        elif c == '\x00':  # offset and line number follow
            off = ins.read(2)
            out += c + off
            if len(off)<2 or off=='\x00\x00':
                linum=-1
                break
            off = ins.read(2)    
            linum = vartypes.uint_to_value(off) 
            out += off
        else:
            out += c
    
    if c!= '':
        ins.seek(-len(c),1)
    
    return out, linum    
    
    
def parse_line_number(ins):

    off = ins.read(2)
    if off=='\x00\x00' or len(off) < 2:
        return -1
    off = ins.read(2)
    if len(off)<2:
        return -1
    else:
        return vartypes.uint_to_value(off)
        
    
def getbasename(ins):
    name = ''
    d=ins.read(1).upper()
    if not (d>='A' and d<='Z'):
        # variable name must start with a letter
        if d != '':
            ins.seek(-1,1)
        return ''
    
    while (d>='A' and d<='Z') or (d>='0' and d<='9') or d=='.':
        name += d
        d = ins.read(1).upper()
    
    if d in vartypes.all_types:
        name += d
    else:
        if d != '':
            ins.seek(-1,1)
    return name


def skip_to_next(ins, for_char, next_char, allow_comma=False):
    
    stack = 0
    d = ''
    while True:
        linum = skip_to(ins, (for_char, next_char)) 
        d = peek(ins)
            
        if d == for_char:
            ins.read(1)
            stack += 1
        
        elif d == next_char:
            if stack <= 0:
                break
            else:    
                ins.read(1)
                stack -= 1
                
                # NEXT I, J
                if allow_comma: 
                    while (skip_white(ins) not in end_statement):
                        skip_to(ins, end_statement + (',',))
                        if peek(ins)==',':
                            if stack >0:
                                ins.read(1)
                                stack -= 1
                            else:
                                return linum
                     
        elif d in ('', '\x1a'):
            ins.seek(-1)
            break
            
    return linum
    
    
  
# parses a line number when referred toindirectly as in GOTO, GOSUB, LIST, RENUM, EDIT, etc.
def parse_jumpnum(ins):
    d = skip_white_read(ins)
    jumpnum=-1
    if d in ('\x0d', '\x0e'):
    
        jumpnum = vartypes.uint_to_value(ins.read(2))    
    else:
        # Syntax error
        raise error.RunError(2)
        return
    return jumpnum


# parses a list of line numbers
def parse_jumpnum_list(ins, size, err=2):
    pos=0
    output = [-1] * size
    while True:
        skip_white(ins)
        d= peek(ins)
        
        if d==',':
            ins.read(1)
            pos += 1
            if pos >= size:
                # 5 = illegal function call
                raise error.RunError(err)

        elif d in end_expression:
            break
        else:  
            output[pos] = parse_jumpnum(ins)
    return output
    
  
  
  
def map_list(action, ins, size, err):
    pos=0
    output = [None] * size
    while True:
        skip_white(ins)
        d= peek(ins)
        
        if d==',':
            ins.read(1)
            pos += 1
            if pos >= size:
                # 5 = illegal function call
                raise error.RunError(err)
                return output
        elif d in end_expression:
            break
        else:  
            output[pos] = action(ins)
    return output



def require_read(ins, char, err=2):
    if skip_white_read(ins) != char:
        raise error.RunError(err)
    
def require(ins, rnge, err=2):
    if skip_white(ins) not in rnge:
        raise error.RunError(err)
    

def skip_white_read_if(ins, char):
    val = (skip_white(ins) == char)
    if val:
        ins.read(1)
    return val


