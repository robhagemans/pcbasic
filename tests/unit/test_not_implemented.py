"""
PC-BASIC tests.test_not_implemented
Exercise not-implemented and part-implemented statements and functions

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pcbasic import Session

from tests.unit.utils import TestCase, run_tests


class NotImplementedTest(TestCase):
    """Exercise not-implemented statements and functions."""

    tag = u'not_implemented'

    async def test_call(self):
        """Exercise CALL statement."""
        with Session() as s:
            # well-formed calls
            await s.execute('call a%(b)')
            await s.execute('call a(b!, c$)')
            await s.execute('call a(b!, c$, d(0))')
            await s.execute('call a#')
            await s.execute('call a!')
            await s.execute('call a%')
        assert self.get_text_stripped(s) == [b''] * 25

    async def test_call_wrong(self):
        """Exercise CALL statement with badly-formed arguments."""
        with Session() as s:
            # type mismatch
            await s.execute('call a$(b)')
            # syntax error
            await s.execute('call a(b!, c$())')
            # syntax error
            await s.execute('call')
            # syntax error
            await s.execute('call 0')
            # syntax error
            await s.execute('call "a"')
        assert self.get_text_stripped(s)[:5] == [b'Type mismatch\xff'] + [b'Syntax error\xff'] * 4

    async def test_calls(self):
        """Exercise CALLS statement."""
        with Session() as s:
            # well-formed calls
            await s.execute('calls a%(b)')
            await s.execute('calls a(b!, c$)')
            await s.execute('calls a(b!, c$, d(0))')
        assert self.get_text_stripped(s) == [b''] * 25

    async def test_calls_wrong(self):
        """Exercise CALLS statement with badly-formed arguments."""
        with Session() as s:
            # type mismatch
            await s.execute('calls a$(b)')
            # syntax error
            await s.execute('calls a(b!, c$())')
            # syntax error
            await s.execute('calls')
            # syntax error
            await s.execute('calls 0')
            # syntax error
            await s.execute('calls "a"')
        assert self.get_text_stripped(s)[:5] == [b'Type mismatch\xff'] + [b'Syntax error\xff'] * 4


if __name__ == '__main__':
    run_tests()
