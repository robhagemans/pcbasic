#
# PC-BASIC 3.23 - fp.py
#
# MBF Floating-point arithmetic 
# 
# (c) 2013 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.




# description of MBF found here:
# http://www.experts-exchange.com/Programming/Languages/Pascal/Delphi/Q_20245266.html

#     /* MS Binary Format                         */
#     /* byte order =>    m3 | m2 | m1 | exponent */
#     /* m1 is most significant byte => sbbb|bbbb */
#     /* m3 is the least significant byte         */
#     /*      m = mantissa byte                   */
#     /*      s = sign bit                        */
#     /*      b = bit                             */

#   /* MS Binary Format                                           */
#   /* byte order =>  m7 | m6 | m5 | m4 | m3 | m2 | m1 | exponent */
#   /* m1 is most significant byte => smmm|mmmm                   */
#   /* m7 is the least significant byte                           */
#   /*      m = mantissa byte                                     */
#   /*      s = sign bit                                          */
#   /*      b = bit                                               */


# Another description of the single-precision format found here:
# http://www.boyet.com/Articles/MBFSinglePrecision.html

# Microsoft Binary Format (single precision)
# =======================           
# 32 bits long (4 bytes)
#
# exponent (8 bits) | sign (1 bit) | fraction (23 bits)
#
# The exponent is biased by 128. 
# There is an assumed 1 bit after the radix point 
#  (so the assumed mantissa is 0.1ffff... where f's are the fraction bits)


# information on the string representation of floating point numbers can be found in the manual:
# http://www.antonis.de/qbebooks/gwbasman/chapter%206.html

import error

# this is where in-calculation error messages (Overflow, Division by Zero) go
error_console = None

# for to_str
# for numbers, tab and LF are whitespace    
whitespace = (' ', '\x09', '\x0a')
# these seem to lead to a zero outcome all the time
kill_char = ('\x1c', '\x1d', '\x1f')

# the exponent is biased by 128
true_bias = 128

########################

# for Ints    
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

#######################



def from_bytes(s):
    if len(s) == 4:   
        return Single.from_bytes(s)
    elif len(s) == 8:   
        return Double.from_bytes(s)
    
def unpack(value):
    return from_bytes(value[1])

def pack(n):
    s = n.to_bytes()
    if len(s) == 8:
        return ('#', s)
    elif len(s) == 4:
        return ('!', s)
        
                       
def print_error(errnum, linenum):
    global error_console
    if error_console==None:
        return
    msg = error.get_message(errnum)
    error_console.write_error_message(msg,linenum)
        

class Float:
    def __init__(self, neg=False, man=0, exp=0):
        self.neg = neg
        self.man = man
        self.exp = exp

    @classmethod    
    def new(cls, neg=False, man=0, exp=0):
        return cls(neg, man, exp)
    
    def copy(self):
        return self.__class__(self.neg, self.man, self.exp)
    
    @classmethod
    def from_int(cls, num):
        # this creates an mbf float. the carry byte will also be in use
        # call mbf_trunc afterwards if you want an empty carry.    
        
        # set mantissa to number, shift to create carry bytes
        n = cls.new( (num<0), long(abs(num) << 8), cls.bias )
        
        # normalise shifts to turn into proper mbf
        n.normalise()
        return n

    @classmethod
    def from_bytes(cls,s):
        s = map(ord, s) 
                   
        # extract sign bit
        neg = s[-2] >= 0x80
        # put mantissa in form . 1 f1 f2 f3 ... f23
        # internal representation has four bytes, last byte is carry for intermediate results
        # put mantissa in form . 1 f1 f2 f3 ... f55
        # internal representation has seven bytes, last bytes are carry for intermediate results
        man = long((s[-2]|0x80) * 0x100**(cls.byte_size-2))
        for i in range(cls.byte_size-2):
            man += s[-cls.byte_size+i] * 0x100**i
        man <<= 8
        exp = s[-1]  # biased exponent, including mantissa shift 
        return cls(neg,man,exp)
    
    
    def to_bytes(self):
        self.apply_carry()
        # extract bytes    
        s=[]
        for _ in range(self.byte_size-1):
            self.man = self.man >> 8
            s.append(self.man&0xff)
        # append exponent byte
        s.append(self.exp)
        # apply sign
        s[-2] &= 0x7f
        if (self.neg):
            s[-2] |= 0x80
        return map(chr, s)

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
        n = self # no copy
        # zero mantissa -> make zero
        if n.man == 0 or n.exp==0:
            n = n.zero
            return n
                
        while n.man <= 2**(n.mantissa_bits+8-1): # 0x7fffffffffffffff: # < 2**63
            n.exp -= 1
            n.man = n.man << 1
        
        while n.man > 2**(n.mantissa_bits+8): #0xffffffffffffffff: # 2**64 or 0x100**8
            n.exp += 1
            n.man = n.man >> 1
        
        # underflow
        if n.exp < 0:
            n.exp = 0
        
        # overflow    
        if n.exp > 0xff:
            # overflow
            # message does not break execution, no line number
            print_error(6, -1)
            n.exp = 0xff
            n.man = n.carry_mask #0xffffffffffffff00L
        
    def to_python_float(self):
        self.apply_carry()
        
        man = self.man >> 8
        val = man * 2**(self.exp - self.bias)
        
        if self.neg:
            return -val
        else:
            return val    


    
    def floor(self):
        # discards carry & truncates towards neg infty, returns mbf
        if self.is_zero():
            return
        
        n = self.from_int(self.trunc_to_int())
        
        if equals(self, n) or not n.neg:
            pass
        else:
            self = sub(n, n.one) 


    def round(self):
        #n = n_in.copy()
        
        if self.exp-self.bias > 0:
            self.man = long(self.man * 2**(self.exp-self.bias))
        else:
            self.man = long(self.man / 2**(-self.exp+self.bias))
        self.exp = self.bias
        
        # carry bit set? then round up (moves exponent on overflow)
        self.apply_carry()
        self.normalise()
        

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
    

Single.zero = from_bytes('\x00\x00\x00\x00')
Single.half = from_bytes('\x00\x00\x00\x80')
Single.one  = from_bytes('\x00\x00\x00\x81')
Single.two  = from_bytes('\x00\x00\x00\x82')
Single.ten  = from_bytes('\x00\x00\x20\x84')
Single.max  = from_bytes('\xff\xff\x7f\xff')
Single.e    = from_bytes('\x54\xf8\x2d\x82')
Single.pi   = from_bytes('\xdb\x0f\x49\x82')
Single.log2 = from_bytes('\x16\x72\x31\x80')    # ln 2


Double.zero = from_bytes('\x00\x00\x00\x00\x00\x00\x00\x00')
Double.half = from_bytes('\x00\x00\x00\x00\x00\x00\x00\x80')
Double.one  = from_bytes('\x00\x00\x00\x00\x00\x00\x00\x81')
Double.two  = from_bytes('\x00\x00\x00\x00\x00\x00\x00\x82')
Double.ten  = from_bytes('\x00\x00\x00\x00\x00\x00\x20\x84')
Double.max  = from_bytes('\xff\xff\xff\xff\xff\xff\x7f\xff')
Double.e    = from_bytes('\x4b\xbb\xa2\x58\x54\xf8\x2d\x82')
Double.pi   = from_bytes('\xc2\x68\x21\xa2\xda\x0f\x49\x82')


####################################    
    
# 9999999, highest float less than 10e+7
Single.lim_top = from_bytes([ '\x7f', '\x96', '\x18', '\x98' ])
# 999999.9, highest float  less than 10e+6
Single.lim_bot = from_bytes([ '\xff', '\x23', '\x74', '\x94' ])
    
# lowest float greater than 10e+16 ?
# 10**16 ['0x0L', '0x0L', '0x4L', '0xbfL', '0xc9L', '0x1bL', '0xeL', '0xb6']
# no, need highest float less than 10e+16
Double.lim_top = from_bytes([ '\xff', '\xff', '\x03', '\xbf', '\xc9', '\x1b', '\x0e', '\xb6' ])
# highest float less than 10e+15 ?
# 10**15 ['\x0L', '\x0L', '\xa0L', '\x31L', '\xa9L', '\x5fL', '\x63L', '\xb2']
Double.lim_bot = from_bytes([ '\xff', '\xff', '\x9f', '\x31', '\xa9', '\x5f', '\x63', '\xb2' ])



    

    
    


        
def add_nonormalise(left_in, right_in):
    
    if left_in.is_zero():
        return right_in.copy()
    if right_in.is_zero():
        return left_in.copy()
        
    # ensure right has largest exponent
    if left_in.exp > right_in.exp:
        left = right_in.copy()
        right = left_in.copy()
    else:
        left = left_in.copy()
        right = right_in.copy()
    
    # denormalise left to match exponents
    while left.exp < right.exp:
        left.exp += 1
        left.man = left.man >> 1


    # add mantissas, taking sign into account
    if (left.neg == right.neg):
        left.man += right.man
    else:
        if left.man>right.man:
            left.man -= right.man    
        else:
            left.man = right.man - left.man
            left.neg = right.neg         
    return left



def add(left_in, right_in):
    n_out = add_nonormalise(left_in, right_in)
    n_out.normalise()
    return n_out        



def mul10_nonormalise(n_in):    
    n = n_in.copy()

    if n.is_zero():
        return n
    
    m = n_in.copy()
    n.exp += 2
    
    m = add_nonormalise(m, n)            
    m.exp += 1    
        
    return m



def mul10(n_in):
    n_out = mul10_nonormalise(n_in)
    n_out.normalise()
    return n_out

    
    

def mul(left_in, right_in):    
    
    if left_in.is_zero():
        return left_in.copy()
    
    if right_in.is_zero():
        return right_in.copy()
    
    prod = left_in.new()
    prod.exp = left_in.exp + right_in.exp - left_in.bias - 8
    prod.neg = (left_in.neg != right_in.neg)
    prod.man = long(left_in.man * right_in.man)
    prod.normalise()
    
    return prod
    
    
    


def div(left_in, right_in):
    
    if left_in.is_zero():
        return left_in.copy()
    
    if right_in.is_zero():
        print_error(11, -1)
        return left_in.max

    work = left_in.copy()
    denom = right_in.copy()
    
    quot = left_in.new()
    # subtract exponentials
    quot.exp = left_in.exp - right_in.exp + left_in.bias + 8
    # signs
    quot.neg = (left_in.neg != right_in.neg)
    
    # long division of mantissas
    quot.man = 0L 
    quot.exp += 1
    
    while (denom.man > 0 ):
        quot.man = quot.man << 1
        quot.exp -= 1
        
        if work.man > denom.man:
            work.man -= denom.man
            quot.man += 1L
            
        denom.man = denom.man >> 1     
    quot.normalise()
    return quot
         


def div10(n):
    return div(n, n.ten)
    
    
# absolute value is greater than
def abs_gt (left, right):
    if left.exp != right.exp:
        return  (left.exp > right.exp)     
    return (left.man > right.man)     

   
# greater than    
def gt (left, right):
    if left.neg and not right.neg:
        return False
    elif right.neg and not left.neg:
        return True    
    # signs are the same
    return left.neg != abs_gt(left, right)
    
  
 

def equals(left, right):
    return left.neg == right.neg and left.exp==right.exp and left.man & left.carry_mask == right.man & right.carry_mask
    
def equals_inc_carry(left, right, grace_bits=0):
    return left.neg == right.neg and left.exp==right.exp and abs(left.man -right.man) < (1<<grace_bits) 
    
 
def sq(n):
    return mul(n, n)


def sub(left, right_in):
    right = right_in.copy()
    right.neg = not right.neg
    return add(left, right)

def neg(n_in):
    n = n_in.copy()
    n.neg = not n.neg
    return n
  
  
        
# mbf raised to integer exponent
# exponentiation by squares
def pow_int(base, exp):
    if exp < 0:
        return div(base.one, pow_int(base, -exp))

    elif exp > 1:
        if (exp%2) == 0:
            return sq(pow_int(base, exp/2))
        else:
            return mul(base, sq(pow_int(base, (exp-1)/2)))
    elif exp == 0:
        return base.one
    else:
        return base

    



def bring_to_range(mbf, lim_bot, lim_top):
    exp10 = 0    
    while abs_gt(mbf, lim_top):
        mbf = div10(mbf)
        exp10 += 1
        
    while abs_gt(lim_bot, mbf):
        mbf = mul10(mbf)
        exp10 -= 1
    
    # round off carry byte before doing the decimal rounding
    # this brings results closer in line with GW-BASIC output 
    mbf.apply_carry()
    #mbf.discard_carry()
    
    # round to integer: first add one half
    mbf = add(mbf, mbf.half)
    #mbf.apply_carry()
    
    # then truncate to int (this throws away carry)
    num = abs(mbf.trunc_to_int())
    # round towards neg infinity when negative
    if mbf.neg:
        num += 1
    
    return num, exp10



    
    

        
    
    
# screen=True (ie PRINT) - leading space, no type sign
# screen='w' (ie WRITE) - no leading space, no type sign
# default mode is for LIST    
def to_str(n_in, screen=False, write=False):
    mbf = n_in.copy()
    valstr = ''
    if isinstance(n_in, Double):
        type_sign, exp_sign = '#', 'D'
    else:
        type_sign, exp_sign = '!', 'E'
    
    # zero exponent byte means zero
    if mbf.is_zero(): 
        if screen and not write:
            valstr = ' 0'
        else:
            valstr = '0'+type_sign
        return valstr
    
    # print sign
    if mbf.neg:
        valstr = '-'
    else:
        if screen and not write:
            valstr=' '
        else:
            valstr = ''
    
    num, exp10 = bring_to_range(mbf, mbf.lim_bot, mbf.lim_top)
    digitstr = get_digits(num, mbf.digits)
    
    # exponent for scientific notation
    exp10 += mbf.digits-1  
    
    if (exp10>mbf.digits-1 or len(digitstr)-exp10>mbf.digits+1):
        # use scientific notation
        valstr += scientific_notation(digitstr, exp10, exp_sign)
    else:
        # use decimal notation
        if screen or write:
            type_sign=''
        valstr += decimal_notation(digitstr, exp10, type_sign)
    
    return valstr
    
    
    
##################################
    


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
    zeros=0
      
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
                #found_digits = True
                mantissa *=10
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
            #print "parsing error 2"
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
        
    if is_double:
        mbf = Double()
    else:
        mbf = Single()

    mbf.neg = neg
    mbf.exp = mbf.bias
    mbf.man = mantissa * 0x100
    mbf.normalise()
    
    while (exp10 < 0):
        mbf = div10 (mbf)
        exp10 += 1
        
    while (exp10 > 0):
        mbf = mul10 (mbf)
        exp10 -= 1
        
    mbf.normalise()    
    return mbf
        

###########################################
        
 
 
##########################################
#
# single precision math        
        
        
# mbf raised to mbf exponent
def mbf_pow(base_in, exp_in):
    base = base_in.copy()
    exp = exp_in.copy()
    
    if exp.is_zero():
        # 0^0 returns 1 too
        return Single.one
        
    elif exp.neg:
        exp.neg = False
        return div(Single.one, mbf_pow(base, exp))

    else:
        shift = exp.exp - 0x81
        exp.exp = 0x81
        
        while shift < 0:
            base = mbf_sqrt(base)
            shift += 1

        # to avoid doing sqrt(sq( ...
        roots = []
        while shift > 0:
            roots.append(base)
            base = sq(base)
            shift -= 1
        
        # exp.exp = 0x81 means exp's exponent is one  
        # and most significant mantissa bit must be 1  
        
        # we have 0x80 00 00 (00) <=exp.mant <= 0xff ff ff (ff) 
        # exp.mant == 1011... means exp == 1 + 0/2 + 1/4 + 1/8 + ...
        # meaning we return base * 0**sqrt(base) * 1**sqrt(sqrt(base)) * 1**sqrt(sqrt(sqrt(base))) * ...
        
        bit = 0x40000000 # skip most significant bit, we know it's one
        exp.man &= 0x7fffffff
        out = base
        count = 0
        while exp.man >= 0x7f and bit >= 0x7f :
            
            if len(roots) > count:
                base = roots[-count-1]
            else:
                base = mbf_sqrt(base)
            count += 1

            if exp.man & bit:
                out = mul(out, base)
            exp.man = exp.man & ~bit
            bit = bit >> 1
            
        return out



# square root
# Newton's method
def mbf_sqrt(target):
    if target.neg:
        # illegal function call
        raise error.RunError(5)
    if target.is_zero() or equals(target, Single.one):
        return target

    # initial guess, divide exponent by 2
    n = target.copy()
    
    n.exp = (n.exp - n.bias+24)/2 + n.bias-24
    
    # iterate to convergence, max_iter = 7
    for _ in range (0,7):
        nxt = sub(n, mul(Single.half, div( sub(sq(n), target), n )))  
        # check convergence
        if equals_inc_carry(nxt,n):
            break
        n = nxt
        
    return n

    





# trig functions

mbf_taylor = [
    Single.one,                      # 1/0!
    Single.one,                      # 1/1!
    Single.half,                     # 1/2
    from_bytes('\xab\xaa\x2a\x7e'),  # 1/6
    from_bytes('\xab\xaa\x2a\x7c'),  # 1/24
    from_bytes('\x89\x88\x08\x7a'),  # 1/120
    from_bytes('\x61\x0b\x36\x77'),  # 1/720
    from_bytes('\x01\x0D\x50\x74'),  # 1/5040
    from_bytes('\x01\x0D\x50\x71'),  # 1/40320
    from_bytes('\x1d\xef\x38\x6e'),  # 1/362880
    from_bytes('\x7e\xf2\x13\x6b'),  # 1/3628800
    from_bytes('\x2b\x32\x57\x67'),  # 1/39916800
    ]


Single.twopi = mul(Single.pi, Single.two) 
Single.pi2 = mul(Single.pi, Single.half)
Single.pi4 = mul(Single.pi2, Single.half)

            
def mbf_sin(n_in):
    if n_in.is_zero():
        return n_in
    n = n_in.copy()
    
    neg = n.neg
    n.neg = False 
    sin = Single.zero
    
    if gt(n, Single.twopi):
        n = sub(n, mul(Single.twopi, div(n, Single.twopi).floor()))
    if gt(n, Single.pi):
        neg = not neg     
        n = sub(n, Single.pi)
    if gt(n, Single.pi2):
        n = sub(Single.pi, n)    
    if gt(n, Single.pi4):
        n = sub(n, Single.pi2)
        sin = mbf_cos(n)    
    else:
        termsgn = False
        for expt in range(1,12,2):
            term = mul(mbf_taylor[expt], pow_int(n, expt)) 
            term.neg = termsgn
            termsgn = not termsgn
            sin = add(sin, term) 
        
    sin.neg = sin.neg ^ neg    
    return sin




# e raised to mbf exponent
def mbf_exp(arg_in):
    arg = arg_in.copy()
    
    if arg.is_zero():
        return Single.one
        
    elif arg.neg:
        arg.neg = False
        return div(Single.one, mbf_exp(arg))
    
    exp = Single.zero
    for npow in range(0,12):
        term = mul(mbf_taylor[npow], pow_int(arg, npow)) 
        exp = add(exp, term) 
    return exp


def mbf_cos(n_in):
    if n_in.is_zero():
        return Single.one
        
    n = n_in.copy()
    
    neg = False
    n.neg = False 
    cos = Single.one
    
    if gt(n, Single.twopi):
        n = sub(n, mul(Single.twopi, div(n, Single.twopi).floor()))
    if gt(n, Single.pi):
        neg = not neg     
        n = sub(n, Single.pi)
    if gt(n, Single.pi2):
        neg = not neg     
        n = sub(Single.pi, n)    
    if gt(n, Single.pi4):
        neg = not neg
        n = sub(n, Single.pi2)
        cos = mbf_sin(n)    
    else:
        termsgn = True
        for expt in range(2,11,2):
            term = mul(mbf_taylor[expt], pow_int(n, expt)) 
            term.neg = termsgn
            termsgn = not termsgn
            cos = add(cos, term) 
        
    cos.neg = cos.neg ^ neg    
    return cos


def mbf_tan(n_in):
    return div(mbf_sin(n_in), mbf_cos(n_in))


# atn and log, don't know what algorithm MS use.

# find arctangent using secant method
def mbf_atn(n_in):
    if n_in.is_zero():
        return n_in
    if equals(n_in, Single.one):
        return Single.pi4
    if gt(n_in, Single.one):
        # atn (1/x) = pi/2 - atn(x) 
        return sub(Single.pi2, mbf_atn(div(Single.one, n_in)))
    if n_in.neg:
        n = n_in.copy()
        n.neg = False
        n = mbf_atn(n)
        n.neg = True
        return n
        
    # calculate atn of x between 0 and 1 which is between 0 and pi/4
    # also, in that range, atn(x) <= x and atn(x) >= x*pi/4

#    hi = n_in.copy()
#    if gt(hi, Single.pi4):
#        hi = Single.pi4
#        tan_hi = Single.one
#    else:
#        tan_hi = mbf_tan(hi)
#    lo = mul(Single.pi4, n_in)
#    tan_lo = mbf_tan(lo)
#    count = 0 
   
    last = Single.pi4
    tan_last = Single.one

    guess = mul(Single.pi4, n_in)
    tan = mbf_tan(guess)    
    
    count = 0 
    while (guess.exp != last.exp or abs(guess.man-last.man) > 0x100) and count<30:
        count+=1
        guess, last = add(guess, mul( sub(n_in, tan), div(sub(last, guess), sub(tan_last, tan)) ) ), guess
        tan, tan_last = mbf_tan(guess), tan
    
    return guess






# natural logarithm
def mbf_log(n_in):
    if equals(n_in, Single.one):
        return Single.zero
    if equals(n_in, Single.two):
        return Single.log2
    
    if not gt(n_in, Single.zero):
        raise error.RunError(5)
    if equals(n_in, Single.one):
        return Single.zero
    
    if gt(n_in, Single.one):
        # log (1/x) = -log(x)
        
        n = mbf_log(div(Single.one, n_in).apply_carry())
        n.neg = not n.neg
        return n
    
    # if n = a*2^b, log(n) = log(a) + b*log(2)
    expt = n_in.exp - n_in.bias + 24
    loge = mul(Single.log2, Single.from_int(expt))
    
    n = n_in.copy()
    n.exp = n.bias - 24
    
    # our remaining input a is the mantissa, between 0.5 and 1.
    # lo is log(0.5) = -log(2), hi is zero
    # also log(x) above -log(2) + x- 0.5
    # and below 1-x
    
    # 1-n
    hi = n.copy()
    hi.man = 0xffffffff - hi.man
    hi.neg = True
    
    lo = Single.log2.copy()
    lo.neg= True 
    
#    count = 0
#    while not equals(lo, hi) and not (lo.exp==hi.exp and abs(hi.man-lo.man)<0x100) and count<50: 
#        count+=1
#        mid = mul(Single.half, add(hi, lo)) 
#        exp = mbf_exp(mid) 
#        
#        if gt(exp, n):
#            hi = mid.copy()
#        else:
#            lo = mid.copy()  
#    loge = add(mid, loge)
#    return loge
    
    
    last = hi
    f_last = mbf_exp(last)
    guess = lo
    f_guess = mbf_exp(guess)
    
    count = 0 
    while not equals(guess, last) and not equals(f_guess, f_last) and count<30:
        count+=1
        guess, last = add(guess, mul( sub(n, f_guess), div(sub(last, guess), sub(f_last, f_guess)) ) ), guess
        f_guess, f_last = mbf_exp(guess), f_guess
    
    loge = add(guess, loge)
    return loge.apply_carry() 
    
    
    

