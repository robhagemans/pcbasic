"""
PC-BASIC - values.py
Value classes - String, Integer and Floating Point

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

import basictoken as bt

class Value(object):
    """Abstract base class for value types"""

    sigil = None
    size = None

    def __init__(self, buffer=None):
        """Initialise the value"""
        if buffer is None:
            buffer = memoryview(bytearray(self.size))
        self.buffer = memoryview(buffer)

    #RENAME clone()
    def temp_copy(self):
        """Create a temporary copy"""
        return self.__class__().from_bytes(self.buffer)

    def to_bytes(self):
        """Get a copy of the byte representation"""
        return bytearray(self.buffer)

    def from_bytes(self, in_bytes):
        """Copy a new byte representation into the value"""
        self.buffer[:] = in_bytes
        return self

    def view(self):
        """Get a reference to the storage space"""
        return self.buffer



class String(Value):
    """String pointer"""

    sigil = '$'
    size = 3

    def __init__(self, buffer, stringspace):
        """Initialise the pointer"""
        Value.__init__(buffer)
        self.stringspace = memoryview(stringspace)

    def length(self):
        """String length"""
        return ord(self.buffer[0])

    def address(self):
        """Pointer address"""
        return struct.unpack_from('<H', self.buffer, 1)[0]

    def dereference(self):
        """String value pointed to"""
        return bytearray(self.stringspace[self.address:self.address+self.length])

    value = dereference


class Number(Value):
    """Abstract base class for numeric value"""


class Integer(Number):
    """16-bit signed little-endian integer"""

    sigil = '%'
    size = 2

    zero = '\0\0'
    pos_max = '\xff\x7f'
    neg_max = '\xff\xff'

    def is_zero(self):
        """Value is zero"""
        return self.buffer == '\0\0'

    def sign(self):
        """Sign of value"""
        return -1 if (ord(self.buffer[-1]) & 0x80) != 0 else (0 if self.buffer == '\0\0' else 1)

    def to_int(self):
        """Return value as Python int"""
        return struct.unpack('<h', self.buffer)[0]

    def from_int(self, in_int):
        """Set value to Python int"""
        if not (-0x8000 <= in_int <= 0x7fff):
            raise OverflowError()
        struct.pack_into('<h', self.buffer, 0, in_int)
        return self

    value = to_int

    def to_unsigned(self):
        """Return value as unsigned Python int"""
        return struct.unpack('<H', self.buffer)[0]

    def from_unsigned(self):
        """Set value to unsigned Python int"""
        # we can in fact assign negatives as 'unsigned'
        if not (-0x8000 <= in_int <= 0xffff):
            raise OverflowError()
        if in_int < 0:
            in_int += 0xffff
        struct.pack_into('<H', self.buffer, 0, in_int)
        return self

    def to_token(self):
        """Return signed value as integer token"""
        if self.buffer[1] == '\0':
            byte = ord(self.buffer[0])
            if byte <= 10:
                return chr(ord(tk.C_0) + byte)
            else:
                return tk.T_BYTE + self.buffer[0]
        else:
            return tk.T_INT + self.buffer[:]

    def to_token_linenum(self):
        """Return unsigned value as line number token"""
        return tk.T_UINT + self.buffer[:]

    def to_token_hex(self):
        """Return unsigned value as hex token"""
        return tk.T_HEX + self.buffer[:]

    def to_token_hex(self):
        """Return unsigned value as oct token"""
        return tk.T_OCT + self.buffer[:]

    def from_token(self, token):
        """Set value to signed or unsigned integer token"""
        d = token[0]
        if d in (tk.T_OCT, tk.T_HEX, tk.T_INT, tk.T_UINT):
            self.buffer[:] = token[-2:]
        elif d == tk.T_BYTE:
            self.buffer[:] = token[-1] + '\0'
        elif d >= tk.C_0 and d <= tk.C_10:
            self.buffer[:] = chr(ord(d) - 0x11) + '\0'
        else:
            raise ValueError()
        return self

    # operations

    def ineg(self):
        """Negate in-place"""
        self.buffer[-1]  = chr(ord(self.buffer[-1]) ^ 0x80)
        return self

    def iabs(self):
        """Absolute value in-place"""
        self.buffer[-1] = chr(ord(self.buffer[-1]) & 0x7F)
        return self

    def iadd(self, rhs):
        """Add another Integer in-place"""
        if (ord(self.buffer[-1]) & 0x80) != (ord(rhs.buffer[-1]) & 0x80):
            return self.ineg().isub(rhs).ineg()
        lsb = ord(self.buffer[0]) + ord(rhs.buffer[0])
        msb = ord(self.buffer[1]) + ord(rhs.buffer[1])
        self._carry_list(lsb, msb)
        return self

    def isub(self, rhs):
        """Subtract another Integer in-place"""
        if (ord(self.buffer[-1]) & 0x80) != (ord(rhs.buffer[-1]) & 0x80):
            return self.ineg().iadd(rhs).ineg()
        lsb = ord(self.buffer[0]) - ord(rhs.buffer[0])
        msb = ord(self.buffer[1]) - ord(rhs.buffer[1])
        self._carry_list(lsb, msb)
        return self

    def _carry_list(self, lsb, msb):
        """Check for overflow and assign"""
        if lsb > 0xff:
            lsb -= 0xff
            msb += 1
        elif lsb < 0:
            lsb += 0xff
            msb -= 1
        if not (0 <= msb <= 0xff):
            raise OverflowError()
        self.buffer[:] = chr(lsb) + chr(msb)

    # relations

    def gt(self, rhs):
        """Greater than"""
        if isinstance(rhs, Float):
            # upgrade to Float
            return rhs.__class__().from_integer(self).gt(rhs)
        isneg = ord(self.buffer[-1]) & 0x80
        if isneg != (ord(rhs.buffer[-1]) & 0x80):
            return not(isneg)
        if isneg:
            return rhs.abs_gt(self)
        return self.abs_gt(rhs)

    def abs_gt(self, rhs):
        """Absolute values greater than"""
        if isinstance(rhs, Float):
            # upgrade to Float
            return rhs.__class__().from_integer(self).abs_gt(rhs)
        if ord(self.buffer[1]) > ord(rhs.buffer[1]):
            return True
        elif ord(self.buffer[1]) < ord(rhs.buffer[1]):
            return False
        return ord(self.buffer[0]) > ord(rhs.buffer[0])

    def eq(self, rhs):
        """Equals"""
        if isinstance(rhs, Float):
            # upgrade to Float
            return rhs.__class__().from_integer(self).eq(rhs)
        return self.buffer == rhs.buffer


class Float(Number):
    """Abstract base class for floating-point value"""

    bias = None
    shift = None
    pos_max = None
    neg_max = None
    intformat = None
    mask = None
    posmask = None

    def __init__(self, buffer=None):
        """Initialise the float"""
        Number.__init__(self, buffer)
        self.zero_flag = True
        self.sub_flag = False

    def is_zero(self):
        """Value is zero"""
        return self.buffer[-1] == '\0'

    def _is_negative(self):
        """Value is negative"""
        return self.buffer[-2] >= '\x80'

    def sign(self):
        """Sign of value"""
        return 0 if self.buffer[-1] == '\0' else (-1 if (ord(self.buffer[-2]) & 0x80) != 0 else 1)

    def to_float(self):
        """Return value as Python float"""
        exp = ord(self.buffer[-1]) - self.bias
        if exp == -self.bias:
            return 0.
        # unpack as unsigned long int
        man = struct.unpack(self.intformat, bytearray(self.buffer[:-1]) + '\0')[0]
        # preprend assumed bit and apply sign
        if man & self.signmask:
            man = -man
        else:
            man |= self.signmask
        return man * 2.**exp

    value = to_float

    def from_float(self, in_float):
        """Set to value of Python float."""
        if in_float == 0.:
            self.buffer[:] = '\0'*self.size
        neg = in_float < 0
        exp = int(math.log(abs(in_float), 2) - self.shift)
        man = int(abs(in_float) * 0.5**exp)
        exp += self.bias
        # why do we need this here?
        man, exp = self._bring_to_range(man, exp, self.posmask, self.mask)
        if not self._check_limits(exp, neg):
            return
        struct.pack_into(self.intformat, self.buffer, 0, man & (self.mask if neg else self.posmask))
        self.buffer[-1] = chr(exp)
        return self

    def _check_limits(self, exp, neg):
        """Overflow and underflow check
        returns:
            True if nonzero non-infinite
            False if underflow
        raises:
            OverflowError if overflow
        """
        if exp > 255:
            self.buffer[:] = self.neg_max if neg else self.pos_max
            raise OverflowError()
        elif exp <= 0:
            self.buffer[:] = self.zero
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

    def to_int(self):
        """Return value rounded to Python int"""
        exp = ord(self.buffer[-1]) - self.bias
        mand = struct.unpack(self.intformat, '\0' + bytearray(self.buffer[:-1]))[0] | self.den_mask
        neg = self._is_negative()
        if exp > 0:
            mand <<= exp
        else:
            mand >>= -exp
        # round
        if mand & 0x80:
            mand += 0x80
        return -mand >> 8 if neg else mand >> 8

    def from_int(self, in_int):
        """Set value to Python int"""
        if in_int == 0:
            self.buffer[:] = self.zero
        else:
            neg = in_int < 0
            man, exp = self._bring_to_range(abs(in_int), self.bias, self.posmask, self.mask)
            if not self._check_limits(exp, neg):
                return
            struct.pack_into(self.intformat, self.buffer, 0, man & (self.mask if neg else self.posmask))
            self.buffer[-1] = chr(exp)
        return self

    def from_integer(self, in_integer):
        """Convert Integer to single, in-place"""
        return self.from_int(in_integer.to_int())

    def ineg(self):
        """Negate in-place"""
        self.buffer[-2] = chr(ord(self.buffer[-2]) ^ 0x80)
        return self

    def iabs(self):
        """Absolute value in-place"""
        self.buffer[-2] = chr(ord(self.buffer[-2]) & 0x7F)
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
        rhsneg = rhs._is_negative()
        # treat zero separately to avoid comparing different mantissas
        # zero is only greater than negative
        if self.is_zero():
            return self.buffer[-1] != '\0' and bool(rhsneg)
        isneg = self._is_negative()
        if isneg != rhsneg:
            return not(isneg)
        if isneg:
            return rhs.abs_gt(self)
        return self.abs_gt(rhs)

    def abs_gt(self, rhs):
        """Absolute values greater than"""
        if isinstance(rhs, Integer):
            # upgrade rhs to Float
            return self.abs_gt(self.__class__().from_integer(rhs))
        elif isinstance(rhs, Double) and isinstance(self, Single):
            # upgrade to Double
            return Double().from_single(self).abs_gt(rhs)
        # don't compare zeroes
        if self.is_zero():
            return False
        # we can compare floats as if they were ints
        # so long as the sign is the same
        for l, r in reversed(zip(self.buffer, rhs.buffer)):
            if l > r:
                return True
            elif l < r:
                return False
        # equal
        return False

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
        return self.buffer == rhs.buffer

    def iadd(self, right):
        """ Add in-place. """
        return self._normalise(*self._iadd_den(self._denormalise(), right._denormalise()))

    def isub(self, right):
        """ Subtract in-place. """
        return self._normalise(*self._isub_den(self._denormalise(), right._denormalise()))

    def _denormalise(self):
        """Denormalise to shifted mantissa, exp, sign"""
        exp = ord(self.buffer[-1])
        man = struct.unpack(self.intformat, '\0' + bytearray(self.buffer[:-1]))[0] | self.den_mask
        neg = self._is_negative()
        return exp, man, neg

    def _normalise(self, exp, man, neg):
        """Normalise from shifted mantissa, exp, sign"""
        global pden_s, lsh, rsh
        lsh = 0; rsh = 0
        # zero denormalised mantissa -> make zero
        if man == 0 or exp == 0:
            exp, man, neg = False, 0, 0
        else:
            # shift left if subnormal
            while man < self.den_mask:
                lsh += 1
                exp -= 1
                man <<= 1
            self._check_limits(exp, neg)
        pden_s = man

        # strange rounding criterion to align with GW
        if self.zero_flag and not self.sub_flag:
            round_up = (man & 0xff > 0x80) or (man & 0x180 == 0x180)
        elif self.sub_flag:
            round_up = (man & 0xff >= 0x80) and not ((man & 0x1c0 == 0x80) and not (man & 0x1ff == 0xa0))
        else:
            # normal, sane rounding
            round_up = (man & 0xff >= 0x80)
        man = (man >> 8) + round_up

        struct.pack_into(self.intformat, self.buffer, 0, man & (self.mask if neg else self.posmask))
        self.buffer[-1] = chr(exp)
        return self


    def _iadd_den(self, lden, rden):
        """ Denormalised add. """
        lexp, lman, lneg = lden
        rexp, rman, rneg = rden
        global lden_s, rden_s, sden_s
        if rexp == 0:
            return lexp, lman, lneg
        if lexp == 0:
            return rexp, rman, rneg
        # ensure right has largest exponent
        if lexp > rexp:
            lexp, lman, lneg, rexp, rman, rneg = rexp, rman, rneg, lexp, lman, lneg
        # zero flag for quirky rounding
        # only set if all the bits we lose by matching exponents were zero
        self.zero_flag = lman & ((1<<(rexp-lexp))-1) == 0
        self.sub_flag = lneg != rneg
        # match exponents
        lman >>= (rexp - lexp)
        lexp = rexp
        lden_s = lman
        rden_s = rman
        # shortcut (this affects quirky rounding)
        if lman < 0x80 and lneg != rneg:
            return rexp, rman, rneg
        # add mantissas, taking sign into account
        sden_s = bin(lman - rman), lneg, rneg
        if (lneg == rneg):
            man = lman + rman
            if man >= self.den_upper:
                lexp += 1
                man >>= 1
            return lexp, man, lneg
        elif lman > rman:
            return lexp, lman - rman, lneg
        return lexp, rman - lman, rneg

    def _isub_den(self, lden, rden):
        """ Denormalised subtract. """
        rexp, rman, rneg = rden
        return self._iadd_den(lden, (rexp, rman, not rneg))


class Single(Float):
    """Single-precision MBF float"""

    sigil = '!'
    size = 4

    intformat = '<L'

    bias = 128 + 24
    shift = bias - 129

    den_mask = 0x80000000
    den_upper = den_mask * 2
    signmask = 0x800000
    mask = 0xffffff
    posmask = 0x7fffff

    pos_max = '\xff\xff\x7f\xff'
    neg_max = '\xff\xff\xff\xff'
    zero = '\0\0\0\0'

    def to_token(self):
        """Return value as Single token"""
        return tk.T_SINGLE + self.buffer[:]

    def from_token(self, token):
        """Set value to Single token"""
        if token[0] != tk.T_SINGLE:
            raise ValueError()
        self.buffer[:] = token[-4:]
        return self

class Double(Float):
    """Double-precision MBF float"""

    sigil = '#'
    size = 8

    intformat = '<Q'

    bias = 128 + 56
    shift = bias - 129

    den_mask = 0x8000000000000000
    den_upper = den_mask * 2

    signmask = 0x80000000000000
    mask = 0xffffffffffffff
    posmask = 0x7fffffffffffff

    pos_max = '\xff\xff\xff\xff\xff\xff\x7f\xff'
    neg_max = '\xff\xff\xff\xff\xff\xff\xff\xff'
    zero = '\0\0\0\0\0\0\0\0'

    def from_single(self, in_single):
        """Convert Single to Double in-place"""
        self.buffer[:4] = '\0\0\0\0'
        self.buffer[4:] = in_single.buffer

    def to_token(self):
        """Return value as Single token"""
        return tk.T_DOUBLE + self.buffer[:]

    def from_token(self, token):
        """Set value to Single token"""
        if token[0] != tk.T_DOUBLE:
            raise ValueError()
        self.buffer[:] = token[-8:]
        return self


def number_from_token(token):
    """Convert number token to new Number temporary"""
    if token[0] == tk.T_SINGLE:
        return Single().from_token(token)
    elif token[0] == tk.T_DOUBLE:
        return Double().from_token(token)
    else:
        return Integer().from_token(token)



lden_s, rden_s, sden_s, pden_s = 0,0,0,0
lsh, rsh = 0, 0
