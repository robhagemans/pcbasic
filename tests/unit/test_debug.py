"""
PC-BASIC tests.test_debug
Tests for debugging module

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pcbasic.basic import debug
from pcbasic.basic.base import error
from tests.unit.utils import TestCase, run_tests


class DebugTest(TestCase):
    """Debug module tests."""

    tag = u'debug'

    def test_get_platform_info(self):
        """Ensure get_platform_info outputs unicode."""
        info = debug.get_platform_info()
        assert isinstance(info, type(u''))

    def test_debug(self):
        """Exercise debug statements."""
        with debug.DebugSession() as s:
            s.execute('_dir')
            s.execute('_logprint "test"')
            s.execute('_logwrite "test"')
            s.execute('_showvariables')
            s.execute('_showscreen')
            s.execute('_showprogram')
            s.execute('_showplatform')
            s.execute('_python "print(\'--test--\')"')

    def test_trace_watch(self):
        """Exercise _trace and _watch."""
        with debug.DebugSession() as s:
            s.execute('_trace')
            # string
            s.execute('_watch "a$"')
            # single
            s.execute('_watch "a!"')
            # error
            s.execute('_watch "log(-1)"')
            s.execute('10 a=1:? a')
            s.execute('20 a$="test"')
            s.execute('run')
            s.execute('_trace 0')
            s.execute('run')

    def test_crash(self):
        """Test _crash."""
        with self.assertRaises(debug.DebugException):
            with debug.DebugSession() as s:
                s.execute('_crash')

    def test_debugexception_repr(self):
        """Test DebugException.__repr__."""
        assert isinstance(repr(debug.DebugException()), str)

    def test_restart(self):
        """Test _restart."""
        # Restart exception is not absorbed
        with self.assertRaises(error.Reset):
            with debug.DebugSession() as s:
                s.execute('_restart')

    def test_exit(self):
        """Test _exit."""
        with debug.DebugSession() as s:
            # Exit exception would be absorbed by the Session context
            with self.assertRaises(error.Exit):
                s.execute('_exit')

    def test_exception(self):
        """Test exception in debug statement."""
        with debug.DebugSession() as s:
            # no exception raised
            s.execute('_python "blah"')


if __name__ == '__main__':
    run_tests()
