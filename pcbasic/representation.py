"""
PC-BASIC - representation.py
Convert between numbers and their string representations

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

from string import digits as ascii_digits
from string import hexdigits as ascii_hexits
from string import octdigits as ascii_octits

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import error
import util
import fp
from fp import Single, Double
from fp import from_bytes, unpack
from fp import mul, div, pow_int
import vartypes

import basictoken as tk


def value_to_str_keep(inp, screen=False, write=False, allow_empty_expression=False):
    """ Convert BASIC number to BASIC string. """
    # screen=False means in a program listing
    # screen=True is used for screen, str$ and sequential files
    if not inp:
        if allow_empty_expression:
            return ('$', '')
        else:
            raise error.RunError(error.STX)
    typechar = inp[0]
    if typechar == '$':
        return ('$', inp[1])
    elif typechar == '%':
        if screen and not write and vartypes.unpack_int(inp) >= 0:
            return ('$', ' ' + str(vartypes.unpack_int(inp)))
        else:
            return ('$', str(vartypes.unpack_int(inp)))
    elif typechar == '!':
        return ('$', float_to_str(fp.unpack(inp), screen, write) )
    elif typechar == '#':
        return ('$', float_to_str(fp.unpack(inp), screen, write) )
    else:
        raise error.RunError(error.STX)

# tokenised ints to python str

def uint_to_str(s):
    """ Convert unsigned int token to Python string. """
    return str(vartypes.uint_to_value(s))

def sint_to_str(s):
    """ Convert signed int token to Python string. """
    return str(vartypes.sint_to_value(s))

def ubyte_to_str(s):
    """ Convert unsigned byte token to Python string. """
    return str(s[0])

def hex_to_str(s):
    """ Convert hex token to Python string. """
    return "&H" + hex(vartypes.uint_to_value(s))[2:].upper()

def oct_to_str(s):
    """ Convert oct token to Python string. """
    return "&O" + oct(vartypes.uint_to_value(s))[1:]



# floating point to string

# for to_str
# for numbers, tab and LF are whitespace
ascii_whitespace = ' \t\n'
# these seem to lead to a zero outcome all the time
kill_char = '\x1c\x1d\x1f'

# string representations

Single.lim_top = from_bytes(bytearray('\x7f\x96\x18\x98')) # 9999999, highest float less than 10e+7
Single.lim_bot = from_bytes(bytearray('\xff\x23\x74\x94')) # 999999.9, highest float  less than 10e+6
Single.type_sign, Single.exp_sign = '!', 'E'

Double.lim_top = from_bytes(bytearray('\xff\xff\x03\xbf\xc9\x1b\x0e\xb6')) # highest float less than 10e+16
Double.lim_bot = from_bytes(bytearray('\xff\xff\x9f\x31\xa9\x5f\x63\xb2')) # highest float less than 10e+15
Double.type_sign, Double.exp_sign = '#', 'D'


def just_under(n_in):
    """ Return the largest floating-point number less than the given value. """
    # decrease mantissa by one (leaving carry unchanged)
    return n_in.__class__(n_in.neg, n_in.man - 0x100, n_in.exp)

def get_digits(num, digits, remove_trailing=True):
    """ Get the digits for an int. """
    pow10 = 10L**(digits-1)
    digitstr = ''
    while pow10 >= 1:
        digit = ord('0')
        while num >= pow10:
            digit += 1
            num -= pow10
        digitstr += chr(digit)
        pow10 /= 10
    if remove_trailing:
        # remove trailing zeros
        while len(digitstr)>1 and digitstr[-1] == '0':
            digitstr = digitstr[:-1]
    return digitstr

def scientific_notation(digitstr, exp10, exp_sign='E', digits_to_dot=1, force_dot=False):
    """ Put digits in scientific E-notation. """
    valstr = digitstr[:digits_to_dot]
    if len(digitstr) > digits_to_dot:
        valstr += '.' + digitstr[digits_to_dot:]
    elif len(digitstr) == digits_to_dot and force_dot:
        valstr += '.'
    exponent = exp10-digits_to_dot+1
    valstr += exp_sign
    if (exponent<0):
        valstr+= '-'
    else:
        valstr+= '+'
    valstr += get_digits(abs(exponent),2,False)
    return valstr

def decimal_notation(digitstr, exp10, type_sign='!', force_dot=False):
    """ Put digits in decimal notation. """
    valstr = ''
    # digits to decimal point
    exp10 += 1
    if exp10 >= len(digitstr):
        valstr += digitstr + '0'*(exp10-len(digitstr))
        if force_dot:
            valstr+='.'
        if not force_dot or type_sign=='#':
            valstr += type_sign
    elif exp10 > 0:
        valstr += digitstr[:exp10] + '.' + digitstr[exp10:]
        if type_sign=='#':
            valstr += type_sign
    else:
        valstr += '.' + '0'*(-exp10) + digitstr
        if type_sign=='#':
            valstr += type_sign
    return valstr

def float_to_str(n_in, screen=False, write=False):
    """ Convert BASIC float to Python string. """
    # screen=True (ie PRINT) - leading space, no type sign
    # screen='w' (ie WRITE) - no leading space, no type sign
    # default mode is for LIST
    # zero exponent byte means zero
    if n_in.is_zero():
        if screen and not write:
            valstr = ' 0'
        else:
            valstr = '0' + n_in.type_sign
        return valstr
    # print sign
    if n_in.neg:
        valstr = '-'
    else:
        if screen and not write:
            valstr = ' '
        else:
            valstr = ''
    mbf = n_in.copy()
    num, exp10 = mbf.bring_to_range(mbf.lim_bot, mbf.lim_top)
    digitstr = get_digits(num, mbf.digits)
    # exponent for scientific notation
    exp10 += mbf.digits-1
    if (exp10>mbf.digits-1 or len(digitstr)-exp10>mbf.digits+1):
        # use scientific notation
        valstr += scientific_notation(digitstr, exp10, n_in.exp_sign)
    else:
        # use decimal notation
        if screen or write:
            type_sign=''
        else:
            type_sign = n_in.type_sign
        valstr += decimal_notation(digitstr, exp10, type_sign)
    return valstr

def format_number(value, tokens, digits_before, decimals):
    """ Format a number to a format string. For PRINT USING. """
    # illegal function call if too many digits
    if digits_before + decimals > 24:
        raise error.RunError(error.IFC)
    # extract sign, mantissa, exponent
    value = unpack(value)
    # dollar sign, decimal point
    has_dollar, force_dot = '$' in tokens, '.' in tokens
    # leading sign, if any
    valstr, post_sign = '', ''
    if tokens[0] == '+':
        valstr += '-' if value.neg else '+'
    elif tokens[-1] == '+':
        post_sign = '-' if value.neg else '+'
    elif tokens[-1] == '-':
        post_sign = '-' if value.neg else ' '
    else:
        valstr += '-' if value.neg else ''
        # reserve space for sign in scientific notation by taking away a digit position
        if not has_dollar:
            digits_before -= 1
            if digits_before < 0:
                digits_before = 0
            # just one of those things GW does
            if force_dot and digits_before == 0 and decimals != 0:
                valstr += '0'
    # take absolute value
    value.neg = False
    # currency sign, if any
    valstr += '$' if has_dollar else ''
    # format to string
    if '^' in tokens:
        valstr += format_float_scientific(value, digits_before, decimals, force_dot)
    else:
        valstr += format_float_fixed(value, decimals, force_dot)
    # trailing signs, if any
    valstr += post_sign
    if len(valstr) > len(tokens):
        valstr = '%' + valstr
    else:
        # filler
        valstr = ('*' if '*' in tokens else ' ') * (len(tokens) - len(valstr)) + valstr
    return valstr

def format_float_scientific(expr, digits_before, decimals, force_dot):
    """ Put a float in scientific format. """
    work_digits = digits_before + decimals
    if work_digits > expr.digits:
        # decimal precision of the type
        work_digits = expr.digits
    if expr.is_zero():
        if not force_dot:
            if expr.exp_sign == 'E':
                return 'E+00'
            return '0D+00'  # matches GW output. odd, odd, odd
        digitstr, exp10 = '0'*(digits_before+decimals), 0
    else:
        if work_digits > 0:
            # scientific representation
            lim_bot = just_under(pow_int(expr.ten, work_digits-1))
        else:
            # special case when work_digits == 0, see also below
            # setting to 0.1 results in incorrect rounding (why?)
            lim_bot = expr.one.copy()
        lim_top = lim_bot.copy().imul10()
        num, exp10 = expr.bring_to_range(lim_bot, lim_top)
        digitstr = get_digits(num, work_digits)
        if len(digitstr) < digits_before + decimals:
            digitstr += '0' * (digits_before + decimals - len(digitstr))
    # this is just to reproduce GW results for no digits:
    # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
    if work_digits == 0:
        exp10 += 1
    exp10 += digits_before + decimals - 1
    return scientific_notation(digitstr, exp10, expr.exp_sign, digits_to_dot=digits_before, force_dot=force_dot)

def format_float_fixed(expr, decimals, force_dot):
    """ Put a float in fixed-point representation. """
    unrounded = mul(expr, pow_int(expr.ten, decimals)) # expr * 10**decimals
    num = unrounded.copy().iround()
    # find exponent
    exp10 = 1
    pow10 = pow_int(expr.ten, exp10) # pow10 = 10L**exp10
    while num.gt(pow10) or num.equals(pow10): # while pow10 <= num:
        pow10.imul10() # pow10 *= 10
        exp10 += 1
    work_digits = exp10 + 1
    diff = 0
    if exp10 > expr.digits:
        diff = exp10 - expr.digits
        num = div(unrounded, pow_int(expr.ten, diff)).iround()  # unrounded / 10**diff
        work_digits -= diff
    num = num.trunc_to_int()
    # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
    # fill up with zeros
    digitstr = get_digits(num, work_digits-1, remove_trailing=False) + ('0' * diff)
    return decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', force_dot)


##################################

def from_str(s, allow_nonnum = True):
    """ Return Float value for Python string. """
    found_sign = False
    found_point = False
    found_exp = False
    found_exp_sign = False
    exp_neg = False
    neg = False
    exp10 = 0
    exponent = 0
    mantissa = 0
    digits = 0
    zeros = 0
    is_double = False
    is_single = False
    for c in s:
        # ignore whitespace throughout (x = 1   234  56  .5  means x=123456.5 in gw!)
        if c in ascii_whitespace:   #(' ', '\t'):
            continue
        if c in kill_char:
            return Single.zero
        # find sign
        if (not found_sign):
            if c=='+':
                found_sign=True
                continue
            elif c=='-':
                found_sign=True
                neg=True
                continue
            else:
                # number has started, sign must be pos. parse chars below.
                found_sign=True
        # parse numbers and decimal points, until 'E' or 'D' is found
        if (not found_exp):
            if c >= '0' and c <= '9':
                mantissa *= 10
                mantissa += ord(c)-ord('0')
                if found_point:
                    exp10 -= 1
                # keep track of precision digits
                if mantissa != 0:
                    digits += 1
                    if found_point and c=='0':
                        zeros+=1
                    else:
                        zeros=0
                continue
            elif c=='.':
                found_point = True
                continue
            elif c.upper()=='E':
                found_exp = True
                continue
            elif c.upper()=='D':
                found_exp = True
                is_double = True
                continue
            elif c=='!':
                # makes it a single, even if more than eight digits specified
                is_single=True
                break
            elif c=='#':
                is_double = True
                break
            else:
                if allow_nonnum:
                    break
                else:
                    return None
        elif (not found_exp_sign):
            if c=='+':
                found_exp_sign = True
                continue
            elif c=='-':
                found_exp_sign = True
                exp_neg = True
                continue
            else:
                # number has started, sign must be pos. parse chars below.
                found_exp_sign = True
        if (c >= '0' and c <= '9'):
            exponent *= 10
            exponent += ord(c)-ord('0')
            continue
        else:
            if allow_nonnum:
                break
            else:
                return None
    if exp_neg:
        exp10 -= exponent
    else:
        exp10 += exponent
    # eight or more digits means double, unless single override
    if digits - zeros > 7 and not is_single:
        is_double = True
    cls = Double if is_double else Single
    mbf = cls(neg, mantissa * 0x100, cls.bias).normalise()
    while (exp10 < 0):
        mbf.idiv10()
        exp10 += 1
    while (exp10 > 0):
        mbf.imul10()
        exp10 -= 1
    mbf.normalise()
    return mbf


def str_to_type(word, type_char):
    """ Convert Python-string to requested type. """
    packed = vartypes.pack_string(bytearray(word))
    if type_char == '$':
        return packed
    else:
        try:
            return str_to_value_keep(packed, allow_nonnum=False)
        except AttributeError:
            return None
#####

def tokenise_number(ins, outs):
    """ Convert Python-string number representation to number token. """
    c = util.peek(ins)
    # handle hex or oct constants
    if not c:
        return
    elif c == '&':
        ins.read(1)
        nxt = util.peek(ins).upper()
        if nxt == 'H': # hex constant
            ins.read(1)
            word = ''
            while True:
                c = util.peek(ins).upper()
                if not c or c not in ascii_hexits:
                    break
                else:
                    word += ins.read(1).upper()
            val = int(word, 16) if word else 0
            outs.write(tk.T_HEX + str(vartypes.value_to_uint(val)))
        else: # nxt == 'O': # octal constant
            if nxt == 'O':
                ins.read(1)
            word = ''
            while True:
                c = util.peek(ins).upper()
                if not c or c not in ascii_octits:
                    break
                else:
                    word += ins.read(1).upper()
            val = int(word, 8) if word else 0
            outs.write(tk.T_OCT + str(vartypes.value_to_uint(val)))
    # handle other numbers
    # note GW passes signs separately as a token and only stores positive numbers in the program
    elif c in ascii_digits + '.+-':
        have_exp = False
        have_point = False
        word = ''
        while True:
            c = ins.read(1).upper()
            if not c:
                break
            elif c == '.' and not have_point and not have_exp:
                have_point = True
                word += c
            elif c in 'ED' and not have_exp:
                have_exp = True
                word += c
            elif c in '-+' and (not word or word[-1] in 'ED'):
                # must be first token or in exponent
                word += c
            elif c in ascii_digits:
                word += c
            elif c in ascii_whitespace:
                # we'll remove this later but need to keep it for now
                # so we can reposition the stream on removing trailing whitespace
                word += c
            elif c in '!#' and not have_exp:
                word += c
                break
            elif c == '%':
                # swallow a %, but break parsing
                break
            else:
                ins.seek(-1, 1)
                break
        # don't claim trailing whitespace, don't end in D or E
        while len(word)>0 and (word[-1] in ascii_whitespace + 'DE'):
            if word[-1] in 'DE':
                have_exp = False
            word = word[:-1]
            ins.seek(-1,1) # even if c==''
        # remove all internal whitespace
        trimword = ''
        for c in word:
            if c not in ascii_whitespace:
                trimword += c
        word = trimword
        # write out the numbers
        if len(word) == 1 and word in ascii_digits:
            # digit
            outs.write(chr(0x11+int(word)))
        elif not (have_exp or have_point or word[-1] in '!#') and int(word) <= 0x7fff and int(word) >= -0x8000:
            if int(word) <= 0xff and int(word)>=0:
                # one-byte constant
                outs.write(tk.T_BYTE + chr(int(word)))
            else:
                # two-byte constant
                outs.write(tk.T_INT + str(vartypes.value_to_sint(int(word))))
        else:
            mbf = str(from_str(word).to_bytes())
            if len(mbf) == 4:
                outs.write(tk.T_SINGLE + mbf)
            else:
                outs.write(tk.T_DOUBLE + mbf)
    else:
        ins.seek(-1, 1)


##########################################


def parse_value(ins):
    """ Token to value. """
    d = ins.read(1)
    # note that hex and oct strings are interpreted signed here, but unsigned the other way!
    try:
        length = tk.plus_bytes[d]
    except KeyError:
        length = 0
    val = bytearray(ins.read(length))
    if len(val) < length:
        # truncated stream
        raise error.RunError(error.STX)
    if d in (tk.T_OCT, tk.T_HEX, tk.T_INT):
        return ('%', val)
    elif d == tk.T_BYTE:
        return ('%', val + '\0')
    elif d >= tk.C_0 and d <= tk.C_10:
        return ('%', bytearray(chr(ord(d)-0x11) + '\0'))
    elif d == tk.T_SINGLE:
        return ('!', val)
    elif d == tk.T_DOUBLE:
        return ('#', val)
    return None

def str_to_value_keep(strval, allow_nonnum=True):
    """ Convert BASIC string to BASIC value. """
    if strval == ('$', ''):
        return vartypes.null['%']
    strval = str(vartypes.pass_string_unpack(strval))
    ins = StringIO(strval)
    outs = StringIO()
    # skip spaces and line feeds (but not NUL).
    util.skip(ins, (' ', '\n'))
    tokenise_number(ins, outs)
    outs.seek(0)
    value = parse_value(outs)
    if not allow_nonnum:
        if util.skip_white(ins) != '':
            # not everything has been parsed - error
            return None
    return value

def detokenise_number(ins, output):
    """ Convert number token to Python string. """
    s = ins.read(1)
    if s == tk.T_OCT:
        output += oct_to_str(bytearray(ins.read(2)))
    elif s == tk.T_HEX:
        output += hex_to_str(bytearray(ins.read(2)))
    elif s == tk.T_BYTE:
        output += ubyte_to_str(bytearray(ins.read(1)))
    elif s >= tk.C_0 and s < tk.C_10:
        output += chr(ord('0') + ord(s) - 0x11)
    elif s == tk.C_10:
        output += '10'
    elif s == tk.T_INT:
        output += sint_to_str(bytearray(ins.read(2)))
    elif s == tk.T_SINGLE:
        output += float_to_str(fp.Single.from_bytes(bytearray(ins.read(4))), screen=False, write=False)
    elif s == tk.T_DOUBLE:
        output += float_to_str(fp.Double.from_bytes(bytearray(ins.read(8))), screen=False, write=False)
    else:
        ins.seek(-len(s),1)
