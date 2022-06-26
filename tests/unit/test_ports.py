"""
PC-BASIC test.disk
Tests for disk devices

(c) 2020--2021 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import platform

from pcbasic import Session
from tests.unit.utils import TestCase, run_tests


class PortsTest(TestCase):
    """Parallel and serial ports tests."""

    tag = u'ports'

    def test_write_enabled(self):
        """Write to serial and parallel ports with writes enabled."""
        with Session(
            devices={b'COM1:': 'STDIO:CRLF', b'LPT1:': 'STDIO:CRLF'},
            enabled_writes=['parallel','serial'],
        ) as s:
            s.execute('open "com1:" for output as #1')
            s.execute('open "lpt1:" for output as #2')
            s.execute('print#1,"Hello "')
            s.execute('print#2,"world!"')
            output = [_row.strip() for _row in self.get_text(s)]
        assert output[:4] == [b'']*4

    def test_write_disabled(self):
        """Write to serial and parallel ports without writes enabled."""
        with Session(devices={b'COM1:': 'STDIO:CRLF', b'LPT1:': 'STDIO:CRLF'}) as s:
            s.execute('open "com1:" for output as #1')
            s.execute('open "lpt1:" for output as #2')
            s.execute('print#1,"Hello "')
            s.execute('print#2,"world!"')
            output = [_row.strip() for _row in self.get_text(s)]
        assert output[:2] == [b'Device I/O error\xff', b'Device I/O error\xff']


if __name__ == '__main__':
    run_tests()
