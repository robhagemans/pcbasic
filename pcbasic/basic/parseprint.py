"""
PC-BASIC - parseprint.py
Formatted output handling

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from . import codestream
from . import values
from . import error
from . import tokens as tk


def write_(parser, ins):
    """WRITE: Output machine-readable expressions to the screen or a file."""
    outstr = ''
    expr = parser.parse_expression(ins, allow_empty=True)
    if expr is not None:
        while True:
            if isinstance(expr, values.String):
                with parser.temp_string:
                    outstr += '"' + expr.to_str() + '"'
            else:
                outstr += values.to_repr(expr, leading_space=False, type_sign=False)
            if ins.skip_blank_read_if((',', ';')):
                outstr += ','
            else:
                break
            expr = parser.parse_expression(ins)
    return outstr

def print_(parser, ins, output):
    """PRINT: Write expressions to screen or file."""
    number_zones = max(1, int(output.width/14))
    newline = True
    while True:
        d = ins.skip_blank()
        if d == tk.USING:
            ins.read(1)
            newline = print_using_(parser, ins, output)
            break
        elif d in tk.END_STATEMENT:
            break
        elif d in (',', ';', tk.SPC, tk.TAB):
            ins.read(1)
            newline = False
            if d == ',':
                next_zone = int((output.col-1) / 14) + 1
                if next_zone >= number_zones and output.width >= 14 and output.width != 255:
                    output.write_line()
                else:
                    output.write(' ' * (1 + 14*next_zone-output.col), can_break=False)
            elif d == tk.SPC:
                numspaces = max(0, values.to_int(parser.parse_expression(ins), unsigned=True)) % output.width
                ins.require_read((')',))
                output.write(' ' * numspaces, can_break=False)
            elif d == tk.TAB:
                pos = max(0, values.to_int(parser.parse_expression(ins), unsigned=True) - 1) % output.width + 1
                ins.require_read((')',))
                if pos < output.col:
                    output.write_line()
                    output.write(' ' * (pos-1))
                else:
                    output.write(' ' * (pos-output.col), can_break=False)
        else:
            newline = True
            with parser.temp_string:
                expr = parser.parse_expression(ins)
                # numbers always followed by a space
                if isinstance(expr, values.Number):
                    word = values.to_repr(expr, leading_space=True, type_sign=False) + ' '
                else:
                    word = expr.to_str()
            # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
            output.write(word)
    return newline

def print_using_(parser, ins, output):
    """PRINT USING: Write expressions to screen or file using a formatting string."""
    format_expr = parser.parse_temporary_string(ins)
    if format_expr == '':
        raise error.RunError(error.IFC)
    ins.require_read((';',))
    fors = codestream.CodeStream(format_expr)
    semicolon, format_chars = False, False
    while True:
        data_ends = ins.skip_blank() in tk.END_STATEMENT
        c = fors.peek()
        if c == '':
            if not format_chars:
                # there were no format chars in the string, illegal fn call (avoids infinite loop)
                raise error.RunError(error.IFC)
            if data_ends:
                break
            # loop the format string if more variables to come
            fors.seek(0)
        elif c == '_':
            # escape char; write next char in fors or _ if this is the last char
            output.write(fors.read(2)[-1])
        else:
            string_field = _get_string_tokens(fors)
            if string_field:
                if not data_ends:
                    s = parser.parse_temporary_string(ins)
                    if string_field == '&':
                        output.write(s)
                    else:
                        output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
            else:
                number_field, digits_before, decimals = _get_number_tokens(fors)
                if number_field:
                    if not data_ends:
                        num = values.pass_number(parser.parse_expression(ins))
                        output.write(_format_number(num, number_field, digits_before, decimals))
                else:
                    output.write(fors.read(1))
            if string_field or number_field:
                format_chars = True
                semicolon = ins.skip_blank_read_if((';', ','))
    return not semicolon

def _get_string_tokens(fors):
    """Get consecutive string-related formatting tokens."""
    word = ''
    c = fors.peek()
    if c in ('!', '&'):
        word += fors.read(1)
    elif c == '\\':
        word += fors.read(1)
        # count the width of the \ \ token;
        # only spaces allowed and closing \ is necessary
        while True:
            c = fors.read(1)
            word += c
            if c == '\\':
                break
            elif c != ' ': # can be empty as well
                fors.seek(-len(word), 1)
                return ''
    return word

def _get_number_tokens(fors):
    """Get consecutive number-related formatting tokens."""
    word, digits_before, decimals = '', 0, 0
    # + comes first
    leading_plus = (fors.peek() == '+')
    if leading_plus:
        word += fors.read(1)
    # $ and * combinations
    c = fors.peek()
    if c in ('$', '*'):
        word += fors.read(2)
        if word[-1] != c:
            fors.seek(-len(word), 1)
            return '', 0, 0
        if c == '*':
            digits_before += 2
            if fors.peek() == '$':
                word += fors.read(1)
        else:
            digits_before += 1
    # number field
    c = fors.peek()
    dot = (c == '.')
    if dot:
        word += fors.read(1)
    if c in ('.', '#'):
        while True:
            c = fors.peek()
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
    if fors.peek(4) == '^^^^':
        word += fors.read(4)
    if not leading_plus and fors.peek() in ('-', '+'):
        word += fors.read(1)
    return word, digits_before, decimals


##############################################################################
# convert float to string representation

def _format_number(value, tokens, digits_before, decimals):
    """Format a number to a format string. For PRINT USING."""
    # promote ints to single
    value = value.to_float()
    # illegal function call if too many digits
    if digits_before + decimals > 24:
        raise error.RunError(error.IFC)
    # dollar sign, decimal point
    has_dollar, force_dot = '$' in tokens, '.' in tokens
    # leading sign, if any
    valstr, post_sign = '', ''
    neg = value.is_negative()
    if tokens[0] == '+':
        valstr += '-' if neg else '+'
    elif tokens[-1] == '+':
        post_sign = '-' if neg else '+'
    elif tokens[-1] == '-':
        post_sign = '-' if neg else ' '
    else:
        valstr += '-' if neg else ''
        # reserve space for sign in scientific notation by taking away a digit position
        if not has_dollar:
            digits_before -= 1
            if digits_before < 0:
                digits_before = 0
            # just one of those things GW does
            #if force_dot and digits_before == 0 and decimals != 0:
            #    valstr += '0'
    # take absolute value
    # NOTE: this could overflow for Integer -32768
    # but we convert to Float before calling format_number
    value = value.clone().iabs()
    # currency sign, if any
    valstr += '$' if has_dollar else ''
    # format to string
    if '^' in tokens:
        valstr += _format_float_scientific(value, digits_before, decimals, force_dot)
    else:
        valstr += _format_float_fixed(value, decimals, force_dot)
    # trailing signs, if any
    valstr += post_sign
    if len(valstr) > len(tokens):
        valstr = '%' + valstr
    else:
        # filler
        valstr = ('*' if '*' in tokens else ' ') * (len(tokens) - len(valstr)) + valstr
    return valstr

def _format_float_scientific(expr, digits_before, decimals, force_dot):
    """Put a float in scientific format."""
    work_digits = min(expr.digits, digits_before + decimals)
    if expr.is_zero():
        if not force_dot:
            if expr.exp_sign == 'E':
                return 'E+00'
            return '0D+00'  # matches GW output. odd, odd, odd
        digitstr = '0' * (digits_before + decimals)
        exp10 = 0
    else:
        # special case when work_digits == 0, see also below
        # setting to 0 results in incorrect rounding (why?)
        num, exp10 = expr.to_decimal(1 if work_digits == 0 else work_digits)
        digitstr = values.get_digits(num, work_digits, remove_trailing=True)
        if len(digitstr) < digits_before + decimals:
            digitstr += '0' * (digits_before + decimals - len(digitstr))
    # this is just to reproduce GW results for no digits:
    # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
    if work_digits == 0:
        exp10 += 1
    exp10 += digits_before + decimals - 1
    return values.scientific_notation(digitstr, exp10, expr.exp_sign, digits_to_dot=digits_before, force_dot=force_dot)

def _format_float_fixed(expr, decimals, force_dot):
    """Put a float in fixed-point representation."""
    num, exp10 = expr.to_decimal()
    # -exp10 is the number of digits after the radix point
    if -exp10 > decimals:
        nwork = expr.digits - (-exp10 - decimals)
        # bring to decimal form of working precision
        # this has nwork or nwork+1 digits, depending on rounding
        num, exp10 = expr.to_decimal(nwork)
    digitstr = str(abs(num))
    # number of digits before the radix point.
    nbefore = len(digitstr) + exp10
    # fill up with zeros to required number of figures
    digitstr += '0' * (decimals + exp10)
    return values.decimal_notation(
                digitstr, nbefore - 1,
                type_sign='', force_dot=force_dot)
