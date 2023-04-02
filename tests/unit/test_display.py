"""
PC-BASIC test_display
unit tests for display features of Session API

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import unittest
import os

from pcbasic import Session
from pcbasic.compat import int2byte
from tests.unit.utils import TestCase, run_tests


class DisplayTest(TestCase):
    """Unit tests for display."""

    tag = u'display'

    def test_pixels(self):
        """Display all characters in default font."""
        with Session() as s:
            s.execute(b'''
                10 KEY OFF: SCREEN 0: WIDTH 80: CLS
                20 DEF SEG = &HB800
                30 FOR B = 0 TO 255
                40   POKE 2*B, B
                50 NEXT
                RUN
            ''')
            with open(self.model_path('pixels.bin'), 'rb') as model:
                model_pix = model.read()
            assert bytes(bytearray(_c for _r in s.get_pixels() for _c in _r)) == model_pix

    def test_characters(self):
        """Display all characters."""
        with Session() as s:
            s.execute(b'''
                10 KEY OFF: SCREEN 0: WIDTH 80: CLS
                20 DEF SEG = &HB800
                30 FOR B = 0 TO 255
                40   POKE 2*B, B
                50 NEXT
                RUN
            ''')
            with open(self.model_path('characters.bin'), 'rb') as model:
                model_chars = model.read()
            assert bytes(bytearray(_c for _r in self.get_text(s) for _c in _r)) == model_chars


if __name__ == '__main__':
    run_tests()
