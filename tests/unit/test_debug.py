"""
PC-BASIC tests.test_debug
Tests for debugging module

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pcbasic import debug
from pcbasic.basic.base import error
from tests.unit.utils import TestCase, run_tests


class DebugTest(TestCase):
    """Debug module tests."""

    tag = u'debug'

    def test_get_platform_info(self):
        """Ensure get_platform_info outputs unicode."""
        info = debug.get_platform_info()
        assert isinstance(info, type(u''))

    async def test_debug(self):
        """Exercise debug statements."""
        with debug.DebugSession() as s:
            await s.execute('_dir')
            await s.execute('_logprint "test"')
            await s.execute('_logwrite "test"')
            await s.execute('_showvariables')
            await s.execute('_showscreen')
            await s.execute('_showprogram')
            await s.execute('_showplatform')
            await s.execute('_python "print(\'--test--\')"')

    async def test_trace_watch(self):
        """Exercise _trace and _watch."""
        with debug.DebugSession() as s:
            await s.execute('_trace')
            # string
            await s.execute('_watch "a$"')
            # single
            await s.execute('_watch "a!"')
            # error
            await s.execute('_watch "log(-1)"')
            await s.execute('10 a=1:? a')
            await s.execute('20 a$="test"')
            await s.execute('run')
            await s.execute('_trace 0')
            await s.execute('run')

    async def test_crash(self):
        """Test _crash."""
        with self.assertRaises(debug.DebugException):
            with debug.DebugSession() as s:
                await s.execute('_crash')

    async def test_debugexception_repr(self):
        """Test DebugException.__repr__."""
        assert isinstance(repr(debug.DebugException()), str)

    async def test_restart(self):
        """Test _restart."""
        # Restart exception is not absorbed
        with self.assertRaises(error.Reset):
            with debug.DebugSession() as s:
                await s.execute('_restart')

    async def test_exit(self):
        """Test _exit."""
        with debug.DebugSession() as s:
            # Exit exception would be absorbed by the Session context
            with self.assertRaises(error.Exit):
                await s.execute('_exit')

    async def test_exception(self):
        """Test exception in debug statement."""
        with debug.DebugSession() as s:
            # no exception raised
            await s.execute('_python "blah"')


if __name__ == '__main__':
    run_tests()
