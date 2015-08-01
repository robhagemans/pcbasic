"""
PC-BASIC - expressions.py
Expression parser

(c) 2013, 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from functools import partial
import logging
import string

import config
import fp
import vartypes
import representation
import rnd
import shell
import util
import error
import var
import devices
import graphics
import console
# for FRE() only
import program
import state
import machine
import timedate
import basictoken as tk

# binary operator priority, lowest index is tightest bound
# operators of the same priority are evaluated left to right
priority = (
    (tk.O_CARET,),
    (tk.O_TIMES, tk.O_DIV),
    (tk.O_INTDIV,),
    (tk.MOD,),
    (tk.O_PLUS, tk.O_MINUS),
    (tk.O_GT, tk.O_EQ, tk.O_LT,
     tk.O_GT + tk.O_EQ, tk.O_LT + tk.O_EQ, tk.O_LT + tk.O_GT),
    (tk.AND,),
    (tk.OR,),
    (tk.XOR,),
    (tk.EQV,),
    (tk.IMP,))

# flatten list
operator_tokens = [item for sublist in priority for item in sublist]
# command line option /d
# allow double precision math for ^, ATN, COS, EXP, LOG, SIN, SQR, and TAN
option_double = False
# enable pcjr/tandy syntax extensions
is_pcjr_syntax = False


def prepare():
    """ Initialise expressions module. """
    global option_double, is_pcjr_syntax
    is_pcjr_syntax = config.get('syntax') in ('pcjr', 'tandy')
    option_double = config.get('double')

def parse_expression(ins, allow_empty=False, empty_err=22):
    """ Compute the value of the expression at the current code pointer. """
    units, operators = [], []
    while True:
        d = util.skip_white(ins)
        if d in tk.end_expression:
            break
        units.append(parse_expr_unit(ins))
        d = util.skip_white(ins)
        # string lit breaks expression, number after string lit breaks expression, + or - doesnt (could be an operator...
        if d not in operator_tokens:
            break
        else:
            ins.read(1)
        if d in (tk.O_LT, tk.O_EQ, tk.O_GT):
            nxt = util.skip_white(ins)
            if nxt in (tk.O_LT, tk.O_EQ, tk.O_GT):
                ins.read(1)
                if d == nxt:
                    raise error.RunError(2)
                else:
                    d += nxt
                    if d[0] == tk.O_EQ:
                        # =>, =<
                        d = d[1] + d[0]
                    elif d == tk.O_GT + tk.O_LT: # ><
                        d = tk.O_LT + tk.O_GT
        operators.append(d)
    # empty expression is a syntax error (inside brackets) or Missing Operand (in an assignment) or ok (in print)
    # PRINT 1+      :err 22
    # Print (1+)    :err 2
    # print 1+)     :err 2
    if len(units) == 0:
        if allow_empty:
            return None
        else:
            if d in (')', ']'):
                ins.read(1) # for positioning of cursor in edit gadget
            # always 22 here now that the bracket is taken out?
            raise error.RunError(2 if d in (')', ']') else empty_err)
    if len(units) <= len(operators):
        if d in (')', ']'):
            ins.read(1)
        raise error.RunError(2 if d in (')', ']') else 22)
    return parse_operators(operators, units)

def parse_operators(operators, units):
    """ Parse the operator stack. """
    for current_priority in priority:
        pos = 0
        while pos < len(operators):
            if operators[pos] in current_priority:
                units[pos] = value_operator(operators[pos], units[pos], units[pos+1])
                del units[pos+1]
                del operators[pos]
            else:
                pos += 1
        if len(operators) == 0:
            break
    if len(operators) > 0:
        # unrecognised operator, syntax error
        raise error.RunError(2)
    return units[0]

def parse_expr_unit(ins):
    """ Compute the value of the expression unit at the current code pointer. """
    d = util.skip_white(ins)
    # string literal
    if d == '"':
        ins.read(1)
        output = bytearray()
        # while tokenised nmbers inside a string literal will be printed as tokenised numbers, they don't actually execute as such:
        # a \00 character, even if inside a tokenised number, will break a string literal (and make the parser expect a
        # line number afterwards, etc. We follow this.
        d = ins.read(1)
        while d not in tk.end_line + ('"',):
            output += d
            d = ins.read(1)
        if d == '\0':
            ins.seek(-1, 1)
        return vartypes.pack_string(output)
    # variable name
    elif d in string.ascii_uppercase:
        name, indices = get_var_or_array_name(ins)
        return var.get_var_or_array(name, indices)
    # number literals as ASCII are accepted in tokenised streams. only if they start with a figure (not & or .)
    # this happens e.g. after non-keywords like AS. They are not acceptable as line numbers.
    elif d in string.digits:
        outs = StringIO()
        representation.tokenise_number(ins, outs)
        outs.seek(0)
        return representation.parse_value(outs)
    # number literals
    elif d in tk.number:
        return representation.parse_value(ins)
    # gw-basic allows adding line numbers to numbers
    elif d == tk.T_UINT:
        return vartypes.pack_int(util.parse_jumpnum(ins))
    # brackets
    elif d == '(':
        return parse_bracket(ins)
    # single-byte tokens
    else:
        ins.read(1)
        if d == tk.INPUT:         return value_input(ins)
        elif d == tk.SCREEN:      return value_screen(ins)
        elif d == tk.USR:         return value_usr(ins)
        elif d == tk.FN:          return value_fn(ins)
        elif d == tk.NOT:         return value_not(ins)
        elif d == tk.ERL:         return value_erl(ins)
        elif d == tk.ERR:         return value_err(ins)
        elif d == tk.STRING:      return value_string(ins)
        elif d == tk.INSTR:       return value_instr(ins)
        elif d == tk.VARPTR:      return value_varptr(ins)
        elif d == tk.CSRLIN:      return value_csrlin(ins)
        elif d == tk.POINT:       return value_point(ins)
        elif d == tk.INKEY:       return value_inkey(ins)
        elif d == tk.O_PLUS:      return parse_expr_unit(ins)
        elif d == tk.O_MINUS:     return value_neg(ins)
        # two-byte tokens
        elif d == '\xFD':
            d += ins.read(1)
            if d == tk.CVI:       return value_cvi(ins)
            elif d == tk.CVS:     return value_cvs(ins)
            elif d == tk.CVD:     return value_cvd(ins)
            elif d == tk.MKI:     return value_mki(ins)
            elif d == tk.MKS:     return value_mks(ins)
            elif d == tk.MKD:     return value_mkd(ins)
            elif d == tk.EXTERR:  return value_exterr(ins)
        # two-byte tokens
        elif d == '\xFE':
            d += ins.read(1)
            if d == tk.DATE:      return value_date(ins)
            elif d == tk.TIME:    return value_time(ins)
            elif d == tk.PLAY:    return value_play(ins)
            elif d == tk.TIMER:   return value_timer(ins)
            elif d == tk.ERDEV:   return value_erdev(ins)
            elif d == tk.IOCTL:   return value_ioctl(ins)
            elif d == tk.ENVIRON: return value_environ(ins)
            elif d == tk.PMAP:    return value_pmap(ins)
        # two-byte tokens
        elif d == '\xFF':
            d += ins.read(1)
            if d == tk.LEFT:    return value_left(ins)
            elif d == tk.RIGHT: return value_right(ins)
            elif d == tk.MID:   return value_mid(ins)
            elif d == tk.SGN:   return value_sgn(ins)
            elif d == tk.INT:   return value_int(ins)
            elif d == tk.ABS:   return value_abs(ins)
            elif d == tk.SQR:   return value_sqr(ins)
            elif d == tk.RND:   return value_rnd(ins)
            elif d == tk.SIN:   return value_sin(ins)
            elif d == tk.LOG:   return value_log(ins)
            elif d == tk.EXP:   return value_exp(ins)
            elif d == tk.COS:   return value_cos(ins)
            elif d == tk.TAN:   return value_tan(ins)
            elif d == tk.ATN:   return value_atn(ins)
            elif d == tk.FRE:   return value_fre(ins)
            elif d == tk.INP:   return value_inp(ins)
            elif d == tk.POS:   return value_pos(ins)
            elif d == tk.LEN:   return value_len(ins)
            elif d == tk.STR:   return value_str(ins)
            elif d == tk.VAL:   return value_val(ins)
            elif d == tk.ASC:   return value_asc(ins)
            elif d == tk.CHR:   return value_chr(ins)
            elif d == tk.PEEK:  return value_peek(ins)
            elif d == tk.SPACE: return value_space(ins)
            elif d == tk.OCT:   return value_oct(ins)
            elif d == tk.HEX:   return value_hex(ins)
            elif d == tk.LPOS:  return value_lpos(ins)
            elif d == tk.CINT:  return value_cint(ins)
            elif d == tk.CSNG:  return value_csng(ins)
            elif d == tk.CDBL:  return value_cdbl(ins)
            elif d == tk.FIX:   return value_fix(ins)
            elif d == tk.PEN:   return value_pen(ins)
            elif d == tk.STICK: return value_stick(ins)
            elif d == tk.STRIG: return value_strig(ins)
            elif d == tk.EOF:   return value_eof(ins)
            elif d == tk.LOC:   return value_loc(ins)
            elif d == tk.LOF:   return value_lof(ins)
        else:
            return None

######################################################################
# expression parsing utility functions

def parse_bracket(ins):
    """ Compute the value of the bracketed expression. """
    util.require_read(ins, ('(',))
    # we need a Syntax error, not a Missing operand
    val = parse_expression(ins, empty_err=2)
    util.require_read(ins, (')',))
    return val

def parse_int_list(ins, size, err=5, allow_last_empty=False):
    """ Helper function: parse a list of integers. """
    exprlist = parse_expr_list(ins, size, err, allow_last_empty=allow_last_empty)
    return [(vartypes.pass_int_unpack(expr) if expr else None) for expr in exprlist]

def parse_expr_list(ins, size, err=5, separators=(',',), allow_last_empty=False):
    """ Helper function : parse a list of expressions. """
    output = []
    while True:
        output.append(parse_expression(ins, allow_empty=True))
        if not util.skip_white_read_if(ins, separators):
            break
    if len(output) > size:
        raise error.RunError(err)
    # can't end on a comma: Missing Operand
    if not allow_last_empty and output and output[-1] is None:
        raise error.RunError(22)
    while len(output) < size:
        output.append(None)
    return output

def parse_file_number(ins, file_mode='IOAR'):
    """ Helper function: parse a file number and retrieve the file object. """
    screen = None
    if util.skip_white_read_if(ins, ('#',)):
        number = vartypes.pass_int_unpack(parse_expression(ins))
        util.range_check(0, 255, number)
        screen = devices.get_file(number, file_mode)
        util.require_read(ins, (',',))
    return screen

def parse_file_number_opthash(ins):
    """ Helper function: parse a file number, with optional hash. """
    util.skip_white_read_if(ins, ('#',))
    number = vartypes.pass_int_unpack(parse_expression(ins))
    util.range_check(0, 255, number)
    return number

def get_var_or_array_name(ins):
    """ Helper function: parse a variable or array name. """
    name = util.get_var_name(ins)
    indices = []
    if util.skip_white_read_if(ins, ('[', '(')):
        # it's an array, read indices
        indices = parse_int_list(ins, 255, 9) # subscript out of range
        while len(indices) > 0 and indices[-1] is None:
            indices = indices[:-1]
        if None in indices:
            raise error.RunError(2)
        util.require_read(ins, (']', ')'))
    return name, indices

######################################################################
# conversion

def value_cvi(ins):
    """ CVI: return the int value of a byte representation. """
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 2:
        raise error.RunError(5)
    return vartypes.pack_int(vartypes.sint_to_value(cstr[:2]))

def value_cvs(ins):
    """ CVS: return the single-precision value of a byte representation. """
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 4:
        raise error.RunError(5)
    return ('!', cstr[:4])

def value_cvd(ins):
    """ CVD: return the double-precision value of a byte representation. """
    cstr =  vartypes.pass_string_unpack(parse_bracket(ins))
    if len(cstr) < 8:
        raise error.RunError(5)
    return ('#', cstr[:8])

def value_mki(ins):
    """ MKI$: return the byte representation of an int. """
    return vartypes.pack_string(vartypes.value_to_sint(vartypes.pass_int_unpack(parse_bracket(ins))))

def value_mks(ins):
    """ MKS$: return the byte representation of a single. """
    return vartypes.pack_string(vartypes.pass_single_keep(parse_bracket(ins))[1])

def value_mkd(ins):
    """ MKD$: return the byte representation of a double. """
    return vartypes.pack_string(vartypes.pass_double_keep(parse_bracket(ins))[1])

def value_cint(ins):
    """ CINT: convert a number to integer. """
    return vartypes.pass_int_keep(parse_bracket(ins))

def value_csng(ins):
    """ CSNG: convert a number to single. """
    return vartypes.pass_single_keep(parse_bracket(ins))

def value_cdbl(ins):
    """ CDBL: convert a number to double. """
    return vartypes.pass_double_keep(parse_bracket(ins))

def value_str(ins):
    """ STR$: string representation of a number. """
    s = vartypes.pass_number_keep(parse_bracket(ins))
    return representation.value_to_str_keep(s, screen=True)

def value_val(ins):
    """ VAL: number value of a string. """
    val = representation.str_to_value_keep(parse_bracket(ins))
    return val if val else vartypes.null['%']

def value_chr(ins):
    """ CHR$: character for ASCII value. """
    val = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 255, val)
    return vartypes.pack_string(bytearray(chr(val)))

def value_oct(ins):
    """ OCT$: octal representation of int. """
    # allow range -32768 to 65535
    val = vartypes.pass_int_unpack(parse_bracket(ins), 0xffff)
    return vartypes.pack_string(representation.oct_to_str(vartypes.value_to_sint(val))[2:])

def value_hex(ins):
    """ HEX$: hexadecimal representation of int. """
    # allow range -32768 to 65535
    val = vartypes.pass_int_unpack(parse_bracket(ins), 0xffff)
    return vartypes.pack_string(representation.hex_to_str(vartypes.value_to_sint(val))[2:])

######################################################################
# string maniulation

def value_len(ins):
    """ LEN: length of string. """
    return vartypes.pack_int(len(vartypes.pass_string_unpack(parse_bracket(ins))) )

def value_asc(ins):
    """ ASC: ordinal ASCII value of a character. """
    s = vartypes.pass_string_unpack(parse_bracket(ins))
    if not s:
        raise error.RunError(5)
    return vartypes.pack_int(s[0])

def value_instr(ins):
    """ INSTR: find substring in string. """
    util.require_read(ins, ('(',))
    big, small, n = '', '', 1
    s = parse_expression(ins, empty_err=2)
    if s[0] != '$':
        n = vartypes.pass_int_unpack(s)
        util.range_check(1, 255, n)
        util.require_read(ins, (',',))
        big = vartypes.pass_string_unpack(parse_expression(ins, allow_empty=True))
    else:
        big = vartypes.pass_string_unpack(s)
    util.require_read(ins, (',',))
    small = vartypes.pass_string_unpack(parse_expression(ins, allow_empty=True))
    util.require_read(ins, (')',))
    return vartypes.str_instr(big, small, n)

def value_mid(ins):
    """ MID$: get substring. """
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    start = vartypes.pass_int_unpack(parse_expression(ins))
    if util.skip_white_read_if(ins, (',',)):
        num = vartypes.pass_int_unpack(parse_expression(ins))
    else:
        num = len(s)
    util.require_read(ins, (')',))
    util.range_check(1, 255, start)
    util.range_check(0, 255, num)
    if num == 0 or start > len(s):
        return vartypes.null['$']
    start -= 1
    stop = start + num
    stop = min(stop, len(s))
    return vartypes.pack_string(s[start:stop])

def value_left(ins):
    """ LEFT$: get substring at the start of string. """
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    stop = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 255, stop)
    if stop == 0:
        return vartypes.null['$']
    stop = min(stop, len(s))
    return vartypes.pack_string(s[:stop])

def value_right(ins):
    """ RIGHT$: get substring at the end of string. """
    util.require_read(ins, ('(',))
    s = vartypes.pass_string_unpack(parse_expression(ins))
    util.require_read(ins, (',',))
    stop = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 255, stop)
    if stop == 0:
        return vartypes.null['$']
    stop = min(stop, len(s))
    return vartypes.pack_string(s[-stop:])

def value_string(ins):
    """ STRING$: repeat characters. """
    util.require_read(ins, ('(',))
    n, j = parse_expr_list(ins, 2)
    n = vartypes.pass_int_unpack(n)
    util.range_check(0, 255, n)
    if j[0] == '$':
        j = vartypes.unpack_string(j)
        util.range_check(1, 255, len(j))
        j = j[0]
    else:
        j = vartypes.pass_int_unpack(j)
        util.range_check(0, 255, j)
    util.require_read(ins, (')',))
    return vartypes.pack_string(bytearray(chr(j)*n))

def value_space(ins):
    """ SPACE$: repeat spaces. """
    num = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 255, num)
    return vartypes.pack_string(bytearray(' '*num))

######################################################################
# console functions

def value_screen(ins):
    """ SCREEN: get char or attribute at a location. """
    util.require_read(ins, ('(',))
    row, col, z = parse_int_list(ins, 3, 5)
    if row is None or col is None:
        raise error.RunError(5)
    if z is None:
        z = 0
    cmode = state.console_state.screen.mode
    util.range_check(1, cmode.height, row)
    if state.console_state.view_set:
        util.range_check(state.console_state.view_start, state.console_state.scroll_height, row)
    util.range_check(1, cmode.width, col)
    util.range_check(0, 255, z)
    util.require_read(ins, (')',))
    if z and not cmode.is_text_mode:
        return vartypes.null['%']
    else:
        return vartypes.pack_int(state.console_state.screen.apage.get_char_attr(row, col, z!=0))

def value_input(ins):
    """ INPUT$: get characters from the keyboard or a file. """
    util.require_read(ins, ('$',))
    util.require_read(ins, ('(',))
    num = vartypes.pass_int_unpack(parse_expression(ins))
    util.range_check(1, 255, num)
    infile = state.io_state.kybd_file
    if util.skip_white_read_if(ins, (',',)):
        infile = devices.get_file(parse_file_number_opthash(ins))
    util.require_read(ins, (')',))
    word = vartypes.pack_string(bytearray(infile.read_raw(num)))
    if len(word) < num:
        # input past end
        raise error.RunError(62)
    return word

def value_inkey(ins):
    """ INKEY$: get a character from the keyboard. """
    return vartypes.pack_string(bytearray(state.console_state.keyb.get_char()))

def value_csrlin(ins):
    """ CSRLIN: get the current screen row. """
    row, col = state.console_state.row, state.console_state.col
    if (col == state.console_state.screen.mode.width and
            state.console_state.overflow and
            row < state.console_state.scroll_height):
        # in overflow position, return row+1 except on the last row
        row += 1
    return vartypes.pack_int(row)

def value_pos(ins):
    """ POS: get the current screen column. """
    # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
    parse_bracket(ins)
    col = state.console_state.col
    if col == state.console_state.screen.mode.width and state.console_state.overflow:
        # in overflow position, return column 1.
        col = 1
    return vartypes.pack_int(col)

def value_lpos(ins):
    """ LPOS: get the current printer column. """
    num = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, num)
    printer = state.io_state.devices['LPT' + max(1, num) + ':']
    if printer.device_file:
        return vartypes.pack_int(printer.device_file.col)
    else:
        return vartypes.pack_int(1)

######################################################################
# file access

def value_loc(ins):
    """ LOC: get file pointer. """
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    util.range_check(0, 255, num)
    the_file = devices.get_file(num)
    return vartypes.pack_int(the_file.loc())

def value_eof(ins):
    """ EOF: get end-of-file. """
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    if num == 0:
        return vartypes.null['%']
    util.range_check(0, 255, num)
    the_file = devices.get_file(num, 'IR')
    return vartypes.bool_to_int_keep(the_file.eof())

def value_lof(ins):
    """ LOF: get length of file. """
    util.skip_white(ins)
    num = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    util.range_check(0, 255, num)
    the_file = devices.get_file(num)
    return vartypes.pack_int(the_file.lof() )


######################################################################
# env, time and date functions

def value_environ(ins):
    """ ENVIRON$: get environment string. """
    util.require_read(ins, ('$',))
    expr = parse_bracket(ins)
    if expr[0] == '$':
        return vartypes.pack_string(shell.get_env(vartypes.unpack_string(expr)))
    else:
        expr = vartypes.pass_int_unpack(expr)
        util.range_check(1, 255, expr)
        return vartypes.pack_string(shell.get_env_entry(expr))

def value_timer(ins):
    """ TIMER: get clock ticks since midnight. """
    # precision of GWBASIC TIMER is about 1/20 of a second
    return fp.pack(fp.div( fp.Single.from_int(timedate.timer_milliseconds()/50), fp.Single.from_int(20)))

def value_time(ins):
    """ TIME$: get current system time. """
    return vartypes.pack_string(timedate.get_time())

def value_date(ins):
    """ DATE$: get current system date. """
    return vartypes.pack_string(timedate.get_date())

#######################################################
# user-defined functions

def value_fn(ins):
    """ FN: get value of user-defined function. """
    fnname = util.get_var_name(ins)
    try:
        varnames, fncode = state.basic_state.functions[fnname]
    except KeyError:
        # undefined user function
        raise error.RunError(18)
    # save existing vars
    varsave = {}
    for name in varnames:
        if name in state.basic_state.variables:
            # copy the *value* - set_var is in-place it's safe for FOR loops
            varsave[name] = state.basic_state.variables[name][:]
    # read variables
    if util.skip_white_read_if(ins, ('(',)):
        exprs = parse_expr_list(ins, len(varnames), err=2)
        if None in exprs:
            raise error.RunError(2)
        for i in range(len(varnames)):
            var.set_var(varnames[i], exprs[i])
        util.require_read(ins, (')',))
    # execute the code
    fns = StringIO(fncode)
    fns.seek(0)
    value = parse_expression(fns)
    # restore existing vars
    for name in varsave:
        # re-assign the stored value
        state.basic_state.variables[name][:] = varsave[name]
    return value

###############################################################
# graphics

def value_point(ins):
    """ POINT: get pixel attribute at screen location. """
    util.require_read(ins, ('(',))
    lst = parse_expr_list(ins, 2, err=2)
    util.require_read(ins, (')',))
    if not lst[0]:
        raise error.RunError(2)
    screen = state.console_state.screen
    if not lst[1]:
        # single-argument version
        try:
            x, y = screen.drawing.last_point
            fn = vartypes.pass_int_unpack(lst[0])
            if fn == 0:
                return vartypes.pack_int(x)
            elif fn == 1:
                return vartypes.pack_int(y)
            elif fn == 2:
                fx, _ = screen.drawing.get_window_logical(x, y)
                return fp.pack(fx)
            elif fn == 3:
                _, fy = screen.drawing.get_window_logical(x, y)
                return fp.pack(fy)
        except AttributeError:
            return vartypes.null['%']
    else:
        # two-argument mode
        if screen.mode.is_text_mode:
            raise error.RunError(5)
        return vartypes.pack_int(screen.drawing.point(
                        (fp.unpack(vartypes.pass_single_keep(lst[0])),
                         fp.unpack(vartypes.pass_single_keep(lst[1])), False)))

def value_pmap(ins):
    """ PMAP: convert between logical and physical coordinates. """
    util.require_read(ins, ('(',))
    coord = parse_expression(ins)
    util.require_read(ins, (',',))
    mode = vartypes.pass_int_unpack(parse_expression(ins))
    util.require_read(ins, (')',))
    util.range_check(0, 3, mode)
    screen = state.console_state.screen
    if screen.mode.is_text_mode:
        return vartypes.null['%']
    if mode == 0:
        value, _ = screen.drawing.get_window_physical(fp.unpack(vartypes.pass_single_keep(coord)), fp.Single.zero)
        return vartypes.pack_int(value)
    elif mode == 1:
        _, value = screen.drawing.get_window_physical(fp.Single.zero, fp.unpack(vartypes.pass_single_keep(coord)))
        return vartypes.pack_int(value)
    elif mode == 2:
        value, _ = screen.drawing.get_window_logical(vartypes.pass_int_unpack(coord), 0)
        return fp.pack(value)
    elif mode == 3:
        _, value = screen.drawing.get_window_logical(0, vartypes.pass_int_unpack(coord))
        return fp.pack(value)

#####################################################################
# sound functions

def value_play(ins):
    """ PLAY: get length of music queue. """
    voice = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 255, voice)
    if not(is_pcjr_syntax and voice in (1, 2)):
        voice = 0
    return vartypes.pack_int(state.console_state.sound.queue_length(voice))

#####################################################################
# error functions

def value_erl(ins):
    """ ERL: get line number of last error. """
    return fp.pack(fp.Single.from_int(program.get_line_number(state.basic_state.errp)))

def value_err(ins):
    """ ERR: get error code of last error. """
    return vartypes.pack_int(state.basic_state.errn)

#####################################################################
# pen, stick and strig

def value_pen(ins):
    """ PEN: poll the light pen. """
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 9, fn)
    pen = state.console_state.pen.poll(fn)
    if pen is None or not state.basic_state.events.pen.enabled:
        # should return 0 or char pos 1 if PEN not ON
        pen = 1 if fn >= 6 else 0
    return vartypes.pack_int(pen)

def value_stick(ins):
    """ STICK: poll the joystick. """
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, fn)
    return vartypes.pack_int(state.console_state.stick.poll(fn))

def value_strig(ins):
    """ STRIG: poll the joystick fire button. """
    fn = vartypes.pass_int_unpack(parse_bracket(ins))
    # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
    util.range_check(0, 7, fn)
    return vartypes.bool_to_int_keep(state.console_state.stick.poll_trigger(fn))

#########################################################
# memory and machine

def value_fre(ins):
    """ FRE: get free memory and optionally collect garbage. """
    val = parse_bracket(ins)
    if val[0] == '$':
        # grabge collection if a string-valued argument is specified.
        var.collect_garbage()
    return fp.pack(fp.Single.from_int(var.fre()))

def value_peek(ins):
    """ PEEK: read memory location. """
    addr = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    if state.basic_state.protected and not state.basic_state.run_mode:
        raise error.RunError(5)
    return vartypes.pack_int(machine.peek(addr))

def value_varptr(ins):
    """ VARPTR, VARPTR$: get memory address for variable or FCB. """
    dollar = util.skip_white_read_if(ins, ('$',))
    util.require_read(ins, ('(',))
    if (not dollar) and util.skip_white(ins) == '#':
        filenum = parse_file_number_opthash(ins)
        var_ptr = machine.varptr_file(filenum)
    else:
        name, indices = get_var_or_array_name(ins)
        var_ptr = machine.varptr(name, indices)
    util.require_read(ins, (')',))
    if var_ptr < 0:
        raise error.RunError(5) # ill fn cll
    if dollar:
        return vartypes.pack_string(bytearray(chr(var.byte_size[name[-1]])) + vartypes.value_to_uint(var_ptr))
    else:
        return vartypes.pack_int(var_ptr)

def value_usr(ins):
    """ USR: get value of machine-code function; not implemented. """
    util.require_read(ins, tk.digit)
    parse_bracket(ins)
    logging.warning("USR() function not implemented.")
    return vartypes.null['%']

def value_inp(ins):
    """ INP: get value from machine port. """
    port = vartypes.pass_int_unpack(parse_bracket(ins), maxint=0xffff)
    return vartypes.pack_int(machine.inp(port))

def value_erdev(ins):
    """ ERDEV$: device error string; not implemented. """
    logging.warning("ERDEV or ERDEV$ function not implemented.")
    if util.skip_white_read_if(ins, ('$',)):
        return vartypes.null['$']
    else:
        return vartypes.null['%']

def value_exterr(ins):
    """ EXTERR: device error information; not implemented. """
    x = vartypes.pass_int_unpack(parse_bracket(ins))
    util.range_check(0, 3, x)
    logging.warning("EXTERR() function not implemented.")
    return vartypes.null['%']

def value_ioctl(ins):
    """ IOCTL$: read device control string response; not implemented. """
    util.require_read(ins, ('$',))
    util.require_read(ins, ('(',))
    num = parse_file_number_opthash(ins)
    util.require_read(ins, (')',))
    devices.get_file(num)
    logging.warning("IOCTL$() function not implemented.")
    raise error.RunError(5)

###########################################################
# option_double regulated single & double precision math

def value_unary(ins, fn):
    """ Return value of unary math function. """
    return fp.pack(fn(fp.unpack(vartypes.pass_float_keep(parse_bracket(ins), option_double))))

value_sqr = partial(value_unary, fn=fp.sqrt)
value_exp = partial(value_unary, fn=fp.exp)
value_sin = partial(value_unary, fn=fp.sin)
value_cos = partial(value_unary, fn=fp.cos)
value_tan = partial(value_unary, fn=fp.tan)
value_atn = partial(value_unary, fn=fp.atn)
value_log = partial(value_unary, fn=fp.log)

def value_rnd(ins):
    """ RND: get pseudorandom value. """
    if util.skip_white(ins) == '(':
        return rnd.get_random(fp.unpack(vartypes.pass_single_keep(parse_bracket(ins))))
    else:
        return rnd.get_random_int(1)

def value_abs(ins):
    """ ABS: get absolute value. """
    return vartypes.number_abs(vartypes.pass_number_keep(parse_bracket(ins)))

def value_int(ins):
    """ INT: get floor value. """
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    return inp if inp[0] == '%' else fp.pack(fp.unpack(inp).ifloor())

def value_sgn(ins):
    """ SGN: get sign. """
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    if inp[0] == '%':
        inp_int = vartypes.unpack_int(inp)
        return vartypes.pack_int(0 if inp_int==0 else (1 if inp_int > 0 else -1))
    else:
        return vartypes.pack_int(fp.unpack(inp).sign() )

def value_fix(ins):
    """ FIX: round towards zero. """
    inp = vartypes.pass_number_keep(parse_bracket(ins))
    if inp[0] == '%':
        return inp
    elif inp[0] == '!':
        # needs to be a float to avoid overflow
        return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int()))
    elif inp[0] == '#':
        return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int()))

def value_neg(ins):
    """ -: get negative value. """
    return vartypes.number_neg(vartypes.pass_number_keep(parse_expr_unit(ins)))

def value_not(ins):
    """ NOT: get two's complement NOT, -x-1. """
    return vartypes.pack_int(~vartypes.pass_int_unpack(parse_expr_unit(ins)))

# binary operators

def value_operator(op, left, right):
    """ Get value of binary operator expression. """
    if op == tk.O_CARET:
        return vcaret(left, right)
    elif op == tk.O_TIMES:
        return vtimes(left, right)
    elif op == tk.O_DIV:
        return vdiv(left, right)
    elif op == tk.O_INTDIV:
        return fp.pack(fp.div(fp.unpack(vartypes.pass_single_keep(left)).ifloor(),
                fp.unpack(vartypes.pass_single_keep(right)).ifloor()).apply_carry().ifloor())
    elif op == tk.MOD:
        numerator = vartypes.pass_int_unpack(right)
        if numerator == 0:
            # simulate division by zero
            return fp.pack(fp.div(fp.unpack(vartypes.pass_single_keep(left)).ifloor(),
                    fp.unpack(vartypes.pass_single_keep(right)).ifloor()).ifloor())
        return vartypes.pack_int(vartypes.pass_int_unpack(left) % numerator)
    elif op == tk.O_PLUS:
        return vplus(left, right)
    elif op == tk.O_MINUS:
        return vartypes.number_add(left, vartypes.number_neg(right))
    elif op == tk.O_GT:
        return vartypes.bool_to_int_keep(vartypes.gt(left,right))
    elif op == tk.O_EQ:
        return vartypes.bool_to_int_keep(vartypes.equals(left, right))
    elif op == tk.O_LT:
        return vartypes.bool_to_int_keep(not(vartypes.gt(left,right) or vartypes.equals(left, right)))
    elif op == tk.O_GT + tk.O_EQ:
        return vartypes.bool_to_int_keep(vartypes.gt(left,right) or vartypes.equals(left, right))
    elif op == tk.O_LT + tk.O_EQ:
        return vartypes.bool_to_int_keep(not vartypes.gt(left,right))
    elif op == tk.O_LT + tk.O_GT:
        return vartypes.bool_to_int_keep(not vartypes.equals(left, right))
    elif op == tk.AND:
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) & vartypes.pass_twoscomp(right) )
    elif op == tk.OR:
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) | vartypes.pass_twoscomp(right) )
    elif op == tk.XOR:
        return vartypes.twoscomp_to_int( vartypes.pass_twoscomp(left) ^ vartypes.pass_twoscomp(right) )
    elif op == tk.EQV:
        return vartypes.twoscomp_to_int( ~(vartypes.pass_twoscomp(left) ^ vartypes.pass_twoscomp(right)) )
    elif op == tk.IMP:
        return vartypes.twoscomp_to_int( (~vartypes.pass_twoscomp(left)) | vartypes.pass_twoscomp(right) )
    else:
        raise error.RunError(2)

def vcaret(left, right):
    """ Left^right. """
    if (left[0] == '#' or right[0] == '#') and option_double:
        return fp.pack( fp.power(fp.unpack(vartypes.pass_double_keep(left)), fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        if right[0] == '%':
            return fp.pack( fp.unpack(vartypes.pass_single_keep(left)).ipow_int(vartypes.unpack_int(right)) )
        else:
            return fp.pack( fp.power(fp.unpack(vartypes.pass_single_keep(left)), fp.unpack(vartypes.pass_single_keep(right))) )

def vtimes(left, right):
    """ Left*right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.unpack(vartypes.pass_double_keep(left)).imul(fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        return fp.pack( fp.unpack(vartypes.pass_single_keep(left)).imul(fp.unpack(vartypes.pass_single_keep(right))) )

def vdiv(left, right):
    """ Left/right. """
    if left[0] == '#' or right[0] == '#':
        return fp.pack( fp.div(fp.unpack(vartypes.pass_double_keep(left)), fp.unpack(vartypes.pass_double_keep(right))) )
    else:
        return fp.pack( fp.div(fp.unpack(vartypes.pass_single_keep(left)), fp.unpack(vartypes.pass_single_keep(right))) )

def vplus(left, right):
    """ Left+right. """
    if left[0] == '$':
        return vartypes.pack_string(vartypes.pass_string_unpack(left) + vartypes.pass_string_unpack(right))
    else:
        return vartypes.number_add(left, right)

prepare()
