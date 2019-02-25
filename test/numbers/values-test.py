
import sys
import os
from binascii import hexlify
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, '..', '..'))

from pcbasic.compat import int2byte
from pcbasic.basic.values import *
import pcbasic.basic.values
from pcbasic.basic.values.numbers import *
from pcbasic.basic.values import numbers

# ALLWORD.DAT is generated like so:
# with open('input/ALLWORD.DAT', 'wb') as f:
#     for i in range(256):
#         for j in range(256):
#             f.write(int2byte(j)+int2byte(i)+'\0'+'\x80')


class TestSingle(unittest.TestCase):
    """Test frame for single-precision MBF math."""

    def setUp(self):
        """Create the Values object."""
        self._vm = values.Values(None, False)

    def test_single(self):
        """Test MBF single representation."""
        result = []
        for i in range(0, 255):
            a = self._vm.new_single().from_int(i)
            r = self._vm.new_single().from_int(2**23)
            r.iadd(a)
            s = r.clone()
            s.view()[-1:] = int2byte(bytearray(s.view())[-1] + 8)
            t = s.clone()
            result.append(s.iadd(r).isub(t).isub(r).to_value())
        model = [1.0*_i for _i in list(range(0, -129, -1)) + list(range(127, 1, -1))]
        assert result == model

    def test_all_bytes_add(self):
        """Test adding singles, all first-byte combinations."""
        with open('input/ALLWORD.DAT', 'rb') as f:
            with open('model/GWBASABY.DAT', 'rb') as h:
                with open('output/ADDBYTE.DAT', 'wb') as g:
                    while True:
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray(b'%c\0\0\x80' % buf[0])
                        bufr = bytearray(b'%c\0\0\x80' % buf[1])
                        l = Single(bufl, self._vm)
                        r = Single(bufr, self._vm)
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        assert out == inp

    def test_all_bytes_sub(self):
        """Test subtracting singles, all first-byte combinations."""
        with open('input/ALLWORD.DAT', 'rb') as f:
            with open ('model/GWBASSBY.DAT', 'rb') as h:
                with open('output/SUBBYTE.DAT', 'wb') as g:
                    while True:
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        bufl = bytearray(b'%c\0\0\x80' % buf[0])
                        bufr = bytearray(b'%c\0\0\x80' % buf[1])
                        l = Single(bufl, self._vm)
                        r = Single(bufr, self._vm)
                        out = bytes(l.isub(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        assert out == inp

    def test_exponents(self):
        """Test adding with various exponents."""
        for shift in [0,] + list(range(9, 11)):
            r = self._vm.new_single()
            letter = ord('0')+shift if shift<10 else ord('A')-10+shift
            with open('input/ALLWORD.DAT', 'rb') as f:
                with open('model/GWBASAL%c.DAT' % (letter,), 'rb') as h:
                    with open('output/ALLWORD%c.DAT' % (letter,), 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = int2byte(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = b'\0\x80'
                            r = Single(buf, self._vm)
                            ll = l.clone()
                            out = bytes(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            l = ll
                            assert out == inp


    def test_exponents_low(self):
        """Test adding with various exponents."""
        for shift in range(17):
            r = self._vm.new_single()
            letter = ord('0')+shift if shift<10 else ord('A')-10+shift
            with open('input/BYTES.DAT', 'rb') as f:
                with open ('model/GWBASLO%c.DAT' % (letter,), 'rb') as h:
                    with open('output/LO%c.DAT' % (letter,), 'wb') as g:
                        while True:
                            l = r
                            l.view()[3:] = int2byte(0x80+shift)
                            buf = bytearray(f.read(4))
                            if len(buf) < 4:
                                break
                            buf[2:] = b'\0\x80'
                            r = Single(buf, self._vm)
                            ll = l.clone()
                            out = bytes(l.iadd(r).to_bytes())
                            g.write(out)
                            inp = h.read(4)
                            l = ll
                            assert out == inp

    def test_bytes(self):
        """Test additions on random generated byte sequences."""
        fails = {}
        r = self._vm.new_single()
        with open('input/BYTES.DAT', 'rb') as f:
            with open ('model/GWBASADD.DAT', 'rb') as h:
                with open('output/ADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, self._vm)
                        ll = l.clone()
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            fails[hexlify(inp)] = hexlify(out)
                        l = ll
        # two additions are slightly different
        accepted = {
            b'920a03ce': b'930a03ce',
            b'52810dbe': b'53810dbe',
        }
        assert fails == accepted

    def test_bigbytes(self):
        """Test additions on random generated byte sequences."""
        fails = {}
        r = self._vm.new_single()
        with open('input/BIGBYTES.DAT', 'rb') as f:
            with open ('model/GWBIGADD.DAT', 'rb') as h:
                with open('output/BIGADD.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, self._vm)
                        ll = l.clone()
                        out = bytes(l.iadd(r).to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        if out != inp:
                            fails[hexlify(inp)] = hexlify(out)
                        l = ll
        accepted = {
            b'922ed14b': b'932ed14b',
            b'80c02477': b'81c02477',
            b'fe4b89df': b'ff4b89df',
            b'a9b37594': b'a8b37594',
            b'bc3e8549': b'bd3e8549',
            b'b2337a91': b'b3337a91',
            b'2ef4007a': b'2ff4007a'
        }
        assert fails == accepted

    def test_mult(self):
        """Test multiplications on random generated byte sequences."""
        r = self._vm.new_single()
        with open('input/BIGBYTES.DAT', 'rb') as f:
            with open ('model/GWBIGMUL.DAT', 'rb') as h:
                with open('output/BIGMUL.DAT', 'wb') as g:
                    while True:
                        l = r
                        buf = bytearray(f.read(4))
                        if len(buf) < 4:
                            break
                        r = Single(buf, self._vm)
                        ll = l.clone()
                        try:
                            l.imul(r)
                        except OverflowError:
                            pass
                        out = bytes(l.to_bytes())
                        g.write(out)
                        inp = h.read(4)
                        l = ll
                        assert out == inp

if __name__ == '__main__':
    unittest.main()
