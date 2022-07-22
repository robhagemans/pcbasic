"""
PC-BASIC test.program
Tests for programs

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os
import shutil
import platform

from pcbasic import Session


HERE = os.path.dirname(os.path.abspath(__file__))


class DiskTest(unittest.TestCase):
    """Disk tests."""

    def setUp(self):
        """Ensure output directory exists."""
        try:
            os.mkdir(os.path.join(HERE, u'output', u'program'))
        except EnvironmentError:
            pass
        # create directory to mount
        self._test_dir = os.path.join(HERE, u'output', u'program', u'test_dir')
        try:
            shutil.rmtree(self._test_dir)
        except EnvironmentError:
            pass
        os.mkdir(self._test_dir)

    def _output_path(self, *name):
        """Test output file name."""
        return os.path.join(self._test_dir, *name)

    def test_unprotect(self):
        """Save in protected format to a file, load in plaintext."""
        plaintext = b'60 SAVE "test.bin"\r\n70 SAVE "test.asc",A\r\n80 LIST,"test.lst"\r\n'
        tokenised = (
            b'\xff\x7f\x12<\x00\xbe "test.bin"\x00\x92\x12F\x00\xbe '
            b'"test.asc",A\x00\xa3\x12P\x00\x93,"test.lst"\x00\x00\x00\x1a'
        )
        protected = (
            b'\xfe\xd0\xa9\x81T\xed\x12\xbd} f\x15\xd0\xf0:\x99\xc3\xb2!\x01(\x13\xe2\x8c%J\x91'
            b'\xf0\x81S\xf2IR%f\x0f\xc4\xd6\xc8H\xbf{\xf8_c\xcb<\xd2\x82\xd4\x04j\xd3\x06\xfa\x05'
            b'\x1a'
        )
        with Session(devices={b'A': self._test_dir}, current_device='A:') as s:
            s.execute(plaintext)
            s.execute('save "prog",P')
        with Session(devices={b'A': self._test_dir}, current_device='A:') as s:
            # the program saves itself as plaintext and tokenised
            # in gw-basic, illegal funcion call.
            s.execute('run "prog"')
        with open(self._output_path('PROG.BAS'), 'rb') as f:
            assert f.read() == protected
        with open(self._output_path('TEST.BIN'), 'rb') as f:
            assert f.read() == tokenised
        with open(self._output_path('TEST.ASC'), 'rb') as f:
            assert f.read() == plaintext + b'\x1a'
        # execution stops after save,a !
        assert not os.path.isfile(self._output_path('TEST.LST'))


    def test_program_repr(self):
        """Test Program.__repr__."""
        with Session() as s:
            s.execute("""
                10 ' test
                20 print "test"
            """)
            assert repr(s._impl.program) == (
                '00 7b12 (+013) 0a00 [00010] 3a8fd9207465737400881214009120227465737422000000\n'
                '00 8812 (+013) 1400 [00020] 9120227465737422000000\n'
                '00 0000 (ENDS)  '
            ), repr(repr(s._impl.program))




if __name__ == '__main__':
    unittest.main()
