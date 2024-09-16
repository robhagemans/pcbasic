"""
PC-BASIC - formatter.py
Formatted output handling

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""
import inspect
from typing import TYPE_CHECKING
from typing import Union

from .. import values
from ..base import codestream
from ..base import error
from ..base import tokens as tk

if TYPE_CHECKING:
    from ..console import Console


class Formatter(object):
    """Output string formatter."""

    def __init__(self, output, console: Union[None, 'Console'] = None):
        """Initialise."""
        self._console = console
        self._output = output

    async def format(self, args):
        """PRINT: Write expressions to console or file."""
        newline = True
        async for sep, value in args:
            if sep == tk.USING:
                newline = await self._print_using(args)
                break
            elif sep == b',':
                await self._print_comma()
            elif sep == b';':
                pass
            elif sep == tk.SPC:
                await self._print_spc(values.to_int(value, unsigned=True))
            elif sep == tk.TAB:
                self._print_tab(values.to_int(value, unsigned=True))
            else:
                await self._print_value(await anext(args))
            newline = sep not in (tk.TAB, tk.SPC, b',', b';')
        if newline:
            if self._console and self._console.overflow:
                await self._output.write_line()
            await self._output.write_line()

    async def _print_value(self, expr):
        """Print a value."""
        # numbers always followed by a space
        if isinstance(expr, values.Number):
            word = values.to_repr(expr, leading_space=True, type_sign=False) + b' '
        else:
            word = expr.to_str()
        # output file (devices) takes care of width management;
        # we must send a whole string at a time for this to be correct.
        await self._output.write(word)

    async def _print_comma(self):
        """Skip to next output zone."""
        number_zones = max(1, int(self._output.width // 14))
        next_zone = int((self._output.col-1) // 14) + 1
        if next_zone >= number_zones and self._output.width >= 14 and self._output.width != 255:
            await self._output.write_line()
        else:
            await self._output.write(b' ' * (1 + 14*next_zone-self._output.col), can_break=False)

    async def _print_spc(self, num):
        """Print SPC separator."""
        numspaces = max(0, num) % self._output.width
        await self._output.write(b' ' * numspaces, can_break=False)

    def _print_tab(self, num):
        """Print TAB separator."""
        pos = max(0, num - 1) % self._output.width + 1
        if pos < self._output.col:
            self._output.write_line()
            self._output.write(b' ' * (pos-1))
        else:
            self._output.write(b' ' * (pos-self._output.col), can_break=False)

    async def _print_using(self, args):
        """PRINT USING clause: Write expressions to console or file using a formatting string."""
        format_expr = await values.next_string(args)
        if format_expr == b'':
            raise error.BASICError(error.IFC)
        fors = codestream.CodeStream(format_expr)
        newline, format_chars = True, False
        start_cycle = True
        initial_literal = b''
        try:
            while True:
                c = fors.peek()
                if c == b'':
                    if not format_chars:
                        # avoid infinite loop
                        break
                    # loop the format string if more variables to come
                    start_cycle = True
                    initial_literal = b''
                    fors.seek(0)
                elif c == b'_':
                    # escape char; write next char in fors or _ if this is the last char
                    if start_cycle:
                        initial_literal += fors.read(2)[-1:]
                    else:
                        await self._output.write(fors.read(2)[-1:])
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
                                await self._output.write(fors.read(1))
                            continue
                    format_chars = True
                    value = await anext(args)
                    if value is None:
                        newline = False
                        break
                    if start_cycle:
                        await self._output.write(initial_literal)
                        start_cycle = False
                    await self._output.write(format_field.format(value))
            # consume any remaining arguments / finish parser
            # noinspection PyStatementEffect
            (_ async for _ in args)
        except (StopIteration, StopAsyncIteration):
            pass
        if not format_chars:
            await self._output.write(initial_literal)
            # there were no format chars in the string, illegal fn call
            raise error.BASICError(error.IFC)
        return newline


##############################################################################
# formatting functions and format string parsers

class StringField(object):
    """String Formatter for PRINT USING."""

    def __init__(self, fors):
        """Get consecutive string-related formatting tokens."""
        word = b''
        c = fors.peek()
        if c in (b'!', b'&'):
            word += fors.read(1)
        elif c == b'\\':
            word += fors.read(1)
            # count the width of the \ \ token;
            # only spaces allowed and closing \ is necessary
            while True:
                c = fors.read(1)
                word += c
                if c == b'\\':
                    break
                elif c != b' ': # can be empty as well
                    fors.seek(-len(word), 1)
                    raise ValueError()
        if not word:
            raise ValueError()
        self._string_field = word

    def format(self, value):
        """Format a string."""
        s = values.pass_string(value)
        if self._string_field == b'&':
            s = s.to_str()
        else:
            s = s.to_str().ljust(len(self._string_field))[:len(self._string_field)]
        return s

class NumberField(object):
    """Number formatter for PRINT USING."""

    def __init__(self, fors):
        """Get consecutive number-related formatting tokens."""
        word, digits_before, decimals = b'', 0, 0
        # + comes first
        leading_plus = (fors.peek() == b'+')
        if leading_plus:
            word += fors.read(1)
        # $ and * combinations
        c = fors.peek()
        if c in (b'$', b'*'):
            word += fors.read(2)
            if word[-1:] != c:
                fors.seek(-len(word), 1)
                raise ValueError()
            if c == b'*':
                digits_before += 2
                if fors.peek() == b'$':
                    word += fors.read(1)
            else:
                digits_before += 1
        # number field
        c = fors.peek()
        dot = (c == b'.')
        comma = False
        if dot:
            word += fors.read(1)
        if c in (b'.', b'#'):
            while True:
                c = fors.peek()
                if not dot and c == b'.':
                    word += fors.read(1)
                    dot = True
                elif c == b'#' or (not dot and c == b','):
                    word += fors.read(1)
                    if dot:
                        decimals += 1
                    else:
                        digits_before += 1
                        if c == b',':
                            comma = True
                else:
                    break
        if digits_before + decimals == 0:
            fors.seek(-len(word), 1)
            raise ValueError()
        # post characters
        if fors.peek(4) == b'^^^^':
            word += fors.read(4)
        if not leading_plus and fors.peek() in (b'-', b'+'):
            word += fors.read(1)
        self._tokens, self._digits_before = word, digits_before
        self._decimals, self._comma = decimals, comma

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
        has_dollar, force_dot = b'$' in tokens, b'.' in tokens
        # leading sign, if any
        valstr, post_sign = b'', b''
        neg = value.is_negative()
        if tokens[:1] == b'+':
            valstr += b'-' if neg else b'+'
        elif tokens[-1:] == b'+':
            post_sign = b'-' if neg else b'+'
        elif tokens[-1:] == b'-':
            post_sign = b'-' if neg else b' '
        else:
            valstr += b'-' if neg else b''
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
        valstr += b'$' if has_dollar else b''
        # format to string
        if b'^' in tokens:
            # don't group thousands in scientific notation
            valstr += value.to_str_scientific(digits_before, decimals, force_dot)
        else:
            valstr += value.to_str_fixed(decimals, force_dot, comma)
        # trailing signs, if any
        valstr += post_sign
        # add leading zero before radix if there's space
        if len(valstr) < len(tokens):
            if valstr.startswith(b'.'):
                valstr = b'0' + valstr
            elif valstr.startswith(b'+.'):
                valstr = b'+0' + valstr[1:]
            elif valstr.startswith(b'-.'):
                valstr = b'-0' + valstr[1:]
        if len(valstr) > len(tokens):
            # number does not fit in field
            valstr = b'%' + valstr
        else:
            # filler
            valstr = valstr.rjust(len(tokens), b'*' if b'*' in tokens else b' ')
        return valstr
