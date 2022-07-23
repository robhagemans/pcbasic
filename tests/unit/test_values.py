"""
PC-BASIC test.session
unit tests for values.values

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pcbasic import Session
from pcbasic.basic.values import values
from pcbasic.basic.values.numbers import Integer, Single, Double
from pcbasic.basic.values.strings import String
from pcbasic.basic.base import error
from tests.unit.utils import TestCase, run_tests


class ValuesTest(TestCase):
    """Unit tests for values.values module."""

    tag = u'values'

    def test_pass_number(self):
        """Test pass_number()."""
        vm = values.Values(None, False)
        i = vm.new_integer()
        s = vm.new_string()
        assert values.pass_number(i) == i
        with self.assertRaises(error.BASICError):
            values.pass_number(s)
        with self.assertRaises(TypeError):
            values.pass_number(None)

    def test_pass_string(self):
        """Test pass_string()."""
        vm = values.Values(None, False)
        i = vm.new_integer()
        s = vm.new_string()
        assert values.pass_string(s) == s
        with self.assertRaises(error.BASICError):
            values.pass_string(i)
        with self.assertRaises(TypeError):
            values.pass_string(None)

    def test_to_type_errors(self):
        """Test to_type() error cases."""
        vm = values.Values(None, False)
        s = vm.new_string()
        with self.assertRaises(TypeError):
            values.to_repr(None, True, True)
        with self.assertRaises(error.BASICError):
            values.to_repr(s, True, True)

    def test_to_repr_errors(self):
        """Test to_repr() error cases."""
        vm = values.Values(None, False)
        i = vm.new_integer()
        with self.assertRaises(ValueError):
            values.to_type("&", i)

    def test_match_types_errors(self):
        """Test match_types() error cases."""
        vm = values.Values(None, False)
        i = vm.new_integer()
        s = vm.new_string()
        with self.assertRaises(error.BASICError):
            values.match_types(s, i)
        with self.assertRaises(TypeError):
            values.match_types(s, None)
        with self.assertRaises(TypeError):
            values.match_types(None, None)

    def test_call_float_function_errors(self):
        """Test call_float_function error cases."""
        vm = values.Values(None, False)
        vm.set_handler(values.FloatErrorHandler(None))
        def itimes(x):
            return complex(0, x)
        with self.assertRaises(error.BASICError):
            values._call_float_function(itimes, vm.new_single().from_int(1))

    def test_float_error_handler_errors(self):
        """Test FloatErrorHandler error cases."""
        vm = values.Values(None, False)
        vm.set_handler(values.FloatErrorHandler(None))
        # use an exception class not supported by FloatErrorHandler
        def typerr(x):
            raise TypeError()
        with self.assertRaises(TypeError):
            values._call_float_function(typerr, vm.new_single().from_int(1))

    def test_float_error_handler_soft(self):
        """Test FloatErrorHandler."""
        class MockConsole(object):
            def write_line(self, s):
                pass
        vm = values.Values(None, double_math=False)
        vm.set_handler(values.FloatErrorHandler(MockConsole()))
        # overflowerror *is* handled
        def ovflerr(x):
            e = OverflowError()
            raise e
        assert isinstance(
            values._call_float_function(ovflerr, vm.new_double().from_int(1)),
            Single
        )

    def test_float_error_handler_soft_double(self):
        """Test FloatErrorHandler."""
        class MockConsole(object):
            def write_line(self, s):
                pass
        vm = values.Values(None, double_math=True)
        vm.set_handler(values.FloatErrorHandler(MockConsole()))
        # overflowerror *is* handled
        def ovflerr(x):
            e = OverflowError()
            raise e
        one = vm.new_double().from_int(1)
        result = values._call_float_function(ovflerr, one)
        assert isinstance(result, Double)

    def test_from_token_errors(self):
        """Test from_token error cases."""
        vm = values.Values(None, True)
        with self.assertRaises(ValueError):
            # no token
            vm.from_token(None)
        with self.assertRaises(ValueError):
            # not a number token
            vm.from_token(b'\0\0')

    def test_pow_double(self):
        """Test a^b with double-precision values."""
        vm = values.Values(None, double_math=True)
        i = vm.new_integer().from_int(1)
        s = vm.new_single().from_int(1)
        d = vm.new_double().from_int(1)
        assert isinstance(values.pow(i, d), Double)
        assert isinstance(values.pow(d, i), Double)
        assert isinstance(values.pow(s, d), Double)
        assert isinstance(values.pow(d, s), Double)
        assert isinstance(values.pow(s, s), Single)

    def test_pow_single(self):
        """Test a^b with double-precision values but -d not set."""
        vm = values.Values(None, double_math=False)
        i = vm.new_integer().from_int(1)
        s = vm.new_single().from_int(1)
        d = vm.new_double().from_int(1)
        assert isinstance(values.pow(i, d), Single)
        assert isinstance(values.pow(d, i), Single)
        assert isinstance(values.pow(s, d), Single)
        assert isinstance(values.pow(d, s), Single)
        assert isinstance(values.pow(s, s), Single)

    def test_repr(self):
        """Test representation."""
        vm = values.Values(None, double_math=False)
        i = vm.new_integer().from_int(1)
        s = vm.new_single().from_int(1)
        d = vm.new_double().from_int(1)
        st = vm.new_string()
        assert isinstance(repr(i), type(''))
        assert isinstance(repr(s), type(''))
        assert isinstance(repr(d), type(''))
        assert isinstance(repr(st), type(''))

    def test_from_token_error(self):
        """Test Integer.from_token()."""
        vm = values.Values(None, double_math=False)
        with self.assertRaises(ValueError):
            vm.new_integer().from_token(b'abc')
        with self.assertRaises(ValueError):
            vm.new_single().from_token(b'abc')
        with self.assertRaises(ValueError):
            vm.new_double().from_token(b'abc')

    def test_integer_ineg(self):
        """Test in-place negate operations on integers."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        one = vm.new_integer().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        assert vm.new_integer().from_int(1).ineg().eq(neg_one)
        assert vm.new_integer().from_int(0).ineg().eq(zero)
        assert vm.new_integer().from_int(-1).ineg().eq(one)
        # overflow -(-32768)
        with self.assertRaises(error.BASICError):
            vm.new_integer().from_int(-32768).ineg()

    def test_integer_iabs(self):
        """Test in-place absolute operations on integers."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        one = vm.new_integer().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        assert one.iabs().eq(vm.new_integer().from_int(1))
        assert zero.iabs().eq(vm.new_integer().from_int(0))
        assert neg_one.iabs().eq(vm.new_integer().from_int(1))

    def test_integer_isub(self):
        """Test in-place subtract operations on integers."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        one = vm.new_integer().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        assert one.isub(one).eq(zero)
        assert neg_one.isub(neg_one).eq(zero)
        assert vm.new_integer().from_int(0).isub(vm.new_integer().from_int(-1)).eq(vm.new_integer().from_int(1))
        assert vm.new_integer().from_int(0).isub(vm.new_integer().from_int(1)).eq(vm.new_integer().from_int(-1))
        assert vm.new_integer().from_int(1).isub(vm.new_integer().from_int(-1)).to_int() == 2

    def test_integer_comparisons(self):
        """Test comparison operations on integers."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        one = vm.new_integer().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        twobyte = vm.new_integer().from_int(256)
        assert one.gt(zero)
        assert zero.gt(neg_one)
        assert not neg_one.gt(zero)
        assert twobyte.gt(one)
        assert not one.gt(twobyte)
        assert one.eq(vm.new_integer().from_int(1))

    def test_integer_float_comparisons(self):
        """Test comparison operations between integers and floats."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        one = vm.new_integer().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        d_zero = vm.new_double().from_int(0)
        s_zero = vm.new_single().from_int(0)
        assert zero.eq(d_zero)
        assert zero.eq(s_zero)
        assert one.gt(d_zero)
        assert one.gt(s_zero)

    def test_float_idiv(self):
        """Test in-place divide operations on floats."""
        vm = values.Values(None, double_math=False)
        four = vm.new_single().from_int(4)
        two = vm.new_single().from_int(2)
        zero = vm.new_single().from_int(0)
        assert four.idiv(two).eq(two)
        assert zero.idiv(two).eq(vm.new_single().from_int(0))

    def test_float_ipow_int(self):
        """Test in-place power operation on floats."""
        vm = values.Values(None, double_math=False)
        four = vm.new_single().from_int(4)
        zero = vm.new_single().from_int(0)
        assert four.ipow_int(zero).to_value() == 1.

    def test_float_comparisons(self):
        """Test comparison operations between floats and other types."""
        vm = values.Values(None, double_math=False)
        zero = vm.new_integer().from_int(0)
        s_one = vm.new_single().from_int(1)
        neg_one = vm.new_integer().from_int(-1)
        d_zero = vm.new_double().from_int(0)
        s_zero = vm.new_single().from_int(0)
        assert s_zero.eq(zero)
        assert s_zero.eq(s_zero)
        assert s_zero.eq(d_zero)
        assert s_one.gt(zero)
        assert s_one.gt(s_zero)
        assert s_one.gt(d_zero)

    # string representations of floats

    def test_from_decimal_repr(self):
        """Test converting bytes string in decimal representation to float."""
        assert values.numbers.str_to_decimal(b'1.0e2a', allow_nonnum=True) == (False, 10, 1)
        with self.assertRaises(ValueError):
            values.numbers.str_to_decimal(b'1.0e2a', allow_nonnum=False)
        assert values.numbers.str_to_decimal(b'x.0e2', allow_nonnum=True) == (False, 0, 0)
        with self.assertRaises(ValueError):
            values.numbers.str_to_decimal(b'x.0e2', allow_nonnum=False)

    def test_to_decimal_repr(self):
        """Test converting float to bytes string in decimal representation."""
        vm = values.Values(None, double_math=False)
        one = vm.new_single().from_int(1)
        assert one.to_decimal(digits=0) == (0, 1)
        assert vm.new_single().from_value(1e-5).to_decimal(7) == (1000000, -11)
        assert vm.new_single().from_value(1e38).to_decimal(7) == (1000000, 32)

    def test_to_fixed_repr(self):
        """Test converting float to bytes string in fixed-point representation."""
        vm = values.Values(None, double_math=False)
        assert vm.new_single().from_value(0).to_str_fixed(3, False, False) == b'000'


if __name__ == '__main__':
    run_tests()
