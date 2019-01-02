"""
PC-BASIC - bytematrix.py
2D matrices of bytes

(c) 2018--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import operator
from binascii import hexlify, unhexlify

from ...compat import zip, int2byte


class ByteMatrix(object):
    """2D byte matrix."""

    def __init__(self, height=0, width=0, data=0):
        """Create a new matrix."""
        self._height = height
        self._width = width
        if not width and not height:
            self._data = None
        elif isinstance(data, int):
            self._rows = [bytearray([data])*width for _ in range(self._height)]
        else:
            # assume iterable, TypeError if not
            data = list(data)
            if len(data) == 1:
                self._rows = [bytearray(data)*width for _ in range(self._height)]
            elif len(data) == height:
                assert len(data[0]) == width
                self._rows = [bytearray(_row) for _row in data]
            else:
                assert len(data) == height * width
                self._rows = [
                    bytearray(data[_offs : _offs+width])
                    for _offs in range(0, len(data), width)
                ]

    def __repr__(self):
        """Debugging representation."""
        hexreps = [''.join('\\x{:02x}'.format(_c) for _c in _row) for _row in self._rows]
        return "ByteMatrix({0._height}, {0._width}, [\n    '{1}' ])".format(
            self, "',\n    '".join(hexreps)
        )

    def __getitem__(self, index):
        """Extract items by [y, x] indexing or slicing or 1D index."""
        y, x = index
        if isinstance(y, slice):
            if isinstance(x, slice):
                return self._create_from_rows([_row[x] for _row in self._rows[y]])
            else:
                return self._create_from_rows([bytearray([_row[x]]) for _row in self._rows[y]])
        if isinstance(x, slice):
            return self._create_from_rows([self._rows[y][x]])
        return self._rows[y][x]

    def __setitem__(self, index, value):
        """Set items by [y, x] indexing or slicing."""
        y, x = index
        if isinstance(value, int):
            if isinstance(x, slice):
                if isinstance(y, slice):
                    for row in self._rows[y]:
                        row[x] = [value for _ in row[x]]
                else:
                    self._rows[y][x] = [value for _ in self._rows[y][x]]
            else:
                if isinstance(y, slice):
                    for row in self._rows[y]:
                        row[x] = value
                else:
                    self._rows[y][x] = value
        else:
            if isinstance(value, ByteMatrix):
                value = value._rows
            if isinstance(y, slice):
                for _dst, _src in zip(self._rows[y], value):
                    # if x is a slice, this will copy too -> e.g. array[:] = another_array
                    _dst[x] = _src
            elif isinstance(x, slice):
                assert len(value) == 1
                self._rows[y][x] = value[0]
            else:
                raise TypeError(
                    'Can only assign ByteMatrix, list of bytes-like or int, not %s.' % type(value)
                )


    def _elementwise_list(self, rhs, oper):
        """Helper for elementwise operations."""
        if isinstance(rhs, int):
            return [
                bytearray(oper(_lbyte, rhs) for _lbyte in _lrow)
                for _lrow in self._rows
            ]
        else:
            assert self._height == rhs._height
            assert self._width == rhs._width
            return [
                bytearray(oper(_lbyte, _rbyte) for _lbyte, _rbyte in zip(_lrow, _rrow))
                for _lrow, _rrow in zip(self._rows, rhs._rows)
            ]

    def elementwise(self, rhs, oper):
        """Element-wise operation with another matrix or a scalar."""
        return self._create_from_rows(self._elementwise_list(rhs, oper))

    def __or__(self, rhs):
        """Bitwise or."""
        return self.elementwise(rhs, operator.__or__)

    def __and__(self, rhs):
        """Bitwise and."""
        return self.elementwise(rhs, operator.__and__)

    def __xor__(self, rhs):
        """Bitwise exclusive or."""
        return self.elementwise(rhs, operator.__xor__)

    def __rshift__(self, rhs):
        """Right-shift."""
        return self.elementwise(rhs, operator.__rshift__)

    def __lshift__(self, rhs):
        """Byte-masked left-shift."""
        return self.elementwise(rhs, lambda _l, _r: (_l << _r) & 0xff)

    def elementwise_inplace(self, rhs, oper):
        """In-place element-wise operation with another matrix or a scalar."""
        self._rows = self._elementwise_list(rhs, oper)
        return self

    def __ior__(self, rhs):
        """In-place bitwise or."""
        return self.elementwise_inplace(rhs, operator.__ior__)

    def __iand__(self, rhs):
        """In-place bitwise and."""
        return self.elementwise_inplace(rhs, operator.__iand__)

    def __ixor__(self, rhs):
        """In-place bitwise exclusive or."""
        return self.elementwise_inplace(rhs, operator.__ixor__)

    def __irshift__(self, rhs):
        """In-place right-shift."""
        return self.elementwise_inplace(rhs, operator.__irshift__)

    def __ilshift__(self, rhs):
        """In-place left-shift."""
        return self.elementwise_inplace(rhs, lambda _l, _r: (_l << _r) & 0xff)


    @property
    def width(self):
        """Number of columns."""
        return self._width

    @property
    def height(self):
        """Number of rows."""
        return self._height

    @classmethod
    def _create_from_rows(cls, data):
        """Construct byte matrix from rows of bytearrays."""
        new = cls()
        new._height = len(data)
        new._width = len(data[0])
        new._rows = data
        assert len(set(len(_r) for _r in data)) == 1, 'ByteMatrix rows must all be same length'
        return new

    @classmethod
    def frompacked(cls, packed, height, items_per_byte):
        """Unpack from packed-bits representation."""
        width = len(packed) // height
        return cls._create_from_rows([
            unpack_bytes(packed[_offs : _offs+width], items_per_byte)
            for _offs in range(0, len(packed), width)
        ])

    def packed(self, items_per_byte):
        """Pack into packed-bits representation, byte aligned on rows."""
        return bytearray().join(
            pack_bytes(_r, items_per_byte) for _r in self._rows
        )

    @classmethod
    def fromhex(cls, hex, height, items_per_byte):
        """Unpack from hex representation."""
        return cls.frompacked(unhexlify(hex), height, items_per_byte)

    def hex(self, items_per_byte):
        """Pack to hex representation."""
        return hexlify(self.packed(items_per_byte))

    def render(self, back, fore):
        """Set attributes on bit matrix."""
        return self._create_from_rows([
            _row.replace(b'\0', int2byte(back)).replace(b'\x01', int2byte(fore))
            for _row in self._rows
        ])

    def hextend(self, by_width, fill=0):
        """Extend width by given number of bytes."""
        new_row = bytearray([fill])*by_width
        return self._create_from_rows([_row + new_row for _row in self._rows])

    def vextend(self, by_height, fill=0):
        """Extend height by given number of bytes."""
        return self._create_from_rows(
            self._rows
            + [bytearray([fill])*self._width for _ in range(by_height)]
        )

    def hrepeat(self, times=1):
        """Multiply width by byte repetition (00 11 22 ...) ."""
        return self._create_from_rows([
            bytearray(_byte for _byte in _row for _ in range(times))
            for _row in self._rows
        ])


##############################################################################
# concatenation

def hstack(matrices):
    """Horizontally concatenate matrices."""
    matrices = list(matrices)
    return ByteMatrix._create_from_rows([
        bytearray().join(_rows)
        for _rows in zip(*(_mat._rows for _mat in matrices))
    ])

def vstack(matrices):
    """Vertically concatenate matrices."""
    return ByteMatrix._create_from_rows([
        _row for _mat in matrices for _row in _mat._rows
    ])


##############################################################################
# bytearray functions

def unpack_bytes(packed, items_per_byte):
    """Unpack from packed-bits representation."""
    bpp = 8 // items_per_byte
    mask = (1 << bpp) - 1
    shifts = [8 - bpp - _sh for _sh in range(0, 8, bpp)]
    return bytearray(
        (_byte >> _shift) & mask
        for _byte in packed
        for _shift in shifts
    )

def pack_bytes(unpacked, items_per_byte):
    """Pack into packed-bits representation."""
    bpp = 8 // items_per_byte
    mask = (1 << bpp) - 1
    shifts = [8 - bpp - _sh for _sh in range(0, 8, bpp)]
    # ceildiv(a,b) == -(floowrdiv(-a,b))
    packed_width = -(-len(unpacked) // items_per_byte)
    prepacked = [(_byte & mask) << _shift for _byte, _shift in zip(unpacked, shifts*packed_width)]
    return bytearray([
        sum(prepacked[_offs : _offs+items_per_byte])
        for _offs in range(0, len(prepacked), items_per_byte)
    ])
