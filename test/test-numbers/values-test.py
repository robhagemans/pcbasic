
import sys
import os
from binascii import hexlify

from six import int2byte

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pcbasic.basic.values import *
import pcbasic.basic.values
from pcbasic.basic.values.numbers import *
from pcbasic.basic.values import numbers


if __name__ == '__main__':
    vm = values.Values(None, None, False)
    for i in range(127,130):
        a = vm.new_single().from_int(i)
        r = vm.new_single().from_int(2**23)
        r.iadd(a)
        s = r.clone()
        s.view()[-1:] = int2byte(ord(s.view()[-1])+8)
        t = s.clone()
        print s.iadd(r).isub(t).isub(r).to_value(),

    print


    # with open('ALLWORD.DAT', 'wb') as f:
    #     for i in range(256):
    #         for j in range(256):
    #             f.write(int2byte(j)+int2byte(i)+'\0'+'\x80')

    print 'allbytes-add'

    with open('input/ALLWORD.DAT', 'rb') as f:
        with open ('model/GWBASABY.DAT', 'rb') as h:
            with open('output/ADDBYTE.DAT', 'wb') as g:
                    while True:

                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray('%c\0\0\80' % buf[0])
                        bufr = bytearray('%c\0\0\80' % buf[1])

                        l = Single(bufl, vm)
                        bufs = bytes(bufl), bytes(bufr)
                        r = Single(bufr, vm)
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print hexlify(out), hexlify(inp)


    print 'allbytes-sub'

    with open('input/ALLWORD.DAT', 'rb') as f:
        with open ('model/GWBASSBY.DAT', 'rb') as h:
            with open('output/SUBBYTE.DAT', 'wb') as g:
                    while True:

                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray('%c\0\0\80' % buf[0])
                        bufr = bytearray('%c\0\0\80' % buf[1])

                        l = Single(bufl, vm)
                        bufs = bytes(bufl), bytes(bufr)
                        r = Single(bufr, vm)
                        out = bytes(l.isub(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print hexlify(out), hexlify(inp)

    print 'allshifts'

    for shift in [0,]+range(9, 11):
        r = vm.new_single()
        letter = int2byte(ord('0')+shift) if shift<10 else int2byte(ord('A')-10+shift)
        print letter

        with open('input/ALLWORD.DAT', 'rb') as f:
            with open ('model/GWBASAL'+letter+'.DAT', 'rb') as h:
                with open('output/ALLWORD'+letter+'.DAT', 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = int2byte(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = '\0\x80'
                            r = Single(buf, vm)
                            ll = l.clone()
                            bufs = bytes(l.to_bytes()), bytes(buf)
                            out = bytes(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            if out != inp:
                                print hexlify(out), hexlify(inp)
                            l = ll


    #import sys
    #sys.exit(0)
    print 'lowshifts'

    for shift in range(17):
        r = vm.new_single()
        letter = int2byte(ord('0')+shift) if shift<10 else int2byte(ord('A')-10+shift)
        print letter

        with open('input/BYTES.DAT', 'rb') as f:
            with open ('model/GWBASLO'+letter+'.DAT', 'rb') as h:
                with open('output/LO'+letter+'.DAT', 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = int2byte(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = '\0\x80'
                            r = Single(buf, vm)
                            ll = l.clone()
                            bufs = bytes(l.to_bytes()), bytes(buf)
                            out = bytes(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            if out != inp:
                                print hexlify(out), hexlify(inp)
                            l = ll


    print 'bytes'

    r = vm.new_single()
    with open('input/BYTES.DAT', 'rb') as f:
        with open ('model/GWBASADD.DAT', 'rb') as h:
            with open('output/ADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, vm)
                        ll = l.clone()
                        bufs = bytes(l.to_bytes()), bytes(buf)
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print hexlify(out), hexlify(inp)
                        l = ll

    print 'bigbytes'

    r = vm.new_single()
    with open('input/BIGBYTES.DAT', 'rb') as f:
        with open ('model/GWBIGADD.DAT', 'rb') as h:
            with open('output/BIGADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, vm)
                        ll = l.clone()
                        bufs = bytes(l.to_bytes()), bytes(buf)
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print hexlify(out), hexlify(inp)
                        l = ll


    print 'bigmul'

    r = vm.new_single()
    with open('input/BIGBYTES.DAT', 'rb') as f:
        with open ('model/GWBIGMUL.DAT', 'rb') as h:
            with open('output/BIGMUL.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, vm)
                        ll = l.clone()
                        bufs = bytes(l.to_bytes()), bytes(buf)
                        try:
                            l.imul(r)
                        except OverflowError:
                            pass
                        out = bytes(l.to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            print hexlify(out), hexlify(inp)
                        l = ll
