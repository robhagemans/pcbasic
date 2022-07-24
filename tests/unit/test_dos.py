# -*- coding: utf-8 -*-

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
from pcbasic.basic import BASICError
from tests.unit.utils import TestCase, run_tests
from pcbasic.data import read_codepage


class DosTest(TestCase):
    """Unit tests for DOS module."""

    tag = u'dos'

    def test_shell(self):
        """Test SHELL statement with commands."""
        helper = os.path.join(os.path.dirname(__file__), 'simple_shell_helper.py')
        with Session(shell='/usr/bin/python3 ' + helper, codepage=read_codepage('850')) as s:
            # outputs come through stdout
            s.execute(u'SHELL "echo 1"')
            # test non-ascii char
            s.execute(u'SHELL "echo £"')
            # outputs come through stderr
            s.execute(u'SHELL "x"')
            # test non-ascii char
            s.execute(u'SHELL "£"')
        assert self.get_text_stripped(s)[:4] == [b'1', b'\x9c', b"'x' is not recognised.", b"'\x9c' is not recognised."]


    def test_shell_utf16(self):
        """Test SHELL statement to utf-16 script with commands."""
        helper = os.path.join(os.path.dirname(__file__), 'simple_shell_helper.py')
        with Session(shell='/usr/bin/python3 ' + helper + ' -u', codepage=read_codepage('850')) as s:
            # outputs come through stdout
            s.execute(u'SHELL "echo 1"')
            # test non-ascii char
            s.execute(u'SHELL "echo £"')
            # outputs come through stderr
            s.execute(u'SHELL "x"')
            # test non-ascii char
            s.execute(u'SHELL "£"')
        assert self.get_text_stripped(s)[:4] == [b'1', b'\x9c', b"'x' is not recognised.", b"'\x9c' is not recognised."]

    def test_no_shell(self):
        """Test SHELL statement with no shell specified."""
        with Session() as s:
        # assertRaises doesn't work as the error is absorbed by the session
        #with self.assertRaises(BASICError):
            s.execute(u'SHELL "echo 1"')
        assert self.get_text_stripped(s)[0] == b'Illegal function call\xff'

    def test_bad_shell(self):
        """Test SHELL statement with nonexistant shell specified."""
        with Session(shell='_this_does_not_exist_') as s:
            s.execute(u'SHELL "echo 1"')
        assert self.get_text_stripped(s)[0] == b'Illegal function call\xff'

    def test_interactive_shell(self):
        """Test SHELL statement with interaction."""
        helper = os.path.join(os.path.dirname(__file__), 'simple_shell_helper.py')
        with Session(shell='/usr/bin/python3 ' + helper, codepage=read_codepage('850')) as s:
            s.press_keys(u'echo _check_for_this_')
            # test backspace
            s.press_keys(u'\rexix\bt\r')
            s.execute(u'SHELL')
        # output is messy due to race between press_keys and shell thread, but this should work
        assert b'_check_for_this' in self.get_text_stripped(s)[1]

    def test_interactive_shell_no_lf_at_end(self):
        """Test SHELL statement with interaction, helper script ends without LF."""
        helper = os.path.join(os.path.dirname(__file__), 'simple_shell_helper.py')
        with Session(shell='/usr/bin/python3 ' + helper + ' -b') as s:
            s.press_keys(u'exit\r')
            s.execute(u'SHELL')
        assert self.get_text_stripped(s)[1] == b'Bye!'

    def test_environ(self):
        """Test ENVIRON statement."""
        with Session() as s:
            s.execute(u'ENVIRON "test=ok"')
            assert s.evaluate(u'ENVIRON$("test")') == b'ok'
            assert s.evaluate(u'ENVIRON$("TEST")') == b'ok'
            assert s.evaluate(u'ENVIRON$("Test")') == b'ok'
            s.execute(u'ENVIRON "TEST=OK"')
            assert s.evaluate(u'ENVIRON$("test")') == b'OK'
            assert s.evaluate(u'ENVIRON$("TEST")') == b'OK'
            assert s.evaluate(u'ENVIRON$("Test")') == b'OK'

    def test_environ_noascii_key(self):
        """Test ENVIRON statement with non-ascii key."""
        with Session() as s:
            s.execute(u'ENVIRON "t£st=ok"')
            assert self.get_text_stripped(s)[0] == b'Illegal function call\xff'

    def test_environ_fn_noascii_key(self):
        """Test ENVIRON$ function with non-ascii key."""
        with Session() as s:
            s.evaluate(u'ENVIRON$("t£st")')
            assert self.get_text_stripped(s)[0] == b'Illegal function call\xff'

    def test_environ_noascii_value(self):
        """Test ENVIRON statement with non-ascii values."""
        with Session() as s:
            s.execute(u'ENVIRON "TEST=£"')
            assert self.get_text_stripped(s)[0] == b''


if __name__ == '__main__':
    run_tests()
