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
            os.mkdir(os.path.join(HERE, u'output', u'codepage'))
        except EnvironmentError:
            pass
        # create directory to mount
        self._test_dir = os.path.join(HERE, u'output', u'codepage', u'test_dir')
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

    def test_hello(self):
        """Hello world in 9 codepages."""
        hello = {
            # contains \u064b which is not in 720
            #'720': u'أهلاً بالعالم',
            '720': u'أهلا بالعالم',
            '737': u'Γεια σου κόσμε',
            '862': u'שלום עולם',
            '866': u'Здравствуй, мир',
            # combining graphemes \u0e27\u0e31 \u0e14\u0e35 are in codepage as separate chars
            # so converting to bytes fails
            #'874': u'สวัสดีโลก',
            #'874': u'\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35\u0e42\u0e25\u0e01',
            '932': u'こんにちは、 世界',
            '936': u'你好世界',
            '949': u'반갑다 세상아',
            'viscii': u'Xin chào thế giới',
        }
        # note that we're making a round-trip conversion unicode -> codepage -> unicode
        # this doesn't always work
        for cp, hi in hello.items():
            with open(self._output_path(hi), 'w') as f:
                f.write(hi)
            cp_dict = read_codepage(cp)
            with Session(
                    codepage=cp_dict, textfile_encoding='utf-8', devices={'c': self._test_dir},
                ) as s:
                s.execute(u'cls:print "{}"'.format(hi))

                #TODO: (api) should have an errors= option in convert?
                #TODO: (codepages) only perform grapheme clustering if the codepage has actual clusters in code points? (but: non-canonical combinations) override clustering if clustering elements in codepage?
                #cp_inv = {_v: _k for _k, _v in cp_dict.items()}
                #print repr(hi), repr(s.convert(hi, to_type=type(b''))), repr([cp_inv[x] for x in hi])

                s.execute(u'open "c:{}" for input as 1'.format(hi))
                s.execute('line input#1, a$')
                assert s.get_variable('a$', as_type=type(u'')) == hi
                output_unicode = [_row.strip() for _row in s.get_text(as_type=type(u''))]
                assert output_unicode[0] == hi


if __name__ == '__main__':
    unittest.main()
