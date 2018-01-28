"""
PC-BASIC - formatter.py
Formatted output handling

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ..base import codestream
from ..base import error
from ..base import tokens as tk
from .. import values


class Formatter(object):
    """Output string formatter."""

    def __init__(self, output, screen=None):
        """Initialise."""
        self._screen = screen
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
        format_expr = values.next_string(args)
        if format_expr == '':
            raise error.BASICError(error.IFC)
        fors = codestream.CodeStream(format_expr)
        newline, format_chars = True, False
        start_cycle = True
        initial_literal = ''
        try:
            while True:
                c = fors.peek()
                if c == '':
                    if not format_chars:
                        # avoid infinite loop
                        break
                    # loop the format string if more variables to come
                    start_cycle = True
                    initial_literal = ''
                    fors.seek(0)
                elif c == '_':
                    # escape char; write next char in fors or _ if this is the last char
                    if start_cycle:
                        initial_literal += fors.read(2)[-1]
                    else:
                        self._output.write(fors.read(2)[-1])
                else:
                    try:
                        format_field = StringField(fors)
                    except ValueError:
                        try:
                            format_field = NumberField(fors)
                        except ValueError:
                            if start_cycle:
                                initial_literal += fors.read(1)
                            else:
                                self._output.write(fors.read(1))
                            continue
                    value = next(args)
                    if value is None:
                        newline = False
                        break
                    if start_cycle:
                        self._output.write(initial_literal)
                        start_cycle = False
                        format_chars = True
                    self._output.write(format_field.format(value))
        except StopIteration:
            pass
        if not format_chars:
            self._output.write(initial_literal)
            # there were no format chars in the string, illegal fn call
            raise error.BASICError(error.IFC)
        return newline


##############################################################################
# formatting functions and format string parsers

class StringField(object):
    """String Formatter for PRINT USING."""

    def __init__(self, fors):
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
                    raise ValueError()
        if not word:
            raise ValueError()
        self._string_field = word

    def format(self, value):
        """Format a string."""
        s = values.pass_string(value)
        if self._string_field == '&':
            s = s.to_str()
        else:
            s = s.to_str().ljust(len(self._string_field))[:len(self._string_field)]
        return s

class NumberField(object):
    """Number formatter for PRINT USING."""

    def __init__(self, fors):
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
                raise ValueError()
            if c == '*':
                digits_before += 2
                if fors.peek() == '$':
                    word += fors.read(1)
            else:
                digits_before += 1
        # number field
        c = fors.peek()
        dot = (c == '.')
        comma = False
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
                        if c == ',':
                            comma = True
                else:
                    break
        if digits_before + decimals == 0:
            fors.seek(-len(word), 1)
            raise ValueError()
        # post characters
        if fors.peek(4) == '^^^^':
            word += fors.read(4)
        if not leading_plus and fors.peek() in ('-', '+'):
            word += fors.read(1)
        self._tokens, self._digits_before, self._decimals, self._comma = word, digits_before, decimals, comma

    def format(self, value):
        """Format a number to a format string."""
        value = values.pass_number(value)
        tokens = self._tokens
        digits_before = self._digits_before
        decimals = self._decimals
        comma = self._comma
        # promote ints to single
        value = value.to_float()
        # illegal function call if too many digits
        if digits_before + decimals > 24:
            raise error.BASICError(error.IFC)
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
        # take absolute value
        # NOTE: this could overflow for Integer -32768
        # but we convert to Float before calling format_number
        value = value.clone().iabs()
        # currency sign, if any
        valstr += '$' if has_dollar else ''
        # format to string
        if '^' in tokens:
            valstr += value.to_str_scientific(digits_before, decimals, force_dot, comma)
        else:
            valstr += value.to_str_fixed(decimals, force_dot, comma)
        # trailing signs, if any
        valstr += post_sign
        if len(valstr) > len(tokens):
            valstr = '%' + valstr
        else:
            # filler
            valstr = valstr.rjust(len(tokens), '*' if '*' in tokens else ' ')
        return valstr
