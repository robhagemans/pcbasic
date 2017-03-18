"""
PC-BASIC - formatter.py
Formatted output handling

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from .base import codestream
from .base import error
from .base import tokens as tk
from . import values


class Formatter(object):
    """Output string formatter."""

    def __init__(self, output, memory, screen=None):
        """Initialise."""
        self._screen = screen
        self._memory = memory
        self._output = output

    def format(self, args):
        """PRINT: Write expressions to screen or file."""
        newline = True
        for sep, value in args:
            if sep == tk.USING:
                newline = self._print_using(args)
                break
            elif sep == ',':
                self._print_comma()
            elif sep == ';':
                pass
            elif sep == tk.SPC:
                self._print_spc(values.to_int(value, unsigned=True))
            elif sep == tk.TAB:
                self._print_tab(values.to_int(value, unsigned=True))
            else:
                with self._memory.strings:
                    self._print_value(next(args))
            newline = sep not in (tk.TAB, tk.SPC, ',', ';')
        if newline:
            if self._screen and self._screen.overflow:
                self._output.write_line()
            self._output.write_line()

    def _print_value(self, expr):
        """Print a value."""
        # numbers always followed by a space
        if isinstance(expr, values.Number):
            word = values.to_repr(expr, leading_space=True, type_sign=False) + ' '
        else:
            word = expr.to_str()
        # output file (devices) takes care of width management; we must send a whole string at a time for this to be correct.
        self._output.write(word)

    def _print_comma(self):
        """Skip to next output zone."""
        number_zones = max(1, int(self._output.width/14))
        next_zone = int((self._output.col-1) / 14) + 1
        if next_zone >= number_zones and self._output.width >= 14 and self._output.width != 255:
            self._output.write_line()
        else:
            self._output.write(' ' * (1 + 14*next_zone-self._output.col), can_break=False)

    def _print_spc(self, num):
        """Print SPC separator."""
        numspaces = max(0, num) % self._output.width
        self._output.write(' ' * numspaces, can_break=False)

    def _print_tab(self, num):
        """Print TAB separator."""
        pos = max(0, num - 1) % self._output.width + 1
        if pos < self._output.col:
            self._output.write_line()
            self._output.write(' ' * (pos-1))
        else:
            self._output.write(' ' * (pos-self._output.col), can_break=False)

    def _print_using(self, args):
        """PRINT USING clause: Write expressions to screen or file using a formatting string."""
        format_expr = self._memory.strings.next_temporary(args)
        if format_expr == '':
            raise error.RunError(error.IFC)
        fors = FormatParser(format_expr)
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
                    self._output.write(fors.read(2)[-1])
                else:
                    with self._memory.strings:
                        string_field = fors._get_string_tokens()
                        if not string_field:
                            number_field = fors._get_number_tokens()
                        if string_field or number_field:
                            format_chars = True
                            value = next(args)
                            if value is None:
                                newline = False
                                break
                        if string_field:
                            s = values.pass_string(value)
                            if string_field == '&':
                                self._output.write(s)
                            else:
                                self._output.write(s[:len(string_field)] + ' '*(len(string_field)-len(s)))
                        elif number_field:
                            num = values.pass_number(value)
                            self._output.write(_format_number(num, *number_field))
                        else:
                            self._output.write(fors.read(1))
        except StopIteration:
            pass
        if not format_chars:
            # there were no format chars in the string, illegal fn call
            raise error.RunError(error.IFC)
        return newline


class FormatParser(codestream.CodeStream):
    """Format string parser."""

    def _get_string_tokens(self):
        """Get consecutive string-related formatting tokens."""
        word = ''
        c = self.peek()
        if c in ('!', '&'):
            word += self.read(1)
        elif c == '\\':
            word += self.read(1)
            # count the width of the \ \ token;
            # only spaces allowed and closing \ is necessary
            while True:
                c = self.read(1)
                word += c
                if c == '\\':
                    break
                elif c != ' ': # can be empty as well
                    self.seek(-len(word), 1)
                    return ''
        return word

    def _get_number_tokens(self):
        """Get consecutive number-related formatting tokens."""
        word, digits_before, decimals = '', 0, 0
        # + comes first
        leading_plus = (self.peek() == '+')
        if leading_plus:
            word += self.read(1)
        # $ and * combinations
        c = self.peek()
        if c in ('$', '*'):
            word += self.read(2)
            if word[-1] != c:
                self.seek(-len(word), 1)
                return None
            if c == '*':
                digits_before += 2
                if self.peek() == '$':
                    word += self.read(1)
            else:
                digits_before += 1
        # number field
        c = self.peek()
        dot = (c == '.')
        comma = False
        if dot:
            word += self.read(1)
        if c in ('.', '#'):
            while True:
                c = self.peek()
                if not dot and c == '.':
                    word += self.read(1)
                    dot = True
                elif c == '#' or (not dot and c == ','):
                    word += self.read(1)
                    if dot:
                        decimals += 1
                    else:
                        digits_before += 1
                        if c == ',':
                            comma = True
                else:
                    break
        if digits_before + decimals == 0:
            self.seek(-len(word), 1)
            return None
        # post characters
        if self.peek(4) == '^^^^':
            word += self.read(4)
        if not leading_plus and self.peek() in ('-', '+'):
            word += self.read(1)
        return word, digits_before, decimals, comma


##############################################################################
# formatting functions

def _format_number(value, tokens, digits_before, decimals, comma):
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
        valstr += _format_float_scientific(value, digits_before, decimals, force_dot, comma)
    else:
        valstr += _format_float_fixed(value, decimals, force_dot, comma)
    # trailing signs, if any
    valstr += post_sign
    if len(valstr) > len(tokens):
        valstr = '%' + valstr
    else:
        # filler
        valstr = ('*' if '*' in tokens else ' ') * (len(tokens) - len(valstr)) + valstr
    return valstr

def _format_float_scientific(expr, n_before, n_decimals, force_dot, comma):
    """Put a float in scientific format."""
    n_work = min(expr.digits, n_before + n_decimals)
    if expr.is_zero():
        if not force_dot:
            if expr.exp_sign == 'E':
                return 'E+00'
            return '0D+00'  # matches GW output. odd, odd, odd
        digitstr = '0' * (n_before + n_decimals)
        exp10 = 0
    else:
        # special case when work_digits == 0, see also below
        # setting to 0 results in incorrect rounding (why?)
        mantissa, exp10 = expr.to_decimal(1 if n_work == 0 else n_work)
        digitstr = values.get_digits(mantissa, n_work, remove_trailing=True)
        # append zeros if necessary
        digitstr += '0' * (n_decimals + n_before - len(digitstr))
    # this is just to reproduce GW results for no digits:
    # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
    if n_work == 0:
        exp10 += 1
    exp10 += n_before + n_decimals - 1
    return values.scientific_notation(digitstr, exp10, expr.exp_sign, digits_to_dot=n_before, force_dot=force_dot, group_digits=comma)

def _format_float_fixed(expr, n_decimals, force_dot, comma):
    """Put a float in fixed-point representation."""
    # convert to integer_mantissa * 10**exponent
    mantissa, exp10 = expr.to_decimal()
    # -exp10 is the number of digits after the radix point
    n_after = -exp10
    # bring to decimal form of working precision
    if n_after > n_decimals:
        n_work = expr.digits - (n_after - n_decimals)
        # this has n_work or n_work+1 digits, depending on rounding
        mantissa, exp10 = expr.to_decimal(n_work)
        n_after = -exp10
    digitstr = str(abs(mantissa))
    # number of digits before the radix point.
    n_before = len(digitstr) - n_after
    # fill up with zeros to required number of figures
    digitstr += '0' * (n_decimals - n_after)
    return values.decimal_notation(digitstr, n_before-1, type_sign='', force_dot=force_dot, group_digits=comma)
