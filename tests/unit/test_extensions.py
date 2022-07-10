"""
PC-BASIC tests.test_extension
unit tests for extensions

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os

from pcbasic import Session
from tests.unit.utils import TestCase, run_tests


class ExtensionTest(TestCase):
    """Unit tests for extensions."""

    tag = u'extensions'

    def test_extension(self):
        """Test extension functions."""

        class Extension(object):
            @staticmethod
            def add(x, y):
                return '%s plus %s equals %s' % (repr(x), repr(y), repr(x+y))

            @staticmethod
            def one():
                return 1

        with Session(extension=Extension) as s:
            s.execute('''
                10 a=5
                run
                b$ = _add(a, 1)
                c% = _one
            ''')
            assert s.get_variable("a!") == 5
            assert s.get_variable("c%") == 1
            assert s.get_variable("b$") == b'5.0 plus 1 equals 6.0'

    def test_extension_statement(self):
        """Test extension statements."""
        outfile = self.output_path('python-output.txt')

        class Extension(object):
            @staticmethod
            def output(*args):
                with open(outfile, 'ab') as g:
                    for arg in args:
                        if isinstance(arg, bytes):
                            g.write(arg)
                        else:
                            g.write(b'%d' % (arg,))
                        g.write(b' ')

        with Session(extension=Extension) as s:
            s.execute(b'''
                _OUTPUT "one", 2, 3!, 4#
                _output "!\x9c$"
            ''')
        with open(outfile, 'rb') as f:
            assert f.read() == b'one 2 3 4 !\x9c$ '

    def test_extended_session(self):
        """Test extensions accessing the session."""

        class ExtendedSession(Session):
            def __init__(self):
                Session.__init__(self, extension=self)

            def adda(self, x):
                return x + self.get_variable("a!")

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

    def test_extension_module_string(self):
        """Test using a module name as extension."""
        with Session(extension='random') as s:
            s.execute('''
                _seed(42)
                b = _uniform(a, 25.6)
            ''')
            self.assertAlmostEqual(s.evaluate('b'), 16.3693256378, places=10)

    def test_extension_module_not_found(self):
        """Test using a non-existant module name as extension."""
        with Session(extension='no-sirree') as s:
            s.execute('_test')
        assert self.get_text_stripped(s)[0] == b'Internal error\xff'

    def test_no_extension(self):
        """Test attempting to access extensions that aren't there."""
        with Session() as s:
            s.execute(b'''
                _NOPE "one", 2, 3!, 4#
            ''')
        assert self.get_text_stripped(s)[0] == b'Syntax error\xff'

    def test_no_statement(self):
        """Test attempting to access extensions that aren't there."""
        empty_ext = object()
        with Session(extension=empty_ext) as s:
            s.execute(b'''
                _NOPE "one", 2, 3!, 4#
            ''')
        assert self.get_text_stripped(s)[0] == b'Internal error\xff'

    def test_extension_function(self):
        """Test extension functions."""
        class Extension(object):
            @staticmethod
            def boolfunc():
                return True
            @staticmethod
            def unicodefunc():
                return u'test'
            @staticmethod
            def bytesfunc():
                return b'test'
            @staticmethod
            def intfunc():
                return 1
            @staticmethod
            def floatfunc():
                return 1

        with Session(extension=Extension) as s:
            assert s.evaluate('_BOOLFUNC') == -1
            assert s.evaluate('_INTFUNC') == 1.0
            assert s.evaluate('_FLOATFUNC') == 1.0
            assert s.evaluate('_UNICODEFUNC') == b'test'
            assert s.evaluate('_BYTESFUNC') == b'test'


    def test_extension_function_none(self):
        """Test extension functions with disallowed return type."""
        class Extension(object):
            @staticmethod
            def nonefunc():
                return None
        with Session(extension=Extension) as s:
            s.evaluate('_NONEFUNC')
        assert self.get_text_stripped(s)[0] == b'Type mismatch\xff'


if __name__ == '__main__':
    run_tests()
