#
# PC-BASIC 3.23 - tokenise.py
#
# Token parser
# converts between tokenised and ASCII formats of a GW-BASIC program file
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#
# Acknowledgements:
#
# Norman De Forest for documentation of the file format:
#   http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html
# danvk for the open-source detokenise implementation here:
#   http://www.danvk.org/wp/2008-02-03/reading-old-gw-basic-programs/
# Julian Bucknall and asburgoyne for descriptions of the Microsoft Binary Format posted here:
#   http://www.boyet.com/Articles/MBFSinglePrecision.html
#   http://www.experts-exchange.com/Programming/Languages/Pascal/Delphi/Q_20245266.html


#################################################################
from cStringIO import StringIO

import error
import representation
import util
import vartypes

from representation import ascii_digits
# newline is considered whitespace
tokenise_whitespace = representation.whitespace #[' ', '\t', '\x0a']

debug = False
tokens_number = ('\x0b','\x0c','\x0f',
    '\x11','\x12','\x13','\x14','\x15','\x16','\x17','\x18','\x19','\x1a','\x1b',
    '\x1c','\x1d', '\x1f')
tokens_linenum = ('\x0d', '\x0e')
tokens_operator = tuple(map(chr, range(0xe6, 0xed+1)))
tokens_with_bracket = ('\xd2', '\xce')

ascii_operators = ('+', '-', '=', '/', '\\', '^', '*', '<', '>')
ascii_uppercase = tuple(map(chr, range(ord('A'),ord('Z')+1)))        

# allowable as chars 2.. in a variable name (first char must be a letter)
name_chars = ascii_uppercase + ascii_digits + ('.',)

# keywords than can followed by one or more line numbers
linenum_words = [
    'GOTO', 'THEN', 'ELSE', 'GOSUB', 
    'LIST', 'RENUM', 'EDIT', 'LLIST', 
    'DELETE', 'RUN', 'RESUME', 'AUTO', 
    'ERL', 'RESTORE', 'RETURN']

#################################################################
# Detokenise functions

def ascii_read_to(ins, findrange):
    out = ''
    while True:
        d = ins.read(1)
        if d == '':
            break
        if d in findrange:
            break
        out += d
    ins.seek(-len(d),1)    
    return out

def detokenise_line(bytes, bytepos=None):
    litstring, comment = False, False
    textpos = 0
    current_line = util.parse_line_number(bytes)
    if current_line < 0:
        # parse_line_number has returned -1 and left us here:  .. 00 | _00_ 00 1A
        # stream ends or end of file sequence \x00\x00\x1A
        return -1, '', 0
    elif current_line == 0 and util.peek(bytes)==' ':
        # ignore up to one space after line number 0
        bytes.read(1)
    # write one extra whitespace character after line number
    output = representation.int_to_str(current_line) + bytearray(' ')
    # detokenise tokens until end of line
    while True:
        s = bytes.read(1)
        if not textpos and bytes.tell() >= bytepos:
            textpos = len(output)
        if s in util.end_line:
            # \x00 ends lines and comments when listed, if not inside a number constant
            # stream ended or end of line
            break
        elif s == '"':
            # start of literal string, passed verbatim until a closing quote or EOL comes by
            # however number codes are *printed* as the corresponding numbers, even inside comments & literals
            output += s
            litstring = not litstring  
        elif s in tokens_number:
            bytes.seek(-1,1)
            representation.detokenise_number(bytes, output)
        elif s in tokens_linenum: 
            # 0D: line pointer (unsigned int) - this token should not be here; interpret as line number and carry on
            # 0E: line number (unsigned int)
            output += representation.uint_to_str(bytearray(bytes.read(2)))
        elif comment or litstring or (s >= '\x20' and s <= '\x7e'):   # honest ASCII
            output += s
        else:
            bytes.seek(-1,1)
            comment = detokenise_keyword(bytes, output)
    return current_line, output, textpos

# de tokenise one- or two-byte tokens
# output must be mutable
def detokenise_keyword(bytes, output):
    # try for single-byte token or two-byte token
    # if no match, first char is passed unchanged
    s = bytes.read(1)
    try:
        keyword = token_to_keyword[s]
    except KeyError:
        s += util.peek(bytes)
        try:
            keyword = token_to_keyword[s]
            bytes.read(1)
        except KeyError:
            output += s[0]
            return False
    # when we're here, s is an actual keyword token.
    # number followed by token is separated by a space 
    if (len(output)>0) and (chr(output[-1]) in ascii_digits) and (s not in tokens_operator):
            output += ' '
    output += keyword
    comment = False
    if keyword == "'":
        comment = True
    elif keyword == "REM":
        nxt = bytes.read(1)
        if nxt == '':
            pass
        elif token_to_keyword.has_key(nxt) and token_to_keyword[nxt] == "'":
            # if next char is token('), we have the special value REM' -- replaced by ' below.
            output += "'"
        else:
            # otherwise, it's part of the comment or an EOL or whatever, pass back to stream so it can be processed
            bytes.seek(-1,1)
        comment = True
    # check for special cases
    #   [:REM']   ->  [']
    if len(output) > 4 and str(output[-5:]) ==  ":REM'":
        output[:] = output[:-5] + "'"  
    #   [WHILE+]  ->  [WHILE]
    elif len(output) > 5 and str(output[-6:]) == "WHILE+":
        output[:] = output[:-1]        
    #   [:ELSE]  ->  [ELSE]
    # note that anything before ELSE gets cut off, e.g. if we have 1ELSE instead of :ELSE it also becomes ELSE
    # SIC: len(output) > 4 and str(output[-4:])
    elif len(output) > 4 and str(output[-4:]) == "ELSE":
        if len(output) > 5 and chr(output[-5]) == ':' and chr(output[-6]) in ascii_digits:
            output[:] = output[:-5] + " ELSE" 
        else:
            output[:] = output[:-5] + "ELSE"
    # token followed by token or number is separated by a space, except operator tokens and SPC(, TAB(, FN, USR
    nxt = util.peek(bytes)
    if (not comment and nxt.upper() not in (util.end_line + tokens_operator + 
                                    ('\xD9', '"', ',', ' ', ':', '(', ')', '$', '%', '!', '#', '_', '@', '~', '|', '`')) 
                and s not in (tokens_operator + tokens_with_bracket + ('\xD0', '\xD1'))): 
        # excluding TAB( SPC( and FN. \xD9 is ', \xD1 is FN, \xD0 is USR.
        output += ' '
    return comment
    
#################################################################
# Tokenise functions

# readln, but break on \r rather than \n. ignore single starting LF to account for CRLF *without seeking*.
# include the \r at the end of the line. break at \x1a EOF. Do not include \x1a.
def read_program_line(ins):
    d = ins.read(1)
    eof = d in ('\x1a', '')
    out = d if (not eof and d != '\n') else ''    
    while d != '\r' and not eof:
        d = ins.read(1)
        eof = d in ('\x1a', '')
        if eof:
            break
        out += d       
    return out, eof

def tokenise_line(line):      
    ins = StringIO(line)
    outs = StringIO()          
    # skip whitespace at start of line
    d = util.skip(ins, tokenise_whitespace)
    if d == '':
        # empty line at EOF
        return outs
    # read the line number
    tokenise_line_number(ins, outs)
    # non-parsing modes
    rem = False     # REM: pass unchanged until e-o-line
    data = False    # DATA: pass unchanged until :
    # expect line number
    allow_jumpnum = False
    # expect number (6553 6 -> the 6 is encoded as \x17)
    allow_number = True
    # flag for SPC( or TAB( as numbers can follow the closing bracket
    spc_or_tab = False
    # parse through elements of line
    while True: 
        # non-parsing modes        
        if rem:
            # anything after REM is passed as is till EOL
            outs.write(ascii_read_to(ins, ('', '\r', '\0')))
            break
        elif data:
            # read DATA as is, till end of statement, except for literals    
            while True:
                outs.write(ascii_read_to(ins, ('', '\r', '\0', ':', '"')))
                if util.peek(ins) == '"':
                    # string literal in DATA
                    tokenise_literal(ins, outs)
                else:
                    break            
            data = False
        elif util.peek(ins)=='"':
            # handle string literals    
            tokenise_literal(ins, outs)
        # read next character
        char = util.peek(ins)
        # anything after NUL is ignored till EOL
        if char == '\x00':
            ins.read(1)
            ascii_read_to(ins, ('', '\r'))
            break
        # end of line    
        if char in ('', '\r'):
            break
        # convert anything else to upper case
        c = char.upper()
        # handle whitespace
        if c in tokenise_whitespace:
            ins.read(1)
            outs.write(char)
        # handle jump numbers
        elif allow_number and allow_jumpnum and c in ascii_digits + ('.',):
            tokenise_jump_number(ins, outs) 
        # handle numbers
        # numbers following var names with no operator or token in between should not be parsed, eg OPTION BASE 1
        # note we don't include leading signs, they're encoded as unary operators
        # number starting with . or & are always parsed
        elif c in ('&', '.') or (allow_number and not allow_jumpnum and c in ascii_digits):
            representation.tokenise_number(ins, outs)
        # operator keywords ('+', '-', '=', '/', '\\', '^', '*', '<', '>'):    
        elif c in ascii_operators: 
            ins.read(1)
            # operators don't affect line number mode- can do line number arithmetic and RENUM will do the strangest things
            # this allows for 'LIST 100-200' etc.
            outs.write(keyword_to_token[c])    
            allow_number = True
        # special case ' -> :REM'
        elif c == "'":
            ins.read(1)
            rem = True
            outs.write(':\x8F\xD9')
        # special case ? -> PRINT 
        elif c == '?':
            ins.read(1)
            outs.write(keyword_to_token['PRINT'])
            allow_number = True
        # keywords & variable names       
        elif c in ascii_uppercase:
            allow_jumpnum = False
            word = tokenise_word(ins, outs)
            # handle non-parsing modes
            if word in ('REM', "'") or debug and word=='DEBUG':  # note: DEBUG - this is not GW-BASIC behaviour
                rem = True
            elif word == "DATA":    
                data = True
            elif word in linenum_words: 
                allow_jumpnum = True
            # numbers can follow tokenised keywords (which does not include the word 'AS')
            allow_number = (word in keyword_to_token)
            if word in ('SPC(', 'TAB('):
                spc_or_tab = True
        else:
            ins.read(1)
            if c in (',', '#', ';'):
                # can separate numbers as well as jumpnums
                allow_number = True
            elif c in ('(', '['):
                allow_jumpnum, allow_number = False, True
            elif c == ')' and spc_or_tab:
                spc_or_tab = False
                allow_jumpnum, allow_number = False, True
            else:
                # replace all other nonprinting chars by spaces
                allow_jumpnum, allow_number = False, False
            outs.write(c if ord(c)>=32 else ' ')
    outs.seek(0)
    return outs
    
def tokenise_literal(ins, outs):
    # string literal
    outs.write(ins.read(1))
    outs.write(ascii_read_to(ins, ('', '\r', '\0', '"') ))
    if util.peek(ins)=='"':
        outs.write(ins.read(1))    
            
def tokenise_line_number(ins, outs): 
    linenum = tokenise_uint(ins)
    if linenum != '':    
        # terminates last line and fills up the first char in the buffer (that would be the magic number when written to file)
        # in direct mode, we'll know to expect a line number if the output starts with a  00
        outs.write('\x00')        
        # write line number. first two bytes are for internal use & can be anything nonzero; we use this.
        outs.write('\xC0\xDE' + linenum)
        # ignore single whitespace after line number, if any, unless line number is zero (as does GW)
        if util.peek(ins) == ' ' and linenum != '\x00\x00' :
            ins.read(1)
    else:
        # direct line; internally, we need an anchor for the program pointer, so we encode a ':'
        outs.write(':')
            
def tokenise_jump_number(ins, outs):
    word = tokenise_uint(ins)
    if word != '':
        outs.write('\x0e' + word)
    elif util.peek(ins) == '.':
        ins.read(1)
        outs.write('.')
    
def tokenise_uint(ins):
    word = bytearray()
    while True:
        c = ins.read(1)
        if c in ascii_digits + tokenise_whitespace:
            word += c
        else:    
            ins.seek(-len(c), 1)
            break
    # don't claim trailing w/s
    while len(word)>0 and chr(word[-1]) in tokenise_whitespace:
        del word[-1]        
        ins.seek(-1, 1)
    # remove all whitespace
    trimword = bytearray()
    for c in word:
        if chr(c) not in tokenise_whitespace:
            trimword += chr(c)
    word = trimword        
    # line number (jump)
    if len(word) > 0:
        if int(word) >= 65530:
            # note: anything >= 65530 is illegal in GW-BASIC
            # in loading an ASCII file, GWBASIC would interpret these as '6553 1' etcetera, generating a syntax error on load.
            # keep 6553 as line number and push back the last number:
            ins.seek(4-len(word), 1)
            word = word[:4]
        return str(vartypes.value_to_uint(int(word)))
    else:
        return ''    

def tokenise_word(ins, outs):
    word = ''
    while True: 
        c = ins.read(1).upper()
        word += c
        # special cases 'GO     TO' -> 'GOTO', 'GO SUB' -> 'GOSUB'    
        if word == 'GO':
            pos = ins.tell()
            # GO SUB allows 1 space
            if util.peek(ins, 4) == ' SUB':
                word = 'GOSUB'
                ins.read(4)
            else:
                # GOTO allows any number of spaces
                nxt = ins.read(1) 
                while nxt in tokenise_whitespace:
                    nxt = ins.read(1)
                if ins.read(2)=='TO':
                   word='GOTO'
                else:
                   ins.seek(pos)
            if word in ('GOTO', 'GOSUB'):
                nxt = util.peek(ins).upper()
                if nxt in name_chars:
                    ins.seek(pos)
                    word='GO'
                else:
                    pass
        if word in keyword_to_token:
            # ignore if part of a longer name, except 'FN', 'SPC(', 'TAB(', 'USR'
            if word not in ('FN', 'SPC(', 'TAB(', 'USR'):
                nxt = util.peek(ins).upper()
                if nxt in name_chars:  
                    continue
            token = keyword_to_token[word]
            # handle special case ELSE -> :ELSE
            if word == 'ELSE':
                outs.write('\x3a'+ token)
            # handle special case WHILE -> WHILE+
            elif word == 'WHILE':
                outs.write(token +'\xe9')
            else:
                outs.write(token)
            break
        # allowed names: letter + (letters, numbers, .)    
        elif not(c in name_chars): 
            if c!='':
                word = word[:-1]
                ins.seek(-1,1)
            outs.write(word)            
            break
    return word


#################################################################
#################################################################
#################################################################

token_to_keyword = {  
    '\x81': 'END',    '\x82': 'FOR',       '\x83': 'NEXT',   '\x84': 'DATA',  '\x85': 'INPUT',   '\x86': 'DIM',    '\x87': 'READ',  
    '\x88': 'LET',    '\x89': 'GOTO',      '\x8A': 'RUN',    '\x8B': 'IF',    '\x8C': 'RESTORE', '\x8D': 'GOSUB',  '\x8E': 'RETURN',  
    '\x8F': 'REM',    '\x90': 'STOP',      '\x91': 'PRINT',  '\x92': 'CLEAR', '\x93': 'LIST',    '\x94': 'NEW',    '\x95': 'ON',  
    '\x96': 'WAIT',   '\x97': 'DEF',       '\x98': 'POKE',   '\x99': 'CONT',  '\x9C': 'OUT',     '\x9D': 'LPRINT', '\x9E': 'LLIST',  
    '\xA0': 'WIDTH',  '\xA1': 'ELSE',      '\xA2': 'TRON',   '\xA3': 'TROFF', '\xA4': 'SWAP',    '\xA5': 'ERASE',  '\xA6': 'EDIT',  
    '\xA7': 'ERROR',  '\xA8': 'RESUME',    '\xA9': 'DELETE', '\xAA': 'AUTO',  '\xAB': 'RENUM',   '\xAC': 'DEFSTR', '\xAD': 'DEFINT',  
    '\xAE': 'DEFSNG', '\xAF': 'DEFDBL',    '\xB0': 'LINE',   '\xB1': 'WHILE', '\xB2': 'WEND',    '\xB3': 'CALL',   '\xB7': 'WRITE',  
    '\xB8': 'OPTION', '\xB9': 'RANDOMIZE', '\xBA': 'OPEN',   '\xBB': 'CLOSE', '\xBC': 'LOAD',    '\xBD': 'MERGE',  '\xBE': 'SAVE',      
    '\xBF': 'COLOR',  '\xC0': 'CLS',       '\xC1': 'MOTOR',  '\xC2': 'BSAVE', '\xC3': 'BLOAD',   '\xC4': 'SOUND',  '\xC5': 'BEEP',
    '\xC6': 'PSET',   '\xC7': 'PRESET',    '\xC8': 'SCREEN', '\xC9': 'KEY',   '\xCA': 'LOCATE',  '\xCC': 'TO',     '\xCD': 'THEN',  
    '\xCE': 'TAB(',   '\xCF': 'STEP',      '\xD0': 'USR',    '\xD1': 'FN',    '\xD2': 'SPC(',    '\xD3': 'NOT',    '\xD4': 'ERL',
    '\xD5': 'ERR',    '\xD6': 'STRING$',   '\xD7': 'USING',  '\xD8': 'INSTR', '\xD9': "'",       '\xDA': 'VARPTR', '\xDB': 'CSRLIN',  
    '\xDC': 'POINT',  '\xDD': 'OFF',       '\xDE': 'INKEY$', '\xE6': '>',     '\xE7': '=',       '\xE8': '<',      '\xE9': '+', 
    '\xEA': '-',      '\xEB': '*',         '\xEC': '/',      '\xED': '^',     '\xEE': 'AND',     '\xEF': 'OR',     '\xF0': 'XOR',  
    '\xF1': 'EQV',    '\xF2': 'IMP',       '\xF3': 'MOD',    '\xF4': '\\',
    '\xFD\x81': 'CVI',    '\xFD\x82': 'CVS',     '\xFD\x83': 'CVD',   '\xFD\x84': 'MKI$',    '\xFD\x85': 'MKS$',  '\xFD\x86': 'MKD$',
    '\xFD\x8B': 'EXTERR', '\xFE\x81': 'FILES',   '\xFE\x82': 'FIELD', '\xFE\x83': 'SYSTEM',  '\xFE\x84': 'NAME',  '\xFE\x85': 'LSET',  
    '\xFE\x86': 'RSET',   '\xFE\x87': 'KILL',    '\xFE\x88': 'PUT',   '\xFE\x89': 'GET',     '\xFE\x8A': 'RESET', '\xFE\x8B': 'COMMON',
    '\xFE\x8C': 'CHAIN',  '\xFE\x8D': 'DATE$',   '\xFE\x8E': 'TIME$', '\xFE\x8F': 'PAINT',   '\xFE\x90': 'COM',   '\xFE\x91': 'CIRCLE', 
    '\xFE\x92': 'DRAW',   '\xFE\x93': 'PLAY',    '\xFE\x94': 'TIMER', '\xFE\x95': 'ERDEV',   '\xFE\x96': 'IOCTL', '\xFE\x97': 'CHDIR', 
    '\xFE\x98': 'MKDIR',  '\xFE\x99': 'RMDIR',   '\xFE\x9A': 'SHELL', '\xFE\x9B': 'ENVIRON', '\xFE\x9C': 'VIEW',  '\xFE\x9D': 'WINDOW',
    '\xFE\x9E': 'PMAP',   '\xFE\x9F': 'PALETTE', '\xFE\xA0': 'LCOPY', '\xFE\xA1': 'CALLS',   '\xFE\xA5': 'PCOPY', 
    '\xFE\xA7': 'LOCK',   '\xFE\xA8': 'UNLOCK',  '\xFF\x81': 'LEFT$', '\xFF\x82': 'RIGHT$',  '\xFF\x83': 'MID$',  '\xFF\x84': 'SGN',    
    '\xFF\x85': 'INT',    '\xFF\x86': 'ABS',     '\xFF\x87': 'SQR',   '\xFF\x88': 'RND',     '\xFF\x89': 'SIN',   '\xFF\x8A': 'LOG',   
    '\xFF\x8B': 'EXP',    '\xFF\x8C': 'COS',     '\xFF\x8D': 'TAN',   '\xFF\x8E': 'ATN',     '\xFF\x8F': 'FRE',   '\xFF\x90': 'INP',   
    '\xFF\x91': 'POS',    '\xFF\x92': 'LEN',     '\xFF\x93': 'STR$',  '\xFF\x94': 'VAL',     '\xFF\x95': 'ASC',   '\xFF\x96': 'CHR$',   
    '\xFF\x97': 'PEEK',   '\xFF\x98': 'SPACE$',  '\xFF\x99': 'OCT$',  '\xFF\x9A': 'HEX$',    '\xFF\x9B': 'LPOS',  '\xFF\x9C': 'CINT',  
    '\xFF\x9D': 'CSNG',   '\xFF\x9E': 'CDBL',    '\xFF\x9F': 'FIX',   '\xFF\xA0': 'PEN',     '\xFF\xA1': 'STICK', '\xFF\xA2': 'STRIG',  
    '\xFF\xA3': 'EOF',    '\xFF\xA4': 'LOC',     '\xFF\xA5': 'LOF'          
}
    
keyword_to_token = dict((reversed(item) for item in token_to_keyword.items()))

def init_DEBUG(on=False):
    global debug
    # Note - I have implemented this as my own debugging command, executes python string.
    debug = on
    if on:
        token_to_keyword['\xFE\xA4'] = 'DEBUG'
        keyword_to_token['DEBUG'] = '\xFE\xA4'
        


# other keywords documented on http://www.chebucto.ns.ca/~af380/GW-BASIC-tokens.html :

# PCjr only:
#   0xFEA4: 'NOISE' 
#   0xFEA6: 'TERM'
# The site also remarks - 0xFEA5: PCOPY (PCjr or EGA system only) 
# Apparently I have an 'EGA system', as this keyword is in the GW-BASIC 3.23 documentation.

# Sperry PC only:
#   0xFEA4: 'DEBUG'

# Undefined tokens:
#   0x9A,  0x9B,  0x9F,  0xB4,  0xB5,  0xB6,  0xCB,  0xDF,  0xE0,  0xE1,  0xE2
#   0xE3,  0xE4,  0xE5,  0xF5,  0xF6,  0xF7,  0xF8,  0xF9,  0xFA,  0xFB,  0xFC

