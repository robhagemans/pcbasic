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

SIZE_TO_CLASS = {2: numbers.Integer, 4: numbers.Single, 8: numbers.Double}
TYPE_TO_CLASS = {INT: numbers.Integer, SNG: numbers.Single, DBL: numbers.Double}

def null(sigil):
    """Return null value for the given type."""
    if sigil == '$':
        return (sigil, bytearray(TYPE_TO_SIZE[sigil]))
    else:
        return TYPE_TO_CLASS[sigil]()

def size_bytes(name):
    """Return the size of a value type, by variable name or type char."""
    return TYPE_TO_SIZE[name[-1]]


###############################################################################
# type checks

def pass_string(inp, err=error.TYPE_MISMATCH):
    """Check if variable is String-valued."""
    if Values.sigil(inp) != '$':
        raise error.RunError(err)
    return inp

def pass_number(inp, err=error.TYPE_MISMATCH):
    """Check if variable is numeric."""
    if Values.sigil(inp) not in ('%', '!', '#'):
        raise error.RunError(err)
    return inp


###############################################################################
# convert between BASIC String and token address bytes

def string_length(in_string):
    """Get string length as Python int."""
    return Values.to_bytes(in_string)[0]

def string_address(in_string):
    """Get string address as Python int."""
    return struct.unpack('<H', Values.to_bytes(in_string)[1:])[0]


###############################################################################
# convert between BASIC Integer and Python int

#D
def int_to_integer(n, unsigned=False):
    """Convert Python int to BASIC Integer."""
    return numbers.Integer().from_int(n, unsigned)

#D
def integer_to_int(in_integer, unsigned=False):
    """Convert BASIC Integer to Python int."""
    return in_integer.to_int(unsigned)




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
        typechar = self.sigil(basic_val)
        if typechar == '$':
            return self._strings.copy(basic_val)
        else:
            return basic_val.to_value()

    @float_safe
    def from_value(self, python_val, typechar):
        """Convert Python value to BASIC value."""
        if typechar == '$':
            return self._strings.store(python_val)
        else:
            return TYPE_TO_CLASS[typechar]().from_value(python_val)

    def to_int(self, inp, unsigned=False):
        """Round numeric variable and convert to Python integer."""
        return self.to_integer(inp, unsigned).to_int(unsigned)

    def from_bool(self, boo):
        """Convert Python boolean to Integer."""
        return self.from_bytes('\xff\xff') if boo else self.from_bytes('\0\0')

    def to_bool(self, basic_value):
        """Convert Integer to Python boolean."""
        return not self.is_zero(basic_value)

    ###########################################################################
    # convert to and from internal representation

    @staticmethod
    def to_bytes(basic_val):
        """Convert BASIC value to internal byte representation."""
        if isinstance(basic_val, tuple):
            return bytearray(basic_val[1])
        else:
            # make a copy, not a view
            return basic_val.to_bytes()

    @staticmethod
    def from_bytes(token_bytes):
        """Convert internal byte representation to BASIC value."""
        typechar = SIZE_TO_TYPE[len(token_bytes)]
        if typechar == '$':
            return (SIZE_TO_TYPE[len(token_bytes)], bytearray(token_bytes))
        else:
            # make a copy, not a view
            return SIZE_TO_CLASS[len(token_bytes)]().from_bytes(token_bytes)

    ###########################################################################
    # type conversions

    @staticmethod
    def sigil(num):
        if isinstance(num, tuple):
            return num[0]
        elif isinstance(num, numbers.Value):
            return num.sigil
        else:
            assert False, 'Unrecognised value type: %s' % type(num)

    def to_integer(self, inp, unsigned=False):
        """Check if variable is numeric, convert to Int."""
        typechar = self.sigil(inp)
        if typechar == '$':
            # type mismatch
            raise error.RunError(error.TYPE_MISMATCH)
        return inp.to_integer(unsigned)

    @float_safe
    def to_single(self, num):
        """Check if variable is numeric, convert to Single."""
        typechar = self.sigil(num)
        if typechar == '$':
            raise error.RunError(error.TYPE_MISMATCH)
        elif typechar == '%':
            return numbers.Single().from_integer(num)
        else:
            return num.to_single()

    @float_safe
    def to_double(self, num):
        """Check if variable is numeric, convert to Double."""
        typechar = self.sigil(num)
        if typechar == '$':
            raise error.RunError(error.TYPE_MISMATCH)
        elif typechar == '%':
            return numbers.Double().from_integer(num)
        elif typechar == '!':
            return numbers.Double().from_single(num)
        elif typechar == '#':
            return num

    def to_float(self, num, allow_double=True):
        """Check if variable is numeric, convert to Double or Single."""
        typechar = self.sigil(num)
        if typechar == '#' and allow_double:
            return num
        else:
            return self.to_single(num)

    def to_most_precise(self, left, right):
        """Check if variables are numeric and convert to highest-precision."""
        left_type, right_type = self.sigil(left), self.sigil(right)
        if left_type == '#' or right_type == '#':
            return (self.to_double(left), self.to_double(right))
        elif left_type == '!' or right_type == '!':
            return (self.to_single(left), self.to_single(right))
        elif left_type == '%' or right_type == '%':
            return (self.to_integer(left), self.to_integer(right))
        else:
            raise error.RunError(error.TYPE_MISMATCH)

    def to_type(self, typechar, value):
        """Check if variable can be converted to the given type and convert."""
        if typechar == '$':
            return pass_string(value)
        elif typechar == '%':
            return self.to_integer(value)
        elif typechar == '!':
            return self.to_single(value)
        elif typechar == '#':
            return self.to_double(value)

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
        """Add two numbers."""
        # promote Integer to Single to avoid integer overflow
        left = self.to_float(left)
        left, right = self.to_most_precise(left, right)
        return left.clone().iadd(right)

    @float_safe
    def subtract(self, left, right):
        """Subtract two numbers."""
        return self.add(left, self.negate(right))

    def abs(self, inp):
        """Return the absolute value of a number. No-op for strings."""
        if self.sigil(inp) == '$':
            # strings pass unchanged
            return inp
        # promote Integer to Single to avoid integer overflow on -32768
        return self.to_float(inp).clone().iabs()

    def negate(self, inp):
        """Negation (unary -). No-op for strings."""
        if self.sigil(inp) == '$':
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
        if self.sigil(left) == '$':
            return (self._strings.copy(pass_string(left)) ==
                    self._strings.copy(pass_string(right)))
        else:
            left, right = self.to_most_precise(left, right)
            return left.eq(right)

    def bool_gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        ltype = self.sigil(left)
        if self.sigil(left) == '$':
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
            left, right = self.to_most_precise(left, right)
            return left.gt(right)

    def equals(self, left, right):
        """Return -1 if left == right, 0 otherwise."""
        return self.from_bool(self._bool_eq(left, right))

    def not_equals(self, left, right):
        """Return -1 if left != right, 0 otherwise."""
        return self.from_bool(not self._bool_eq(left, right))

    def gt(self, left, right):
        """Ordering: return -1 if left > right, 0 otherwise."""
        return self.from_bool(self.bool_gt(left, right))

    def gte(self, left, right):
        """Ordering: return -1 if left >= right, 0 otherwise."""
        return self.from_bool(not self.bool_gt(right, left))

    def lte(self, left, right):
        """Ordering: return -1 if left <= right, 0 otherwise."""
        return self.from_bool(not self.bool_gt(left, right))

    def lt(self, left, right):
        """Ordering: return -1 if left < right, 0 otherwise."""
        return self.from_bool(self.bool_gt(right, left))

    def plus(self, left, right):
        """Binary + operator: add or concatenate."""
        if self.sigil(left) == '$':
            return self.concat(left, right)
        else:
            return self.add(left, right)

    ##########################################################################
    # conversion

    def cvi(self, x):
        """CVI: return the int value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 2)
        return self.from_bytes(cstr[:2])

    def cvs(self, x):
        """CVS: return the single-precision value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 4)
        return self.from_bytes(cstr[:4])

    def cvd(self, x):
        """CVD: return the double-precision value of a byte representation."""
        cstr = self._strings.copy(pass_string(x))
        error.throw_if(len(cstr) < 8)
        return self.from_bytes(cstr[:8])

    def mki(self, x):
        """MKI$: return the byte representation of an int."""
        return self._strings.store(self.to_bytes(self.to_integer(x)))

    def mks(self, x):
        """MKS$: return the byte representation of a single."""
        return self._strings.store(self.to_bytes(self.to_single(x)))

    def mkd(self, x):
        """MKD$: return the byte representation of a double."""
        return self._strings.store(self.to_bytes(self.to_double(x)))

    def representation(self, x):
        """STR$: string representation of a number."""
        return self._strings.store(number_to_str(pass_number(x), screen=True))

    def val(self, x):
        """VAL: number value of a string."""
        return self.str_to_number(self._strings.copy(pass_string(x)))

    def character(self, x):
        """CHR$: character for ASCII value."""
        val = self.to_int(x)
        error.range_check(0, 255, val)
        return self._strings.store(chr(val))

    def octal(self, x):
        """OCT$: octal representation of int."""
        # allow range -32768 to 65535
        val = self.to_integer(x, unsigned=True)
        return self._strings.store(integer_to_str_oct(val))

    def hexadecimal(self, x):
        """HEX$: hexadecimal representation of int."""
        # allow range -32768 to 65535
        val = self.to_integer(x, unsigned=True)
        return self._strings.store(integer_to_str_hex(val))


    ######################################################################
    # string manipulation

    def length(self, x):
        """LEN: length of string."""
        return numbers.Integer().from_int(string_length(pass_string(x)))

    def asc(self, x):
        """ASC: ordinal ASCII value of a character."""
        s = self._strings.copy(pass_string(x))
        error.throw_if(not s)
        return numbers.Integer().from_int(ord(s[0]))

    def space(self, x):
        """SPACE$: repeat spaces."""
        num = self.to_int(x)
        error.range_check(0, 255, num)
        return self._strings.store(' '*num)

    # FIXME: start is still a Python int
    def instr(self, big, small, start):
        """INSTR: find substring in string."""
        big = self._strings.copy(pass_string(big))
        small = self._strings.copy(pass_string(small))
        if big == '' or start > len(big):
            return null('%')
        # BASIC counts string positions from 1
        find = big[start-1:].find(small)
        if find == -1:
            return null('%')
        return numbers.Integer().from_int(start + find)

    def mid(self, s, start, num=None):
        """MID$: get substring."""
        s = self._strings.copy(s)
        start = self.to_int(start)
        if num is None:
            num = len(s)
        else:
            num = self.to_int(num)
        error.range_check(1, 255, start)
        error.range_check(0, 255, num)
        if num == 0 or start > len(s):
            return null('$')
        start -= 1
        stop = start + num
        stop = min(stop, len(s))
        return self._strings.store(s[start:stop])

    def left(self, s, stop):
        """LEFT$: get substring at the start of string."""
        s = self._strings.copy(s)
        stop = self.to_int(stop)
        error.range_check(0, 255, stop)
        if stop == 0:
            return null('$')
        stop = min(stop, len(s))
        return self._strings.store(s[:stop])

    def right(self, s, stop):
        """RIGHT$: get substring at the end of string."""
        s = self._strings.copy(s)
        stop = self.to_int(stop)
        error.range_check(0, 255, stop)
        if stop == 0:
            return null('$')
        stop = min(stop, len(s))
        return self._strings.store(s[-stop:])


    ###########################################################################
    # string representation of numbers

    def str_to_number(self, strval, allow_nonnum=True):
        """Convert Python str to BASIC value."""
        ins = StringIO(strval)
        # skip spaces and line feeds (but not NUL).
        util.skip(ins, (' ', '\n'))
        token = self.tokenise_number(ins)
        value = numbers.from_token(token)
        if not allow_nonnum and util.skip_white(ins) != '':
            # not everything has been parsed - error
            return None
        if not value:
            return null('%')
        return value

    def str_to_type(self, typechar, word):
        """Convert Python str to requested type, be strict about non-numeric chars."""
        if typechar == '$':
            return self._strings.store(word)
        else:
            return self.str_to_number(word, allow_nonnum=False)

    # this should not be in the interface but is quite entangled
    # REFACTOR 2) to util.read_numeric_string -> str_to_number
    def tokenise_number(self, ins):
        """Convert Python-string number representation to number token."""
        c = util.peek(ins)
        if not c:
            return ''
        elif c == '&':
            # handle hex or oct constants
            ins.read(1)
            if util.peek(ins).upper() == 'H':
                # hex constant
                return self._tokenise_hex(ins)
            else:
                # octal constant
                return self._tokenise_oct(ins)
        elif c in string.digits + '.+-':
            # handle other numbers
            # note GW passes signs separately as a token
            # and only stores positive numbers in the program
            return self._tokenise_dec(ins)

    def _tokenise_dec(self, ins):
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
        while len(word) > 0 and (word[-1] in number_whitespace):
            word = word[:-1]
            ins.seek(-1, 1) # even if c==''
        # remove all internal whitespace
        trimword = ''
        for c in word:
            if c not in number_whitespace:
                trimword += c
        word = trimword
        # write out the numbers
        if len(word) == 1 and word in string.digits:
            # digit
            return chr(0x11 + _str_to_int(word))
        elif (not (have_exp or have_point or word[-1] in '!#') and
                                _str_to_int(word) <= 0x7fff and _str_to_int(word) >= -0x8000):
            if _str_to_int(word) <= 0xff and _str_to_int(word) >= 0:
                # one-byte constant
                return tk.T_BYTE + chr(_str_to_int(word))
            else:
                # two-byte constant
                return tk.T_INT + self.to_bytes(numbers.Integer().from_int(_str_to_int(word)))
        else:
            mbf = self.to_bytes(self._str_to_float(word))
            if len(mbf) == 4:
                return tk.T_SINGLE + mbf
            else:
                return tk.T_DOUBLE + mbf

    def _tokenise_hex(self, ins):
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
        return tk.T_HEX + struct.pack('<H', val)

    def _tokenise_oct(self, ins):
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
        return tk.T_OCT + struct.pack('<H', val)

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

    @float_safe
    def _float_from_exp10(self, neg, mantissa, exp10, is_double):
        """Create floating-point value from mantissa and decomal exponent."""
        cls = numbers.Double if is_double else numbers.Single
        return cls().from_decimal(-mantissa if neg else mantissa, exp10)


##############################################################################

def number_to_str(inp, screen=False, write=False):
    """Convert BASIC number to Python str."""
    # screen=False means in a program listing
    # screen=True is used for screen, str$ and sequential files
    if not inp:
        raise error.RunError(error.STX)
    typechar = Values.sigil(inp)
    if typechar == '%':
        if screen and not write and integer_to_int(inp) >= 0:
            return ' ' + str(integer_to_int(inp))
        else:
            return str(integer_to_int(inp))
    elif typechar == '!':
        return float_to_str(inp, screen, write)
    elif typechar == '#':
        return float_to_str(inp, screen, write)
    else:
        raise error.RunError(error.TYPE_MISMATCH)

def integer_to_str_oct(inp):
    """Convert integer to str in octal representation."""
    intval = inp.to_int(unsigned=True)
    if intval == 0:
        return '0'
    else:
        return oct(intval)[1:]

def integer_to_str_hex(inp):
    """Convert integer to str in hex representation."""
    return hex(inp.to_int(unsigned=True))[2:].upper()

def _str_to_int(s):
    """Return Python int value for Python str, zero if malformed."""
    try:
        return int(s)
    except ValueError:
        return 0

def float_to_str(n_in, screen=False, write=False):
    """Convert BASIC float to Python string."""
    # screen=True (ie PRINT) - leading space, no type sign
    # write=True (ie WRITE) - no leading space, no type sign
    # default mode is for LIST
    # zero exponent byte means zero
    if n_in.is_zero():
        if screen and not write:
            return ' 0'
        elif write:
            return '0'
        else:
            return '0' + n_in.sigil
    # print sign
    sign = ''
    if n_in.is_negative():
        sign = '-'
    elif screen and not write:
        sign = ' '
    num, exp10 = n_in.to_decimal()
    ndigits = n_in.digits
    digitstr = _get_digits(num, ndigits, remove_trailing=True)
    # exponent for scientific notation
    exp10 += ndigits - 1
    if exp10 > ndigits - 1 or len(digitstr)-exp10 > ndigits + 1:
        # use scientific notation
        valstr = _scientific_notation(digitstr, exp10, n_in.exp_sign, digits_to_dot=1, force_dot=False)
    else:
        # use decimal notation
        type_sign = '' if screen or write else n_in.sigil
        valstr = _decimal_notation(digitstr, exp10, type_sign, force_dot=False)
    return sign + valstr

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



# for to_str
# for numbers, tab and LF are whitespace
number_whitespace = ' \t\n'

# string representations

def _get_digits(num, digits, remove_trailing):
    """Get the digits for an int."""
    digitstr = str(abs(num))
    digitstr = '0'*(digits-len(digitstr)) + digitstr[:digits]
    if remove_trailing:
        return digitstr.rstrip('0')
    return digitstr

def _scientific_notation(digitstr, exp10, exp_sign, digits_to_dot, force_dot):
    """Put digits in scientific E-notation."""
    valstr = digitstr[:digits_to_dot]
    if len(digitstr) > digits_to_dot:
        valstr += '.' + digitstr[digits_to_dot:]
    elif len(digitstr) == digits_to_dot and force_dot:
        valstr += '.'
    exponent = exp10 - digits_to_dot + 1
    valstr += exp_sign
    if exponent < 0:
        valstr += '-'
    else:
        valstr += '+'
    valstr += _get_digits(abs(exponent), digits=2, remove_trailing=False)
    return valstr

def _decimal_notation(digitstr, exp10, type_sign, force_dot):
    """Put digits in decimal notation."""
    # digits to decimal point
    exp10 += 1
    if exp10 >= len(digitstr):
        valstr = digitstr + '0'*(exp10-len(digitstr))
        if force_dot:
            valstr += '.'
        if not force_dot or type_sign == '#':
            valstr += type_sign
    elif exp10 > 0:
        valstr = digitstr[:exp10] + '.' + digitstr[exp10:]
        if type_sign == '#':
            valstr += type_sign
    else:
        if force_dot:
            valstr = '0'
        else:
            valstr = ''
        valstr += '.' + '0'*(-exp10) + digitstr
        if type_sign == '#':
            valstr += type_sign
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
        digitstr = _get_digits(num, work_digits, remove_trailing=True)
        if len(digitstr) < digits_before + decimals:
            digitstr += '0' * (digits_before + decimals - len(digitstr))
    # this is just to reproduce GW results for no digits:
    # e.g. PRINT USING "#^^^^";1 gives " E+01" not " E+00"
    if work_digits == 0:
        exp10 += 1
    exp10 += digits_before + decimals - 1
    return _scientific_notation(digitstr, exp10, expr.exp_sign, digits_to_dot=digits_before, force_dot=force_dot)

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
    return _decimal_notation(
                digitstr, nbefore - 1,
                type_sign='', force_dot=force_dot)
