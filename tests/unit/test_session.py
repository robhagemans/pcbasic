"""
PC-BASIC test.session
unit tests for session API

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io

from pcbasic import Session
from tests.unit.utils import TestCase, run_tests


def istypeval(val, refval):
    """Check agreement in both type and value."""
    return isinstance(val, type(refval)) and val == refval


class SessionTest(TestCase):
    """Unit tests for Session."""

    tag = u'session'

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
            assert istypeval(s.evaluate('LEN(B$)'), 4)
            # unset variable
            assert s.evaluate('C!') == 0.
            assert istypeval(s.get_variable('D%'), 0)
            # unset array
            s.set_variable('A%()', [[0,0,5], [0,0,6]])
            assert s.get_variable('A%()') == [
                [0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 6, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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
            assert istypeval(s.convert(1, None), 1)
            # from_type == to_type
            assert istypeval(s.convert(1, int), 1)
            # cp437 string to unicode
            assert s.convert(b'\x00\x01\x9C\x86\xe0', unicode) == u'\x00\u263a\xa3\xe5\u03b1'
            # unicode to cp437
            assert s.convert(u'\x00\u263a\xa3\xe5\u03b1', bytes) == b'\x00\x01\x9C\x86\xe0'
            # int to bool
            assert istypeval(s.convert(0, bool), False)
            assert istypeval(s.convert(-1, bool), True)
            assert istypeval(s.convert(1, bool), True)
            # float to bool
            assert istypeval(s.convert(0., bool), False)
            assert istypeval(s.convert(-1., bool), True)
            # bool to int
            assert istypeval(s.convert(True, int), -1)
            assert istypeval(s.convert(False, int), 0)
            # bool to float
            assert istypeval(s.convert(True, float), -1.)
            assert istypeval(s.convert(False, float), 0.)
            assert isinstance(s.convert(True, float), float)
            # int to float
            assert istypeval(s.convert(1, float), 1.0)
            # float to int (floor)
            assert istypeval(s.convert(1.1, int), 1)
            assert istypeval(s.convert(-0.1, int), -1)
            # error
            with self.assertRaises(ValueError):
                s.convert(b'1', int)

    def test_session_getset_variable(self):
        """Test Session.set_variable and Session.get_variable."""
        with Session() as s:
            s.set_variable(b'A%', 1)
            assert istypeval(s.get_variable(b'A%'), 1)
            # bytes or unicode argument
            s.set_variable(u'A%', 2)
            assert istypeval(s.get_variable(b'A%'), 2)
            s.set_variable(u'A%', 3)
            assert istypeval(s.get_variable(u'A%'), 3)
            s.set_variable(u'A%', 3)
            assert istypeval(s.get_variable(b'A%'), 3)
            # undefined variable
            assert istypeval(s.get_variable('A!'), 0.)
            # sigil must be explicit
            with self.assertRaises(ValueError):
                s.set_variable('B', 0.)
            # sigil must be explicit
            with self.assertRaises(ValueError):
                s.get_variable('B', 0.)
            # boolean
            s.set_variable(b'A%', True)
            assert istypeval(s.get_variable(b'A%'), -1)
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
            # undefined array
            assert s.get_variable('A%()') == []
            # can't set array to empty
            with self.assertRaises(ValueError):
                s.set_variable('ARR2!()', [])

    def test_session_evaluate(self):
        """Test Session.set_variable and Session.get_variable."""
        with Session() as s:
            s.set_variable(b'A!', 1)
            assert s.evaluate(b'A') == 1
            assert s.evaluate(u'A') == 1
            # syntax error
            assert s.evaluate(b'LOG+1') is None

    def test_session_bind_file(self):
        """test Session.bind_file."""
        # open file object
        with open(self.output_path('testfile'), 'wb') as f:
            with Session() as s:
                name = s.bind_file(f)
                # can use name as string
                assert len(str(name)) <= 12
                # write to file
                s.execute('open "{0}" for output as 1: print#1, "x"'.format(name))
        with open(self.output_path('testfile'), 'rb') as f:
            output = f.read()
        assert output == b'x\r\n\x1a'
        # existing file by name
        with Session() as s:
            name = s.bind_file(self.output_path('testfile'))
            # write to file
            s.execute('open "{0}" for input as 1'.format(name))
            s.execute('input#1, a$')
            assert s.get_variable('A$') == b'x'
        # create file by name
        native_name = self.output_path(u'new-test-file')
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
        with Session(devices={b'Z': self.output_path()}) as s:
            name = s.bind_file(b'Z:TESTFILE')
            # write to file
            s.execute('open "{0}" for input as 1'.format(name))
            s.execute('input#1, a$')
            assert s.get_variable('A$') == b'x'
        # create file by name, provide BASIC name (bytes)
        native_name = self.output_path(u'new-test-file').encode('ascii')
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
        # create file by name, provide BASIC name (unicode)
        native_name = self.output_path(u'new-test-file')
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
            output = [_row.strip() for _row in self.get_text(s)]
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
        output = [_row.strip() for _row in self.get_text(s)]
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
        output = [_row.strip() for _row in self.get_text(s)]
        # \xff checked against DOSbox/GW-BASIC
        assert output[:3] == [b'0', b'Break\xff', b'Syntax error\xff']
        assert output[3:] == [b''] * 22

    def test_session_no_streams(self):
        """Test Session without stream copy."""
        with Session(input_streams=None, output_streams=None) as s:
            s.execute(b'a=1')
            s.execute(b'print a')
        output = self.get_text_stripped(s)
        assert output[:1] == [b' 1']

    def test_session_iostreams(self):
        """Test Session with copy to BytesIO."""
        bi = io.BytesIO()
        with Session(input_streams=None, output_streams=bi) as s:
            s.execute(b'a=1')
            s.execute(b'print a')
        assert bi.getvalue() == b' 1 \r\n'

    def test_session_inputstr_iostreams(self):
        """Test Session with INPUT$ reading from pipe."""
        bi = io.BytesIO(b'abc')
        with Session(input_streams=bi, output_streams=None) as s:
            abc = s.evaluate(b'input$(3)')
        assert abc == b'abc'

    def test_session_bad_type_iostreams(self):
        """Test Session with iostreams of incorrect type."""
        with self.assertRaises(TypeError):
            Session(input_streams=1).start()
        with self.assertRaises(TypeError):
            Session(output_streams=2).start()

    def test_session_printcopy(self):
        """Test Session with ctrl print-screen copy."""
        with Session(
                input_streams=None, output_streams=None,
                devices={'LPT1': 'FILE:{}'.format(self.output_path('print.txt'))}
            ) as s:
            # ctrl+printscreen
            s.press_keys(u'\0\x72')
            s.press_keys(u'system\r')
            s.interact()
        with open(self.output_path('print.txt'), 'rb') as f:
            output = f.read()
            assert output == b'system\r\n', repr(output)

    def test_session_no_printcopy(self):
        """Test Session switching off ctrl print-screen copy."""
        with Session(
                input_streams=None, output_streams=None,
                devices={'LPT1': 'FILE:{}'.format(self.output_path('print.txt'))}
            ) as s:
            # ctrl+printscreen
            s.press_keys(u'\0\x72\0\x72')
            s.press_keys(u'system\r')
            s.interact()
        with open(self.output_path('print.txt')) as f:
            assert f.read() == ''

    def test_gosub_from_direct_line(self):
        """Test for issue#184: GOSUB from direct line should not RETURN into program."""
        SOURCE = """\
        10 PRINT "Main"
        30 A = -42
        40 END
        50 PRINT "After End"
        60 A = 42
        70 RETURN
        """
        with Session() as session:
            session.execute(SOURCE)
            session.execute("GOSUB 60")
            assert session.evaluate('A') == 42

    def test_to_list_off_by_one(self):
        """Test for issue #182: range off by one in to_list."""
        with Session() as session:
            session.execute("""
            DIM J2(5,2)
            J2(1,1)=-1
            J2(1,2)=-1
            """)
            assert session.get_variable('J2!()') == [
                [0.0, 0.0, 0.0], [0.0, -1.0, -1.0], [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
            ]


from pcbasic.basic import iostreams
from pcbasic.basic.codepage import Codepage

class NonBlockingInputWrapperTest(TestCase):
    """Unit tests for NonBlockingInputWrapper."""

    tag = u'nonblockinginputwrapper'

    def test_read_lfcr(self):
        """Test read() with LF/CR conversion."""
        with io.open(self.output_path('inp.txt'), 'w') as f:
            f.write(u'12\n34')
        stream = io.open(self.output_path('inp.txt'), 'r')
        nbiw = iostreams.NonBlockingInputWrapper(stream, Codepage(), lfcr=True)
        assert nbiw.read() == u'12\r34'


if __name__ == '__main__':
    run_tests()
