"""
PC-BASIC test.statements
unit tests for PC-BASIC specific behaviour of statements

(c) 2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from io import BytesIO
from tempfile import NamedTemporaryFile

from pcbasic import Session, run
from tests.unit.utils import TestCase, run_tests


class StatementTest(TestCase):
    """Unit tests for statements."""

    tag = u'statements'

    def test_llist(self):
        """Test LLIST to stream."""
        with NamedTemporaryFile() as output:
            with Session(devices={'lpt1': 'FILE:'+output.name}) as s:
                s.execute("""
                    10 rem program
                    20?1
                """)
                s.execute('LLIST')
            assert output.read() == b'10 REM program\r\n20 PRINT 1\r\n'


if __name__ == '__main__':
    run_tests()
