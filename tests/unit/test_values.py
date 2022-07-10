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

    def test_integer_from_token_error(self):
        """Test Integer.from_token()."""
        vm = values.Values(None, double_math=False)
        with self.assertRaises(ValueError):
            vm.new_integer().from_token(b'abc')



if __name__ == '__main__':
    run_tests()
