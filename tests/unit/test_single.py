"""
PC-BASIC test.single
unit tests for single precision MBF floats

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
from binascii import hexlify
import unittest

from pcbasic.compat import int2byte
from pcbasic.basic.values import Values, Single


HERE = os.path.dirname(os.path.abspath(__file__))


# ALLWORD.DAT is generated like so:
# with open('input/ALLWORD.DAT', 'wb') as f:
#     for i in range(256):
#         for j in range(256):
#             f.write(int2byte(j)+int2byte(i)+'\0'+'\x80')


def open_input(name):
    """Open test input file."""
    return open(os.path.join(HERE, 'input', 'single', name), 'rb')

def open_model(name):
    """Open test model file."""
    return open(os.path.join(HERE, 'model', 'single', name), 'rb')

def open_output(name):
    """Open test output file."""
    return open(os.path.join(HERE, 'output', 'single', name), 'wb')



class TestSingle(unittest.TestCase):
    """Test frame for single-precision MBF math."""

    def setUp(self):
        """Create the Values object."""
        self._vm = Values(None, False)
        try:
            os.makedirs(os.path.join(HERE, 'output', 'single'))
        except EnvironmentError:
            pass

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
        with open_input('ALLWORD.DAT') as f:
            with open_model('GWBASABY.DAT') as h:
                with open_output('ADDBYTE.DAT') as g:
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
        with open_input('ALLWORD.DAT') as f:
            with open_model('GWBASSBY.DAT') as h:
                with open_output('SUBBYTE.DAT') as g:
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

    def _cmp_add_exponents(self, shift, finput, model, output):
        """Adding with various exponents."""
        r = self._vm.new_single()
        with open_input(finput) as f:
            with open_model(model) as h:
                with open_output(output) as g:
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

    def test_exponents(self):
        """Test adding with various exponents."""
        for shift in [0,] + list(range(9, 11)):
            letter = ord('0')+shift if shift<10 else ord('A')-10+shift
            model = 'GWBASAL%c.DAT' % (letter,)
            output = 'ALLWORD%c.DAT' % (letter,)
            self._cmp_add_exponents(shift, 'ALLWORD.DAT', model, output)

    def test_exponents_low(self):
        """Test adding with various exponents."""
        for shift in range(17):
            letter = ord('0')+shift if shift<10 else ord('A')-10+shift
            model = 'GWBASLO%c.DAT' % (letter,)
            output = 'LO%c.DAT' % (letter,)
            self._cmp_add_exponents(shift, 'BYTES.DAT', model, output)

    def _comp_add_bytes(self, finput, model, output):
        """Additions on random generated byte sequences."""
        fails = {}
        r = self._vm.new_single()
        with open_input(finput) as f:
            with open_model(model) as h:
                with open_output(output) as g:
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
        return fails

    def test_bytes(self):
        """Test additions on random generated byte sequences."""
        fails = self._comp_add_bytes('BYTES.DAT', 'GWBASADD.DAT', 'ADD.DAT')
        # two additions are slightly different
        accepted = {
            b'920a03ce': b'930a03ce',
            b'52810dbe': b'53810dbe',
        }
        assert fails == accepted

    def test_bigbytes(self):
        """Test additions on random generated byte sequences."""
        fails = self._comp_add_bytes('BIGBYTES.DAT', 'GWBIGADD.DAT', 'BIGADD.DAT')
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
        with open_input('BIGBYTES.DAT') as f:
            with open_model('GWBIGMUL.DAT') as h:
                with open_output('BIGMUL.DAT') as g:
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
