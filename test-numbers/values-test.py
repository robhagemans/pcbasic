
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pcbasic.basic.numbers import *
from pcbasic.basic import numbers

if __name__ == '__main__':
    for i in range(127,130):
        a = Single().from_int(i)
        r = Single().from_int(2**23)
        r.iadd(a)
        s = r.clone()
        s.view()[-1:] = chr(ord(s.view()[-1])+8)
        t = s.clone()
        print s.iadd(r).isub(t).isub(r).to_value(),

    print


    # with open('ALLWORD.DAT', 'wb') as f:
    #     for i in range(256):
    #         for j in range(256):
    #             f.write(chr(j)+chr(i)+'\0'+'\x80')

    print 'allbytes-add'

    with open('input/ALLWORD.DAT', 'rb') as f:
        with open ('model/GWBASABY.DAT', 'rb') as h:
            with open('output/ADDBYTE.DAT', 'wb') as g:
                    while True:

                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray(chr(buf[0])+'\0\0'+chr(0x80))
                        bufr = bytearray(chr(buf[1])+'\0\0'+chr(0x80))

                        l = Single(bufl)
                        bufs = str(bufl), str(bufr)
                        r = Single(bufr)
                        out = str(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print format(numbers.lden_s, '032b'), format(numbers.rden_s, '032b'), out.encode('hex')[:2], inp.encode('hex')[:2], bin(numbers.pden_s), bufs


    print 'allbytes-sub'

    with open('input/ALLWORD.DAT', 'rb') as f:
        with open ('model/GWBASSBY.DAT', 'rb') as h:
            with open('output/SUBBYTE.DAT', 'wb') as g:
                    while True:

                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray(chr(buf[0])+'\0\0'+chr(0x80))
                        bufr = bytearray(chr(buf[1])+'\0\0'+chr(0x80))

                        l = Single(bufl)
                        bufs = str(bufl), str(bufr)
                        r = Single(bufr)
                        out = str(l.isub(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print format(numbers.lden_s, '032b'), format(numbers.rden_s, '032b'), out.encode('hex')[:2], inp.encode('hex')[:2], bin(numbers.pden_s), bufs

    print 'allshifts'

    for shift in [0,]+range(9, 11):
        r = Single()
        letter = chr(ord('0')+shift) if shift<10 else chr(ord('A')-10+shift)
        print letter

        with open('input/ALLWORD.DAT', 'rb') as f:
            with open ('model/GWBASAL'+letter+'.DAT', 'rb') as h:
                with open('output/ALLWORD'+letter+'.DAT', 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = chr(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = '\0\x80'
                            r = Single(buf)
                            ll = l.clone()
                            bufs = str(l.to_bytes()), str(buf)
                            out = str(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            if out != inp:
                                print format(numbers.lden_s, '032b'), format(numbers.rden_s, '032b'), out.encode('hex')[:2], inp.encode('hex')[:2], bin(numbers.pden_s), bufs
#                                print format(lden_s, '032b'), format(rden_s, '032b'), out.encode('hex')[:2], inp.encode('hex')[:2], bin(pden_s), bin(carry_s), bufs
                            l = ll


    #import sys
    #sys.exit(0)
    print 'lowshifts'

    for shift in range(17):
        r = Single()
        letter = chr(ord('0')+shift) if shift<10 else chr(ord('A')-10+shift)
        print letter

        with open('input/BYTES.DAT', 'rb') as f:
            with open ('model/GWBASLO'+letter+'.DAT', 'rb') as h:
                with open('output/LO'+letter+'.DAT', 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = chr(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = '\0\x80'
                            r = Single(buf)
                            ll = l.clone()
                            bufs = str(l.to_bytes()), str(buf)
                            out = str(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            if out != inp:
                                print format(lden_s, '032b'), format(rden_s, '032b'), out.encode('hex')[:2], inp.encode('hex')[:2], bin(pden_s), bufs, numbers.sden_s
                            l = ll


    print 'bytes'

    r = Single()
    with open('input/BYTES.DAT', 'rb') as f:
        with open ('model/GWBASADD.DAT', 'rb') as h:
            with open('output/ADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf)
                        ll = l.clone()
                        bufs = str(l.to_bytes()), str(buf)
                        out = str(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print format(numbers.lden_s>>8, '025b'), format(numbers.lden_s & 0xff, '08b'),
                            print format(numbers.rden_s>>8, '025b'), format(numbers.rden_s & 0xff, '08b'),
                            print out.encode('hex')[:2], inp.encode('hex')[:2],
                            print format(numbers.pden_s>>8, '025b'), format(numbers.pden_s & 0xff, '08b'),
                            print format(numbers.sden_s>>8, '025b'), format(numbers.sden_s & 0xff, '08b')
                        l = ll

    print 'bigbytes'

    r = Single()
    with open('input/BIGBYTES.DAT', 'rb') as f:
        with open ('model/GWBIGADD.DAT', 'rb') as h:
            with open('output/BIGADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf)
                        ll = l.clone()
                        bufs = str(l.to_bytes()), str(buf)
                        out = str(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print format(numbers.lden_s>>8, '025b'), format(numbers.lden_s & 0xff, '08b'),
                            print format(numbers.rden_s>>8, '025b'), format(numbers.rden_s & 0xff, '08b'),
                            print out.encode('hex')[:2], inp.encode('hex')[:2],
                            print format(numbers.pden_s>>8, '025b'), format(numbers.pden_s & 0xff, '08b'),
                            print format(numbers.sden_s>>8, '025b'), format(numbers.sden_s & 0xff, '08b')
                        l = ll


    print 'bigmul'

    r = Single()
    with open('input/BIGBYTES.DAT', 'rb') as f:
        with open ('model/GWBIGMUL.DAT', 'rb') as h:
            with open('output/BIGMUL.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf)
                        ll = l.clone()
                        bufs = str(l.to_bytes()), str(buf)
                        try:
                            l.imul(r)
                        except OverflowError:
                            pass
                        out = str(l.to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print bufs[0].encode('hex'), '*', bufs[1].encode('hex'), '==', out.encode('hex'), '!=', inp.encode('hex'),
                            print format(numbers.lden_s>>8, '025b'), format(numbers.lden_s & 0xff, '08b'),
                            print format(numbers.rden_s>>8, '025b'), format(numbers.rden_s & 0xff, '08b'),
                            print format(numbers.pden_s>>8, '025b'), format(numbers.pden_s & 0xff, '08b'),
                            print numbers.sden_s #format(numbers.sden_s>>8, '025b'), format(numbers.sden_s & 0xff, '08b')
                        l = ll
