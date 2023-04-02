"""
PC-BASIC test.session
unit tests for pcbasic.base

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os

from pcbasic.basic.base.error import BASICError
from pcbasic.basic.base.signals import Event, QUIT
from pcbasic.basic.base.bytestream import ByteStream
from pcbasic.basic.base.codestream import CodeStream, TokenisedStream
from pcbasic.basic.base.bytematrix import ByteMatrix, hstack, vstack



class BaseTest(unittest.TestCase):
    """Unit tests for small classes in base."""

    def test_exception(self):
        """Test exceptions."""
        assert repr(BASICError(100)) == 'Unprintable error'

    def test_event_signal(self):
        """Test event signals."""
        assert repr(Event(QUIT)) == '<Event quit: ()>'


class ByteStreamTest(unittest.TestCase):
    """Unit tests for bytestream."""

    def test_bytestream_read(self):
        """Test ByteStream read."""
        buf = bytearray(b'12345abcde')
        bs = ByteStream(buf)
        assert bs.read(1) == b'1'
        assert bs.read() == b'2345abcde'
        assert bs.read(1) == b''

    def test_bytestream_write(self):
        """Test ByteStream write."""
        buf = bytearray(b'12345abcde')
        bs = ByteStream(buf)
        bs.write(b'ABCDE')
        # write as changed buffer
        assert buf == bytearray(b'ABCDEabcde')
        # can't write beyond buffer
        with self.assertRaises(ValueError):
            bs.write(b'123456')
        # no change on write error
        assert buf == bytearray(b'ABCDEabcde')

    def test_bytestream_read_closed(self):
        """Test read attempt on closed stream."""
        buf = bytearray(b'12345abcde')
        bs = ByteStream(buf)
        bs.close()
        with self.assertRaises(ValueError):
            bs.read()

    def test_bytestream_read_bad(self):
        """Test read attempt with bad argument."""
        buf = bytearray(b'12345abcde')
        bs = ByteStream(buf)
        with self.assertRaises(TypeError):
            bs.read(b'1')


class CodeStreamTest(unittest.TestCase):
    """Unit tests for code stream."""

    def test_backskip_blank(self):
        """Test backskip_blank."""
        buf = bytearray(b'a  \n\t b')
        cs = CodeStream(buf)
        cs.read(6)
        assert cs.backskip_blank() == b'a'

    def test_read_to(self):
        """Test read_to."""
        buf = bytearray(b'a  \n\t b')
        cs = CodeStream(buf)
        assert cs.read_to(b' ') == b'a'
        assert cs.read_to(b'c') == b'  \n\t b'

    def test_read_name(self):
        """Test read_name."""
        buf = bytearray(b'abc1\0hjk')
        cs = CodeStream(buf)
        assert cs.read_name() == b'ABC1'
        buf = bytearray(b'  abc1$jhjk')
        cs = CodeStream(buf)
        assert cs.read_name() == b'ABC1$'
        buf = bytearray(b'1abc1$jhjk')
        cs = CodeStream(buf)
        assert cs.read_name() == b''

    def test_read_number(self):
        """Test read_number."""
        buf = bytearray(b'123ab')
        cs = CodeStream(buf)
        assert cs.read_number() == b'123'
        buf = bytearray(b'')
        cs = CodeStream(buf)
        assert cs.read_number() == b''
        buf = bytearray(b'a')
        cs = CodeStream(buf)
        assert cs.read_number() == b''
        buf = bytearray(b'&ha')
        cs = CodeStream(buf)
        assert cs.read_number() == b'&Ha'
        buf = bytearray(b'&7')
        cs = CodeStream(buf)
        assert cs.read_number() == b'&O7'

    def test_read_string(self):
        """Test read_string."""
        buf = bytearray(b'123ab')
        cs = CodeStream(buf)
        assert cs.read_string() == b''
        buf = bytearray(b'"123ab"ghj')
        cs = CodeStream(buf)
        cs.end_line = (b'', b'\n')
        assert cs.read_string() == b'"123ab"'
        buf = bytearray(b'"123ab')
        cs = CodeStream(buf)
        cs.end_line = (b'', b'\n')
        assert cs.read_string() == b'"123ab'


class TokenisedStreamTest(unittest.TestCase):
    """Unit tests for tokenised stream."""

    def test_read_number_token(self):
        """Test read_number_token."""
        cs = TokenisedStream()
        cs.write(b'\x0b\x01\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x0b\x01\x00'
        cs.seek(0)
        cs.write(b'\x0c\x01\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x0c\x01\x00'
        cs.seek(0)
        cs.write(b'\x11\x01\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x11'
        cs.seek(0)
        cs.write(b'\x0f\xff\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x0f\xff'
        cs.seek(0)
        cs.write(b'\x1c\xff\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x1c\xff\x00'
        cs.seek(0)
        cs.write(b'\x1d\xff\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b'\x1d\xff\x00gh'
        cs.seek(0)
        cs.write(b'\x1f\xff\x00ghjagh007')
        cs.seek(0)
        assert cs.read_number_token() == b'\x1f\xff\x00ghjagh'
        cs.seek(0)
        cs.write(b'\x00\xff\x00ghja')
        cs.seek(0)
        assert cs.read_number_token() == b''

    def test_skip_to_token_not_found(self):
        """Test skip_to_token where token is not found."""
        cs = TokenisedStream()
        cs.write(b'\x0b\x01\x00ghja')
        cs.seek(0)
        assert cs.skip_to_token(b'\x91') is None

    def test_skip_block_not_found(self):
        """Test skip_block where token is not found."""
        cs = TokenisedStream()
        cs.write(b'\x0b\x01\x00ghja')
        cs.seek(0)
        cs.skip_block(b'\x91', b'\x90')
        assert cs.tell() == 7


class ByteMatrixTest(unittest.TestCase):
    """Unit tests for bytematrix."""

    def test_empty(self):
        """Create empty matrix."""
        bm = ByteMatrix()
        assert bm.width == 0
        assert bm.height == 0
        assert bm.to_bytes() == b''

    def test_int(self):
        """Create matrix with all elements equal."""
        bm = ByteMatrix(2, 3, 1)
        assert bm.width == 3
        assert bm.height == 2
        assert bm.to_bytes() == b'\x01' * 6

    def test_list_of_list(self):
        """Create matrix from list of list."""
        bm = ByteMatrix(2, 3, [[1, 2, 3], [4, 5, 6]])
        assert bm.width == 3
        assert bm.height == 2
        assert bm.to_bytes() == bytes(bytearray(range(1, 7)))

    def test_bytes(self):
        """Create matrix from bytes."""
        bm = ByteMatrix(2, 3, b'123456')
        assert bm.width == 3
        assert bm.height == 2
        assert bm.to_bytes() == b'123456'

    def test_bytearray(self):
        """Create matrix from bytearray."""
        bm = ByteMatrix(2, 3, bytearray(b'123456'))
        assert bm.width == 3
        assert bm.height == 2
        assert bm.to_bytes() == b'123456'

    def test_bytearray_wide(self):
        """Create 1-row matrix from bytearray."""
        bm = ByteMatrix(1, 6, bytearray(b'123456'))
        assert bm.width == 6
        assert bm.height == 1
        assert bm.to_bytes() == b'123456'

    def test_bytearray_tall(self):
        """Create 1-column matrix from bytearray."""
        bm = ByteMatrix(6, 1, bytearray(b'123456'))
        assert bm.width == 1
        assert bm.height == 6
        assert bm.to_bytes() == b'123456'

    def test_list_of_bytes(self):
        """Create matrix from list of bytes."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        assert bm.width == 3
        assert bm.height == 2
        assert bm.to_bytes() == b'123456'

    def test_repr(self):
        """Debugging repr."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        assert isinstance(repr(bm), str)

    def test_getitem(self):
        """Test int and slice indexing."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        assert bm[0, 0] == ord(b'1')
        assert isinstance(bm[0:1, 0], ByteMatrix)
        assert bm[:, :] == bm
        assert bm[0:1, 0:2] == ByteMatrix(1, 2, [b'12'])
        assert bm[0, 0:2] == ByteMatrix(1, 2, [b'12'])
        assert bm[0:2, 0] == ByteMatrix(2, 1, [b'1', b'4'])
        assert bm[0:0, :] == ByteMatrix()

    def test_setitem(self):
        """Test int and slice assignment."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        bm[1, 2] = ord(b'Z')
        assert bm.to_bytes() == b'12345Z'
        bm[0:1, 0:2] = ByteMatrix(1, 2, [[1, 2]])
        assert bm.to_bytes() == b'\x01\x02345Z'
        bm[1, 0:2] = ByteMatrix(1, 2, [[4, 5]])
        assert bm.to_bytes() == b'\x01\x023\x04\x05Z'
        bm[0:2, 0] = ByteMatrix(2, 1, [[65], [66]])
        assert bm.to_bytes() == b'A\x023B\x05Z'

    def test_setitem_int(self):
        """Test slice assignment to same int."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        bm[0:1, 0:2] = 0
        assert bm.to_bytes() == b'\x00\x003456'
        bm[1, 0:2] = 1
        assert bm.to_bytes() == b'\x00\x003\x01\x016'
        bm[0:2, 0] = 2
        assert bm.to_bytes() == b'\x02\x003\x02\x016'

    def test_setitem_bad(self):
        """Test slice assignment to bad type."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        with self.assertRaises(TypeError):
            bm[0:1, 0:2] = 1.5
        with self.assertRaises(ValueError):
            bm[0:1, 0:2] = -1

    def test_eq(self):
        """Test equality."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        assert bm == bm
        assert bm == ByteMatrix(2, 3, [b'123', b'456'])
        assert not(bm == ByteMatrix(2, 3, [b'123', b'457']))

    def test_ne(self):
        """Test nonequality."""
        bm = ByteMatrix(2, 3, [b'123', b'456'])
        assert not (bm != bm)
        assert not (bm != ByteMatrix(2, 3, [b'123', b'456']))
        assert bm != ByteMatrix(2, 3, [b'123', b'457'])

    def test_elementwise(self):
        """Test elementwise operations."""
        bm = ByteMatrix(2, 3, 1)
        rhs = ByteMatrix(2, 3, b'\x00\x01\x02\x03\x04\x05')
        assert (bm | rhs).to_bytes() == b'\x01\x01\x03\x03\x05\x05'
        assert (bm & rhs).to_bytes() == b'\x00\x01\x00\x01\x00\x01'
        assert (bm ^ rhs).to_bytes() == b'\x01\x00\x03\x02\x05\x04'
        assert (bm >> rhs).to_bytes() == b'\x01\0\0\0\0\0'
        assert (bm << rhs).to_bytes() == b'\x01\x02\x04\x08\x10\x20'

    def test_elementwise_int(self):
        """Test elementwise operations with scalar."""
        bm = ByteMatrix(2, 3, b'\x00\x01\x02\x03\x04\x05')
        assert (bm | 1).to_bytes() == b'\x01\x01\x03\x03\x05\x05'
        assert (bm & 1).to_bytes() == b'\x00\x01\x00\x01\x00\x01'
        assert (bm ^ 1).to_bytes() == b'\x01\x00\x03\x02\x05\x04'
        assert (bm >> 1).to_bytes() == b'\x00\x00\x01\x01\x02\x02'
        assert (bm << 1).to_bytes() == b'\x00\x02\x04\x06\x08\x0a'
        # lsh out of bounds
        assert (bm << 8).to_bytes() == b'\0\0\0\0\0\0'

    def test_elementwise_inplace_int(self):
        """Test in-place elementwise operations with scalar."""
        bm = ByteMatrix(2, 3, 0)
        bm |= 1
        assert bm.to_bytes() == b'\x01'*6
        bm &= 255
        assert bm.to_bytes() == b'\x01'*6
        bm ^= 2
        assert bm.to_bytes() == b'\x03'*6
        bm >>= 1
        assert bm.to_bytes() == b'\x01'*6
        bm <<= 2
        assert bm.to_bytes() == b'\x04'*6

    def test_pack(self):
        """Test packed representation."""
        assert ByteMatrix(2, 8, 0).packed(8) == b'\0\0'
        assert ByteMatrix(1, 8, [[0, 1, 2, 4, 8, 16, 32, 64]]).packed(4) == bytearray(b'\x18\x00')
        # zero fill-out
        assert ByteMatrix(1, 7, 1).packed(8) == bytearray(b'\xfe')

    def test_unpack(self):
        """Test unpacking packed representation."""
        assert ByteMatrix.frompacked(b'\x18\x00', 1, 4) == ByteMatrix(1, 8, [[0, 1, 2, 0, 0, 0, 0, 0]])
        assert ByteMatrix.frompacked(b'\xfe', 1, 8) == ByteMatrix(1, 8, [[1, 1, 1, 1, 1, 1, 1, 0]])
        # empty
        assert ByteMatrix.frompacked(b'', 0, 8) == ByteMatrix()
        # insufficient length
        assert ByteMatrix.frompacked(b'\0', 2, 8) == ByteMatrix()


    def test_hex(self):
        """Test hex representation."""
        assert ByteMatrix(2, 8, 0).hex(8) == b'0000'
        assert ByteMatrix(1, 8, [[0, 1, 2, 4, 8, 16, 32, 64]]).hex(4) == b'1800'
        # zero fill-out
        assert ByteMatrix(1, 7, 1).hex(8) == b'fe'

    def test_fromhex(self):
        """Test unpacking packed representation."""
        assert ByteMatrix.fromhex(b'1800', 1, 4) == ByteMatrix(1, 8, [[0, 1, 2, 0, 0, 0, 0, 0]])
        assert ByteMatrix.fromhex(b'fe', 1, 8) == ByteMatrix(1, 8, [[1, 1, 1, 1, 1, 1, 1, 0]])
        # empty
        assert ByteMatrix.fromhex(b'', 0, 8) == ByteMatrix()

    def test_render(self):
        """Test rendering."""
        bm = ByteMatrix(2, 3, 0)
        bm[1, :] = 1
        assert bm.render(10, 42) == ByteMatrix(2, 3, [[10, 10, 10], [42, 42, 42]])

    def test_hextend(self):
        """Test horizontal extending."""
        bm = ByteMatrix(2, 3, 0)
        assert bm.hextend(2, 1) == ByteMatrix(2, 5, [[0, 0, 0, 1, 1], [0, 0, 0, 1, 1]])

    def test_vextend(self):
        """Test vertical extending."""
        bm = ByteMatrix(2, 3, 0)
        assert bm.vextend(2, 1) == ByteMatrix(4, 3, [[0, 0, 0], [0, 0, 0], [1, 1, 1], [1, 1, 1]])

    def test_hrepeat(self):
        """Test horizontal repeating."""
        bm = ByteMatrix(2, 3, b'123456')
        assert bm.hrepeat(2) == ByteMatrix(2, 6, b'112233445566')

    def test_vrepeat(self):
        """Test vertical reapeating."""
        bm = ByteMatrix(2, 3, b'123456')
        assert bm.vrepeat(2) == ByteMatrix(4, 3, b'123123456456')

    def test_htile(self):
        """Test horizontal tiling."""
        bm = ByteMatrix(2, 3, b'123456')
        assert bm.htile(2) == ByteMatrix(2, 6, b'123123456456')

    def test_vtile(self):
        """Test vertical tiling."""
        bm = ByteMatrix(2, 3, b'123456')
        assert bm.vtile(2) == ByteMatrix(4, 3, b'123456123456')

    def test_move(self):
        """Test moving submatrix."""
        bm = ByteMatrix(2, 3, b'123456')
        bm.move(1, 2, 0, 2, 0, 0)
        assert bm == ByteMatrix(2, 3, b'453\x00\x006')

    def test_to_bytes(self):
        """Test to_bytes."""
        assert ByteMatrix(2, 3, b'123456').to_bytes() == b'123456'

    def test_to_rows(self):
        """Test to_rows."""
        assert ByteMatrix(2, 3, b'123456').to_rows() == ((0x31, 0x32, 0x33), (0x34, 0x35, 0x36))

    def test_copy(self):
        """Test copying."""
        bm = ByteMatrix(2, 3, b'123456')
        copy = bm.copy()
        bm[:, :] = 0
        assert copy == ByteMatrix(2, 3, b'123456')

    def test_view(self):
        """Test viewing."""
        bm = ByteMatrix(2, 3, b'123456')
        copy = bm.view
        bm[:, :] = 0
        assert copy == ByteMatrix(2, 3, 0)

    def test_view_from_buffer(self):
        """Test view over buffer with pitch."""
        buf = bytearray(b'1230000045600000')
        bm = ByteMatrix.view_from_buffer(2, 3, 8, buf)
        bm[:, :] = 0
        assert buf == bytearray(b'\0\0\x0000000\0\0\x0000000')

    def test_hstack(self):
        """Test horizontal stacking."""
        bm = ByteMatrix(2, 3, b'123456')
        bm2 = ByteMatrix(2, 1, b'ab')
        assert hstack((bm, bm2)) == ByteMatrix(2, 4, b'123a456b')

    def test_vstack(self):
        """Test vertical stacking."""
        bm = ByteMatrix(2, 3, b'123456')
        bm2 = ByteMatrix(1, 3, b'abc')
        assert vstack((bm, bm2)) == ByteMatrix(3, 3, b'123456abc')


if __name__ == '__main__':
    unittest.main()
