"""
PC-BASIC test.statements
unit tests for PC-BASIC specific behaviour of statements

(c) 2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from io import BytesIO
from tempfile import NamedTemporaryFile

from pcbasic import Session
from tests.unit.utils import TestCase, run_tests


class StatementTest(TestCase):
    """Unit tests for statements."""

    tag = u'statements'

    def test_llist(self):
        """Test LLIST to stream."""
        with NamedTemporaryFile(delete=False) as output:
            with Session(devices={'lpt1': 'FILE:'+output.name}) as s:
                s.execute("""
                    10 rem program
                    20?1
                """)
                s.execute('LLIST')
            outstr = output.read()
            assert outstr == b'10 REM program\r\n20 PRINT 1\r\n', outstr

    def test_cls_pcjr(self):
        """Test CLS syntax on pcjr."""
        with Session(syntax='pcjr') as s:
            s.execute('CLS')
            assert self.get_text_stripped(s)[0] == b''
            s.execute('CLS 0')
            assert self.get_text_stripped(s)[0] == b'Syntax error\xFF'
            s.execute('CLS 0,')
            assert self.get_text_stripped(s)[0] == b'Syntax error\xFF'
            s.execute('CLS ,')
            assert self.get_text_stripped(s)[0] == b'Syntax error\xFF'

    def test_wait(self):
        """Test WAIT syntax."""
        with Session(syntax='pcjr') as s:
            s.execute('')
            s._impl.keyboard.last_scancode = 255
            s.execute('wait &h60, 255')
            s._impl.keyboard.last_scancode = 0
            s.execute('wait &h60, 255, 255')
            assert self.get_text_stripped(s)[0] == b''

if __name__ == '__main__':
    run_tests()
