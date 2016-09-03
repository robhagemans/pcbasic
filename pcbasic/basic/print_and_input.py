"""
PC-BASIC - print_and_input.py
Console I/O operations

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import util
from . import devices
from . import numbers
from . import error


class InputTextFile(devices.TextFileBase):
    """Handle INPUT from console."""

    # spaces do not separate numbers on console INPUT
    soft_sep = ''

    def __init__(self, line):
        """Initialise InputStream."""
        devices.TextFileBase.__init__(self, StringIO(line), 'D', 'I')


def input_console(editor, value_handler, prompt, readvar, newline):
    """Read a list of variables for INPUT."""
    # readvar is a list of (name, indices) tuples
    # we return a list of (name, indices, values) tuples
    while True:
        editor.screen.write(prompt)
        line = editor.wait_screenline(write_endl=newline)
        inputstream = InputTextFile(line)
        # read the values and group them and the separators
        values, seps = [], []
        for v in readvar:
            word, sep = inputstream.input_entry(v[0][-1], allow_past_end=True)
            value = value_handler.from_repr(word, allow_nonnum=False, typechar=v[0][-1])
            values.append(value)
            seps.append(sep)
        # last separator not empty: there were too many values or commas
        # earlier separators empty: there were too few values
        # empty values will be converted to zero by from_str
        # None means a conversion error occurred
        if (seps[-1] or '' in seps[:-1] or None in values):
            # good old Redo!
            editor.screen.write_line('?Redo from start')
        else:
            return [r + [v] for r, v in zip(readvar, values)]


########################################
# for PRINT USING

def get_string_tokens(fors):
    """Get consecutive string-related formatting tokens."""
    word = ''
    c = util.peek(fors)
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

def get_number_tokens(fors):
    """Get consecutive number-related formatting tokens."""
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



##############################################################################
# convert float to string representation

def format_number(value, tokens, digits_before, decimals):
    """Format a number to a format string. For PRINT USING."""
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
        digitstr = numbers.get_digits(num, work_digits, remove_trailing=True)
        if len(digitstr) < digits_before + decimals:
            digitstr += '0' * (digits_before + decimals - len(digitstr))
    # this is just to reproduce GW results for no digits:
    # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
    if work_digits == 0:
        exp10 += 1
    exp10 += digits_before + decimals - 1
    return numbers.scientific_notation(digitstr, exp10, expr.exp_sign, digits_to_dot=digits_before, force_dot=force_dot)

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
    return numbers.decimal_notation(
                digitstr, nbefore - 1,
                type_sign='', force_dot=force_dot)
