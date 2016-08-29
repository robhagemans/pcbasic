"""
PC-BASIC - numbers.py
Integer and Floating Point values

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

# descriptions of the Microsoft Binary Format found here:
# http://www.experts-exchange.com/Programming/Languages/Pascal/Delphi/Q_20245266.html
# http://www.boyet.com/Articles/MBFSinglePrecision.html
#
# single precision:                      m3 | m2 | m1 | exponent
# double precision:  m7 | m6 | m5 | m4 | m3 | m2 | m1 | exponent
# where:
#     m1 is most significant byte => sbbb|bbbb
#     m7 is the least significant byte
#     m = mantissa byte
#     s = sign bit
#     b = bit
#
# The exponent is biased by 128.
# There is an assumed 1 bit after the radix point (so the assumed mantissa is 0.1ffff... where f's are the fraction bits)

import struct
import math

from . import basictoken as tk
from . import error


##############################################################################
# value base class

class Value(object):
    """Abstract base class for value types"""

    sigil = None
    size = None

    def __init__(self, buffer=None):
        """Initialise the value"""
        if buffer is None:
            buffer = memoryview(bytearray(self.size))
        self._buffer = memoryview(buffer)

    def clone(self):
        """Create a temporary copy"""
        return self.__class__().from_bytes(self._buffer)

    def copy_from(self, other):
        """Copy another value into this one"""
        self._buffer[:] = other._buffer
        return self

    def to_bytes(self):
        """Get a copy of the byte representation"""
        return bytearray(self._buffer)

    def from_bytes(self, in_bytes):
        """Copy a new byte representation into the value"""
        self._buffer[:] = in_bytes
        return self

    def view(self):
        """Get a reference to the storage space"""
        return self._buffer


##############################################################################
# numeric value base class

class Number(Value):
    """Abstract base class for numeric value"""

    zero = None
    pos_max = None
    neg_max = None

    def __str__(self):
        """String representation for debugging."""
        return '[%s] %s %s' % (str(self.to_bytes()).encode('hex'), self.to_value(), self.sigil)

    def to_value(self):
        """Convert to Python value."""


##############################################################################
# integer number

class Integer(Number):
    """16-bit signed little-endian integer"""

    sigil = '%'
    size = 2

    def is_zero(self):
        """Value is zero"""
        return self._buffer == '\0\0'

    def is_negative(self):
        """Value is negative"""
        return (ord(self._buffer[-1]) & 0x80) != 0

    def sign(self):
        """Sign of value"""
        return -1 if (ord(self._buffer[-1]) & 0x80) != 0 else (0 if self._buffer == '\0\0' else 1)

    def to_int(self):
        """Return value as Python int"""
        return struct.unpack('<h', self._buffer)[0]

    def from_int(self, in_int):
        """Set value to Python int"""
        if not (-0x8000 <= in_int <= 0x7fff):
            self.copy_from(self.neg_max if in_int < 0 else self.pos_max)
            raise OverflowError(self)
        struct.pack_into('<h', self._buffer, 0, in_int)
        return self

    to_value = to_int
    from_value = from_int

    def to_unsigned(self):
        """Return value as unsigned Python int"""
        return struct.unpack('<H', self._buffer)[0]

    def from_unsigned(self, in_int):
        """Set value to unsigned Python int"""
        # we can in fact assign negatives as 'unsigned'
        if not (-0x8000 <= in_int <= 0xffff):
            self.copy_from(self.neg_max if in_int < 0 else self.pos_max)
            raise OverflowError(self)
        if in_int < 0:
            in_int += 0xffff
        struct.pack_into('<H', self._buffer, 0, in_int)
        return self

    def to_token(self):
        """Return signed value as integer token"""
        if self._buffer[1] == '\0':
            byte = ord(self._buffer[0])
            if byte <= 10:
                return chr(ord(tk.C_0) + byte)
            else:
                return tk.T_BYTE + self._buffer[0]
        else:
            return tk.T_INT + self._buffer[:]

    def to_token_linenum(self):
        """Return unsigned value as line number token"""
        return tk.T_UINT + self._buffer[:]

    def to_token_hex(self):
        """Return unsigned value as hex token"""
        return tk.T_HEX + self._buffer[:]

    def to_token_oct(self):
        """Return unsigned value as oct token"""
        return tk.T_OCT + self._buffer[:]

    def from_token(self, token):
        """Set value to signed or unsigned integer token"""
        d = token[0]
        if d in (tk.T_OCT, tk.T_HEX, tk.T_INT, tk.T_UINT):
            self._buffer[:] = token[-2:]
        elif d == tk.T_BYTE:
            self._buffer[:] = token[-1] + '\0'
        elif d >= tk.C_0 and d <= tk.C_10:
            self._buffer[:] = chr(ord(d) - 0x11) + '\0'
        else:
            raise ValueError()
        return self

    # operations

    def ineg(self):
        """Negate in-place"""
        self._buffer[-1]  = chr(ord(self._buffer[-1]) ^ 0x80)
        return self

    def iabs(self):
        """Absolute value in-place"""
        self._buffer[-1] = chr(ord(self._buffer[-1]) & 0x7F)
        return self

    def iadd(self, rhs):
        """Add another Integer in-place"""
        if (ord(self._buffer[-1]) & 0x80) != (ord(rhs._buffer[-1]) & 0x80):
            return self.ineg().isub(rhs).ineg()
        lsb = ord(self._buffer[0]) + ord(rhs._buffer[0])
        msb = ord(self._buffer[1]) + ord(rhs._buffer[1])
        self._carry_list(lsb, msb)
        return self

    def isub(self, rhs):
        """Subtract another Integer in-place"""
        if (ord(self._buffer[-1]) & 0x80) != (ord(rhs._buffer[-1]) & 0x80):
            return self.ineg().iadd(rhs).ineg()
        lsb = ord(self._buffer[0]) - ord(rhs._buffer[0])
        msb = ord(self._buffer[1]) - ord(rhs._buffer[1])
        self._carry_list(lsb, msb)
        return self

    # no imul - we always promote to float first for multiplication
    # no idiv - we always promote to float first for true division

    def idiv_int(self, rhs):
        """Perform integer division."""
        if rhs.is_zero():
            # division by zero - return single-precision maximum
            raise ZeroDivisionError(Single.neg_max if self.is_negative() else Single.pos_max)
        dividend = self.to_int()
        divisor = rhs.to_int()
        # BASIC intdiv rounds to zero, Python's floordiv to -inf
        if (dividend >= 0) == (divisor >= 0):
            return self.from_int(dividend // divisor)
        else:
            return self.from_int(-(abs(dividend) // abs(divisor)))

    def imod(self, rhs):
        """Left modulo right."""
        if rhs.is_zero():
            # division by zero - return single-precision maximum
            raise ZeroDivisionError(Single.neg_max if self.is_negative() else Single.pos_max)
        dividend = self.to_int()
        divisor = rhs.to_int()
        # BASIC MOD has same sign as dividend, Python mod has same sign as divisor
        mod = dividend % divisor
        if dividend < 0 or mod < 0:
            mod -= divisor
        return self.from_int(mod)

    # relations

    def gt(self, rhs):
        """Greater than"""
        if isinstance(rhs, Float):
            # upgrade to Float
            return rhs.__class__().from_integer(self).gt(rhs)
        isneg = ord(self._buffer[-1]) & 0x80
        if isneg != (ord(rhs._buffer[-1]) & 0x80):
            return not(isneg)
        if isneg:
            return rhs._abs_gt(self)
        return self._abs_gt(rhs)

    def eq(self, rhs):
        """Equals"""
        if isinstance(rhs, Float):
            # upgrade to Float
            return rhs.__class__().from_integer(self).eq(rhs)
        return self._buffer == rhs._buffer

    # implementation

    def _abs_gt(self, rhs):
        """Absolute values greater than"""
        lmsb = ord(self._buffer[1] & 0x7f)
        rmsb = ord(rhs._buffer[1] & 0x7f)
        if lmsb > rmsb:
            return True
        elif lmsb < rmsb:
            return False
        return ord(self._buffer[0]) > ord(rhs._buffer[0])

    def _carry_list(self, lsb, msb):
        """Check for overflow and assign"""
        if lsb > 0xff:
            lsb -= 0xff
            msb += 1
        elif lsb < 0:
            lsb += 0xff
            msb -= 1
        if not (0 <= msb <= 0xff):
            self.copy_from(self.neg_max if msb & 0x80 != 0 else self.pos_max)
            raise OverflowError(self)
        self._buffer[:] = chr(lsb) + chr(msb)


Integer.pos_max = Integer('\xff\x7f')
Integer.neg_max = Integer('\xff\xff')


##############################################################################
# floating-point base class

class Float(Number):
    """Abstract base class for floating-point value"""

    digits = None
    pos_max = None
    neg_max = None

    def __init__(self, buffer=None):
        """Initialise float."""
        Number.__init__(self, buffer)

    # properties

    def is_zero(self):
        """Value is zero"""
        return self._buffer[-1] == '\0'

    def is_negative(self):
        """Value is negative"""
        return self._buffer[-2] >= '\x80'

    def sign(self):
        """Sign of value"""
        return 0 if self._buffer[-1] == '\0' else (-1 if (ord(self._buffer[-2]) & 0x80) != 0 else 1)

    # BASIC type conversions

    def from_integer(self, in_integer):
        """Convert Integer to single, in-place"""
        return self.from_int(in_integer.to_int())

    # Python float conversions

    def to_float(self):
        """Return value as Python float"""
        exp = ord(self._buffer[-1]) - self._bias
        if exp == -self._bias:
            return 0.
        # unpack as unsigned long int
        man = struct.unpack(self._intformat, bytearray(self._buffer[:-1]) + '\0')[0]
        # prepend assumed bit and apply sign
        if man & self._signmask:
            man = -man
        else:
            man |= self._signmask
        return man * 2.**exp

    def from_float(self, in_float):
        """Set to value of Python float."""
        if in_float == 0.:
            self._buffer[:] = '\0'*self.size
        neg = in_float < 0
        exp = int(math.log(abs(in_float), 2) - self._shift)
        man = int(abs(in_float) * 0.5**exp)
        exp += self._bias
        # why do we need this here?
        man, exp = self._bring_to_range(man, exp, self._posmask, self._mask)
        if not self._check_limits(exp, neg):
            return self
        struct.pack_into(self._intformat, self._buffer, 0, man & (self._mask if neg else self._posmask))
        self._buffer[-1] = chr(exp)
        return self

    to_value = to_float
    from_value = from_float


    # Python int conversions

    def to_int(self):
        """Return value rounded to Python int"""
        man, neg = self._to_int_den()
        # carry: round to nearest, halves away from zero
        if man & 0x80:
            man += 0x80
        # note that -man >> 8 and -(man >> 8) are different
        # due to Python's rounding rules
        return -(man >> 8) if neg else man >> 8

    def from_int(self, in_int):
        """Set value to Python int"""
        if in_int == 0:
            self._buffer[:] = '\0'*self.size
        else:
            neg = in_int < 0
            man, exp = self._bring_to_range(abs(in_int), self._bias, self._posmask, self._mask)
            if not self._check_limits(exp, neg):
                return self
            struct.pack_into(self._intformat, self._buffer, 0, man & (self._mask if neg else self._posmask))
            self._buffer[-1] = chr(exp)
        return self

    def to_int_truncate(self):
        """Truncate float to integer."""
        man, neg = self._to_int_den()
        # discard carry
        return -(man >> 8) if neg else man >> 8

    def mantissa(self):
        """Integer value of mantissa."""
        exp, man, neg = self._denormalise()
        return -(man >> 8) if neg else (man >> 8)

    # in-place unary operations

    def ineg(self):
        """Negate in-place"""
        self._buffer[-2] = chr(ord(self._buffer[-2]) ^ 0x80)
        return self

    def iabs(self):
        """Absolute value in-place"""
        self._buffer[-2] = chr(ord(self._buffer[-2]) & 0x7F)
        return self

    def iround(self):
        """In-place. Round and return as float."""
        return self.from_int(self.to_int())

    def itrunc(self):
        """In-place. Truncate towards zero and return as float."""
        return self.from_int(self.to_int_truncate())

    def ifloor(self):
        """In-place. Truncate towards negative infinity and return as float."""
        if self.is_negative():
            self.itrunc().isub(self._one)
        else:
            self.itrunc()
        return self

    # relations

    def gt(self, rhs):
        """Greater than"""
        if isinstance(rhs, Integer):
            # upgrade rhs to Float
            return self.gt(self.__class__().from_integer(rhs))
        elif isinstance(rhs, Double) and isinstance(self, Single):
            # upgrade to Double
            return Double().from_single(self).gt(rhs)
        rhsneg = rhs.is_negative()
        # treat zero separately to avoid comparing different mantissas
        # zero is only greater than negative
        if self.is_zero():
            return bool(rhsneg) and not rhs.is_zero()
        isneg = self.is_negative()
        if isneg != rhsneg:
            return not(isneg)
        if isneg:
            return rhs._abs_gt(self)
        return self._abs_gt(rhs)

    def eq(self, rhs):
        """Equals"""
        if isinstance(rhs, Integer):
            # upgrade rhs to Float
            return self.eq(self.__class__().from_integer(rhs))
        elif isinstance(rhs, Double) and isinstance(self, Single):
            # upgrade to Double
            return Double().from_single(self).eq(rhs)
        # all zeroes are equal
        if self.is_zero():
            return rhs.is_zero()
        return self._buffer == rhs._buffer

    # in-place binary operations

    def iadd(self, right):
        """Add in-place"""
        return self._normalise(*self._add_den(self._denormalise(), right._denormalise()))

    def isub(self, right):
        """Subtract in-place"""
        rexp, rman, rneg = right._denormalise()
        return self._normalise(*self._add_den(self._denormalise(), (rexp, rman, not rneg)))

    def imul(self, right_in):
        """Multiply in-place"""
        global lden_s, rden_s, sden_s
        if self.is_zero() or right_in.is_zero():
            # set any zeroes to standard zero
            self._buffer[:] = '\0' * self.size
            return self
        lexp, lman, lneg = self._denormalise()
        rexp, rman, rneg = right_in._denormalise()
        lden_s, rden_s = lman, rman
        lexp += rexp - right_in._bias - 8
        lneg = (lneg != rneg)
        lman *= rman
        sden_s = lman
        if lexp < -31:
            self._buffer[:] = '\0' * self.size
            return self._buffer
        # drop some precision
        lman, lexp = self._bring_to_range(lman, lexp, self._den_mask>>4, self._den_upper>>4)
        # rounding quirk
        if lman & 0xf == 0x9:
            #FIXME: single only?
            lman &= 0xfffffffffe
        self._normalise(lexp, lman, lneg)
        return self

    def idiv(self, right_in):
        """Divide in-place."""
        if right_in.is_zero():
            # division by zero - return max float with the type and sign of self
            self.copy_from(self.neg_max if self.is_negative() else self.pos_max)
            raise ZeroDivisionError(self)
        if self.is_zero():
            return self
        lexp, lman, lneg = self._div_den(self._denormalise(), right_in._denormalise())
        # normalise and return
        return self._normalise(lexp, lman, lneg)

    def ipow_int(self, expt):
        """Raise to integer power in-place."""
        return self._ipow_int(expt.to_int())


    # decimal representations

    def to_decimal(self, digits=None):
        """Return value as mantissa and decimal exponent."""
        if digits is None:
            # we'd be better off storing these (and self._ten) in denormalised form
            lim_bot, lim_top = self._lim_bot, self._lim_top
            digits = self.digits
        elif digits > 0:
            lim_bot = self.__class__().from_int(10**(digits-1))._just_under()
            lim_top = self.__class__().from_int(10**digits)._just_under()
        else:
            return 0, 0
        tden = lim_top._denormalise()
        bden = lim_bot._denormalise()
        exp10 = 0
        den = self._denormalise()
        while self._abs_gt_den(den, tden):
            den = self._div10_den(den)
            exp10 += 1
        # rounding - gets us close to GW results
        den = self._apply_carry_den(den)
        while self._abs_gt_den(bden, den):
            den = self._mul10_den(den)
            exp10 -= 1
        # rounding - gets us close to GW results
        den = self._apply_carry_den(den)
        # round to int
        exp, man, neg = den
        exp -= self._bias
        if exp > 0:
            man <<= exp
        else:
            man >>= -exp
        if man & 0x80:
            man += 0x80
        num = -(man >> 8) if neg else man >> 8
        return num, exp10

    def from_decimal(self, mantissa, exp10):
        """Set value to mantissa and decimal exponent."""
        den = self.from_int(mantissa)._denormalise()
        # apply decimal exponent
        while (exp10 < 0):
            den = self._div10_den(den)
            exp10 += 1
        while (exp10 > 0):
            den = self._mul10_den(den)
            exp10 -= 1
        return self._normalise(*den)

    ##########################################################################
    # implementation: decimal representations only

    _one = None
    _ten = None
    _lim_bot = None
    _lim_top = None

    def _apply_carry_den(self, den):
        """Round the carry byte (to be used only in to_decimal)."""
        exp, man, neg = den
        # apply_carry()
        # carry bit set? then round up
        if (man & 0xff) > 0x7f:
            man += 0x100
        # overflow?
        if man >= self._den_upper:
            exp += 1
            man >>= 1
        # discard carry
        man ^= man & 0xff
        return exp, man, neg

    def _just_under(self):
        """Return the largest floating-point number less than the given value."""
        lexp, lman, lneg = self._denormalise()
        # decrease mantissa by one
        return self.__class__()._normalise(lexp, lman - 0x100, lneg)

    def _abs_gt_den(self, lden, rden):
        """Absolute value is greater than."""
        lexp, lman, _ = lden
        rexp, rman, _ = rden
        if lexp != rexp:
            return (lexp > rexp)
        return (lman > rman)

    def _div10_den(self, lden):
        """Divide by 10 in-place."""
        exp, man, neg = self._div_den(lden, self._ten._denormalise())
        # perhaps this should be in _div_den
        while man < self._den_mask:
            exp -= 1
            man <<= 1
        return exp, man, neg

    def _mul10_den(self, den):
        """Multiply in-place by 10"""
        exp, man, neg = den
        # 10x == 2(x+4x)
        return self._add_den((exp+1, man, neg), (exp+3, man, neg))


    ##########################################################################
    # implementation: general

    _bias = None
    _shift = None
    _intformat = None
    _mask = None
    _posmask = None
    _signmask = None
    _den_mask = None
    _den_upper = None

    def _denormalise(self):
        """Denormalise to shifted mantissa, exp, sign"""
        exp = ord(self._buffer[-1])
        man = struct.unpack(self._intformat, '\0' + bytearray(self._buffer[:-1]))[0] | self._den_mask
        neg = self.is_negative()
        return exp, man, neg

    def _normalise(self, exp, man, neg):
        """Normalise from shifted mantissa, exp, sign"""
        global pden_s
        # zero denormalised mantissa -> make zero
        if man == 0 or exp <= 0:
            self._buffer[:] = '\0' * self.size
            return self
        # shift left if subnormal
        while man < (self._den_mask-1):
            exp -= 1
            man <<= 1
        pden_s = man
        # round to nearest; halves to even (Gaussian rounding)
        round_up = (man & 0xff > 0x80) or (man & 0xff == 0x80 and man & 0x100 == 0x100)
        man = (man ^ (man & 0xff)) + 0x100 * round_up
        if man >= self._den_upper:
            exp += 1
            man >>= 1
        # pack into byte representation
        struct.pack_into(self._intformat, self._buffer, 0, (man>>8) & (self._mask if neg else self._posmask))
        if self._check_limits(exp, neg):
            self._buffer[-1] = chr(exp)
        return self

    def _to_int_den(self):
        """Denormalised float to integer."""
        exp, man, neg = self._denormalise()
        exp -= self._bias
        if exp > 0:
            man <<= exp
        else:
            man >>= -exp
        return man, neg

    def _check_limits(self, exp, neg):
        """Overflow and underflow check
        returns:
            True if nonzero non-infinite
            False if underflow
        raises:
            OverflowError if overflow
        """
        if exp > 255:
            self.copy_from(self.neg_max if neg else self.pos_max)
            raise OverflowError(self)
        elif exp <= 0:
            # set to zero, but leave mantissa as is
            self._buffer[-1:] = chr(0)
            return False
        return True

    def _bring_to_range(self, man, exp, lower, upper):
        """Bring mantissa to range (posmask, mask]"""
        while abs(man) <= lower:
            exp -= 1
            man <<= 1
        while abs(man) > upper:
            exp += 1
            man >>= 1
        return man, exp

    def _abs_gt(self, rhs):
        """Absolute values greater than"""
        # don't compare zeroes
        if self.is_zero():
            return False
        rhscopy = bytearray(rhs._buffer)
        # so long as the sign is the same ...
        rhscopy[-2] &= (ord(self._buffer[-2]) | 0x7f)
        # ... we can compare floats as if they were ints
        for l, r in reversed(zip(self._buffer, rhscopy)):
            # memoryview elements are str, bytearray elements are int
            if ord(l) > r:
                return True
            elif ord(l) < r:
                return False
        # equal
        return False

    def _add_den(self, lden, rden):
        """ Denormalised add. """
        lexp, lman, lneg = lden
        rexp, rman, rneg = rden
        global lden_s, rden_s, sden_s
        if rexp == 0:
            return lexp, lman, lneg
        if lexp == 0:
            return rexp, rman, rneg
        # ensure right is larger
        if lexp > rexp or (lexp == rexp and lman > rman):
            lexp, lman, lneg, rexp, rman, rneg = rexp, rman, rneg, lexp, lman, lneg
        # zero flag for quirky rounding
        # only set if all the bits we lose by matching exponents were zero
        zero_flag = lman & ((1<<(rexp-lexp))-1) == 0
        sub_flag = lneg != rneg
        # match exponents
        lman >>= (rexp - lexp)
        lexp = rexp
        lden_s = lman
        rden_s = rman
        # shortcut (this affects quirky rounding)
        if (lman < 0x80 or lman == 0x80 and zero_flag) and sub_flag:
            return rexp, rman, rneg
        # add mantissas, taking sign into account
        if not sub_flag:
            man, neg = lman + rman, lneg
            if man >= self._den_upper:
                lexp += 1
                man >>= 1
        else:
            man, neg = rman - lman, rneg
        # break tie for rounding if we're at exact half after dropping digits
        if not zero_flag and not sub_flag:
            man |= 0x1
        # attempt to match GW-BASIC subtraction rounding
        sden_s = -man if sub_flag else man
        if sub_flag and (man & 0x1c0 == 0x80) and (man & 0x1df != 0x80):
            # FIXME: single only?
            man &= 0xffffffff7f
        return lexp, man, neg

    def _ipow_int(self, expt):
        """Raise to int power in-place."""
        # exponentiation by squares
        if expt < 0:
            self._ipow_int(-expt)
            self = self._one.clone().idiv(self)
        elif expt > 1:
            if (expt % 2) == 0:
                self._ipow_int(expt // 2)
                self.imul(self)
            else:
                base = self.clone()
                self._ipow_int((expt-1) // 2)
                self.imul(self)
                self.imul(base)
        elif expt == 0:
            self = self._one.clone()
        return self

    def _div_den(self, lden, rden):
        """Denormalised divide."""
        lexp, lman, lneg = lden
        rexp, rman, rneg = rden
        # signs
        lneg = (lneg != rneg)
        # subtract exponentials
        lexp -= rexp - self._bias - 8
        # long division of mantissas
        work_man = lman
        lman = 0
        lexp += 1
        while (rman > 0):
            lman <<= 1
            lexp -= 1
            if work_man > rman:
                work_man -= rman
                lman += 1
            rman >>= 1
        return lexp, lman, lneg



##############################################################################
# single-precision floating-point number

class Single(Float):
    """Single-precision MBF float"""

    sigil = '!'
    size = 4

    exp_sign = 'E'
    digits = 7

    _intformat = '<L'

    _bias = 128 + 24
    _shift = _bias - 129

    _den_mask = 0x80000000
    _den_upper = _den_mask * 2
    _signmask = 0x800000
    _mask = 0xffffff
    _posmask = 0x7fffff

    def to_token(self):
        """Return value as Single token"""
        return tk.T_SINGLE + self._buffer[:]

    def from_token(self, token):
        """Set value to Single token"""
        if token[0] != tk.T_SINGLE:
            raise ValueError()
        self._buffer[:] = token[-4:]
        return self

    def to_single(self):
        """Convert single to single (no-op)."""
        return self


Single.pos_max = Single('\xff\xff\x7f\xff')
Single.neg_max = Single('\xff\xff\xff\xff')

Single._one = Single('\x00\x00\x00\x81')
Single._ten = Single('\x00\x00\x20\x84')
Single._lim_top = Single('\x7f\x96\x18\x98') # 9999999, highest float less than 10e+7
Single._lim_bot = Single('\xff\x23\x74\x94') # 999999.9, highest float  less than 10e+6


###############################################################################
# double-precision floating-point number

class Double(Float):
    """Double-precision MBF float"""

    sigil = '#'
    size = 8

    exp_sign = 'D'
    digits = 16

    _intformat = '<Q'

    _bias = 128 + 56
    _shift = _bias - 129

    _den_mask = 0x8000000000000000
    _den_upper = _den_mask * 2

    _signmask = 0x80000000000000
    _mask = 0xffffffffffffff
    _posmask = 0x7fffffffffffff

    def from_single(self, in_single):
        """Convert Single to Double in-place"""
        self._buffer[:4] = '\0\0\0\0'
        self._buffer[4:] = in_single._buffer

    def to_token(self):
        """Return value as Single token"""
        return tk.T_DOUBLE + self._buffer[:]

    def from_token(self, token):
        """Set value to Single token"""
        if token[0] != tk.T_DOUBLE:
            raise ValueError()
        self._buffer[:] = token[-8:]
        return self

    def to_single(self):
        """Round double to single."""
        mybytes = self.to_bytes()
        single = Single().from_bytes(mybytes[4:])
        exp, man, neg = single._denormalise()
        # carry byte
        man += mybytes[3]
        return single._normalise(exp, man, neg)


Double.pos_max = Double('\xff\xff\xff\xff\xff\xff\x7f\xff')
Double.neg_max = Double('\xff\xff\xff\xff\xff\xff\xff\xff')

Double._one = Double('\x00\x00\x00\x00\x00\x00\x00\x81')
Double._ten = Double('\x00\x00\x00\x00\x00\x00\x20\x84')
Double._lim_top = Double('\xff\xff\x03\xbf\xc9\x1b\x0e\xb6') # highest float less than 10e+16
Double._lim_bot = Double('\xff\xff\x9f\x31\xa9\x5f\x63\xb2') # highest float less than 10e+15


###############################################################################
# error handling

def float_safe(fn):
    """Decorator to handle floating point errors."""
    def wrapped_fn(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except (ValueError, ArithmeticError) as e:
            return self._float_error_handler.handle(e)
    return wrapped_fn


class FloatErrorHandler(object):
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
        if e.args and e.args[0]:
            if isinstance(e.args[0], Float):
                return e.args[0]
            elif isinstance(e.args[0], Integer):
                # integer values are not soft-handled
                raise e
        return Single.pos_max

##############################################################################

def from_token(token):
    """Convert number token to new Number temporary"""
    if token[0] == tk.T_SINGLE:
        return Single().from_token(token)
    elif token[0] == tk.T_DOUBLE:
        return Double().from_token(token)
    else:
        return Integer().from_token(token)


lden_s, rden_s, sden_s, pden_s = 0,0,0,0
