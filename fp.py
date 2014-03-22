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

overflow = False
zero_div = False


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
#        man <<= 8
        return cls(neg, man, exp).normalise()

########################

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
        
class Single(Float):
    digits = 7
    mantissa_bits = 24
    byte_size = 4
    bias = true_bias + mantissa_bits
    carry_mask = 0xffffff00
    
Single.zero    = from_bytes(bytearray('\x00\x00\x00\x00'))
Single.half    = from_bytes(bytearray('\x00\x00\x00\x80'))
Single.one     = from_bytes(bytearray('\x00\x00\x00\x81'))
Single.two     = from_bytes(bytearray('\x00\x00\x00\x82'))
Single.ten     = from_bytes(bytearray('\x00\x00\x20\x84'))
Single.max     = from_bytes(bytearray('\xff\xff\x7f\xff'))
Single.e       = from_bytes(bytearray('\x54\xf8\x2d\x82'))
Single.pi      = from_bytes(bytearray('\xdb\x0f\x49\x82'))
Single.log2    = from_bytes(bytearray('\x16\x72\x31\x80'))    # ln 2
Single.twopi   = mul(Single.pi, Single.two) 
Single.pi2     = mul(Single.pi, Single.half)
Single.pi4     = mul(Single.pi2, Single.half)

Single.taylor = [
    Single.one,                      # 1/0!
    Single.one,                      # 1/1!
    Single.half,                     # 1/2
    from_bytes(bytearray('\xab\xaa\x2a\x7e')),  # 1/6
    from_bytes(bytearray('\xab\xaa\x2a\x7c')),  # 1/24
    from_bytes(bytearray('\x89\x88\x08\x7a')),  # 1/120
    from_bytes(bytearray('\x61\x0b\x36\x77')),  # 1/720
    from_bytes(bytearray('\x01\x0D\x50\x74')),  # 1/5040
    from_bytes(bytearray('\x01\x0D\x50\x71')),  # 1/40320
    from_bytes(bytearray('\x1d\xef\x38\x6e')),  # 1/362880
    from_bytes(bytearray('\x7e\xf2\x13\x6b')),  # 1/3628800
    from_bytes(bytearray('\x2b\x32\x57\x67')),  # 1/39916800
    ]

class Double(Float):
    digits = 16
    mantissa_bits = 56
    byte_size = 8
    bias = true_bias + mantissa_bits
    carry_mask = 0xffffffffffffff00    

Double.zero = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x00'))
Double.half = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x80'))
Double.one  = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x81'))
Double.two  = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x00\x82'))
Double.ten  = from_bytes(bytearray('\x00\x00\x00\x00\x00\x00\x20\x84'))
Double.max  = from_bytes(bytearray('\xff\xff\xff\xff\xff\xff\x7f\xff'))
Double.e    = from_bytes(bytearray('\x4b\xbb\xa2\x58\x54\xf8\x2d\x82'))
Double.pi   = from_bytes(bytearray('\xc2\x68\x21\xa2\xda\x0f\x49\x82'))

##########################################
# math        

# convert to IEEE, do library math operations, convert back

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


### experimental MBF math functions (finding BASIC's algorithms)        
        
# Float raised to Float exponent
def _power(base_in, exp_in):
    base = base_in.copy()
    exp = exp_in.copy()
    if exp.is_zero():
        # 0^0 returns 1 too
        return base.one.copy()
    elif exp.neg:
        # y^-x = 1/(y^x)
        exp.neg = False
        return div(base.one, power(base, exp))
    else:   
        shift = exp.exp - true_bias - 1
        exp.exp = true_bias+1
        while shift < 0:
            base = sqrt(base)
            shift += 1
        # to avoid doing sqrt(sq( ...
        roots = []
        while shift > 0:
            roots.append(base.copy())
            base.isq()
            shift -= 1
        # exp.exp = 0x81 means exp's exponent is one  
        # and most significant mantissa bit must be 1  
        # we have 0x80 00 00 (00) <=exp.mant <= 0xff ff ff (ff) 
        # exp.mant == 1011... means exp == 1 + 0/2 + 1/4 + 1/8 + ...
        # meaning we return base * 0**sqrt(base) * 1**sqrt(sqrt(base)) * 1**sqrt(sqrt(sqrt(base))) * ...
        #bit = 0x40000000 # skip most significant bit, we know it's one
        bit = 0x40 * (0x100 ** (base.byte_size-1))
        exp.man &= 2**(exp.mantissa_bits+8-1)-1 #exp.man &= 0x7fffffff
        out = base.copy()
        count = 0
        while exp.man >= 0x7f and bit >= 0x7f :
            if len(roots) > count:
                base = roots[-count-1]
            else:
                base = sqrt(base)
            count += 1
            if exp.man & bit:
                out.imul(base)
            exp.man &= ~bit
            bit >>= 1
        return out

# square root
# Newton's method
def _sqrt(target):
    if target.neg:
        # illegal function call
        raise error.RunError(5)
    if target.is_zero() or target.equals(target.one):
        return target
    # initial guess, divide exponent by 2
    n = target.copy()
    #n.exp = (n.exp - n.bias + 24)/2 + n.bias-24
    n.exp = (n.exp - n.bias + n.mantissa_bits)/2 + n.bias - n.mantissa_bits
    # iterate to convergence, max_iter = 7
    for _ in range (0,7):
        nxt = sub(n, mul(n.half, div(sub(sq(n), target),n)))  
        # check convergence
        if nxt.equals_inc_carry(n):
            break
        n = nxt
    return n

# e raised to mbf exponent
def _exp(arg_in):
    if arg_in.is_zero():
        return arg_in.one.copy()
    arg = arg_in.copy()
    if arg.neg:
        arg.neg = False
        return div(arg.one, exp(arg))
    if arg.gt(arg_in.one):
        arg_int = arg.copy().ifloor()
        arg.isub(arg_int)
        return arg.e.copy().ipow_int(arg_int.trunc_to_int()).imul(exp(arg))
    exp_out = arg.zero.copy()
    for npow in range(0,12):
        term = mul(arg.taylor[npow], pow_int(arg, npow)) 
        exp_out.iadd(term) 
    return exp_out
            
def _sin(n_in):
    if n_in.is_zero():
        return n_in
    n = n_in.copy()
    neg = n.neg
    n.neg = False 
    sin_out = n.zero.copy()
    if n.gt(n.twopi):
        n.isub(mul(n.twopi, div(n, n.twopi).ifloor()))
    if n.gt(n.pi):
        neg = not neg     
        n.isub(n.pi)
    if n.gt(n.pi2):
        n.negate()
        n.iadd(n.pi)    
    if n.gt(n.pi4):
        n.isub(n.pi2)
        sin_out = cos(n)    
    else:
        termsgn = False
        for expt in range(1,12,2):
            term = mul(n.taylor[expt], pow_int(n, expt)) 
            term.neg = termsgn
            termsgn = not termsgn
            sin_out.iadd(term) 
    sin_out.neg ^= neg    
    return sin_out

def _cos(n_in):
    if n_in.is_zero():
        return Single.one.copy()
    n = n_in.copy()
    neg = False
    n.neg = False 
    cos_out = n.one.copy()
    if n.gt(n.twopi):
        n.isub(mul(n.twopi, div(n, n.twopi).ifloor()))
    if n.gt(n.pi):
        neg = not neg     
        n.isub(n.pi)
    if n.gt(n.pi2):
        neg = not neg
        n.negate()     
        n.iadd(n.pi)    
    if n.gt(n.pi4):
        neg = not neg
        n.isub(n.pi2)
        cos_out = sin(n)    
    else:
        termsgn = True
        for expt in range(2,11,2):
            term = mul(n.taylor[expt], pow_int(n, expt)) 
            term.neg = termsgn
            termsgn = not termsgn
            cos_out.iadd(term) 
    cos_out.neg ^= neg    
    return cos_out

def _tan(n_in):
    return div(sin(n_in), cos(n_in))

# atn and log, don't know what algorithm MS use.

# find arctangent using secant method
def _atn(n_in):
    if n_in.is_zero():
        return n_in.copy()
    if n_in.equals(n_in.one):
        return n_in.pi4.copy()
    if n_in.gt(n_in.one):
        # atn (1/x) = pi/2 - atn(x) 
        return sub(n_in.pi2, atn(div(n_in.one, n_in)))
    if n_in.neg:
        n = n_in.copy()
        n.neg = False
        n = atn(n)
        n.neg = True
        return n
    # calculate atn of x between 0 and 1 which is between 0 and pi/4
    # also, in that range, atn(x) <= x and atn(x) >= x*pi/4
    last = n_in.pi4.copy()
    tan_last = n_in.one.copy()
    guess = mul(n_in.pi4, n_in)
    tan_out = tan(guess)    
    count = 0 
    while (guess.exp != last.exp or abs(guess.man-last.man) > 0x100) and count<30:
        count+=1
        offset = mul( sub(n_in, tan_out), div(sub(last, guess), sub(tan_last, tan_out)) ) 
        last.neg, last.man, last.exp = guess.neg, guess.man, guess.exp
        tan_last.neg, tan_last.man, tan_last.exp = tan_out.neg, tan_out.man, tan_out.exp
        guess.iadd(offset)
        tan_out = tan(guess)
    return guess

# natural logarithm
def _log(n_in):
    if n_in.equals(n_in.one):
        return n_in.zero.copy()
    if n_in.equals(Single.two):
        return n_in.log2.copy()
    if n_in.neg or n_in.is_zero():
        raise error.RunError(5)
    if n_in.gt(n_in.one):
        # log (1/x) = -log(x)
        n = log(div(n_in.one, n_in).apply_carry())
        n.neg = not n.neg
        return n
    # if n = a*2^b, log(n) = log(a) + b*log(2)
    expt = n_in.exp - n_in.bias + n_in.mantissa_bits
    loge = mul(n_in.log2, n_in.from_int(expt))
    n = n_in.copy()
    n.exp = n.bias - n.mantissa_bits
    # our remaining input a is the mantissa, between 0.5 and 1.
    # lo is log(0.5) = -log(2), hi is zero
    # also log(x) above -log(2) + x- 0.5
    # and below 1-x
    # 1-n
    # hi.man = 0xffffffff - n.man
    hi = n.__class__(True, 0x100**n.byte_size - 1 - n.man, n.exp) 
    lo = n.log2.copy()
    lo.neg = True 
    last = hi
    guess = lo
    f_last = exp(last)
    f_guess = exp(guess)
    count = 0 
    while not guess.equals(last) and not f_guess.equals(f_last) and count<30:
        count += 1
        offset = mul(sub(n, f_guess), div(sub(last, guess), sub(f_last, f_guess)))  
        last.neg, last.man, last.exp = guess.neg, guess.man, guess.exp
        f_last.neg, f_last.man, f_last.exp = f_guess.neg, f_guess.man, f_guess.exp
        guess.iadd(offset)
        f_guess = exp(guess)
    loge.iadd(guess)
    loge.apply_carry()
    return loge 
    
######################################    

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

################################

# for to_str
# for numbers, tab and LF are whitespace    
whitespace = (' ', '\x09', '\x0a')
# these seem to lead to a zero outcome all the time
kill_char = ('\x1c', '\x1d', '\x1f')

# string representations

Single.lim_top = from_bytes(bytearray('\x7f\x96\x18\x98')) # 9999999, highest float less than 10e+7
Single.lim_bot = from_bytes(bytearray('\xff\x23\x74\x94')) # 999999.9, highest float  less than 10e+6
Single.type_sign, Single.exp_sign = '!', 'E'

Double.lim_top = from_bytes(bytearray('\xff\xff\x03\xbf\xc9\x1b\x0e\xb6')) # highest float less than 10e+16
Double.lim_bot = from_bytes(bytearray('\xff\xff\x9f\x31\xa9\x5f\x63\xb2')) # highest float less than 10e+15 
Double.type_sign, Double.exp_sign = '#', 'D'


def just_under(n_in):
    # decrease mantissa by one (leaving carry unchanged)
    return n_in.__class__(n_in.neg, n_in.man - 0x100, n_in.exp)

# for Ints?    
def get_digits(num, digits, remove_trailing=True):    
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
    valstr = ''
    # digits to decimal point
    exp10 += 1
    if exp10 >= len(digitstr):
        valstr += digitstr + '0'*(exp10-len(digitstr))
        if force_dot:
            valstr+='.'
        if not force_dot or type_sign=='#':
            valstr += type_sign
    elif exp10 > 0:
        valstr += digitstr[:exp10] + '.' + digitstr[exp10:]       
        if type_sign=='#':
            valstr += type_sign
    else:
        valstr += '.' + '0'*(-exp10) + digitstr 
        if type_sign=='#':
            valstr += type_sign
    return valstr

# screen=True (ie PRINT) - leading space, no type sign
# screen='w' (ie WRITE) - no leading space, no type sign
# default mode is for LIST    
def to_str(n_in, screen=False, write=False):
    # zero exponent byte means zero
    if n_in.is_zero(): 
        if screen and not write:
            valstr = ' 0'
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
    
# for PRINT USING
def format_number(value, tokens, digits_before, decimals):
    # illegal function call if too many digits
    if digits_before + decimals > 24:
         raise error.RunError(5)
    # extract sign, mantissa, exponent     
    value = unpack(value)
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
            if force_dot and digits_before == 0 and decimals == 0:
                valstr += '0'
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
            lim_bot = just_under(pow_int(expr.ten, work_digits-1))
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
    # fixed-point representation
    unrounded = mul(expr, pow_int(expr.ten, decimals)) # expr * 10**decimals
    num = unrounded.copy().iround()
    # find exponent 
    exp10 = 1
    pow10 = pow_int(expr.ten, exp10) # pow10 = 10L**exp10
    while num.gt(pow10) or num.equals(pow10): # while pow10 <= num:
        pow10.imul10() # pow10 *= 10
        exp10 += 1
    work_digits = exp10 + 1
    diff = 0
    if exp10 > expr.digits:
        diff = exp10 - expr.digits
        num = div(unrounded, pow_int(expr.ten, diff)).iround()  # unrounded / 10**diff
        work_digits -= diff
    num = num.trunc_to_int()   
    # argument work_digits-1 means we're getting work_digits==exp10+1-diff digits
    # fill up with zeros
    digitstr = get_digits(num, work_digits-1, remove_trailing=False) + ('0' * diff)
    return decimal_notation(digitstr, work_digits-1-1-decimals+diff, '', force_dot)

    
##################################

# create Float from string

def from_str(s, allow_nonnum = True):
    found_sign = False
    found_point = False
    found_exp = False
    found_exp_sign = False
    exp_neg = False
    neg = False
    exp10 = 0
    exponent = 0
    mantissa = 0
    digits = 0  
    zeros = 0
    is_double = False
    is_single = False
    for c in s:
        # ignore whitespace throughout (x = 1   234  56  .5  means x=123456.5 in gw!)
        if c in whitespace:   #(' ', '\t'):
            continue
        if c in kill_char:
            return Single.zero
        # find sign
        if (not found_sign):
            if c=='+':
                found_sign=True
                continue
            elif c=='-':
                found_sign=True    
                neg=True
                continue
            else:
                # number has started, sign must be pos. parse chars below.
                found_sign=True
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
                        zeros+=1
                    else:
                        zeros=0
                continue               
            elif c=='.':
                found_point = True    
                continue
            elif c.upper()=='E': 
                found_exp = True
                continue
            elif c.upper()=='D':
                found_exp = True
                is_double = True
                continue
            elif c=='!':
                # makes it a single, even if more than eight digits specified
                is_single=True
                break
            elif c=='#':
                is_double = True
                break    
            else:
                if allow_nonnum:
                    break    
                else:
                    return None
        elif (not found_exp_sign):
            if c=='+':
                found_exp_sign = True
                continue
            elif c=='-':
                found_exp_sign = True    
                exp_neg = True
                continue
            else:
                # number has started, sign must be pos. parse chars below.
                found_exp_sign = True
        if (c >= '0' and c <= '9'):
            exponent *= 10
            exponent += ord(c)-ord('0')
            continue
        else:
            if allow_nonnum:
                break    
            else:    
                return None
    if exp_neg:
        exp10 -= exponent
    else:           
        exp10 += exponent
    # eight or more digits means double, unless single override
    if digits - zeros > 7 and not is_single:
        is_double = True
    cls = Double if is_double else Single
    mbf = cls(neg, mantissa * 0x100, cls.bias).normalise() 
    while (exp10 < 0):
        mbf.idiv10()
        exp10 += 1
    while (exp10 > 0):
        mbf.imul10()
        exp10 -= 1
    mbf.normalise()    
    return mbf
        
