"""
PC-BASIC - values.py
Types, values and conversions

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import math
import string
import struct
import functools

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from . import error
from . import util
from . import basictoken as tk
from . import numbers
from . import strings
from .numbers import float_safe


# BASIC type sigils:
# Integer (%) - stored as two's complement, little-endian
# Single (!) - stored as 4-byte Microsoft Binary Format
# Double (#) - stored as 8-byte Microsoft Binary Format
# String ($) - stored as 1-byte length plus 2-byte pointer to string space
INT = '%'
SNG = '!'
DBL = '#'
STR = '$'

# storage size in bytes
TYPE_TO_SIZE = {STR: 3, INT: 2, SNG: 4, DBL: 8}
SIZE_TO_TYPE = {2: INT, 3: STR, 4: SNG, 8: DBL}

SIZE_TO_CLASS = {2: numbers.Integer, 3: strings.String, 4: numbers.Single, 8: numbers.Double}
TYPE_TO_CLASS = {INT: numbers.Integer, STR: strings.String, SNG: numbers.Single, DBL: numbers.Double}

def size_bytes(name):
    """Return the size of a value type, by variable name or type char."""
    return TYPE_TO_SIZE[name[-1]]

###############################################################################
# type checks

def pass_string(inp, err=error.TYPE_MISMATCH):
    """Check if variable is String-valued."""
    if not isinstance(inp, strings.String):
        if not isinstance(inp, numbers.Value):
            raise TypeError('%s is not of class Value' % type(inp))
        raise error.RunError(err)
    return inp

def pass_number(inp, err=error.TYPE_MISMATCH):
    """Check if variable is numeric."""
    if not isinstance(inp, numbers.Number):
        if not isinstance(inp, numbers.Value):
            raise TypeError('%s is not of class Value' % type(inp))
        raise error.RunError(err)
    return inp


###############################################################################

class Values(object):
    """Handles BASIC strings and numbers."""

    def __init__(self, screen, string_space, double_math):
        """Setup values."""
        self._float_error_handler = numbers.FloatErrorHandler(screen)
        self._strings = string_space
        # double-precision EXP, SIN, COS, TAN, ATN, LOG
        self._double_math = double_math

    def pause_error_handling(self, do_pause):
        """Suspend floating-point soft error handling."""
        self._float_error_handler.pause_handling(do_pause)

    ###########################################################################
    # convert between BASIC and Python values

    @float_safe
    def to_value(self, basic_val):
        """Convert BASIC value to Python value."""
        return basic_val.to_value()

    @float_safe
    def from_value(self, python_val, typechar):
        """Convert Python value to BASIC value."""
        return TYPE_TO_CLASS[typechar](values=self).from_value(python_val)

    def from_str_at(self, python_str, address):
        """Convert str to String at given address."""
        return strings.String(values=self).from_pointer(
            *self._strings.store(python_str, address))

    # NOTE that this function will overflow if outside the range of Integer
    # whereas Float.to_int will not
    def to_int(self, inp, unsigned=False):
        """Round numeric variable and convert to Python integer."""
        return self.to_integer(inp, unsigned).to_int(unsigned)

    def from_bool(self, boo):
        """Convert Python boolean to Integer."""
        if boo:
            return numbers.Integer().from_bytes('\xff\xff')
        return numbers.Integer()

    def to_bool(self, basic_value):
        """Convert Integer to Python boolean."""
        return not self.is_zero(basic_value)

    ###########################################################################
    # convert to and from internal representation

    @staticmethod
    def to_bytes(basic_val):
        """Convert BASIC value to internal byte representation."""
        # make a copy, not a view
        return basic_val.to_bytes()

    def from_bytes(self, token_bytes):
        """Convert internal byte representation to BASIC value."""
        # make a copy, not a view
        return SIZE_TO_CLASS[len(token_bytes)](values=self).from_bytes(token_bytes)

    def create(self, buf):
        """Create new variable object with buffer provided."""
        # this sets a view, not a copy
        return SIZE_TO_CLASS[len(buf)](buf, values=self)

    def null(self, sigil):
        """Return newly allocated value of the given type with zeroed buffer."""
        return TYPE_TO_CLASS[sigil](values=self)

    ###########################################################################
    # representations

    @float_safe
    def from_str(self, word, allow_nonnum, typechar=None):
        """Convert decimal str representation to number."""
        # keep as string if typechar asks for it, ignore typechar otherwise
        # FIXME: typechar is only used in INPUT and should be replaced
        # by creating the desired variable and then filling it with its class from_str
        if typechar == STR:
            return strings.String(buf=None, values=self).from_str(word)
        # skip spaces and line feeds (but not NUL).
        word = word.lstrip(' \n').upper()
        if not word:
            return numbers.Integer().from_int(0)
        if word[:2] == '&H':
            return numbers.Integer().from_hex(word[2:])
        elif word[:1] == '&':
            return numbers.Integer().from_oct(word[2:] if word[1:2] == 'O' else word[1:])
        # we need to try to convert to int first,
        # mainly so that the tokeniser can output the right token type
        try:
            return numbers.Integer().from_str(word)
        except ValueError as e:
            # non-integer characters, try a float
            pass
        except error.RunError as e:
            if e.err != error.OVERFLOW:
                raise
        # if allow_nonnum == False, raises ValueError for non-numerical characters
        is_double, mantissa, exp10 = numbers.str_to_decimal(word, allow_nonnum)
        if is_double:
            return numbers.Double().from_decimal(mantissa, exp10)
        return numbers.Single().from_decimal(mantissa, exp10)

    @staticmethod
    def to_str(inp, leading_space, type_sign):
        """Convert BASIC number to Python str."""
        # PRINT, STR$ - yes leading space, no type sign
        # WRITE - no leading space, no type sign
        # LIST - no loading space, yes type sign
        if isinstance(inp, numbers.Number):
            return inp.to_str(leading_space, type_sign)
        elif isinstance(inp, strings.String):
            raise error.RunError(error.TYPE_MISMATCH)
        raise TypeError('%s is not of class Value' % type(inp))


    ###########################################################################
    # type conversions

    def to_integer(self, inp, unsigned=False):
        """Check if variable is numeric, convert to Int."""
        if isinstance(inp, strings.String):
            raise error.RunError(error.TYPE_MISMATCH)
        return inp.to_integer(unsigned)

    @float_safe
    def to_single(self, num):
        """Check if variable is numeric, convert to Single."""
        if isinstance(num, strings.String):
            raise error.RunError(error.TYPE_MISMATCH)
        elif isinstance(num, numbers.Integer):
            return numbers.Single().from_integer(num)
        return num.to_single()

    @float_safe
    def to_double(self, num):
        """Check if variable is numeric, convert to Double."""
        if isinstance(num, strings.String):
            raise error.RunError(error.TYPE_MISMATCH)
        elif isinstance(num, numbers.Integer):
            return numbers.Double().from_integer(num)
        elif isinstance(num, numbers.Single):
            return numbers.Double().from_single(num)
        return num

    def to_float(self, num, allow_double=True):
        """Check if variable is numeric, convert to Double or Single."""
        if isinstance(num, numbers.Double) and allow_double:
            return num
        return self.to_single(num)

    def match_types(self, left, right):
        """Check if variables are numeric and convert to highest-precision."""
        if isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
            return self.to_double(left), self.to_double(right)
        elif isinstance(left, numbers.Single) or isinstance(right, numbers.Single):
            return self.to_single(left), self.to_single(right)
        elif isinstance(left, numbers.Integer) or isinstance(right, numbers.Integer):
            return self.to_integer(left), self.to_integer(right)
        elif isinstance(left, strings.String) or isinstance(right, strings.String):
            return pass_string(left), pass_string(right)
        raise TypeError('%s or %s is not of class Value.' % (type(left), type(right)))

    def to_type(self, typechar, value):
        """Check if variable can be converted to the given type and convert."""
        if typechar == STR:
            return pass_string(value)
        elif typechar == INT:
            return self.to_integer(value)
        elif typechar == SNG:
            return self.to_single(value)
        elif typechar == DBL:
            return self.to_double(value)
        raise ValueError('%s is not a valid sigil.' % typechar)


    ###############################################################################

    def round(self, x):
        """Round to nearest whole number without converting to int."""
        return self.to_float(x).iround()

    def is_zero(self, x):
        """Return whether a number is zero."""
        return pass_number(x).is_zero()

    ###############################################################################
    # math functions

    @float_safe
    def _call_float_function(self, fn, *args):
        """Convert to IEEE 754, apply function, convert back."""
        args = [self.to_float(arg, self._double_math) for arg in args]
        floatcls = args[0].__class__
        try:
            args = (arg.to_value() for arg in args)
            return floatcls().from_value(fn(*args))
        except ArithmeticError as e:
            # positive infinity of the appropriate class
            raise e.__class__(floatcls.pos_max)

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
        return numbers.Integer().from_int(pass_number(x).sign())

    def floor(self, x):
        """Truncate towards negative infinity (INT)."""
        return pass_number(x).clone().ifloor()

    def fix(self, x):
        """Truncate towards zero."""
        return pass_number(x).clone().itrunc()


    ###############################################################################
    # numeric operators

    @float_safe
    def add(self, left, right):
        """Add two numbers or concatenate two strings."""
        if isinstance(left, numbers.Number):
            # promote Integer to Single to avoid integer overflow
            left = self.to_float(left)
        left, right = self.match_types(left, right)
        return left.clone().iadd(right)

    @float_safe
    def subtract(self, left, right):
        """Subtract two numbers."""
        return self.add(pass_number(left), self.negate(right))

    def abs(self, inp):
        """Return the absolute value of a number. No-op for strings."""
        if isinstance(inp, strings.String):
            # strings pass unchanged
            return inp
        # promote Integer to Single to avoid integer overflow on -32768
        return self.to_float(inp).clone().iabs()

    def negate(self, inp):
        """Negation (unary -). No-op for strings."""
        if isinstance(inp, strings.String):
            # strings pass unchanged
            return inp
        # promote Integer to Single to avoid integer overflow on -32768
        return self.to_float(inp).clone().ineg()

    @float_safe
    def power(self, left, right):
        """Left^right."""
        if self._double_math and (
                isinstance(left, numbers.Double) or isinstance(right, numbers.Double)):
            return self._call_float_function(lambda a, b: a**b, self.to_double(left), self.to_double(right))
        elif isinstance(right, numbers.Integer):
            return self.to_single(left).ipow_int(right)
        else:
            return self._call_float_function(lambda a, b: a**b, self.to_single(left), self.to_single(right))

    @float_safe
    def multiply(self, left, right):
        """Left*right."""
        if isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
            return self.to_double(left).clone().imul(self.to_double(right))
        else:
            return self.to_single(left).clone().imul(self.to_single(right))

    @float_safe
    def divide(self, left, right):
        """Left/right."""
        if isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
            return self.to_double(left).clone().idiv(self.to_double(right))
        else:
            return self.to_single(left).clone().idiv(self.to_single(right))

    @float_safe
    def divide_int(self, left, right):
        """Left\\right."""
        return left.to_integer().clone().idiv_int(right.to_integer())

    @float_safe
    def mod(self, left, right):
        """Left modulo right."""
        return left.to_integer().clone().imod(right.to_integer())

    def bitwise_not(self, right):
        """Bitwise NOT, -x-1."""
        return numbers.Integer().from_int(-right.to_int()-1)

    def bitwise_and(self, left, right):
        """Bitwise AND."""
        return numbers.Integer().from_int(
            left.to_integer().to_int(unsigned=True) &
            right.to_integer().to_int(unsigned=True), unsigned=True)

    def bitwise_or(self, left, right):
        """Bitwise OR."""
        return numbers.Integer().from_int(
            left.to_integer().to_int(unsigned=True) |
            right.to_integer().to_int(unsigned=True), unsigned=True)

    def bitwise_xor(self, left, right):
        """Bitwise XOR."""
        return numbers.Integer().from_int(
            left.to_integer().to_int(unsigned=True) ^
            right.to_integer().to_int(unsigned=True), unsigned=True)

    def bitwise_eqv(self, left, right):
        """Bitwise equivalence."""
        return numbers.Integer().from_int(0xffff - (
                left.to_integer().to_int(unsigned=True) ^
                right.to_integer().to_int(unsigned=True)
            ), unsigned=True)

    def bitwise_imp(self, left, right):
        """Bitwise implication."""
        return numbers.Integer().from_int(
                (0xffff - left.to_integer().to_int(unsigned=True)) |
                right.to_integer().to_int(unsigned=True),
            unsigned=True)


    ###############################################################################
    # number and string operations

    def _bool_eq(self, left, right):
        """Return true if left == right, false otherwise."""
        left, right = self.match_types(left, right)
        return left.eq(right)

    def _bool_gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        left, right = self.match_types(left, right)
        return left.gt(right)

    def equals(self, left, right):
        """Return -1 if left == right, 0 otherwise."""
        return self.from_bool(self._bool_eq(left, right))

    def not_equals(self, left, right):
        """Return -1 if left != right, 0 otherwise."""
        return self.from_bool(not self._bool_eq(left, right))

    def gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        return self.from_bool(self._bool_gt(left, right))

    def gte(self, left, right):
        """Ordering: return -1 if left >= right, 0 otherwise."""
        return self.from_bool(not self._bool_gt(right, left))

    def lte(self, left, right):
        """Ordering: return -1 if left <= right, 0 otherwise."""
        return self.from_bool(not self._bool_gt(left, right))

    def lt(self, left, right):
        """Ordering: return -1 if left < right, 0 otherwise."""
        return self.from_bool(self._bool_gt(right, left))


    ##########################################################################
    # conversion between numbers and strings

    def cvi(self, x):
        """CVI: return the int value of a byte representation."""
        cstr = pass_string(x).to_str()
        error.throw_if(len(cstr) < 2)
        return self.from_bytes(cstr[:2])

    def cvs(self, x):
        """CVS: return the single-precision value of a byte representation."""
        cstr = pass_string(x).to_str()
        error.throw_if(len(cstr) < 4)
        return self.from_bytes(cstr[:4])

    def cvd(self, x):
        """CVD: return the double-precision value of a byte representation."""
        cstr = pass_string(x).to_str()
        error.throw_if(len(cstr) < 8)
        return self.from_bytes(cstr[:8])

    def mki(self, x):
        """MKI$: return the byte representation of an int."""
        return strings.String(buf=None, values=self).from_str(self.to_bytes(self.to_integer(x)))

    def mks(self, x):
        """MKS$: return the byte representation of a single."""
        return strings.String(buf=None, values=self).from_str(self.to_bytes(self.to_single(x)))

    def mkd(self, x):
        """MKD$: return the byte representation of a double."""
        return strings.String(buf=None, values=self).from_str(self.to_bytes(self.to_double(x)))

    def representation(self, x):
        """STR$: string representation of a number."""
        return strings.String(buf=None, values=self).from_str(
                    self.to_str(pass_number(x), leading_space=True, type_sign=False))

    def val(self, x):
        """VAL: number value of a string."""
        return self.from_str(pass_string(x).to_str(), allow_nonnum=True)

    def character(self, x):
        """CHR$: character for ASCII value."""
        val = self.to_int(x)
        error.range_check(0, 255, val)
        return strings.String(buf=None, values=self).from_str(chr(val))

    def octal(self, x):
        """OCT$: octal representation of int."""
        # allow range -32768 to 65535
        val = self.to_integer(x, unsigned=True)
        return strings.String(buf=None, values=self).from_str(val.to_oct())

    def hexadecimal(self, x):
        """HEX$: hexadecimal representation of int."""
        # allow range -32768 to 65535
        val = self.to_integer(x, unsigned=True)
        return strings.String(buf=None, values=self).from_str(val.to_hex())


    ######################################################################
    # string manipulation

    def length(self, s):
        """LEN: length of string."""
        return pass_string(s).len()

    def asc(self, s):
        """ASC: ordinal ASCII value of a character."""
        return pass_string(s).asc()

    def space(self, num):
        """SPACE$: repeat spaces."""
        return strings.String(buf=None, values=self).space(num)
