"""
PC-BASIC - values.py
Types, values and conversions

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import math
import struct
import functools

from ...compat import int2byte

from ..base import error
from ..base import tokens as tk
from . import numbers
from . import strings


# BASIC type sigils:
# Integer (%) - stored as two's complement, little-endian
# Single (!) - stored as 4-byte Microsoft Binary Format
# Double (#) - stored as 8-byte Microsoft Binary Format
# String ($) - stored as 1-byte length plus 2-byte pointer to string space
INT = numbers.Integer.sigil
SNG = numbers.Single.sigil
DBL = numbers.Double.sigil
STR = strings.String.sigil

# storage size in bytes
TYPE_TO_SIZE = {STR: 3, INT: 2, SNG: 4, DBL: 8}
SIZE_TO_TYPE = {2: INT, 3: STR, 4: SNG, 8: DBL}

# type classes
SIZE_TO_CLASS = {
    2: numbers.Integer,
    3: strings.String,
    4: numbers.Single,
    8: numbers.Double
}

TYPE_TO_CLASS = {
    INT: numbers.Integer,
    STR: strings.String,
    SNG: numbers.Single,
    DBL: numbers.Double
}

# cutoff for trigonometric functions
# above this machine precision makes the result useless and machine/os dependent
# this is close to what gw uses but not quite equivalent
TRIG_MAX = 5e16

def size_bytes(name):
    """Return the size of a value type, by variable name or type char."""
    return TYPE_TO_SIZE[name[-1:]]

###############################################################################
# type checks

def check_value(inp):
    """Check if value is of Value type."""
    if not isinstance(inp, numbers.Value):
        raise TypeError('%s is not of class Value' % type(inp))

def pass_string(inp, err=error.TYPE_MISMATCH):
    """Check if variable is String-valued."""
    if not isinstance(inp, strings.String):
        check_value(inp)
        raise error.BASICError(err)
    return inp

def pass_number(inp, err=error.TYPE_MISMATCH):
    """Check if variable is numeric."""
    if not isinstance(inp, numbers.Number):
        check_value(inp)
        raise error.BASICError(err)
    return inp

def next_string(args):
    """Retrieve a string from an iterator and return as Python value."""
    expr = next(args)
    return to_string_or_none(expr)

def to_string_or_none(expr):
    if isinstance(expr, strings.String):
        return expr.to_value()
    elif expr is None:
        return expr
    else:
        raise error.BASICError(error.TYPE_MISMATCH)


###############################################################################
# type conversions

def match_types(left, right):
    """Check if variables are numeric and convert to highest-precision."""
    if isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
        return to_double(left), to_double(right)
    elif isinstance(left, numbers.Single) or isinstance(right, numbers.Single):
        return to_single(left), to_single(right)
    elif isinstance(left, numbers.Integer) or isinstance(right, numbers.Integer):
        return to_integer(left), to_integer(right)
    elif isinstance(left, strings.String) or isinstance(right, strings.String):
        return pass_string(left), pass_string(right)
    raise TypeError('%s or %s is not of class Value.' % (type(left), type(right)))


###############################################################################
# error handling

def float_safe(fn):
    """Decorator to handle floating point errors."""
    def wrapped_fn(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, ArithmeticError) as e:
            return args[0].error_handler.handle(e)
    wrapped_fn.__name__ = fn.__name__
    return wrapped_fn

def _call_float_function(fn, *args):
    """Convert to IEEE 754, apply function, convert back."""
    args = list(args)
    pass_number(args[0])
    values = args[0]._values
    feh = args[0].error_handler
    try:
        # to_float can overflow on Double.pos_max
        args = [_arg.to_float(values.double_math) for _arg in args]
        floatcls = args[0].__class__
        python_args = [_arg.to_value() for _arg in args]
        result = fn(*python_args)
        # python3 may return complex values for some real functions
        # where python2 simply raises an error
        if isinstance(result, complex):
            raise ValueError('Non-real result')
        return floatcls(None, values).from_value(result)
    except (ValueError, ArithmeticError) as e:
        # create positive infinity of the appropriate class
        if values.double_math and isinstance(args[0], numbers.Double):
            floatcls = numbers.Double
        else:
            floatcls = numbers.Single
        infty = floatcls(None, values).from_bytes(floatcls.pos_max)
        # attach as exception payload for float error handler to deal with
        return feh.handle(e.__class__(infty))


class FloatErrorHandler(object):
    """Handles floating point errors."""

    # types of errors that do not always interrupt execution
    soft_types = (error.OVERFLOW, error.DIVISION_BY_ZERO)

    def __init__(self, console):
        """Setup handler."""
        self._console = console
        self._do_raise = False

    def suspend(self, do_raise):
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
        else: # pragma: no cover
            # shouldn't happen, we're only called with ValueError/ArithmeticError
            raise e
        if (self._do_raise or self._console is None or math_error not in self.soft_types):
            # also raises exception in error_handle_mode!
            # in that case, prints a normal error message
            raise error.BASICError(math_error)
        else:
            # write a message & continue as normal
            # message should not include line number or trailing \xFF
            self._console.write_line(error.BASICError(math_error).message)
        # return max value for the appropriate float type
        # integer operations should just raise the BASICError directly, they are not handled
        if e.args and isinstance(e.args[0], numbers.Float):
            return e.args[0]
        else: # pragma: no cover
            return numbers.Single(None, self).from_bytes(numbers.Single.pos_max)


###############################################################################

class Values(object):
    """Handles BASIC strings and numbers."""

    def __init__(self, string_space, double_math):
        """Setup values."""
        self.stringspace = string_space
        # double-precision EXP, SIN, COS, TAN, ATN, LOG
        self.double_math = double_math
        self.error_handler = None

    def set_handler(self, handler):
        """Initialise the error message console."""
        self.error_handler = handler

    def create(self, buf):
        """Create new variable object with buffer provided."""
        # this sets a view, not a copy
        return SIZE_TO_CLASS[len(buf)](buf, self)

    def new(self, sigil):
        """Return newly allocated value of the given type with zeroed buffer."""
        return TYPE_TO_CLASS[sigil](None, self)

    def new_string(self):
        """Return newly allocated null string."""
        return strings.String(None, self)

    def new_integer(self):
        """Return newly allocated zero integer."""
        return numbers.Integer(None, self)

    def new_single(self):
        """Return newly allocated zero single."""
        return numbers.Single(None, self)

    def new_double(self):
        """Return newly allocated zero double."""
        return numbers.Double(None, self)

    ###########################################################################
    # convert between BASIC and Python values

    @float_safe
    def from_value(self, python_val, typechar):
        """Convert Python value to BASIC value."""
        return TYPE_TO_CLASS[typechar](None, self).from_value(python_val)

    def from_str_at(self, python_str, address):
        """Convert str to String at given address."""
        return strings.String(None, self).from_pointer(
            *self.stringspace.store(python_str, address))

    def from_bool(self, boo):
        """Convert Python boolean to Integer."""
        if boo:
            return numbers.Integer(None, self).from_bytes(b'\xff\xff')
        return numbers.Integer(None, self)

    ###########################################################################
    # convert to and from internal representation

    def from_bytes(self, token_bytes):
        """Convert internal byte representation to BASIC value."""
        # make a copy, not a view
        return SIZE_TO_CLASS[len(token_bytes)](None, self).from_bytes(token_bytes)

    def from_token(self, token):
        """Convert number token to new Number temporary"""
        if not token:
            raise ValueError('Token must not be empty')
        lead = bytes(token)[0:1]
        if lead == tk.T_SINGLE:
            return numbers.Single(None, self).from_token(token)
        elif lead == tk.T_DOUBLE:
            return numbers.Double(None, self).from_token(token)
        elif lead in tk.NUMBER:
            return numbers.Integer(None, self).from_token(token)
        raise ValueError('%s is not a number token' % repr(token))

    ###########################################################################
    # create value from string representations

    @float_safe
    def from_repr(self, word, allow_nonnum, typechar=None):
        """Convert representation to value."""
        # keep as string if typechar asks for it, ignore typechar otherwise
        if typechar == STR:
            return self.new_string().from_str(word)
        # skip spaces and line feeds (but not NUL).
        word = word.lstrip(b' \n').upper()
        if not word:
            return self.new_integer()
        if word[:2] == b'&H':
            return self.new_integer().from_hex(word[2:])
        elif word[:1] == b'&':
            return self.new_integer().from_oct(word[2:] if word[1:2] == b'O' else word[1:])
        # we need to try to convert to int first,
        # mainly so that the tokeniser can output the right token type
        try:
            return self.new_integer().from_str(word)
        except ValueError as e:
            # non-integer characters, try a float
            pass
        except error.BASICError as e:
            if e.err != error.OVERFLOW: # pragma: no cover
                # shouldn't happen, from_str only raises Overflow
                raise
        # if allow_nonnum == False, raises ValueError for non-numerical characters
        is_double, mantissa, exp10 = numbers.str_to_decimal(word, allow_nonnum)
        if is_double:
            return self.new_double().from_decimal(mantissa, exp10)
        return self.new_single().from_decimal(mantissa, exp10)


###############################################################################
# conversions

def to_integer(inp, unsigned=False):
    """Check if variable is numeric, convert to Int."""
    if isinstance(inp, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    return inp.to_integer(unsigned)

@float_safe
def to_single(num):
    """Check if variable is numeric, convert to Single."""
    if isinstance(num, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    return num.to_single()

@float_safe
def to_double(num):
    """Check if variable is numeric, convert to Double."""
    if isinstance(num, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    return num.to_double()

def cint_(args):
    """CINT: convert to integer (by rounding, halves away from zero)."""
    value, = args
    return to_integer(value)

def csng_(args):
    """CSNG: convert to single (by Gaussian rounding)."""
    value, = args
    return to_single(value)

def cdbl_(args):
    """CDBL: convert to double."""
    value, = args
    return to_double(value)

def to_type(typechar, value):
    """Check if variable can be converted to the given type and convert if necessary."""
    if typechar == STR:
        return pass_string(value)
    elif typechar == INT:
        return to_integer(value)
    elif typechar == SNG:
        return to_single(value)
    elif typechar == DBL:
        return to_double(value)
    raise ValueError('%s is not a valid sigil.' % typechar)

# NOTE that this function will overflow if outside the range of Integer
# whereas Float.to_int will not
def to_int(inp, unsigned=False):
    """Round numeric variable and convert to Python integer."""
    return to_integer(inp, unsigned).to_int(unsigned)

def mki_(args):
    """MKI$: return the byte representation of an int."""
    x, = args
    return x._values.new_string().from_str(bytes(to_integer(x).to_bytes()))

def mks_(args):
    """MKS$: return the byte representation of a single."""
    x, = args
    return x._values.new_string().from_str(bytes(to_single(x).to_bytes()))

def mkd_(args):
    """MKD$: return the byte representation of a double."""
    x, = args
    return x._values.new_string().from_str(bytes(to_double(x).to_bytes()))

def cvi_(args):
    """CVI: return the int value of a byte representation."""
    x, = args
    cstr = pass_string(x).to_str()
    error.throw_if(len(cstr) < 2)
    return x._values.from_bytes(cstr[:2])

def cvs_(args):
    """CVS: return the single-precision value of a byte representation."""
    x, = args
    cstr = pass_string(x).to_str()
    error.throw_if(len(cstr) < 4)
    return x._values.from_bytes(cstr[:4])

def cvd_(args):
    """CVD: return the double-precision value of a byte representation."""
    x, = args
    cstr = pass_string(x).to_str()
    error.throw_if(len(cstr) < 8)
    return x._values.from_bytes(cstr[:8])


###############################################################################
# comparisons

def _bool_eq(left, right):
    """Return true if left == right, false otherwise."""
    left, right = match_types(left, right)
    return left.eq(right)

def _bool_gt(left, right):
    """Ordering: return -1 if left > right, 0 otherwise."""
    left, right = match_types(left, right)
    return left.gt(right)

def eq(left, right):
    """Return -1 if left == right, 0 otherwise."""
    return left._values.from_bool(_bool_eq(left, right))

def neq(left, right):
    """Return -1 if left != right, 0 otherwise."""
    return left._values.from_bool(not _bool_eq(left, right))

def gt(left, right):
    """Ordering: return -1 if left > right, 0 otherwise."""
    return left._values.from_bool(_bool_gt(left, right))

def gte(left, right):
    """Ordering: return -1 if left >= right, 0 otherwise."""
    return left._values.from_bool(not _bool_gt(right, left))

def lte(left, right):
    """Ordering: return -1 if left <= right, 0 otherwise."""
    return left._values.from_bool(not _bool_gt(left, right))

def lt(left, right):
    """Ordering: return -1 if left < right, 0 otherwise."""
    return left._values.from_bool(_bool_gt(right, left))


###############################################################################
# bitwise operators

def not_(num):
    """Bitwise NOT, -x-1."""
    return num._values.new_integer().from_int(~to_integer(num).to_int())

def and_(left, right):
    """Bitwise AND."""
    return left._values.new_integer().from_int(
        to_integer(left).to_int(unsigned=True) & to_integer(right).to_int(unsigned=True),
        unsigned=True)

def or_(left, right):
    """Bitwise OR."""
    return left._values.new_integer().from_int(
        to_integer(left).to_int(unsigned=True) | to_integer(right).to_int(unsigned=True),
        unsigned=True)

def xor_(left, right):
    """Bitwise XOR."""
    return left._values.new_integer().from_int(
        to_integer(left).to_int(unsigned=True) ^ to_integer(right).to_int(unsigned=True),
        unsigned=True)

def eqv_(left, right):
    """Bitwise equivalence."""
    return left._values.new_integer().from_int(
        ~(to_integer(left).to_int(unsigned=True) ^ to_integer(right).to_int(unsigned=True)),
        unsigned=True)

def imp_(left, right):
    """Bitwise implication."""
    return left._values.new_integer().from_int(
        (~to_integer(left).to_int(unsigned=True)) | right.to_integer().to_int(unsigned=True),
        unsigned=True)


##############################################################################
# unary operations

def abs_(args):
    """Return the absolute value of a number. No-op for strings."""
    inp, = args
    if isinstance(inp, strings.String):
        # strings pass unchanged
        return inp
    # promote Integer to Single to avoid integer overflow on -32768
    return inp.to_float().clone().iabs()

def neg(inp):
    """Negation (unary -). No-op for strings."""
    if isinstance(inp, strings.String):
        # strings pass unchanged
        return inp
    # promote Integer to Single to avoid integer overflow on -32768
    return inp.to_float().clone().ineg()

def sgn_(args):
    """Sign."""
    x, = args
    return numbers.Integer(None, x._values).from_int(pass_number(x).sign())

def int_(args):
    """Truncate towards negative infinity (INT)."""
    inp, = args
    if isinstance(inp, strings.String):
        # strings pass unchanged
        return inp
    return inp.clone().ifloor()

def fix_(args):
    """Truncate towards zero."""
    inp, = args
    return pass_number(inp).clone().itrunc()

def sqr_(args):
    """Square root."""
    x, = args
    return _call_float_function(math.sqrt, x)

def exp_(args):
    """Exponential."""
    x, = args
    return _call_float_function(math.exp, x)

def sin_(args):
    """Sine."""
    x, = args
    return _call_float_function(lambda _x: math.sin(_x) if abs(_x) < TRIG_MAX else 0., x)

def cos_(args):
    """Cosine."""
    x, = args
    return _call_float_function(lambda _x: math.cos(_x) if abs(_x) < TRIG_MAX else 1., x)

def tan_(args):
    """Tangent."""
    x, = args
    return _call_float_function(lambda _x: math.tan(_x) if abs(_x) < TRIG_MAX else 0., x)

def atn_(args):
    """Inverse tangent."""
    x, = args
    return _call_float_function(math.atan, x)

def log_(args):
    """Logarithm."""
    x, = args
    return _call_float_function(math.log, x)


######################################################################
# string representations and characteristics

def to_repr(inp, leading_space, type_sign):
    """Convert BASIC number to Python bytes representation."""
    # PRINT, STR$ - yes leading space, no type sign
    # WRITE - no leading space, no type sign
    # LIST - no loading space, yes type sign
    if isinstance(inp, numbers.Number):
        return inp.to_str(leading_space, type_sign)
    elif isinstance(inp, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    raise TypeError('%s is not of class Value' % type(inp))

def str_(args):
    """STR$: string representation of a number."""
    x, = args
    return x._values.new_string().from_str(
        to_repr(pass_number(x), leading_space=True, type_sign=False)
    )

def val_(args):
    """VAL: number value of a string."""
    x, = args
    return x._values.from_repr(pass_string(x).to_str(), allow_nonnum=True)

def len_(args):
    """LEN: length of string."""
    s, = args
    return pass_string(s).len()

def space_(args):
    """SPACE$: repeat spaces."""
    num, = args
    return num._values.new_string().space(pass_number(num))

def asc_(args):
    """ASC: ordinal ASCII value of a character."""
    s, = args
    return pass_string(s).asc()

def chr_(args):
    """CHR$: character for ASCII value."""
    x, = args
    val = pass_number(x).to_integer().to_int()
    error.range_check(0, 255, val)
    return x._values.new_string().from_str(int2byte(val))

def oct_(args):
    """OCT$: octal representation of int."""
    x, = args
    # allow range -32768 to 65535
    val = to_integer(x, unsigned=True)
    return x._values.new_string().from_str(val.to_oct())

def hex_(args):
    """HEX$: hexadecimal representation of int."""
    x, = args
    # allow range -32768 to 65535
    val = to_integer(x, unsigned=True)
    return x._values.new_string().from_str(val.to_hex())

##############################################################################
# sring operations

def left_(args):
    """LEFT$: get substring of num characters at the start of string."""
    s, num = next(args), next(args)
    s, num = pass_string(s), to_integer(num)
    list(args)
    stop = num.to_integer().to_int()
    if stop == 0:
        return s.new()
    error.range_check(0, 255, stop)
    return s.new().from_str(s.to_str()[:stop])

def right_(args):
    """RIGHT$: get substring of num characters at the end of string."""
    s, num = next(args), next(args)
    s, num = pass_string(s), to_integer(num)
    list(args)
    stop = num.to_integer().to_int()
    if stop == 0:
        return s.new()
    error.range_check(0, 255, stop)
    return s.new().from_str(s.to_str()[-stop:])

def mid_(args):
    """MID$: get substring."""
    s, start = next(args), to_integer(next(args))
    p = pass_string(s)
    num = next(args)
    if num is not None:
        num = to_integer(num)
    list(args)
    length = s.length()
    start = start.to_integer().to_int()
    if num is None:
        num = length
    else:
        num = num.to_integer().to_int()
    error.range_check(1, 255, start)
    error.range_check(0, 255, num)
    if num == 0 or start > length:
        return s.new()
    # BASIC's indexing starts at 1, Python's at 0
    start -= 1
    return s.new().from_str(s.to_str()[start:start+num])

def instr_(args):
    """INSTR: find substring in string."""
    arg0 = next(args)
    if isinstance(arg0, numbers.Number):
        start = to_int(arg0)
        error.range_check(1, 255, start)
        big = pass_string(next(args))
    else:
        start = 1
        big = pass_string(arg0)
    small = pass_string(next(args))
    list(args)
    new_int = numbers.Integer(None, big._values)
    big = big.to_str()
    small = small.to_str()
    if big == b'' or start > len(big):
        return new_int
    # BASIC counts string positions from 1
    find = big[start-1:].find(small)
    if find == -1:
        return new_int
    return new_int.from_int(start + find)

def string_(args):
    """STRING$: repeat a character num times."""
    num = to_int(next(args))
    error.range_check(0, 255, num)
    asc_value_or_char = next(args)
    if isinstance(asc_value_or_char, numbers.Integer):
        error.range_check(0, 255, asc_value_or_char.to_int())
    list(args)
    if isinstance(asc_value_or_char, strings.String):
        char = asc_value_or_char.to_str()[:1]
    else:
        # overflow if outside Integer range
        ascval = asc_value_or_char.to_integer().to_int()
        error.range_check(0, 255, ascval)
        char = int2byte(ascval)
    return strings.String(None, asc_value_or_char._values).from_str(char * num)

##############################################################################
# binary operations

@float_safe
def pow(left, right):
    """Left^right."""
    if isinstance(left, strings.String) or isinstance(right, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    if left._values.double_math and (
            isinstance(left, numbers.Double) or isinstance(right, numbers.Double)
        ):
        return _call_float_function(lambda a, b: a**b, to_double(left), to_double(right))
    elif isinstance(right, numbers.Integer):
        return left.to_single().clone().ipow_int(right)
    else:
        return _call_float_function(lambda a, b: a**b, to_single(left), to_single(right))

@float_safe
def add(left, right):
    """Add two numbers or concatenate two strings."""
    if isinstance(left, numbers.Number):
        # promote Integer to Single to avoid integer overflow
        left = left.to_float()
    left, right = match_types(left, right)
    # note that we can't call iadd here, as it breaks with strings
    # since between copy and dereference the address may change due to garbage collection
    # it may be better to define non-in-place operators for everything
    return left.add(right)

@float_safe
def sub(left, right):
    """Subtract two numbers."""
    if isinstance(left, strings.String) or isinstance(right, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    # promote Integer to Single to avoid integer overflow
    left, right = match_types(left.to_float(), right)
    return left.clone().isub(right)


@float_safe
def mul(left, right):
    """Left*right."""
    if isinstance(left, strings.String) or isinstance(right, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    elif isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
        return left.to_double().clone().imul(right.to_double())
    else:
        return left.to_single().clone().imul(right.to_single())

@float_safe
def div(left, right):
    """Left/right."""
    if isinstance(left, strings.String) or isinstance(right, strings.String):
        raise error.BASICError(error.TYPE_MISMATCH)
    elif isinstance(left, numbers.Double) or isinstance(right, numbers.Double):
        return left.to_double().clone().idiv(right.to_double())
    else:
        return left.to_single().clone().idiv(right.to_single())

@float_safe
def intdiv(left, right):
    """Left\\right."""
    return to_integer(left).clone().idiv_int(to_integer(right))

@float_safe
def mod_(left, right):
    """Left modulo right."""
    return to_integer(left).clone().imod(to_integer(right))


# conversions to type
TYPE_TO_CONV = {STR: pass_string, INT: to_integer, SNG: to_single, DBL: to_double}
