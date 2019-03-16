"""
PC-BASIC test.session
unit tests for session API

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest

from pcbasic import Session


class SessionTest(unittest.TestCase):
    """Unit tests for Session."""

    def test_session(self):
        """Test basic Session API."""
        with Session() as s:
            s.execute('a=1')
            assert s.evaluate('a+2') == 3.
            assert s.evaluate('"abc"+"d"') == b'abcd'
            assert s.evaluate('string$(a+2, "@")') == b'@@@'
            # string variable
            s.set_variable('B$', 'abcd')
            assert s.get_variable('B$') == b'abcd'
            assert s.evaluate('LEN(B$)') is 4
            # unset variable
            assert s.evaluate('C!') == 0.
            assert s.get_variable('D%') is 0
            # unset array
            s.set_variable('A%()', [[0,0,5], [0,0,6]])
            assert s.get_variable('A%()') == [
                [0, 0, 5, 0, 0, 0, 0, 0, 0, 0], [0, 0, 6, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            ]
            assert s.evaluate('A%(0,2)') == 5
            assert s.evaluate('A%(1,2)') == 6
            assert s.evaluate('A%(1,7)') == 0
            assert s.evaluate('FRE(0)') == 60020.
            assert s.evaluate('CSRLIN') == 1
            s.execute('print b$')
            assert s.evaluate('CSRLIN') == 2

    def test_extension(self):
        """Text extensions."""

        class Extension(object):
            @staticmethod
            def add(x, y):
                return '%s plus %s equals %s' % (repr(x), repr(y), repr(x+y))

        with Session(extension=Extension) as s:
            s.execute('''
                10 a=5
                run
                b$ = _add(a, 1)
            ''')
            assert s.get_variable("a") == 5
            assert s.get_variable("b$") == b'5.0 plus 1 equals 6.0'

    def test_extended_session(self):
        """Test extensions accessing the session."""

        class ExtendedSession(Session):
            def __init__(self):
                Session.__init__(self, extension=self)

            def adda(self, x):
                return x + self.get_variable("a")

        with ExtendedSession() as s:
            s.execute('a=4')
            s.execute('b=_adda(1)')
            assert s.evaluate('b') == 5.

    def test_extension_module(self):
        """Test using a module as extension."""
        import random
        with Session(extension=random) as s:
            s.execute('''
                _seed(42)
                b = _uniform(a, 25.6)
            ''')
            self.assertAlmostEqual(s.evaluate('b'), 16.3693256378, places=10)


if __name__ == '__main__':
    unittest.main()
