"""
PC-BASIC - values.py
Types, values and conversions

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import string
import functools
import math

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import fp
from . import error
from . import util
from . import basictoken as tk


# BASIC types:
# Integer (%) - stored as two's complement, little-endian
# Single (!) - stored as 4-byte Microsoft Binary Format
# Double (#) - stored as 8-byte Microsoft Binary Format
# String ($) - stored as 1-byte length plus 2-byte pointer to string space

byte_size = {'$': 3, '%': 2, '!': 4, '#': 8}

def null(sigil):
    """Return null value for the given type."""
    return (sigil, bytearray(byte_size[sigil]))


def math_safe(fn):
    """Decorator to handle math errors."""
    def wrapped_fn(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except (ValueError, ArithmeticError) as e:
            return self._math_error_handler.handle(e)
    return wrapped_fn

class Values(object):
    """Handles BASIC strings and numbers."""

    def __init__(self, screen, string_space, double_math):
        """Setup values."""
        self._math_error_handler = MathErrorHandler(screen)
        self._strings = string_space
        # double-precision EXP, SIN, COS, TAN, ATN, LOG
        self._double_math = double_math

    ###########################################################################
    # string representation of numbers

    def str_to_number(self, strval, allow_nonnum=True):
        """Convert Python str to BASIC value."""
        ins = StringIO(strval)
        outs = StringIO()
        # skip spaces and line feeds (but not NUL).
        util.skip(ins, (' ', '\n'))
        self.tokenise_number(ins, outs)
        outs.seek(0)
        value = parse_value(outs)
        if not allow_nonnum and util.skip_white(ins) != '':
            # not everything has been parsed - error
            return None
        if not value:
            return null('%')
        return value

    #REFACTOR: stringspace should be a member of this class (init order problem with DataSegment)
    def str_to_type(self, typechar, word, stringspace):
        """convert result to requested type, be strict about non-numeric chars """
        if typechar == '$':
            return stringspace.store(word)
        else:
            return self.str_to_number(word, allow_nonnum=False)

    # this should not be in the interface but is quite entangled
    # REFACTOR 1) to produce a string return value rather than write to stream
    # REFACTOR 2) to util.read_numeric_string -> str_to_number
    def tokenise_number(self, ins, outs):
        """Convert Python-string number representation to number token."""
        c = util.peek(ins)
        if not c:
            return
        elif c == '&':
            # handle hex or oct constants
            ins.read(1)
            if util.peek(ins).upper() == 'H':
                # hex constant
                self._tokenise_hex(ins, outs)
            else:
                # octal constant
                self._tokenise_oct(ins, outs)
        elif c in string.digits + '.+-':
            # handle other numbers
            # note GW passes signs separately as a token
            # and only stores positive numbers in the program
            self._tokenise_dec(ins, outs)
        else:
            # why is this here?
            # this looks wrong but hasn't hurt so far
            ins.seek(-1, 1)

    def _tokenise_dec(self, ins, outs):
        """Convert decimal expression in Python string to number token."""
        have_exp = False
        have_point = False
        word = ''
        kill = False
        while True:
            c = ins.read(1).upper()
            if not c:
                break
            elif c in '\x1c\x1d\x1f':
                # ASCII separator chars invariably lead to zero result
                kill = True
            elif c == '.' and not have_point and not have_exp:
                have_point = True
                word += c
            elif c in 'ED' and not have_exp:
                # there's a special exception for number followed by EL or EQ
                # presumably meant to protect ELSE and maybe EQV ?
                if c == 'E' and util.peek(ins).upper() in ('L', 'Q'):
                    ins.seek(-1, 1)
                    break
                else:
                    have_exp = True
                    word += c
            elif c in '-+' and (not word or word[-1] in 'ED'):
                # must be first token or in exponent
                word += c
            elif c in string.digits:
                word += c
            elif c in number_whitespace:
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
        # ascii separators encountered: zero output
        if kill:
            word = '0'
        # don't claim trailing whitespace
        while len(word)>0 and (word[-1] in number_whitespace):
            word = word[:-1]
            ins.seek(-1,1) # even if c==''
        # remove all internal whitespace
        trimword = ''
        for c in word:
            if c not in number_whitespace:
                trimword += c
        word = trimword
        # write out the numbers
        if len(word) == 1 and word in string.digits:
            # digit
            outs.write(chr(0x11+str_to_int(word)))
        elif (not (have_exp or have_point or word[-1] in '!#') and
                                str_to_int(word) <= 0x7fff and str_to_int(word) >= -0x8000):
            if str_to_int(word) <= 0xff and str_to_int(word) >= 0:
                # one-byte constant
                outs.write(tk.T_BYTE + chr(str_to_int(word)))
            else:
                # two-byte constant
                outs.write(tk.T_INT + str(integer_to_bytes(int_to_integer_signed(str_to_int(word)))))
        else:
            mbf = str(self._str_to_float(word)[1])
            if len(mbf) == 4:
                outs.write(tk.T_SINGLE + mbf)
            else:
                outs.write(tk.T_DOUBLE + mbf)

    def _tokenise_hex(self, ins, outs):
        """Convert hex expression in Python string to number token."""
        # pass the H in &H
        ins.read(1)
        word = ''
        while True:
            c = util.peek(ins)
            # hex literals must not be interrupted by whitespace
            if not c or c not in string.hexdigits:
                break
            else:
                word += ins.read(1)
        val = int(word, 16) if word else 0
        outs.write(tk.T_HEX + str(integer_to_bytes(int_to_integer_unsigned(val))))

    def _tokenise_oct(self, ins, outs):
        """Convert octal expression in Python string to number token."""
        # O is optional, could also be &777 instead of &O777
        if util.peek(ins).upper() == 'O':
            ins.read(1)
        word = ''
        while True:
            c = util.peek(ins)
            # oct literals may be interrupted by whitespace
            if c and c in number_whitespace:
                ins.read(1)
            elif not c or c not in string.octdigits:
                break
            else:
                word += ins.read(1)
        val = int(word, 8) if word else 0
        outs.write(tk.T_OCT + str(integer_to_bytes(int_to_integer_unsigned(val))))

    def _str_to_float(self, s):
        """Return Float value for Python string."""
        allow_nonnum = True
        found_sign, found_point, found_exp = False, False, False
        found_exp_sign, exp_neg, neg = False, False, False
        exp10, exponent, mantissa, digits, zeros = 0, 0, 0, 0, 0
        is_double, is_single = False, False
        for c in s:
            # ignore whitespace throughout (x = 1   234  56  .5  means x=123456.5 in gw!)
            if c in number_whitespace:
                continue
            # determine sign
            if (not found_sign):
                found_sign = True
                # number has started; if no sign encountered here, sign must be pos.
                if c in '+-':
                    neg = (c == '-')
                    continue
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
                            zeros += 1
                        else:
                            zeros=0
                    continue
                elif c == '.':
                    found_point = True
                    continue
                elif c.upper() in 'DE':
                    found_exp = True
                    is_double = (c.upper() == 'D')
                    continue
                elif c == '!':
                    # makes it a single, even if more than eight digits specified
                    is_single = True
                    break
                elif c == '#':
                    is_double = True
                    break
                else:
                    if allow_nonnum:
                        break
                    return None
            # parse exponent
            elif (not found_exp_sign):
                # exponent has started; if no sign given, it must be pos.
                found_exp_sign = True
                if c in '+-':
                    exp_neg = (c == '-')
                    continue
            if (c >= '0' and c <= '9'):
                exponent *= 10
                exponent += ord(c) - ord('0')
                continue
            else:
                if allow_nonnum:
                    break
                return None
        if exp_neg:
            exp10 -= exponent
        else:
            exp10 += exponent
        # eight or more digits means double, unless single override
        if digits - zeros > 7 and not is_single:
            is_double = True
        return self._float_from_exp10(neg, mantissa, exp10, is_double)

    @math_safe
    def _float_from_exp10(self, neg, mantissa, exp10, is_double):
        """Create floating-point value from mantissa and decomal exponent."""
        cls = fp.Double if is_double else fp.Single
        # isn't this just cls.from_int(-mantissa if neg else mantissa)?
        mbf = cls(neg, mantissa * 0x100, cls.bias).normalise()
        # apply decimal exponent
        while (exp10 < 0):
            mbf.idiv10()
            exp10 += 1
        while (exp10 > 0):
            mbf.imul10()
            exp10 -= 1
        mbf.normalise()
        return fp.pack(mbf)

    ###########################################################################
    # type conversions

    @math_safe
    def pass_single(self, num):
        """Check if variable is numeric, convert to Single."""
        if not num:
            raise error.RunError(error.STX)
        typechar = num[0]
        if typechar == '!':
            return num
        elif typechar == '%':
            return fp.pack(fp.Single.from_int(integer_to_int_signed(num)))
        elif typechar == '#':
            return fp.pack(fp.unpack(num).round_to_single())
        elif typechar == '$':
            raise error.RunError(error.TYPE_MISMATCH)

    @math_safe
    def pass_double(self, num):
        """Check if variable is numeric, convert to Double."""
        if not num:
            raise error.RunError(error.STX)
        typechar = num[0]
        if typechar == '#':
            return num
        elif typechar == '%':
            return fp.pack(fp.Double.from_int(integer_to_int_signed(num)))
        elif typechar == '!':
            return ('#', bytearray(4) + num[1])
        elif typechar == '$':
            raise error.RunError(error.TYPE_MISMATCH)

    def pass_float(self, num, allow_double=True):
        """Check if variable is numeric, convert to Double or Single."""
        if num and num[0] == '#' and allow_double:
            return num
        else:
            return self.pass_single(num)

    def pass_most_precise(self, left, right, err=error.TYPE_MISMATCH):
        """Check if variables are numeric and convert to highest-precision."""
        left_type, right_type = left[0][-1], right[0][-1]
        if left_type=='#' or right_type=='#':
            return (self.pass_double(left), self.pass_double(right))
        elif left_type=='!' or right_type=='!':
            return (self.pass_single(left), self.pass_single(right))
        elif left_type=='%' or right_type=='%':
            return (pass_integer(left), pass_integer(right))
        else:
            raise error.RunError(err)

    def pass_type(self, typechar, value):
        """Check if variable can be converted to the given type and convert."""
        if typechar == '$':
            return pass_string(value)
        elif typechar == '%':
            return pass_integer(value)
        elif typechar == '!':
            return self.pass_single(value)
        elif typechar == '#':
            return self.pass_double(value)
        else:
            raise error.RunError(error.STX)


    ####################################
    # math functions

    @math_safe
    def _call_float_function(self, fn, *args):
        """Convert to IEEE 754, apply function, convert back."""
        args = [self.pass_float(arg, self._double_math) for arg in args]
        floatcls = fp.unpack(args[0]).__class__
        try:
            args = (fp.unpack(arg).to_value() for arg in args)
            return fp.pack(floatcls().from_value(fn(*args)))
        except ArithmeticError as e:
            # positive infinity
            raise e.__class__(floatcls.max.copy())

    def sqr(self, x):
        """Square root."""
        return self._call_float_function(math.sqrt, x)

    def exp(self, x):
        """Exponential."""
        return self._call_float_function(math.exp, x)

    def sin(self, x):
        """Sine."""
        return self._call_float_function(math.sin, x)

    def cos(self, x):
        """Cosine."""
        return self._call_float_function(math.cos, x)

    def tan(self, x):
        """Tangent."""
        return self._call_float_function(math.tan, x)

    def atn(self, x):
        """Inverse tangent."""
        return self._call_float_function(math.atan, x)

    def log(self, x):
        """Logarithm."""
        return self._call_float_function(math.log, x)

    ###########################################################################

    def sgn(self, x):
        """Sign."""
        x = pass_number(x)
        if x[0] == '%':
            inp_int = integer_to_int_signed(x)
            return int_to_integer_signed(0 if inp_int == 0 else (1 if inp_int > 0 else -1))
        else:
            return int_to_integer_signed(fp.unpack(x).sign())

    def floor(self, x):
        """Truncate towards negative infinity (INT)."""
        x = pass_number(x)
        return x if x[0] == '%' else fp.pack(fp.unpack(x).ifloor())

    def fix(self, x):
        """Truncate towards zero."""
        inp = pass_number(x)
        if inp[0] == '%':
            return inp
        elif inp[0] == '!':
            # needs to be a float to avoid overflow
            return fp.pack(fp.Single.from_int(fp.unpack(inp).trunc_to_int()))
        elif inp[0] == '#':
            return fp.pack(fp.Double.from_int(fp.unpack(inp).trunc_to_int()))


    ###############################################################################
    # numeric operators

    @math_safe
    def add(self, left, right):
        """Add two numbers."""
        left, right = self.pass_most_precise(left, right)
        if left[0] in ('#', '!'):
            return fp.pack(fp.unpack(left).iadd(fp.unpack(right)))
        else:
            # return Single to avoid wrapping on integer overflow
            return fp.pack(fp.Single.from_int(
                                integer_to_int_signed(left) +
                                integer_to_int_signed(right)))

    @math_safe
    def subtract(self, left, right):
        """Subtract two numbers."""
        return self.add(left, self.negate(right))

    def abs(self, inp):
        """Return the absolute value of a number. No-op for strings."""
        if inp[0] == '%':
            val = abs(integer_to_int_signed(inp))
            if val == 32768:
                return fp.pack(fp.Single.from_int(val))
            else:
                return int_to_integer_signed(val)
        elif inp[0] in ('!', '#'):
            out = (inp[0], inp[1][:])
            out[1][-2] &= 0x7F
            return out
        return inp

    @staticmethod
    def negate(inp):
        """Negation (unary -). No-op for strings."""
        if inp[0] == '%':
            val = -integer_to_int_signed(inp)
            if val == 32768:
                return fp.pack(fp.Single.from_int(val))
            else:
                return int_to_integer_signed(val)
        elif inp[0] in ('!', '#'):
            out = (inp[0], inp[1][:])
            out[1][-2] ^= 0x80
            return out
        return inp

    @math_safe
    def power(self, left, right):
        """Left^right."""
        if (left[0] == '#' or right[0] == '#') and self._double_math:
            return self._call_float_function(lambda a, b: a**b, self.pass_double(left), self.pass_double(right))
        else:
            if right[0] == '%':
                return fp.pack(fp.unpack(self.pass_single(left)).ipow_int(integer_to_int_signed(right)))
            else:
                return self._call_float_function(lambda a, b: a**b, self.pass_single(left), self.pass_single(right))

    @math_safe
    def multiply(self, left, right):
        """Left*right."""
        if left[0] == '#' or right[0] == '#':
            return fp.pack( fp.unpack(self.pass_double(left)).imul(fp.unpack(self.pass_double(right))) )
        else:
            return fp.pack( fp.unpack(self.pass_single(left)).imul(fp.unpack(self.pass_single(right))) )

    @math_safe
    def divide(self, left, right):
        """Left/right."""
        if left[0] == '#' or right[0] == '#':
            return fp.pack( fp.div(fp.unpack(self.pass_double(left)), fp.unpack(self.pass_double(right))) )
        else:
            return fp.pack( fp.div(fp.unpack(self.pass_single(left)), fp.unpack(self.pass_single(right))) )

    @math_safe
    def divide_int(self, left, right):
        """Left\\right."""
        dividend = pass_int_unpack(left)
        divisor = pass_int_unpack(right)
        if divisor == 0:
            # division by zero, return single-precision maximum
            raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
        if (dividend >= 0) == (divisor >= 0):
            return int_to_integer_signed(dividend / divisor)
        else:
            return int_to_integer_signed(-(abs(dividend) / abs(divisor)))

    @math_safe
    def mod(self, left, right):
        """Left modulo right."""
        divisor = pass_int_unpack(right)
        dividend = pass_int_unpack(left)
        if divisor == 0:
            # division by zero, return single-precision maximum
            raise ZeroDivisionError(fp.Single(dividend<0, fp.Single.max.man, fp.Single.max.exp))
        mod = dividend % divisor
        if dividend < 0 or mod < 0:
            mod -= divisor
        return int_to_integer_signed(mod)

    def bitwise_not(self, right):
        """Bitwise NOT, -x-1."""
        return int_to_integer_signed(-pass_int_unpack(right)-1)

    def bitwise_and(self, left, right):
        """Bitwise AND."""
        return int_to_integer_unsigned(
            integer_to_int_unsigned(pass_integer(left)) &
            integer_to_int_unsigned(pass_integer(right)))

    def bitwise_or(self, left, right):
        """Bitwise OR."""
        return int_to_integer_unsigned(
            integer_to_int_unsigned(pass_integer(left)) |
            integer_to_int_unsigned(pass_integer(right)))

    def bitwise_xor(self, left, right):
        """Bitwise XOR."""
        return int_to_integer_unsigned(
            integer_to_int_unsigned(pass_integer(left)) ^
            integer_to_int_unsigned(pass_integer(right)))

    def bitwise_eqv(self, left, right):
        """Bitwise equivalence."""
        return int_to_integer_unsigned(0xffff-(
            integer_to_int_unsigned(pass_integer(left)) ^
            integer_to_int_unsigned(pass_integer(right))))

    def bitwise_imp(self, left, right):
        """Bitwise implication."""
        return int_to_integer_unsigned(
            (0xffff - integer_to_int_unsigned(pass_integer(left))) |
            integer_to_int_unsigned(pass_integer(right)))


    ###############################################################################
    # string operations

    def concat(self, left, right):
        """Concatenate strings."""
        return self._strings.store(
            self._strings.copy(pass_string(left)) +
            self._strings.copy(pass_string(right)))


    ###############################################################################
    # number and string operations

    def _bool_eq(self, left, right):
        """Return true if left == right, false otherwise."""
        if left[0] == '$':
            return (self._strings.copy(pass_string(left)) ==
                    self._strings.copy(pass_string(right)))
        else:
            left, right = self.pass_most_precise(left, right)
            if left[0] in ('#', '!'):
                return fp.unpack(left).equals(fp.unpack(right))
            else:
                return integer_to_int_signed(left) == integer_to_int_signed(right)

    def _bool_gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        if left[0] == '$':
            left = self._strings.copy(pass_string(left))
            right = self._strings.copy(pass_string(right))
            shortest = min(len(left), len(right))
            for i in range(shortest):
                if left[i] > right[i]:
                    return True
                elif left[i] < right[i]:
                    return False
            # the same so far...
            # the shorter string is said to be less than the longer,
            # provided they are the same up till the length of the shorter.
            if len(left) > len(right):
                return True
            # left is shorter, or equal strings
            return False
        else:
            left, right = self.pass_most_precise(left, right)
            if left[0] in ('#', '!'):
                return fp.unpack(left).gt(fp.unpack(right))
            else:
                return integer_to_int_signed(left) > integer_to_int_signed(right)

    def equals(self, left, right):
        """Return -1 if left == right, 0 otherwise."""
        return bool_to_integer(self._bool_eq(left, right))

    def not_equals(self, left, right):
        """Return -1 if left != right, 0 otherwise."""
        return bool_to_integer(not self._bool_eq(left, right))

    def gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        return bool_to_integer(self._bool_gt(left, right))

    def gte(self, left, right):
        """Ordering: return -1 if left >= right, 0 otherwise."""
        return bool_to_integer(not self._bool_gt(right, left))

    def lte(self, left, right):
        """Ordering: return -1 if left <= right, 0 otherwise."""
        return bool_to_integer(not self._bool_gt(left, right))

    def lt(self, left, right):
        """Ordering: return -1 if left < right, 0 otherwise."""
        return bool_to_integer(self._bool_gt(right, left))

    def plus(self, left, right):
        """Binary + operator: add or concatenate."""
        if left[0] == '$':
            return self.concat(left, right)
        else:
            return self.add(left, right)

    ##########################################################################
    # conversion

    def cvi(self, x):
        """CVI: return the int value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 2)
        return bytes_to_integer(cstr[:2])

    def cvs(self, x):
        """CVS: return the single-precision value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 4)
        return ('!', bytearray(cstr[:4]))

    def cvd(self, x):
        """CVD: return the double-precision value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 8)
        return ('#', bytearray(cstr[:8]))

    def mki(self, x):
        """MKI$: return the byte representation of an int."""
        return self._strings.store(integer_to_bytes(pass_integer(x)))

    def mks(self, x):
        """MKS$: return the byte representation of a single."""
        return self._strings.store(self.pass_single(x)[1])

    def mkd(self, x):
        """MKD$: return the byte representation of a double."""
        return self._strings.store(self.pass_double(x)[1])

    def representation(self, x):
        """STR$: string representation of a number."""
        return self._strings.store(number_to_str(pass_number(x), screen=True))

    def val(self, x):
        """VAL: number value of a string."""
        return self.str_to_number(self._strings.copy(pass_string(x)))

    def character(self, x):
        """CHR$: character for ASCII value."""
        val = pass_int_unpack(x)
        error.range_check(0, 255, val)
        return self._strings.store(chr(val))

    def octal(self, x):
        """OCT$: octal representation of int."""
        # allow range -32768 to 65535
        val = pass_integer(x, 0xffff)
        return self._strings.store(integer_to_str_oct(val))

    def hexadecimal(self, x):
        """HEX$: hexadecimal representation of int."""
        # allow range -32768 to 65535
        val = pass_integer(x, 0xffff)
        return self._strings.store(integer_to_str_hex(val))


    ######################################################################
    # string manipulation

    def length(self, x):
        """LEN: length of string."""
        return int_to_integer_signed(string_length(pass_string(x)))

    def asc(self, x):
        """ASC: ordinal ASCII value of a character."""
        s = self._strings.copy(pass_string(x))
        error.throw_if(not s)
        return int_to_integer_signed(ord(s[0]))


class MathErrorHandler(object):
    """Handles floating point errors."""

    # types of errors that do not always interrupt execution
    soft_types = (error.OVERFLOW, error.DIVISION_BY_ZERO)

    def __init__(self, screen):
        """Setup handler."""
        self._screen = screen
        self._do_raise = False

    def pause_handling(self, do_raise):
        """Pause local handling of floating point errors."""
        self._do_raise = do_raise

    def handle(self, e):
        """Handle Overflow or Division by Zero."""
        if isinstance(e, ValueError):
            # math domain errors such as SQR(-1)
            math_error = error.IFC
        elif isinstance(e, OverflowError):
            math_error = error.OVERFLOW
        elif isinstance(e, ZeroDivisionError):
            math_error = error.DIVISION_BY_ZERO
        else:
            raise e
        if (self._do_raise or self._screen is None or
                math_error not in self.soft_types):
            # also raises exception in error_handle_mode!
            # in that case, prints a normal error message
            raise error.RunError(math_error)
        else:
            # write a message & continue as normal
            self._screen.write_line(error.RunError(math_error).message)
        # return max value for the appropriate float type
        if e.args and e.args[0] and isinstance(e.args[0], fp.Float):
            return fp.pack(e.args[0])
        return fp.pack(fp.Single.max.copy())


def number_to_str(inp, screen=False, write=False, allow_empty_expression=False):
    """Convert BASIC number to Python str."""
    # screen=False means in a program listing
    # screen=True is used for screen, str$ and sequential files
    if not inp:
        if allow_empty_expression:
            return ''
        else:
            raise error.RunError(error.STX)
    typechar = inp[0]
    if typechar == '%':
        if screen and not write and integer_to_int_signed(inp) >= 0:
            return ' ' + str(integer_to_int_signed(inp))
        else:
            return str(integer_to_int_signed(inp))
    elif typechar == '!':
        return float_to_str(fp.unpack(inp), screen, write)
    elif typechar == '#':
        return float_to_str(fp.unpack(inp), screen, write)
    else:
        raise ValueError('Number operation on string')


# tokenised ints to python str
#MOVE to tokenise

def uint_token_to_str(s):
    """Convert unsigned int token to Python string."""
    return str(integer_to_int_unsigned(bytes_to_integer(s)))

def int_token_to_str(s):
    """Convert signed int token to Python string."""
    return str(integer_to_int_signed(bytes_to_integer(s)))

def byte_token_to_str(s):
    """Convert unsigned byte token to Python string."""
    return str(bytearray(s)[0])

def hex_token_to_str(s):
    """Convert hex token to Python str."""
    return '&H' + integer_to_str_hex(bytes_to_integer(s))

def oct_token_to_str(s):
    """Convert oct token to Python str."""
    return '&O' + integer_to_str_oct(bytes_to_integer(s))

def integer_to_str_oct(inp):
    """Convert integer to str in octal representation."""
    if integer_to_int_unsigned(inp) == 0:
        return '0'
    else:
        return oct(integer_to_int_unsigned(inp))[1:]

def integer_to_str_hex(inp):
    """Convert integer to str in hex representation."""
    return hex(integer_to_int_unsigned(inp))[2:].upper()


# floating point to string

# for to_str
# for numbers, tab and LF are whitespace
number_whitespace = ' \t\n'

# string representations

fp.Single.lim_top = fp.from_bytes(bytearray('\x7f\x96\x18\x98')) # 9999999, highest float less than 10e+7
fp.Single.lim_bot = fp.from_bytes(bytearray('\xff\x23\x74\x94')) # 999999.9, highest float  less than 10e+6
fp.Single.type_sign, fp.Single.exp_sign = '!', 'E'

fp.Double.lim_top = fp.from_bytes(bytearray('\xff\xff\x03\xbf\xc9\x1b\x0e\xb6')) # highest float less than 10e+16
fp.Double.lim_bot = fp.from_bytes(bytearray('\xff\xff\x9f\x31\xa9\x5f\x63\xb2')) # highest float less than 10e+15
fp.Double.type_sign, fp.Double.exp_sign = '#', 'D'


def just_under(n_in):
    """Return the largest floating-point number less than the given value."""
    # decrease mantissa by one
    return n_in.__class__(n_in.neg, n_in.man - 0x100, n_in.exp)

def get_digits(num, digits, remove_trailing=True):
    """Get the digits for an int."""
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
    """Put digits in scientific E-notation."""
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
    """Put digits in decimal notation."""
    # digits to decimal point
    exp10 += 1
    if exp10 >= len(digitstr):
        valstr = digitstr + '0'*(exp10-len(digitstr))
        if force_dot:
            valstr+='.'
        if not force_dot or type_sign=='#':
            valstr += type_sign
    elif exp10 > 0:
        valstr = digitstr[:exp10] + '.' + digitstr[exp10:]
        if type_sign=='#':
            valstr += type_sign
    else:
        if force_dot:
            valstr = '0'
        else:
            valstr = ''
        valstr += '.' + '0'*(-exp10) + digitstr
        if type_sign=='#':
            valstr += type_sign
    return valstr

def float_to_str(n_in, screen=False, write=False):
    """Convert BASIC float to Python string."""
    # screen=True (ie PRINT) - leading space, no type sign
    # screen='w' (ie WRITE) - no leading space, no type sign
    # default mode is for LIST
    # zero exponent byte means zero
    if n_in.is_zero():
        if screen and not write:
            valstr = ' 0'
        elif write:
            valstr = '0'
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
    """Format a number to a format string. For PRINT USING."""
    # illegal function call if too many digits
    if digits_before + decimals > 24:
        raise error.RunError(error.IFC)
    # extract sign, mantissa, exponent
    value = fp.unpack(value)
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
            #if force_dot and digits_before == 0 and decimals != 0:
            #    valstr += '0'
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
    """Put a float in scientific format."""
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
            lim_bot = just_under(fp.pow_int(expr.ten, work_digits-1))
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
    """Put a float in fixed-point representation."""
    unrounded = fp.mul(expr, fp.pow_int(expr.ten, decimals)) # expr * 10**decimals
    num = unrounded.copy().iround()
    # find exponent
    exp10 = 1
    pow10 = fp.pow_int(expr.ten, exp10) # pow10 = 10L**exp10
    while num.gt(pow10) or num.equals(pow10): # while pow10 <= num:
        pow10.imul10() # pow10 *= 10
        exp10 += 1
    work_digits = exp10 + 1
    diff = 0
    if exp10 > expr.digits:
        diff = exp10 - expr.digits
        num = fp.div(unrounded, fp.pow_int(expr.ten, diff)).iround()  # unrounded / 10**diff
        work_digits -= diff
    num = num.trunc_to_int()
    # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
    # fill up with zeros
    digitstr = get_digits(num, work_digits-1, remove_trailing=False) + ('0' * diff)
    return decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', force_dot)


##################################


def str_to_int(s):
    """Return Python int value for Python str, zero if malformed."""
    try:
        return int(s)
    except ValueError:
        return 0

##########################################

#REFACTOR to util.read_full_token -> token_to_value
def parse_value(ins):
    """Token to value."""
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

#MOVE to tokenise
def detokenise_number(ins, output):
    """Convert number token to Python string."""
    s = ins.read(1)
    if s == tk.T_OCT:
        output += oct_token_to_str(ins.read(2))
    elif s == tk.T_HEX:
        output += hex_token_to_str(ins.read(2))
    elif s == tk.T_BYTE:
        output += byte_token_to_str(ins.read(1))
    elif s >= tk.C_0 and s < tk.C_10:
        output += chr(ord('0') + ord(s) - 0x11)
    elif s == tk.C_10:
        output += '10'
    elif s == tk.T_INT:
        output += int_token_to_str(ins.read(2))
    elif s == tk.T_SINGLE:
        output += float_to_str(fp.Single.from_bytes(bytearray(ins.read(4))), screen=False, write=False)
    elif s == tk.T_DOUBLE:
        output += float_to_str(fp.Double.from_bytes(bytearray(ins.read(8))), screen=False, write=False)
    else:
        ins.seek(-len(s),1)


###############################################################################


###############################################################################
# type checks

def pass_integer(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """Check if variable is numeric, convert to Int."""
    if not inp:
        raise error.RunError(error.STX)
    typechar = inp[0]
    if typechar == '%':
        return inp
    elif typechar in ('!', '#'):
        val = fp.unpack(inp).round_to_int()
        if val > maxint or val < -0x8000:
            # overflow
            raise error.RunError(error.OVERFLOW)
        return int_to_integer_unsigned(val)
    else:
        # type mismatch
        raise error.RunError(err)


def pass_string(inp, err=error.TYPE_MISMATCH):
    """Check if variable is String-valued."""
    if not inp:
        raise error.RunError(error.STX)
    if inp[0] == '$':
        return inp
    else:
        raise error.RunError(err)

def pass_number(inp, err=error.TYPE_MISMATCH):
    """Check if variable is numeric."""
    if inp[0] not in ('%', '!', '#'):
        raise error.RunError(err)
    return inp



###############################################################################
# convenience functions

#D
def pass_int_unpack(inp, maxint=0x7fff, err=error.TYPE_MISMATCH):
    """Convert numeric variable to Python integer."""
    return integer_to_int_signed(pass_integer(inp, maxint, err))


#D
def number_unpack(value):
    """Unpack a number value."""
    if value[0] in ('#', '!'):
        return fp.unpack(value)
    else:
        return integer_to_int_signed(value)

###############################################################################
# convert between BASIC Integer and token bytes

def bytes_to_integer(in_bytes):
    """Copy and convert token bytearray, list or str to BASIC integer."""
    return ('%', bytearray(in_bytes))

def integer_to_bytes(in_integer):
    """Copy and convert BASIC integer to token bytearray."""
    return bytearray(in_integer[1])


###############################################################################
# convert between BASIC String and token address bytes

def bytes_to_string(in_bytes):
    """Copy and convert token bytearray, list or str to BASIC string."""
    return ('$', bytearray(in_bytes))

def string_to_bytes(in_string):
    """Copy and convert BASIC string to token bytearray."""
    return bytearray(in_string[1])

def string_length(in_string):
    """Get string length as Python int."""
    return in_string[1][0]

def string_address(in_string):
    """Get string address as Python int."""
    return integer_to_int_unsigned(bytes_to_integer(in_string[1][1:]))


###############################################################################
# convert between BASIC Integer and Python int

def int_to_integer_signed(n):
    """Convert Python int in range [-32768, 32767] to BASIC Integer."""
    if n > 0x7fff or n < -0x8000:
        raise error.RunError(error.OVERFLOW)
    if n < 0:
        n = 0x10000 + n
    return ('%', bytearray((n&0xff, n >> 8)))

def int_to_integer_unsigned(n):
    """Convert Python int in range [-32768, 65535] to BASIC Integer."""
    if n > 0xffff or n < -0x8000:
        raise error.RunError(error.OVERFLOW)
    if n < 0:
        n = 0x10000 + n
    return ('%', bytearray((n&0xff, n >> 8)))

def integer_to_int_signed(in_integer):
    """Convert BASIC Integer to Python int in range [-32768, 32767]."""
    s = in_integer[1]
    # 2's complement signed int, least significant byte first,
    # sign bit is most significant bit
    value = 0x100 * (s[1] & 0x7f) + s[0]
    if (s[1] & 0x80) == 0x80:
        return -0x8000 + value
    else:
        return value

def integer_to_int_unsigned(in_integer):
    """Convert BASIC Integer to Python int in range [0, 65535]."""
    s = in_integer[1]
    return 0x100 * s[1] + s[0]

###############################################################################
# boolean functions operate as bitwise functions on unsigned Python ints

def bool_to_integer(boo):
    """Convert Python boolean to Integer."""
    return ('%', bytearray('\xff\xff')) if boo else ('%', bytearray('\0\0'))

def integer_to_bool(in_integer):
    """Convert Integer to Python boolean."""
    return (in_integer[1][0] != 0 or in_integer[1][1] != 0)
