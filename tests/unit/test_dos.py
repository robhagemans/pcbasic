"""
PC-BASIC test.session
unit tests for session API

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import io

from pcbasic import Session
from pcbasic.basic.debug import DebugSession
from tests.unit.utils import TestCase, run_tests
from pcbasic.data import read_codepage


class DosTest(TestCase):
    """Unit tests for DOS module."""

    tag = u'dos'

    def test_session(self):
        """Test basic Session API."""
        helper = os.path.join(os.path.dirname(__file__), 'simple_shell_helper.py')
        with Session(shell='/usr/bin/python3 ' + helper, codepage=read_codepage('850')) as s:
            # utputs come through stdout
            s.execute(u'SHELL "echo 1"')
            # test non-ascii char
            s.execute(u'SHELL "echo £"')
            # outputs coe through stderr
            s.execute(u'SHELL "x"')
            # test non-ascii char
            s.execute(u'SHELL "£"')
        assert self.get_text_stripped(s)[:4] == [b'1', b'\x9c', b"'x' is not recognised.", b"'\x9c' is not recognised."]


if __name__ == '__main__':
    run_tests()
