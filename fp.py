#
# PC-BASIC 3.23 - fp.py
#
# MBF Floating-point arithmetic 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.

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

import math
from functools import partial

import error

# the exponent is biased by 128
true_bias = 128

######################################    

overflow = False
zero_div = False

def msg_overflow():
    global overflow
    if overflow:
        return
    overflow = True    
    error.math_error(6)

def msg_zero_div():
    global zero_div
    if zero_div:
        return
    zero_div = True
    error.math_error(11)


####################################

class Float(object):
    def __init__(self, neg=False, man=0, exp=0):
        self.neg, self.man, self.exp = neg, man, exp
            
    def copy(self):
        return self.__class__(self.neg, self.man, self.exp)
    
    @classmethod
    def from_int(cls, num):
        # this creates an mbf float. the carry byte will also be in use. call discard_carry afterwards if you want an empty carry.    
        # set mantissa to number, shift to create carry bytes
        n = cls( (num<0), long(abs(num) << 8), cls.bias )
        # normalise shifts to turn into proper mbf
        n.normalise()
        return n

    @classmethod
    def from_bytes(cls,s):
        # put mantissa in form . 1 f1 f2 f3 ... f23
        # internal representation has four bytes, last byte is carry for intermediate results
        # put mantissa in form . 1 f1 f2 f3 ... f55
        # internal representation has seven bytes, last bytes are carry for intermediate results
        man = long((s[-2]|0x80) * 0x100**(cls.byte_size-2))
        for i in range(cls.byte_size-2):
            man += s[-cls.byte_size+i] * 0x100**i
        man <<= 8
        return cls( (s[-2] >= 0x80), man, s[-1])
    
    def to_bytes(self):
        #n = self.copy()
        self.apply_carry()
        # extract bytes    
        s = bytearray()
        man = self.man
        for _ in range(self.byte_size-1):
            man >>= 8
            s.append(man&0xff)
        # append exponent byte
        s.append(self.exp)
        # apply sign
        s[-2] &= 0x7f
        if (self.neg):
            s[-2] |= 0x80
        return s

    def is_zero(self):
        return self.exp==0

    def sign(self):
        if self.exp==0:
            return 0
        elif self.neg:
            return -1
        else:
            return 1

    def apply_carry(self):
        # carry bit set? then round up
        if (self.man & 0xff) > 0x7f:
            self.man += 0x100 
        # overflow?
        if self.man >= 0x100**self.byte_size:
            self.exp +=1
            self.man >>= 1
        # discard carry
        self.man ^= (self.man&0xff) 
        return self
        
    def discard_carry(self):
        self.man ^= (self.man&0xff) 
        return self
    
    def trunc_to_int(self):
        man = self.man >> 8 
        if self.exp > self.bias :
            val = long(man << (self.exp-self.bias))
        else:
            val = long(man >> (-self.exp+self.bias))
        if self.neg:
            return -val
        else:
            return val    

    def round_to_int(self):
        if self.exp > self.bias:
            man = long(self.man << (self.exp-self.bias))
        else:
            man = long(self.man >> (-self.exp+self.bias))
        # carry bit set? then round up (affect mantissa only, note we can be bigger than our byte_size allows)
        #if (n_in.man & 0xff) > 0x7f:
        if (man & 0xff) > 0x7f:
            man += 0x100 
        if self.neg:
            return -(man >> 8)
        else:
            return (man >> 8)

    def normalise(self):
        # zero mantissa -> make zero
        if self.man == 0 or self.exp == 0:
            self.neg, self.man, self.exp = self.zero.neg, self.zero.man, self.zero.exp
            return self
        # are these correct?        
        while self.man <= 2**(self.mantissa_bits+8-1): # 0x7fffffffffffffff: # < 2**63
            self.exp -= 1
            self.man <<= 1
        while self.man > 2**(self.mantissa_bits+8): #0xffffffffffffffff: # 2**64 or 0x100**8
            self.exp += 1
            self.man >>= 1
        # underflow
        if self.exp < 0:
            self.exp = 0
        # overflow    
        if self.exp > 0xff:
            # overflow
            # message does not break execution, no line number
            msg_overflow()
            self.exp = 0xff
            self.man = self.carry_mask #0xffffffffffffff00L
        return self
            
    def ifloor(self):
        # discards carry & truncates towards neg infty, returns mbf
        if self.is_zero():
            return self
        n = self.from_int(self.trunc_to_int())
        if n.neg and not self.equals(n):
            self = sub(n, n.one)
        else:
            self = n     
        return self

    def iround(self):
        if self.exp-self.bias > 0:
            self.man = long(self.man * 2**(self.exp-self.bias))
        else:
            self.man = long(self.man / 2**(-self.exp+self.bias))
        self.exp = self.bias
        # carry bit set? then round up (moves exponent on overflow)
        self.apply_carry()
        self.normalise()
        return self
        
    def negate(self):
        self.neg = not self.neg
        return self
        
    # unnormalised add in place        
    def iadd_raw(self, right_in):
        if right_in.is_zero():
            return self
        if self.is_zero():
            self.neg, self.man, self.exp = right_in.neg, right_in.man, right_in.exp
            return self
        # ensure right has largest exponent
        if self.exp > right_in.exp:
            right = self.copy() 
            self.neg, self.man, self.exp = right_in.neg, right_in.man, right_in.exp
        else:
            right = right_in
        # denormalise left to match exponents
        while self.exp < right.exp:
            self.exp += 1
            self.man >>= 1
        # add mantissas, taking sign into account
        if (self.neg == right.neg):
            self.man += right.man
        else:
            if self.man > right.man:
                self.man -= right.man    
            else:
                self.man = right.man - self.man
                self.neg = right.neg         
        return self
        
    def iadd(self, right):
        return self.iadd_raw(right).normalise()
        
    def isub(self, right_in):
        return self.iadd(self.__class__(not right_in.neg, right_in.man, right_in.exp))
        
    def imul10(self):    
        if self.is_zero():
            return self
        # 10x == 2(x+4x)    
        n = self.__class__(self.neg, self.man, self.exp+2)
        self.iadd_raw(n)            
        self.exp += 1    
        self.normalise()    
        return self
        
    def imul(self, right_in):    
        if self.is_zero():
            return self
        if right_in.is_zero():
            self.neg, self.man, self.exp = right_in.neg, right_in.man, right_in.exp
            return self
        self.exp += right_in.exp - right_in.bias - 8
        self.neg = (self.neg != right_in.neg)
        self.man = long(self.man * right_in.man)
        self.normalise()
        return self
        
    def isq(self):
        self.imul(self)
        return self
        
    def idiv(self, right_in):
        if right_in.is_zero():
            msg_zero_div()
            self.man, self.exp = self.max.man, self.max.exp
            return self
        if self.is_zero():
            return self
        # signs
        self.neg = (self.neg != right_in.neg)
        # subtract exponentials
        self.exp -= right_in.exp - right_in.bias - 8
        # long division of mantissas
        work_man = self.man
        denom_man = right_in.man
        self.man = 0L 
        self.exp += 1
        while (denom_man > 0):
            self.man <<= 1
            self.exp -= 1
            if work_man > denom_man:
                work_man -= denom_man
                self.man += 1L
            denom_man >>= 1     
        self.normalise()
        return self
        
    def idiv10(self):
        self.idiv(self.ten)
        return self
        
    # Float raised to integer exponent
    # exponentiation by squares
    def ipow_int(self, exp):
        if exp < 0:
            self.ipow_int(-exp)
            self = div(self.one, self)
        elif exp > 1:
            if (exp%2) == 0:
                self.ipow_int(exp/2)
                self.isq()
            else:
                base = self.copy()
                self.ipow_int((exp-1)/2)
                self.isq()
                self.imul(base)
        elif exp == 0:
            self = self.one.copy()
        return self
              
    # absolute value is greater than
    def abs_gt(self, right):
        if self.exp != right.exp:
            return (self.exp > right.exp)     
        return (self.man > right.man)     

    # greater than    
    def gt(self, right):
        if self.neg != right.neg:
            return right.neg
        return self.neg != self.abs_gt(right)
    
    def equals(self, right):
        return (self.neg==right.neg and self.exp==right.exp and self.man&self.carry_mask == right.man&right.carry_mask)
        
    def equals_inc_carry(self, right, grace_bits=0):
        return (self.neg==right.neg and self.exp==right.exp and abs(self.man-right.man) < (1<<grace_bits)) 
     
    def bring_to_range(self, lim_bot, lim_top):
        exp10 = 0    
        while self.abs_gt(lim_top):
            self.idiv10()
            exp10 += 1
        self.apply_carry()
        while lim_bot.abs_gt(self):
            self.imul10()
            exp10 -= 1
        # round off carry byte before doing the decimal rounding
        # this brings results closer in line with GW-BASIC output 
        self.apply_carry()
        ##self.discard_carry()
        # round to integer: first add one half
        self.iadd(self.half)
        ##self.apply_carry()
        # then truncate to int (this throws away carry)
        num = abs(self.trunc_to_int())
        # round towards neg infinity when negative
        if self.neg:
            num += 1
        return num, exp10

    # get python float
    def to_value(self):
        self.apply_carry()
        man = self.man >> 8
        return man * 2**(self.exp - self.bias) * (1-2*self.neg)

    @classmethod
    def from_value(cls, value):
        neg = value < 0
        fexp = math.log(abs(value), 2) - cls.mantissa_bits
        man = int(abs(value) * 0.5**int(fexp-8))
        exp = int(fexp) + cls.bias
        return cls(neg, man, exp).normalise()

        
class Single(Float):
    digits = 7
    mantissa_bits = 24
    byte_size = 4
    bias = true_bias + mantissa_bits
    carry_mask = 0xffffff00

    
class Double(Float):
    digits = 16
    mantissa_bits = 56
    byte_size = 8
    bias = true_bias + mantissa_bits
    carry_mask = 0xffffffffffffff00    
    
    def round_to_single(self):
        mybytes = self.to_bytes()
        single = Single.from_bytes(mybytes[4:])
        single.man += mybytes[3]
        return single.normalise()

####################################

def from_bytes(s):
    if len(s) == 4:   
        return Single.from_bytes(s)
    elif len(s) == 8:   
        return Double.from_bytes(s)
    
def unpack(value):
    global overflow, zero_div
    overflow = False
    zero_div = False
    return from_bytes(value[1])

def pack(n):
    s = n.to_bytes()
    if len(s) == 8:
        return ('#', s)
    elif len(s) == 4:
        return ('!', s)


####################################
# standalone arithmetic operators

def add(left_in, right_in):
    return left_in.copy().iadd(right_in)

def sub(left_in, right_in):
    return left_in.copy().isub(right_in)

def mul(left_in, right_in):
    return left_in.copy().imul(right_in)
    
def div(left_in, right_in):
    return left_in.copy().idiv(right_in)
    
def sq(n):
    return mul(n, n)

def pow_int(left_in, right_in):
    return left_in.copy().ipow_int(right_in)
    
####################################
# math function       

# convert to IEEE 754, do library math operations, convert back
def power(base_in, exp_in):
    try:
        return base_in.__class__().from_value(base_in.to_value() ** exp_in.to_value())    
    except OverflowError:
        msg_overflow()
        return base_in.__class__(mbf_in.neg, mbf_in.carry_mask, 0xff)

def unary(mbf_in, fn):
    try:
        return mbf_in.__class__().from_value(fn(mbf_in.to_value()))    
    except OverflowError:
        msg_overflow()
        return mbf_in.__class__(mbf_in.neg, mbf_in.carry_mask, 0xff)
    
sqrt = partial(unary, fn=math.sqrt)
exp  = partial(unary, fn=math.exp )
sin  = partial(unary, fn=math.sin )
cos  = partial(unary, fn=math.cos )
tan  = partial(unary, fn=math.tan )
atn  = partial(unary, fn=math.atan)
log  = partial(unary, fn=math.log )

####################################
# constants
    
Single.zero     = from_bytes(bytearray('\x00\x00\x00\x00'))
Single.half     = from_bytes(bytearray('\x00\x00\x00\x80'))
Single.one      = from_bytes(bytearray('\x00\x00\x00\x81'))
Single.two      = from_bytes(bytearray('\x00\x00\x00\x82'))
Single.ten      = from_bytes(bytearray('\x00\x00\x20\x84'))
Single.max      = from_bytes(bytearray('\xff\xff\x7f\xff'))
Single.e        = from_bytes(bytearray('\x54\xf8\x2d\x82'))
Single.pi       = from_bytes(bytearray('\xdb\x0f\x49\x82'))
Single.log2     = from_bytes(bytearray('\x16\x72\x31\x80'))    # rounding not correct but extracted from GW-BASIC
Single.twopi    = mul(Single.pi, Single.two) 
Single.pi2      = mul(Single.pi, Single.half)
Single.pi4      = mul(Single.pi2, Single.half)

Double.zero     = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x00'))
Double.half     = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x80'))
Double.one      = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x81'))
Double.two      = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x82'))
Double.ten      = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x20\x84'))
Double.max      = from_bytes(bytearray('\xff\xff\xff\xff\xff\xff\x7f\xff'))
Double.e        = from_bytes(bytearray('\x4b\xbb\xa2\x58\x54\xf8\x2d\x82'))
Double.pi       = from_bytes(bytearray('\xc2\x68\x21\xa2\xda\x0f\x49\x82'))
Double.log2     = from_bytes(bytearray('\x7a\xcf\xd1\xf7\x17\x72\x31\x80'))
Double.twopi    = mul(Double.pi, Double.two) 
Double.pi2      = mul(Double.pi, Double.half)
Double.pi4      = mul(Double.pi2, Double.half)
    

