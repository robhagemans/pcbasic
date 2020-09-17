"""
PC-BASIC test.session
unit tests for session API

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os

from pcbasic import Session, run

HERE = os.path.dirname(os.path.abspath(__file__))


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

    def test_session_convert(self):
        """Test Session.convert(variable)."""
        unicode = type(u'')
        with Session() as s:
            # omit to_type
            assert s.convert(1, None) is 1
            # from_type == to_type
            assert s.convert(1, int) is 1
            # cp437 string to unicode
            assert s.convert(b'\x00\x01\x9C\x86\xe0', unicode) == u'\x00\u263a\xa3\xe5\u03b1'
            # unicode to cp437
            assert s.convert(u'\x00\u263a\xa3\xe5\u03b1', bytes) == b'\x00\x01\x9C\x86\xe0'
            # int to bool
            assert s.convert(0, bool) == False
            assert s.convert(-1, bool) == True
            assert s.convert(1, bool) == True
            # float to bool
            assert s.convert(0., bool) == False
            assert s.convert(-1., bool) == True
            # bool to int
            assert s.convert(True, int) is -1
            assert s.convert(False, int) is 0
            # bool to float
            assert s.convert(True, float) == -1.
            assert s.convert(False, float) == 0.
            assert isinstance(s.convert(True, float), float)
            # int to float
            assert s.convert(1, float) == 1.0
            # float to int (floor)
            assert s.convert(1.1, int) == 1
            assert s.convert(-0.1, int) == -1
            # error
            with self.assertRaises(ValueError):
                s.convert(b'1', int)

    def test_session_getset_variable(self):
        """Test Session.set_variable and Session.get_variable."""
        with Session() as s:
            s.set_variable(b'A%', 1)
            assert s.get_variable(b'A%') is 1
            # bytes or unicode argument
            s.set_variable(u'A%', 2)
            assert s.get_variable(b'A%') is 2
            s.set_variable(u'A%', 3)
            assert s.get_variable(u'A%') is 3
            s.set_variable(u'A%', 3)
            assert s.get_variable(b'A%') is 3
            # undefined variable
            assert s.get_variable('A!') == 0
            # sigil must be explicit
            with self.assertRaises(ValueError):
                s.set_variable('B', 0.)
            # sigil must be explicit
            with self.assertRaises(ValueError):
                s.get_variable('B', 0.)
            # boolean
            s.set_variable(b'A%', True)
            assert s.get_variable(b'A%') is -1
            # single
            s.set_variable(b'A!', 1.1)
            self.assertAlmostEqual(s.get_variable(b'A!'), 1.1, places=6)
            # double
            s.set_variable(b'A#', 0.1234567890123)
            self.assertAlmostEqual(s.get_variable(b'A#'), 0.1234567890123, places=14)
            # bytes string
            s.set_variable(b'A$', b'1')
            assert s.get_variable(b'A$') == b'1'
            # unicode string value (sterling sign)
            s.set_variable(b'A$', u'\xc2\xa3')
            # bytes output, in cp437
            assert s.get_variable(b'A$') == b'\x9C'
            # unset array
            assert s.get_variable('A%()') == []

    def test_session_evaluate(self):
        """Test Session.set_variable and Session.get_variable."""
        with Session() as s:
            s.set_variable(b'A!', 1)
            assert s.evaluate(b'A') == 1
            assert s.evaluate(u'A') == 1
            # syntax error
            assert s.evaluate(b'LOG+1') is None

    def test_resume(self):
        """Test resume."""
        loc = os.path.join(HERE, 'output', 'session')
        run("--exec='A=1:open\"z:output.txt\" for output as 1:SYSTEM'", '--mount=z:%s' % loc, '-b')
        run('--resume', '--keys=?#1,A:close:system\r', '-b')
        with open(os.path.join(loc, 'OUTPUT.TXT'), 'rb') as outfile:
            output = outfile.read()
        assert output == b' 1 \r\n\x1a'

    def test_session_bind_file(self):
        """test Session.bind_file."""
        # open file object
        loc = os.path.join(HERE, 'output', 'session')
        with open(os.path.join(loc, 'testfile'), 'wb') as f:
            with Session() as s:
                name = s.bind_file(f)
                # can use name as string
                assert len(str(name)) <= 12
                # write to file
                s.execute('open "{0}" for output as 1: print#1, "x"'.format(name))
        with open(os.path.join(loc, 'testfile'), 'rb') as f:
            output = f.read()
        assert output == b'x\r\n\x1a'
        # existing file by name
        with Session() as s:
            name = s.bind_file(os.path.join(loc, 'testfile'))
            # write to file
            s.execute('open "{0}" for input as 1'.format(name))
            s.execute('input#1, a$')
            assert s.get_variable('A$') == b'x'
        # create file by name
        native_name = os.path.join(loc, u'new-test-file')
        try:
            os.remove(native_name)
        except EnvironmentError:
            pass
        with Session() as s:
            name = s.bind_file(native_name, create=True)
            s.execute('open "{0}" for output as 1: print#1, "test";: close'.format(name))
        with open(native_name, 'rb') as f:
            output = f.read()
        assert output == b'test\x1a'
        # existing file by BASIC name
        with Session(devices={b'Z': loc}) as s:
            name = s.bind_file(b'Z:TESTFILE')
            # write to file
            s.execute('open "{0}" for input as 1'.format(name))
            s.execute('input#1, a$')
            assert s.get_variable('A$') == b'x'
        # create file by name , provide BASIC name (bytes)
        native_name = os.path.join(loc.encode('ascii'), b'new-test-file')
        try:
            os.remove(native_name)
        except EnvironmentError:
            pass
        with Session() as s:
            name = s.bind_file(native_name, name=b'A B C', create=True)
            s.execute(b'open "@:A B C" for output as 1: print#1, "test";: close')
        with open(native_name, 'rb') as f:
            output = f.read()
        assert output == b'test\x1a'
        # create file by name , provide BASIC name (unicode)
        native_name = os.path.join(loc.encode('ascii'), b'new-test-file')
        try:
            os.remove(native_name)
        except EnvironmentError:
            pass
        with Session() as s:
            name = s.bind_file(native_name, name=u'A B C', create=True)
            s.execute(u'open "@:A B C" for output as 1: print#1, "test";: close')
        with open(native_name, 'rb') as f:
            output = f.read()
        assert output == b'test\x1a'

    def test_session_greeting(self):
        """Test welcome screen."""
        with Session() as s:
            s.greet()
            output = [_row.strip() for _row in s.get_text()]
        assert output[0].startswith(b'PC-BASIC ')
        assert output[1].startswith(b'(C) Copyright 2013--')
        assert output[1].endswith(b' Rob Hagemans.')
        assert output[2] == b'60300 Bytes free'
        assert output[-1] == (
            b'1LIST   2RUN\x1b   3LOAD"  4SAVE"  5CONT\x1b'
            b'  6,"LPT1 7TRON\x1b  8TROFF\x1b 9KEY    0SCREEN'
        )

    def test_session_press_keys(self):
        """Test Session.press_keys."""
        with Session() as s:
            # eascii: up, esc, SYSTEM, enter
            s.press_keys(u'\0\x48\x1bSYSTEM\r')
            s.interact()
            # note that SYSTEM raises an exception absorbed by the context manager
            # no nothing further in this block will be executed
        output = [_row.strip() for _row in s.get_text()]
        # OK prompt should have been overwritten
        assert output[0] == b'SYSTEM'

    def test_session_execute(self):
        """Test Session.execute."""
        with Session() as s:
            # statement
            s.execute(b'?LOG(1)')
            # break
            s.execute(b'STOP')
            # error
            s.execute(b'A')
        output = [_row.strip() for _row in s.get_text()]
        # \xff checked against DOSbox/GW-BASIC
        assert output[:3] == [b'0', b'Break\xff', b'Syntax error\xff']
        assert output[3:] == [b''] * 22

    def test_extension(self):
        """Test extension functions."""

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
            assert s.get_variable("a!") == 5
            assert s.get_variable("b$") == b'5.0 plus 1 equals 6.0'

    def test_extension_statement(self):
        """Test extension statements."""
        outfile = os.path.join(HERE, 'output', 'session', 'python-output.txt')
        try:
            os.remove(outfile)
        except EnvironmentError:
            pass

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
            s.execute('''
                _OUTPUT "one", 2, 3!, 4#
                _output "!\x9c$"
            ''')
        with open(outfile, 'rb') as f:
            #print repr(f.read())
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


if __name__ == '__main__':
    unittest.main()
