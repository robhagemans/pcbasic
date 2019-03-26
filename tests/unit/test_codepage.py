# -*- coding: utf-8 -*-

"""
PC-BASIC test.codepage
codepage functionality tests

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import shutil
from io import open

from pcbasic import Session, run
from pcbasic.data import read_codepage

HERE = os.path.dirname(os.path.abspath(__file__))


class SessionTest(unittest.TestCase):
    """Unit tests for Session."""

    def setUp(self):
        """Ensure output directory exists."""
        try:
            os.mkdir(os.path.join(HERE, u'output', u'disk'))
        except EnvironmentError:
            pass
        # create directory to mount
        self._test_dir = os.path.join(HERE, u'output', u'disk', u'test_dir')
        try:
            shutil.rmtree(self._test_dir)
        except EnvironmentError:
            pass
        os.mkdir(self._test_dir)

    def _output_path(self, *name):
        """Test output file name."""
        return os.path.join(self._test_dir, *name)

    def test_box(self):
        """Test box protection."""
        cp_936 = read_codepage('936')
        with Session(
                codepage=cp_936, box_protect=True, textfile_encoding='utf-8',
                devices={'c': self._test_dir},
            ) as s:
            # to file
            s.execute('open "c:boxtest.txt" for output as 1')
            s.execute('PRINT#1, CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # to screen
            s.execute('PRINT CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # bytes text
            output_bytes = [_row.strip() for _row in s.get_text()]
            # unicode text
            output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
        with open(self._output_path('BOXTEST.TXT'), 'r') as f:
            assert f.read() == u'\ufeff┌──────────┐\n\x1a'
        assert output_bytes[0] == b'\xda\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xbf'
        assert output_unicode[0] == u'┌──────────┐'
        print

    def test_nobox(self):
        """Test no box protection."""
        cp_936 = read_codepage('936')
        with Session(
                codepage=cp_936, box_protect=False, textfile_encoding='utf-8',
                devices={'c': self._test_dir},
            ) as s:
            s.execute('open "c:boxtest.txt" for output as 1')
            s.execute('PRINT#1, CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # to screen
            s.execute('PRINT CHR$(218);STRING$(10,CHR$(196));CHR$(191)')
            # bytes text
            # bytes text
            output_bytes = [_row.strip() for _row in s.get_text()]
            # unicode text
            output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
        with open(self._output_path('BOXTEST.TXT'), 'r') as f:
            assert f.read() == u'\ufeff谀哪哪哪哪目\n\x1a'
        assert output_bytes[0] == b'\xda\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xbf'
        assert output_unicode[0] == u'谀哪哪哪哪目'


if __name__ == '__main__':
    unittest.main()
