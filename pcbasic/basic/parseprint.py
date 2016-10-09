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

def lprint_(devices, args):
    """LPRINT: Write expressions to printer LPT1."""
    _print_loop(devices, devices.lpt1_file, args)

def print_(files, args):
    """PRINT: Write expressions to the screen or a file."""
    # check for a file number
    file_number = next(args)
    if file_number is not None:
        output = files.get(file_number, 'OAR')
    else:
        # neither LPRINT not a file number: print to screen
        output = files.devices.scrn_file
    _print_loop(files.devices, output, args)

def _print_loop(devices, output, args):
    """PRINT: Write expressions to screen or file."""
    newline = True
    for d, value in args:
        if d == tk.USING:
            if value == '':
                raise error.RunError(error.IFC)
            newline = _print_using(output, value, args)
            break
        elif d == ',':
            newline = False
            _print_comma(output)
        elif d == ';':
            newline = False
        elif d == tk.SPC:
            newline = False
            _print_spc(output, value)
        elif d == tk.TAB:
            newline = False
            _print_tab(output, value)
        else:
            newline = True
            _print_value(output, value)
    if newline:
        if output == devices.scrn_file and output.screen.overflow:
            output.write_line()
        output.write_line()

def _print_value(output, expr):
    """Print a value."""
    # numbers always followed by a space
    if isinstance(expr, values.Number):
        word = values.to_repr(expr, leading_space=True, type_sign=False) + ' '
    else:
        word = expr.to_str()
    # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
    output.write(word)

def _print_comma(output):
    """Skip to next output zone."""
    number_zones = max(1, int(output.width/14))
    next_zone = int((output.col-1) / 14) + 1
    if next_zone >= number_zones and output.width >= 14 and output.width != 255:
        output.write_line()
    else:
        output.write(' ' * (1 + 14*next_zone-output.col), can_break=False)

def _print_spc(output, num):
    """Print SPC separator."""
    numspaces = max(0, num) % output.width
    output.write(' ' * numspaces, can_break=False)

def _print_tab(output, num):
    """Print TAB separator."""
    pos = max(0, num - 1) % output.width + 1
    if pos < output.col:
        output.write_line()
        output.write(' ' * (pos-1))
    else:
        output.write(' ' * (pos-output.col), can_break=False)

###############################################################################
# parse format string

def _print_using(output, format_expr, args):
    """PRINT USING: Write expressions to screen or file using a formatting string."""
    fors = codestream.CodeStream(format_expr)
    newline, format_chars = True, False
    try:
        while True:
            c = fors.peek()
            if c == '':
                if not format_chars:
                    # avoid infinite loop
                    break
                # loop the format string if more variables to come
                fors.seek(0)
            elif c == '_':
                # escape char; write next char in fors or _ if this is the last char
                output.write(fors.read(2)[-1])
            else:
                string_field = _get_string_tokens(fors)
                if not string_field:
                    number_field = _get_number_tokens(fors)
                if string_field or number_field:
                    format_chars = True
                    value = next(args)
                    if value is None:
                        newline = False
                        break
                if string_field:
                    s = values.pass_string(value)
                    if string_field == '&':
                        output.write(s)
                    else:
                        output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
                elif number_field:
                    num = values.pass_number(value)
                    output.write(_format_number(num, *number_field))
                else:
                    output.write(fors.read(1))
    except StopIteration:
        pass
    if not format_chars:
        # there were no format chars in the string, illegal fn call
        raise error.RunError(error.IFC)
    return newline

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
            return None
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
        return None
    # post characters
    if fors.peek(4) == '^^^^':
        word += fors.read(4)
    if not leading_plus and fors.peek() in ('-', '+'):
        word += fors.read(1)
    return word, digits_before, decimals


##############################################################################
# formatting functions

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
