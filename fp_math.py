#
# PC-BASIC 3.23 - fp_math.py
#
# MBF Math functions 
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.

import fp

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
        shift = exp.exp - fp.true_bias - 1
        exp.exp = fp.true_bias+1
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
    
